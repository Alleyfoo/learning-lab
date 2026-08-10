# Experiment 3B — Reviewer Policy vs Model Diversity: Preregistration

**Frozen before any run.** Expected answers in `experiment3b/expected.json` (hidden
from every reviewer). Reuses the frozen A1 fixture from Experiment 2B by path, unmodified.

## What 3A left us with

3A's G3 failed with an unusually clean trace: the architecture did not fail downstream.
The failure was born twice upstream — the classifier over-asserted (`Jakso A → not_month`)
and the independent WarrantReviewer endorsed it (`supported`). The orchestrator and the
deterministic gate were not implicated: given `supported`, the gate correctly did not
escalate. The gate's contract is strong enough — had the reviewer returned
`insufficient_evidence`, G3 would have passed.

So the open question is narrow: **why did the reviewer ratify an unwarranted assertion?**

3A's hypothesis was that a fresh, structurally independent reviewer would catch the
classifier's overconfidence. It did not. The likely reason, stated as a hypothesis to test
rather than a conclusion: the reviewer was the **same model** as the specialist, carrying
the same prior ("does not look like a month name → not a month"), so structural
independence (no shared reasoning) did not produce different judgement.

## Terminology (corrected from 3A)

A different model gives **model diversity**, not necessarily epistemic independence. Two
models can share the same intuitive prior. Model diversity is still a legitimate way to
test whether **correlated judgement** is the problem — but it is not a guarantee of
independence, and a result here is read accordingly.

## The principle being tested

> Don't require the intelligent component to never be wrong.
> Require unsupported assertions to fail to acquire authority.

In 3A, `not_month` for `Jakso A` existed as a proposal and immediately became an
authorized fact. The fix may not be "a perfectly calibrated specialist"; it may be a
**different decision standard** sitting between classifications and authority.

## Design: freeze seq 11, test the reviewer in isolation

Before touching the whole G3 chain, isolate the reviewer. One variable changes at a time.

Three propositions, **identical source context** (the A1 rendered rows + header row 4) for
all three:

| # | proposition | expected warrant | role |
| --- | --- | --- | --- |
| C1 | `Tammi = month` | **supported** | positive control, month direction |
| C2 | `Tuote = not_month` | **supported** | positive control, non-month direction |
| T  | `Jakso A = not_month` | **insufficient_evidence** | the target — the 3A failure |

The two controls are essential. A reviewer that rejects everything would pass the target
while being useless. Controls in **both semantic directions** (a real month, and a real
non-month) ensure that passing the target means *discrimination*, not reflexive opposition.

These are exactly three of G3's six propositions: C1 and C2 are the two correct
classifications G3's classifier made and its reviewer endorsed; T is the over-assertion
G3's reviewer wrongly endorsed. Isolating them tests the reviewer policy directly.

---

## Probe 3B.1 — Evidence-burden reviewer, same GLM

**Same model as 3A (GLM-5.2), invoked the same way (fresh isolated agent call). Only the
reviewer's epistemic contract changes.** One variable.

The contract is **not** "try to refute this." That would swing the bias from overconfidence
to reflexive opposition and risk the paranoid-reviewer failure. Instead it states a stricter
**evidence-burden** standard:

```text
Your task is not to decide which classification seems most plausible.

Your task is to determine whether the supplied evidence establishes
the proposed classification.

Return SUPPORTED only when the evidence positively supports the claim.

The absence of evidence that a header is a month is not evidence that
it is not a month.

If the evidence permits both the proposal and a materially different
interpretation, return INSUFFICIENT_EVIDENCE.
```

The line *"the absence of evidence that a header is a month is not evidence that it is not
a month"* is the operative clause for the target: `Jakso A` not looking like a month name
does not establish it is not a month. The same clause must not break the controls —
`Tuote` *is* positively a non-month (it is a product label, and the data rows confirm it),
so the clause does not force `insufficient_evidence` there.

### Run

One fresh WarrantReviewer call per proposition (C1, C2, T), identical A1 context, the
evidence-burden contract, one run each.

### Decision table — declared before running

| C1 Tammi | C2 Tuote | T Jakso A | Reading | Action |
| --- | --- | --- | --- | --- |
| supported | supported | **insufficient_evidence** | **Policy fix works.** GLM possessed the discrimination; the original reviewer asked the wrong epistemic question. The fix is architectural/policy, not "two giant models." | **Replay full frozen G3 with this contract** (3B.1-replay). |
| supported | supported | supported | Still overconfident. The evidence-burden contract did not change the judgement. | Run **3B.2** (different model). |
| insufficient | insufficient | insufficient | **Paranoid reviewer.** The contract swung bias to reflexive opposition. Not useful. | Run **3B.2** (different model, neutral contract). |
| supported | insufficient | * | Control broken in the non-month direction — the clause over-fires on `Tuote`. | Inspect; the contract needs refinement before any 3B.2 reading is meaningful. |
| insufficient | supported | * | Control broken in the month direction. | Inspect. |
| (any other mix) | | | Ambiguous. | Inspect the trace before concluding anything. |

