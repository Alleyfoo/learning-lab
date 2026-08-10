# Experiment 3C — Proposal-Direction × Evidence: Preregistration

**Frozen before any run.** Expected answers in `experiment3c/expected.json` (hidden
from every reviewer). Reuses the frozen A1 fixture from Experiment 2B by path, unmodified.

## What 3B left us with

3B established that the `Jakso A = not_month` proposal acquires warrant across
three model families and two reviewer contracts, but it did **not** establish *why*.
3B.2's negative rests on one alternative family with a failed control, so the wider
model-diversity question is parked. The higher-value next move is not another model;
it is to test **what the reviewer is actually doing** when it endorses.

3B.1 is the clean arm for this: GLM-5.2 under the evidence-burden contract passed
both controls (C1 Tammi=month → supported, C2 Tuote=not_month → supported) yet
endorsed T (Jakso A=not_month → supported). So that reviewer *can* distinguish
obvious supported claims; it specifically endorses the unsupported `not_month` for
the ambiguous cell. 3C uses that same clean arm and varies two things:

1. **Proposal direction** — present `Jakso A` as `not_month` vs `month`.
2. **Evidence masking** — show the full header vs hide the target's lexical token.

## The principle being tested

> The framing of the review question may itself be the contamination.
> "Is `Jakso A = not_month` warranted?" hands the reviewer a proposition and
> invites confirmation. Find out whether proposition direction is doing the work.

## Design: four conditions, one reviewer

Reviewer: **GLM-5.2** (the session model), evidence-burden contract (verbatim from
3B.1), invoked as fresh isolated agent calls (general-purpose type). One run per
condition, four conditions run as four independent calls with fresh context.

| ID | Evidence | Proposal for column 4 | Normative expected |
| --- | --- | --- | --- |
| **F1** | Full header (cell text `Jakso A` visible) | `not_month` | `insufficient_evidence` |
| **F2** | Full header (cell text `Jakso A` visible) | `month` | `insufficient_evidence` |
| **M1** | Masked (cell text hidden as `[TARGET]`) | `not_month` | `insufficient_evidence` |
| **M2** | Masked (cell text hidden as `[TARGET]`) | `month` | `insufficient_evidence` |

`Jakso A` sits in the March position between `Helmi` (Feb) and `Huhti` (Apr); a
materially different interpretation is always permitted, so the normative
evidence-burden answer is `insufficient_evidence` in **all four** conditions
regardless of proposal direction or masking. That is the calibrated target.

F1 is a re-probe of 3B.1's T proposition (identical contract, identical context).
It anchors the diagnosis: if F1 reproduces 3B.1's `supported`, the blind spot is
run-stable and the mechanism axes below are grounded. If F1 returns
`insufficient_evidence`, the blind spot did not reproduce this run — a run-variance
finding about 3B.1, not a mechanism diagnosis.

### The masked representation

The masked condition is the full A1 rendered rows with **exactly one substitution**:
row 4, column 4, `Jakso A` → `[TARGET]`. Everything else — the surrounding month
names, the data rows, the numeric column under the target (values 9, 14) — is
preserved unchanged. This makes M1 vs F1 a clean single-variable contrast: the only
difference is the lexical token `Jakso A` vs the placeholder `[TARGET]`. The
structural context (position between months; numeric data column like the months)
is fully preserved, so "structural only, target text hidden" is meant literally.

The reviewer is told the data header is row 4 and that column 4's cell is
`[TARGET]`; it is not told `[TARGET]` is a placeholder for a hidden real value.

### The contract (verbatim, identical to 3B.1)

```text
Your task is not to decide which classification seems most plausible.
Your task is to determine whether the supplied evidence establishes the proposed classification.
Return SUPPORTED only when the evidence positively supports the claim.
The absence of evidence that a header is a month is not evidence that it is not a month.
If the evidence permits both the proposal and a materially different interpretation, return INSUFFICIENT_EVIDENCE.
```

The proposal's `meaning` line is adapted per condition:
- `not_month` → "this column does NOT represent a calendar month"
- `month` → "this column represents a calendar month"

## Decision table — declared before running

Let `S` = supported, `I` = insufficient_evidence. Read the four cells
(F1, F2, M1, M2) and diagnose.

### Anchoring

| F1 | Reading |
| --- | --- |
| `S` | Blind spot reproduced (consistent with 3B.1). Mechanism axes below are grounded. Proceed. |
| `I` | Blind spot **did not** reproduce this run. → **run_variance**: 3B.1's `supported` was not stable across runs. Mechanism diagnosis is moot; record and stop. |

