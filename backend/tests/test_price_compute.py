"""Pure unit tests for price sanity-checking + GasBuddy normalization — no network.

NOTE: the `compute_region_prices(..., gasbuddy=, source=)` tests that used to
live here exercise the realtime-headline signature introduced by the companion
price-pipeline PR, not the signature on this branch. They moved with that code;
this file keeps only what this branch actually implements.
"""
import price_collector as pc
from providers import gasbuddy


def test_sanity_check_rejects_out_of_range():
    # 10.0 is way outside ±50% of a 3.00 baseline → fall back to prev price.
    assert pc._sanity_check_price("tx", 10.0, baseline=3.00, prev_price=2.90) == 2.90
    # In-range value passes through unchanged.
    assert pc._sanity_check_price("tx", 3.10, baseline=3.00, prev_price=2.90) == 3.10


def test_gasbuddy_canada_cents_to_dollars(monkeypatch):
    # CA stations report ¢/L; region_low_station must divide by 100 exactly once.
    fake = [{"station_id": "1", "name": "Petro", "lat": 43.6, "lng": -79.4,
             "price_raw": 145.9, "price_unit": "cents", "locality": "Toronto",
             "region": "ON", "url": "https://www.gasbuddy.com/station/1"}]
    monkeypatch.setattr(gasbuddy, "search", lambda *a, **k: list(fake))
    monkeypatch.setattr(gasbuddy.cache, "get", lambda k: None)
    monkeypatch.setattr(gasbuddy.cache, "set", lambda *a, **k: None)
    res = gasbuddy.region_low_station("on", "Toronto, ON", is_canada=True)
    assert res["price"] == 1.459
    assert res["unit"] == "L"


def test_gasbuddy_us_dollars_per_gallon_unchanged(monkeypatch):
    fake = [{"station_id": "2", "name": "Shell", "lat": 30, "lng": -95,
             "price_raw": 2.79, "price_unit": "dollars", "locality": "Houston",
             "region": "TX", "url": "https://www.gasbuddy.com/station/2"}]
    monkeypatch.setattr(gasbuddy, "search", lambda *a, **k: list(fake))
    monkeypatch.setattr(gasbuddy.cache, "get", lambda k: None)
    monkeypatch.setattr(gasbuddy.cache, "set", lambda *a, **k: None)
    res = gasbuddy.region_low_station("tx", "Houston, TX", is_canada=False)
    assert res["price"] == 2.79
    assert res["unit"] == "gal"


def test_search_normalizes_pygasbuddy_result(monkeypatch):
    # py-gasbuddy returns a PriceServiceResult ({"results": [StationPrice, ...]});
    # search() must flatten each station's nested regular_gas node into our
    # {station_id, price_raw, url, ...} shape and drop price-less stations.
    fake_result = {"results": [
        {"station_id": "42", "name": "Costco",
         "latitude": 43.6, "longitude": -79.4, "unit_of_measure": "litre",
         "address": {"locality": "Toronto", "region": "ON"},
         "regular_gas": {"price": 145.9, "cash_price": 143.9}},
        {"station_id": "7", "name": "NoPrice",
         "latitude": 1.0, "longitude": 2.0,
         "regular_gas": {"price": None, "cash_price": None}},
    ]}

    class _FakeClient:
        async def price_lookup_service(self, **kw):
            return fake_result

    monkeypatch.setattr(gasbuddy, "_HAVE_LIB", True)
    monkeypatch.setattr(gasbuddy, "_client", lambda *a, **k: _FakeClient())

    out = gasbuddy.search(lat=43.6, lng=-79.4)
    assert len(out) == 1                       # price-less station dropped
    s = out[0]
    assert s["station_id"] == "42"
    assert s["price_raw"] == 145.9             # native unit preserved (credit wins)
    assert s["price_unit"] == "litre"
    assert s["url"] == "https://www.gasbuddy.com/station/42"


def test_search_without_coords_returns_none(monkeypatch):
    # py-gasbuddy queries by coordinates; no coords -> graceful None (no network).
    monkeypatch.setattr(gasbuddy, "_HAVE_LIB", True)
    assert gasbuddy.search(search_term="Nowhere, ZZ") is None
