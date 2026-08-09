# Workorder Amendment 002 — Detection Power, Evidence Dimensions, Preregistration

**Amends:** [workorder_amendment_001.md](workorder_amendment_001.md) and the base workorder.
**Status:** Research amended. Build authorization: Experiment 1 only, as scoped in §B6.
**Date:** 2026-08-09

---

## B1. The detection floor requires power, not just confidence

**Correction accepted.** `min_detectable_shift_pct: 3.2, confidence: 0.95` is under-specified
and reads as more definite than it is. Confidence bounds Type I error; a detection floor is a
statement about **Type II** error — the probability of *missing* a real shift. Stating α while
using the result to justify "we would have caught this" bounds the wrong error.

Amended contract field:

```yaml
L4_detection_floor:
  period_total:
    statistic: monthly_total
    test: <declared test>              # must be named, not implied
    baseline_window: 12
    min_detectable_shift_pct: 3.2
    alpha: 0.05                        # Type I
    power: 0.80                        # 1 - Type II
    variance_basis: independently_anchored_periods
    independence_assumed: true         # see B2 — must be visible
    seasonality_model: none            # first experiment only
```

The permitted claim becomes exactly:

> Given this baseline, this test and this power requirement, changes smaller than ~3.2% are not
> reliably distinguishable from normal variation.

Not "we are 95% confident nothing changed."

## B2. The independence assumption biases the floor in the unsafe direction

Business monthly series are seasonal and autocorrelated. Treating 12 monthly observations as
i.i.d. **overstates effective sample size and understates variance**, which makes the computed
floor *smaller* than the true floor.

That is the dangerous direction. The floor is used to conclude "a shift of this size would have
been detected, therefore absence of an alarm is evidence." An optimistic floor turns that into a
false assurance — precisely the failure N1 exists to prevent.

Sophisticated time-series modelling is out of scope for Experiment 1. Three requirements are
not:

1. `independence_assumed: true` is recorded in the contract, so the optimism is visible rather
   than implicit.
2. The reported floor carries a declared **safety factor** (start at 1.5×) until the assumption
   is relaxed, and the factor is named in the contract rather than folded silently into the
   number.
3. Experiment 1's results memo states the direction of the bias explicitly, so nobody later
   reads a naive floor as conservative.

### B2.1 The floor is not a constant — it degrades as the anchor ages

A consequence of `variance_basis` worth making explicit, because it was not obvious.

If variance is estimated from procedure-generated (unanchored) history, the baseline may itself
contain undetected drift. For a sustained sub-floor change (S-creep) the contamination is
*monotone*, which inflates the variance estimate, which **widens the floor** — so detection
capability quietly decays exactly when drift is present.

Therefore:

> **Detection capability is a function of anchor freshness.**
> `min_detectable_shift_pct` should be reported alongside `periods_since_independent_anchor`,
> and re-computed rather than cached when the anchor ages.

This gives evidence expiry (B5, reason 3) a measurable statistical consequence rather than only
a policy justification. It also means a model can lose applicability *without the source
changing at all* — which is a genuinely counter-intuitive property and worth stating in the
contract documentation.

## B3. Evidence dimensions, not tiers

**Correction accepted.** T0–T3 implies an order. The relation demonstrated is not ordered:

- A human can confirm *"Revenue means product revenue excluding freight"* and never notice that
  3% of rows vanished.
- Reconciliation can prove *"the total agrees with the ledger"* while establishing nothing about
  what was included in that total.

Those are orthogonal. Replacing the tier ladder with an **evidence vector**:

```yaml
evidence:
  semantic_meaning:
    source: human_confirmation
    strength: <declared>
    established: 2025-11-03
    staleness_tolerance_periods: 24        # meaning is slow-moving

  aggregate_correctness:
    source: independent_reconciliation
    strength: <declared>
    established: 2026-02-28
    staleness_tolerance_periods: 6         # totals stale fast

  structural_fit:
    source: deterministic_validation
    strength: <declared>
    established: 2026-08-01
    staleness_tolerance_periods: 1         # re-established every run

  freshness:
    periods_since_independent_anchor: 4
```

### B3.1 Freshness is per-dimension, not global

One refinement on the proposed shape. `freshness` is not a fourth dimension of the same kind as
the other three — it is a **decay applied to each of them**, and the decay rates differ by more
than an order of magnitude. A semantic confirmation from 18 months ago is still fairly good
evidence about what a measure *means*. A reconciliation from 18 months ago is nearly worthless
evidence about whether *this month's* total is right.

So each dimension carries its own `established` date and `staleness_tolerance_periods`. The
global `periods_since_independent_anchor` is retained as the headline number for operators, but
the per-dimension values are what the escalation logic reads.

## B4. Definition of a published task model

Adopted as stated, with the amendments above folded in:

