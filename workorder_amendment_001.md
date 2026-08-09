# Workorder Amendment 001 — Applicability, Evidence and the Semantic Non-Claim

**Amends:** Research Workorder — Agentic Data Task Modelling (2026-08-09)
**Status:** Research amended. Build authorization: Experiment 1 only.
**Date:** 2026-08-09

This amendment records five corrections arising from review of the research return. Two of
them (A1, A4) change what the system is allowed to *claim*, which is more consequential than
changing what it does.

---

## A1. The problem is restated

**Was:** can an isolated agentic modelling network infer a reusable executable data-task model?

**Now:** *deciding when a learned procedure is allowed to run again* is the research object.
Inferring the procedure is established prior art.

Amended lifecycle:

```text
MODELLING
   ↓
candidate procedure
   ↓
VERIFICATION
   ↓
published procedure + applicability contract
   ↓
future input
   ↓
APPLICABILITY CHECK
   ├── match             → deterministic work
   └── mismatch/unknown  → escalation
```

The `Data-tool` D1 defect is the argument in miniature: inserting one column shifts every
positional mapping while the pipeline exits successfully. A reusable procedure that cannot
independently establish that the incoming source is still the thing it thinks it is, is not a
task model. It is a loaded gun with a clean exit code.

---

## A2. L4 is renamed, and its claim is narrowed

**Was:** `L4_statistical` — described in the report as the "only automatic semantic-drift
signal."

**Now:** **`L4 — statistical evidence relevant to applicability`.**

Statistical monitoring can produce *evidence that something changed*. It cannot establish that
*meaning stayed the same*. The report conflated the two, and the phrase "semantic drift
detection" overstated what the method can deliver. Corrected throughout.

---

## A3. New falsifiable non-claim, N1

> **N1 — Structural and statistical agreement cannot prove semantic continuity.**
>
> Some semantic changes are observationally indistinguishable from the available data. Where
> the magnitude of a definitional change falls below the natural variation of the measure, no
> amount of structural or statistical checking will separate it from a normal period.

N1 is stated as a **non-claim the architecture must never violate**, not as a caveat. Its
operational consequences:

1. **The system may never output "semantically unchanged."** The strongest permitted statement
   is *"no evidence of change, at detection floor X."*
2. External metadata, contractual meaning, or a human gate is **structurally necessary**, not
   a fallback for immature automation. No future improvement in modelling removes it.
3. N1 is falsifiable in the useful direction: it would be refuted by a method that reliably
   separates definitional change from normal variation using only the delivered data. If
   someone demonstrates that, the architecture simplifies considerably.

### A3.1 The detection floor becomes a published property

N1 is more useful as a **number than as a disclaimer.** Given the historical variance of a
measure, it is computable what size of definitional shift L4 would catch at a stated
confidence. Every published applicability contract should therefore carry:

```jsonc
"L4_detection_floor": {
  "period_total": { "min_detectable_shift_pct": 3.2, "confidence": 0.95, "baseline_periods": 14 },
  "note": "Shifts below this are indistinguishable from normal variation."
}
```

This converts an unanswerable question into an answerable one. "Could freight have been folded
into this measure?" becomes: *"freight is ~0.4% of revenue for this provider, which is below
our 3.2% detection floor. We cannot tell from the data. Only external evidence can settle it."*

That is a far better answer than either "no drift detected" (false comfort) or "we can never
know" (useless).

---

## A4. The memory object is a triple, not a mapping file

**Was (implicit):** memory = published schema/mapping.

**Now:**

```text
MEMORY OBJECT =
      executable procedure
    + applicability contract
    + evidence / history
```

At 2,000-company scale you do not retrieve company 947's conversation. You retrieve a versioned
model that states: *I know how to process this source when these conditions hold, and here is
the evidence supporting that claim.*

The third element is what the survey found missing everywhere. Without it the contract is an
assertion; with it the contract is auditable and its confidence is inspectable.

---

## A5. Evidence provenance tiers, and the self-certification guard

UQ-10 is promoted from an open question to a **design constraint**. Historical agreement is
evidence only to the extent the historical result is independently trustworthy. Otherwise:

```text
wrong model → wrong output → output becomes memory
           → future wrong model matches memory → "verified"
```

Baselines must therefore be tiered by provenance:

