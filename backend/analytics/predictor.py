"""
Module C — Time-Series Prediction.

Uses exponential smoothing (Holt's linear method) on historical weekly price
data to project 5-day price direction, compute weekDelta, and generate the
14-point trend array for the sparkline.
"""
import sys
import logging
import statistics
from datetime import datetime, timezone


sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import db

log = logging.getLogger(__name__)


# ── Exponential smoothing ─────────────────────────────────────────────────────

def holt_forecast(series: list[float], h: int = 5) -> list[float]:
    """
    Holt's linear exponential smoothing — h-step ahead forecast.
    Uses statsmodels if available; pure-Python Holt otherwise.
    Returns list of h forecast values.
    """
    if len(series) < 3:
        return [series[-1]] * h

    try:
        from statsmodels.tsa.holtwinters import Holt
        model = Holt(series, initialization_method="estimated").fit(
            optimized=True, remove_bias=True
        )
        forecast = model.forecast(h)
        return [round(float(v), 4) for v in forecast]
    except Exception:
        pass

    # Pure-Python fallback: simple double exponential smoothing
    alpha, beta = 0.3, 0.2
    level  = series[0]
    trend  = series[1] - series[0]
    for val in series[1:]:
        prev_level = level
        level = alpha * val + (1 - alpha) * (level + trend)
        trend = beta  * (level - prev_level) + (1 - beta) * trend
    return [round(level + i * trend, 4) for i in range(1, h + 1)]


# ── Trend array from history ──────────────────────────────────────────────────

def build_trend_array(region_id: str, current_price: float,
                      weekly_series: list[float] | None = None) -> list[float]:
    """
    Build a 14-point daily price series (past → present) for the sparkline.

    Preference order:
      1. ≥14 days of real daily history from SQLite.
      2. A provider weekly series (newest-first), interpolated weekly → daily —
         lets EIA/PADD-backed regions show real movement before daily history
         has accumulated.
      3. Whatever thin daily history exists, padded with a synthetic slope.
      4. Flat line at the current price (absolute last resort).
    """
    history = db.get_price_history(region_id, days=30)
    if len(history) >= 14:
        prices = [p for _, p in history][-14:]
        return [round(p, 3) for p in prices]

    # Weekly provider series → daily (newest-first input, so reverse to oldest-first)
    if weekly_series and len(weekly_series) >= 2:
        weekly_oldest_first = list(reversed(weekly_series))
        daily = _interp_to_daily(weekly_oldest_first)
        if len(daily) >= 14:
            return [round(p, 3) for p in daily[-14:]]
        if daily:
            pad   = 14 - len(daily)
            slope = (daily[-1] - daily[0]) / max(len(daily) - 1, 1)
            prepend = [round(daily[0] - slope * (pad - i), 3) for i in range(pad)]
            return prepend + [round(p, 3) for p in daily]

    if history:
        prices = [p for _, p in history]
        # Linear interpolation to daily
        daily = _interp_to_daily(prices)
        if len(daily) >= 14:
            return [round(p, 3) for p in daily[-14:]]
        # Pad from the left with synthetic trend
        pad  = 14 - len(daily)
        if len(prices) >= 2:
            slope = (prices[-1] - prices[0]) / max(len(prices) - 1, 1)
        else:
            slope = 0.0
        prepend = [round(prices[0] - slope * (pad - i), 3) for i in range(pad)]
        return prepend + [round(p, 3) for p in daily]

    # No history at all: flat line at current price
    return [round(current_price, 3)] * 14


def _interp_to_daily(weekly: list[float]) -> list[float]:
    """Linear interpolation of weekly prices to daily."""
    daily: list[float] = []
    for i in range(len(weekly) - 1):
        a, b = weekly[i], weekly[i + 1]
        for d in range(7):
            daily.append(a + (b - a) * d / 7)
    daily.append(weekly[-1])
    return daily


# ── Directional prediction ────────────────────────────────────────────────────

