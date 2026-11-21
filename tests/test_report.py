"""Tests for the Markdown report generator."""

from water_quality.report import build_report


def _stations():
    return [
        {"station_id": "S1", "name": "Upstream", "river_km": 0.0},
        {"station_id": "S2", "name": "Downstream", "river_km": 10.0},
    ]


def _wqi_daily():
    return {
        "S1": [{"day": 0.0, "nsf_wqi": 85.0, "nsf_class": "Good",
                "ccme_wqi": 92.0, "ccme_class": "Good", "water_class": "II"}],
        "S2": [{"day": 0.0, "nsf_wqi": 72.0, "nsf_class": "Good",
                "ccme_wqi": 78.0, "ccme_class": "Fair", "water_class": "II"}],
    }


def _summaries():
    entry = {"stats": {"n": 24, "n_total": 24, "completeness": 1.0,
                       "mean": 7.0, "min": 6.5, "max": 7.5, "std": 0.2},
             "exceedance": {"n": 24, "n_exceed": 0, "pct_exceed": 0.0,
                            "limit": "6-9 -", "kind": "range"},
             "trend": {"slope_per_day": 0.01, "intercept": 7.0, "r2": 0.5,
                       "mann_kendall": {"tau": 0.1, "S": 5, "p_value": 0.4,
                                        "trend": "no trend"}}}
    return {"S1": {"ph": entry}, "S2": {"ph": entry}}


def test_report_contains_key_sections():
    md = build_report("Kali Test", 1, _stations(), _wqi_daily(),
                      {"total": 1, "by_max_level": {"warning": 1},
                       "by_parameter": {"do_mg_l": 1}, "unresolved": 0},
                      [{"station_id": "S1", "parameter": "do_mg_l",
                        "max_level": "warning", "triggered_at_day": 0.5,
                        "resolved_at_day": None, "peak_value": 3.0,
                        "peak_at_day": 0.5, "n_readings": 5}],
                      _summaries())
    assert "# Water Quality Monitoring Report — Kali Test" in md
    assert "## Executive summary" in md
    assert "## Water Quality Index by station and day" in md
    assert "## Alerts" in md
    assert "## Exceedance of PP 22/2021 class II limits" in md
    assert "## Trends" in md
    assert "85.00" in md  # S1 NSF WQI
    assert "72.00" in md  # S2 NSF WQI
    assert "do_mg_l" in md
    assert "unresolved" in md


def test_report_no_alerts_message():
    md = build_report("Kali Test", 1, _stations(), _wqi_daily(),
                      {"total": 0, "by_max_level": {}, "by_parameter": {},
                       "unresolved": 0}, [], _summaries())
    assert "No alerts were raised" in md


def test_report_documents_nsf_subset():
    md = build_report("Kali Test", 1, _stations(), _wqi_daily(),
                      {"total": 0, "by_max_level": {}, "by_parameter": {},
                       "unresolved": 0}, [], _summaries())
    assert "six-parameter NSF-style index" in md
    assert "PP 22/2021 class II" in md
