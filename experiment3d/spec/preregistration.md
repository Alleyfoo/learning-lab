# Experiment 3D — Symmetric Reviewer: Preregistration

**Frozen before any run.** Expected answers in `experiment3d/expected.json` (hidden
from every reviewer). Reuses the frozen A1 fixture from Experiment 2B by path, unmodified.

## What 3C left us with

3C located the mechanism behind the 3A/3B blind spot:

> The reviewer uses a closed-world lexical heuristic — if the token does not look
> like a known month name, `not_month` becomes the default — and this lexical prior
> can override stronger structural evidence even under an explicit evidence-burden rule.

The 3C 2×2 cross was:

```text
                 not_month        month
Full  Jakso A     supported      insufficient      <- direction matters; not_month wins
Masked [TARGET]   insufficient   supported         <- masking inverts the default to month
```

Two things were established:

1. **Direction matters.** The reviewer endorsed `not_month` but withheld on `month`
   for the same token — a directional prior, not proposition-ratifying.
2. **The prior is lexical and overrides structure.** Hiding `Jakso A` → `[TARGET]`
   flipped `not_month` to `insufficient`; the masked structure read as `month`
   (M2). The structural surroundings are month-positive; the lexical token was the
   *only* thing driving `not_month`.

Crucially, the evidence-burden clause *"the absence of evidence that a header is a
month is not evidence that it is not a month"* did **not** prevent the inference.
3C showed why: under asymmetric proposition framing ("is `Jakso A = not_month`
warranted?"), the handed proposal aligns with the closed-world default, and the
default answers before the evidence standard can bite.

## The principle being tested

> Does the closed-world lexical default *require* a handed proposal to confirm
> against, or does it fire on its own?

3D removes the handed proposal. The reviewer is no longer asked to validate a
proposition; it independently answers a **symmetric** question:

```text
Given the supplied evidence, which conclusion is established?
  A. The target is a calendar month
  B. The target is not a calendar month
  C. Neither conclusion is established by the evidence
```

`C` is now an ordinary classification outcome, not "refusing the proposed answer."
The closed-world default would have to **select B over C** against a symmetric
field, rather than confirm a handed B. If the default cannot do that, `C` appears —
and the gate receives the escalation signal it has been waiting for since 2B.3.

## Design: four probes, one reviewer, symmetric question

Reviewer: **GLM-5.2** (the session model), invoked as fresh isolated agent calls
(general-purpose type). One run per probe, four probes run as four independent
calls with fresh context. Same fixture, same evidence-burden standard as 3B.1/3C;
**only the review framing changes** — symmetric A/B/C instead of a handed proposal.

All four probes show the **full A1 table** (or masked A1) and point at a target
column. Only the target column differs across conditions — a clean single-variable
contrast.

| ID | Evidence | Target | Expected | Role |
| --- | --- | --- | --- | --- |
| **CTRL-MONTH** | Full A1 | col 2 `Tammi` | **A** (month) | control: symmetric contract must establish a real month |
| **CTRL-NONMONTH** | Full A1 | col 1 `Tuote` | **B** (not_month) | control: symmetric contract must establish a real non-month |
| **3D-FULL** | Full A1 | col 4 `Jakso A` | **C** (neither) | the target — 3A/3B/3C failure cell, now without a handed proposal |
| **3D-MASKED** | Masked A1 (col 4 → `[TARGET]`) | col 4 `[TARGET]` | **A** (month) | structure-only — 3C's M2 said structure establishes month; does it hold without a handed proposal? |

### Why these expected answers

- `Tammi → A`: a real Finnish month, full context. If the symmetric contract cannot
  establish this, the contract is over-withholding (broken).
- `Tuote → B`: a product label with alphanumeric data below it. If the symmetric
  contract cannot establish this, it is over-withholding (broken).
- `Jakso A → C`: the 3C finding is that the evidence establishes *neither* month
  nor not_month for this cell (F2 said month is not established; the warrant for
  not_month was a lexical default, not evidence). Under symmetric framing, with no
  handed `not_month` to confirm, the resting state should be `C`. **This is the
  load-bearing prediction.**
- `[TARGET] → A`: 3C's M2 returned `supported` for the masked month proposal — i.e.
  the reviewer found the structural evidence sufficient to establish month for
  `[TARGET]`. Under symmetric framing, the same evidence should yield `A`
  independently. If it instead yields `C`, then 3C's M2 confidence depended on
  proposition framing too.

### The masked representation

Same as 3C: full A1 with one substitution, row 4 col 4 `Jakso A` → `[TARGET]`.
All other cells (incl. data 9, 14 under col 4) preserved. The reviewer is told the
data header is row 4 and that column 4's cell is `[TARGET]`; it is not told
`[TARGET]` is a placeholder for a hidden real value.

### The symmetric contract (binding)

```text
You are an independent reviewer. Determine which conclusion the supplied evidence
establishes for the target column. You are NOT validating a proposed answer; you
are independently reading the evidence.

A conclusion is established only when the supplied evidence positively supports it.
The absence of evidence that the target is a month is not evidence that it is not
a month. If the evidence does not establish that the target is a month, and does
not establish that it is not a month, the answer is C.

Given the supplied evidence, which conclusion is established for the target column?
  A. The target is a calendar month
  B. The target is not a calendar month
  C. Neither conclusion is established by the evidence
```

Output: a single JSON object `{"established": "A"}` (or B, or C) — no explanation,
no reasoning, no prose. The A/B/C verdict only.

## Decision table — declared before running

Let each probe return one of {A, B, C}.

### Controls (must both hold for any clean reading)

| CTRL-MONTH (Tammi) | CTRL-NONMONTH (Tuote) | Reading |
| --- | --- | --- |
| A | B | **controls_pass** — symmetric contract calibrated; proceeds to target diagnosis. |
| C | * | **control_broken_month** — symmetric contract over-withholds; cannot establish even a real month. Target diagnosis moot. |
| * | C | **control_broken_nonmonth** — symmetric contract over-withholds; cannot establish even a real non-month. Target diagnosis moot. |
| B | * | **control_misclassified_month** — gross error (Tammi→not_month). Inspect. |
| A→other combos | | **controls_broken** — symmetric contract itself is the problem; record and stop. |

### Primary axis — 3D-FULL (Jakso A), only if controls pass

| Jakso A | Mechanism | Reading |
| --- | --- | --- |
| **C** | **framing_was_the_problem** | Symmetric framing lets the model represent uncertainty. The closed-world lexical default required a handed `not_month` proposal to fire; without it, the reviewer correctly withholds. **The architecture should switch to symmetric review.** |
| **B** | **closed_world_prior_persists** | Even without a handed proposal, the model treats "Jakso A doesn't look like a month" as positive evidence for `not_month`. Symmetric framing does NOT solve it. The prior is deeper than framing. |
| **A** | **surprising_month_established** | The reviewer establishes month for `Jakso A` under symmetric framing — the lexical prior is not firing `not_month` and structure/context is winning toward month even with the text visible. Unexpected given 3C F1/F2; flag for inspection. |

### Secondary axis — 3D-MASKED ([TARGET]), only if controls pass

| [TARGET] | Mechanism | Reading |
| --- | --- | --- |
| **A** | **structure_establishes_month** | Consistent with 3C M2. Without the lexical token and without a handed proposal, the reviewer independently concludes month from structure. Confirms structure is month-positive and the lexical token was the only override. |
| **C** | **structure_insufficient_under_symmetric** | Removing the proposal framing also removed the confidence on structure — 3C's M2 `supported` may have depended on proposition framing (the reviewer endorsed a handed month proposal but won't independently assert month). Structure alone does not *establish* month under the symmetric standard. |
| **B** | **masked_defaults_not_month** | Contradicts 3C M2; symmetric framing flips masked to `not_month`. Unexpected; inspect. |

