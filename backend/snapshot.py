"""
Assembles the full data.json payload from SQLite snapshots and writes it to
frontend/data/data.json (Approach A — no API server needed).

Also runs the analytics pipeline (Modules B, C, D) to populate verdict/why/
advice/breakdown fields if they haven't been set in the current cycle.

Run directly:
    cd shouldigetgas
    python backend/snapshot.py
"""
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

import db
from config import DATA_JSON, ALL_REGIONS, US_REGIONS, CA_REGIONS, BASELINE_PRICES, is_canadian, ANTHROPIC_API_KEY
from analytics.gather import gather_all
from analytics.news_analysis import analyze_region, analyze_regions_batch, filter_news_for_region
from analytics.predictor import (
    build_trend_array, predict_direction, compute_week_delta, determine_verdict
)
from analytics.breakdown import get_breakdown

log = logging.getLogger(__name__)

NOW = lambda: datetime.now(timezone.utc)

# Week-over-week deltas smaller than half a cent per unit are noise, not a real
# move. Snap them to exactly 0.0 and flag the direction as "flat" so the frontend
# never renders an ambiguous directional zero (e.g. "↓ −0¢").
FLAT_DELTA_THRESHOLD = 0.005


def normalize_week_delta(week_delta: float) -> tuple[float, str]:
    """Return (snapped_delta, direction) where direction ∈ {up, down, flat}."""
    if week_delta is None or abs(week_delta) < FLAT_DELTA_THRESHOLD:
        return 0.0, "flat"
    return week_delta, ("up" if week_delta > 0 else "down")


def _run_batch_llm(snap_by_id: dict, context: dict) -> dict:
    """Pre-compute LLM verdicts for all regions via the Batch API."""
    regions_data = []
    for region_def in ALL_REGIONS:
        r_id = region_def[0]
        snap = snap_by_id.get(r_id)

        if snap:
            price       = snap.get("price") or BASELINE_PRICES.get(r_id, 3.0)
            price_low   = snap.get("price_low") or price * 0.95
            week_delta  = snap["week_delta"] if snap.get("week_delta") is not None else compute_week_delta(r_id, price)
            region_name = snap.get("state", region_def[1])
        else:
            price       = BASELINE_PRICES.get(r_id, 3.0)
            price_low   = round(price * 0.95, 3)
            week_delta  = 0.0
            region_name = region_def[1]

        local_news = filter_news_for_region(r_id, context["news"], max_items=3)
        regions_data.append({
            "region_id":   r_id,
            "region_name": region_name,
            "price":       price,
            "price_low":   price_low,
            "week_delta":  week_delta,
            "wti":         context["wti"],
            "news":        local_news,
            "seasonal":    context["seasonal"],
            "is_ca":       is_canadian(r_id),
        })

    return analyze_regions_batch(regions_data)


