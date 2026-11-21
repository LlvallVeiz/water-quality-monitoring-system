# Water Quality Monitoring System

End-to-end river water-quality monitoring in Python: realistic
sensor simulation, a multi-station river network, Water Quality
Index scoring (NSF and CCME), a threshold alert engine, SQLite
storage, statistical analysis, Markdown reports and a static HTML
dashboard.

```
rain + bloom + spill  →  sensors  →  SQLite  →  WQI + alerts + trends
                                                     →  report.md + dashboard.html
```

## Background

A river is described by many parameters in different units. This
system turns hourly probe readings into decisions:

- **Water Quality Index** — one 0–100 number per station per day,
  computed two ways: the **NSF WQI** (Brown et al. 1970, weighted
  sub-indices, six-parameter NSF-style subset with renormalised
  weights) and the **CCME WQI** (CCME 2001, scope/frequency/amplitude
  of exceedances against PP 22/2021 class II objectives).
- **Water class** — the strictest PP No. 22 Tahun 2021 class (I–IV)
  whose limits a sample meets.
- **Alerts** — warning/critical levels from PP 22/2021 + WHO GDWQ,
  with persistence (3 consecutive readings), escalation and dedup,
  so a single spike never pages anyone.
- **Analysis** — per-parameter statistics, % exceedance of the
  standard, OLS trend + Mann-Kendall test, Pearson correlations,
  rolling z-score anomaly detection.

Full theory, limit tables and sources: [`docs/RESEARCH.md`](docs/RESEARCH.md).
Hand-worked verification of the index math: [`docs/WORKED_EXAMPLE.md`](docs/WORKED_EXAMPLE.md).

## Project structure

```
water-quality-monitoring-system/
├── src/water_quality/
│   ├── parameters.py      # parameter metadata, units, conversions
│   ├── do_saturation.py   # Benson & Krause DO saturation (APHA 4500-O)
│   ├── standards.py       # PP 22/2021 + WHO GDWQ limits, alert thresholds
│   ├── wqi.py             # NSF + CCME indices, Q-curves
│   ├── simulator.py       # sensor simulator (diurnal/seasonal/noise/drift/events)
│   ├── network.py         # station network, downstream propagation
│   ├── alerts.py          # alert engine (persistence, escalation, dedup)
│   ├── storage.py         # SQLite store + CSV ingest/export
│   ├── analysis.py        # stats, exceedance, trends, correlation, anomalies
│   ├── report.py          # Markdown report generator
│   ├── dashboard.py       # static HTML dashboard (matplotlib PNGs)
│   ├── pipeline.py        # end-to-end orchestration
│   └── cli.py             # `wqm` command-line interface
├── configs/
│   └── network_river.json # Kali Biru: 3 stations, Hulu → Hilir
├── scenarios/
│   ├── normal_river.json  # 30 days, no events
│   └── event_river.json   # rain (d10–12) + bloom (d15–19) + spill (d20–21)
├── examples/
│   ├── run_examples.py    # regenerates all example outputs
│   ├── RESULTS.md         # key results from the real runs
│   └── output/            # generated artefacts per scenario
├── docs/
│   ├── RESEARCH.md
│   └── WORKED_EXAMPLE.md
└── tests/                 # 103 pytest tests
```

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt   # numpy, matplotlib; pytest for tests
export PYTHONPATH=src             # makes `python -m water_quality` work
# alternative: pip install -e . --break-system-packages  (installs the `wqm` command)
```

## Usage

Run the whole pipeline on a scenario (simulate → store → WQI →
alerts → analysis → report + dashboard):

```bash
python -m water_quality run --network scenarios/event_river.json \
    --days 30 --seed 42 --out examples/output/event
