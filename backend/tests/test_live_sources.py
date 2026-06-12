"""
Short live-API tests against the real data providers.

Marked `network` so they can be skipped offline with `-m "not network"`. Each is
a single round-trip and finishes in a few seconds.
"""
import pytest

from conftest import requires_eia
import price_collector as pc
from providers import gasbuddy

pytestmark = pytest.mark.network


@requires_eia
def test_eia_state_returns_moving_series():
    series = pc.fetch_eia_state_prices(["CA"]).get("CA", [])
    assert len(series) >= 2, "EIA state series too short"
    assert len(set(series)) > 1, "EIA state series is flat (suspicious)"


@requires_eia
def test_eia_padd_codes_resolve():
    # The P# → R## translation must return a real Gulf-Coast (P3) series.
    series = pc.fetch_eia_padd_prices(["P3"]).get("P3", [])
    assert len(series) >= 2, "EIA PADD P3 returned nothing — duoarea code wrong?"
    assert all(1.0 < v < 8.0 for v in series), "PADD prices out of plausible $/gal range"


def test_nrcan_returns_plausible_prices():
    data = pc.fetch_nrcan_prices()
    assert data, "NRCAN scrape returned nothing"
    # At least one tracked Canadian city with a plausible $/L series.
    series = data.get("Toronto") or data.get("Canada")
    assert series and all(0.8 <= v <= 3.0 for v in series), "NRCAN $/L out of range"


def test_gasbuddy_never_raises_and_degrades_gracefully():
    # Resilience contract: returns a station dict where reachable, or None when
    # blocked by Cloudflare — but never raises. (None on hardened datacenter IPs;
    # a real station from a residential host.)
    res = gasbuddy.region_low_station("on", "Toronto, ON", is_canada=True)
    assert res is None or (isinstance(res, dict) and "url" in res and "price" in res)
