"""Tests for NSF and CCME Water Quality Index calculations."""

import pytest

from water_quality.wqi import (
    ccme_class,
    ccme_wqi,
    nsf_class,
    nsf_q_value,
    nsf_wqi,
)

#: The published BASIN worked example (Brown et al. 1970 values).
BASIN_EXAMPLE = {
    "do_percent": 82.0,
    "fecal_coliform": 12.0,
    "ph": 7.67,
    "bod_mg_l": 2.0,
    "temperature_change_c": 5.0,
    "phosphate_mg_l_p": 0.5,
    "nitrate_mg_l_no3": 5.0,
    "turbidity_ntu": 5.0,
    "tds_mg_l": 150.0,
}


def test_nsf_q_values_reproduce_basin_example():
    # DO curve input is percent saturation when no temperature is
    # given: 82 % sat is an anchor point (Q 90). With a temperature
    # the mg/L value is converted to percent saturation first.
    assert nsf_q_value("do_mg_l", 82.0) == pytest.approx(90.0, abs=0.01)
    assert nsf_q_value("do_mg_l", 7.45, temperature_c=20.0) == pytest.approx(90.0, abs=0.5)
    assert nsf_q_value("ph", 7.67) == pytest.approx(92.0, abs=0.5)
    assert nsf_q_value("bod_mg_l", 2.0) == pytest.approx(80.0, abs=0.01)
    assert nsf_q_value("temperature_change_c", 5.0) == pytest.approx(72.0, abs=0.01)
    assert nsf_q_value("phosphate_mg_l_p", 0.5) == pytest.approx(60.0, abs=0.01)
    assert nsf_q_value("nitrate_mg_l_no3", 5.0) == pytest.approx(67.0, abs=0.01)
    assert nsf_q_value("turbidity_ntu", 5.0) == pytest.approx(85.0, abs=0.01)
    assert nsf_q_value("tds_mg_l", 150.0) == pytest.approx(78.0, abs=0.01)
    assert nsf_q_value("fecal_coliform", 12.0) == pytest.approx(72.0, abs=0.01)


def test_nsf_wqi_reproduces_basin_total():
    result = nsf_wqi(BASIN_EXAMPLE)
    assert result["wqi"] == pytest.approx(77.9, abs=0.05)
    assert result["class"] == "Good"
    assert result["n_parameters"] == 9


def test_nsf_wqi_subset_renormalises_weights():
    # BASIN: BOD + temperature change removed -> subtotals 61.9 over
    # weights 0.79 -> WQI 78.4.
    subset = {k: v for k, v in BASIN_EXAMPLE.items()
              if k not in ("bod_mg_l", "temperature_change_c")}
    result = nsf_wqi(subset)
    assert result["wqi"] == pytest.approx(78.4, abs=0.1)
    assert result["weight_sum"] == pytest.approx(0.79, abs=0.01)


def test_nsf_wqi_perfect_water_near_100():
    result = nsf_wqi({
        "do_percent": 100.0, "ph": 7.5, "nitrate_mg_l_no3": 0.0,
        "turbidity_ntu": 0.0, "tds_mg_l": 50.0, "temperature_change_c": 0.0,
    })
    assert result["wqi"] > 90
    assert result["class"] == "Excellent"


def test_nsf_wqi_polluted_water_low():
    result = nsf_wqi({
        "do_percent": 10.0, "ph": 4.0, "nitrate_mg_l_no3": 80.0,
        "turbidity_ntu": 300.0, "tds_mg_l": 1800.0, "temperature_change_c": 20.0,
    })
    assert result["wqi"] < 25
    assert result["class"] == "Very Bad"


def test_nsf_wqi_do_concentration_uses_temperature():
    # Same DO mg/L is worth more (higher % saturation) in warm water.
    cold = nsf_wqi({"do_mg_l": 8.0, "ph": 7.0}, temperature_c=10.0)
    warm = nsf_wqi({"do_mg_l": 8.0, "ph": 7.0}, temperature_c=30.0)
    assert warm["wqi"] > cold["wqi"]


