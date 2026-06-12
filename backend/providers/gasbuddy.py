"""
GasBuddy station-level realtime prices (PRIMARY price source where reachable).

Backed by the maintained `py-gasbuddy` library, which speaks GasBuddy's GraphQL
API with the now-required ``gbcsrf`` CSRF token (fetched from ``/home``), retry +
exponential backoff, and on-disk token caching. py-gasbuddy is async; this module
exposes a thin *synchronous* facade (``search``, ``region_low_station``,
``get_station``) so the rest of the (sync) pipeline is unchanged.

Cloudflare: GasBuddy sits behind Cloudflare's interactive JS challenge. From a
residential host the API is typically reachable; from hardened datacenter IPs it
is blocked. Set ``GASBUDDY_SOLVER_URL`` (a FlareSolverr-compatible endpoint) to
route token acquisition through a solver. Everything here is best-effort —
callers MUST treat ``None`` as "GasBuddy unavailable" and fall back to
EIA / NRCAN / baseline.

Units: US stations report regular gasoline in **$/gal**; Canadian stations report
in **¢/L**. ``region_low_station`` normalizes Canadian prices to **$/L** by
dividing by 100 exactly once (see ``is_canada``).
"""
import asyncio
import concurrent.futures
import logging

import cache
import config

try:
    import py_gasbuddy as _gb
    _HAVE_LIB = True
except Exception:                                  # pragma: no cover - env dependent
    _gb = None
    _HAVE_LIB = False

log = logging.getLogger(__name__)

STATION_URL = "https://www.gasbuddy.com/station/{id}"

# Regular gasoline == fuel product 1 in GasBuddy's schema.
_REGULAR_FUEL = 1
# Stations to pull per region before picking the cheapest.
_SEARCH_LIMIT = 15

_SOLVER_URL = config.GASBUDDY_SOLVER_URL or None
_TOKEN_CACHE = str(config.GASBUDDY_TOKEN_CACHE)


def _run(coro):
    """Run an async coroutine from sync code, tolerating an active event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)          # no loop running — the common path
    # Already inside an event loop (e.g. called from async code): run the
    # coroutine to completion in a dedicated worker thread.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


def _client(station_id: int | None = None):
    return _gb.GasBuddy(
        station_id=station_id,
        solver_url=_SOLVER_URL,
        cache_file=_TOKEN_CACHE,
    )


def _regular_price(station: dict) -> float | None:
    """Lowest posted regular price (credit preferred, else cash) for a station."""
    node = station.get("regular_gas") or {}
    for key in ("price", "cash_price"):
        val = node.get(key)
        if val not in (None, 0, "0"):
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None


def _normalize(station: dict) -> dict | None:
    """Normalize a py-gasbuddy station dict; price kept in its native unit."""
    sid = station.get("station_id")
    price = _regular_price(station)
    if sid is None or price is None:
        return None
    addr = station.get("address") or {}
    lat = station.get("latitude")
    lng = station.get("longitude")
    return {
        "station_id": str(sid),
        "name": station.get("name") or "",
        "lat": float(lat) if lat is not None else None,
        "lng": float(lng) if lng is not None else None,
        "price_raw": price,
        "price_unit": station.get("unit_of_measure"),
        "locality": addr.get("locality"),
        "region": addr.get("region"),
        "url": STATION_URL.format(id=sid),
    }


def search(search_term: str | None = None, lat: float | None = None,
           lng: float | None = None) -> list[dict] | None:
    """
    Search regular-gas stations near ``lat``/``lng`` via py-gasbuddy.

    Returns a list of normalized stations (native price unit), or None when
    GasBuddy is unreachable. ``search_term`` is accepted for backwards
    compatibility and logging only — py-gasbuddy queries by coordinates.
    """
    if not _HAVE_LIB:
        log.debug("py-gasbuddy not installed; GasBuddy disabled")
        return None
    if lat is None or lng is None:
        log.debug("GasBuddy search needs coordinates (search_term=%r)", search_term)
        return None
    try:
        result = _run(
            _client().price_lookup_service(
                lat=lat, lon=lng, fuel=_REGULAR_FUEL, limit=_SEARCH_LIMIT,
            )
        )
    except Exception as e:                          # CloudflareBlocked, APIError, …
        log.debug("GasBuddy search failed (%s, %s): %s", lat, lng, e)
        return None
    # py-gasbuddy 0.7 returns {"results": [station, ...]}. Be defensive about the
    # exact shape: a future/library change (or a Cloudflare interstitial slipping
    # through as a non-dict body) must degrade to "no data", never throw.
    if not isinstance(result, dict):
        log.warning("GasBuddy returned unexpected type %s; treating as no data",
                    type(result).__name__)
        return None
    results = result.get("results")
    if results is None:
        return []                                   # well-formed response, no stations
    if not isinstance(results, list):
        log.warning("GasBuddy 'results' was %s, expected list; treating as no data",
                    type(results).__name__)
        return []
    return [n for s in results if isinstance(s, dict) and (n := _normalize(s))]


def get_station(station_id: str) -> dict | None:
    """Fetch a single station (used to refresh coords/price for the deep link)."""
    if not _HAVE_LIB:
        return None
    try:
        station = _run(_client(station_id=int(station_id)).price_lookup())
    except Exception as e:
        log.debug("GasBuddy get_station failed for %s: %s", station_id, e)
        return None
    if not isinstance(station, dict) or station.get("error"):
        return None
    return _normalize(station)


def region_low_station(region_id: str, search_term: str, is_canada: bool,
                       lat: float | None = None, lng: float | None = None) -> dict | None:
    """
    Find the lowest-price regular-gas station for a region's reference area.

    Returns a dict for the cheapest station with price normalized to the region's
    unit ($/gal for US, $/L for CA) plus the full station list, or None when
    GasBuddy is unavailable. Coordinates default to the region's reference city
    (``config.REGION_COORDS``). Cached per region for TTL_GASBUDDY.
    """
    cache_key = f"gasbuddy_low:{region_id}"
    hit = cache.get(cache_key)
    if hit is not None:
        return hit or None   # cached empty -> None

    if lat is None or lng is None:
        coords = config.REGION_COORDS.get(region_id)
        if coords:
            lat, lng = coords

    stations = search(search_term=search_term, lat=lat, lng=lng)
    if not stations:
        # Cache a negative sentinel ({}) so a Cloudflare-blocked or genuinely
        # empty region short-circuits on the next run instead of re-hitting the
        # network every cycle (datacenter IPs are blocked for every region —
        # ~62 doomed round-trips/30 min without this). The `hit or None` read
        # above treats the empty dict as "no data". Same TTL as the hit path.
        cache.set(cache_key, {}, ttl=cache.TTL_GASBUDDY)
        return None

    def to_region_unit(raw: float) -> float:
        return round(raw / 100.0, 3) if is_canada else round(raw, 3)

    priced = [{**s, "price": to_region_unit(s["price_raw"])} for s in stations]
    priced.sort(key=lambda s: s["price"])
    low = priced[0]

    result = {
        "station_id": low["station_id"],
        "name": low["name"],
        "price": low["price"],
        "lat": low["lat"],
        "lng": low["lng"],
        "url": low["url"],
        "unit": "L" if is_canada else "gal",
        "all_prices": [s["price"] for s in priced],
    }
    cache.set(cache_key, result, ttl=cache.TTL_GASBUDDY)
    return result
