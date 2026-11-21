"""Water Quality Index: NSF (1970) and CCME (2001).

NSF WQI
-------
Brown et al. (1970) for the National Sanitation Foundation: each of
nine parameters is converted to a sub-index ("Q-value", 0-100) through
an expert-averaged weighting curve, multiplied by a weighting factor
and summed::

    WQI = sum(Q_i * w_i)

Weights (Brown et al. 1970): DO 0.17, fecal coliform 0.16, pH 0.11,
BOD 0.11, temperature change 0.10, total phosphate 0.10, nitrate
0.10, turbidity 0.08, total solids 0.07 (sum 1.00).

The published curves exist as graphs; this module implements them as
piecewise-linear interpolations over anchor points calibrated so the
published BASIN worked example is reproduced exactly:

    DO 82 % sat -> Q 90, fecal coliform 12 -> 72, pH 7.67 -> 92,
    BOD 2 mg/L -> 80, delta-T 5 degC -> 72, phosphate 0.5 -> 60,
    nitrate 5 mg/L as NO3 -> 67, turbidity 5 NTU -> 85,
    total solids 150 mg/L -> 78, giving WQI = 77.9.

When fewer than nine parameters are available the weights are
renormalised over the parameters present, exactly as BASIN documents
("add the subtotals, add the weights, divide"). Our sensor network
measures DO, pH, nitrate, turbidity, TDS and temperature change, so
the NSF score reported here is a six-parameter NSF-style index; the
docstring and reports say so explicitly.

NSF classes (Brown et al. 1970): 90-100 Excellent, 70-90 Good,
50-70 Medium, 25-50 Bad, 0-25 Very Bad.

CCME WQI
--------
Canadian Council of Ministers of the Environment (2001): an
objective-based index from three factors::

    F1 (scope)     = 100 * failed variables / total variables
    F2 (frequency) = 100 * failed tests / total tests
    F3 (amplitude) = nse / (0.01*nse + 0.01), nse = sum(excursions)/tests
    WQI = 100 - sqrt(F1^2 + F2^2 + F3^2) / 1.732

Excursion of a failed test: (value/objective - 1) when the objective
must not be exceeded, (objective/value - 1) when it must not fall
below, and for a range objective the distance to the nearest bound
divided by that bound.

CCME classes: 95-100 Excellent, 80-94 Good, 65-79 Fair, 45-64
Marginal, 0-44 Poor.
"""

from __future__ import annotations

import math

from .do_saturation import do_percent_saturation
from .parameters import nitrate_as_no3

#: NSF weighting factors (Brown et al. 1970).
NSF_WEIGHTS: dict[str, float] = {
    "do_mg_l": 0.17,
    "fecal_coliform": 0.16,
    "ph": 0.11,
    "bod_mg_l": 0.11,
    "temperature_change_c": 0.10,
    "phosphate_mg_l_p": 0.10,
    "nitrate_mg_l_no3": 0.10,
    "turbidity_ntu": 0.08,
    "tds_mg_l": 0.07,
}

