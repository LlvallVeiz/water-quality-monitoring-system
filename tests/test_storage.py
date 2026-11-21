"""Tests for SQLite storage and CSV ingest/export."""

import csv

import pytest

from water_quality.storage import (
    Store,
    export_readings_csv,
    ingest_csv,
)


def _sample_rows(n=5):
    return [{
        "timestamp_day": i / 24.0, "hour": i % 24,
        "ph": 7.0 + i * 0.01, "temperature_c": 25.0, "do_mg_l": 8.0,
        "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
        "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0,
    } for i in range(n)]


def test_insert_and_query_round_trip():
    with Store() as store:
        store.insert_readings("S1", _sample_rows())
        rows = store.query_readings("S1")
        assert len(rows) == 5
        assert rows[0]["ph"] == pytest.approx(7.0)
        assert rows[-1]["ph"] == pytest.approx(7.04)
        assert rows[0]["station_id"] == "S1"


def test_missing_values_round_trip_as_none():
    rows = _sample_rows(3)
    rows[1]["ph"] = None
    with Store() as store:
        store.insert_readings("S1", rows)
        got = store.query_readings("S1")
        assert got[1]["ph"] is None
        assert got[0]["ph"] == pytest.approx(7.0)


def test_query_filters_by_station_and_period():
    with Store() as store:
        store.insert_readings("S1", _sample_rows(10))
        store.insert_readings("S2", _sample_rows(10))
        assert len(store.query_readings("S1")) == 10
        assert len(store.query_readings()) == 20
        subset = store.query_readings("S1", day_from=0.1, day_to=0.2)
        assert all(0.1 <= r["timestamp_day"] < 0.2 for r in subset)
        assert store.station_ids() == ["S1", "S2"]
        assert store.count_readings("S1") == 10
        assert store.count_readings() == 20


def test_alerts_round_trip():
    alert = {"station_id": "S1", "parameter": "do_mg_l", "level": "warning",
             "max_level": "critical", "triggered_at_day": 1.5,
             "resolved_at_day": 2.0, "peak_value": 1.2, "peak_at_day": 1.6,
             "n_readings": 12}
    with Store() as store:
        assert store.insert_alerts([alert]) == 1
        got = store.query_alerts("S1")
        assert len(got) == 1
        assert got[0]["max_level"] == "critical"
        assert got[0]["peak_value"] == pytest.approx(1.2)


def test_wqi_daily_round_trip():
    row = {"nsf_wqi": 82.5, "nsf_class": "Good", "ccme_wqi": 91.0,
           "ccme_class": "Good", "water_class": "II"}
    with Store() as store:
        store.insert_wqi_daily("S1", 0.0, row)
        got = store.query_wqi_daily("S1")
        assert len(got) == 1
        assert got[0]["nsf_wqi"] == pytest.approx(82.5)
        assert got[0]["water_class"] == "II"


def test_ingest_csv(tmp_path):
    csv_path = tmp_path / "in.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "timestamp_day", "hour", "ph", "temperature_c", "do_mg_l",
            "turbidity_ntu", "conductivity_us_cm", "tds_mg_l",
            "nitrate_mg_l_n", "orp_mv"])
        writer.writeheader()
        writer.writerow({"timestamp_day": 0.0, "hour": 0, "ph": 7.1,
                         "temperature_c": 25.0, "do_mg_l": 8.0,
                         "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
                         "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0,
                         "orp_mv": 300.0})
        writer.writerow({"timestamp_day": 0.0417, "hour": 1, "ph": "",
                         "temperature_c": 25.0, "do_mg_l": 8.0,
                         "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
                         "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0,
                         "orp_mv": 300.0})
    with Store() as store:
        assert ingest_csv(store, str(csv_path), "S9") == 2
        rows = store.query_readings("S9")
        assert rows[0]["ph"] == pytest.approx(7.1)
        assert rows[1]["ph"] is None


def test_export_readings_csv(tmp_path):
    with Store() as store:
        store.insert_readings("S1", _sample_rows(4))
        out = tmp_path / "out.csv"
        assert export_readings_csv(store, str(out), "S1") == 4
        with open(out, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 4
        assert rows[0]["station_id"] == "S1"
