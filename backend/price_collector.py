"""
Part 1 — Price Collector (runs every 30 minutes).

Pulls current gasoline prices for all regions, computes regional medians and
lows, stores raw station data in SQLite, and updates regional_snapshot rows.

Run directly:
    cd shouldigetgas
    python backend/price_collector.py [--regions ca tx on]
"""
import sys
import re
import json
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

# allow running from repo root or from backend/
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

import db
import cache
from providers import gasbuddy, http_client
from config import (
    EIA_API_KEY, EIA_GAS_ENDPOINT,
    US_REGIONS, CA_REGIONS, BASELINE_PRICES, PADD_DUOAREA,
    NRCAN_PRICE_URL, ONTARIO_FUEL_API, ONTARIO_RESOURCE_ID,
    is_canadian, region_unit,
)

log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "shouldigetgas/1.0 (+https://shouldigetgas.com)"})

NOW = lambda: datetime.now(timezone.utc).isoformat()


# ── EIA — US state weekly prices ─────────────────────────────────────────────

def fetch_eia_state_prices(state_ids: list[str]) -> dict[str, list[float]]:
    """
    Fetch last 14 weeks of regular gasoline prices per US state from EIA API v2.
    Uses duoarea facets with "S" prefix (e.g. "SCA" for California).
    Returns {state_id_upper: [price_newest_first]}.
    Falls back to EIA PADD districts if state-level data is missing.
    """
    if not EIA_API_KEY:
        log.warning("EIA_API_KEY not set — skipping EIA price fetch")
        return {}

    cache_key = "eia_state_prices:" + ",".join(sorted(state_ids))
    hit = cache.get(cache_key)
    if hit:
        return hit

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[product][]": "EPMR",    # regular gasoline (not EPM0 = all grades)
        "facets[process][]": "PTE",     # retail price (taxes incl.)
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": "14",
        "offset": "0",
    }
    # EIA v2 requires repeated keys for array facets (not indexed notation)
    param_list = list(params.items())
    for sid in state_ids:
        param_list.append(("facets[duoarea][]", f"S{sid}"))

    try:
        resp = SESSION.get(EIA_GAS_ENDPOINT, params=param_list, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("response", {}).get("data", [])
    except Exception as e:
        log.error("EIA state prices fetch failed: %s", e)
        return {}

    result: dict[str, list[float]] = {}
    for row in data:
        sid   = row.get("duoarea", "")[1:].upper()   # strip leading "S" prefix
        value = row.get("value")
        if sid and value is not None:
            try:
                result.setdefault(sid, []).append(float(value))
            except (ValueError, TypeError):
                pass

    # Deduplicate — newest first already from sort
    cache.set(cache_key, result, ttl=cache.TTL_EIA_WEEKLY)
    return result


def fetch_eia_padd_prices(padd_codes: list[str]) -> dict[str, list[float]]:
    """
    Fallback: fetch PADD district weekly prices from EIA for regions with no
    state-level data.

    Returns {padd_code: [price_newest_first]} keyed by the *requested* "P#"
    codes. The EIA `gnd` dataset addresses PADD districts as duoarea "R10".."R50"
    (the "P1".."P5" codes return zero rows), so we translate via PADD_DUOAREA on
    the way out and map the response back to the caller's "P#" code.
    """
    if not EIA_API_KEY:
        return {}

    cache_key = "eia_padd:" + ",".join(sorted(padd_codes))
    hit = cache.get(cache_key)
    if hit:
        return hit

    # Translate P# -> R## for the EIA query, remembering the reverse mapping.
    duoarea_to_padd = {
        PADD_DUOAREA[p]: p for p in padd_codes if p in PADD_DUOAREA
    }
    if not duoarea_to_padd:
        return {}

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[product][]": "EPMR",    # regular gasoline (not EPM0 = all grades)
        "facets[process][]": "PTE",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": "14",
    }
    param_list = list(params.items())
    for duoarea in duoarea_to_padd:
        param_list.append(("facets[duoarea][]", duoarea))

    try:
        resp = SESSION.get(EIA_GAS_ENDPOINT, params=param_list, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("response", {}).get("data", [])
    except Exception as e:
        log.error("EIA PADD prices fetch failed: %s", e)
        return {}

    result: dict[str, list[float]] = {}
    for row in data:
        area  = row.get("duoarea", "")
        value = row.get("value")
        padd  = duoarea_to_padd.get(area)
        if padd and value is not None:
            try:
                result.setdefault(padd, []).append(float(value))
            except (ValueError, TypeError):
                pass

    cache.set(cache_key, result, ttl=cache.TTL_EIA_WEEKLY)
    return result


# ── GasBuddy — station-level prices ──────────────────────────────────────────

def fetch_gasbuddy_region(region_id: str, city: str, abbr: str,
                          is_canada: bool = False) -> dict | None:
    """
    Look up the lowest-price regular-gas station for a region via GasBuddy.

    Returns the normalized low-station dict from ``gasbuddy.region_low_station``
    (``{station_id, name, price, lat, lng, url, unit, all_prices}``) with the
    price already in the region's unit, or None when GasBuddy is unavailable.
    """
    search_term = f"{city}, {abbr}"
    try:
        return gasbuddy.region_low_station(region_id, search_term, is_canada)
    except Exception as e:
        log.debug("GasBuddy lookup failed for %s (%s): %s", region_id, search_term, e)
        return None


# ── Canadian prices ──────────────────────────────────────────────────────────

def fetch_ontario_prices() -> dict[str, float] | None:
    """
    Pull Ontario fuel price survey data from data.ontario.ca CKAN API.
    Returns {city: price_in_cpl} or None.
    """
    cache_key = "ontario_prices"
    hit = cache.get(cache_key)
    if hit:
        return hit

    try:
        resp = SESSION.get(
            ONTARIO_FUEL_API,
            params={"resource_id": ONTARIO_RESOURCE_ID, "limit": 100, "sort": "Date desc"},
            timeout=20,
        )
        resp.raise_for_status()
        records = resp.json().get("result", {}).get("records", [])
        if not records:
            return None
        prices = {}
        for r in records:
            city  = r.get("Municipality") or r.get("City", "")
            price = r.get("Regular") or r.get("Regular_Grade_Gasoline")
            if city and price:
                try:
                    prices[city] = float(price)
                except (ValueError, TypeError):
                    pass
        result = prices if prices else None
        if result:
            cache.set(cache_key, result, ttl=cache.TTL_EIA_WEEKLY)
        return result
    except Exception as e:
        log.debug("Ontario CKAN fetch failed: %s", e)
        return None


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch_nrcan_prices() -> dict[str, list[float]] | None:
    """
    Scrape the NRCAN Fuel Price Monitor "prices by city" table.

    The table is a wide pump-price-components grid: one "Day of" date column
    followed by, for each tracked city, four sub-columns (Price, Taxes, Marketing
    Margin, Refining Margin) in ¢/L. We extract each city's daily *Price* series
    and convert to $/L.

    Returns {city: [price_$L oldest→newest]} (including the "Canada" national
    average), or None on failure.
    """
    cache_key = "nrcan_prices"
    hit = cache.get(cache_key)
    if hit:
        return hit

    try:
        from bs4 import BeautifulSoup
        resp = http_client.get(NRCAN_PRICE_URL, impersonate=False)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table")
        if table is None:
            return None
        rows = [[c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                for r in table.find_all("tr")]

        # City header row: the one that contains the "Canada" column label.
        cities: list[str] = []
        for cells in rows:
            if "Canada" in cells:
                cities = [c for c in cells if c]   # drop the empty corner cell
                break
        if not cities:
            return None

        # Layout: col 0 = date; city i's Price column = 1 + i*4.
        history: dict[str, list[float]] = {c: [] for c in cities}
        for cells in rows:
            if not cells or not _DATE_RE.match(cells[0]):
                continue
            for i, city in enumerate(cities):
                col = 1 + i * 4
                if col >= len(cells):
                    continue
                raw = cells[col].replace(",", ".")
                try:
                    price = float(raw) / 100.0          # ¢/L → $/L
                except (ValueError, TypeError):
                    continue
                if 0.5 <= price <= 3.5:                 # plausible CA pump $/L
                    history[city].append(round(price, 3))

        history = {c: s for c, s in history.items() if s}
        if not history:
            return None
        cache.set(cache_key, history, ttl=cache.TTL_EIA_WEEKLY)
        return history
    except Exception as e:
        log.debug("NRCAN scrape failed: %s", e)
        return None


# City → province mapping for NRCAN data aggregation.
# (The current NRCAN "by city" view publishes Calgary, Halifax, Toronto + the
# Canada national average; the rest are kept for resilience if more cities appear.)
NRCAN_CITY_PROVINCE = {
    "Calgary": "ab", "Edmonton": "ab",
    "Vancouver": "bc", "Victoria": "bc",
    "Winnipeg": "mb",
    "Moncton": "nb", "Saint John": "nb",
    "St. John's": "nl",
    "Halifax": "ns",
    "Toronto": "on", "Ottawa": "on", "Thunder Bay": "on",
    "Charlottetown": "pe",
    "Montreal": "qc", "Quebec City": "qc",
    "Regina": "sk", "Saskatoon": "sk",
    "Whitehorse": "north", "Yellowknife": "north",
}


def aggregate_nrcan_by_province(nrcan: dict[str, list[float]]) -> dict[str, list[float]]:
    """
    Reduce NRCAN city price series to province-level series.

    Input/output values are $/L. When several cities map to one province their
    series are element-wise medianed (aligned to the shortest series).
    """
    buckets: dict[str, list[list[float]]] = {}
    for city, series in nrcan.items():
        prov = NRCAN_CITY_PROVINCE.get(city)
        if prov and series:
            buckets.setdefault(prov, []).append(series)

    out: dict[str, list[float]] = {}
    for prov, series_list in buckets.items():
        n = min(len(s) for s in series_list)
        aligned = [s[-n:] for s in series_list]
        out[prov] = [round(statistics.median(vals), 3) for vals in zip(*aligned)]
    return out


# ── Compute regional aggregate ────────────────────────────────────────────────

def compute_region_prices(
    region_id: str,
    raw_prices: list[float],
    gasbuddy: dict | None,
    source: str,
) -> dict:
    """
    Assemble the price fields for a US regional_snapshot from a weekly EIA series.

    `raw_prices` is the weekly series, newest-first (state or PADD). GasBuddy, when
    available, becomes the realtime *headline* price and the lowest-station source,
    but the 14-day `trend` and `week_delta` always come from the weekly EIA series
    so the sparkline reflects real movement. `source` is the series provenance
    ("eia_state" | "eia_padd" | "baseline").
    """
    has_series = bool(raw_prices)
    # raw_prices[0] is the newest weekly point — the current price. (Using a
    # median of the last 3 weeks would surface an older, laggier value.)
    series_price = round(raw_prices[0], 3) if has_series else None

    # Week-over-week from the weekly series: this week's level vs ~one week back.
    if has_series and len(raw_prices) >= 2:
        week_delta = round(raw_prices[0] - raw_prices[1], 3)
    else:
        week_delta = 0.0

    trend = interpolate_to_daily(raw_prices[:14]) if has_series else []

    # GasBuddy (realtime, station-level) is the PRIMARY headline price when present.
    price_source = source
    low_station  = None
    if gasbuddy and gasbuddy.get("price"):
        price        = round(gasbuddy["price"], 3)
        price_low    = round(gasbuddy["price"], 3)
        price_source = "gasbuddy"
        low_station  = gasbuddy
    elif has_series:
        price     = series_price
        price_low = round(min(raw_prices[:3]), 3)
    else:
        return {}

    if not trend:
        trend = [round(price, 3)] * 14

    return {
        "price":        price,
        "price_low":    price_low,
        "week_delta":   week_delta,
        "trend":        trend,
        "price_source": price_source,
        "low_station":  low_station,
    }


def interpolate_to_daily(weekly_prices: list[float]) -> list[float]:
    """
    Convert up-to-14 weekly price points (newest first) to a 14-point daily
    array by linear interpolation. Returns newest last (left→right = past→now).
    """
    if not weekly_prices:
        return []
    # Reverse so index 0 = oldest
    pts = list(reversed(weekly_prices))
    # Expand each weekly gap (~7 days) to daily via lerp
    daily: list[float] = []
    for i in range(len(pts) - 1):
        start, end = pts[i], pts[i + 1]
        for d in range(7):
            daily.append(round(start + (end - start) * d / 7, 3))
    daily.append(round(pts[-1], 3))
    # Return last 14 data points
    return daily[-14:] if len(daily) >= 14 else daily


# ── Main collection loop ──────────────────────────────────────────────────────


# ── Price sanity check ────────────────────────────────────────────────────────

def _sanity_check_price(
    region_id: str,
    new_price: float,
    baseline: float | None,
    prev_price: float | None,
) -> float:
    """
    Validate that new_price is within ±50% of the baseline.
    If it fails the check, log a warning and return the previous stored price
    (or the baseline itself) instead of the new value.
    """
    if baseline is None:
        return new_price   # no baseline — nothing to check against

    lo = baseline * 0.50
    hi = baseline * 1.50
    if lo <= new_price <= hi:
        return new_price

    fallback = prev_price if prev_price is not None else baseline
    log.warning(
        "Price sanity check FAILED for %s: fetched $%.3f is outside \u00b150%% of "
        "baseline $%.3f (allowed range $%.3f\u2013$%.3f). Using fallback $%.3f.",
        region_id, new_price, baseline, lo, hi, fallback,
    )
    return fallback


def collect_us_prices(region_subset: list[str] | None = None):
    """
    Fetch and store US state prices.

    Provider precedence per region: GasBuddy (realtime, station-level) for the
    headline price, with the EIA state weekly series (or PADD district fallback)
    always providing the trend/week_delta backbone; baseline only as last resort.
    """
    targets = [r for r in US_REGIONS if region_subset is None or r[0] in region_subset]
    state_ids = [r[4] for r in targets]   # EIA stateid column

    log.info("Fetching EIA prices for %d US states", len(state_ids))
    current  = fetch_eia_state_prices(state_ids)

    now_ts = NOW()
    for r_id, state, abbr, city, eia_sid, padd in targets:
        source = "eia_state"
        prices = current.get(eia_sid.upper(), [])
        if not prices:
            # Try PADD district fallback (real, weekly-moving regional series)
            padd_data = fetch_eia_padd_prices([padd])
            prices    = padd_data.get(padd, [])
            source    = "eia_padd"

        if not prices:
            # Final fallback: static baseline
            base   = BASELINE_PRICES.get(r_id)
            prices = [base] if base else []
            source = "baseline"
            log.debug("Using baseline price for %s", r_id)

        if not prices:
            continue

        # A PADD district is a multi-state regional average (e.g. P5 West Coast is
        # dominated by California), so its absolute level can be far from a given
        # state's. Anchor the series to the state's baseline level while preserving
        # its real week-to-week movement — otherwise the ±50% sanity check below
        # would reject every reading and flatten the trend to baseline.
        if source == "eia_padd":
            base   = BASELINE_PRICES.get(r_id)
            mean_p = statistics.mean(prices) if prices else 0
            if base and mean_p:
                ratio  = base / mean_p
                prices = [round(v * ratio, 3) for v in prices]

        # Sanity-check all price readings so anomalous values in prices[1]/[2]
        # cannot skew the median (or week_delta) computed from raw_prices[:3].
        baseline   = BASELINE_PRICES.get(r_id)
        snap       = db.get_snapshot(r_id)
        prev_price = snap["price"] if snap and snap.get("price") else None
        prices = [
            _sanity_check_price(r_id, p, baseline, prev_price) for p in prices
        ]

        # GasBuddy realtime station-level lookup (primary headline price + low).
        gb = fetch_gasbuddy_region(r_id, city, abbr, is_canada=False)

        agg = compute_region_prices(r_id, prices, gb, source)
        if not agg:
            continue

        # Store the headline price as a station reading for daily-history trend.
        db.store_station_price(
            region_id=r_id, price=agg["price"], unit="gal",
            city=city, fetched_at=now_ts
        )

        db.upsert_snapshot(r_id, {
            "state":  state,
            "abbr":   abbr,
            "city":   city,
            "country": "US",
            "unit":   "gal",
            "price":        agg["price"],
            "price_low":    agg["price_low"],
            "week_delta":   agg["week_delta"],
            "trend":        agg["trend"],
            "price_source": agg["price_source"],
            "low_station":  agg["low_station"],
            "prices_updated_at": now_ts,
        })
        log.info("Updated %s: $%.3f/gal (Δ%+.3f) [%s]",
                 r_id, agg["price"], agg["week_delta"], agg["price_source"])


def _fields_from_daily_series(daily: list[float], gasbuddy: dict | None,
                              base_source: str) -> dict:
    """
    Build price fields from a daily $/L series (oldest→newest), overlaying a
    GasBuddy realtime headline price when available.
    """
    price        = round(daily[-1], 3)
    price_source = base_source
    price_low    = round(price * 0.97, 3)   # estimate when no station-level data
    low_station  = None

    if gasbuddy and gasbuddy.get("price"):
        price        = round(gasbuddy["price"], 3)
        price_low    = round(gasbuddy["price"], 3)
        price_source = "gasbuddy"
        low_station  = gasbuddy

    trend = [round(v, 3) for v in daily[-14:]]
    while len(trend) < 14:
        trend = [trend[0]] + trend

    if len(daily) >= 8:
        week_delta = round(daily[-1] - daily[-8], 3)
    elif len(daily) >= 2:
        week_delta = round(daily[-1] - daily[0], 3)
    else:
        week_delta = 0.0

    return {
        "price":        price,
        "price_low":    price_low,
        "week_delta":   week_delta,
        "trend":        trend,
        "price_source": price_source,
        "low_station":  low_station,
    }


def collect_canada_prices(region_subset: list[str] | None = None):
    """
    Fetch and store Canadian provincial prices.

    Provider precedence per province: GasBuddy (realtime, station-level) headline
    price; NRCAN daily city series for the trend/week_delta backbone where a city
    maps to the province; the NRCAN national-average series scaled to the province's
    baseline level for provinces NRCAN doesn't track directly (so they still MOVE
    with the national trend); static baseline only as a last resort.
    """
    targets = [r for r in CA_REGIONS if region_subset is None or r[0] in region_subset]

    nrcan_raw  = fetch_nrcan_prices()
    nrcan_prov = aggregate_nrcan_by_province(nrcan_raw) if nrcan_raw else {}
    national   = (nrcan_raw or {}).get("Canada") or []

    # Reference national baseline = median of provincial baselines, used to scale
    # the national series to a province's typical price level.
    ca_baselines = [BASELINE_PRICES[r[0]] for r in CA_REGIONS if r[0] in BASELINE_PRICES]
    national_ref = statistics.median(ca_baselines) if ca_baselines else 1.55

    now_ts = NOW()
    for r_id, state, abbr, city, nrcan_city_key, country in targets:
        gb = fetch_gasbuddy_region(r_id, city, abbr, is_canada=True)

        if r_id in nrcan_prov:
            daily, base_source = nrcan_prov[r_id], "nrcan"
        elif national:
            ratio = (BASELINE_PRICES.get(r_id, national_ref) / national_ref)
            daily = [round(v * ratio, 3) for v in national]
            base_source = "nrcan_est"
        elif gb and gb.get("price"):
            daily, base_source = [gb["price"]], "gasbuddy"
        else:
            base = BASELINE_PRICES.get(r_id)
            if base is None:
                log.warning("No price data available for %s", r_id)
                continue
            daily, base_source = [base], "baseline"

        # Sanity-check the latest value against the baseline.
        baseline = BASELINE_PRICES.get(r_id)
        snap     = db.get_snapshot(r_id)
        prev     = snap["price"] if snap and snap.get("price") else None
        daily[-1] = _sanity_check_price(r_id, daily[-1], baseline, prev)

        agg = _fields_from_daily_series(daily, gb, base_source)

        db.store_station_price(
            region_id=r_id, price=agg["price"], unit="L",
            city=city, fetched_at=now_ts
        )
        db.upsert_snapshot(r_id, {
            "state":  state,
            "abbr":   abbr,
            "city":   city,
            "country": "CA",
            "unit":   "L",
            "price":        agg["price"],
            "price_low":    agg["price_low"],
            "week_delta":   agg["week_delta"],
            "trend":        agg["trend"],
            "price_source": agg["price_source"],
            "low_station":  agg["low_station"],
            "prices_updated_at": now_ts,
        })
        log.info("Updated %s: $%.3f/L (Δ%+.3f) [%s]",
                 r_id, agg["price"], agg["week_delta"], agg["price_source"])


def run(region_subset: list[str] | None = None):
    """Run both US and Canadian price collection."""
    db.init_db()
    log.info("=== Price Collector starting ===")

    us_subset = [r for r in (region_subset or []) if not is_canadian(r)] or None
    ca_subset = [r for r in (region_subset or []) if is_canadian(r)] or None

    if region_subset is None or us_subset:
        collect_us_prices(us_subset)

    if region_subset is None or ca_subset:
        collect_canada_prices(ca_subset)

    log.info("=== Price Collector done ===")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    )
    subset = sys.argv[1:] if len(sys.argv) > 1 else None
    if subset and subset[0] == "--regions":
        subset = subset[1:]
    run(region_subset=subset)
