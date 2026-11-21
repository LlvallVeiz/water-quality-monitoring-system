"""Realistic river water-quality sensor simulator.

Each station produces an hourly time series for eight parameters
(pH, temperature, DO, turbidity, conductivity, TDS, nitrate as N,
ORP). The signal is built from interpretable components:

* baseline — station-specific mean per parameter;
* seasonal cycle — annual sine on temperature (and, through DO
  solubility, on DO);
* diurnal cycle — temperature peaks mid-afternoon; DO and pH follow
  photosynthesis (peak late afternoon); turbidity dips slightly at
  night;
* Gaussian measurement noise (seeded);
* slow sensor drift — a linear bias that grows over the run;
* events — rain/runoff, algal bloom and industrial spill, each with
  a start day, duration and magnitude, applied as a smooth
  rise-and-fall pulse;
* data gaps — seeded random dropouts plus explicit gap windows.

TDS is not simulated independently: it is derived from conductivity
as ``TDS = 0.64 * conductivity`` (see ``parameters.py``), which is
how many field probes report it. DO is simulated in mg/L around a
baseline that respects the saturation concentration at the simulated
temperature (values are clipped to 0-120 % of saturation).

All randomness comes from one ``numpy.random.Generator`` seeded by
the caller, so a (seed, config) pair reproduces its output exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .parameters import TDS_PER_CONDUCTIVITY

#: Default baseline (mean) value per parameter for a clean lowland river.
DEFAULT_BASELINE: dict[str, float] = {
    "ph": 7.2,
    "temperature_c": 27.0,
    "do_mg_l": 7.5,
    "turbidity_ntu": 8.0,
    "conductivity_us_cm": 250.0,
    "nitrate_mg_l_n": 1.5,
    "orp_mv": 280.0,
}

#: Default Gaussian noise sigma per parameter.
DEFAULT_NOISE: dict[str, float] = {
    "ph": 0.05,
    "temperature_c": 0.3,
    "do_mg_l": 0.25,
    "turbidity_ntu": 1.5,
    "conductivity_us_cm": 8.0,
    "nitrate_mg_l_n": 0.15,
    "orp_mv": 8.0,
}

#: Default diurnal amplitude per parameter (peak hour given below).
DEFAULT_DIURNAL_AMP: dict[str, float] = {
    "temperature_c": 1.5,
    "do_mg_l": 0.8,
    "ph": 0.15,
    "turbidity_ntu": -1.0,
    "orp_mv": 5.0,
}

#: Hour of day at which each diurnal cycle peaks.
DIURNAL_PEAK_HOUR: dict[str, float] = {
    "temperature_c": 14.0,
    "do_mg_l": 15.0,
    "ph": 15.0,
    "turbidity_ntu": 14.0,
    "orp_mv": 15.0,
}

#: Default linear sensor drift per day (added bias at end of run).
DEFAULT_DRIFT_PER_DAY: dict[str, float] = {
    "ph": 0.0,
    "temperature_c": 0.0,
    "do_mg_l": 0.0,
    "turbidity_ntu": 0.02,
    "conductivity_us_cm": 0.0,
    "nitrate_mg_l_n": 0.0,
    "orp_mv": 0.0,
}


@dataclass
class Event:
    """A water-quality event applied to a station's time series.

    ``kind`` is one of ``"rain"``, ``"bloom"`` or ``"spill"``.
    ``start_day``/``duration_days`` locate the pulse; ``magnitude``
    scales its strength (1.0 = nominal). The pulse shape is a raised
    cosine: it rises smoothly, peaks mid-event and falls back to zero.
    """

    kind: str
    start_day: float
    duration_days: float
    magnitude: float = 1.0

    def shape(self, day: float) -> float:
        """Pulse height in [0, 1] at fractional ``day``."""
        if day < self.start_day or day > self.start_day + self.duration_days:
            return 0.0
        phase = (day - self.start_day) / self.duration_days
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)

    def effects(self) -> dict[str, float]:
        """Additive effect per parameter at pulse height 1.0."""
        if self.kind == "rain":
            # Runoff: sediment + fertiliser wash-in, oxygen dip.
            return {
                "turbidity_ntu": 120.0,
                "nitrate_mg_l_n": 4.0,
                "conductivity_us_cm": 80.0,
                "do_mg_l": -1.2,
                "ph": -0.3,
                "orp_mv": -40.0,
            }
        if self.kind == "bloom":
            # Algal bloom: photosynthesis raises pH by day, respiration
            # consumes oxygen; biomass raises turbidity. A strong bloom
            # can push DO below the PP 22/2021 class II minimum (4 mg/L).
            return {
                "do_mg_l": -4.0,
                "ph": 0.6,
                "turbidity_ntu": 25.0,
                "orp_mv": -60.0,
                "nitrate_mg_l_n": -0.5,
            }
        if self.kind == "spill":
            # Industrial discharge: ionic load + oxidants. A strong
            # spill pushes conductivity past the 1500 uS/cm warning
            # level and ORP past the 600 mV warning level.
            return {
                "conductivity_us_cm": 1800.0,
                "orp_mv": 350.0,
                "turbidity_ntu": 30.0,
                "do_mg_l": -1.5,
                "ph": -0.8,
            }
        raise ValueError(f"unknown event kind: {self.kind!r}")


@dataclass
class StationConfig:
    """Configuration of one monitoring station."""

    station_id: str
    name: str
    river_km: float = 0.0
    baseline: dict[str, float] = field(default_factory=dict)
    noise: dict[str, float] = field(default_factory=dict)
    drift_per_day: dict[str, float] = field(default_factory=dict)
    gap_probability: float = 0.01
    gap_windows: list[tuple[float, float]] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def merged_baseline(self) -> dict[str, float]:
        out = dict(DEFAULT_BASELINE)
        out.update(self.baseline)
        return out

    def merged_noise(self) -> dict[str, float]:
        out = dict(DEFAULT_NOISE)
        out.update(self.noise)
        return out

    def merged_drift(self) -> dict[str, float]:
        out = dict(DEFAULT_DRIFT_PER_DAY)
        out.update(self.drift_per_day)
        return out


def _seasonal_temperature(day_of_year: int, mean: float, amplitude: float = 2.0) -> float:
    """Annual temperature cycle; warmest near day 100 (April, tropics)."""
    return mean + amplitude * math.sin(2.0 * math.pi * (day_of_year - 100) / 365.0)


class Simulator:
    """Hourly sensor simulator for one station."""

    def __init__(self, config: StationConfig, seed: int = 42,
                 start_day_of_year: int = 1) -> None:
        self.config = config
        self.seed = seed
        self.start_day_of_year = start_day_of_year
        self.rng = np.random.default_rng(seed)

    def simulate(self, n_days: int) -> list[dict]:
        """Simulate ``n_days`` of hourly readings.

        Returns a list of dicts with ``timestamp_day`` (float days
        since start), ``hour`` and one key per parameter; missing
        readings are ``None``.
        """
        baseline = self.config.merged_baseline()
        noise = self.config.merged_noise()
        drift = self.config.merged_drift()
        n_hours = n_days * 24
        rows: list[dict] = []
        for h in range(n_hours):
            day = h / 24.0
            doy = (self.start_day_of_year + int(day) - 1) % 365 + 1
            hour = h % 24
            row: dict = {"timestamp_day": round(day, 6), "hour": hour}
            temp = _seasonal_temperature(doy, baseline["temperature_c"])
            temp += DEFAULT_DIURNAL_AMP["temperature_c"] * math.sin(
                2.0 * math.pi * (hour - DIURNAL_PEAK_HOUR["temperature_c"] + 6) / 24.0)
            values: dict[str, float] = {"temperature_c": temp}
            for param, base in baseline.items():
                if param == "temperature_c":
                    continue
                value = base
                if param in DEFAULT_DIURNAL_AMP:
                    peak = DIURNAL_PEAK_HOUR[param]
                    value += DEFAULT_DIURNAL_AMP[param] * math.sin(
                        2.0 * math.pi * (hour - peak + 6) / 24.0)
                if param == "do_mg_l":
                    # DO follows temperature through solubility: warmer
                    # water holds less oxygen; scale baseline by the
                    # saturation ratio relative to the annual mean.
                    from .do_saturation import do_saturation_mg_l
                    sat_now = do_saturation_mg_l(temp)
                    sat_ref = do_saturation_mg_l(baseline["temperature_c"])
                    value = base * sat_now / sat_ref
                value += drift.get(param, 0.0) * day
                value += float(self.rng.normal(0.0, noise.get(param, 0.0)))
                values[param] = value
            values["temperature_c"] = temp + float(
                self.rng.normal(0.0, noise["temperature_c"]))
            for event in self.config.events:
                height = event.shape(day) * event.magnitude
                if height == 0.0:
                    continue
                for param, effect in event.effects().items():
                    if param in values:
                        values[param] += effect * height
            # Physical clipping, then TDS from conductivity.
            values["ph"] = min(14.0, max(0.0, values["ph"]))
            values["do_mg_l"] = max(0.0, values["do_mg_l"])
            values["turbidity_ntu"] = max(0.0, values["turbidity_ntu"])
            values["conductivity_us_cm"] = max(0.0, values["conductivity_us_cm"])
            values["nitrate_mg_l_n"] = max(0.0, values["nitrate_mg_l_n"])
            values["tds_mg_l"] = values["conductivity_us_cm"] * TDS_PER_CONDUCTIVITY
            is_gap = self.rng.random() < self.config.gap_probability
            if not is_gap:
                for start, end in self.config.gap_windows:
                    if start <= day < end:
                        is_gap = True
                        break
            for param in ("ph", "temperature_c", "do_mg_l", "turbidity_ntu",
                          "conductivity_us_cm", "tds_mg_l", "nitrate_mg_l_n",
                          "orp_mv"):
                row[param] = None if is_gap else round(values[param], 4)
            rows.append(row)
        return rows
