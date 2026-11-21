"""Tests for DO saturation (Benson & Krause / APHA 4500-O)."""

import math

import pytest

from water_quality.do_saturation import (
    do_mg_l_from_percent,
    do_percent_saturation,
    do_saturation_mg_l,
)


def test_saturation_known_values():
    # Standard textbook values for freshwater at 1 atm.
    assert do_saturation_mg_l(20.0) == pytest.approx(9.09, abs=0.01)
    assert do_saturation_mg_l(25.0) == pytest.approx(8.26, abs=0.01)
    assert do_saturation_mg_l(0.0) == pytest.approx(14.62, abs=0.02)
    assert do_saturation_mg_l(30.0) == pytest.approx(7.56, abs=0.01)


def test_saturation_decreases_with_temperature():
    temps = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0]
    sats = [do_saturation_mg_l(t) for t in temps]
    assert all(b < a for a, b in zip(sats, sats[1:]))


def test_percent_saturation_round_trip():
    for temp in (10.0, 20.0, 28.0):
        for pct in (50.0, 82.0, 100.0):
            mg = do_mg_l_from_percent(pct, temp)
            assert do_percent_saturation(mg, temp) == pytest.approx(pct, abs=1e-9)


def test_percent_saturation_basin_example():
    # DO 82 % saturation is the BASIN worked-example input.
    assert do_percent_saturation(do_mg_l_from_percent(82.0, 20.0), 20.0) == pytest.approx(82.0)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        do_saturation_mg_l(60.0)
    with pytest.raises(ValueError):
        do_percent_saturation(-1.0, 20.0)
    with pytest.raises(ValueError):
        do_mg_l_from_percent(-5.0, 20.0)
