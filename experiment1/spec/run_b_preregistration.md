# RUN B — Preregistration

**Committed before `run_b.py` exists.** The commit ordering is the integrity mechanism
([B6.2](../workorder_amendment_002.md), [C4](../workorder_amendment_003.md)).

Supersedes nothing. RUN A is frozen at tag `exp1-runA-final`; this run produces a **new**
floor version and does not edit v1.

---

## 1. The defect being corrected — exactly one

RUN A measured empirical power of **0.7685** at a declared floor of 22.4367%, against a declared
0.80. The cause is identified and specific:

> `min_detectable_shift_pct` solves a noncentral-t power equation for an **additive location
> shift**. The event it is used to reason about — a measure redefinition — is **multiplicative**.
> Folding freight into `amount` scales the mean *and* the standard deviation. Under a
> multiplicative shift δ the test numerator has variance σ²[(1+δ)² + 1/n], not σ²[1 + 1/n], and
> the extra variance costs power the additive model does not predict.

**Scope is limited to this.** Explicitly **not** corrected in RUN B:

- The `iid` dependence assumption stays declared as `iid` and stays labelled optimistic.
  Correcting it would change what the contract claims about the world, not fix an error in how
  it computes what it claims, and would confound the certification.
- No new predicate levels. No identity-value predicate. No change to L1–L5.
- No change to α (0.05), power (0.80), baseline window (12) or sustained window (6).

## 2. Corrected method — declared now

**`l4/2.0.0` — Monte-Carlo minimum detectable effect under a declared shift model.**

The closed form is abandoned rather than patched. Its failure was an assumption about the
*shape* of the change, and a second closed form would carry a second untested assumption.

```
floor(model, shift_model, alpha, power, mu, sigma, n, k):
    solve for delta such that  P(alarm | delta) = power
    where each trial:
        base  ~ history(model, n)              # dependence model, declared
        x     ~ next_period(model) * (1+delta) # MULTIPLICATIVE shift
        alarm := declared test (t reference, sd re-estimated from base)
    root-find delta by bisection on the simulated alarm rate
```

The floor artifact must additionally record `shift_model: "multiplicative"`,
`mde_method: "monte_carlo"`, `calibration_trials`, and `calibration_seed_family`.

## 3. Seed discipline — calibration and certification are disjoint

| Phase | Seed family | Purpose |
| --- | --- | --- |
| **Calibration** | `seed_family = 700000` | Find δ\* such that simulated power = 0.80 |
| **Certification** | `seed_family = 810000` | Measure power at δ\* and the null alarm rate. **Disjoint from calibration.** |

RUN A's sweep used seed family `90909`; both RUN B families are disjoint from it.

Certification is run in **two baseline regimes**, reported separately:

- **resampled baseline** — a fresh 12-period window per trial. Matches the floor's own
  assumption; measures the method.
- **fixed committed baseline** — the frozen RUN A baseline held constant. Matches deployment;
  measures the procedure as it would actually run.

## 4. Pass criteria — declared before any result is seen

RUN B **passes** only if, on certification seeds:

| # | Criterion | Threshold |
| --- | --- | --- |
| P1 | Empirical power at the corrected floor, resampled baseline | 0.78 ≤ p ≤ 0.82 |
| P2 | Null alarm rate, resampled baseline | 0.04 ≤ a ≤ 0.06 |
| P3 | Empirical power at the corrected floor, fixed committed baseline | 0.75 ≤ p ≤ 0.85 |
| P4 | Corrected floor is **larger** than v1 | δ\* > 22.4367% |

P3 is deliberately wider: with the baseline realisation held fixed, the sd estimate is a single
draw and power is expected to deviate from nominal in whichever direction that draw errs. A
narrow band there would be measuring the luck of one baseline, not the method.

P4 is directional and stated in advance: the identified defect *costs* power, so the corrected
floor must move up. A corrected floor that came out smaller would mean the diagnosis is wrong,
and RUN B would fail even if P1–P3 passed.

## 5. What a failure means, declared now

| Outcome | Consequence |
| --- | --- |
| All of P1–P4 pass | Corrected floor `detection_floor_v2.json` may be published. The calibration question is **closed** |
| P4 fails | The additive/multiplicative diagnosis is wrong. Preserve the result, do **not** adjust, reopen the cause analysis |
| P1 or P2 fails | The Monte-Carlo method is itself miscalibrated. Preserve, do not tune, report the calibration question as **open** |
| P3 fails while P1–P2 pass | The method is sound but the deployed procedure's single fixed baseline is unrepresentative. This is a **finding about baseline windows**, not about the method — report it and keep the floor |

No threshold in §4 may be changed after results are observed. Any change requires a RUN C with
its own preregistration.

## 6. Stress re-measurement — descriptive, not a pass criterion

The AR(1) ρ=0.3 / ρ=0.6 / seasonal stress will be re-run against the **corrected** floor so the
dependence picture is comparable across versions. It is reported for information only and
**cannot cause RUN B to pass or fail**, because the dependence assumption is out of scope (§1).

## 7. Honest limit, restated

[C4.1](../workorder_amendment_003.md) stands. Certification seeds are held out from calibration,
but both draw from the **same declared world model**. RUN B therefore establishes *internal
calibration stability under the assumed world model*. It does not establish external validity.
Only real archived history does that, which is UQ-1's job and not this run's.