#: Piecewise-linear anchors (x, Q) approximating the NSF weighting
#: curves. Anchors are calibrated to the BASIN worked example (see
#: module docstring); values between anchors are linearly
#: interpolated, values outside the anchor range clamp to the ends.
NSF_CURVES: dict[str, list[tuple[float, float]]] = {
    "do_mg_l": [  # x = DO percent saturation
        (0, 2), (10, 12), (20, 22), (30, 33), (40, 44), (50, 55),
        (60, 66), (70, 77), (80, 88), (82, 90), (90, 93), (100, 96),
        (110, 95), (120, 90), (140, 80),
    ],
    "ph": [
        (2, 2), (3, 10), (4, 25), (5, 45), (6, 70), (6.5, 84),
        (7, 90), (7.5, 93), (8, 90), (8.5, 82), (9, 70), (10, 50),
        (11, 25), (12, 5),
    ],
    "nitrate_mg_l_no3": [  # x = mg/L as NO3
        (0, 97), (1, 95), (2, 90), (5, 67), (10, 50), (20, 35),
        (30, 25), (40, 18), (50, 12), (100, 5),
    ],
    "turbidity_ntu": [
        (0, 98), (5, 85), (10, 75), (25, 60), (50, 45), (100, 30),
        (200, 15), (400, 5),
    ],
    "tds_mg_l": [  # NSF "total solids"
        (0, 85), (50, 85), (100, 82), (150, 78), (200, 72), (300, 60),
        (500, 40), (1000, 20), (2000, 5),
    ],
    "bod_mg_l": [
        (0, 95), (1, 90), (2, 80), (3, 70), (5, 55), (8, 40),
        (10, 30), (20, 12), (30, 5),
    ],
    "phosphate_mg_l_p": [
        (0, 98), (0.1, 90), (0.5, 60), (1, 45), (2, 30), (5, 15),
        (10, 5),
    ],
    "fecal_coliform": [  # x = colonies / 100 mL
        (0, 98), (1, 95), (12, 72), (50, 55), (100, 45), (500, 25),
        (1000, 15), (10000, 2),
    ],
    "temperature_change_c": [  # x = |delta T| in degC
        (0, 92), (1, 88), (2, 84), (5, 72), (8, 58), (10, 48),
        (15, 28), (20, 12), (30, 2),
    ],
}