The pass criterion for 3B.1 is the **first row only**: both controls `supported` AND the
target `insufficient_evidence`. Anything else does not pass.

---

## 3B.1-replay — full frozen G3 with the evidence-burden reviewer

**Only if 3B.1 passes (first row).** Checks the whole chain end-to-end with the new
reviewer contract, changing only the reviewer policy relative to 3A's G3.

The G3 **classifier outputs are frozen** — reused verbatim from 3A's recorded G3
(`experiment3a/judgements/G3.json`): `Tuote=not_month, Tammi=month, Helmi=month,
Jakso A=not_month, Huhti=month, Touko=month`. The classifier is **allowed to still be
wrong** on `Jakso A`. The point is to show the reviewer + gate catch it regardless.

Six fresh WarrantReviewer calls under the evidence-burden contract, one per frozen
classification, identical A1 context. Then the **same deterministic gate** as 3A
(`experiment3a/harness/compose.py`, reused by import — no drift).

Expected:

```text
classifier   Jakso A -> not_month          # frozen, still allowed to be wrong
reviewer     Jakso A = not_month -> insufficient_evidence
gate         -> ASK_HUMAN (month_columns=[2,3,5,6] partial, unknown_columns=[4])
```

Pass criterion: `ask_human = true` (with the five non-target warrants `supported`).
This is the demonstration of the principle: the specialist need not be perfectly
calibrated, provided a different decision standard sits between its classifications and
authority. **If this passes, 3B is done — 3B.2 is not run.**

---

## Probe 3B.2 — Different-model reviewer (conditional)

**Only if 3B.1 does not give the control-preserving result.** Tests **model diversity**:
does a reviewer from a different model family, under the **original neutral contract**
(3A's contract, not the evidence-burden one), catch the target?

Only the reviewer model changes. Everything else frozen: same A1 context, same three
propositions (C1, C2, T), same output schema, same scoring, same single run each.

### Model choice (frozen)

Reviewer model: **`llama3.1:8b`** via Ollama (`http://localhost:11434/api/chat`), a
different family from GLM/qwen, 8B class (capable of the JSON contract). Digest verified
before running. If `llama3.1:8b` cannot produce valid JSON for the contract on a control
proposition, that is recorded as an interface failure (a datapoint, not a rescue); in that
case `gemma4:latest` is the declared fallback (also a different family), recorded as the
fallback used.

`qwen3.5:9b` is deliberately **not** the 3B.2 reviewer: it is the model that made the
`Jakso A → not_month` over-assertion in 2B.5, so it carries the same prior by origin and is
not a clean test of model diversity.

The 3B.2 reviewer is invoked via the Ollama HTTP API (not the Claude Code agent tool),
because it is a different model. The contract text is 3A's original neutral reviewer
contract. The invocation mechanism differs from 3B.1 (Agent tool) but the contract,
context, propositions and schema are identical — the mechanism is infrastructure.

### Decision table — read together with 3B.1

| 3B.1 (GLM evidence-rule) | 3B.2 (other model, neutral) | Reading |
| --- | --- | --- |
| pass | (not run) | **Policy problem.** The decision standard was the fix. |
| fail (overconfident or paranoid) | pass (controls supported, target insufficient) | **Model diversity helps.** A different family's prior does not share the blind spot. |
| fail | fail (target supported) | **Ambiguity is harder than the reviewer design assumes.** The `Jakso A` case defeats both the policy fix and a different model. |
| fail | fail (paranoid / interface) | Inconclusive on model diversity; record the mode. |

## Hard stop (carried from 3A)

No normalization, no transformation code, no country mappings, no numeric parsing, no
multiple sheets, no joins, no procedure synthesis. 3B tests **reviewer policy and model
diversity for the escalation signal only**. It ends there.

## Stated limitations (declared before running)

- One run per proposition, one model per probe, no seed control over GLM-5.2 in the agent
  tool (3B.1/replay) and a single Ollama seed (3B.2). Cannot distinguish *always* from
  *once*.
- Model diversity ≠ epistemic independence (terminology above). A 3B.2 pass is evidence
  that *this* other model does not share the prior on *this* cell, not that diverse models
  are independent in general.
- The 3B.1 contract was designed knowing the target (`Jakso A`) and the desired outcome
  (`insufficient_evidence`). There is no way around this: the contract is the manipulation.
  The controls are what make the result interpretable — a contract engineered to reject
  `Jakso A` but that also rejects `Tuote` is caught by C2. The honest framing is that 3B.1
  tests a **specific decision standard**, not reviewer skill in the abstract.
- Orchestrator foreknowledge (from 3A) persists; mitigated by frozen grading, verbatim
  traces, and the controls. The propositions and expected warrants are fixed here.