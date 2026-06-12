"""Validate the generated frontend/data/data.json contract (no network)."""
import json
import pathlib

import pytest

DATA = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "data" / "data.json"

REQUIRED = {"id", "state", "abbr", "city", "country", "unit", "verdict",
            "price", "priceLow", "weekDelta", "why", "advice", "bestDayIdx",
            "wtiDir", "news", "breakdown", "trend", "priceSource"}


@pytest.fixture(scope="module")
def payload():
    assert DATA.exists(), f"{DATA} not generated yet — run backend/snapshot.py"
    return json.loads(DATA.read_text())


def test_region_count(payload):
    assert len(payload["regions"]) == 62


def test_required_keys_and_units(payload):
    for r in payload["regions"]:
        missing = REQUIRED - r.keys()
        assert not missing, f"{r.get('id')} missing keys: {missing}"
        # Units always match country: US=$/gal, CA=$/L.
        expected_unit = "L" if r["country"] == "CA" else "gal"
        assert r["unit"] == expected_unit, f"{r['id']} unit/country mismatch"


def test_trend_is_14_points(payload):
    for r in payload["regions"]:
        assert len(r["trend"]) == 14, f"{r['id']} trend not 14 points"


def test_price_low_not_above_price(payload):
    for r in payload["regions"]:
        assert r["priceLow"] <= r["price"] + 1e-6, f"{r['id']} priceLow > price"


def test_at_least_one_region_has_real_movement(payload):
    """The core regression guard: not every trend may be flat."""
    moving = [r["id"] for r in payload["regions"] if len(set(r["trend"])) > 1]
    assert moving, "every region has a flat trend — price data is stale"


def test_low_station_shape_when_present(payload):
    for r in payload["regions"]:
        low = r.get("lowStation")
        if low:
            assert {"id", "price", "url"} <= low.keys()
            assert low["url"].startswith("https://www.gasbuddy.com/station/")
