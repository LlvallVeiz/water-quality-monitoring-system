"""Tests for the alert engine: persistence, escalation, dedup, resolve."""

import pytest

from water_quality.alerts import AlertEngine


def _rows(param: str, values: list[float | None], start_day: float = 0.0) -> list[dict]:
    rows = []
    for i, value in enumerate(values):
        row = {"timestamp_day": start_day + i / 24.0, "hour": i % 24,
               "ph": 7.0, "temperature_c": 25.0, "do_mg_l": 8.0,
               "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
               "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0}
        row[param] = value
        rows.append(row)
    return rows


def test_no_alert_below_persistence():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0]))  # below warning 4, only 2 readings
    assert engine.alerts == []


def test_alert_after_persistence_readings():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0, 3.0, 3.0]))
    assert len(engine.alerts) == 1
    alert = engine.alerts[0]
    assert alert.parameter == "do_mg_l"
    assert alert.level == "warning"
    assert alert.triggered_at_day == pytest.approx(0.0)
    assert alert.peak_value == 3.0


def test_single_spike_never_alerts():
    engine = AlertEngine(persistence=3)
    values = [8.0, 8.0, 1.0, 8.0, 8.0, 8.0, 1.0, 8.0]
    engine.process("S1", _rows("do_mg_l", values))
    assert engine.alerts == []


def test_escalation_to_critical():
    engine = AlertEngine(persistence=3)
    # 3 warning readings, then critical readings (DO < 2).
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0, 3.0, 1.5, 1.5]))
    assert len(engine.alerts) == 1
    assert engine.alerts[0].max_level == "critical"
    assert engine.alerts[0].level == "warning"  # triggered as warning
    assert any(lvl == "critical" for _, lvl in engine.alerts[0].history)


def test_critical_trigger_directly():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [1.0, 1.0, 1.0]))
    assert len(engine.alerts) == 1
    assert engine.alerts[0].level == "critical"
    assert engine.alerts[0].max_level == "critical"


def test_dedup_no_second_alert_while_active():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [3.0] * 10))
    assert len(engine.alerts) == 1
    assert engine.alerts[0].n_readings == 10


def test_resolve_then_new_alert():
    engine = AlertEngine(persistence=3, resolve_after=2)
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0, 3.0, 8.0, 8.0]))
    assert len(engine.alerts) == 1
    assert engine.alerts[0].resolved_at_day is not None
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0, 3.0], start_day=1.0))
    assert len(engine.alerts) == 2


def test_no_resolve_before_enough_in_range():
    engine = AlertEngine(persistence=3, resolve_after=2)
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0, 3.0, 8.0]))
    assert engine.alerts[0].resolved_at_day is None


def test_high_side_alert_turbidity():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("turbidity_ntu", [120.0, 130.0, 110.0]))
    assert len(engine.alerts) == 1
    assert engine.alerts[0].parameter == "turbidity_ntu"
    assert engine.alerts[0].peak_value == 130.0


def test_low_do_peak_tracks_minimum():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [3.5, 2.5, 3.0, 2.0]))
    assert engine.alerts[0].peak_value == 2.0


def test_summary_counts():
    engine = AlertEngine(persistence=2)
    engine.process("S1", _rows("do_mg_l", [3.0, 3.0]))
    engine.process("S1", _rows("turbidity_ntu", [200.0, 200.0], start_day=1.0))
    summary = engine.summary()
    assert summary["total"] == 2
    assert summary["by_parameter"] == {"do_mg_l": 1, "turbidity_ntu": 1}
    assert summary["by_max_level"]["warning"] == 1
    assert summary["by_max_level"]["critical"] == 1  # turbidity 200 > critical 100


def test_missing_values_skipped():
    engine = AlertEngine(persistence=3)
    engine.process("S1", _rows("do_mg_l", [3.0, None, 3.0, 3.0]))
    # None breaks nothing: 3 valid consecutive crossings still trigger.
    assert len(engine.alerts) == 1
