"""Markdown report generator.

Builds a human-readable monitoring report for one period: executive
summary, per-station WQI table (NSF + CCME + PP 22/2021 class),
alert summary, exceedance table and trend table. All numbers come
from the analysis functions; this module only formats them.
"""

from __future__ import annotations

from .parameters import PARAMETERS


def build_report(river: str, n_days: int, stations: list[dict],
                 wqi_daily: dict[str, list[dict]],
                 alert_summary: dict, alerts: list[dict],
                 summaries: dict[str, dict],
                 correlations: dict[str, dict] | None = None) -> str:
    """Assemble the full Markdown report.

    ``stations``: list of ``{"station_id", "name", "river_km"}``.
    ``wqi_daily``: ``{station_id: [daily rows]}`` from the store.
    ``summaries``: ``{station_id: station_summary(...)}``.
    """
    lines: list[str] = []
    lines.append(f"# Water Quality Monitoring Report — {river}")
    lines.append("")
    lines.append(f"**Period:** {n_days} days (hourly readings). "
                 f"**Stations:** {len(stations)}.")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    total_alerts = alert_summary.get("total", 0)
    lines.append(f"- Total alerts raised: **{total_alerts}** "
                 f"({alert_summary.get('by_max_level', {})}).")
    for st in stations:
        sid = st["station_id"]
        daily = wqi_daily.get(sid, [])
        if not daily:
            continue
        nsf_vals = [d["nsf_wqi"] for d in daily if d.get("nsf_wqi") is not None]
        ccme_vals = [d["ccme_wqi"] for d in daily if d.get("ccme_wqi") is not None]
        nsf_mean = sum(nsf_vals) / len(nsf_vals) if nsf_vals else float("nan")
        ccme_mean = sum(ccme_vals) / len(ccme_vals) if ccme_vals else float("nan")
        last_class = daily[-1].get("water_class", "?")
        lines.append(
            f"- **{st['name']} ({sid}, km {st['river_km']:.1f})**: "
            f"mean NSF WQI {nsf_mean:.1f}, mean CCME WQI {ccme_mean:.1f}, "
            f"PP 22/2021 class on the last day: **{last_class}**.")
    lines.append("")
    lines.append("## Water Quality Index by station and day")
    lines.append("")
    lines.append("| Station | Day | NSF WQI | NSF class | CCME WQI | CCME class | PP22 class |")
    lines.append("|---------|----:|--------:|-----------|---------:|------------|-----------:|")
    for st in stations:
        for d in wqi_daily.get(st["station_id"], []):
            lines.append(
                f"| {st['station_id']} | {d['day']:.0f} | "
                f"{_fmt(d.get('nsf_wqi'))} | {d.get('nsf_class', '-')} | "
                f"{_fmt(d.get('ccme_wqi'))} | {d.get('ccme_class', '-')} | "
                f"{d.get('water_class', '-')} |")
    lines.append("")
    lines.append("## Alerts")
    lines.append("")
    if not alerts:
        lines.append("No alerts were raised in this period.")
    else:
        lines.append("| Station | Parameter | Max level | Triggered (day) | "
                     "Resolved (day) | Peak value |")
        lines.append("|---------|-----------|-----------|----------------:|"
                     "---------------:|-----------:|")
        for a in alerts:
            res = f"{a['resolved_at_day']:.2f}" if a.get("resolved_at_day") is not None else "unresolved"
            lines.append(
                f"| {a['station_id']} | {a['parameter']} | {a['max_level']} | "
                f"{a['triggered_at_day']:.2f} | {res} | {a['peak_value']:.2f} |")
    lines.append("")
    lines.append("## Exceedance of PP 22/2021 class II limits")
    lines.append("")
    lines.append("| Station | Parameter | n | n exceed | % exceed | Limit |")
    lines.append("|---------|-----------|---:|---------:|---------:|-------|")
    for st in stations:
        summary = summaries.get(st["station_id"], {})
        for param, entry in summary.items():
            exc = entry.get("exceedance")
            if exc is None:
                continue
            lines.append(
                f"| {st['station_id']} | {param} | {exc['n']} | "
                f"{exc['n_exceed']} | {exc['pct_exceed']:.2f} | {exc['limit']} |")
    lines.append("")
    lines.append("## Trends (OLS slope per day + Mann-Kendall)")
    lines.append("")
    lines.append("| Station | Parameter | Slope/day | R² | Mann-Kendall | p |")
    lines.append("|---------|-----------|----------:|---:|--------------|---:|")
    for st in stations:
        summary = summaries.get(st["station_id"], {})
        for param, entry in summary.items():
            tr = entry["trend"]
            mk = tr["mann_kendall"]
            slope = tr["slope_per_day"]
            lines.append(
                f"| {st['station_id']} | {param} | "
                f"{slope if slope is not None else '-'} | "
                f"{tr['r2'] if tr['r2'] is not None else '-'} | "
                f"{mk['trend']} | {mk['p_value'] if mk['p_value'] is not None else '-'} |")
    lines.append("")
    lines.append("## Parameter statistics")
    lines.append("")
    lines.append("| Station | Parameter | Mean | Min | Max | Std | Completeness |")
    lines.append("|---------|-----------|-----:|----:|----:|----:|-------------:|")
    for st in stations:
        summary = summaries.get(st["station_id"], {})
        for param, entry in summary.items():
            s = entry["stats"]
            lines.append(
                f"| {st['station_id']} | {param} | "
                f"{_fmt(s['mean'])} | {_fmt(s['min'])} | {_fmt(s['max'])} | "
                f"{_fmt(s['std'])} | {s['completeness']:.2%} |")
    if correlations:
        lines.append("")
        lines.append("## Correlations (Pearson, strongest pairs)")
        lines.append("")
        pairs: list[tuple[float, str, str, str]] = []
        for sid, matrix in correlations.items():
            for a in matrix:
                for b in matrix[a]:
                    if a < b and matrix[a][b] is not None:
                        pairs.append((abs(matrix[a][b]), sid, a, b))
        pairs.sort(reverse=True)
        lines.append("| Station | Parameter A | Parameter B | r |")
        lines.append("|---------|-------------|-------------|---:|")
        for _, sid, a, b in pairs[:10]:
            lines.append(f"| {sid} | {a} | {b} | {correlations[sid][a][b]:.3f} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- NSF WQI here is a six-parameter NSF-style index (DO, pH, "
                 "nitrate, turbidity, TDS, temperature change) with weights "
                 "renormalised over the parameters present, per the BASIN "
                 "subset rule.")
    lines.append("- CCME WQI uses PP 22/2021 class II objectives "
                 "(pH 6-9, DO >= 4 mg/L, nitrate <= 10 mg/L as N, "
                 "TDS <= 1000 mg/L) plus a project operational turbidity "
                 "objective of 50 NTU; the WHO 5 NTU target applies to "
                 "treated drinking water, not a raw river.")
    lines.append("- Temperature exceedance is measured as deviation from "
                 "the station median temperature (PP 22/2021 limits "
                 "deviation, not absolute temperature).")
    lines.append("")
    return "\n".join(lines)


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
