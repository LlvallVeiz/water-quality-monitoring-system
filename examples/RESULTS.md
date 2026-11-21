# Example Results — Kali Biru, 30 days, seed 42

All numbers below are the actual outputs of
`python examples/run_examples.py` (pipeline v1.0.0, 30 days × 3
stations × 24 hourly readings = 2160 readings per scenario).
Artefacts: `examples/output/normal/` and `examples/output/event/`
(`report.md`, `dashboard.html`, `readings.csv`, `readings.db`,
`summary.json`).

## Scenario 1 — Normal river (no events)

| Station | Mean NSF WQI | Min NSF WQI | Mean CCME WQI | Alerts | Last PP22 class |
|---|---|---|---|---|---|
| KB-01 Hulu (km 0) | 87.09 | 86.49 | 100.00 | 0 | I |
| KB-02 Tengah (km 12) | 80.73 | 80.62 | 100.00 | 0 | I |
| KB-03 Hilir (km 25) | 78.48 | 78.26 | 100.00 | 0 | I |

- Water quality degrades gradually downstream (NSF 87.1 → 80.7 →
  78.5), as designed: turbidity baseline rises 5 → 12 → 15 NTU and
  nitrate 1.0 → 2.5 → 3.5 mg/L as N along the river.
- Zero exceedances of any PP 22/2021 class II limit at any station.
- Missing readings (seeded gaps + a 12 h outage at KB-02 on day 8):
  KB-01 4/720, KB-02 17/720, KB-03 11/720.

## Scenario 2 — Rain + algal bloom + industrial spill

Events: rain days 10–12 at KB-01 (propagates downstream), algal
bloom days 15–19 at KB-02, industrial spill day 20–21 at KB-02.

| Station | Mean NSF WQI | Min NSF WQI | Mean CCME WQI | Min CCME WQI | Alerts | Last PP22 class |
|---|---|---|---|---|---|---|
| KB-01 Hulu (km 0) | 86.35 | 76.10 | 99.04 | 85.36 | 1 | I |
| KB-02 Tengah (km 12) | 79.20 | 69.83 | 97.39 | 81.11 | 5 | I |
| KB-03 Hilir (km 25) | 76.97 | 66.18 | 97.45 | 85.42 | 4 | I |

- **10 alerts total: 3 critical, 7 warning.**
  Turbidity 3, DO 2, TDS 2, conductivity 2, ORP 1.
- **Downstream propagation is visible in the alert times**
  (flow 24 km/day, attenuation 1 %/km):
  turbidity critical KB-01 day 10.46 (peak 127.24 NTU) →
  KB-02 day 10.92 (peak 118.84 NTU) → KB-03 day 11.50
  (peak 110.98 NTU). Spill: conductivity warning KB-02 day 20.33
  (peak 2064.80 µS/cm) → KB-03 day 20.88 (peak 1904.17 µS/cm).
- **Worst day overall:** KB-03 day 17, NSF WQI 66.18 (Medium) —
  the propagated algal bloom at its peak.
- **Exceedance of PP 22/2021 class II limits** (30 days):
  KB-02 DO 1.85 % of readings below 4 mg/L, TDS 1.28 % above
  1000 mg/L; KB-03 DO 2.26 %, TDS 0.99 %; KB-01 0 % everywhere.
- **Extremes:** turbidity max 127.24 NTU (KB-01, rain),
  DO min 3.17 mg/L (KB-03, bloom), conductivity max 2064.80 µS/cm
  (KB-02, spill), nitrate max 6.73 mg/L as N (KB-03, rain runoff).
- All alerts resolved on their own as the events decayed; none
  remained unresolved at day 30.

## How to reproduce

```bash
python examples/run_examples.py
# or a single scenario:
python -m water_quality run --network scenarios/event_river.json \
    --days 30 --seed 42 --out examples/output/event
```
