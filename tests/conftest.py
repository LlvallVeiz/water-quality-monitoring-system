"""Shared fixtures for the water-quality test suite."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from water_quality.network import Network
from water_quality.simulator import Event, StationConfig


@pytest.fixture
def small_network() -> Network:
    """Two-station network with a rain event upstream."""
    upstream = StationConfig(
        station_id="T-01", name="Upstream", river_km=0.0,
        events=[Event(kind="rain", start_day=2.0, duration_days=1.0)],
    )
    downstream = StationConfig(
        station_id="T-02", name="Downstream", river_km=12.0,
    )
    return Network(river="Test River", stations=[upstream, downstream])


@pytest.fixture
def flat_rows() -> list[dict]:
    """10 days of perfectly flat hourly readings (no noise, no events)."""
    rows = []
    for h in range(10 * 24):
        rows.append({
            "timestamp_day": h / 24.0, "hour": h % 24,
            "ph": 7.0, "temperature_c": 25.0, "do_mg_l": 8.0,
            "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
            "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0,
        })
    return rows
