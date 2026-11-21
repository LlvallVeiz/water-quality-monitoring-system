"""Dissolved-oxygen saturation concentration.

The saturation concentration of oxygen in freshwater is computed with
the Benson & Krause equation as adopted by APHA Standard Methods
(Section 4500-O), valid at 1 atm:

    ln(C*) = -139.34411 + 1.575701e5/T - 6.642308e7/T**2
             + 1.243800e10/T**3 - 8.621949e11/T**4

with T in kelvin and C* in mg/L. Percent saturation is then
100 * DO_measured / C*. The NSF WQI dissolved-oxygen sub-index is
defined on percent saturation, so this module is the bridge between a
raw DO reading (mg/L) and the index.
"""

from __future__ import annotations

import math


def do_saturation_mg_l(temperature_c: float) -> float:
    """Saturation DO concentration (mg/L) in freshwater at 1 atm.

    >>> round(do_saturation_mg_l(20.0), 2)
    9.09
    >>> round(do_saturation_mg_l(25.0), 2)
    8.26
    >>> round(do_saturation_mg_l(0.0), 2)
    14.62
    """
    if temperature_c < -5.0 or temperature_c > 50.0:
        raise ValueError(f"temperature out of range: {temperature_c} degC")
    t_k = temperature_c + 273.15
    ln_c = (
        -139.34411
        + 1.575701e5 / t_k
        - 6.642308e7 / t_k**2
        + 1.243800e10 / t_k**3
        - 8.621949e11 / t_k**4
    )
    return math.exp(ln_c)


def do_percent_saturation(do_mg_l: float, temperature_c: float) -> float:
    """Dissolved oxygen as percent of saturation.

    >>> round(do_percent_saturation(7.5, 25.0), 1)
    90.8
    """
    if do_mg_l < 0:
        raise ValueError(f"DO cannot be negative: {do_mg_l}")
    return 100.0 * do_mg_l / do_saturation_mg_l(temperature_c)


def do_mg_l_from_percent(percent: float, temperature_c: float) -> float:
    """DO concentration (mg/L) for a given percent saturation."""
    if percent < 0:
        raise ValueError(f"percent saturation cannot be negative: {percent}")
    return percent / 100.0 * do_saturation_mg_l(temperature_c)
