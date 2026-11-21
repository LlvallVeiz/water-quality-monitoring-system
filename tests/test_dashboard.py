"""Tests for the static HTML dashboard generator."""

from water_quality.dashboard import build_dashboard, time_series_chart, wqi_chart


def _readings():
    rows = []
    for h in range(48):
        rows.append({"timestamp_day": h / 24.0, "hour": h % 24,
                     "ph": 7.0, "temperature_c": 25.0, "do_mg_l": 8.0,
                     "turbidity_ntu": 10.0, "conductivity_us_cm": 250.0,
                     "tds_mg_l": 160.0, "nitrate_mg_l_n": 2.0, "orp_mv": 300.0})
    return {"S1": rows}


def test_time_series_chart_is_base64_png():
    import base64
    b64 = time_series_chart(_readings(), "ph", "pH")
    raw = base64.b64decode(b64)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_wqi_chart_is_base64_png():
    import base64
    daily = {"S1": [{"day": 0.0, "nsf_wqi": 85.0}, {"day": 1.0, "nsf_wqi": 80.0}]}
    raw = base64.b64decode(wqi_chart(daily))
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_dashboard_html_structure():
    stations = [{"station_id": "S1", "name": "Upstream", "river_km": 0.0}]
    daily = {"S1": [{"day": 0.0, "nsf_wqi": 85.0, "nsf_class": "Good",
                     "ccme_wqi": 90.0, "ccme_class": "Good", "water_class": "II"},
                    {"day": 1.0, "nsf_wqi": 80.0, "nsf_class": "Good",
                     "ccme_wqi": 88.0, "ccme_class": "Good", "water_class": "II"}]}
    html = build_dashboard("Kali Test", 2, stations, _readings(), daily, [], {})
    assert "<!DOCTYPE html>" in html
    assert "Kali Test" in html
    assert "82.5" in html  # mean NSF WQI (85 + 80) / 2 in summary table
    assert "data:image/png;base64," in html
    assert html.count("data:image/png;base64,") == 9  # 8 params + WQI chart
    assert "No alerts." in html


def test_dashboard_lists_alerts():
    stations = [{"station_id": "S1", "name": "Upstream", "river_km": 0.0}]
    daily = {"S1": [{"day": 0.0, "nsf_wqi": 85.0, "nsf_class": "Good",
                     "ccme_wqi": 90.0, "ccme_class": "Good", "water_class": "II"}]}
    alerts = [{"station_id": "S1", "parameter": "do_mg_l", "max_level": "critical",
               "triggered_at_day": 0.5, "peak_value": 1.5}]
    html = build_dashboard("Kali Test", 1, stations, _readings(), daily, alerts, {})
    assert "do_mg_l" in html
    assert "critical" in html
