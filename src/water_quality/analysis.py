"""Statistical analysis of stored water-quality series.

Implemented from first principles (stdlib + numpy) so every number
is auditable:

* descriptive statistics per station/parameter (mean, min, max,
  standard deviation, completeness);
* exceedance: fraction of readings breaching a PP 22/2021 class
  limit (or a WHO objective);
* linear trend: ordinary least-squares slope per day, with R²;
* Mann-Kendall trend test (implemented here, with tie correction
  and the normal approximation; two-sided p-value from the normal
  CDF via ``math.erf``);
* Pearson correlation between parameters;
* anomaly detection: rolling-window z-score (default window 24 h,
  threshold |z| > 3).
"""

from __future__ import annotations

import math

import numpy as np

from .parameters import PARAMETERS
from .standards import PP22_RIVER


def _values(rows: list[dict], parameter: str) -> list[float]:
    return [float(r[parameter]) for r in rows if r.get(parameter) is not None]


def describe(rows: list[dict], parameter: str) -> dict:
    """Descriptive statistics for one parameter over ``rows``."""
    values = _values(rows, parameter)
    n_total = len(rows)
    if not values:
        return {"n": 0, "n_total": n_total, "completeness": 0.0,
                "mean": None, "min": None, "max": None, "std": None}
    arr = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "n_total": n_total,
        "completeness": round(len(values) / n_total, 4) if n_total else 0.0,
        "mean": round(float(np.mean(arr)), 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "std": round(float(np.std(arr, ddof=1)), 4) if len(values) > 1 else 0.0,
    }


def exceedance(rows: list[dict], parameter: str, water_class: str = "II") -> dict:
    """Fraction of readings breaching the PP 22/2021 limit.

    Temperature is compared as deviation from the series median
    (the PP 22/2021 limit is on deviation, not absolute temperature).
    Returns ``{"n", "n_exceed", "pct_exceed", "limit", "kind"}``.
    """
    limit = PP22_RIVER.get(parameter)
    if limit is None:
        raise KeyError(f"no PP 22/2021 limit for {parameter!r}")
    values = _values(rows, parameter)
    bound = limit.values[water_class]
    if bound is None:
        raise ValueError(f"no PP 22/2021 limit for {parameter} class {water_class}")
    if parameter == "temperature_c":
        baseline = float(np.median(values)) if values else 0.0
        n_exceed = sum(1 for v in values if abs(v - baseline) > float(bound))
        limit_text = f"deviation > {bound} degC from median {baseline:.2f} degC"
    elif limit.kind == "max":
        n_exceed = sum(1 for v in values if v > float(bound))
        limit_text = f"<= {bound} {limit.unit}"
    elif limit.kind == "min":
        n_exceed = sum(1 for v in values if v < float(bound))
        limit_text = f">= {bound} {limit.unit}"
    else:
        lo, hi = bound  # type: ignore[misc]
        n_exceed = sum(1 for v in values if v < lo or v > hi)
        limit_text = f"{lo}-{hi} {limit.unit}"
    return {
        "n": len(values),
        "n_exceed": n_exceed,
        "pct_exceed": round(100.0 * n_exceed / len(values), 2) if values else 0.0,
        "limit": limit_text,
        "kind": limit.kind,
    }


