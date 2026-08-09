# Workorder Amendment 003 — Warranted Procedures, Frozen Terminology, Split Runs

**Amends:** [amendment 001](workorder_amendment_001.md), [amendment 002](workorder_amendment_002.md), base workorder.
**Status:** **Conceptual amendments closed.** Next information comes from Experiment 1, not from further architecture.
**Date:** 2026-08-09

---

## C1. Three states, frozen

Terminology is fixed here to stop it hardening incorrectly.

```text
WORLD STATE          Does this procedure actually still describe the source?
EVIDENCE STATE       How strongly can we establish that?
AUTHORIZATION STATE  Are we willing to let it run unattended?
```

These are independent. A procedure can remain perfectly correct while its evidence expires;
evidence can look excellent while the procedure has silently become wrong.

### C1.1 Correction to amendment 002 B2.1

**Superseded wording:** *"A model can lose applicability without the source changing at all."*

That sentence asserts a change in world state on the basis of a change in evidence state. It is
wrong, and wrong in the direction that matters.

**Correct wording:**

> **Authorization to rely on a model can expire without evidence of source change.**

Variance contamination degrades the **evidence state**. The world state may be entirely
stationary. What we lose is the warrant to assert applicability, not applicability itself.

**Why this is load-bearing rather than fussy:** when agents are eventually allowed to propose
contracts, they must not be permitted to convert *"we no longer know"* into *"the schema
changed."* The second is a claim about the provider; the first is a claim about us. An agent
that blurs them will generate false drift reports, and false drift reports are how a modelling
plane earns distrust and gets bypassed.

Name for the phenomenon, to be used in the experiment: **epistemic decay in the contract** —
explicitly not drift in the source.

## C2. Authorization state machine

```text
APPLICABLE + WELL-EVIDENCED      -> autonomous execution
POSSIBLY APPLICABLE + STALE      -> re-anchor required
OBSERVED MISMATCH                -> modelling escalation
SEMANTIC STATUS UNDECIDABLE      -> external evidence / human gate
```

Each state has a distinct owner and a distinct remedy. Collapsing any two of them destroys
information — most damagingly, collapsing *stale* into *mismatch*, which manufactures phantom
source changes out of our own epistemic decay.

## C3. `safety_factor: 1.5` withdrawn

**Challenge accepted.** It was my addition and it reproduced the error it was meant to fix one
level up: a policy number wearing statistical clothing.

```text
"95% confidence"     looked rigorous  -> was incomplete
"safety factor 1.5"  looks conservative -> conservative against what?
```

**Replaced by:** make the dependence assumption itself part of the falsification.

```yaml
baseline_model: iid                    # floor is calibrated under this
stress_models:
  - ar1_rho_0.3
  - ar1_rho_0.6
  - seasonal_component
```

**Question measured:** given a floor calibrated under the declared baseline assumption, how far
does the claimed 80% detection power degrade when the dependence assumption is wrong?

This produces an **empirical misspecification correction** rather than blessing a constant. A
`safety_factor` may return later as operator policy — but only once its coverage is known, i.e.
once we can say which range of model misspecification it actually absorbs.

## C4. Split calibration from certification

The 0.1×–4× sweep yields the empirical power curve (`shift / claimed_floor` → `P(alarm)`), which
is what we want. It must not be used to both correct the floor and certify the correction.

```text
RUN A  — calibration / falsification
         Does the claimed floor correspond to ~80% power?
         If not: the claim fails. Preserve the result. Do not repair in place.

RUN B  — separately preregistered
         New baseline, new seeds, held-out histories, corrected method.
         Test the revised floor.
```

Otherwise the conclusion is *"our empirical floor was exactly where our empirical experiment
reached 80% power"* — true by construction, and not a test.

The git-commit-ordering rule from B6.2 already blocks most of this. Independent random seeds and
held-out histories close the remaining gap.

### C4.1 Honest limit of RUN B under synthetic data

Worth recording rather than designing around: with a synthetic corpus, "held-out" means new
seeds from the **same generator**. That tests estimator stability, not model correctness. If the
generator's assumptions are wrong in the same way the floor's assumptions are wrong, RUN B will
certify the error.

