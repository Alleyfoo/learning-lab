# S4 — spec: scale, supervision, and the unprompted Python bench

> **Research question.** When a fleet snapshot is too large to read by
> inspection, does the supervisor *autonomously* reach for computation (the
> Python bench, which is available but never prompted), and *what* does it
> choose to compute?

S1 asked "what does the supervisor notice?" S2 added memory. S3 added a
rulebook. **S4 changes none of that.** It runs the supervisor **cold** — no
memory, no rulebook, no personality — with the **broad S1 prompt unchanged**,
over a fleet sized so the important findings are cross-worker and cannot be
eyeballed. The only new variable is *scale*.

## What is held frozen

- **The prompt.** `s1/prompt.txt`, verbatim. Not adapted to scale, not hinted
  about Python, not told what to look for.
- **The supervisor core.** `supervisor/core.py` unchanged. The bench is
  described as *optional*; nothing nudges the model toward it.
- **The model.** `glm-5.2:cloud` via local Ollama (standing constraint).
- **No memory, no rulebook.** `knowledge=None`, `preferences=None`. S2/S3
  machinery is absent — this is a cold reading.

## What is NOT in scope (deliberately deferred)

- No rule creation or promotion (still deferred from S3).
- No new memory machinery, no personality, no output schema.
- No fixing the two known fleet defects (pending_exceptions / summary.committing)
  — they stay recorded, and one of them is *planted at scale* as signal C6.

## The stimulus: a frozen, constructed fleet

`s4/fixtures/fleet/` is **not** a live fleet and not real execution. It is a
generated, frozen fixture (the same approach as the S1 conditions), shaped
exactly as `supervisor.snapshot.build` reads it. The generator
(`s4/build_snapshot.py`) is deterministic: no real clock (timestamps run from a
fixed epoch), no randomness. Running it twice yields the same bytes and the same
snapshot hash.

Scale (as built):

```text
workers                 70
runs                    473
promotions              17
confirmation-bearing    29  (10 stale on an older version, 19 fresh)
inbox-bearing           21
enrichment : reservation 60 : 10  (86% on one engine)
snapshot (pretty JSON)  ~308 KB  (~77k tokens)
snapshot hash           a38f6a5a1382ab03
```

> **Why 70, not 100.** An initial 100-worker design produced a ~508 KB / ~127k
> token snapshot, which would leave almost no context for the supervisor's
> multi-turn computation inside a 128k-token window. The count was reduced so
> the *full* snapshot fits with ~50k tokens of headroom for turns. 70 workers
> with ~473 runs and seven planted cross-worker signals is still far beyond
> inspection — the cross-worker findings require computation. This reduction is
> a validity adjustment, recorded here, not a quiet change.

## Expectations frozen BEFORE any model call

`s4/oracle.json` is written by the generator and stamped with the snapshot hash
*before* the supervisor runs. The supervisor is assessed against it; **misses
are preserved, not hidden.** Seven signals are planted:

### Local (readable by inspecting one worker — expected HIT even without Python)

| id | location | what it is |
|---|---|---|
| **L1** | `reserv-acme-failed-effect` | a reservation worker whose last run was accepted but the effect failed (`effect_applied=false`, `ok=false`), with an OPEN investigation → in `pending_exceptions`. |
| **L2** | `enrich-fazerish-open-inv` | an enrichment worker with a failed run (`field_not_in_source: price_list.Article`) and an OPEN investigation → in `pending_exceptions`. |

### Cross-worker / time-series (require computation — the real test)

| id | location | what it is | hit criterion |
|---|---|---|---|
| **C1** | 8 `northwind-orders-*` | refusal rate climbs from 0 to 5/10 over each worker's run history — a shared upward trend. Data quality degrading over time. | names the *rising refusal trend over time* in the Northwind cohort, not just "some workers have refusals". |
| **C2** | 5 `promo-regress-*` | promoted to v2; the *current* version refuses ~8/10 rows every run, the prior version refused 0. A post-promotion regression cluster. | identifies that *recently promoted* workers' current versions refuse many rows, as a cluster. |
| **C3** | 10 `confirm-stale-*` | a confirmation bound to v1 while `current_version` is 2 — a human-held fact never re-confirmed for the current version. | identifies confirmations bound to an *older version* than current, as a cross-worker pattern. |
| **C5** | fleet-wide | ~60 of 70 workers share one engine (`execute_enrichment.py`). | notes the disproportionate concentration on one shared engine. |
| **C6** | 6 `hidden-exception-*` | an inbox exception file + a failed run, but NO open investigation → absent from `pending_exceptions`. The fleet view reports 2 pending exceptions while 8 workers have exceptions. | identifies that some inbox exceptions are *not* reflected in fleet-level `pending_exceptions` (the visibility gap). This is D-001 at scale. |

C6 is the S1 fleet defect `pending_exceptions` (which misses inbox exceptions),
planted across six workers so it is a *pattern*, not a one-off — and so the
supervisor must *count across workers* to find it, exactly the kind of thing
inspection cannot do.

### Reference assertions

The generator asserts, after building, that **every planted signal is
computationally detectable from the snapshot** (it re-derives each one the way a
correct Python analysis would). A miss in the supervisor's run is therefore the
supervisor's failure, not a planting bug. These assertions must pass before the
model is run.

## Run parameters

- `options = {"temperature": 0.2, "num_ctx": 131072}` — large context for the
  full snapshot plus turns.
- `max_turns = 10` — room for several compute-then-read cycles.
- No memory (`knowledge=None`, `preferences=None`).
- Every turn is recorded: assistant text, each ```python block, its
  stdout/error/refusal, and the final prose response.

## Assessment

For each signal the verdict is **HIT / PARTIAL / MISS**, with evidence drawn
from the final response and the turn transcripts. `s4/run.py` performs a
scripted first-pass evidence scan (names + signal-specific terms) and saves it
alongside the raw run; the authoritative verdict is hand-judged in
`s4/results/FINDINGS.md` against the *criterion* above (so "lists some
refusals" is not credited as C1 — the *trend* is the finding).

The primary research question is answered not by the hit count alone but by
**whether and how the supervisor used the bench**: did it reach for Python at
all, what did it compute, and did computation surface the cross-worker signals
that inspection could not? A run that hits L1/L2 by inspection but misses
C1–C6 while never touching Python is itself a clean result: scale did not, on
this run, trigger computation.

## Preserved artefacts

```text
s4/build_snapshot.py        generator (deterministic; reference-asserts signals)
s4/fixtures/fleet/          the frozen fleet (read by supervisor.snapshot.build)
s4/oracle.json              frozen expectations (stamped with snapshot hash)
s4/spec.md                  this file
s4/run.py                   run the cold supervisor, record every tool call
s4/results/run.json         the full run record (turns, python calls, final)
s4/results/evidence.json    scripted first-pass evidence scan vs oracle
s4/results/FINDINGS.md      hand-judged verdicts + the computation narrative
```