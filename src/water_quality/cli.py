"""Command-line interface.

Subcommands (all read/write plain files, no server needed)::

    wqm simulate --network configs/network_river.json --days 30 --seed 42 --out readings.csv
    wqm ingest   --db out/readings.db --csv readings.csv --station KB-01
    wqm wqi      --db out/readings.db --class II
    wqm alerts   --db out/readings.db
    wqm analyze  --db out/readings.db --class II
    wqm report   --db out/readings.db --out out/report.md
    wqm dashboard --db out/readings.db --out out/dashboard.html
    wqm run      --network configs/network_river.json --days 30 --seed 42 --out out

``wqm run`` executes the whole pipeline in one step; the other
commands expose each stage separately for scripting and debugging.
"""

from __future__ import annotations

import argparse
import json
import sys

from .alerts import AlertEngine
from .analysis import correlation_matrix, station_summary
from .dashboard import build_dashboard
from .network import load_network
from .pipeline import CCME_OBJECTIVES_CLASS_II, compute_daily_wqi, run_pipeline
from .report import build_report
from .storage import Store, export_readings_csv, ingest_csv
from .wqi import ccme_wqi


def _station_meta(network) -> list[dict]:
    return [{"station_id": s.station_id, "name": s.name,
             "river_km": s.river_km} for s in network.stations]


def _load_station_data(store: Store, network_path: str | None) -> tuple[dict, list[dict], str]:
    if network_path:
        network = load_network(network_path)
        meta = _station_meta(network)
        river = network.river
    else:
        meta = [{"station_id": sid, "name": sid, "river_km": 0.0}
                for sid in store.station_ids()]
        river = "river"
    readings = {m["station_id"]: store.query_readings(m["station_id"]) for m in meta}
    return readings, meta, river


def cmd_simulate(args) -> int:
    network = load_network(args.network)
    network.propagate_events()
    readings = network.simulate_all(args.days, seed=args.seed,
                                    start_day_of_year=args.start_day_of_year)
    import csv
    from .parameters import PARAMETERS
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["station_id", "timestamp_day", "hour"] + list(PARAMETERS))
        writer.writeheader()
        for sid, rows in readings.items():
            for row in rows:
                writer.writerow({"station_id": sid, **row})
    total = sum(len(r) for r in readings.values())
    print(f"simulated {total} hourly readings for {len(readings)} station(s) -> {args.out}")
    return 0


def cmd_ingest(args) -> int:
    with Store(args.db) as store:
        n = ingest_csv(store, args.csv, args.station)
    print(f"ingested {n} readings for station {args.station} into {args.db}")
    return 0


def cmd_wqi(args) -> int:
    with Store(args.db) as store:
        readings, meta, _river = _load_station_data(store, args.network)
        order = [m["station_id"] for m in meta]
        daily = compute_daily_wqi(readings, order, args.water_class)
        for sid in order:
            for row in daily[sid]:
                store.insert_wqi_daily(sid, row["day"], row)
        for sid in order:
            vals = [d["nsf_wqi"] for d in daily[sid] if d.get("nsf_wqi") is not None]
            cvals = [d["ccme_wqi"] for d in daily[sid] if d.get("ccme_wqi") is not None]
            print(f"{sid}: mean NSF {sum(vals)/len(vals):.2f} "
                  f"(min {min(vals):.2f}), mean CCME {sum(cvals)/len(cvals):.2f} "
                  f"(min {min(cvals):.2f}), {len(vals)} days")
    return 0


def cmd_alerts(args) -> int:
    with Store(args.db) as store:
        readings, meta, _river = _load_station_data(store, args.network)
        engine = AlertEngine(persistence=args.persistence)
        for m in meta:
            sid = m["station_id"]
            engine.process(sid, readings[sid])
        store.insert_alerts([a.to_dict() for a in engine.alerts])
        summary = engine.summary()
        print(f"alerts: total {summary['total']}, "
              f"by level {summary['by_max_level']}, "
              f"by parameter {summary['by_parameter']}")
        for alert in engine.alerts:
            print(f"  {alert.station_id} {alert.parameter} {alert.max_level} "
                  f"day {alert.triggered_at_day:.2f} peak {alert.peak_value:.2f}")
    return 0


