"""CLI smoke tests (each subcommand, via main())."""

import json
import os

import pytest

from water_quality.cli import main


def test_cli_simulate(tmp_path):
    out = tmp_path / "sim.csv"
    rc = main(["simulate", "--network",
               "configs/network_river.json", "--days", "2", "--seed", "1",
               "--out", str(out)])
    assert rc == 0
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 + 3 * 48  # header + 3 stations x 48 h
    assert lines[0].startswith("station_id,timestamp_day,hour,ph")


def test_cli_run_full_pipeline(tmp_path):
    out = tmp_path / "out"
    rc = main(["run", "--network", "configs/network_river.json",
               "--days", "3", "--seed", "1", "--out", str(out)])
    assert rc == 0
    for name in ("readings.db", "report.md", "dashboard.html",
                 "readings.csv", "summary.json"):
        assert (out / name).exists()
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["stations"]["KB-01"]["mean_nsf_wqi"] > 70


def test_cli_wqi_alerts_analyze_report_dashboard(tmp_path):
    out = tmp_path / "out"
    assert main(["run", "--network", "configs/network_river.json",
                 "--days", "2", "--seed", "1", "--out", str(out)]) == 0
    db = str(out / "readings.db")
    assert main(["wqi", "--db", db, "--network",
                 "configs/network_river.json"]) == 0
    assert main(["alerts", "--db", db, "--network",
                 "configs/network_river.json"]) == 0
    assert main(["analyze", "--db", db, "--network",
                 "configs/network_river.json"]) == 0
    report = tmp_path / "r.md"
    assert main(["report", "--db", db, "--network",
                 "configs/network_river.json", "--out", str(report)]) == 0
    assert report.exists()
    dash = tmp_path / "d.html"
    assert main(["dashboard", "--db", db, "--network",
                 "configs/network_river.json", "--out", str(dash)]) == 0
    assert dash.exists()


def test_cli_ingest_round_trip(tmp_path):
    out = tmp_path / "out"
    assert main(["run", "--network", "configs/network_river.json",
                 "--days", "1", "--seed", "1", "--out", str(out)]) == 0
    db2 = tmp_path / "fresh.db"
    assert main(["ingest", "--db", str(db2), "--csv", str(out / "readings.csv"),
                 "--station", "KB-01"]) == 0
    assert db2.exists()
    assert os.path.getsize(db2) > 0