```text
PUBLISHED TASK MODEL

  executable procedure
+ applicability contract              (L0-L5)
+ statistical detection capability    (floor, with alpha, power, variance basis, assumptions)
+ evidence vector                     (semantic / aggregate / structural, each dated)
+ anchor freshness                    (per-dimension staleness)
+ known undecidable assumptions       (L5 semantic assertions, explicitly not checkable)
```

The last component is the one that distinguishes this from "schema memory." A published model
that cannot enumerate what it *cannot* establish is making an implicit claim of completeness it
has no basis for.

## B5. Three escalation reasons

Adopted verbatim, because the third is the one ordinary monitoring architectures miss:

| # | Reason | Trigger | Character |
| --- | --- | --- | --- |
| 1 | **Observed mismatch** | L0–L4 predicate fails | Something looks wrong |
| 2 | **Epistemic insufficiency** | Question falls below the declared detection floor; or two semantic readings survive the evidence | We cannot know from this data |
| 3 | **Evidence expiry** | A dimension's `staleness_tolerance_periods` exceeded | **Nothing looks wrong** |

Reason 3 must be a **distinct, first-class terminal state**, not a failure:

```text
VALIDATION PASSES
APPLICABILITY APPEARS VALID
EVIDENCE TOO STALE
  -> RE-ANCHOR REQUIRED
```

Everything green, everything structurally valid, all statistics normal, and correctness has not
been independently established for 18 months. That is a legitimate and *actionable* state, and
conflating it with either "pass" or "fail" destroys the information.

This is the architectural move that makes the whole system defensible. It changes the goal from
**detect every meaningful change** — which N1 says is impossible — to:

> detect what we can, explicitly bound what we cannot detect, and periodically obtain
> independent evidence before self-generated history becomes circular.

## B6. Experiment 1, final scope and preregistration

```text
frozen synthetic history
       |
published deterministic procedure
       |
applicability checks L0-L4
       |
evidence / anchor model
       |
controlled source changes
       |
measure outcomes
```

**No agents. No LLM.**

### B6.1 Preregistered outcomes

| # | Outcome | Definition |
| --- | --- | --- |
| **O1** | **False apply** | Procedure runs when it should not |
| **O2** | **False escalation** | Applicable procedure rejected or escalated |
| **O3** | **Detectable-drift miss** | Change *above* the declared L4 floor that did not trigger |
| **O4** | **Correct undecidability** | Change *below* declared detection capability, and the system correctly does not claim semantic continuity |
| **O5** | **Anchor expiry** | Measured separately: does the system eventually demand external evidence while all automatic applicability checks continue to pass? |

O4 is the unusual one: **a miss counted as a correct result.** It is only valid because the
inability was declared before the result was seen — so the declaration order has to be
mechanically verifiable, not asserted.

### B6.2 Preregistration protocol (makes O4 honest)

1. Compute the detection floor from the frozen baseline **only**.
2. Commit the floor to git as its own commit, before the drift corpus exists.
3. Generate corpus variants *relative to the committed floor* — S-invisible at ≈0.15× floor,
   S-obvious at ≈2.5× floor — so "invisible" and "obvious" are defined rather than guessed.
4. Run the harness. Do not adjust the floor afterwards. Any post-hoc change to the floor
   invalidates O3 and O4 and must be reported as a separate, re-preregistered run.

The git commit ordering is the integrity mechanism. It is cheap and it is checkable by anyone
reading the history later.

### B6.3 Added measurement — floor calibration error

The named trio (S-obvious / S-invisible / S-creep) are the preregistered anchors and their
asymmetry is preserved exactly as specified. One addition makes the floor claim itself testable
rather than merely applied.

Sweep shift magnitudes across ≈0.1× to 4× the declared floor and locate the **empirical
80%-power point**. Compare to the declared floor.

| Result | Meaning |
| --- | --- |
| Empirical point ≈ declared floor | The floor claim is calibrated. It can be published |
| Shift at 2.5× floor missed | Floor is **overstated** — the contract claims detection power it does not have. Unsafe direction |
| Shift at 0.15× floor caught reliably | Floor is **understated** — needlessly conservative, causing avoidable human escalation |

This reframes the semantic variants usefully: they are not a test of whether the detector works,
they are a **calibration test of the floor claim**. Both directions of miscalibration are
informative failures of the *claim*, not of the detector — which is the correct place to locate
the error.

---

## Changes to prior deliverables

| Document | Change |
| --- | --- |
| `experiment_001_drift_discrimination.md` | Floor spec (α/power/variance basis), preregistration protocol, O1–O5, calibration sweep, evidence vector |
| `research_agentic_data_task_modelling.md` | §5 floor spec, §7 evidence dimensions replacing tiers, §8 three escalation reasons |
| `falsification_ledger.md` | N1 operational consequences updated for power and floor decay |
| `README.md` | Published task model definition, three escalation reasons |

`workorder_amendment_001.md` §A3.1 and §A5 are superseded by B1–B3 respectively and are
retained for legibility of the correction.