def cmd_analyze(args) -> int:
    with Store(args.db) as store:
        readings, meta, _river = _load_station_data(store, args.network)
        for m in meta:
            sid = m["station_id"]
            summary = station_summary(readings[sid], args.water_class)
            print(f"== {sid} ==")
            for param, entry in summary.items():
                s = entry["stats"]
                exc = entry.get("exceedance")
                tr = entry["trend"]
                line = (f"  {param}: mean {s['mean']}, range "
                        f"[{s['min']}, {s['max']}], completeness {s['completeness']:.0%}")
                if exc:
                    line += f", exceedance {exc['pct_exceed']:.1f}%"
                line += f", slope {tr['slope_per_day']}/day, MK {tr['mann_kendall']['trend']}"
                print(line)
    return 0


def _build_outputs(store: Store, meta, readings, river, args, out_path: str,
                   make_dashboard: bool) -> int:
    order = [m["station_id"] for m in meta]
    daily = compute_daily_wqi(readings, order, args.water_class)
    alerts = store.query_alerts()
    summaries = {sid: station_summary(readings[sid], args.water_class) for sid in order}
    correlations = {sid: correlation_matrix(readings[sid]) for sid in order}
    n_days = 0
    for rows in readings.values():
        if rows:
            n_days = max(n_days, int(max(r["timestamp_day"] for r in rows)) + 1)
    if make_dashboard:
        html = build_dashboard(river, n_days, meta, readings, daily, alerts, summaries)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html)
    else:
        engine = AlertEngine()
        report_md = build_report(river, n_days, meta, daily, engine.summary(),
                                 alerts, summaries, correlations)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report_md)
    print(f"wrote {out_path}")
    return 0


def cmd_report(args) -> int:
    with Store(args.db) as store:
        readings, meta, river = _load_station_data(store, args.network)
        return _build_outputs(store, meta, readings, river, args, args.out, False)


def cmd_dashboard(args) -> int:
    with Store(args.db) as store:
        readings, meta, river = _load_station_data(store, args.network)
        return _build_outputs(store, meta, readings, river, args, args.out, True)


def cmd_run(args) -> int:
    summary = run_pipeline(args.network, n_days=args.days, seed=args.seed,
                           out_dir=args.out, water_class=args.water_class,
                           start_day_of_year=args.start_day_of_year)
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wqm", description="Water quality monitoring system")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("simulate", help="simulate sensor readings to CSV")
    p.add_argument("--network", required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--start-day-of-year", type=int, default=1)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("ingest", help="load a readings CSV into SQLite")
    p.add_argument("--db", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--station", required=True)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("wqi", help="compute daily WQI into the database")
    p.add_argument("--db", required=True)
    p.add_argument("--network", default=None)
    p.add_argument("--class", dest="water_class", default="II")
    p.set_defaults(func=cmd_wqi)

    p = sub.add_parser("alerts", help="run the alert engine on stored readings")
    p.add_argument("--db", required=True)
    p.add_argument("--network", default=None)
    p.add_argument("--persistence", type=int, default=3)
    p.set_defaults(func=cmd_alerts)

    p = sub.add_parser("analyze", help="print per-station statistics")
    p.add_argument("--db", required=True)
    p.add_argument("--network", default=None)
    p.add_argument("--class", dest="water_class", default="II")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("report", help="write a Markdown report")
    p.add_argument("--db", required=True)
    p.add_argument("--network", default=None)
    p.add_argument("--class", dest="water_class", default="II")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("dashboard", help="write a static HTML dashboard")
    p.add_argument("--db", required=True)
    p.add_argument("--network", default=None)
    p.add_argument("--class", dest="water_class", default="II")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("run", help="run the full pipeline end to end")
    p.add_argument("--network", required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--start-day-of-year", type=int, default=1)
    p.add_argument("--class", dest="water_class", default="II")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
