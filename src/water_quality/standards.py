"""Water-quality standards: PP No. 22/2021 and WHO GDWQ.

All limit values in this module were taken from the sources listed in
``docs/RESEARCH.md`` and cross-checked against the regulation text
(PP 22/2021, Lampiran VI, "Baku Mutu Air Sungai dan Sejenisnya") and
the WHO Guidelines for Drinking-water Quality, 4th edition.

Verified PP 22/2021 river limits (classes I-IV):

    parameter            I      II     III    IV     unit
    temperature dev.     3      3      3      3      degC
    TDS                  1000   1000   1000   2000   mg/L
    TSS                  40     50     100    400    mg/L
    pH                   6-9    6-9    6-9    6-9    -
    BOD                  2      3      6      12     mg/L
    COD                  10     25     40     80     mg/L
    DO (minimum)         6      4      3      1      mg/L
    nitrate (as N)       10     10     20     20     mg/L as N
    nitrite (as N)       0.06   0.06   0.06   -      mg/L as N
    total phosphate      0.2    0.2    1      -      mg/L as P
    ammonia (as N)       0.1    0.2    0.5    -      mg/L as N

Values marked "-" in the regulation are stored as ``None`` here.
Turbidity, conductivity and ORP have NO limit in PP 22/2021; the
WHO GDWQ gives turbidity < 5 NTU (drinking-water, operational),
nitrate 50 mg/L as NO3 (11.3 mg/L as N), pH 6.5-8.5 (operational, no
health-based guideline value) and no health-based value for TDS or DO.

Alert thresholds (warning/critical) are *operational* levels built on
top of these standards; each entry records its source so a user can
tell a legal limit apart from a project assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: PP 22/2021 river-water classes, in order of strictness.
CLASSES = ("I", "II", "III", "IV")

#: Per-class use of river water (PP 22/2021, Lampiran VI notes).
CLASS_USES = {
    "I": "Raw water for drinking water and other uses requiring equal quality.",
    "II": "Water recreation infrastructure, freshwater fish farming, "
    "animal husbandry, irrigation.",
    "III": "Freshwater fish farming, animal husbandry, irrigation.",
    "IV": "Irrigation of crops.",
    "V": "Does not meet class IV limits.",
}


@dataclass(frozen=True)
class Limit:
    """One regulatory limit for one parameter."""

    parameter: str
    kind: str  # "max", "min" or "range"
    values: dict[str, float | tuple[float, float] | None]
    unit: str
    source: str


def _pp22(source_note: str = "PP 22/2021 Lampiran VI (river)") -> dict[str, Limit]:
    return {
        "temperature_c": Limit(
            "temperature_c", "deviation",
            {"I": 3.0, "II": 3.0, "III": 3.0, "IV": 3.0},
            "degC", source_note,
        ),
        "tds_mg_l": Limit(
            "tds_mg_l", "max",
            {"I": 1000.0, "II": 1000.0, "III": 1000.0, "IV": 2000.0},
            "mg/L", source_note,
        ),
        "ph": Limit(
            "ph", "range",
            {"I": (6.0, 9.0), "II": (6.0, 9.0), "III": (6.0, 9.0), "IV": (6.0, 9.0)},
            "-", source_note,
        ),
        "do_mg_l": Limit(
            "do_mg_l", "min",
            {"I": 6.0, "II": 4.0, "III": 3.0, "IV": 1.0},
            "mg/L", source_note,
        ),
        "nitrate_mg_l_n": Limit(
            "nitrate_mg_l_n", "max",
            {"I": 10.0, "II": 10.0, "III": 20.0, "IV": 20.0},
            "mg/L as N", source_note,
        ),
        "nitrite_mg_l_n": Limit(
            "nitrite_mg_l_n", "max",
            {"I": 0.06, "II": 0.06, "III": 0.06, "IV": None},
            "mg/L as N", source_note,
        ),
        "phosphate_mg_l_p": Limit(
            "phosphate_mg_l_p", "max",
            {"I": 0.2, "II": 0.2, "III": 1.0, "IV": None},
            "mg/L as P", source_note,
        ),
        "ammonia_mg_l_n": Limit(
            "ammonia_mg_l_n", "max",
            {"I": 0.1, "II": 0.2, "III": 0.5, "IV": None},
            "mg/L as N", source_note,
        ),
        "bod_mg_l": Limit(
            "bod_mg_l", "max",
            {"I": 2.0, "II": 3.0, "III": 6.0, "IV": 12.0},
            "mg/L", source_note,
        ),
        "cod_mg_l": Limit(
            "cod_mg_l", "max",
            {"I": 10.0, "II": 25.0, "III": 40.0, "IV": 80.0},
            "mg/L", source_note,
        ),
        "tss_mg_l": Limit(
            "tss_mg_l", "max",
            {"I": 40.0, "II": 50.0, "III": 100.0, "IV": 400.0},
            "mg/L", source_note,
        ),
    }


#: The PP 22/2021 national river-water standards.
PP22_RIVER: dict[str, Limit] = _pp22()

#: WHO Guidelines for Drinking-water Quality, 4th edition (incl. addenda).
#: Only values with a published guideline value or operational target
#: are listed; "no GV" entries are documented, not invented.
WHO_GDWQ: dict[str, dict] = {
    "nitrate_mg_l_no3": {
        "guideline_value": 50.0, "unit": "mg/L as NO3",
        "note": "Health-based guideline value; 11.3 mg/L as N.",
    },
    "nitrite_mg_l_no2": {
        "guideline_value": 3.0, "unit": "mg/L as NO2",
        "note": "Health-based guideline value (short-term).",
    },
    "turbidity_ntu": {
        "guideline_value": 5.0, "unit": "NTU",
        "note": "Operational target for drinking water; "
        "preferably < 1 NTU for effective disinfection. "
        "Not a health-based guideline value.",
    },
    "ph": {
        "guideline_value": None, "unit": "-",
        "note": "No health-based guideline value; operational range "
        "6.5-8.5 for corrosion control and disinfection efficiency.",
    },
    "tds_mg_l": {
        "guideline_value": None, "unit": "mg/L",
        "note": "No health-based guideline value; palatability "
        "generally acceptable below about 1000 mg/L.",
    },
    "do_mg_l": {
        "guideline_value": None, "unit": "mg/L",
        "note": "No WHO drinking-water guideline value for DO.",
    },
}


@dataclass(frozen=True)
class AlertThreshold:
    """Warning/critical alert levels for one parameter.

    ``source`` states where each level comes from; levels marked
    "project assumption" are operational choices of this project, not
    legal limits.
    """

    parameter: str
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    source: str = ""


#: Default alert thresholds, built on PP 22/2021 class II (the usual
#: river-use class) with a stricter "critical" escalation level.
DEFAULT_ALERT_THRESHOLDS: dict[str, AlertThreshold] = {
    "ph": AlertThreshold(
        "ph", warning_low=6.0, warning_high=9.0,
        critical_low=5.0, critical_high=10.0,
        source="Warning = PP 22/2021 class I-IV range 6-9; "
        "critical = project assumption (outside 5-10).",
    ),
    "do_mg_l": AlertThreshold(
        "do_mg_l", warning_low=4.0, critical_low=2.0,
        source="Warning = PP 22/2021 class II minimum 4 mg/L; "
        "critical = project assumption (below 2 mg/L).",
    ),
    "turbidity_ntu": AlertThreshold(
        "turbidity_ntu", warning_high=50.0, critical_high=100.0,
        source="Project assumption (operational river levels); "
        "WHO drinking-water target is 5 NTU, too strict for a river alert.",
    ),
    "nitrate_mg_l_n": AlertThreshold(
        "nitrate_mg_l_n", warning_high=10.0, critical_high=20.0,
        source="Warning = PP 22/2021 class I/II 10 mg/L as N; "
        "critical = PP 22/2021 class III/IV 20 mg/L as N.",
    ),
    "tds_mg_l": AlertThreshold(
        "tds_mg_l", warning_high=1000.0, critical_high=2000.0,
        source="Warning = PP 22/2021 class I-III 1000 mg/L; "
        "critical = PP 22/2021 class IV 2000 mg/L.",
    ),
    "conductivity_us_cm": AlertThreshold(
        "conductivity_us_cm", warning_high=1500.0, critical_high=3000.0,
        source="Project assumption, consistent with TDS limits via "
        "TDS = 0.64 x conductivity (1000 mg/L ~= 1560 uS/cm).",
    ),
    "temperature_c": AlertThreshold(
        "temperature_c", warning_high=3.0, critical_high=5.0,
        source="Deviation from seasonal baseline; warning = PP 22/2021 "
        "deviation limit 3 degC; critical = project assumption.",
    ),
    "orp_mv": AlertThreshold(
        "orp_mv", warning_low=150.0, warning_high=600.0,
        critical_low=100.0, critical_high=700.0,
        source="Project assumption (operational ORP band); "
        "ORP has no PP 22/2021 or WHO limit.",
    ),
}


def limit_for(parameter: str, water_class: str) -> float | tuple[float, float] | None:
    """Return the PP 22/2021 limit for ``parameter`` in ``water_class``."""
    limit = PP22_RIVER.get(parameter)
    if limit is None:
        return None
    return limit.values.get(water_class)


def check_value(parameter: str, value: float, water_class: str = "II") -> bool:
    """True when ``value`` meets the PP 22/2021 limit for its class.

    Temperature is handled as a deviation: pass the deviation from the
    seasonal baseline, not the absolute temperature.
    """
    limit = PP22_RIVER.get(parameter)
    if limit is None:
        raise KeyError(f"no PP 22/2021 limit for parameter {parameter!r}")
    bound = limit.values.get(water_class)
    if bound is None:
        raise ValueError(f"no PP 22/2021 limit for {parameter} class {water_class}")
    if limit.kind == "max":
        return value <= float(bound)
    if limit.kind == "min":
        return value >= float(bound)
    if limit.kind == "range":
        lo, hi = bound  # type: ignore[misc]
        return lo <= value <= hi
    # deviation: value is the absolute deviation from baseline
    return abs(value) <= float(bound)


def classify_water_class(
    values: dict[str, float],
    temperature_deviation: float | None = None,
) -> str:
    """Return the strictest PP 22/2021 class all given values meet.

    Only parameters present in ``values`` (and in PP22_RIVER) are
    checked. Returns "V" when no class I-IV is met by every value.
    """
    checked: dict[str, float] = dict(values)
    if temperature_deviation is not None:
        checked["temperature_c"] = temperature_deviation
    for water_class in CLASSES:
        ok = True
        for param, value in checked.items():
            limit = PP22_RIVER.get(param)
            if limit is None:
                continue
            bound = limit.values.get(water_class)
            if bound is None:
                continue
            if limit.kind == "max" and value > float(bound):
                ok = False
                break
            if limit.kind == "min" and value < float(bound):
                ok = False
                break
            if limit.kind == "range":
                lo, hi = bound  # type: ignore[misc]
                if not (lo <= value <= hi):
                    ok = False
                    break
            if limit.kind == "deviation" and abs(value) > float(bound):
                ok = False
                break
        if ok:
            return water_class
    return "V"