def linear_trend(rows: list[dict], parameter: str) -> dict:
    """OLS trend of ``parameter`` against time (per day) with R²."""
    xs = np.array([float(r["timestamp_day"]) for r in rows
                   if r.get(parameter) is not None], dtype=float)
    ys = np.array(_values(rows, parameter), dtype=float)
    if len(xs) < 3 or np.ptp(xs) == 0:
        return {"slope_per_day": None, "intercept": None, "r2": None, "n": len(xs)}
    slope, intercept = np.polyfit(xs, ys, 1)
    y_hat = slope * xs + intercept
    ss_res = float(np.sum((ys - y_hat) ** 2))
    ss_tot = float(np.sum((ys - np.mean(ys)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"slope_per_day": round(float(slope), 4),
            "intercept": round(float(intercept), 4),
            "r2": round(float(r2), 4), "n": len(xs)}


def mann_kendall(values: list[float]) -> dict:
    """Mann-Kendall trend test (two-sided, normal approximation).

    Returns ``{"tau", "S", "p_value", "trend"}`` where ``trend`` is
    "increasing", "decreasing" or "no trend" at alpha = 0.05.
    Tie correction follows the standard variance formula.
    """
    n = len(values)
    if n < 4:
        return {"tau": None, "S": 0, "p_value": None, "trend": "insufficient data"}
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += (values[j] > values[i]) - (values[j] < values[i])
    # Tie correction: count tied groups.
    _, counts = np.unique(values, return_counts=True)
    tie_term = sum(int(t) * (int(t) - 1) * (2 * int(t) + 5) for t in counts if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if var_s == 0:
        return {"tau": 0.0, "S": s, "p_value": 1.0, "trend": "no trend"}
    z = (s - 1) / math.sqrt(var_s) if s > 0 else ((s + 1) / math.sqrt(var_s) if s < 0 else 0.0)
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    tau = s / (0.5 * n * (n - 1))
    trend = "no trend"
    if p_value < 0.05:
        trend = "increasing" if s > 0 else "decreasing"
    return {"tau": round(float(tau), 4), "S": int(s),
            "p_value": round(float(p_value), 4), "trend": trend}


def correlation_matrix(rows: list[dict], parameters: list[str] | None = None) -> dict:
    """Pearson correlation between parameter series (pairwise complete)."""
    params = parameters or list(PARAMETERS)
    out: dict[str, dict[str, float | None]] = {}
    for a in params:
        out[a] = {}
        va = _values(rows, a)
        for b in params:
            vb = _values(rows, b)
            paired = [(r[a], r[b]) for r in rows
                      if r.get(a) is not None and r.get(b) is not None]
            if len(paired) < 3:
                out[a][b] = None
                continue
            x = np.array([p[0] for p in paired], dtype=float)
            y = np.array([p[1] for p in paired], dtype=float)
            if np.std(x) == 0 or np.std(y) == 0:
                out[a][b] = None
                continue
            out[a][b] = round(float(np.corrcoef(x, y)[0, 1]), 3)
    return out


def detect_anomalies(rows: list[dict], parameter: str,
                     window: int = 24, z_threshold: float = 3.0) -> list[dict]:
    """Rolling z-score anomalies: readings far from their 24 h neighbourhood.

    A reading is flagged when ``|x - rolling_mean| > z_threshold *
    rolling_std`` computed over the preceding ``window`` readings.
    Returns a list of ``{"timestamp_day", "value", "z"}`` dicts.
    """
    values = [(float(r["timestamp_day"]), float(r[parameter])) for r in rows
              if r.get(parameter) is not None]
    anomalies: list[dict] = []
    for i in range(window, len(values)):
        window_values = np.array([v for _, v in values[i - window:i]], dtype=float)
        mean = float(np.mean(window_values))
        std = float(np.std(window_values, ddof=1))
        if std == 0:
            continue
        z = (values[i][1] - mean) / std
        if abs(z) > z_threshold:
            anomalies.append({"timestamp_day": values[i][0],
                              "value": round(values[i][1], 4),
                              "z": round(float(z), 2)})
    return anomalies


def station_summary(rows: list[dict], water_class: str = "II") -> dict:
    """Full per-station analysis: stats + exceedance + trend per parameter."""
    out: dict[str, dict] = {}
    for param in PARAMETERS:
        stats = describe(rows, param)
        entry: dict = {"stats": stats}
        if param in PP22_RIVER:
            entry["exceedance"] = exceedance(rows, param, water_class)
        trend = linear_trend(rows, param)
        mk = mann_kendall(_values(rows, param))
        entry["trend"] = {**trend, "mann_kendall": mk}
        out[param] = entry
    return out
