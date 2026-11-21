"""Static HTML dashboard generator.

Renders one self-contained HTML page per run with matplotlib charts
embedded as base64 PNGs: a time-series chart per parameter (all
stations overlaid), a daily WQI chart, and a summary table. No
JavaScript, no external assets — the file opens in any browser.
"""

from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .parameters import PARAMETERS  # noqa: E402

plt.rcParams.update({"figure.dpi": 120, "font.size": 9})


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def time_series_chart(readings_by_station: dict[str, list[dict]],
                      parameter: str, title: str) -> str:
    """Base64 PNG of one parameter's time series for all stations."""
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for sid, rows in readings_by_station.items():
        xs = [r["timestamp_day"] for r in rows if r.get(parameter) is not None]
        ys = [r[parameter] for r in rows if r.get(parameter) is not None]
        ax.plot(xs, ys, label=sid, linewidth=0.8)
    ax.set_xlabel("Day")
    ax.set_ylabel(f"{PARAMETERS[parameter].name} ({PARAMETERS[parameter].unit})")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    return _fig_to_base64(fig)


def wqi_chart(wqi_daily: dict[str, list[dict]]) -> str:
    """Base64 PNG of daily NSF WQI per station with class bands."""
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for sid, daily in wqi_daily.items():
        xs = [d["day"] for d in daily if d.get("nsf_wqi") is not None]
        ys = [d["nsf_wqi"] for d in daily if d.get("nsf_wqi") is not None]
        ax.plot(xs, ys, marker="o", markersize=3, label=f"{sid} NSF")
    for bound, label in ((90, "Excellent"), (70, "Good"), (50, "Medium"), (25, "Bad")):
        ax.axhline(bound, color="grey", linestyle="--", linewidth=0.6)
        ax.text(0.1, bound + 1, label, fontsize=7, color="grey")
    ax.set_xlabel("Day")
    ax.set_ylabel("NSF WQI")
    ax.set_ylim(0, 100)
    ax.set_title("Daily NSF WQI by station")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    return _fig_to_base64(fig)


def build_dashboard(river: str, n_days: int, stations: list[dict],
                    readings_by_station: dict[str, list[dict]],
                    wqi_daily: dict[str, list[dict]],
                    alerts: list[dict], summaries: dict[str, dict]) -> str:
    """Assemble the full dashboard HTML string."""
    charts = []
    for param in PARAMETERS:
        charts.append(
            f"<h2>{PARAMETERS[param].name}</h2>"
            f"<img src=\"data:image/png;base64,"
            f"{time_series_chart(readings_by_station, param, PARAMETERS[param].name)}\" "
            f"alt=\"{param} time series\">")
    charts.append("<h2>Daily NSF WQI</h2>"
                  f"<img src=\"data:image/png;base64,{wqi_chart(wqi_daily)}\" "
                  f"alt=\"Daily NSF WQI\">")
    rows_html = []
    for st in stations:
        sid = st["station_id"]
        daily = wqi_daily.get(sid, [])
        nsf = [d["nsf_wqi"] for d in daily if d.get("nsf_wqi") is not None]
        ccme = [d["ccme_wqi"] for d in daily if d.get("ccme_wqi") is not None]
        n_alerts = sum(1 for a in alerts if a["station_id"] == sid)
        rows_html.append(
            f"<tr><td>{sid}</td><td>{st['name']}</td>"
            f"<td>{sum(nsf)/len(nsf):.1f}</td><td>{min(nsf):.1f}</td>"
            f"<td>{sum(ccme)/len(ccme):.1f}</td><td>{n_alerts}</td></tr>")
    alert_rows = "".join(
        f"<tr><td>{a['station_id']}</td><td>{a['parameter']}</td>"
        f"<td>{a['max_level']}</td><td>{a['triggered_at_day']:.2f}</td>"
        f"<td>{a['peak_value']:.2f}</td></tr>" for a in alerts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<title>Water Quality Dashboard — {river}</title>
<style>
body {{ font-family: sans-serif; max-width: 1000px; margin: 2em auto; padding: 0 1em; }}
img {{ max-width: 100%; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
th {{ background: #eef; }}
</style></head>
<body>
<h1>Water Quality Dashboard — {river}</h1>
<p>Period: {n_days} days, hourly readings, {len(stations)} stations.</p>
<h2>Station summary</h2>
<table>
<tr><th>Station</th><th>Name</th><th>Mean NSF WQI</th><th>Min NSF WQI</th>
<th>Mean CCME WQI</th><th>Alerts</th></tr>
{''.join(rows_html)}
</table>
<h2>Alerts ({len(alerts)})</h2>
<table>
<tr><th>Station</th><th>Parameter</th><th>Max level</th>
<th>Triggered (day)</th><th>Peak value</th></tr>
{alert_rows if alert_rows else '<tr><td colspan="5">No alerts.</td></tr>'}
</table>
{''.join(charts)}
<p><small>NSF WQI: six-parameter NSF-style index (DO, pH, nitrate,
turbidity, TDS, temperature change). CCME WQI: PP 22/2021 class II
objectives. Generated by water-quality-monitoring-system.</small></p>
</body>
</html>
"""
