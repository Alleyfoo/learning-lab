# RUN B — Result: PASSED. Calibration question CLOSED.

Preregistered at `95c8b1f` before `run_b.py` existed. Pass criteria applied as written; no
threshold was moved.

---

## Certification

| # | Criterion | Value | Band | Result |
| --- | --- | --- | --- | --- |
| **P1** | Power at corrected floor, resampled baseline | **0.8002** | [0.78, 0.82] | **PASS** |
| **P2** | Null alarm rate, resampled baseline | **0.0511** | [0.04, 0.06] | **PASS** |
| **P3** | Power at corrected floor, fixed committed baseline | **0.8141** | [0.75, 0.85] | **PASS** |
| **P4** | Corrected floor larger than v1 | **23.7040%** | > 22.4367% | **PASS** |

Calibration seeds `700000`, certification seeds `810000`, disjoint from each other and from
RUN A's sweep family `90909`. 8,000 trials per calibration evaluation, 40,000 per certification.

## The corrected floor

| | v1 (`l4/1.1.0`) | v2 (`l4/2.0.0`) |
| --- | --- | --- |
| Single-period floor | 22.4367% | **23.7040%** |
| Sustained (k=6) floor | 10.7782% | **11.0794%** |
| MDE method | closed-form noncentral-t | **Monte Carlo** |
| Shift model | additive (implicit, unstated) | **multiplicative (declared)** |
| Power at own floor | 0.7685 | 0.8002 |

Ratio v2/v1 = **1.056×**.

### Independent confirmation

RUN A's calibration sweep located the empirical 80%-power point at **1.06× floor = 23.8%**.
RUN B, using a **different method** (Monte-Carlo root-find rather than a power curve) and
**disjoint seeds**, calibrated to **23.70%**.

Two independent estimates of the same quantity agreeing to within 0.4% is the strongest
evidence in the experiment that the diagnosis was right. P4 was declared directionally in
advance precisely so this could not be claimed after the fact.

## What was corrected, and what was not

**Corrected — exactly one thing.** The MDE solved a power equation for an additive location
shift while being used to reason about a measure redefinition, which is multiplicative and
scales the standard deviation along with the mean. The closed form was abandoned rather than
patched: its failure was an assumption about the *shape* of the change, and a replacement
closed form would have carried a second untested assumption. `l4/2.0.0` solves the MDE by
simulation under a **declared** shift model, so the assumption is now a recorded field
(`shift_model: multiplicative`) instead of an implicit property of an equation.

**Not corrected, by preregistered scope.** The `iid` dependence assumption remains declared and
remains labelled optimistic.

## Descriptive stress against the corrected floor — not a pass criterion

| Model | Null alarm rate | Power at v2 floor |
| --- | --- | --- |
| iid | 0.0515 | 0.8083 |
| ar1 ρ=0.3 | 0.0682 | 0.8125 |
| **ar1 ρ=0.6** | **0.1174** | 0.8428 |
| seasonal | 0.0308 | 0.7865 |

The dependence picture is **unchanged by the correction**, which is the expected result and
confirms the two defects are independent:

- AR(1) still inflates Type I — 11.7% actual against a declared 5% at ρ=0.6 — without degrading
  power. Dependence damage is expensive, not unsafe.
- Seasonality still deflates α to 3.1% and costs power (0.787), leaving the contract
  over-conservative.

Fixing the shift model did not touch either. **A contract can be simultaneously right about the
shape of the change and wrong about the dependence of the series**, and the two miscalibrations
do not cancel.

## Status

**The calibration question is closed.** `artifacts/detection_floor_v2.json` is written and
certified.

Standing limits, unchanged:

1. **External validity is not established.** Certification seeds are held out from calibration
   but draw from the same declared world model. RUN B establishes internal calibration
   stability. Only real archived history tests the model itself — UQ-1's job.
2. **The dependence assumption remains optimistic and uncorrected**, deliberately, and remains
   visible in the artifact.
3. Floor v2 does **not** retroactively change RUN A. RUN A is frozen at `exp1-runA-final` and
   its results stand as measured against v1.
