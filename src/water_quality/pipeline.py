"""End-to-end pipeline: simulate -> store -> WQI -> alerts -> analysis -> outputs.

One function, :func:`run_pipeline`, drives a whole monitoring run
from a network JSON file and writes every artefact (SQLite database,
CSV exports, Markdown report, HTML dashboard, JSON summary) into an
output directory. The CLI is a thin wrapper around it.
"""

from __future__ import annotations

import csv
import json
import os
import statistics

from .alerts import AlertEngine
from .analysis import correlation_matrix, station_summary
from .dashboard import build_dashboard
from .network import load_network
from .report import build_report
from .standards import classify_water_class
from .storage import Store, export_readings_csv
from .wqi import ccme_wqi, nsf_wqi

#: CCME objectives for river monitoring (PP 22/2021 class II, with
#: the turbidity objective set as a project operational level — see
#: docs/RESEARCH.md; WHO's 5 NTU target applies to treated drinking
#: water, not a raw river).
CCME_OBJECTIVES_CLASS_II: dict[str, object] = {
    "ph": ("range", (6.0, 9.0)),
    "do_mg_l": ("min", 4.0),
    "nitrate_mg_l_n": 10.0,
    "tds_mg_l": 1000.0,
    "turbidity_ntu": 50.0,
}

PARAMETERS = ("ph", "temperature_c", "do_mg_l", "turbidity_ntu",
              "conductivity_us_cm", "tds_mg_l", "nitrate_mg_l_n", "orp_mv")


def _daily_mean(rows: list[dict], parameter: str) -> float | None:
    values = [r[parameter] for r in rows if r.get(parameter) is not None]
    return sum(values) / len(values) if values else None


def compute_daily_wqi(readings_by_station: dict[str, list[dict]],
                      station_order: list[str],
                      water_class: str = "II") -> dict[str, list[dict]]:
    """Daily NSF + CCME WQI and PP 22/2021 class per station.

    Days are integer days since run start. NSF uses daily means;
    temperature change is the difference to the upstream station's
    same-day mean (first station: deviation from its own median
    temperature). CCME uses that day's hourly observations.
    """
    n_days = 0
    for rows in readings_by_station.values():
        if rows:
            n_days = max(n_days, int(max(r["timestamp_day"] for r in rows)) + 1)
    medians = {}
    for sid, rows in readings_by_station.items():
        temps = [r["temperature_c"] for r in rows if r.get("temperature_c") is not None]
        medians[sid] = statistics.median(temps) if temps else 27.0
    out: dict[str, list[dict]] = {}
    for idx, sid in enumerate(station_order):
        rows = readings_by_station[sid]
        daily: list[dict] = []
        upstream_sid = station_order[idx - 1] if idx > 0 else None
        for day in range(n_days):
            day_rows = [r for r in rows if int(r["timestamp_day"]) == day]
            if not day_rows:
                continue
            means = {p: _daily_mean(day_rows, p) for p in PARAMETERS}
            temp_change = None
            if means["temperature_c"] is not None:
                if upstream_sid is not None:
                    up_rows = [r for r in readings_by_station[upstream_sid]
                               if int(r["timestamp_day"]) == day]
                    up_mean = _daily_mean(up_rows, "temperature_c")
                    temp_change = abs(means["temperature_c"] - up_mean) \
                        if up_mean is not None else None
                else:
                    temp_change = abs(means["temperature_c"] - medians[sid])
            nsf_inputs: dict[str, float] = {}
            if means["do_mg_l"] is not None:
                nsf_inputs["do_mg_l"] = means["do_mg_l"]
            if means["ph"] is not None:
                nsf_inputs["ph"] = means["ph"]
            if means["nitrate_mg_l_n"] is not None:
                nsf_inputs["nitrate_mg_l_n"] = means["nitrate_mg_l_n"]
            if means["turbidity_ntu"] is not None:
                nsf_inputs["turbidity_ntu"] = means["turbidity_ntu"]
            if means["tds_mg_l"] is not None:
                nsf_inputs["tds_mg_l"] = means["tds_mg_l"]
            if temp_change is not None:
                nsf_inputs["temperature_change_c"] = temp_change
            nsf = nsf_wqi(nsf_inputs, temperature_c=means["temperature_c"]) \
                if nsf_inputs else {"wqi": None, "class": None}
            try:
                ccme = ccme_wqi(day_rows, CCME_OBJECTIVES_CLASS_II)
            except ValueError:
                ccme = {"wqi": None, "class": None}
            class_inputs = {k: v for k, v in {
                "ph": means["ph"], "do_mg_l": means["do_mg_l"],
                "nitrate_mg_l_n": means["nitrate_mg_l_n"],
                "tds_mg_l": means["tds_mg_l"]}.items() if v is not None}
            water = classify_water_class(class_inputs, temp_change) \
                if class_inputs else "V"
            daily.append({
                "day": float(day),
                "nsf_wqi": nsf["wqi"], "nsf_class": nsf["class"],
                "ccme_wqi": ccme["wqi"], "ccme_class": ccme["class"],
                "water_class": water,
            })
        out[sid] = daily
    return out


