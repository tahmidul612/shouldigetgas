"""Pure unit tests for the predictor — no network, no DB writes."""
import predictor
import price_collector as pc


def test_interpolate_to_daily_reflects_movement():
    # Weekly series, newest-first, that genuinely moves.
    weekly = [3.40, 3.20, 3.00]            # this week 3.40, two weeks ago 3.00
    daily = pc.interpolate_to_daily(weekly)
    assert len(daily) >= 2
    # The series must not be flat — successive deltas should be non-zero somewhere.
    deltas = [round(b - a, 4) for a, b in zip(daily, daily[1:])]
    assert any(d != 0 for d in deltas), "interpolated trend is flat"
    # Oldest→newest ordering: ends at the most recent (highest here).
    assert daily[-1] >= daily[0]


def test_build_trend_array_uses_weekly_series_when_no_history():
    # 'zz' has no DB history → must fall back to the weekly series, not a flat line.
    weekly = [3.50, 3.30, 3.10, 2.90]
    trend = predictor.build_trend_array("zz", current_price=3.50, weekly_series=weekly)
    assert len(trend) == 14
    assert len(set(trend)) > 1, "trend should reflect real movement, not be flat"


def test_determine_verdict_baseline_is_partial():
    # No real data source → honest 'partial', never a misleading uniform 'buy'.
    assert predictor.determine_verdict("flat", "flat", 0.0, 3.0, "tx",
                                       price_source="baseline") == "partial"


def test_determine_verdict_degenerate_flat_is_partial():
    assert predictor.determine_verdict("flat", "flat", 0.0, 3.0, "tx",
                                       price_source="eia_state") == "partial"


def test_determine_verdict_falling_real_data_is_buy():
    assert predictor.determine_verdict("down", "down", -0.10, 3.0, "tx",
                                       price_source="eia_state") == "buy"


def test_determine_verdict_rising_real_data_is_wait():
    assert predictor.determine_verdict("up", "up", 0.12, 3.0, "tx",
                                       price_source="eia_state") == "wait"