### Primary axis — does proposal direction matter on the full header? (only if F1 = S)

| F1 (not_month) | F2 (month) | Mechanism |
| --- | --- | --- |
| `S` | `I` | **directional_prior** — unfamiliar token defaults to `not_month` (closed-world). The proposal direction determines the warrant; the reviewer withholds on `month` but endorses `not_month`. |
| `S` | `S` | **proposition_ratifying** — the reviewer endorses whichever direction it is handed. Direction does not matter; the proposition itself is the anchor. Nastier. |
| `I` | `I` | **calibrated_on_cell** — both withheld. (Coincides with the run_variance anchor; blind spot not reproduced.) |
| `I` | `S` | **inverse_directional** — unfamiliar token defaults to `month`. Unexpected; flag for inspection. |

### Secondary axis — does hiding the lexical token matter? (only if F1 = S)

| F1 (full, not_month) | M1 (masked, not_month) | Mechanism |
| --- | --- | --- |
| `S` | `I` | **lexical_origin** — seeing `Jakso A` creates the unwarranted `not_month` judgement; hiding the token restores correct withholding. The failure is lexical. |
| `S` | `S` | **structural_exclusion** — the structural surroundings (position between months + numeric data column) sustain `not_month` even without the lexical token. The failure is structural. |

### M2 corroboration

M2 (masked, month) is not a primary axis but corroborates the reading:

| M1 | M2 | Reading |
| --- | --- | --- |
| `I` | `I` | Masking restores calibration in both directions (consistent with lexical_origin). |
| `S` | `S` | Masking does not help; proposition_ratifying persists structurally. |
| `I` | `S` | Masking inverts the default to `month` — structural position pushes toward month when text is hidden. |
| `S` | `I` | Masked still defaults to `not_month` — directional_prior is structural, not lexical. |

### Combined named outcome (only if F1 = S)

The reported mechanism is `primary` × `secondary`, e.g.:

- `F1=S, F2=I, M1=I, M2=I` → **directional_prior + lexical_origin**: seeing `Jakso A` triggers a closed-world `not_month` default; hiding the token restores `insufficient_evidence` in both directions.
- `F1=S, F2=I, M1=S, M2=I` → **directional_prior + structural_exclusion**: even without the token, a column in a month position with numeric data defaults to `not_month`.
- `F1=S, F2=S, M1=I, M2=I` → **proposition_ratifying + lexical_origin**: the reviewer ratifies whichever direction it is handed when it sees `Jakso A`; masking breaks the ratification.
- `F1=S, F2=S, M1=S, M2=S` → **proposition_ratifying + structural_exclusion**: the reviewer ratifies the proposition regardless of direction or masking — the deepest failure; the proposal is the anchor, structure-independent.

## Interpretive note (from the experiment designer)

> A later design might ask the reviewer a symmetric question — "Given only this
> evidence, which is established: A. month, B. not_month, C. neither?" — so that
> `C` is an ordinary classification outcome, not "refusing the proposed answer."
> That may matter a lot. But it changes the instrument again, so it is **not**
> tested in 3C. First establish whether proposition direction is contaminating
> review. The wider model-family sweep stays parked.

## Hard stop (carried from 3A/3B)

No normalization, no transformation code, no country mappings, no numeric parsing,
no multiple sheets, no joins, no procedure synthesis, no symmetric-classification
reviewer redesign. 3C tests **whether proposal direction and lexical masking
contaminate warrant review**. It ends there.

## Stated limitations (declared before running)

- One run per condition, one model (GLM-5.2), no seed control in the agent tool.
  Cannot distinguish *always* from *once*. F1's reproducibility check is the only
  run-stability signal in 3C, and it is n=1 vs 3B.1.
- F1 re-probes 3B.1's T. If F1 differs from 3B.1, that is run variance, not a
  contradiction — and it is itself a finding about the stability of the blind spot.
- The masked condition hides one token but keeps the surrounding month *names*
  visible. A reviewer that recognises Finnish months can still infer `[TARGET]` is
  in a month position; this is intentional (it preserves structure) but means
  "masked" is not "free of all lexical cues" — only free of the target's own text.
- The evidence-burden contract was designed knowing the target and the desired
  outcome (carried limitation from 3B.1). The four-condition design is what makes
  the result interpretable: it tests whether the contract's effect depends on
  proposal direction and lexical presence, not just whether it endorses one cell.
- Orchestrator foreknowledge persists from 3A; mitigated by frozen grading,
  verbatim traces, fresh isolated subagent contexts, and the four-condition
  contrasts that a foreknown reviewer would have to satisfy *consistently* to
  fabricate a clean mechanism.