```

Individual stages are available as subcommands:

```bash
python -m water_quality simulate --network scenarios/normal_river.json --days 30 --seed 42 --out readings.csv
python -m water_quality ingest --db out/readings.db --csv readings.csv --station KB-01
python -m water_quality wqi --db out/readings.db --network scenarios/normal_river.json
python -m water_quality alerts --db out/readings.db --network scenarios/normal_river.json
python -m water_quality analyze --db out/readings.db --network scenarios/normal_river.json
python -m water_quality report --db out/readings.db --network scenarios/normal_river.json --out out/report.md
python -m water_quality dashboard --db out/readings.db --network scenarios/normal_river.json --out out/dashboard.html
```

Run the tests:

```bash
python -m pytest tests/ -q   # 103 passed
```

## Example output

Kali Biru, 3 stations (Hulu → Tengah → Hilir), 30 days, seed 42
(full numbers in [`examples/RESULTS.md`](examples/RESULTS.md)):

| Scenario | Station | Mean NSF WQI | Mean CCME WQI | Alerts |
|---|---|---|---|---|
| Normal | KB-01 Hulu | 87.09 | 100.00 | 0 |
| Normal | KB-02 Tengah | 80.73 | 100.00 | 0 |
| Normal | KB-03 Hilir | 78.48 | 100.00 | 0 |
| Rain + bloom + spill | KB-01 Hulu | 86.35 | 99.04 | 1 |
| Rain + bloom + spill | KB-02 Tengah | 79.20 | 97.39 | 5 |
| Rain + bloom + spill | KB-03 Hilir | 76.97 | 97.45 | 4 |

Event scenario: 10 alerts (3 critical, 7 warning). The rain
turbidity pulse is visible propagating downstream — critical at
KB-01 on day 10.46 (peak 127.24 NTU), KB-02 on day 10.92
(118.84 NTU), KB-03 on day 11.50 (110.98 NTU). Worst day: KB-03
day 17, NSF WQI 66.18 (Medium) at the peak of the algal bloom.

## Design decisions

- **NSF subset, labelled honestly.** The network measures six of
  the nine NSF parameters (no fecal coliform, BOD or phosphate
  probes), so the NSF score is a six-parameter NSF-style index with
  weights renormalised per the BASIN subset rule — stated in every
  report and in the code, never presented as a full nine-parameter
  NSF WQI.
- **TDS derived from conductivity** (`TDS = 0.64 × conductivity`),
  the conventional field-probe conversion, rather than simulated
  independently.
- **Temperature as deviation.** PP 22/2021 limits temperature
  *deviation* (3 °C), not absolute temperature; alerts, exceedance
  and CCME all compare against each station's own median
  temperature, so the seasonal cycle itself never raises an alert.
- **Turbidity objective 50 NTU for the river CCME.** WHO's 5 NTU
  target applies to treated drinking water; a raw river at 8 NTU
  would "fail" permanently. The choice is documented in
  `docs/RESEARCH.md` §5.
- **Deterministic simulation.** One seed reproduces a whole
  network exactly; every example number in this repo comes from a
  real run (`examples/run_examples.py`), never typed by hand.
- **stdlib + numpy/matplotlib only.** No pandas, no web framework;
  the dashboard is a single self-contained HTML file.

## Limitations and future work

- The simulator is synthetic: it models plausible dynamics, not a
  calibrated catchment. Real deployment needs probe calibration
  against laboratory samples.
- No microbiology (fecal coliform / E. coli) or BOD/COD probes, so
  the NSF index stays a six-parameter subset.
- Flow velocity and attenuation are fixed project assumptions
  (24 km/day, 1 %/km); a real river needs gauged hydraulics.
- Alerts are logged, not delivered (no SMS/email/webhook sender yet).
- Mann-Kendall uses the normal approximation; for n < 10 an exact
  test would be more accurate.
- Future: real-time MQTT/HTTP ingest, a live dashboard, more
  parameters (chlorophyll-a, ammonia), and calibration of the
  simulator against a gauged river dataset.

## License

MIT — see [LICENSE](LICENSE).
