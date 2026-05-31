"""
Module B — LLM News Analysis.

Given news headlines and price context, generates per-region why/advice text
and selects the most relevant news items for each region.

Primary: Anthropic Claude (claude-haiku-4-5 — cheapest, fast)
Fallback: VADER sentiment + keyword heuristics (no API key needed)
"""
import sys
import json
import logging
import re
from typing import Optional

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import ANTHROPIC_API_KEY, is_canadian, region_unit

log = logging.getLogger(__name__)

# ── Region classification helpers ────────────────────────────────────────────

# Keywords that signal relevance to a US region
US_REGION_KEYWORDS = {
    "ca": ["california", "west coast", "pacific", "los angeles", "bay area", "refiner"],
    "tx": ["texas", "gulf coast", "houston", "gulf refin"],
    "ny": ["new york", "northeast", "harbor", "atlantic"],
    "fl": ["florida", "hurricane", "southeast"],
    "wa": ["washington", "pacific northwest", "northwest", "seattle"],
    "il": ["illinois", "midwest", "chicago"],
    "pa": ["pennsylvania", "mid-atlantic"],
    "oh": ["ohio", "midwest"],
    "mi": ["michigan", "midwest", "great lakes"],
    "mn": ["minnesota", "midwest"],
    "or": ["oregon", "pacific northwest"],
    "nv": ["nevada", "west coast"],
    "az": ["arizona", "southwest"],
}

CA_REGION_KEYWORDS = {
    "ab":  ["alberta", "calgary", "edmonton", "wcs", "western canada select", "oil sands"],
    "bc":  ["british columbia", "vancouver", "bc", "carbon tax", "pacific"],
    "on":  ["ontario", "toronto", "ottawa", "ontario government"],
    "qc":  ["quebec", "montreal", "régie", "cap-and-trade"],
    "mb":  ["manitoba", "winnipeg"],
    "sk":  ["saskatchewan", "regina"],
    "nb":  ["new brunswick", "atlantic canada"],
    "ns":  ["nova scotia", "atlantic canada", "halifax"],
    "nl":  ["newfoundland", "st. john's", "atlantic canada"],
    "pe":  ["prince edward island", "pei", "charlottetown"],
    "north": ["yukon", "northwest territories", "nunavut", "northern canada"],
}

ALL_REGION_KEYWORDS = {**US_REGION_KEYWORDS, **CA_REGION_KEYWORDS}

GLOBAL_KEYWORDS = [
    "opec", "crude oil", "wti", "brent", "oil price", "gasoline price",
    "refinery", "pipeline", "supply", "demand", "inventory", "barrel",
    "carbon tax", "fuel price", "inflation", "gas price",
]


def is_globally_relevant(headline: str) -> bool:
    hl = headline.lower()
    return any(kw in hl for kw in GLOBAL_KEYWORDS)


def get_region_relevance(region_id: str, headline: str) -> float:
    """Return 0–1 relevance score for a headline and region."""
    hl = headline.lower()
    score = 0.3 if is_globally_relevant(hl) else 0.0
    for kw in ALL_REGION_KEYWORDS.get(region_id, []):
        if kw in hl:
            score = min(1.0, score + 0.4)
    return score


def filter_news_for_region(region_id: str, news: list[dict], max_items: int = 3) -> list[dict]:
    """Return up to max_items most relevant news items for a region."""
    scored = []
    for item in news:
        hl    = item.get("headline", "")
        score = get_region_relevance(region_id, hl)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:max_items]]


# ── VADER heuristic fallback ──────────────────────────────────────────────────

def _vader_sentiment(text: str) -> float:
    """Return compound score -1 (negative) to +1 (positive)."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer().polarity_scores(text)["compound"]
    except ImportError:
        return 0.0


# Price-direction keywords
_UP_KEYWORDS   = ["rise", "rising", "higher", "surge", "spike", "jump", "increase",
                   "cut", "cuts", "tight", "shortage", "disruption", "outage", "storm",
                   "hurricane", "opec cut", "sanctions"]
_DOWN_KEYWORDS = ["fall", "falling", "lower", "drop", "decline", "ease", "soften",
                   "glut", "surplus", "build", "inventory", "overproduction",
                   "opec+ increase", "weak demand"]


def heuristic_price_direction(headlines: list[str]) -> str:
    """Keyword-based price direction: 'up' | 'down' | 'flat'."""
    up_score   = sum(1 for h in headlines for kw in _UP_KEYWORDS   if kw in h.lower())
    down_score = sum(1 for h in headlines for kw in _DOWN_KEYWORDS if kw in h.lower())
    if up_score > down_score + 1:
        return "up"
    if down_score > up_score + 1:
        return "down"
    return "flat"


def heuristic_verdict(price_dir: str, wti_dir: str, week_delta: float, price: float, unit: str) -> str:
    """Simple rule-based verdict: buy / partial / wait."""
    # If both price direction and WTI direction are down → good time to buy
    if price_dir in ("down", "flat") and wti_dir in ("down", "flat") and week_delta <= 0:
        return "buy"
    if price_dir == "up" or (wti_dir == "up" and week_delta > 0.05):
        return "wait"
    return "partial"


def heuristic_best_day(price_dir: str, week_delta: float) -> int:
    """
    Determine best fill-up day (0=Sun … 6=Sat).
    Monday/Tuesday historically cheapest in US; adjust by trend direction.
    """
    if price_dir == "up":
        return 1   # Fill Monday — before week-long climb
    if price_dir == "down":
        return 5   # Wait until Friday/Saturday
    return 2       # Wednesday default (mid-week, often flat)


def heuristic_why_advice(region_id: str, price: float, week_delta: float,
                          price_dir: str, wti_dir: str, verdict: str,
                          news_headlines: list[str], is_ca: bool) -> tuple[str, str]:
    """Generate plain-English why text and short advice string."""
    unit_str = "$/L" if is_ca else "$/gal"

    parts = []
    if abs(week_delta) >= 0.03:
        direction = "up" if week_delta > 0 else "down"
        cents = abs(round(week_delta * 100, 0))
        parts.append(f"Prices are {direction} {cents:.0f}¢/{unit_str.split('/')[1]} this week.")

    if wti_dir == "down":
        parts.append("WTI crude is easing — typically filters through to pump prices within 1–2 weeks.")
    elif wti_dir == "up":
        parts.append("Crude oil is rising, which will put upward pressure on pump prices.")

    # Add one news-derived sentence
    relevant = [h for h in news_headlines if is_globally_relevant(h)]
    if relevant:
        parts.append(relevant[0].rstrip(".") + ".")

    if not parts:
        if verdict == "buy":
            parts.append("Prices are near a recent low with no major upward pressure.")
        elif verdict == "wait":
            parts.append("Conditions suggest prices may ease in the coming days.")
        else:
            parts.append("Mixed signals — prices could move either way.")

    why = " ".join(parts)

    advice_map = {
        "buy":     "Fill up today",
        "partial": "Top off for now",
        "wait":    "Hold a few days",
    }
    advice = advice_map.get(verdict, "Check back tomorrow")
    return why, advice


# ── LLM path (Anthropic Claude) ───────────────────────────────────────────────

_LLM_SYSTEM = """You are a concise gas price analyst for a consumer app. Given regional price data and news context, generate:
1. A "why" explanation (2-3 sentences, plain English, no jargon)
2. A short "advice" action phrase (≤30 characters)
3. A "verdict": "buy" | "partial" | "wait"
4. A "bestDayIdx": integer 0–6 (0=Sunday, 6=Saturday) — best day to fill up this week

