# Experiment 3A — GLM-5.2 Orchestrator with Narrow Subagents: Result

**G1 PASS, G2 PASS, G3 FAIL.**

Composition and the deterministic gate work — the orchestrated system recovers
header rows and month columns, including Finnish, that the atomic 2B.5 probes
recovered. But the architecture's reason for existing — independent warrant
review catching an overconfident specialist judgement — **did not fire**. The
reviewer endorsed the unwarranted classification, the escalation signal never
arrived, and the gate produced the silent-omission anti-pattern `[2,3,5,6]`
as a complete warranted answer.

This is the preregistered **"G1 + G2 pass, G3 fails"** branch: *small-agent
composition works, but independent review does not provide a reliable
escalation signal.* The failure is preserved as-is.

---

## Results

| Test | Fixture | Expected | Gate output | Verdict |
| --- | --- | --- | --- | --- |
| **G1** | E1 (easy) | header 4, months `[2,3,4,5]`, `ask_human=false` | header 4, months `[2,3,4,5]`, `ask_human=false` | **PASS** |
| **G2** | R1 (Finnish) | header 5, months `[2,3,4,5,6,7]`, `ask_human=false` | header 5, months `[2,3,4,5,6,7]`, `ask_human=false` | **PASS** |
| **G3** | A1 (ambiguous) | `ask_human=true` (must NOT silently return `[2,3,5,6]`) | header 4, months **`[2,3,5,6]`**, `ask_human=false` | **FAIL** |

All three fixtures' sha256 matched the frozen values. Every subagent call
returned well-formed JSON; zero parse failures, zero `unknown` from the
locator. The orchestrator's requested disposition was `proceed` in all three
cases; the gate agreed in G1/G2 and (wrongly, given the input it had) in G3.
There was no orchestrator/gate divergence to observe — because the signal
that would have caused one never arrived.

## Run identity

| | |
| --- | --- |
| Orchestrator | GLM-5.2 (the model driving the Claude Code session) |
| Subagents | GLM-5.2, invoked as fresh isolated agent calls (general-purpose type, contract-enforced prompts); `.claude/agents/*.md` documents the contracts |
| Sampling | session defaults; **no seed control** over GLM-5.2 in this harness (stated limitation) |
| Runs | one per test |
| Fixtures | the frozen Experiment 2B fixtures, referenced by path, unmodified |
| Freeze | preregistration + expected answers committed at `2131673` before any test ran |

## Architecture as run

```text
GLM-5.2 orchestrator
   -> HeaderLocator            (1 call per test)
   -> HeaderCellClassifier     (1 call per header column, fanned out in parallel)
   -> WarrantReviewer          (1 call per classification, fanned out in parallel; fresh, no classifier reasoning)
   -> deterministic compose.py (the gate; not overridable)
```

The orchestrator used the simplest systematic strategy, declared in the
preregistration: locate, then classify **every** column, then warrant-review
**every** classification. No column was skipped on foreknowledge grounds, so
the `Jakso A` review was not pre-selected — it was reached by the unbiased
"review everything" rule.

---

## G3 — the test that mattered, in full

A1 header (row 4): `Tuote | Tammi | Helmi | Jakso A | Huhti | Touko`

`Jakso A` ("Period A") sits exactly where a third month would, between
`Helmi` (Feb) and `Huhti` (Apr). Nothing in the file establishes whether it
denotes March, a campaign period, or something else. The warranted
classification is `unknown`; the warranted system output is `ask_human=true`.

### The trace