| Tier | Source | Strong on | Blind to |
| --- | --- | --- | --- |
| **T0** | Procedure-generated, unreviewed | Nothing — self-referential | Everything |
| **T1** | Procedure-generated, passed declared invariants | Internal consistency | Any error the invariants don't encode |
| **T2** | Independently reconciled against an external artifact (provider's stated period total, ERP control total, settlement/payment figure) | **Aggregate correctness** | **Meaning** — a total can reconcile while the definition shifted, if the shift is small |
| **T3** | Human-confirmed against business meaning | **Meaning** | **Coverage** — a human checks samples, not populations |

**The critical point: these are not one ranking.** T2 and T3 are strong on *different axes* and
each is blind where the other is strong. A baseline needs both to be trustworthy, and must
record which axis it is strong on. Treating them as interchangeable recreates the fake-certainty
loop in a more sophisticated form.

### A5.1 Reconciliation freshness

A cheap, checkable guard follows directly. If period N was T2-reconciled and periods N+1…N+6
were T0, the trailing baseline is almost entirely self-generated regardless of how many periods
it spans. Each applicability contract should therefore carry:

```jsonc
"baseline_provenance": {
  "periods_in_baseline": 14,
  "highest_tier_in_baseline": "T2",
  "periods_since_independent_anchor": 6,
  "max_periods_since_anchor": 12          // exceed -> escalate for re-anchoring
}
```

Exceeding `max_periods_since_anchor` is an escalation trigger *even when nothing has drifted*.
This is the only mechanism found in the whole study that breaks the self-certification loop
without external supervision on every period.

---

## A6. Revised sequence

The modelling network is no longer next.

```text
1. Amend research WO                                    ← this document
   ↓
2. Define applicability levels (L0-L5) + evidence tiers
   ↓
3. Build deterministic drift corpus
   ↓
4. Measure false-apply / false-escalate
   ↓
5. Determine what applicability evidence is actually useful
   ↓
6. THEN give agents the job of producing
   procedures + applicability claims + backing evidence
```

The reason step 6 comes last is precise: **before step 5, "build a schema" is an
underspecified instruction.** After step 5 the agent's output contract is known — it must
produce a procedure, an applicability contract, and the evidence backing each clause of that
contract, at a stated evidence tier. That is a specifiable task. "Build a schema" is not.

---

## A7. Corpus requirement — both semantic variants are mandatory

Amends [experiment_001_drift_discrimination.md](experiment_001_drift_discrimination.md) §3.2.
The drift corpus must contain **at least two semantic changes with opposite detectability**:

| Variant | Construction | Expected result |
| --- | --- | --- |
| **S-obvious** | `Summa` redefined to include freight where freight ≈ 8% of revenue — well above period-to-period variation | L4 escalates. Establishes L4 has non-zero power |
| **S-invisible** | `Summa` redefined to include freight where freight ≈ 0.4% of revenue — below the noise floor | **L4 does not escalate. This is the correct result and must be reported as a success of the experiment design, not a failure of the method** |

Without S-invisible, the experiment risks "solving" semantic drift by constructing only
convenient examples. S-invisible is the variant that measures N1 rather than assuming it, and it
is what calibrates the published detection floor (A3.1).

A third variant is worth including: **S-invisible-then-obvious** — the same 0.4% redefinition,
but sustained across six periods so cumulative divergence from an external anchor becomes
detectable while per-period divergence never does. This tests whether reconciliation freshness
(A5.1) catches what per-period L4 cannot.

---

## A8. Empirical priority unchanged, reasoning sharpened

UQ-1 (retrospective classification of archived provider deliveries) remains the highest-value
non-software action. The amended reason:

- If ~95% of monthly files are cosmetically different and semantically stable, the architecture
  is L0–L2 plus a synonym store, and most of this machinery is unjustified.
- If suppliers routinely change accounting packages, grain and meanings, then L3–L5, evidence
  tiers and the human gate are the product, and the deterministic work plane is the easy part.

These are different systems. The distribution decides which one is worth building, and it is
obtainable from files you already hold.

---

## Changes to prior deliverables

| Document | Change |
| --- | --- |
| `research_agentic_data_task_modelling.md` | §0, §5 (L4 rename + detection floor), §6 (N1), §7 (evidence tiers), §13 (revised sequence) |
| `experiment_001_drift_discrimination.md` | §3.1 L4 rename, §3.2 mandatory semantic variants, §4 detection-floor measurement, §5 decision rules |
| `falsification_ledger.md` | N1 added as a stated non-claim |
| `unanswered_questions.md` | UQ-10 promoted to design constraint (A5); UQ-6 reframed |
| `README.md` | Revised sequence, amended decision |

Superseded framing is struck rather than deleted, so the correction remains legible.