### Combined named outcome (only if controls pass)

The reported mechanism is `primary` × `secondary`. The headline outcomes:

- `Jakso A→C, [TARGET]→A` → **framing_was_the_problem + structure_establishes_month**.
  The clean win: symmetric framing solves the escalation (`Jakso A` correctly
  withholds as `C`), and structure alone establishes month for the masked cell. The
  architectural change is justified by measurement.
- `Jakso A→B, [TARGET]→A` → **closed_world_prior_persists + structure_establishes_month**.
  The lexical prior fires even without a proposal; symmetric framing does not solve
  escalation. Structure is still correctly read as month when the token is hidden.
- `Jakso A→C, [TARGET]→C` → **framing_was_the_problem + structure_insufficient_under_symmetric**.
  Symmetric framing fixes `Jakso A` (withholds) but also makes the masked cell
  withhold — the proposal framing was inflating confidence in *both* directions,
  not just `not_month`. Partial win; the gate would still escalate on `Jakso A`.
- `Jakso A→B, [TARGET]→C` → **closed_world_persists + structure_insufficient**.
  Both deeper prior and weak structure under symmetric; symmetric framing does not
  solve escalation and removes the structural confidence too.

## Pass criterion

**Symmetric framing solves escalation** = `controls_pass AND Jakso A→C AND
[TARGET]→A` (the clean-win pattern: Tammi→A, Tuote→B, Jakso A→C, [TARGET]→A).