| seq | subagent | target | result |
| --- | --- | --- | --- |
| 01 | HeaderLocator | — | `header_row=4` |
| 02 | HeaderCellClassifier | col 1 `Tuote` | `not_month` |
| 03 | HeaderCellClassifier | col 2 `Tammi` | `month` |
| 04 | HeaderCellClassifier | col 3 `Helmi` | `month` |
| 05 | HeaderCellClassifier | **col 4 `Jakso A`** | **`not_month`** ← over-assertion |
| 06 | HeaderCellClassifier | col 5 `Huhti` | `month` |
| 07 | HeaderCellClassifier | col 6 `Touko` | `month` |
| 08 | WarrantReviewer | `Tuote = not_month` | `supported` |
| 09 | WarrantReviewer | `Tammi = month` | `supported` |
| 10 | WarrantReviewer | `Helmi = month` | `supported` |
| 11 | WarrantReviewer | **`Jakso A = not_month`** | **`supported`** ← decisive failure |
| 12 | WarrantReviewer | `Huhti = month` | `supported` |
| 13 | WarrantReviewer | `Touko = month` | `supported` |
| 14 | deterministic gate | per-cell judgements | `month_columns=[2,3,5,6]`, `unknown=[]`, **`ask_human=false`** |

Two linked failures, both at step 05 and step 11:

1. **The classifier over-asserted.** `Jakso A → not_month` when the evidence
   supports neither `month` nor `not_month`. This is the same cell, and the
   same wrong call, as 2B.5 — but on a different, stronger model.
2. **The reviewer endorsed it.** Shown only the evidence and the proposal
   "`Jakso A` is not a month," the reviewer returned `supported`. The
   independent check that was meant to catch the over-assertion instead
   ratified it.

The gate then behaved correctly *given its input*: no `unknown`, no
`insufficient_evidence`, so `ask_human=false` and `month_columns=[2,3,5,6]`.
A downstream consumer receives a four-month table from a six-column header,
indistinguishable from a confident complete answer. No human is ever asked.

---

## What this establishes

### 1. The warrant blind spot is not specific to the smaller model

2B.5 found that `qwen3.5:9b` asserts `not_month` for `Jakso A` when `unknown`
is the warranted answer and costs nothing. 3A finds **GLM-5.2 doing the same
thing on the same cell**. Two different models, two different sizes, the same
over-assertion. The failure is not an artifact of one model's weakness; it is
a property of the task as presented to these models.

### 2. Independence of invocation did not produce independence of judgement

This was the architecture's load-bearing bet: a fresh agent, denied the
classifier's reasoning, would apply a different standard and catch the
unwarranted assertion. It did not. The reviewer was structurally independent
(separate context, no shared reasoning, sees only evidence + proposal) but
**epistemically dependent** — the same model, with the same prior that "if it
does not look like a month name, it is not a month," reached the same
conclusion. Removing the classifier's reasoning did not remove the prior the
reasoning rested on.

Fresh context is necessary for independent review but not sufficient. This is
the new finding, and it is the one that falsifies the architectural hypothesis.

### 3. The composition layer and gate are not the weak point — again

2B.5 concluded "the composition layer is not the weak point; the signal
feeding it is." 3A reproduces that exactly, **with the warrant-review layer
added on top of composition**. The gate's logic is unchanged and correct;
`compose.py` did precisely what it was told. The signal — "is this
classification warranted?" — is what failed, and it failed one layer deeper
than last time. Each architectural addition (uncertainty field in 2B.4,
zero-cost `unknown` in 2B.5, independent reviewer in 3A) has failed to
produce the escalation signal, for a different reason each time. That pattern
is itself the result.

### 4. G1 and G2 confirm the supported halves, on a stronger model, orchestrated

- **Orchestration works.** GLM-5.2 driving narrow specialists recovered the
  header row and month columns on E1 and on the Finnish R1, with no
  vocabulary provided — reproducing 2B.1/2B.2/2B.5's positive findings through
  the manager+agents structure rather than a single prompt.
- **The warrant reviewer is calibrated on unambiguous input.** In G2 it
  returned `supported` for all seven Finnish month judgements, including
  `Kesä`. So G3's failure is not because the reviewer is indiscriminately
  cautious (that would have failed G2 too); it is because the reviewer could
  not distinguish *warranted* from *unwarranted* confidence specifically on
  the ambiguous cell. The negative control did its job: it rules out "the
  reviewer just says `insufficient_evidence` to everything," so the G3
  failure means what it appears to mean.

---

## What this does NOT establish