def run_pipeline(network_path: str, n_days: int = 30, seed: int = 42,
                 out_dir: str = "output", water_class: str = "II",
                 start_day_of_year: int = 1) -> dict:
    """Run a full monitoring run and write all artefacts.

    Returns a summary dict with station means, alert counts and the
    paths of the artefacts written.
    """
    os.makedirs(out_dir, exist_ok=True)
    network = load_network(network_path)
    network.propagate_events()
    readings = network.simulate_all(n_days, seed=seed,
                                    start_day_of_year=start_day_of_year)
    station_order = [s.station_id for s in network.stations]
    station_meta = [{"station_id": s.station_id, "name": s.name,
                     "river_km": s.river_km} for s in network.stations]

    db_path = os.path.join(out_dir, "readings.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    with Store(db_path) as store:
        for sid in station_order:
            store.insert_readings(sid, readings[sid])
        engine = AlertEngine()
        for sid in station_order:
            # No explicit baseline: the engine measures temperature
            # deviation from each station's own median temperature,
            # so the seasonal cycle itself does not raise alerts.
            engine.process(sid, readings[sid])
        alerts = [a.to_dict() for a in engine.alerts]
        store.insert_alerts(alerts)
        wqi_daily = compute_daily_wqi(readings, station_order, water_class)
        for sid in station_order:
            for row in wqi_daily[sid]:
                store.insert_wqi_daily(sid, row["day"], row)
        summaries = {sid: station_summary(readings[sid], water_class)
                     for sid in station_order}
        correlations = {sid: correlation_matrix(readings[sid])
                        for sid in station_order}
        report_md = build_report(network.river, n_days, station_meta,
                                 wqi_daily, engine.summary(), alerts,
                                 summaries, correlations)
        report_path = os.path.join(out_dir, "report.md")
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(report_md)
        dashboard_html = build_dashboard(network.river, n_days, station_meta,
                                         readings, wqi_daily, alerts, summaries)
        dashboard_path = os.path.join(out_dir, "dashboard.html")
        with open(dashboard_path, "w", encoding="utf-8") as fh:
            fh.write(dashboard_html)
        csv_path = os.path.join(out_dir, "readings.csv")
        export_readings_csv(store, csv_path)
        summary_path = os.path.join(out_dir, "summary.json")
        station_results = {}
        for sid in station_order:
            daily = wqi_daily[sid]
            nsf = [d["nsf_wqi"] for d in daily if d.get("nsf_wqi") is not None]
            ccme = [d["ccme_wqi"] for d in daily if d.get("ccme_wqi") is not None]
            station_results[sid] = {
                "mean_nsf_wqi": round(sum(nsf) / len(nsf), 2) if nsf else None,
                "min_nsf_wqi": round(min(nsf), 2) if nsf else None,
                "mean_ccme_wqi": round(sum(ccme) / len(ccme), 2) if ccme else None,
                "min_ccme_wqi": round(min(ccme), 2) if ccme else None,
                "n_alerts": sum(1 for a in alerts if a["station_id"] == sid),
                "last_water_class": daily[-1]["water_class"] if daily else None,
                "n_readings": len(readings[sid]),
                "n_missing": sum(1 for r in readings[sid]
                                 if r.get("ph") is None),
            }
        summary = {
            "river": network.river,
            "n_days": n_days,
            "seed": seed,
            "water_class": water_class,
            "stations": station_results,
            "alerts": engine.summary(),
            "artefacts": {
                "database": db_path,
                "report": report_path,
                "dashboard": dashboard_path,
                "readings_csv": csv_path,
                "summary": summary_path,
            },
        }
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
    return summary
