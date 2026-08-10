# Experiment 3E — Architectural Replay with Symmetric Review: Preregistration

**Frozen before any run.** Expected answers in `experiment3e/expected.json` (hidden
from every reviewer). Reuses the frozen A1 fixture (Experiment 2B) and the frozen
3A G3 classifier outputs (Experiment 3A), both by path, unmodified.

## The question

> Would the measured 3D reviewer fix have prevented the actual 3A G3 failure
> end-to-end?

3D showed that symmetric A/B/C review framing produces `Jakso A → C` (neither
established) on GLM-5.2 — the escalation signal no prior probe produced. 3E tests
whether that signal, fed into a deterministic comparison gate alongside the
**original frozen bad classifier judgement**, blocks the failure path that 3A G3
walked into.

## What is frozen, what is new

- **Frozen (reused verbatim):** the 3A G3 classifier outputs, including the
  over-assertion `Jakso A → not_month`. The classifier is NOT changed. This is the
  load-bearing constraint: the fix must work *with the specialist still wrong*.
- **Frozen (reused verbatim):** the A1 fixture, the header row (4), the symmetric
  A/B/C contract from 3D, the evidence-burden standard.
- **New:** the review path is the symmetric A/B/C reviewer (3D framing) on all six
  columns; the composition is a **deterministic comparison gate** (not the 3A
  warrant gate); and a secondary orchestrator-disposition measurement.

### The frozen 3A G3 classifier outputs (verbatim from `experiment3a/judgements/G3.json`)

```text
col 1  Tuote    -> not_month
col 2  Tammi    -> month
col 3  Helmi    -> month
col 4  Jakso A  -> not_month   # the over-assertion, unchanged
col 5  Huhti    -> month
col 6  Touko    -> month
```

3A's gate (warrant-review, same-model) endorsed all six and produced
`month_columns=[2,3,5,6], ask_human=false` — the silent-omission failure.

## Architecture as run

```text
frozen 3A G3 classifier outputs (specialist classifications, NOT re-run)
        ↓
symmetric A/B/C reviewer (GLM-5.2, 3D framing) — 6 fresh independent calls, one per column
        ↓
deterministic comparison gate (code, not LLM; authoritative)
        ↓
final gated output: month_columns, human_columns, ask_human

(secondary, non-authoritative: one orchestrator-disposition LLM call that sees
 the six specialist+reviewer pairs and is asked for a disposition — measures
 whether the reasoning layer agrees with the gate)
```

The orchestrator can request whatever it wants; **authority comes from the
comparison gate.** No orchestrator discretion after the gate.

## The deterministic comparison gate (frozen logic)

For each column, given the frozen specialist classification
(`month`/`not_month`) and the symmetric reviewer verdict (`A`/`B`/`C`):

```text
reviewer = C                                   -> HUMAN  (insufficient warrant)
specialist = month     AND reviewer = A        -> ACCEPT month
specialist = not_month AND reviewer = B        -> ACCEPT not_month
otherwise (specialist/reviewer disagreement)   -> HUMAN
parse failure on either input                  -> HUMAN  (conservative)
```

Aggregate:
```text
month_columns  = sorted(columns ACCEPTed as month)
human_columns  = sorted(columns routed to HUMAN)
ask_human      = bool(human_columns)
```

No LLM participates in this step. The gate is ordinary code.

## Expected per-column reviewer verdicts (symmetric A/B/C)

| col | cell | specialist (frozen) | expected reviewer | basis |
| --- | --- | --- | --- | --- |
| 1 | Tuote | not_month | **B** | measured: 3D CTRL-NONMONTH |
| 2 | Tammi | month | **A** | measured: 3D CTRL-MONTH |
| 3 | Helmi | month | **A** | predicted (obvious Finnish month, by analogy to Tammi) |
| 4 | Jakso A | not_month | **C** | measured: 3D FULL (load-bearing) |
| 5 | Huhti | month | **A** | predicted (by analogy to Tammi) |
| 6 | Touko | month | **A** | predicted (by analogy to Tammi) |

**Note:** 3D measured only Tammi, Tuote, Jakso A. Helmi/Huhti/Touko symmetric
verdicts are *predictions* (A), not yet measured. They are the five-resolvable-cells
positive control: if any returns C or the wrong letter, the fix is either paranoid
or miscalibrated, and the gate's "five resolvable cells accepted correctly" bar
fails for an interpretable reason.

## Expected gate output (frozen)

```text
col 1  not_month + B  -> ACCEPT not_month
col 2  month     + A  -> ACCEPT month
col 3  month     + A  -> ACCEPT month
col 4  not_month + C  -> HUMAN (insufficient warrant)
col 5  month     + A  -> ACCEPT month
col 6  month     + A  -> ACCEPT month

month_columns = [2, 3, 5, 6]
human_columns = [4]
ask_human     = true
```

