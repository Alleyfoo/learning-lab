# S1 — Findings: what the LLM actually did when given a fleet to supervise

Four preserved runs over the frozen conditions in `s1/fixtures/{A,B,C,D}`, local
Ollama `glm-5.2:cloud`, `temperature=0.2`, `max_turns=6`, broad prompt
(`s1/prompt.txt`). Full transcripts in `s1/results/<X>/run-*.json`.

This is the evidence S1 was built to produce. S2 is designed from these results,
not from imagination.

## Headline: the supervisor never used Python (0/4 runs)

In every condition it answered in a single turn, reasoning directly from the
snapshot JSON placed in the prompt. `python_used=False`, `turns=1` for all four.

That is itself the first answer to the research question. At this snapshot scale
(one or two workers, a handful of runs) the answer is readable at a glance, so
the bench is never reached. The implication for experiment design is direct:

> **S4 ("Python as discovery surface") cannot be exercised on snapshots this
> small.** To learn whether and why the supervisor reaches for computation, the
> stimulus must be one where the answer is NOT readable at a glance — large
> histories, cross-worker comparisons, refusal-rate trends over time. The four
> S1 conditions were too small to test the bench. We have zero evidence yet about
> what it would try to calculate.

So the bench is built and canaried but unexercised by S1. That is an honest
result, not a gap to paper over.

## Calibration: B surfaced, A did not stay quiet

| | Prediction | What it did |
|---|---|---|
| **A boring** | should not manufacture concern | **Failed.** Produced 4 "things worth your attention" + 2 system suggestions on one clean worker. |
| **B effect failure** | surface prominently | **Passed, well.** Identified the accepted-but-effect-failed run, the lost reservation, the queued exception, and distinguished them from healthy refusals. |
| **C noisy healthy** | distinguish refusals from failure (may mention volume) | **Passed.** "Technically healthy," no exception; noted the 100% refusal rate as worth an advisory while hedging it may be test data. |
| **D pattern** | maybe a Reflector observation; observe, don't require | **Partial.** Surfaced the human-held-fact-expiry concern unprompted, but per-worker, not as a cross-worker recurring pattern. |

The open problem is calibration on the boring case. It felt compelled to produce
findings when there was nothing to find. **This is the direct motivation for S2**
(feedback changes supervision): the supervisor needs to learn, from operator
feedback, what is worth surfacing — including choosing to say nothing.

## It caught real fleet defects — and one architecture misread

Three genuine, verified system-level findings, made unprompted from the snapshot
alone (no Python):

1. **B — `pending_exceptions` does not include inbox exceptions.** The fleet-level
   `pending_exceptions` is empty while the inbox has one queued exception file, so
   an effect failure is invisible at the fleet summary. *Verified correct.*
   Candidate deterministic platform measurement.
2. **D — `committing` flag discrepancy on `training-room`.** `worker.committing`
   is `true` (declares an effect, reservation task) but `summary.committing` is
   `false` (the summary derives the flag from runs, and this worker has never
   run). *Verified correct — a real reporting bug.* Candidate deterministic
   platform measurement.
3. **D — aggregation has no readable model.** `readable_model` is "(no readable
   rendering for task type aggregation)". *Correct gap.* An operator cannot see
   what an aggregation does without reading the engine.

And one **architecture misread** on A:

- It flagged `committing: false` as "dry-run mode" and asked the operator to
  confirm whether that is intentional. But **enrichment, aggregation and
  reconciliation are non-committing by design** — they produce a result and change
  nothing; only reservation declares an effect. Flagging the absence of an effect
  on an enrichment worker is flagging by-design behaviour as a fault.

This misread is direct evidence for the **Rulebook** (deferred from S1) and for
what its first learned-practice rules should contain: *enrichment/aggregation/
reconciliation are non-committing by design; do not report the absence of an
effect as a concern.* The supervisor needs architectural context to avoid
flagging the system's own invariants.

## The platform-learning loop appeared — in prose, before any code

Even without Python, the supervisor proposed several measurements that are
candidates to become deterministic platform machinery (handoff §10):

- surface inbox exceptions at the fleet level, not just open investigations (B)
- keep `summary.committing` consistent with the worker-level declaration (D)
- a refusal-rate advisory when refusals are at or near 100% (C)
- expiry / re-confirmation prompts for `mechanically_verifiable: false`
  confirmations whose referent data may change (D)

These are exactly "a supervisor noticed something worth measuring → candidate
deterministic platform measurement." The loop is visible before any code is
written or promoted. None of them was auto-promoted (the supervisor cannot change
the fleet); they are suggestions to the operator, as required.

## What it did NOT do

- It never compared the two confirmations in D to surface the **cross-worker
  recurring pattern** ("the fleet repeatedly depends on human-held facts that
  vanish on version change"). It surfaced the expiry concern per-worker. The
  cross-worker pattern is precisely the step that needs computation over the
  snapshot — and it did not compute. This links the no-Python finding to the
  Reflector hypothesis: the Reflector's strongest signal may require the bench.
- It never asked a clarifying question back to the operator. Every run ended in
  statements. Whether the supervisor should ever *ask* (mixed initiative) is an
  open question S1 did not settle.

## What this tells us to do next

1. **S2 is well-motivated and well-shaped as specified.** The boring-case
   over-reporting is the clearest failure: have the operator dismiss the dry-run
   "concern" and the thin-history "concern" as non-issues, record that in a
   journal, and test whether the supervisor later suppresses by-design noise
   while still surfacing a real failure. The architecture-misread (enrichment is
   non-committing) is the exact kind of correction the journal should record.
2. **Before S4, build a stimulus that forces computation.** A snapshot large
   enough — or a question sharp enough — that the answer is not readable at a
   glance. Until then the bench is untested.
3. **Seed the first Rulebook learned-practice rules from this run:**
   - enrichment/aggregation/reconciliation are non-committing by design;
   - a completed run with refusals is healthy;
   - (from B) inbox exceptions and open investigations are both "needs attention,"
     but they are different kinds of attention.

The goal of this round was to come back with four preserved model runs and be
able to say *here is what the LLM actually did*. It did useful supervision on B
and C, caught two real fleet defects, surfaced a Reflector signal on D, and
over-reported on A. The bench was not reached. S2 is designed from those
failures and surprises.