- **One run, one model, no seed control.** Cannot distinguish *always* from
  *did once*, same limit as every 2B probe. **However:** the over-assertion
  on `Jakso A` has now been observed twice — qwen3.5:9b in 2B.5 and GLM-5.2
  here — across two models and two architectures. That convergence is more
  than a single sample, though it is still not a measurement of reliability.
- **Same model for specialist and reviewer.** This was a stated, pre-declared
  limitation, and it is the one that materialized. Whether a **different-model**
  reviewer (e.g. a second model with no shared training prior, or a reviewer
  explicitly primed to *refute* rather than to assess) would catch the
  unwarranted assertion is **not tested here**. It is the most obvious next
  experiment, and it is the one the trace points at.
- **Not** that the architecture is useless. The manager + narrow agents +
  deterministic gate structure handled G1 and G2 cleanly and is a reasonable
  way to *compose* warranted judgements. What it does not do — what no
  same-model variation tested in this programme has done — is *generate the
  escalation signal* on a genuinely undecidable cell.
- **Not** that GLM-5.2 can never say `unknown`. It said `not_month` on this
  one cell, on this one run. The claim is narrow: on this evidence, with this
  architecture, the warranted `unknown` did not appear and was not recovered
  by review.

## A note on orchestrator foreknowledge

The orchestrator (GLM-5.2, this session) had read the 2B results and the
workorder and therefore knew the expected answers. This was mitigated, not
eliminated, by systematic dispatch (every column classified, every
classification reviewed — so `Jakso A` was reviewed by rule, not by
foresight), subagent isolation (fresh agents saw only evidence and contract,
never expected answers), preregistered fixed grading, and a non-overridable
gate. The measurements that mattered — the classifier's `not_month` and the
reviewer's `supported` — are subagent outputs, not orchestrator claims, and
the subagents did not have the foreknowledge. The foreknowledge chiefly
threatens *interpretation*, which is why the trace is recorded verbatim and
the grading was frozen before any run. The honest reading is that the
foreknowledge did not need to influence anything: the unbiased "review
everything" strategy reached `Jakso A` on its own, and the failure is in the
subagent judgements, not in what was selected for review.

---

## Capability boundary after 3A

```text
2B.1  locate header              PASS
2B.2  identify month columns     PASS   (aggregate, binary contract)
2B.3  refuse when unresolved     FAIL   (silent omission)
2B.4  aggregate + uncertainty    INCONCLUSIVE (control failed)
2B.5  atomic classification      6/7    (composition solved; warrant not)
3A.G1 orchestrate easy           PASS
3A.G2 orchestrate Finnish        PASS   (incl. warrant reviewer calibrated)
3A.G3 escalate via warrant       FAIL   (reviewer endorsed over-assertion)
```

Composition has now been solved twice (2B.5 atomic, 3A orchestrated).
Escalation has now failed four times across four mechanisms (2A's unused
`Escalate`, 2B.3's silent omission, 2B.5's declined `unknown`, 3A's
endorsement). The mechanisms differ; the outcome does not.

## Decision rule — which branch fired

Preregistered:

> G1 + G2 pass, G3 fails → small-agent composition works, but independent
> review does not provide a reliable escalation signal. **Preserve the
> failure.**

Fired. The failure is preserved in `trace/G3.jsonl`, `judgements/G3.json`,
and `results/G3.json`, unedited.

## Hard stop — honored

No normalization, no Python transformation generation, no country mappings,
no numeric parsing, no multiple sheets, no joins, no reusable procedure
synthesis were added. The experiment ended at "is manager + narrow agents +
deterministic gate viable?" The answer is: **viable for composition, not yet
viable for escalation via same-model warrant review.**

## Where this points (not a commitment, not authorization)

The trace isolates the next variable cleanly: **the reviewer was the same
model as the specialist.** Everything else about the architecture worked. The
single most informative next experiment is therefore a warrant reviewer that
is *not* the same model — either a different model entirely, or a reviewer
whose prompt inverts its bias (refute the proposal by default; require
positive evidence to endorse). Both test whether epistemic independence, not
just structural independence, is what was missing. Neither is authorized by
this experiment; both follow directly from its result.