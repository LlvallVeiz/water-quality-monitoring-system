# Research — Water Quality Monitoring System

How the science behind this project was chosen, what each formula
does, and where every limit value comes from. Nothing here is
invented: each number is either quoted from the source listed or
explicitly marked as a project assumption.

## 1. Why a Water Quality Index?

A river is described by many parameters (pH, oxygen, turbidity,
nutrients, ...), each in its own unit. A Water Quality Index (WQI)
compresses them into one number on a 0–100 scale so that a manager,
a journalist or a resident can compare days, stations and rivers.
Two complementary indices are implemented because they answer
different questions:

- **NSF WQI** — "how good is the water, on an absolute scale, given
  expert judgement about what matters?" (weighted sum of sub-indices).
- **CCME WQI** — "how often, and by how much, did the water fail the
  legal objectives we chose?" (scope / frequency / amplitude of
  exceedances).

## 2. NSF WQI (Brown et al. 1970)

The National Sanitation Foundation index was developed by surveying
142 water-quality scientists about 35 candidate tests; nine
parameters were selected. Each parameter is converted to a sub-index
("Q-value", 0–100) through an expert-averaged weighting curve, then
multiplied by a weighting factor and summed:

```
WQI = sum(Q_i * w_i)
```

Weights (Brown et al. 1970): DO 0.17, fecal coliform 0.16, pH 0.11,
BOD 0.11, temperature change 0.10, total phosphate 0.10, nitrate
0.10, turbidity 0.08, total solids 0.07 (sum 1.00).

Classes (Brown et al. 1970): 90–100 Excellent, 70–90 Good, 50–70
Medium, 25–50 Bad, 0–25 Very Bad.

The published curves exist as graphs, not formulas. This project
implements them as piecewise-linear interpolations over anchor
points, calibrated so the published BASIN worked example is
reproduced exactly (DO 82 % sat → Q 90; fecal coliform 12 → 72;
pH 7.67 → 92; BOD 2 mg/L → 80; ΔT 5 °C → 72; phosphate 0.5 → 60;
nitrate 5 mg/L as NO3 → 67; turbidity 5 NTU → 85; total solids
150 mg/L → 78; WQI = 77.9). See `docs/WORKED_EXAMPLE.md` and the
test `test_nsf_wqi_reproduces_basin_total`.

When fewer than nine parameters are available, the weights are
renormalised over the parameters present — the subset rule BASIN
documents ("add the subtotals, add the weights, divide"). Our sensor
network measures six NSF parameters (DO, pH, nitrate, turbidity,
TDS, temperature change), so the NSF score reported here is a
**six-parameter NSF-style index**, labelled as such everywhere it
appears. It is comparable across days and stations within this
system, but it is not a full nine-parameter NSF WQI.

## 3. CCME WQI (CCME 2001)

The Canadian Council of Ministers of the Environment index compares
measurements against chosen objectives (here: PP 22/2021 class II,
see §5) through three factors:

```
F1 (scope)     = 100 * failed variables / total variables
F2 (frequency) = 100 * failed tests / total tests
F3 (amplitude) = nse / (0.01 * nse + 0.01),
                 nse = sum of excursions / total tests
WQI = 100 - sqrt(F1^2 + F2^2 + F3^2) / 1.732
```

The excursion of a failed test is `(value/objective - 1)` when the
objective must not be exceeded, `(objective/value - 1)` when it must
not fall below, and the distance to the nearest bound (relative to
that bound) for a range objective. The divisor 1.732 = √3 normalises
the worst case (F1 = F2 = F3 = 100) to a WQI of 0.

Classes (CCME 2001): 95–100 Excellent, 80–94 Good, 65–79 Fair,
45–64 Marginal, 0–44 Poor. CCME recommends at least four variables
measured at least four times; our daily CCME uses five variables
(pH, DO, nitrate, TDS, turbidity) over 24 hourly tests, which meets
that guidance.

## 4. Dissolved-oxygen saturation (Benson & Krause / APHA 4500-O)

The NSF DO sub-index is defined on **percent saturation**, not on
mg/L, so a DO reading must be converted using the saturation
concentration at the water temperature:

```
ln(C*) = -139.34411 + 1.575701e5/T - 6.642308e7/T^2
         + 1.243800e10/T^3 - 8.621949e11/T^4
```

