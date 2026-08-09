# Experiment 1 — Result

**Status: closed for RUN A.** RUN B (separately preregistered certification) not run.
No value-level identity predicate implemented — that decision is deliberately deferred.

Floor committed `a038a2e` before any drift existed and **never refitted**. All results below are
measured against that number.

| | |
| --- | --- |
| Declared single-period floor | **22.44%** of period total |
| Declared sustained (k=6) floor | **10.78%** |
| α / power / assumption | 0.05 / 0.80 / iid |
| Baseline | 12 periods, CV 7.0%, sha256 `1f2575be…` |

---

## 1. Preregistered outcomes

| Metric | Result | Reading |
| --- | --- | --- |
| **O1a** unwarranted execution | **0** | Engine never authorized while a dimension was stale, across both expiry scenarios |
| **O1b** warranted but wrong, **below** capability | **7** | `SEM_invisible` 1/1, `SEM_creep` 6/12. Excused by the declared floor |
| **O1c** warranted but wrong, **not** below capability | **22** | `COS_case_whitespace`, `COS_period_format`. **Genuine contract gap** |
| **O2** false escalation on controls | **0.0833** | 1 of 12 unchanged periods (16.19%, p≈0.048). A real Type I error at α |
| **O3** detectable-drift miss | **0** | Nothing above the declared floor escaped |
| **O4** correct undecidability | **7** | Same events as O1b, judged on conduct: never claimed continuity |
| **O5** expiry while all checks pass | **5 of 5** | First at 2025-08, anchor age 7 vs tolerance 6 |
| N1 guard | **passed, 168/168** | `semantic_status` never left `not_established` |

Taxonomy correction recorded separately in
[o1_taxonomy_correction.md](o1_taxonomy_correction.md). RUN A numbers unchanged.

---

## 2. Structural discrimination: complete

5/5 variants, 12/12 periods, correct level attribution in every case.

| Variant | Escalated | First failing level |
| --- | --- | --- |
| `STR_insert_column` (D1 trap) | 12/12 | L1 |
| `STR_wide` | 12/12 | L1 |
| `STR_drop_column` | 12/12 | L1 |
| `STR_header_offset` | 12/12 | L1 |
| **`STR_grain_split`** | **12/12** | **L3** |

`STR_grain_split` is the load-bearing result. It preserves the period total **exactly**, so
every statistical predicate passes. It is caught *only* because L3 declares a uniqueness key.

> **Grain declaration is not optional.** Without it, a grain change is authorized silently and
> the error is a multiplication of the measure — the highest-consequence undetected failure in
> the whole design.

---

## 3. Floor calibration — the claim is ~6% optimistic, and the cause is identifiable