def run_analytics_for_region(
    region_id: str,
    snapshot: dict,
    context: dict,
) -> dict:
    """
    Run Modules B, C, D for one region and return updated snapshot fields.
    """
    price        = snapshot.get("price") or BASELINE_PRICES.get(region_id, 3.0)
    price_low    = snapshot.get("price_low") or price * 0.95
    price_source = snapshot.get("price_source")
    wti        = context["wti"]
    news       = context["news"]
    seasonal   = context["seasonal"]
    refinery   = context.get("refinery") or {}
    refin_util = refinery.get("national") if refinery else None

    # Module C — prediction
    prediction = predict_direction(region_id, price, wti["dir"], refin_util, seasonal)
    best_day   = prediction["best_day_idx"]
    price_dir  = prediction["dir"]

    # Prefer the price collector's week_delta (computed from the real provider
    # series); only fall back to recomputing from daily history when unset.
    if snapshot.get("week_delta") is not None:
        week_delta = snapshot["week_delta"]
    else:
        week_delta = compute_week_delta(region_id, price)

    # Verdict (confidence-aware: baseline / degenerate signals → 'partial')
    verdict = determine_verdict(price_dir, wti["dir"], week_delta, price, region_id,
                                price_source=price_source)

    # Module B — news analysis (generates why/advice; may upgrade verdict via LLM)
    llm_pre = context.get("llm_results", {}).get(region_id)
    if llm_pre:
        # Use pre-computed batch LLM result
        verdict  = llm_pre["verdict"]
        best_day = llm_pre["bestDayIdx"]
        analysis = {
            "why":        llm_pre["why"],
            "advice":     llm_pre["advice"],
            "verdict":    llm_pre["verdict"],
            "bestDayIdx": llm_pre["bestDayIdx"],
            "wtiDir":     wti["dir"],
            "news": [
                {
                    "headline": n.get("headline", ""),
                    "source":   n.get("source", ""),
                    "url":      n.get("url", ""),
                }
                for n in filter_news_for_region(region_id, news, max_items=3)
            ],
        }
    else:
        analysis = analyze_region(
            region_id    = region_id,
            region_name  = snapshot.get("state", region_id),
            price        = price,
            price_low    = price_low,
            week_delta   = week_delta,
            wti          = wti,
            all_news     = news,
            seasonal     = seasonal,
        )
        # LLM may produce a more accurate verdict
        if analysis.get("verdict"):
            verdict  = analysis["verdict"]
        if analysis.get("bestDayIdx") is not None:
            best_day = analysis["bestDayIdx"]

    # Module D — breakdown
    breakdown = get_breakdown(region_id, price)

    # 14-day trend: prefer the collector's real provider series. When that series is
    # present but short (a thin weekly EIA series the collector could only expand to
    # <14 daily points), left-pad it so its real movement survives — rebuilding from
    # DB history would discard the provider series for a synthetic/flat slope. Only
    # rebuild when no collector trend exists at all.
    trend = snapshot.get("trend")
    if trend and len(trend) < 14:
        trend = [round(trend[0], 3)] * (14 - len(trend)) + [round(p, 3) for p in trend]
    elif not trend:
        trend = build_trend_array(region_id, price)
    if not trend:
        trend = [round(price, 3)] * 14

    now_ts = NOW().isoformat()
    return {
        "verdict":              verdict,
        "why":                  analysis.get("why", ""),
        "advice":               analysis.get("advice", ""),
        "best_day_idx":         best_day,
        "wti_dir":              wti["dir"],
        "breakdown":            breakdown,
        "trend":                trend,
        "week_delta":           week_delta,
        "price_low":            round(price_low, 3),
        "price_source":         price_source,
        "low_station":          snapshot.get("low_station") or {},
        "news":                 analysis.get("news", []),
        "analysis_updated_at":  now_ts,
    }


def build_region_json(snapshot: dict, context: dict) -> dict:
    """
    Merge a snapshot row with analytics output into the frontend region shape.
    """
    r_id    = snapshot["region_id"]
    price   = snapshot.get("price") or BASELINE_PRICES.get(r_id, 3.0)
    unit    = snapshot.get("unit", "gal")

    analytics = run_analytics_for_region(r_id, snapshot, context)

    week_delta, week_delta_dir = normalize_week_delta(analytics["week_delta"])

    region = {
        "id":         r_id,
        "state":      snapshot.get("state", ""),
        "abbr":       snapshot.get("abbr", ""),
        "city":       snapshot.get("city", ""),
        "country":    snapshot.get("country", "US"),
        "unit":       unit,
        "verdict":    analytics["verdict"],
        "price":      round(price, 3),
        "priceLow":   analytics["price_low"],
        "weekDelta":  week_delta,
        "weekDeltaDir": week_delta_dir,
        "why":        analytics["why"],
        "advice":     analytics["advice"],
        "bestDayIdx": analytics["best_day_idx"],
        "wtiDir":     analytics["wti_dir"],
        "news":       analytics["news"],
        "breakdown":  analytics["breakdown"],
        "trend":      analytics["trend"],
        "priceSource": analytics.get("price_source") or "baseline",
    }
    # Additive: lowest-price station for the GasBuddy deep link (when available).
    low = analytics.get("low_station") or {}
    if low and low.get("url"):
        region["lowStation"] = {
            "id":    low.get("station_id"),
            "name":  low.get("name"),
            "price": low.get("price"),
            "lat":   low.get("lat"),
            "lng":   low.get("lng"),
            "url":   low.get("url"),
        }
    return region