This is **exactly 3A G3's frozen *expected* outcome** (`ask_human=true`), which 3A
failed to produce (3A got `ask_human=false`). 3E success = the original failure
path is blocked end-to-end, with the specialist still wrong.

## Success criterion (narrow, frozen)

> All five resolvable cells (cols 1, 2, 3, 5, 6) accepted correctly, `Jakso A`
> escalated, final gate output `ask_human=true`, `month_columns=[2,3,5,6]`.

Formally: `ask_human=true AND month_columns=[2,3,5,6] AND human_columns=[4] AND
cols {1,2,3,5,6} all ACCEPT (not HUMAN)`.

A failure mode where a resolvable cell is wrongly escalated (e.g., Helmi → C) fails
the "five resolvable accepted correctly" bar even if `Jakso A` is escalated — that
is the fix turning paranoid, which the controls are there to catch.

## Secondary measurement (non-authoritative)

One orchestrator-disposition LLM call (GLM-5.2, fresh isolated context). It
receives the full A1 evidence + the six `(cell, specialist classification,
reviewer verdict with meaning)` pairs, and is asked for a final disposition:

```text
{"month_columns": [...], "ask_human": true/false}
```

**Not required for success.** The deterministic gate owns authority. The
measurement records whether the reasoning layer, on seeing the symmetric-review
result (including `Jakso A → C`), requests HUMAN — i.e., whether
`orchestrator.ask_human == gate.ask_human` and `orchestrator.month_columns ==
gate.month_columns`. If the orchestrator says `proceed` (ask_human=false) despite
seeing `C`, that is a datapoint that the reasoning layer would have re-introduced
the failure had it held authority — and the gate's authority is what prevents it.

## Decision table — declared before running

Let the gate output be `(month_columns, human_columns, ask_human)`.

| Gate output | Reading |
| --- | --- |
| `ask_human=true, month_columns=[2,3,5,6], human_columns=[4]`, cols {1,2,3,5,6} ACCEPT | **PASS — failure blocked end-to-end.** The 3D fix, in the 3A architecture with the original bad specialist judgement, produces the escalation 3A failed to produce. The whole causal chain closes: 3A failure → 3B fixes fail → 3C mechanism isolated → 3D framing produces signal → 3E signal blocks the original failure. |
| `ask_human=false` (Jakso A not escalated) | **FAIL — fix did not block the failure.** The symmetric reviewer returned A or B for Jakso A (not C), so the gate accepted it. The 3D result did not survive the six-column replay. |
| `ask_human=true` but a resolvable cell (1,2,3,5,6) also escalated | **FAIL — fix turned paranoid.** A non-target cell returned C or disagreed. The fix is not safe to build on without refinement. |
| `ask_human=true`, Jakso A escalated, but `month_columns` wrong | **FAIL — partial.** Escalation right but composition wrong; inspect which cell mis-rendered. |

The orchestrator-disposition agreement is recorded alongside, independent of pass/fail.

## Hard stop (carried from 3A/3B/3C/3D)

No normalization, no transformation code, no country mappings, no numeric parsing,
no multiple sheets, no joins, no procedure synthesis. 3E replays the 3A G3 chain
with the symmetric reviewer + comparison gate. It does not build a production
system, run the wider model sweep, or measure replication. It ends at "did the
measured fix block the original failure end-to-end?"

## Stated limitations (declared before running)

- One run per reviewer cell, one model (GLM-5.2), no seed control. The 3D win was
  n=1; 3E is n=1 on each of six cells. Reliability still unmeasured — deliberately
  deferred until *after* 3E per the designer's ordering: "first prove the
  intervention closes the original failure path; then worry about replication."
- Helmi/Huhti/Touko symmetric verdicts are predictions (A), not measured in 3D.
  If any is wrong, the failure is interpretable (paranoid or miscalibrated) but
  the load-bearing cell (Jakso A) is still independently tested.
- The frozen specialist is the 3A G3 run's output. A different specialist run
  might classify Jakso A differently; 3E holds the specialist fixed by design (the
  fix must work with the specialist still wrong).
- The comparison gate is new code, not the 3A warrant gate. It is simple and
  deterministic; its correctness is auditable in `harness/compose_3e.py`.
- The orchestrator-disposition call sees the reviewer verdicts, so an
  `ask_human=true` from it is partly "deferring to C" rather than independent
  reasoning. The measurement is "did the reasoning layer agree with the gate,"
  not "did it independently re-derive the escalation." Stated as such.
- Orchestrator foreknowledge persists from 3A; mitigated by frozen grading,
  verbatim traces, fresh isolated subagent contexts (the six reviewers and the
  orchestrator call each see only their own inputs), and the deterministic gate
  that no LLM overrides.