def _interp(x: float, anchors: list[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation with clamping at the ends."""
    if x <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return anchors[-1][1]


def nsf_q_value(parameter: str, value: float, temperature_c: float | None = None) -> float:
    """NSF sub-index (Q-value, 0-100) for one parameter reading.

    ``do_mg_l`` is interpreted as a concentration and converted to
    percent saturation using ``temperature_c``; pass a percent
    saturation directly via ``do_percent`` instead if preferred.
    """
    if parameter == "do_mg_l" and temperature_c is not None:
        value = do_percent_saturation(value, temperature_c)
    anchors = NSF_CURVES[parameter]
    return _interp(value, anchors)


def nsf_wqi(
    values: dict[str, float],
    temperature_c: float | None = None,
) -> dict:
    """Compute the NSF-style WQI from a dict of parameter readings.

    Accepted keys: ``do_mg_l`` (needs ``temperature_c`` for the
    percent-saturation conversion), ``do_percent``, ``ph``,
    ``nitrate_mg_l_n`` (converted to as-NO3), ``nitrate_mg_l_no3``,
    ``turbidity_ntu``, ``tds_mg_l``, ``bod_mg_l``,
    ``phosphate_mg_l_p``, ``fecal_coliform`` and
    ``temperature_change_c``. Unknown keys are ignored. Weights are
    renormalised over the parameters actually present (BASIN subset
    rule). Returns ``{"wqi", "class", "subindices", "n_parameters"}``.
    """
    q_values: dict[str, float] = {}
    if "do_mg_l" in values:
        q_values["do_mg_l"] = nsf_q_value("do_mg_l", values["do_mg_l"], temperature_c)
    if "do_percent" in values:
        q_values["do_mg_l"] = _interp(values["do_percent"], NSF_CURVES["do_mg_l"])
    if "ph" in values:
        q_values["ph"] = nsf_q_value("ph", values["ph"])
    if "nitrate_mg_l_no3" in values:
        q_values["nitrate_mg_l_no3"] = nsf_q_value(
            "nitrate_mg_l_no3", values["nitrate_mg_l_no3"])
    elif "nitrate_mg_l_n" in values:
        q_values["nitrate_mg_l_no3"] = nsf_q_value(
            "nitrate_mg_l_no3", nitrate_as_no3(values["nitrate_mg_l_n"]))
    for key in ("turbidity_ntu", "tds_mg_l", "bod_mg_l",
                "phosphate_mg_l_p", "fecal_coliform", "temperature_change_c"):
        if key in values:
            q_values[key] = nsf_q_value(key, values[key])
    if not q_values:
        raise ValueError("no NSF parameters supplied")
    weight_sum = sum(NSF_WEIGHTS[k] for k in q_values)
    wqi = sum(q_values[k] * NSF_WEIGHTS[k] for k in q_values) / weight_sum
    return {
        "wqi": round(wqi, 2),
        "class": nsf_class(wqi),
        "subindices": {k: round(v, 2) for k, v in q_values.items()},
        "n_parameters": len(q_values),
        "weight_sum": round(weight_sum, 2),
    }


def nsf_class(wqi: float) -> str:
    """NSF WQI class label (Brown et al. 1970)."""
    if wqi >= 90:
        return "Excellent"
    if wqi >= 70:
        return "Good"
    if wqi >= 50:
        return "Medium"
    if wqi >= 25:
        return "Bad"
    return "Very Bad"


def ccme_wqi(
    observations: list[dict[str, float]],
    objectives: dict[str, object],
) -> dict:
    """Compute the CCME WQI over a list of observation dicts.

    ``objectives`` maps a parameter key to its objective: a float for
    a must-not-exceed limit, ``("min", value)`` for a must-not-fall-
    below limit, or ``("range", (low, high))`` for a two-sided limit.
    A parameter is counted in the scope (F1) only if it has at least
    one observation. Returns ``{"wqi", "class", "F1", "F2", "F3",
    "nse", "failed_variables", "failed_tests", "total_tests"}``.
    """
    total_vars = 0
    failed_vars: set[str] = set()
    total_tests = 0
    failed_tests = 0
    excursion_sum = 0.0
    for param, objective in objectives.items():
        values = [obs[param] for obs in observations if param in obs and obs[param] is not None]
        if not values:
            continue
        total_vars += 1
        for value in values:
            total_tests += 1
            failed, excursion = _check_objective(value, objective)
            if failed:
                failed_tests += 1
                failed_vars.add(param)
                excursion_sum += excursion
    if total_vars == 0 or total_tests == 0:
        raise ValueError("no observations matching the objectives")
    f1 = 100.0 * len(failed_vars) / total_vars
    f2 = 100.0 * failed_tests / total_tests
    nse = excursion_sum / total_tests
    f3 = nse / (0.01 * nse + 0.01)
    wqi = 100.0 - math.sqrt(f1**2 + f2**2 + f3**2) / 1.732
    return {
        "wqi": round(max(0.0, min(100.0, wqi)), 2),
        "class": ccme_class(wqi),
        "F1": round(f1, 2),
        "F2": round(f2, 2),
        "F3": round(f3, 2),
        "nse": round(nse, 4),
        "failed_variables": sorted(failed_vars),
        "failed_tests": failed_tests,
        "total_tests": total_tests,
    }


def _check_objective(value: float, objective: object) -> tuple[bool, float]:
    """Return (failed, excursion) for one value against one objective."""
    if isinstance(objective, tuple) and objective and objective[0] == "min":
        bound = float(objective[1])  # type: ignore[index]
        if value >= bound:
            return False, 0.0
        return True, (bound / value - 1.0) if value > 0 else float("inf")
    if isinstance(objective, tuple) and objective and objective[0] == "range":
        lo, hi = objective[1]  # type: ignore[index]
        if lo <= value <= hi:
            return False, 0.0
        if value < lo:
            return True, (lo / value - 1.0) if value > 0 else float("inf")
        return True, value / hi - 1.0
    bound = float(objective)  # type: ignore[arg-type]
    if value <= bound:
        return False, 0.0
    return True, value / bound - 1.0


def ccme_class(wqi: float) -> str:
    """CCME WQI class label (CCME 2001)."""
    if wqi >= 95:
        return "Excellent"
    if wqi >= 80:
        return "Good"
    if wqi >= 65:
        return "Fair"
    if wqi >= 45:
        return "Marginal"
    return "Poor"