with T in kelvin and C* in mg/L (freshwater, 1 atm). Reference
values: 14.62 mg/L at 0 °C, 9.09 at 20 °C, 8.26 at 25 °C,
7.56 at 30 °C. Warm water holds less oxygen, which is why the same
DO concentration scores higher (as percent saturation) in warm
water — and why summer low-DO events are ecologically dangerous.

## 5. Standards: PP No. 22/2021 and WHO GDWQ

### PP No. 22 Tahun 2021, Lampiran VI — Baku Mutu Air Sungai

Verified against the regulation text (river water, classes I–IV):

| Parameter | I | II | III | IV | Unit |
|---|---|---|---|---|---|
| Temperature (deviation) | 3 | 3 | 3 | 3 | °C |
| TDS | 1000 | 1000 | 1000 | 2000 | mg/L |
| TSS | 40 | 50 | 100 | 400 | mg/L |
| pH | 6–9 | 6–9 | 6–9 | 6–9 | – |
| BOD | 2 | 3 | 6 | 12 | mg/L |
| COD | 10 | 25 | 40 | 80 | mg/L |
| DO (minimum) | 6 | 4 | 3 | 1 | mg/L |
| Nitrate (as N) | 10 | 10 | 20 | 20 | mg/L as N |
| Nitrite (as N) | 0.06 | 0.06 | 0.06 | – | mg/L as N |
| Total phosphate (as P) | 0.2 | 0.2 | 1 | – | mg/L as P |
| Ammonia (as N) | 0.1 | 0.2 | 0.5 | – | mg/L as N |

Class uses: I — raw water for drinking water; II — recreation,
freshwater fish farming, animal husbandry, irrigation; III — fish
farming, husbandry, irrigation; IV — irrigation. A sample's class
is the strictest class whose limits it meets for every parameter
checked; if none, it is "below class IV" (reported as class V).

Note what PP 22/2021 does **not** regulate: turbidity,
conductivity and ORP have no river-water limit in the regulation.
For those, this project uses operational thresholds (see §6), never
a pretended legal limit.

### WHO Guidelines for Drinking-water Quality, 4th edition

- Nitrate: guideline value **50 mg/L as NO3** (= 11.3 mg/L as N);
  nitrite: **3 mg/L as NO2**.
- Turbidity: **< 5 NTU** (preferably < 1 NTU for effective
  disinfection) — an operational target for *treated drinking
  water*, not a health-based guideline value and not a river
  standard. That is why the river CCME objective for turbidity is
  set to 50 NTU (project operational level, §6) instead of 5 NTU:
  a raw river at 8 NTU would otherwise "fail" permanently.
- pH: **no health-based guideline value**; operational range
  6.5–8.5 (corrosion control, disinfection efficiency).
- TDS and DO: **no health-based guideline value** (TDS palatability
  is generally acceptable below ~1000 mg/L).

## 6. Alert thresholds (operational levels)

Warning/critical levels are built on PP 22/2021 class II with a
stricter escalation level. Each entry in `standards.py` records its
source; levels marked "project assumption" are operational choices,
not legal limits:

| Parameter | Warning | Critical | Source |
|---|---|---|---|
| pH | outside 6–9 | outside 5–10 | PP 22/2021; critical = assumption |
| DO | < 4 mg/L | < 2 mg/L | PP 22/2021 class II min; critical = assumption |
| Turbidity | > 50 NTU | > 100 NTU | project assumption (operational river levels) |
| Nitrate (as N) | > 10 mg/L | > 20 mg/L | PP 22/2021 class I/II; class III/IV |
| TDS | > 1000 mg/L | > 2000 mg/L | PP 22/2021 class I–III; class IV |
| Conductivity | > 1500 µS/cm | > 3000 µS/cm | assumption, consistent with TDS via 0.64 factor |
| Temperature | dev. > 3 °C | dev. > 5 °C | PP 22/2021 deviation; critical = assumption |
| ORP | < 150 or > 600 mV | < 100 or > 700 mV | project assumption (no PP/WHO limit) |

## 7. Parameter dynamics modelled by the simulator

- **Diurnal cycle.** Temperature peaks mid-afternoon; DO and pH
  follow photosynthesis (peak late afternoon); turbidity dips
  slightly at night. This is the standard limnological pattern
  (APHA Standard Methods; Wetzel, *Limnology*).
