"""Tests for PP 22/2021 + WHO standards and water-class classification."""

import pytest

from water_quality.standards import (
    WHO_GDWQ,
    check_value,
    classify_water_class,
    limit_for,
    PP22_RIVER,
)


def test_pp22_river_limits_match_regulation():
    # Values verified against PP 22/2021 Lampiran VI (river water).
    assert limit_for("do_mg_l", "I") == 6.0
    assert limit_for("do_mg_l", "II") == 4.0
    assert limit_for("do_mg_l", "III") == 3.0
    assert limit_for("do_mg_l", "IV") == 1.0
    assert limit_for("nitrate_mg_l_n", "I") == 10.0
    assert limit_for("nitrate_mg_l_n", "III") == 20.0
    assert limit_for("tds_mg_l", "I") == 1000.0
    assert limit_for("tds_mg_l", "IV") == 2000.0
    assert limit_for("ph", "II") == (6.0, 9.0)
    assert limit_for("bod_mg_l", "II") == 3.0
    assert limit_for("cod_mg_l", "III") == 40.0
    assert limit_for("tss_mg_l", "I") == 40.0
    assert limit_for("nitrite_mg_l_n", "IV") is None  # no limit in regulation


def test_check_value_max_min_range():
    assert check_value("nitrate_mg_l_n", 9.9, "II") is True
    assert check_value("nitrate_mg_l_n", 10.1, "II") is False
    assert check_value("do_mg_l", 4.0, "II") is True
    assert check_value("do_mg_l", 3.9, "II") is False
    assert check_value("ph", 6.0, "II") is True
    assert check_value("ph", 9.0, "II") is True
    assert check_value("ph", 5.9, "II") is False
    assert check_value("ph", 9.1, "II") is False


def test_check_value_temperature_deviation():
    assert check_value("temperature_c", 2.9, "II") is True
    assert check_value("temperature_c", 3.1, "II") is False


def test_check_value_unknown_parameter():
    with pytest.raises(KeyError):
        check_value("turbidity_ntu", 10.0, "II")  # no PP22 limit for turbidity


def test_classify_water_class_clean_water():
    values = {"ph": 7.2, "do_mg_l": 7.0, "nitrate_mg_l_n": 5.0, "tds_mg_l": 300.0}
    assert classify_water_class(values) == "I"


def test_classify_water_class_class_ii():
    # DO 5.0 fails class I (>= 6) but passes class II (>= 4).
    values = {"ph": 7.2, "do_mg_l": 5.0, "nitrate_mg_l_n": 5.0, "tds_mg_l": 300.0}
    assert classify_water_class(values) == "II"


def test_classify_water_class_class_iii():
    values = {"ph": 7.2, "do_mg_l": 3.5, "nitrate_mg_l_n": 15.0, "tds_mg_l": 300.0}
    assert classify_water_class(values) == "III"


def test_classify_water_class_below_iv():
    values = {"ph": 4.5, "do_mg_l": 0.5, "nitrate_mg_l_n": 50.0, "tds_mg_l": 3000.0}
    assert classify_water_class(values) == "V"


def test_classify_water_class_empty_is_class_i():
    assert classify_water_class({}) == "I"


def test_who_gdwq_values():
    assert WHO_GDWQ["nitrate_mg_l_no3"]["guideline_value"] == 50.0
    assert WHO_GDWQ["nitrite_mg_l_no2"]["guideline_value"] == 3.0
    assert WHO_GDWQ["turbidity_ntu"]["guideline_value"] == 5.0
    # WHO sets no health-based guideline value for pH, TDS or DO.
    assert WHO_GDWQ["ph"]["guideline_value"] is None
    assert WHO_GDWQ["tds_mg_l"]["guideline_value"] is None
    assert WHO_GDWQ["do_mg_l"]["guideline_value"] is None
