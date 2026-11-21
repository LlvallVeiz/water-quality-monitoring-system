"""SQLite storage for readings, alerts and daily WQI results.

Schema (three tables, created by :func:`init_db`):

* ``readings`` — one row per station-hour, one column per parameter
  (``NULL`` = missing/gap reading);
* ``alerts`` — one row per alert episode, as produced by the alert
  engine;
* ``wqi_daily`` — one row per station-day with the NSF and CCME
  scores and classes.

The store is a thin wrapper: callers pass plain dicts/lists and get
plain dicts/lists back. ``ingest_csv`` loads a CSV file in the same
column layout the simulator/CLI writes, so external probe data can
enter the same pipeline.
"""

from __future__ import annotations

import csv
import sqlite3

from .parameters import PARAMETERS

READING_COLUMNS = list(PARAMETERS)

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    station_id TEXT NOT NULL,
    timestamp_day REAL NOT NULL,
    hour INTEGER NOT NULL,
    ph REAL, temperature_c REAL, do_mg_l REAL, turbidity_ntu REAL,
    conductivity_us_cm REAL, tds_mg_l REAL, nitrate_mg_l_n REAL,
    orp_mv REAL,
    PRIMARY KEY (station_id, timestamp_day)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    parameter TEXT NOT NULL,
    level TEXT NOT NULL,
    max_level TEXT NOT NULL,
    triggered_at_day REAL NOT NULL,
    resolved_at_day REAL,
    peak_value REAL NOT NULL,
    peak_at_day REAL NOT NULL,
    n_readings INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS wqi_daily (
    station_id TEXT NOT NULL,
    day REAL NOT NULL,
    nsf_wqi REAL,
    nsf_class TEXT,
    ccme_wqi REAL,
    ccme_class TEXT,
    water_class TEXT,
    PRIMARY KEY (station_id, day)
);
CREATE INDEX IF NOT EXISTS idx_readings_station_day
    ON readings (station_id, timestamp_day);
"""


class Store:
    """SQLite-backed store for one monitoring run."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- readings -----------------------------------------------------
    def insert_readings(self, station_id: str, rows: list[dict]) -> int:
        cols = ["station_id", "timestamp_day", "hour"] + READING_COLUMNS
        placeholders = ",".join("?" * len(cols))
        sql = f"INSERT OR REPLACE INTO readings ({','.join(cols)}) VALUES ({placeholders})"
        data = [
            tuple([station_id, row["timestamp_day"], row["hour"]]
                  + [row.get(c) for c in READING_COLUMNS])
            for row in rows
        ]
        self.conn.executemany(sql, data)
        self.conn.commit()
        return len(data)

    def query_readings(self, station_id: str | None = None,
                       day_from: float | None = None,
                       day_to: float | None = None) -> list[dict]:
        sql = "SELECT * FROM readings WHERE 1=1"
        params: list = []
        if station_id is not None:
            sql += " AND station_id = ?"
            params.append(station_id)
        if day_from is not None:
            sql += " AND timestamp_day >= ?"
            params.append(day_from)
        if day_to is not None:
            sql += " AND timestamp_day < ?"
            params.append(day_to)
        sql += " ORDER BY station_id, timestamp_day"
        return [dict(r) for r in self.conn.execute(sql, params)]

    def station_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT station_id FROM readings ORDER BY station_id")
        return [r[0] for r in rows]

    def count_readings(self, station_id: str | None = None) -> int:
        if station_id is None:
            return int(self.conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0])
        return int(self.conn.execute(
            "SELECT COUNT(*) FROM readings WHERE station_id = ?",
            (station_id,)).fetchone()[0])

    # -- alerts -------------------------------------------------------
    def insert_alerts(self, alerts: list[dict]) -> int:
        sql = """INSERT INTO alerts
            (station_id, parameter, level, max_level, triggered_at_day,
             resolved_at_day, peak_value, peak_at_day, n_readings)
            VALUES (?,?,?,?,?,?,?,?,?)"""
        data = [(a["station_id"], a["parameter"], a["level"], a["max_level"],
                 a["triggered_at_day"], a["resolved_at_day"], a["peak_value"],
                 a["peak_at_day"], a["n_readings"]) for a in alerts]
        self.conn.executemany(sql, data)
        self.conn.commit()
        return len(data)

    def query_alerts(self, station_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM alerts WHERE 1=1"
        params: list = []
        if station_id is not None:
            sql += " AND station_id = ?"
            params.append(station_id)
        sql += " ORDER BY triggered_at_day"
        return [dict(r) for r in self.conn.execute(sql, params)]

    # -- daily WQI ----------------------------------------------------
    def insert_wqi_daily(self, station_id: str, day: float, row: dict) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO wqi_daily
               (station_id, day, nsf_wqi, nsf_class, ccme_wqi, ccme_class, water_class)
               VALUES (?,?,?,?,?,?,?)""",
            (station_id, day, row.get("nsf_wqi"), row.get("nsf_class"),
             row.get("ccme_wqi"), row.get("ccme_class"), row.get("water_class")))
        self.conn.commit()

    def query_wqi_daily(self, station_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM wqi_daily WHERE 1=1"
        params: list = []
        if station_id is not None:
            sql += " AND station_id = ?"
            params.append(station_id)
        sql += " ORDER BY station_id, day"
        return [dict(r) for r in self.conn.execute(sql, params)]


def ingest_csv(store: Store, path: str, station_id: str) -> int:
    """Load a CSV of readings (simulator column layout) into ``store``."""
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row: dict = {
                "timestamp_day": float(raw["timestamp_day"]),
                "hour": int(raw["hour"]),
            }
            for col in READING_COLUMNS:
                text = (raw.get(col) or "").strip()
                row[col] = float(text) if text else None
            rows.append(row)
    return store.insert_readings(station_id, rows)


def export_readings_csv(store: Store, path: str,
                        station_id: str | None = None) -> int:
    """Write stored readings to CSV; returns rows written."""
    rows = store.query_readings(station_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["station_id", "timestamp_day", "hour"] + READING_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