Sweep: 0.1×–4× the declared floor, 6,000 trials per point, deployed procedure (mean and sd
re-estimated from each replicate's own baseline window).

| Model | Null alarm rate | α inflation | Power at declared floor | 80% power reached at |
| --- | --- | --- | --- | --- |
| **iid** (the declared assumption) | 0.0562 | 1.12× | **0.7685** | 1.06× floor = **23.8%** |
| ar1_ρ=0.3 | 0.0680 | 1.36× | 0.7863 | 1.03× floor = 23.1% |
| **ar1_ρ=0.6** | **0.1200** | **2.40×** | 0.8047 | 0.99× floor = 22.3% |
| seasonal | 0.0310 | 0.62× | 0.7478 | 1.09× floor = **24.5%** |

**Even in its own assumed world the floor is slightly optimistic**: 22.44% delivers 76.9% power,
not 80%; 23.8% is needed. The cause is specific and worth recording rather than absorbing into a
fudge factor:

> The floor formula assumes an **additive location shift**. A measure redefinition is
> **multiplicative** — folding freight into `amount` scales the mean *and* the standard
> deviation. The inflated variance costs power that an additive model does not predict.

This is a modelling error in the claim, not noise, and it is exactly the kind of thing the
calibration sweep exists to find. It is small (~6%) and it errs in the unsafe direction.

### Misspecification lands on Type I, not on power

Amendment B2 predicted the iid assumption would make the true floor *larger*. Confirmed for the
seasonal case (1.09×), and marginally for iid-with-multiplicative-shift (1.06×). For AR(1) the
prediction is **wrong in an instructive way**:

- Serial correlation makes a short baseline window *understate* the marginal sd. The test
  becomes trigger-happy in **both** directions.
- At ρ=0.6 the actual false-alarm rate is **12% against a declared 5%** — the contract misstates
  its own α by 2.4×. Power at the floor is *not* degraded (0.805).
- So dependence damage is **expensive, not unsafe**: a flood of false escalations rather than
  missed drift.
- Seasonality does the opposite — it *inflates* the baseline sd estimate, deflating α to 0.031
  and cutting power to 0.748. Here the contract is over-conservative and the true floor is
  larger than declared.

Both directions of the paired metric (C6) are therefore observed in one experiment, in different
worlds. Neither would be visible from a single-sided detection rate.

---

## 4. N1 confirmed empirically

`SEM_invisible` — a 3.37% measure redefinition, structurally identical, 0.15× the declared
floor — **was not detected, and the system did not claim it was unchanged.** It reported
"no evidence of change at floor 22.44%".

This was declared before the corpus existed (`a038a2e` precedes the corpus commit), which is the
only thing that makes the miss interpretable as a correct result rather than a failure.

Worth noting: the generator's natural freight share is **3.09%** — arrived at independently of
the floor. The realistic "freight got folded into the measure" event sits below the detection
floor *by construction of the world*, not by the experimenter's choice of magnitude.

### `SEM_creep` — confounded, reported as such

Escalated 6/12 (4 via the sustained test). **This is not evidence that the sustained test catches
sub-floor creep.** The unchanged held-out periods already sit **+4.76%** above the baseline mean
by chance:

| | sustained shift range | sustained alarms |
| --- | --- | --- |
| `C0_unchanged` | −0.69% … +6.26% | **0/12** |
| `SEM_creep` | −0.11% … +9.64% | 4/12 |

The injected creep is 3.37%, far below the 10.78% sustained floor. It crosses only by riding on
a pre-existing baseline/hold-out offset. **On its own it would not be detected.**

Per the decision rules, this triggers the branch: *sustained sub-floor drift is undetectable
without periodic external anchoring — independent re-anchoring becomes a scheduled obligation,
not a trigger.* A recurring business cost, accepted knowingly.

---

## 5. Evidence expiry works, and does not latch

| Scenario | Behaviour |
| --- | --- |
| **no_reanchor** | Authorization stops at anchor age 7 (tolerance 6) and stays stopped for 5 periods. `automatic_checks_pass = True` throughout |
| **reanchor** | Operator supplies fresh independent evidence at 2025-08; authorization resumes immediately and continues |

```
VALIDATION PASSES
APPLICABILITY VALID
EVIDENCE TOO STALE   -> RE_ANCHOR REQUIRED
```

Five consecutive periods in which every structural, typing, grain and statistical check passes
and autonomous execution is nonetheless withheld. That state exists, is reachable, is
distinguishable from both pass and fail, and clears on re-anchoring rather than latching.

O1a = 0 in both scenarios: the engine never authorized while any dimension was stale.

---

## 6. The defect found: value-level identity drift (O1c = 22)

`COS_case_whitespace` (`ART-0001` → `  art-0001 `) and `COS_period_format`
(`2025-07` → `07/2025`) are **authorized**, and should not be.

- Structure unchanged → L1 passes.
- dtype, null rate, **cardinality** unchanged → L2 passes. A case fold does not change cardinality.
- Key still unique → L3 passes.
- Period total identical, 0.00% shift → L4 sees nothing, and the floor is irrelevant.

Downstream this yields 150 phantom articles or an unjoinable period label. **The contract has no
predicate over the *values* of identity columns.** This is O1c, not O1b: it is not excused by the
detection floor, because no declared capability ever addressed it.

Per instruction, **no predicate has been implemented.** Whether this warrants Experiment 2 or a
contract amendment is decided after this document, not inside it.

---

## 7. Decision rules, evaluated against §5 of the protocol

| Preregistered rule | Outcome |
| --- | --- |
| Structural detection ≥90%, attribution ≥80% | **Met** — 100% / 100% |
| Cosmetic self-heal ≥50% | **Not evaluable.** No self-heal was implemented; the harness escalates on rename rather than resolving it. Recorded as not-tested, not as failed |
| Grain change missed → L3 mandatory | **Grain was caught**, and only by L3. Confirms L3 must be mandatory |
| L4 catches S-obvious at tolerable false escalation | **Met** — caught 1/1; O2 = 0.083 on controls, under the 15% threshold |
| L4 misses S-invisible | **Met, as predicted.** N1 confirmed empirically |
| L4 catches S-invisible → investigate | Did not occur for the single-period test |
| Reconciliation freshness catches S-creep | **Not met.** Detection was confounded; re-anchoring becomes a scheduled obligation |
| Detection poor across the board → STOP | **Not triggered** |

**Overall: the harness discriminates as designed, and the two things it cannot do are now
quantified rather than argued.**

---

## 8. What this establishes for the architecture

1. **Declared applicability discriminates structural drift completely** — including the case
   that preserves every aggregate, provided grain is declared.
2. **The undecidable region is real and measurable.** A published floor turns "we cannot know"
   into "we cannot resolve below 22.44% at 80% power", and the number is auditable.
3. **A published floor can itself be miscalibrated**, in either direction, and only a sweep
   finds it. A contract that states α and power without ever testing them is asserting, not
   measuring.
4. **Dependence assumptions cost false escalations before they cost detection.** The expensive
   failure arrives first, which is the survivable ordering.
5. **Evidence expiry is a viable distinct state**, and it is the only mechanism observed here
   that addresses sub-floor creep.
6. **Predicate coverage is a separate failure mode from detection power** — O1c exists, is not
   excusable by N1, and would have been mislabelled as an epistemic limit under the two-way
   taxonomy.

---

## 9. Not done

| Item | Status |
| --- | --- |
| RUN B (separately preregistered certification, new seeds, held-out histories) | Not run. Required before the corrected floor may be published |
| Value-level identity predicate | **Deliberately not implemented** |
| Experiment 2 / contract amendment decision on the identity gap | Deferred until after this document |
| UQ-1 retrospective audit | Not started. Independent of this experiment by the contamination rule |

RUN B's honest limit stands ([C4.1](../workorder_amendment_003.md)): with a synthetic corpus,
"held-out" means new seeds from the same generator, which tests estimator stability rather than
model correctness. Only real archived history breaks that circle.
