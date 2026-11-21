"""Parameter metadata for the water-quality monitoring system.

Every simulated/measured parameter is described once here: its symbol,
unit, plausible physical range and a short description. All other
modules (simulator, standards, storage, analysis, reports) import from
this module so that parameter names and units stay consistent.

Units follow APHA Standard Methods conventions:
pH is dimensionless, temperature in degrees Celsius, dissolved oxygen
(DO) and nitrate in mg/L, turbidity in NTU, conductivity in uS/cm,
total dissolved solids (TDS) in mg/L and ORP in mV.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    """Metadata for one water-quality parameter."""

    key: str
    name: str
    unit: str
    plausible_min: float
    plausible_max: float
    description: str


PARAMETERS: dict[str, Parameter] = {
    "ph": Parameter(
        "ph", "pH", "-", 0.0, 14.0,
        "Degree of acidity/alkalinity; 7 is neutral.",
    ),
    "temperature_c": Parameter(
        "temperature_c", "Temperature", "degC", -5.0, 45.0,
        "Water temperature; controls DO solubility and reaction rates.",
    ),
    "do_mg_l": Parameter(
        "do_mg_l", "Dissolved oxygen (DO)", "mg/L", 0.0, 20.0,
        "Oxygen dissolved in water; low DO stresses aquatic life.",
    ),
    "turbidity_ntu": Parameter(
        "turbidity_ntu", "Turbidity", "NTU", 0.0, 1000.0,
        "Cloudiness from suspended particles; rises after rain/runoff.",
    ),
    "conductivity_us_cm": Parameter(
        "conductivity_us_cm", "Electrical conductivity", "uS/cm", 0.0, 5000.0,
        "Ability to conduct current; proxy for dissolved ions.",
    ),
    "tds_mg_l": Parameter(
        "tds_mg_l", "Total dissolved solids (TDS)", "mg/L", 0.0, 3000.0,
        "Dissolved solids; here derived from conductivity (see simulator).",
    ),
    "nitrate_mg_l_n": Parameter(
        "nitrate_mg_l_n", "Nitrate (as N)", "mg/L as N", 0.0, 100.0,
        "Nitrate-nitrogen; fertiliser/runoff indicator.",
    ),
    "orp_mv": Parameter(
        "orp_mv", "Oxidation-reduction potential (ORP)", "mV", -200.0, 900.0,
        "Redox potential; falls when oxygen is consumed, rises with oxidants.",
    ),
}

#: Parameters produced by the sensor simulator, in canonical order.
SIMULATED_PARAMETERS = list(PARAMETERS)

#: Conversion factor nitrate-as-N -> nitrate-as-NO3 (molar masses 14.01/62.00).
N_TO_NO3 = 62.00 / 14.01

#: TDS/conductivity ratio used when TDS is derived from conductivity.
#: The widely used 0.55-0.70 range is documented in APHA Standard
#: Methods; 0.64 is the conventional mid-range value.
TDS_PER_CONDUCTIVITY = 0.64


def nitrate_as_no3(nitrate_as_n: float) -> float:
    """Convert nitrate expressed as N to nitrate expressed as NO3."""
    return nitrate_as_n * N_TO_NO3


def nitrate_as_n(nitrate_as_no3: float) -> float:
    """Convert nitrate expressed as NO3 to nitrate expressed as N."""
    return nitrate_as_no3 / N_TO_NO3
