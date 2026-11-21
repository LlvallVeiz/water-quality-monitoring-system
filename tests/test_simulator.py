"""Tests for the sensor simulator."""

import pytest

from water_quality.simulator import Event, Simulator, StationConfig


def _rows(config, n_days=5, seed=42):
    return Simulator(config, seed=seed).simulate(n_days)


def test_simulate_length_and_hours():
    rows = _rows(StationConfig(station_id="S1", name="S1"), n_days=3)
    assert len(rows) == 72
    assert [r["hour"] for r in rows[:25]] == list(range(24)) + [0]
    assert rows[0]["timestamp_day"] == 0.0
    assert rows[-1]["timestamp_day"] == pytest.approx(2 + 23 / 24)


def test_simulate_deterministic_same_seed():
    cfg = StationConfig(station_id="S1", name="S1",
                        events=[Event("rain", 1.0, 1.0)])
    a = _rows(cfg, seed=7)
    b = _rows(cfg, seed=7)
    assert a == b


def test_simulate_different_seed_differs():
    cfg = StationConfig(station_id="S1", name="S1")
    a = _rows(cfg, seed=1)
    b = _rows(cfg, seed=2)
    assert a != b


def test_values_in_physical_ranges():
    rows = _rows(StationConfig(station_id="S1", name="S1"), n_days=30)
    for r in rows:
        if r["ph"] is None:  # gap reading: all parameters are None
            continue
        assert 0.0 <= r["ph"] <= 14.0
        assert 0.0 <= r["do_mg_l"] <= 20.0
        assert r["turbidity_ntu"] >= 0.0
        assert r["conductivity_us_cm"] >= 0.0
        assert r["nitrate_mg_l_n"] >= 0.0


def test_tds_derived_from_conductivity():
    rows = _rows(StationConfig(station_id="S1", name="S1"), n_days=2)
    for r in rows:
        assert r["tds_mg_l"] == pytest.approx(r["conductivity_us_cm"] * 0.64, abs=1e-3)


def test_diurnal_temperature_peak_afternoon():
    rows = _rows(StationConfig(station_id="S1", name="S1",
                               noise={"temperature_c": 0.0}), n_days=2)
    day0 = rows[:24]
    temps = {r["hour"]: r["temperature_c"] for r in day0}
    assert temps[14] > temps[2]  # afternoon warmer than night
    assert temps[14] > temps[22]


def test_rain_event_raises_turbidity_and_nitrate():
    base = _rows(StationConfig(station_id="S1", name="S1"), n_days=4, seed=3)
    rain = _rows(StationConfig(
        station_id="S1", name="S1",
        events=[Event("rain", 1.0, 2.0, magnitude=1.0)]), n_days=4, seed=3)
    # Day 2 is the event peak (mid-pulse); compare daily means.
    def day_mean(rows, day, param):
        vals = [r[param] for r in rows
                if int(r["timestamp_day"]) == day and r[param] is not None]
        return sum(vals) / len(vals)
    assert day_mean(rain, 2, "turbidity_ntu") > day_mean(base, 2, "turbidity_ntu") + 20
    assert day_mean(rain, 2, "nitrate_mg_l_n") > day_mean(base, 2, "nitrate_mg_l_n") + 1
    assert day_mean(rain, 2, "do_mg_l") < day_mean(base, 2, "do_mg_l")


def test_bloom_event_lowers_do_and_raises_ph():
    base = _rows(StationConfig(station_id="S1", name="S1"), n_days=4, seed=3)
    bloom = _rows(StationConfig(
        station_id="S1", name="S1",
        events=[Event("bloom", 1.0, 2.0)]), n_days=4, seed=3)
    def day_mean(rows, day, param):
        vals = [r[param] for r in rows
                if int(r["timestamp_day"]) == day and r[param] is not None]
        return sum(vals) / len(vals)
    assert day_mean(bloom, 2, "do_mg_l") < day_mean(base, 2, "do_mg_l") - 0.5
    assert day_mean(bloom, 2, "ph") > day_mean(base, 2, "ph") + 0.1


def test_spill_event_raises_conductivity_and_orp():
    base = _rows(StationConfig(station_id="S1", name="S1"), n_days=4, seed=3)
    spill = _rows(StationConfig(
        station_id="S1", name="S1",
        events=[Event("spill", 1.0, 1.0)]), n_days=4, seed=3)
    def day_mean(rows, day, param):
        vals = [r[param] for r in rows
                if int(r["timestamp_day"]) == day and r[param] is not None]
        return sum(vals) / len(vals)
    assert day_mean(spill, 1, "conductivity_us_cm") > day_mean(base, 1, "conductivity_us_cm") + 100
    assert day_mean(spill, 1, "orp_mv") > day_mean(base, 1, "orp_mv") + 20


def test_event_shape_is_zero_outside_window():
    event = Event("rain", 2.0, 1.0)
    assert event.shape(1.9) == 0.0
    assert event.shape(3.1) == 0.0
    assert 0.0 < event.shape(2.5) <= 1.0
    assert event.shape(2.5) == pytest.approx(1.0)  # mid-pulse peak


def test_event_unknown_kind_raises():
    with pytest.raises(ValueError):
        Event("meteor", 1.0, 1.0).effects()


def test_gap_windows_produce_none():
    cfg = StationConfig(station_id="S1", name="S1", gap_probability=0.0,
                        gap_windows=[(1.0, 2.0)])
    rows = _rows(cfg, n_days=3)
    day1 = [r for r in rows if int(r["timestamp_day"]) == 1]
    assert all(r["ph"] is None for r in day1)
    day0 = [r for r in rows if int(r["timestamp_day"]) == 0]
    assert all(r["ph"] is not None for r in day0)


def test_random_gaps_match_probability_roughly():
    cfg = StationConfig(station_id="S1", name="S1", gap_probability=0.1)
    rows = _rows(cfg, n_days=30)
    missing = sum(1 for r in rows if r["ph"] is None)
    assert 30 < missing < 150  # ~10 % of 720, wide tolerance


def test_drift_increases_turbidity_over_time():
    cfg = StationConfig(station_id="S1", name="S1",
                        drift_per_day={"turbidity_ntu": 1.0},
                        noise={"turbidity_ntu": 0.0})
    rows = _rows(cfg, n_days=10)
    first = sum(r["turbidity_ntu"] for r in rows[:24]) / 24
    last = sum(r["turbidity_ntu"] for r in rows[-24:]) / 24
    assert last - first == pytest.approx(9.0, abs=1.5)


def test_baseline_override_respected():
    rows = _rows(StationConfig(station_id="S1", name="S1",
                               baseline={"ph": 8.5},
                               noise={"ph": 0.0}), n_days=1)
    assert all(abs(r["ph"] - 8.5) < 0.2 for r in rows)