Only real archived provider history breaks that circle. This is a second, independent argument
for the **UQ-1 retrospective audit**, which was already the highest-value non-software action.

## C5. Evidence claims — target shape recorded, not yet built

Decay rates differ, and so do decay *mechanisms*:

| Claim | Decay behaviour |
| --- | --- |
| `NetAmount excludes VAT` | Valid for years, then invalid **instantly** on an ERP configuration change |
| `July total matches the ledger` | Near-perfect for July, tells you almost nothing about December |
| `these columns represent invoice lines` | Valid until a format release changes the export |

A generic staleness counter cannot express "valid indefinitely until a discrete event."
Eventually each evidence claim wants:

```yaml
claim:
source:
established_at:
scope:                # temporal, structural, or unconditional
expiry_rule:          # periodic decay | event-triggered | until-superseded
superseded_by:
```

**Not built for Experiment 1.** The per-dimension `established` + `staleness_tolerance_periods`
from B3 is sufficient. Recorded here so the richer shape is not rediscovered from scratch.

## C6. Calibration has two failure directions — paired metric

```text
floor too optimistic  -> unsafe autonomous reliance
floor too pessimistic -> unnecessary escalation / cost
```

Consequence worth stating plainly, because it inverts an intuition:

> **S-invisible being detected consistently is not necessarily good news.**

It indicates the contract may be over-pessimistic, and therefore expensive — needless
re-anchoring and needless human interventions. Both directions must be reported as a pair; a
single-sided "detection rate" would reward exactly the wrong behaviour.

## C7. The artifact is renamed: **warranted procedure**

It is not a schema validator.

```text
WARRANTED PROCEDURE

  PROCEDURE            what to do
  APPLICABILITY CLAIM  when we believe it describes the source
  DETECTION CAPABILITY which changes our evidence can reasonably expose
  EVIDENCE             why we currently trust those claims
  EXPIRY               when the evidence is no longer sufficient
  UNDECIDABLE REGION   what this machinery cannot establish
```

Execution asks: **does this procedure currently have sufficient warrant for autonomous use?**
Not: *does the Excel match the schema?*

This also constrains the eventual agent task usefully. An agent is not asked to "build a
schema." It is asked to propose **a procedure, the claims under which it may safely be reused,
and the evidence for those claims** — and the deterministic harness decides whether those claims
survive. That is a specifiable task with a checkable output.

## C8. Metric names re-aligned to the frozen terminology

O1 ("false apply: procedure runs when it shouldn't") now spans two different failures with
different owners. Under C1 they separate:

| Metric | Definition | Owner |
| --- | --- | --- |
| **O1a — unwarranted execution** | Procedure ran while warrant was absent or expired | **System failure.** Authorization logic is wrong |
| **O1b — warranted but wrong** | Procedure ran with valid warrant; world state had changed undetectably | **Not a system failure.** This is the undecidable region manifesting — the N1 boundary, and it is what O4 exists to characterise |

Keeping these fused would blame the system for N1, which would in turn create pressure to "fix"
an epistemic limit by tightening thresholds — the exact failure mode C6 warns about.

O2–O5 are unchanged. O3 (detectable-drift miss) remains a genuine system failure, because the
change was above the *declared* floor.

---

## Status

**Conceptual amendments are closed.** Further architecture before measurement would be
designing answers ahead of evidence.

Two things are authorized and nothing else:

1. **Experiment 1** as scoped in [experiment_001_drift_discrimination.md](experiment_001_drift_discrimination.md), amended by C3, C4, C6, C8.
2. **The UQ-1 retrospective audit** — now doubly motivated (C4.1).

---

## Changes to prior deliverables

| Document | Change |
| --- | --- |
| `research_agentic_data_task_modelling.md` | B2.1 wording corrected (C1.1); warranted-procedure definition; authorization state machine |
| `experiment_001_drift_discrimination.md` | `safety_factor` withdrawn for stress models; RUN A / RUN B split; O1a/O1b; paired calibration metric |
| `falsification_ledger.md` | N1 consequence 5 reworded to distinguish evidence state from world state |
| `README.md` | Warranted procedure; three states; authorization state machine |