Rules:
- "buy" = prices at or near a recent low, good window to fill up
- "partial" = mixed signals, top off partially and wait for the rest
- "wait" = prices likely to fall in 2–5 days, hold off if you can
- Advice examples: "Fill up today", "Hold until Thursday", "Half now · full Fri"
- For Canada: prices are in $/L not $/gallon
- Keep why under 60 words

Respond ONLY with JSON like: {"why": "...", "advice": "...", "verdict": "buy", "bestDayIdx": 2}"""


def llm_analyze_region(
    region_id: str,
    region_name: str,
    price: float,
    price_low: float,
    week_delta: float,
    wti: dict,
    news: list[dict],
    seasonal: dict,
    is_ca: bool,
) -> dict | None:
    """
    Call Claude to generate why/advice/verdict/bestDayIdx for one region.
    Returns {"why", "advice", "verdict", "bestDayIdx"} or None on failure.
    """
    if not ANTHROPIC_API_KEY:
        return None

    unit = "$/L" if is_ca else "$/gal"
    news_text = "\n".join(f"- {n['headline']}" for n in news[:5]) or "No specific regional news."

    prompt = f"""Region: {region_name} ({region_id.upper()})
Current price: {price:.3f} {unit}
Lowest nearby: {price_low:.3f} {unit}
Week-over-week: {'+' if week_delta >= 0 else ''}{week_delta:.3f} {unit}
WTI crude: ${wti['price']:.2f}/barrel, direction: {wti['dir']}, change: {wti['change']:+.2f}
Season: {seasonal.get('season', 'unknown')}, Summer blend: {seasonal.get('summer_blend', False)}, Holiday week: {seasonal.get('holiday_week', False)}

Relevant news:
{news_text}

Generate JSON verdict for this region."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON from response (handles markdown code blocks)
        json_match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log.warning("LLM analysis failed for %s: %s", region_id, e)
    return None


# ── Public entry point ────────────────────────────────────────────────────────

def analyze_region(
    region_id: str,
    region_name: str,
    price: float,
    price_low: float,
    week_delta: float,
    wti: dict,
    all_news: list[dict],
    seasonal: dict,
) -> dict:
    """
    Produce analytics output for one region.
    Returns: {"verdict", "why", "advice", "bestDayIdx", "wtiDir", "news"}
    """
    is_ca      = is_canadian(region_id)
    local_news = filter_news_for_region(region_id, all_news, max_items=3)
    headlines  = [n.get("headline", "") for n in local_news]

    wti_dir = wti.get("dir", "flat")

    # Try LLM path first
    llm = llm_analyze_region(
        region_id, region_name, price, price_low, week_delta,
        wti, local_news, seasonal, is_ca,
    )

    if llm and all(k in llm for k in ("why", "advice", "verdict", "bestDayIdx")):
        verdict      = llm["verdict"]
        why          = llm["why"]
        advice       = llm["advice"][:30]
        best_day_idx = int(llm["bestDayIdx"]) % 7
    else:
        # Heuristic fallback
        price_dir    = heuristic_price_direction(headlines) if headlines else wti_dir
        verdict      = heuristic_verdict(price_dir, wti_dir, week_delta, price, region_unit(region_id))
        best_day_idx = heuristic_best_day(price_dir, week_delta)
        why, advice  = heuristic_why_advice(
            region_id, price, week_delta, price_dir, wti_dir, verdict, headlines, is_ca
        )

    # Format news items for frontend
    news_items = [
        {
            "headline": n.get("headline", ""),
            "source":   n.get("source", ""),
            "url":      n.get("url", ""),
        }
        for n in local_news
    ]

    return {
        "verdict":     verdict,
        "why":         why,
        "advice":      advice,
        "bestDayIdx":  best_day_idx,
        "wtiDir":      wti_dir,
        "news":        news_items,
    }
