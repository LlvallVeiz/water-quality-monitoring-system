"""End-to-end pipeline tests on a small network."""

import json
import os

import pytest

from water_quality.pipeline import compute_daily_wqi, run_pipeline


def test_compute_daily_wqi_flat_water(flat_rows):
    readings = {"S1": flat_rows}
    daily = compute_daily_wqi(readings, ["S1"])
    assert len(daily["S1"]) == 10
    first = daily["S1"][0]
    # Flat clean water: DO 8 mg/L at 25 C -> ~97 % sat, pH 7, nitrate 2
    # mg/L as N, turbidity 10 NTU, TDS 160 -> high NSF score.
    assert first["nsf_wqi"] > 80
    assert first["nsf_class"] in ("Good", "Excellent")
    assert first["ccme_wqi"] == 100.0
    assert first["water_class"] == "I"


def test_compute_daily_wqi_bad_day_detected(flat_rows):
    bad = []
    for r in flat_rows:
        row = dict(r)
        if int(row["timestamp_day"]) == 3:
            row["do_mg_l"] = 1.0
            row["ph"] = 5.0
            row["nitrate_mg_l_n"] = 25.0
        bad.append(row)
    daily = compute_daily_wqi({"S1": bad}, ["S1"])
    assert daily["S1"][3]["nsf_wqi"] < daily["S1"][0]["nsf_wqi"]
    assert daily["S1"][3]["water_class"] in ("IV", "V")
    assert daily["S1"][3]["ccme_wqi"] < daily["S1"][0]["ccme_wqi"]


def test_run_pipeline_writes_all_artefacts(tmp_path, small_network):
    import json as _json
    from water_quality.network import network_to_dict
    net_path = tmp_path / "net.json"
    net_path.write_text(_json.dumps(network_to_dict(small_network)), encoding="utf-8")
    out_dir = tmp_path / "out"
    summary = run_pipeline(str(net_path), n_days=5, seed=5, out_dir=str(out_dir))
    assert summary["river"] == "Test River"
    assert summary["n_days"] == 5
    assert set(summary["stations"]) == {"T-01", "T-02"}
    for name in ("readings.db", "report.md", "dashboard.html",
                 "readings.csv", "summary.json"):
        assert os.path.exists(out_dir / name), name
    assert os.path.getsize(out_dir / "dashboard.html") > 10000
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "Test River" in report
    assert "Water Quality Index" in report
    with open(out_dir / "summary.json", encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved["stations"]["T-01"]["n_readings"] == 120


def test_run_pipeline_event_scenario_more_alerts(tmp_path):
    from water_quality.network import Network
    from water_quality.simulator import Event, StationConfig
    from water_quality.network import network_to_dict
    clean = Network(river="R", stations=[StationConfig(station_id="A", name="A")])
    dirty = Network(river="R", stations=[StationConfig(
        station_id="A", name="A",
        events=[Event("spill", 1.0, 2.0), Event("bloom", 3.0, 2.0)])])
    results = {}
    for label, net in (("clean", clean), ("dirty", dirty)):
        path = tmp_path / f"{label}.json"
        path.write_text(json.dumps(network_to_dict(net)), encoding="utf-8")
        out = tmp_path / label
        results[label] = run_pipeline(str(path), n_days=6, seed=5, out_dir=str(out))
    assert results["dirty"]["alerts"]["total"] > results["clean"]["alerts"]["total"]
    assert results["dirty"]["stations"]["A"]["mean_nsf_wqi"] < \
        results["clean"]["stations"]["A"]["mean_nsf_wqi"]
