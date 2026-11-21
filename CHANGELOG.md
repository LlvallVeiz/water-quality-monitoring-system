# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] — 2026-11-19

Initial release.

- Sensor simulator: 8 parameters (pH, temperature, DO, turbidity,
  conductivity, TDS, nitrate as N, ORP) with diurnal + seasonal
  cycles, noise, drift, data gaps and three event kinds (rain,
  algal bloom, industrial spill); deterministic per seed.
- River network: JSON configuration, downstream propagation with
  travel-time lag and attenuation.
- Water Quality Index: NSF-style (six parameters, weights
  renormalised per the BASIN subset rule; Q-curves calibrated to
  reproduce the BASIN worked example, WQI 77.9) and CCME
  (scope/frequency/amplitude, PP 22/2021 class II objectives).
- Standards: PP No. 22/2021 river limits (classes I–IV) and WHO
  GDWQ values, verified against the source texts; water-class
  classification.
- Alert engine: warning/critical levels, 3-reading persistence,
  escalation, dedup, auto-resolve; alert log in SQLite.
- Storage: SQLite (readings, alerts, daily WQI) + CSV ingest/export.
- Analysis: descriptive stats, % exceedance, OLS trend, Mann-Kendall
  test, Pearson correlation, rolling z-score anomalies.
- Outputs: Markdown report + self-contained HTML dashboard with
  matplotlib charts.
- CLI: `simulate`, `ingest`, `wqi`, `alerts`, `analyze`, `report`,
  `dashboard`, `run`.
- Examples: Kali Biru normal 30-day run (0 alerts) and event run
  (rain + bloom + spill, 10 alerts, downstream propagation visible).
- Tests: 103 pytest tests, all passing, including hand-verified
  BASIN/CCME/DO-saturation calculations.
