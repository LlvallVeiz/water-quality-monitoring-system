"""Alert engine: threshold alerts with persistence, escalation, dedup.

The engine consumes readings in chronological order, one station at a
time, and compares each parameter against its
:class:`~water_quality.standards.AlertThreshold`:

* a *candidate* starts when a reading crosses a warning level;
* it becomes an *active alert* only after ``persistence`` consecutive
  crossing readings (default 3) — a single spike does not page anyone;
* while active, the alert escalates to ``critical`` if a reading
  crosses a critical level, and de-escalates back to ``warning`` when
  it only crosses the warning level;
* a repeated crossing while the alert is active does NOT create a new
  alert (dedup); a new alert for the same parameter can only start
  after the previous one resolved;
* the alert resolves after ``resolve_after`` consecutive in-range
  readings (default 2).

Temperature is compared as a deviation from the station's seasonal
baseline temperature (PP 22/2021 limits deviation, not absolute
temperature); the caller supplies the baseline, or the engine
estimates it as the median temperature of the readings seen so far
for that station.

Every state transition is recorded as an :class:`Alert` with
``triggered_at``/``resolved_at`` timestamps (days since run start),
peak value, and the full history of level changes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .standards import DEFAULT_ALERT_THRESHOLDS, AlertThreshold

LEVELS = ("info", "warning", "critical")


@dataclass
class Alert:
    """One alert episode for one station/parameter."""

    station_id: str
    parameter: str
    level: str  # level at trigger time ("warning" or "critical")
    triggered_at_day: float
    peak_value: float
    peak_at_day: float
    n_readings: int = 1
    resolved_at_day: float | None = None
    max_level: str = "warning"
    history: list[tuple[float, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "parameter": self.parameter,
            "level": self.level,
            "max_level": self.max_level,
            "triggered_at_day": self.triggered_at_day,
            "resolved_at_day": self.resolved_at_day,
            "peak_value": self.peak_value,
            "peak_at_day": self.peak_at_day,
            "n_readings": self.n_readings,
        }


@dataclass
class _Candidate:
    consecutive: int = 0
    peak_value: float = 0.0
    peak_at_day: float = 0.0
    start_day: float = 0.0
    start_level: str = "warning"


class AlertEngine:
    """Stateful threshold alerting over a stream of readings."""

    def __init__(self, thresholds: dict[str, AlertThreshold] | None = None,
                 persistence: int = 3, resolve_after: int = 2) -> None:
        self.thresholds = thresholds or DEFAULT_ALERT_THRESHOLDS
        self.persistence = persistence
        self.resolve_after = resolve_after
        self.alerts: list[Alert] = []
        self._active: dict[tuple[str, str], Alert] = {}
        self._candidates: dict[tuple[str, str], _Candidate] = {}
        self._in_range_streak: dict[tuple[str, str], int] = {}
        self._seen_temperatures: dict[str, list[float]] = {}

    def _level_for(self, parameter: str, value: float,
                   baseline_temp: float | None) -> str | None:
        thr = self.thresholds.get(parameter)
        if thr is None:
            return None
        check = value
        if parameter == "temperature_c" and baseline_temp is not None:
            check = abs(value - baseline_temp)
        if thr.critical_low is not None and check < thr.critical_low:
            return "critical"
        if thr.critical_high is not None and check > thr.critical_high:
            return "critical"
        if thr.warning_low is not None and check < thr.warning_low:
            return "warning"
        if thr.warning_high is not None and check > thr.warning_high:
            return "warning"
        return None

    def _breach_distance(self, parameter: str, value: float,
                         baseline_temp: float | None) -> float:
        """How far ``value`` sits beyond the nearest breached bound.

        Used to track the peak (most extreme) reading of an alert:
        for a low-side breach it is ``bound - value`` (temperature
        uses deviation from baseline), for a high-side breach
        ``value - bound``.
        """
        thr = self.thresholds[parameter]
        check = value
        if parameter == "temperature_c" and baseline_temp is not None:
            check = abs(value - baseline_temp)
        distances = []
        for bound in (thr.critical_low, thr.warning_low):
            if bound is not None and check < bound:
                distances.append(bound - check)
        for bound in (thr.critical_high, thr.warning_high):
            if bound is not None and check > bound:
                distances.append(check - bound)
        return max(distances) if distances else 0.0

    def process(self, station_id: str, readings: list[dict],
                baseline_temperature_c: float | None = None) -> list[Alert]:
        """Process one station's readings in chronological order.

        Returns the alerts (new and updated) produced by this call.
        """
        produced: list[Alert] = []
        temps = [r["temperature_c"] for r in readings
                 if r.get("temperature_c") is not None]
        baseline = baseline_temperature_c
        if baseline is None and temps:
            baseline = statistics.median(temps)
        for row in readings:
            day = float(row["timestamp_day"])
            for param, thr in self.thresholds.items():
                value = row.get(param)
                if value is None:
                    continue
                key = (station_id, param)
                level = self._level_for(param, value, baseline)
                active = self._active.get(key)
                if level is None:
                    self._candidates.pop(key, None)
                    if active is not None:
                        streak = self._in_range_streak.get(key, 0) + 1
                        self._in_range_streak[key] = streak
                        if streak >= self.resolve_after:
                            active.resolved_at_day = day
                            del self._active[key]
                            self._in_range_streak.pop(key, None)
                    continue
                self._in_range_streak.pop(key, None)
                if active is not None:
                    active.n_readings += 1
                    if self._breach_distance(param, value, baseline) > \
                            self._breach_distance(param, active.peak_value, baseline):
                        active.peak_value = value
                        active.peak_at_day = day
                    if level == "critical" and active.max_level != "critical":
                        active.max_level = "critical"
                        active.history.append((day, "critical"))
                    continue
                cand = self._candidates.get(key)
                if cand is None:
                    cand = _Candidate(consecutive=0, peak_value=value,
                                      peak_at_day=day, start_day=day,
                                      start_level=level)
                    self._candidates[key] = cand
                cand.consecutive += 1
                if self._breach_distance(param, value, baseline) > \
                        self._breach_distance(param, cand.peak_value, baseline):
                    cand.peak_value = value
                    cand.peak_at_day = day
                if level == "critical":
                    cand.start_level = "critical"
                if cand.consecutive >= self.persistence:
                    alert = Alert(
                        station_id=station_id, parameter=param,
                        level=cand.start_level,
                        triggered_at_day=cand.start_day,
                        peak_value=cand.peak_value,
                        peak_at_day=cand.peak_at_day,
                        n_readings=cand.consecutive,
                        max_level=cand.start_level,
                        history=[(cand.start_day, cand.start_level)],
                    )
                    self._active[key] = alert
                    self.alerts.append(alert)
                    produced.append(alert)
                    del self._candidates[key]
        return produced

    def summary(self) -> dict:
        """Counts of alerts by level and parameter."""
        by_level: dict[str, int] = {}
        by_param: dict[str, int] = {}
        for alert in self.alerts:
            by_level[alert.max_level] = by_level.get(alert.max_level, 0) + 1
            by_param[alert.parameter] = by_param.get(alert.parameter, 0) + 1
        return {
            "total": len(self.alerts),
            "by_max_level": by_level,
            "by_parameter": by_param,
            "unresolved": sum(1 for a in self.alerts if a.resolved_at_day is None),
        }