A `Jakso A→C` with `[TARGET]→C` is a **partial pass**: symmetric framing fixes the
escalation on the failure cell (the gate would receive `C` and escalate), even
though the masked structural confidence did not survive the framing change. This
is still architecturally useful — the gate gets its signal on the cell that
matters. The pass criterion above requires the full clean win; the partial case is
recorded and interpreted separately.

## Architectural implication (if the clean win holds)

```text
specialist proposes classification
        ↓
reviewer does NOT review the proposition

reviewer independently asks: what does the evidence establish?
        ↓
MONTH (A) / NOT_MONTH (B) / NEITHER (C)
        ↓
deterministic comparison
        ↓
specialist = not_month, reviewer = C  ->  disagreement / insufficient warrant  ->  HUMAN
```

This is stronger than "review the specialist's claim" because the reviewer never
inherits the claim's direction. The closed-world default cannot confirm a handed
`not_month` because no `not_month` is handed.

## Hard stop (carried from 3A/3B/3C)

No normalization, no transformation code, no country mappings, no numeric parsing,
no multiple sheets, no joins, no procedure synthesis. 3D tests **whether symmetric
review framing lets the escalation signal appear**. It does not build the
symmetric-reviewer production architecture; it only tests the framing on the one
frozen cell (plus controls). It ends there.

## Stated limitations (declared before running)

- One run per probe, one model (GLM-5.2), no seed control in the agent tool.
  Cannot distinguish *always* from *once*. The four-probe pattern is one sample of
  each cell.
- Only GLM-5.2 tested. Whether symmetric framing solves the same cell on other
  model families is not tested (the wider sweep remains parked).
- The symmetric contract still names `B` (not_month) as an option. Listing B does
  not hand the reviewer a *direction* the way a proposal does, but it cannot be
  claimed that B is absent from the reviewer's view. The test is whether B must
  *compete* with C symmetrically rather than be *confirmed* — which is the
  architecturally relevant distinction.
- The expected `Jakso A→C` is the load-bearing prediction and is grounded in 3C's
  finding (F2: month not established; the not_month warrant was a lexical default,
  not evidence). It is still a prediction about a single run.
- The masked condition preserves surrounding month *names*; "masked" = free of the
  target's own text, not all text (carried from 3C, intentional).
- Orchestrator foreknowledge persists from 3A; mitigated by frozen grading,
  verbatim traces, fresh isolated subagent contexts, and the controls + contrasts
  that a foreknown reviewer would have to satisfy consistently to fake a clean
  result.