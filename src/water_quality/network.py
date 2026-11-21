"""River station network: configuration, downstream propagation, gaps.

A network is an ordered list of stations along one river, from
upstream (``river_km`` = 0) to downstream. Events that occur at an
upstream station propagate downstream: the same pulse arrives later
(lag, from the distance divided by a mean flow velocity) and weaker
(attenuation from dilution and decay). Propagation is applied by
copying each upstream event to every downstream station with a
shifted start day and a scaled magnitude.

Configuration is plain JSON, e.g.::

    {
      "river": "Kali Biru",
      "flow_velocity_km_per_day": 24.0,
      "attenuation_per_km": 0.01,
      "stations": [
        {"station_id": "KB-01", "name": "Hulu", "river_km": 0.0,
         "baseline": {"turbidity_ntu": 5.0},
         "events": [{"kind": "rain", "start_day": 10.0,
                     "duration_days": 2.0, "magnitude": 1.0}]}
      ]
    }

``flow_velocity_km_per_day`` default 24 km/day (~1 km/h, a slow
lowland river) and ``attenuation_per_km`` default 0.01 (1 % loss per
km) are project assumptions, documented here and in RESEARCH.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .simulator import Event, Simulator, StationConfig

#: Default mean flow velocity (km/day) for downstream lag.
DEFAULT_FLOW_VELOCITY_KM_PER_DAY = 24.0
#: Default fractional attenuation of an event pulse per river km.
DEFAULT_ATTENUATION_PER_KM = 0.01


@dataclass
class Network:
    """An ordered set of stations along one river."""

    river: str
    stations: list[StationConfig]
    flow_velocity_km_per_day: float = DEFAULT_FLOW_VELOCITY_KM_PER_DAY
    attenuation_per_km: float = DEFAULT_ATTENUATION_PER_KM

    def propagate_events(self) -> None:
        """Copy upstream events downstream with lag + attenuation.

        Each station's own events are kept; for every pair (upstream,
        downstream) a propagated copy is appended to the downstream
        station with ``start_day`` shifted by the travel time and
        ``magnitude`` scaled by ``(1 - attenuation) ** distance``.
        Idempotent for a single call on a fresh network; calling it
        twice would duplicate propagated events, so callers run it
        once per network build.
        """
        originals = {s.station_id: list(s.events) for s in self.stations}
        for i, downstream in enumerate(self.stations):
            for upstream in self.stations[:i]:
                distance = downstream.river_km - upstream.river_km
                if distance <= 0:
                    continue
                lag_days = distance / self.flow_velocity_km_per_day
                attenuation = (1.0 - self.attenuation_per_km) ** distance
                for event in originals[upstream.station_id]:
                    downstream.events.append(Event(
                        kind=event.kind,
                        start_day=event.start_day + lag_days,
                        duration_days=event.duration_days,
                        magnitude=event.magnitude * attenuation,
                    ))

    def simulate_all(self, n_days: int, seed: int = 42,
                     start_day_of_year: int = 1) -> dict[str, list[dict]]:
        """Simulate every station; returns ``{station_id: rows}``.

        Each station gets a deterministic sub-seed derived from the
        base seed and its index, so the whole network is reproducible
        from one seed.
        """
        out: dict[str, list[dict]] = {}
        for idx, station in enumerate(self.stations):
            sim = Simulator(station, seed=seed + 1000 * idx,
                            start_day_of_year=start_day_of_year)
            out[station.station_id] = sim.simulate(n_days)
        return out


def load_network(path: str) -> Network:
    """Load a network definition from a JSON file."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    stations = []
    for item in raw.get("stations", []):
        events = [Event(kind=e["kind"], start_day=float(e["start_day"]),
                        duration_days=float(e["duration_days"]),
                        magnitude=float(e.get("magnitude", 1.0)))
                  for e in item.get("events", [])]
        stations.append(StationConfig(
            station_id=item["station_id"],
            name=item.get("name", item["station_id"]),
            river_km=float(item.get("river_km", 0.0)),
            baseline={k: float(v) for k, v in item.get("baseline", {}).items()},
            noise={k: float(v) for k, v in item.get("noise", {}).items()},
            drift_per_day={k: float(v) for k, v in item.get("drift_per_day", {}).items()},
            gap_probability=float(item.get("gap_probability", 0.01)),
            gap_windows=[(float(a), float(b)) for a, b in item.get("gap_windows", [])],
            events=events,
        ))
    return Network(
        river=raw.get("river", "Unnamed river"),
        stations=stations,
        flow_velocity_km_per_day=float(
            raw.get("flow_velocity_km_per_day", DEFAULT_FLOW_VELOCITY_KM_PER_DAY)),
        attenuation_per_km=float(
            raw.get("attenuation_per_km", DEFAULT_ATTENUATION_PER_KM)),
    )


def network_to_dict(network: Network) -> dict:
    """Serialise a network back to a JSON-compatible dict."""
    return {
        "river": network.river,
        "flow_velocity_km_per_day": network.flow_velocity_km_per_day,
        "attenuation_per_km": network.attenuation_per_km,
        "stations": [
            {
                "station_id": s.station_id,
                "name": s.name,
                "river_km": s.river_km,
                "baseline": s.merged_baseline(),
                "gap_probability": s.gap_probability,
                "events": [
                    {"kind": e.kind, "start_day": e.start_day,
                     "duration_days": e.duration_days, "magnitude": e.magnitude}
                    for e in s.events
                ],
            }
            for s in network.stations
        ],
    }