def predict_direction(
    region_id: str,
    current_price: float,
    wti_dir: str,
    refinery_util: float | None,
    seasonal: dict,
) -> dict:
    """
    Combine time-series forecast with macro signals to predict price direction
    and determine the best fill-up day.

    Returns {"dir": "up"|"down"|"flat", "best_day_idx": int, "confidence": float}
    """
    history = db.get_price_history(region_id, days=90)
    prices  = [p for _, p in history]

    if len(prices) >= 4:
        forecast      = holt_forecast(prices, h=5)
        proj_end      = forecast[-1]
        forecast_dir  = "up" if proj_end > current_price * 1.005 else \
                         "down" if proj_end < current_price * 0.995 else "flat"
        # Day within the 5-day window that has the lowest projected price
        min_idx       = min(range(len(forecast)), key=lambda i: forecast[i])
        best_future   = min_idx + 1   # 1-indexed days from now
    else:
        forecast_dir  = "flat"
        best_future   = 0

    # Macro adjustments
    signals = [forecast_dir, wti_dir]
    if seasonal.get("summer_blend") and seasonal.get("season") == "spring":
        signals.append("up")     # summer blend switchover drives prices up
    if refinery_util and refinery_util < 88.0:
        signals.append("up")     # low utilisation → supply tightening
    if seasonal.get("holiday_week"):
        signals.append("up")     # demand spike near holidays

    up_count   = signals.count("up")
    down_count = signals.count("down")
    if up_count > down_count:
        final_dir = "up"
    elif down_count > up_count:
        final_dir = "down"
    else:
        final_dir = "flat"

    # Best day to fill: if prices going up → fill ASAP (Mon/Tue)
    # If going down → wait until end of week (Fri/Sat)
    today    = datetime.now(timezone.utc).weekday()  # 0=Mon
    today_js = (today + 1) % 7                       # JS 0=Sun

    if final_dir == "up":
        best_day_idx = (today_js + 1) % 7    # tomorrow
    elif final_dir == "down":
        best_day_idx = (today_js + min(best_future + 1, 5)) % 7
    else:
        best_day_idx = 2                       # Wednesday default

    confidence = min(1.0, (abs(up_count - down_count) + 1) / (len(signals) + 1))

    return {
        "dir":          final_dir,
        "best_day_idx": best_day_idx,
        "confidence":   round(confidence, 2),
    }


# ── Compute week delta ────────────────────────────────────────────────────────

def compute_week_delta(region_id: str, current_price: float) -> float:
    """
    Return price change vs ~7 days ago (or best approximation).

    `get_price_history` returns one averaged point per calendar day, oldest→newest.
    To get the true 7-days-ago point we index 8 from the end (the newest point is
    "today"); we fall back to the oldest available point for short histories.
    """
    history = db.get_price_history(region_id, days=14)
    if not history:
        return 0.0
    prices = [p for _, p in history]
    if len(prices) >= 8:
        return round(current_price - prices[-8], 3)
    if len(prices) >= 2:
        return round(current_price - prices[0], 3)
    return 0.0


# ── Determine verdict ─────────────────────────────────────────────────────────

def determine_verdict(
    price_dir: str,
    wti_dir: str,
    week_delta: float,
    price: float,
    region_id: str,
    price_source: str | None = None,
) -> str:
    """
    Rule-based verdict: 'buy' | 'partial' | 'wait'.
    Considers price direction, WTI direction, and recent delta.

    Confidence guard: when the price is a static baseline (no real source), or the
    signals are degenerate (perfectly flat price AND flat WTI), there is no real
    information to act on — return the honest 'partial' rather than a misleading
    uniform 'buy'. This prevents every region collapsing to the same verdict when
    upstream data is missing.
    """
    if price_source == "baseline":
        return "partial"
    if week_delta == 0 and wti_dir == "flat" and price_dir == "flat":
        return "partial"

    # Strong buy signal: prices dropping or flat AND WTI easing
    if price_dir in ("down", "flat") and wti_dir in ("down", "flat") and week_delta <= 0.01:
        return "buy"
    # Strong wait signal: prices rising AND WTI rising AND last week was up
    if price_dir == "up" and (wti_dir == "up" or week_delta >= 0.05):
        return "wait"
    # Mixed signals
    return "partial"