def test_nsf_wqi_nitrate_as_n_converted():
    as_n = nsf_wqi({"nitrate_mg_l_n": 1.13, "ph": 7.0})
    as_no3 = nsf_wqi({"nitrate_mg_l_no3": 5.0, "ph": 7.0})
    assert as_n["wqi"] == pytest.approx(as_no3["wqi"], abs=0.05)


def test_nsf_wqi_empty_raises():
    with pytest.raises(ValueError):
        nsf_wqi({})


def test_nsf_classes():
    assert nsf_class(95) == "Excellent"
    assert nsf_class(90) == "Excellent"
    assert nsf_class(89.9) == "Good"
    assert nsf_class(70) == "Good"
    assert nsf_class(50) == "Medium"
    assert nsf_class(25) == "Bad"
    assert nsf_class(0) == "Very Bad"


def test_ccme_all_pass_is_100():
    obs = [{"ph": 7.0, "do_mg_l": 7.0, "nitrate_mg_l_n": 2.0} for _ in range(10)]
    result = ccme_wqi(obs, {"ph": ("range", (6.0, 9.0)),
                            "do_mg_l": ("min", 4.0),
                            "nitrate_mg_l_n": 10.0})
    assert result["wqi"] == 100.0
    assert result["class"] == "Excellent"
    assert result["F1"] == 0.0 and result["F2"] == 0.0 and result["F3"] == 0.0


def test_ccme_hand_computed_case():
    # 2 variables x 10 tests; nitrate fails 5 of 10 at 20 mg/L vs
    # objective 10 -> excursion 1.0 each.
    # F1 = 50, F2 = 25, nse = 5/20 = 0.25, F3 = 20,
    # WQI = 100 - sqrt(50^2+25^2+20^2)/1.732 = 65.72.
    obs = []
    for i in range(10):
        obs.append({"ph": 7.0,
                    "nitrate_mg_l_n": 20.0 if i < 5 else 5.0})
    result = ccme_wqi(obs, {"ph": ("range", (6.0, 9.0)),
                            "nitrate_mg_l_n": 10.0})
    assert result["F1"] == pytest.approx(50.0)
    assert result["F2"] == pytest.approx(25.0)
    assert result["F3"] == pytest.approx(20.0)
    assert result["wqi"] == pytest.approx(65.72, abs=0.05)
    assert result["class"] == "Fair"
    assert result["failed_variables"] == ["nitrate_mg_l_n"]


def test_ccme_min_objective_excursion():
    # DO 2 mg/L vs minimum 4 -> excursion 4/2 - 1 = 1.0.
    obs = [{"do_mg_l": 2.0}, {"do_mg_l": 8.0}]
    result = ccme_wqi(obs, {"do_mg_l": ("min", 4.0)})
    assert result["F1"] == 100.0
    assert result["F2"] == 50.0
    assert result["nse"] == pytest.approx(0.5)
    assert result["wqi"] == pytest.approx(100 - (100**2 + 50**2 + (0.5 / 0.015) ** 2) ** 0.5 / 1.732, abs=0.05)


def test_ccme_range_objective_both_sides():
    obs = [{"ph": 5.0}, {"ph": 10.0}, {"ph": 7.0}, {"ph": 7.0}]
    result = ccme_wqi(obs, {"ph": ("range", (6.0, 9.0))})
    assert result["failed_tests"] == 2
    assert result["F2"] == 50.0


def test_ccme_classes():
    assert ccme_class(97) == "Excellent"
    assert ccme_class(95) == "Excellent"
    assert ccme_class(90) == "Good"
    assert ccme_class(80) == "Good"
    assert ccme_class(70) == "Fair"
    assert ccme_class(65) == "Fair"
    assert ccme_class(50) == "Marginal"
    assert ccme_class(45) == "Marginal"
    assert ccme_class(10) == "Poor"


def test_ccme_no_observations_raises():
    with pytest.raises(ValueError):
        ccme_wqi([{"ph": 7.0}], {"nitrate_mg_l_n": 10.0})
