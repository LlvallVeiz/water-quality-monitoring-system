"""Tests for the station network and downstream propagation."""

import json

import pytest

from water_quality.network import Network, load_network, network_to_dict
from water_quality.simulator import Event, StationConfig


def test_propagate_events_lag_and_attenuation():
    upstream = StationConfig(
        station_id="U", name="Up", river_km=0.0,
        events=[Event("rain", 2.0, 1.0, magnitude=1.0)])
    downstream = StationConfig(station_id="D", name="Down", river_km=24.0)
    net = Network(river="R", stations=[upstream, downstream],
                  flow_velocity_km_per_day=24.0, attenuation_per_km=0.01)
    net.propagate_events()
    assert len(downstream.events) == 1
    propagated = downstream.events[0]
    assert propagated.kind == "rain"
    assert propagated.start_day == pytest.approx(3.0)  # 24 km / 24 km/day
    assert propagated.magnitude == pytest.approx(0.99 ** 24, abs=1e-9)


def test_propagate_events_keeps_own_events():
    upstream = StationConfig(
        station_id="U", name="Up", river_km=0.0,
        events=[Event("rain", 1.0, 1.0)])
    downstream = StationConfig(
        station_id="D", name="Down", river_km=10.0,
        events=[Event("spill", 5.0, 1.0)])
    net = Network(river="R", stations=[upstream, downstream])
    net.propagate_events()
    kinds = sorted(e.kind for e in downstream.events)
    assert kinds == ["rain", "spill"]


def test_propagate_events_no_upstream_no_change():
    solo = StationConfig(station_id="S", name="Solo", river_km=0.0)
    net = Network(river="R", stations=[solo])
    net.propagate_events()
    assert solo.events == []


def test_simulate_all_deterministic():
    net = Network(river="R", stations=[
        StationConfig(station_id="A", name="A", river_km=0.0),
        StationConfig(station_id="B", name="B", river_km=5.0)])
    first = net.simulate_all(2, seed=11)
    second = net.simulate_all(2, seed=11)
    assert first == second
    assert set(first) == {"A", "B"}
    assert len(first["A"]) == 48


def test_load_network_from_json(tmp_path):
    data = {
        "river": "Kali Test",
        "flow_velocity_km_per_day": 12.0,
        "stations": [
            {"station_id": "K-01", "name": "Hulu", "river_km": 0.0,
             "baseline": {"ph": 7.5},
             "events": [{"kind": "rain", "start_day": 1.0, "duration_days": 2.0}]},
            {"station_id": "K-02", "name": "Hilir", "river_km": 6.0},
        ],
    }
    path = tmp_path / "net.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    net = load_network(str(path))
    assert net.river == "Kali Test"
    assert net.flow_velocity_km_per_day == 12.0
    assert len(net.stations) == 2
    assert net.stations[0].merged_baseline()["ph"] == 7.5
    assert net.stations[0].events[0].kind == "rain"


def test_network_to_dict_round_trip():
    net = Network(river="R", stations=[
        StationConfig(station_id="A", name="A", river_km=0.0,
                      events=[Event("bloom", 1.0, 2.0, 0.5)])])
    data = network_to_dict(net)
    assert data["river"] == "R"
    assert data["stations"][0]["events"][0]["magnitude"] == 0.5
