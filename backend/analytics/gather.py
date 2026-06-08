"""
Module A — Data Gathering.
Pulls crude oil prices, refinery data, and news headlines from EIA and NewsAPI.
"""
import sys
import logging
from datetime import datetime, timezone, timedelta

import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import cache
import db
from config import (
    EIA_API_KEY, NEWS_API_KEY, GNEWS_API_KEY,
    EIA_SPT_ENDPOINT, EIA_V1_SERIES, EIA_CAP_ENDPOINT,
    NEWS_API_ENDPOINT, GNEWS_API_ENDPOINT,
)

log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "shouldigetgas/1.0"})

NOW = lambda: datetime.now(timezone.utc)


# ── WTI / Brent Crude Oil ─────────────────────────────────────────────────────

def fetch_wti_price() -> dict | None:
    """
    Returns {"price": float, "dir": "up"|"down"|"flat", "change": float} or None.
    Tries EIA API v2 first, falls back to EIA v1 legacy endpoint.
    """
    hit = cache.get("crude:wti")
    if hit:
        return hit

    result = _fetch_wti_v2() or _fetch_wti_v1()
    if result:
        cache.set("crude:wti", result, ttl=cache.TTL_CRUDE)
        # Persist to DB for historical tracking
        db.store_crude("WTI", result["price"], datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    return result


def _fetch_wti_v2() -> dict | None:
    if not EIA_API_KEY:
        return None
    try:
        resp = SESSION.get(
            EIA_SPT_ENDPOINT,
            params={
                "api_key":               EIA_API_KEY,
                "frequency":             "daily",
                "data[0]":               "value",
                "facets[series][]":      "RWTCD",
                "sort[0][column]":       "period",
                "sort[0][direction]":    "desc",
                "length":                "5",
            },
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json().get("response", {}).get("data", [])
        prices = [float(r["value"]) for r in rows if r.get("value") not in (None, "")]
        if len(prices) >= 2:
            return _wti_result(prices[0], prices[1])
        if prices:
            return _wti_result(prices[0], prices[0])
    except Exception as e:
        log.debug("WTI v2 fetch failed: %s", e)
    return None


def _fetch_wti_v1() -> dict | None:
    """EIA API v1 legacy — always reliable."""
    if not EIA_API_KEY:
        return None
    try:
        resp = SESSION.get(
            EIA_V1_SERIES,
            params={"api_key": EIA_API_KEY, "series_id": "RWTCD"},
            timeout=20,
        )
        resp.raise_for_status()
        series = resp.json().get("series", [{}])[0].get("data", [])
        if len(series) >= 2:
            return _wti_result(float(series[0][1]), float(series[1][1]))
        if series:
            return _wti_result(float(series[0][1]), float(series[0][1]))
    except Exception as e:
        log.debug("WTI v1 fetch failed: %s", e)
    return None


def _wti_result(curr: float, prev: float) -> dict:
    change = round(curr - prev, 2)
    if abs(change) < 0.10:
        direction = "flat"
    elif change > 0:
        direction = "up"
    else:
        direction = "down"
    return {"price": round(curr, 2), "dir": direction, "change": change}


# ── Refinery Utilization ──────────────────────────────────────────────────────

def fetch_refinery_utilization() -> dict | None:
    """
    Returns {"national": float, "padd3": float} utilization rates (%) or None.
    Used as context signal: low util → supply tightening → prices up.
    """
    hit = cache.get("refinery_util")
    if hit:
        return hit

    if not EIA_API_KEY:
        return None
    try:
        resp = SESSION.get(
            EIA_CAP_ENDPOINT,
            params={
                "api_key":            EIA_API_KEY,
                "frequency":          "weekly",
                "data[0]":            "value",
                "facets[duoarea][]":  "NUS",   # national
                "sort[0][column]":    "period",
                "sort[0][direction]": "desc",
                "length":             "4",
            },
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json().get("response", {}).get("data", [])
        rates = [float(r["value"]) for r in rows if r.get("value") not in (None, "")]
        if rates:
            result = {"national": round(rates[0], 1)}
            cache.set("refinery_util", result, ttl=cache.TTL_EIA_WEEKLY)
            return result
    except Exception as e:
        log.debug("Refinery util fetch failed: %s", e)
    return None


# ── News Headlines ────────────────────────────────────────────────────────────

_NEWS_QUERIES = [
    "gasoline price crude oil",
]


def fetch_gnews_headlines(max_articles: int = 20) -> list[dict]:
    """
    Fetch energy-relevant news from GNews API.
    Returns list of {"headline", "source", "url", "published_at"} dicts.
    """
    articles = []
    seen_urls: set[str] = set()

    for query in _NEWS_QUERIES:
        if len(articles) >= max_articles:
            break
        try:
            resp = SESSION.get(
                GNEWS_API_ENDPOINT,
                params={
                    "q":        query,
                    "sortby":   "publishedAt",
                    "lang":     "en",
                    "max":      10,
                    "apikey":   GNEWS_API_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                url = a.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                articles.append({
                    "headline":     (a.get("title") or "")[:200],
                    "source":       (a.get("source") or {}).get("name", ""),
                    "url":          url,
                    "published_at": a.get("publishedAt", ""),
                })
        except Exception as e:
            log.debug("GNews fetch failed for query '%s': %s", query, e)

    return articles[:max_articles]


def fetch_news_headlines(max_articles: int = 20) -> list[dict]:
    """
    Fetch energy-relevant news headlines.
    Uses NewsAPI if NEWS_API_KEY is set, GNews if GNEWS_API_KEY is set, else skips.
    Returns list of {"headline", "source", "url", "published_at"} dicts.
    """
    hit = cache.get("news:headlines")
    if hit:
        return hit

    if NEWS_API_KEY:
        articles = _fetch_newsapi_headlines(max_articles)
        # If NewsAPI returned nothing (e.g. invalid/expired key), fall back
        if not articles and GNEWS_API_KEY:
            log.debug("NewsAPI returned empty — falling back to GNews")
            articles = fetch_gnews_headlines(max_articles)
    elif GNEWS_API_KEY:
        log.debug("NEWS_API_KEY not set — falling back to GNews")
        articles = fetch_gnews_headlines(max_articles)
    else:
        log.debug("No news API key set — skipping news fetch")
        return []

    if articles:
        cache.set("news:headlines", articles, ttl=cache.TTL_NEWS)
        _store_news(articles)
    return articles[:max_articles]


def _fetch_newsapi_headlines(max_articles: int = 20) -> list[dict]:
    articles = []
    seen_urls: set[str] = set()
    cutoff = (NOW() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for query in _NEWS_QUERIES:
        if len(articles) >= max_articles:
            break
        try:
            resp = SESSION.get(
                NEWS_API_ENDPOINT,
                params={
                    "q":          query,
                    "sortBy":     "publishedAt",
                    "from":       cutoff,
                    "language":   "en",
                    "pageSize":   10,
                    "apiKey":     NEWS_API_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                url = a.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                articles.append({
                    "headline":     (a.get("title") or "")[:200],
                    "source":       a.get("source", {}).get("name", ""),
                    "url":          url,
                    "published_at": a.get("publishedAt", ""),
                })
        except Exception as e:
            log.debug("NewsAPI fetch failed for query '%s': %s", query, e)

    return articles


def _store_news(articles: list[dict]):
    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat()
    with db.get_conn() as conn:
        for a in articles:
            conn.execute("""
                INSERT INTO news_cache (headline, source, url, published_at, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                a.get("headline", ""),
                a.get("source", ""),
                a.get("url", ""),
                a.get("published_at", ""),
                now_ts,
            ))


# ── Seasonal context ──────────────────────────────────────────────────────────

def get_seasonal_context() -> dict:
    """
    Return a dict describing current seasonal pressures on gas prices.
    Used as prompt context for the LLM analysis module.
    """
    now   = NOW()
    month = now.month
    day   = now.day

    ctx = {
        "month":        month,
        "season":       _season(month),
        "summer_blend": month in (3, 4, 5, 6, 7, 8, 9),  # roughly Apr–Sep
        "holiday_week": _is_holiday_week(month, day),
        "hurricane_season": month in (6, 7, 8, 9, 10, 11),
    }
    return ctx


def _season(month: int) -> str:
    if month in (12, 1, 2):  return "winter"
    if month in (3, 4, 5):   return "spring"
    if month in (6, 7, 8):   return "summer"
    return "fall"


def _is_holiday_week(month: int, day: int) -> bool:
    # US major driving holidays: Memorial Day (~May 25), July 4, Labor Day (~Sep 1), Thanksgiving (~Nov 24)
    return (
        (month == 5 and day >= 23) or
        (month == 7 and 1 <= day <= 7) or
        (month == 9 and day <= 7) or
        (month == 11 and 20 <= day <= 30) or
        (month == 12 and 20 <= day <= 31)
    )


# ── Gather all context ────────────────────────────────────────────────────────

def gather_all() -> dict:
    """
    Gather all analytical context: crude, refinery, news, seasonal.
    Returns a combined context dict passed to the analytics pipeline.
    """
    db.init_db()
    wti       = fetch_wti_price()
    refinery  = fetch_refinery_utilization()
    news      = fetch_news_headlines()
    seasonal  = get_seasonal_context()

    # Also pull DB crude history for trend calc
    crude_row = db.get_latest_crude("WTI")

    if wti is None:
        log.warning(
            "WTI price fetch returned None (possible causes: EIA_API_KEY not set, "
            "both EIA v2 and v1 endpoints unavailable, or response parse error). "
            "Using hardcoded fallback price $71.20 — crude context may be stale."
        )

    return {
        "wti":         wti or {"price": 71.2, "dir": "flat", "change": 0.0},
        "refinery":    refinery,
        "news":        news,
        "seasonal":    seasonal,
        "crude_hist":  crude_row,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    ctx = gather_all()
    print(json.dumps(ctx, indent=2, default=str))