- **Seasonal cycle.** An annual sine on temperature (±2 °C around
  the station mean); DO follows through the solubility relation
  (§4), so summer water carries less oxygen.
- **Rain / runoff.** Sediment and fertiliser wash-in: turbidity
  spikes (×10 or more), nitrate rises, DO dips from oxygen demand
  of washed-in organic matter.
- **Algal bloom.** Daytime photosynthesis raises pH; night
  respiration and decomposition consume oxygen (DO falls, sometimes
  below the class II minimum); biomass raises turbidity.
- **Industrial spill.** Ionic load raises conductivity (and hence
  derived TDS) sharply; oxidants raise ORP; DO falls.
- **Downstream propagation.** An event at an upstream station
  reaches a downstream station after `distance / flow velocity`
  (default 24 km/day ≈ 1 km/h, a slow lowland river) and weakened
  by `(1 - 0.01)^distance` (1 % loss per km — dilution/decay).
  Both constants are project assumptions, stated in `network.py`.
- **TDS from conductivity.** `TDS = 0.64 × conductivity` is the
  conventional mid-range conversion (APHA notes 0.55–0.70); field
  probes commonly report TDS this way.
- **Sensor drift and gaps.** A slow linear bias (default
  +0.02 NTU/day on turbidity) and seeded random dropouts plus
  explicit outage windows model real probe behaviour.

## 8. Trend and anomaly methods

- **Mann-Kendall test** (Mann 1945; Kendall 1975): non-parametric
  trend test on the sign of all pairwise differences, with tie
  correction and the normal approximation; two-sided p-value.
  Implemented from scratch in `analysis.py`.
- **Linear trend**: ordinary least squares slope per day with R².
- **Anomaly detection**: rolling 24 h z-score; a reading is flagged
  when |z| > 3 against its preceding window.
- **Correlation**: Pearson r on pairwise-complete observations.

## References

1. Brown, R. M., McClelland, N. I., Deininger, R. A., & Tozer, R. G.
   (1970). *A Water Quality Index — Do We Dare?* Water & Sewage
   Works, 117(10), 339–343.
   Worked example and curves as reproduced by BASIN:
   https://bcn.boulder.co.us/basin/watershed/wqi_nsf.html
2. Canadian Council of Ministers of the Environment (CCME). (2001).
   *Canadian Water Quality Guidelines for the Protection of Aquatic
   Life: CCME Water Quality Index 1.0, Technical Report.*
   https://www150.statcan.gc.ca/n1/pub/16-001-m/2007003/4053419-eng.htm
   (formula and classes also summarised at
   https://www.gov.nl.ca/mca/files/waterres-reports-hydrogeology-westernnl-appendix-v.pdf)
3. Peraturan Pemerintah Republik Indonesia Nomor 22 Tahun 2021,
   Lampiran VI — Baku Mutu Air Nasional (air sungai dan sejenisnya).
   https://laboratix.co/wp-content/uploads/2024/06/Lampiran-VI-Salinan-PP-Nomor-22-Tahun-2021-Air-Permukaan.pdf
4. World Health Organization. (2022). *Guidelines for
   Drinking-water Quality: Fourth edition incorporating the first,
   second and third addenda.*
   https://cdn.who.int/media/docs/default-source/wash-documents/water-safety-and-quality/dwq-guidelines-4/gdwq_4ed_with_third-addenda_chemical-aspects.pdf
5. APHA, AWWA, WEF. *Standard Methods for the Examination of Water
   and Wastewater*, 24th edition (2023), Section 4500-O (oxygen),
   Section 2540 (solids), Section 2510 (conductivity).
   https://www.standardmethods.org/
6. Benson, B. B., & Krause, D. (1984). The concentration and
   isotopic fractionation of oxygen dissolved in freshwater and
   seawater in equilibrium with the atmosphere. *Limnology and
   Oceanography*, 29(3), 620–632.
7. Mann, H. B. (1945). Nonparametric tests against trend.
   *Econometrica*, 13(3), 245–259; Kendall, M. G. (1975). *Rank
   Correlation Methods*, 4th edition. Charles Griffin.
8. Wetzel, R. G. (2001). *Limnology: Lake and River Ecosystems*,
   3rd edition. Academic Press. (Diurnal/seasonal DO and pH cycles,
   eutrophication dynamics.)
