"""Tests for statistical analysis: stats, exceedance, trends, anomalies."""

import pytest

from water_quality.analysis import (
    correlation_matrix,
    describe,
    detect_anomalies,
    exceedance,
    linear_trend,
    mann_kendall,
    station_summary,
)


def _rows(param_values, param="ph", start=0.0):
    rows = []
    for i, value in enumerate(param_values):
        row = {"timestamp_day": start + i / 24.0, "hour": i % 24,
               "ph": 7.0, "temperature_c": 25.0, "do_mg_l": 8.0,
               "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
               "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0}
        row[param] = value
        rows.append(row)
    return rows


def test_describe_hand_computed():
    stats = describe(_rows([1.0, 2.0, 3.0, 4.0]), "ph")
    assert stats["n"] == 4
    assert stats["mean"] == pytest.approx(2.5)
    assert stats["min"] == 1.0
    assert stats["max"] == 4.0
    assert stats["std"] == pytest.approx(1.29099, abs=1e-4)
    assert stats["completeness"] == 1.0


def test_describe_with_missing_values():
    stats = describe(_rows([1.0, None, 3.0]), "ph")
    assert stats["n"] == 2
    assert stats["completeness"] == pytest.approx(2 / 3, abs=1e-3)


def test_describe_empty():
    stats = describe(_rows([None, None]), "ph")
    assert stats["n"] == 0
    assert stats["mean"] is None


def test_exceedance_nitrate_class_ii():
    rows = _rows([5.0, 12.0, 8.0, 15.0], "nitrate_mg_l_n")
    exc = exceedance(rows, "nitrate_mg_l_n", "II")
    assert exc["n"] == 4
    assert exc["n_exceed"] == 2
    assert exc["pct_exceed"] == 50.0


def test_exceedance_do_minimum():
    rows = _rows([7.0, 3.0, 5.0, 2.0], "do_mg_l")
    exc = exceedance(rows, "do_mg_l", "II")
    assert exc["n_exceed"] == 2  # 3.0 and 2.0 below the 4 mg/L minimum
    assert exc["pct_exceed"] == 50.0


def test_exceedance_ph_range():
    rows = _rows([7.0, 5.5, 9.5, 7.2], "ph")
    exc = exceedance(rows, "ph", "II")
    assert exc["n_exceed"] == 2


def test_exceedance_unknown_parameter_raises():
    with pytest.raises(KeyError):
        exceedance(_rows([1.0, 2.0]), "turbidity_ntu")


def test_linear_trend_exact_line():
    # y = 2x + 1 over days 0..9 (one reading per day).
    rows = [{"timestamp_day": float(d), "hour": 0, "ph": 2.0 * d + 1.0,
             "temperature_c": 25.0, "do_mg_l": 8.0, "turbidity_ntu": 10.0,
             "conductivity_us_cm": 250.0, "tds_mg_l": 160.0,
             "nitrate_mg_l_n": 2.0, "orp_mv": 300.0} for d in range(10)]
    trend = linear_trend(rows, "ph")
    assert trend["slope_per_day"] == pytest.approx(2.0)
    assert trend["intercept"] == pytest.approx(1.0)
    assert trend["r2"] == pytest.approx(1.0)


def test_linear_trend_flat_series():
    rows = _rows([5.0] * 10)
    trend = linear_trend(rows, "ph")
    assert trend["slope_per_day"] == pytest.approx(0.0, abs=1e-9)
    assert trend["r2"] == pytest.approx(0.0)


def test_mann_kendall_increasing():
    result = mann_kendall([float(i) for i in range(10)])
    assert result["S"] == 45
    assert result["tau"] == pytest.approx(1.0)
    assert result["p_value"] < 0.01
    assert result["trend"] == "increasing"


def test_mann_kendall_decreasing():
    result = mann_kendall([float(10 - i) for i in range(10)])
    assert result["S"] == -45
    assert result["trend"] == "decreasing"


def test_mann_kendall_constant():
    result = mann_kendall([5.0] * 10)
    assert result["S"] == 0
    assert result["p_value"] == 1.0
    assert result["trend"] == "no trend"


def test_mann_kendall_too_short():
    result = mann_kendall([1.0, 2.0, 3.0])
    assert result["trend"] == "insufficient data"


def test_correlation_perfect_positive():
    rows = []
    for i in range(10):
        rows.append({"timestamp_day": i / 24.0, "hour": i % 24,
                     "ph": float(i), "temperature_c": 25.0, "do_mg_l": 8.0,
                     "turbidity_ntu": float(2 * i), "conductivity_us_cm": 250.0,
                     "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0})
    matrix = correlation_matrix(rows, ["ph", "turbidity_ntu"])
    assert matrix["ph"]["turbidity_ntu"] == pytest.approx(1.0)
    assert matrix["ph"]["ph"] == pytest.approx(1.0)


def test_correlation_constant_series_is_none():
    rows = _rows([5.0] * 10)
    matrix = correlation_matrix(rows, ["ph", "do_mg_l"])
    assert matrix["ph"]["do_mg_l"] is None


def test_detect_anomalies_finds_spike():
    base = [10.0 + (0.1 if i % 2 else -0.1) for i in range(48)]
    values = base + [100.0] + [10.0] * 10
    anomalies = detect_anomalies(_rows(values, "turbidity_ntu"), "turbidity_ntu")
    assert len(anomalies) == 1
    assert anomalies[0]["value"] == 100.0
    assert abs(anomalies[0]["z"]) > 3.0


def test_detect_anomalies_clean_series_empty():
    values = [10.0 + (0.1 if i % 2 else -0.1) for i in range(60)]
    anomalies = detect_anomalies(_rows(values, "turbidity_ntu"), "turbidity_ntu")
    assert anomalies == []


def test_station_summary_covers_all_parameters(flat_rows):
    summary = station_summary(flat_rows, "II")
    assert set(summary) == {"ph", "temperature_c", "do_mg_l", "turbidity_ntu",
                            "conductivity_us_cm", "tds_mg_l",
                            "nitrate_mg_l_n", "orp_mv"}
    assert summary["ph"]["stats"]["mean"] == pytest.approx(7.0)
    assert summary["do_mg_l"]["exceedance"]["pct_exceed"] == 0.0
    assert summary["ph"]["trend"]["mann_kendall"]["trend"] == "no trend"
