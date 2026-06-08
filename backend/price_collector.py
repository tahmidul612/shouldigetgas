"""
Part 1 — Price Collector (runs every 30 minutes).

Pulls current gasoline prices for all regions, computes regional medians and
lows, stores raw station data in SQLite, and updates regional_snapshot rows.

Run directly:
    cd shouldigetgas
    python backend/price_collector.py [--regions ca tx on]
"""
import sys
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
from config import (
    EIA_API_KEY, EIA_GAS_ENDPOINT,
    US_REGIONS, CA_REGIONS, BASELINE_PRICES,
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
        "facets[product][]": "EPM0",    # regular gasoline
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
    """
    if not EIA_API_KEY:
        return {}

    cache_key = "eia_padd:" + ",".join(sorted(padd_codes))
    hit = cache.get(cache_key)
    if hit:
        return hit

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[product][]": "EPM0",
        "facets[process][]": "PTE",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": "14",
    }
    param_list = list(params.items())
    for code in padd_codes:
        param_list.append(("facets[duoarea][]", code))

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
        if area and value is not None:
            try:
                result.setdefault(area, []).append(float(value))
            except (ValueError, TypeError):
                pass

    cache.set(cache_key, result, ttl=cache.TTL_EIA_WEEKLY)
    return result


# ── GasBuddy — station-level prices ──────────────────────────────────────────

def fetch_gasbuddy_region(region_id: str, city: str, is_canada: bool = False) -> dict | None:
    """
    Use py-gasbuddy to get station prices for a city.
    Returns {prices: [float], low: float, city: str} or None if unavailable.
    """
    try:
        # py-gasbuddy is async — run in sync context
        import asyncio
        from gasbuddy import GasBuddy, TemperatureUnit
        gb = GasBuddy()
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(gb.price_lookup(city))
        loop.close()
        prices = [float(r["price"]) for r in results if r.get("price")]
        if not prices:
            return None
        return {"prices": prices, "low": min(prices), "city": city}
    except ImportError:
        log.debug("py-gasbuddy not installed")
        return None
    except Exception as e:
        log.debug("GasBuddy lookup failed for %s: %s", city, e)
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


def fetch_nrcan_prices() -> dict[str, float] | None:
    """
    Scrape NRCAN Fuel Price Monitor for Canadian city prices (¢/L → $/L).
    Returns {city_key: price_in_dollars_per_L} or None.
    """
    cache_key = "nrcan_prices"
    hit = cache.get(cache_key)
    if hit:
        return hit

    try:
        from bs4 import BeautifulSoup
        resp = SESSION.get(NRCAN_PRICE_URL, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        prices: dict[str, float] = {}
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                city  = cells[0].get_text(strip=True)
                price = cells[1].get_text(strip=True).replace(",", ".")
                try:
                    prices[city] = float(price) / 100.0   # ¢/L → $/L
                except (ValueError, TypeError):
                    pass
        if prices:
            cache.set(cache_key, prices, ttl=cache.TTL_EIA_WEEKLY)
            return prices
        return None
    except Exception as e:
        log.debug("NRCAN scrape failed: %s", e)
        return None


# City → province mapping for NRCAN data aggregation
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


def aggregate_nrcan_by_province(nrcan: dict[str, float]) -> dict[str, float]:
    """Average NRCAN city prices to province-level."""
    buckets: dict[str, list[float]] = {}
    for city, price in nrcan.items():
        prov = NRCAN_CITY_PROVINCE.get(city)
        if prov:
            buckets.setdefault(prov, []).append(price)
    return {prov: statistics.median(prices) for prov, prices in buckets.items()}


# ── Compute regional aggregate ────────────────────────────────────────────────

def compute_region_prices(
    region_id: str,
    raw_prices: list[float],
    prev_prices: list[float] | None,
    gasbuddy: dict | None,
) -> dict:
    """
    Given raw prices (newest first), compute the aggregate fields needed for
    regional_snapshot. Returns partial snapshot dict (price fields only).
    """
    if not raw_prices:
        return {}

    price     = round(statistics.median(raw_prices[:3]), 3)   # median of last 3 readings
    price_low = round(min(raw_prices[:3]), 3)

    # GasBuddy station-level low overrides if available
    if gasbuddy and gasbuddy.get("low"):
        price_low = round(gasbuddy["low"], 3)

    # Week-over-week delta: compare median of latest vs 7-days-ago bucket
    if prev_prices and len(prev_prices) >= 1:
        prev_median = statistics.median(prev_prices[:3])
        week_delta  = round(price - prev_median, 3)
    else:
        week_delta = 0.0

    # 14-day trend: interpolate weekly data to daily
    trend = interpolate_to_daily(raw_prices[:14])

    return {
        "price":      price,
        "price_low":  price_low,
        "week_delta": week_delta,
        "trend":      trend,
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
    """Fetch and store US state prices from EIA."""
    targets = [r for r in US_REGIONS if region_subset is None or r[0] in region_subset]
    state_ids = [r[4] for r in targets]   # EIA stateid column

    log.info("Fetching EIA prices for %d US states", len(state_ids))
    current  = fetch_eia_state_prices(state_ids)
    # Also fetch shifted window to get "last week" prices
    prev_params = {}
    # We use the 14-week series; index 0 = newest, indices 7+ = prev week equivalent

    now_ts = NOW()
    for r_id, state, abbr, city, eia_sid, padd in targets:
        prices = current.get(eia_sid.upper(), [])
        if not prices:
            # Try PADD district fallback
            padd_data = fetch_eia_padd_prices([padd])
            prices    = padd_data.get(padd, [])

        if not prices:
            # Final fallback: use baseline
            base = BASELINE_PRICES.get(r_id)
            prices = [base] if base else []
            log.debug("Using baseline price for %s", r_id)

        if not prices:
            continue

        # Sanity-check all price readings so anomalous values in prices[1]/[2]
        # cannot skew the median (or week_delta) computed from raw_prices[:3].
        baseline   = BASELINE_PRICES.get(r_id)
        snap       = db.get_snapshot(r_id)
        prev_price = snap["price"] if snap and snap.get("price") else None
        prices = [
            _sanity_check_price(r_id, p, baseline, prev_price) for p in prices
        ]

        # Store individual price as a "station"
        db.store_station_price(
            region_id=r_id, price=prices[0], unit="gal",
            city=city, fetched_at=now_ts
        )

        # GasBuddy for station-level low (optional, can be slow)
        gb = fetch_gasbuddy_region(r_id, city)

        prev = prices[7:] if len(prices) > 7 else None
        agg  = compute_region_prices(r_id, prices, prev, gb)
        if not agg:
            continue

        db.upsert_snapshot(r_id, {
            "state":  state,
            "abbr":   abbr,
            "city":   city,
            "country": "US",
            "unit":   "gal",
            "price":      agg["price"],
            "price_low":  agg["price_low"],
            "week_delta": agg["week_delta"],
            "trend":      agg["trend"],
            "prices_updated_at": now_ts,
        })
        log.info("Updated %s: $%.3f/gal (Δ%+.3f)", r_id, agg["price"], agg["week_delta"])


def collect_canada_prices(region_subset: list[str] | None = None):
    """Fetch and store Canadian provincial prices."""
    targets = [r for r in CA_REGIONS if region_subset is None or r[0] in region_subset]

    # Fetch all Canadian source data upfront
    nrcan_raw  = fetch_nrcan_prices()
    nrcan_prov = aggregate_nrcan_by_province(nrcan_raw) if nrcan_raw else {}
    ontario_raw = fetch_ontario_prices()

    now_ts = NOW()
    for r_id, state, abbr, city, nrcan_city_key, country in targets:
        price_cdl: float | None = None

        # Priority 1: NRCAN city data → province aggregate
        if r_id in nrcan_prov:
            price_cdl = nrcan_prov[r_id]

        # Priority 2: Ontario CKAN for ON specifically
        if r_id == "on" and ontario_raw:
            toronto = ontario_raw.get("Toronto") or ontario_raw.get("toronto")
            if toronto:
                price_cdl = toronto / 100.0   # ¢/L → $/L

        # Priority 3: GasBuddy for the reference city
        if price_cdl is None:
            gb = fetch_gasbuddy_region(r_id, city, is_canada=True)
            if gb and gb.get("prices"):
                # GasBuddy returns $/L for Canadian cities
                price_cdl = statistics.median(gb["prices"])

        # Priority 4: baseline
        if price_cdl is None:
            price_cdl = BASELINE_PRICES.get(r_id)
            if price_cdl:
                log.debug("Using baseline price for %s", r_id)

        if price_cdl is None:
            log.warning("No price data available for %s", r_id)
            continue

        db.store_station_price(
            region_id=r_id, price=price_cdl, unit="L",
            city=city, fetched_at=now_ts
        )

        # Build 14-day trend from history
        history = db.get_price_history(r_id, days=21)
        if history:
            hist_prices = [p for _, p in history]
            trend = hist_prices[-14:] if len(hist_prices) >= 14 else hist_prices
            # Pad with current price if too short
            while len(trend) < 14:
                trend = [trend[0]] + trend
            trend = [round(v, 3) for v in trend]
        else:
            trend = [round(price_cdl, 3)] * 14

        # Week delta from history
        if history and len(history) >= 7:
            week_ago_price = history[-7][1] if len(history) >= 7 else history[0][1]
            week_delta = round(price_cdl - week_ago_price, 3)
        else:
            week_delta = 0.0

        db.upsert_snapshot(r_id, {
            "state":  state,
            "abbr":   abbr,
            "city":   city,
            "country": "CA",
            "unit":   "L",
            "price":      round(price_cdl, 3),
            "price_low":  round(price_cdl * 0.95, 3),   # estimate ~5% below avg
            "week_delta": week_delta,
            "trend":      trend,
            "prices_updated_at": now_ts,
        })
        log.info("Updated %s: $%.3f/L (Δ%+.3f)", r_id, price_cdl, week_delta)


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
