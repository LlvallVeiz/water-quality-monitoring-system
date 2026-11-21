# Worked Example — verifying the index math by hand

This document shows, step by step, that the numbers this system
produces can be reproduced with a calculator. All three examples are
also encoded as tests (`tests/test_wqi.py`,
`tests/test_do_saturation.py`, `tests/test_analysis.py`).

## 1. NSF WQI — the BASIN worked example

Input (Brown et al. 1970, as reproduced by BASIN):

| Test | Result | Q-value | Weight | Subtotal |
|---|---|---|---|---|
| DO | 82 % sat | 90 | 0.17 | 15.30 |
| Fecal coliform | 12 /100 mL | 72 | 0.16 | 11.52 |
| pH | 7.67 | 92 | 0.11 | 10.12 |
| BOD | 2 mg/L | 80 | 0.11 | 8.80 |
| Temperature change | 5 °C | 72 | 0.10 | 7.20 |
| Total phosphate | 0.5 mg/L | 60 | 0.10 | 6.00 |
| Nitrates | 5 mg/L as NO3 | 67 | 0.10 | 6.70 |
| Turbidity | 5 NTU | 85 | 0.08 | 6.80 |
| Total solids | 150 mg/L | 78 | 0.07 | 5.46 |
| **WQI** | | | | **77.90** |

Check: 15.30 + 11.52 + 10.12 + 8.80 + 7.20 + 6.00 + 6.70 + 6.80 + 5.46
= 77.90, class **Good** (70–90). The code reproduces this exactly
(`nsf_wqi` on the same inputs returns 77.9).

Subset rule: without BOD and temperature change, the subtotals sum
to 61.90 and the weights to 0.79, so WQI = 61.90 / 0.79 = **78.4**
— again reproduced by the code.

## 2. CCME WQI — hand computation

Two variables, ten tests each. pH always passes (7.0, objective
6–9). Nitrate fails 5 of 10 tests at 20 mg/L against an objective
of 10 mg/L; each failure has excursion 20/10 − 1 = 1.0.

- F1 (scope) = 1 failed variable / 2 variables × 100 = **50**
- F2 (frequency) = 5 failed tests / 20 tests × 100 = **25**
- nse = total excursion / total tests = 5.0 / 20 = **0.25**
- F3 = 0.25 / (0.01 × 0.25 + 0.01) = 0.25 / 0.0125 = **20**
- WQI = 100 − √(50² + 25² + 20²) / 1.732
      = 100 − √3525 / 1.732 = 100 − 59.37 / 1.732 = **65.72**,
  class **Fair** (65–79).

## 3. DO percent saturation — hand computation

At 20 °C the Benson & Krause equation gives a saturation
concentration of 9.09 mg/L. A reading of 7.45 mg/L at 20 °C is
therefore 7.45 / 9.09 × 100 = **81.9 % saturation**, whose NSF
Q-value (curve anchors 80 → 88, 82 → 90) is ≈ **90**. At 25 °C the
same 7.45 mg/L is 7.45 / 8.26 × 100 = 90.2 % saturation (Q ≈ 93):
the same concentration scores higher in warm water because warm
water cannot hold as much oxygen.

## 4. Alert persistence — hand trace

Thresholds: DO warning < 4 mg/L, persistence 3, resolve after 2
in-range readings. Readings (hourly): 3.0, 3.0, 1.5, 1.5, 8.0, 8.0.

- Hour 0–1: candidate, 2 consecutive crossings — no alert yet.
- Hour 2: 3rd consecutive crossing → alert triggers (level
  warning, triggered at day 0.083); the 1.5 mg/L reading is below
  the critical level (2 mg/L), so the alert escalates to critical.
- Hour 3: still breaching — same alert, no duplicate (dedup).
- Hour 4: in range (streak 1) — alert stays open.
- Hour 5: in range (streak 2) — alert resolves.

Result: exactly **one** alert, max level critical, peak value
1.5 mg/L. A single isolated spike (e.g. one 1.0 mg/L reading among
8.0 mg/L readings) never produces an alert.