def build_payload(context: dict) -> dict:
    """
    Assemble the complete data.json payload from all regional snapshots.
    """
    now_ts  = NOW().isoformat()
    wti     = context["wti"]
    regions = []

    snapshots  = db.get_all_snapshots()
    snap_by_id = {s["region_id"]: s for s in snapshots}

    # Pre-compute LLM verdicts for all regions via the Batch API (50% cost reduction)
    if ANTHROPIC_API_KEY:
        log.info("Running batch LLM analysis for %d regions", len(ALL_REGIONS))
        context["llm_results"] = _run_batch_llm(snap_by_id, context)

    # Iterate in canonical order: US first, then Canada
    for region_def in ALL_REGIONS:
        r_id = region_def[0]
        snap = snap_by_id.get(r_id)

        if snap is None:
            # Snapshot doesn't exist yet — create a minimal one from config
            base = BASELINE_PRICES.get(r_id, 3.0)
            country = "CA" if is_canadian(r_id) else "US"
            unit    = "L" if is_canadian(r_id) else "gal"
            snap = {
                "region_id":   r_id,
                "state":       region_def[1],
                "abbr":        region_def[2],
                "city":        region_def[3],
                "country":     country,
                "unit":        unit,
                "price":       base,
                "price_low":   round(base * 0.95, 3),
                "week_delta":  0.0,
                "trend":       [round(base, 3)] * 14,
                "breakdown":   {},
                "news":        [],
                "verdict":     "partial",
                "why":         "",
                "advice":      "",
                "best_day_idx": 2,
                "wti_dir":     "flat",
                "price_source": "baseline",
                "low_station": {},
            }

        try:
            region_json = build_region_json(snap, context)
            regions.append(region_json)
        except Exception as e:
            log.error("Error building region %s: %s", r_id, e, exc_info=True)

    next_price    = (NOW() + timedelta(minutes=30)).isoformat()
    next_analysis = (NOW() + timedelta(hours=6)).isoformat()
    prices_updated = max(
        (s.get("prices_updated_at") or "" for s in snapshots),
        default=now_ts,
    )

    return {
        "meta": {
            "updatedAt":        now_ts,
            "pricesUpdatedAt":  prices_updated,
            "dataSource":       "EIA + GasBuddy + NRCAN",
            "nextPriceUpdate":  next_price,
            "nextAnalysisUpdate": next_analysis,
        },
        "wti": wti,
        "regions": regions,
    }


def write_data_json(payload: dict):
    """Write the payload to frontend/data/data.json atomically."""
    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp.replace(DATA_JSON)
    log.info("Wrote %d regions to %s", len(payload["regions"]), DATA_JSON)


def run(regions_subset: list[str] | None = None):
    """Run the full analytics pipeline and write data.json."""
    db.init_db()
    log.info("=== Analytics / Snapshot starting ===")

    context = gather_all()
    log.info("WTI: $%.2f (%s %+.2f)", context["wti"]["price"],
             context["wti"]["dir"], context["wti"]["change"])
    log.info("News items fetched: %d", len(context["news"]))

    if regions_subset:
        # Only update specified regions
        snapshots = db.get_all_snapshots()
        snap_by_id = {s["region_id"]: s for s in snapshots}
        for r_id in regions_subset:
            snap = snap_by_id.get(r_id)
            if snap:
                analytics = run_analytics_for_region(r_id, snap, context)
                db.upsert_snapshot(r_id, {**snap, **analytics})

    # Always write the full data.json
    payload = build_payload(context)
    write_data_json(payload)
    log.info("=== Analytics / Snapshot done ===")
    return payload


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    )
    import sys
    subset = sys.argv[1:] if len(sys.argv) > 1 else None
    run(regions_subset=subset)
