# S4 — findings: scale, supervision, and the unprompted Python bench

> **Research question.** When a fleet snapshot is too large to read by
> inspection, does the supervisor *autonomously* reach for computation (the
> Python bench, available but never prompted), and *what* does it choose to
> compute?

S4 runs the supervisor **cold** — no memory, no rulebook, no personality — with
the **broad S1 prompt unchanged**, over a frozen 70-worker fleet (473 runs, 17
promotions, 29 confirmation-bearing workers, ~308 KB / ~77k tokens of snapshot).
The only new variable is *scale*. Expectations were frozen in `s4/oracle.json`
(stamped with the snapshot hash) **before** any model call.

## Headline

**Yes — the supervisor reached for computation on its own, and the computation
was what surfaced the cross-worker findings inspection could not.** With a prompt
that never mentions Python, it made **4 Python bench calls across 3 turns**,
errored, recovered, and produced a final report that hit **6 of 7** planted
signals. The one miss (engine concentration) is preserved below.

```text
python_used          True
python_call_count    4   (turn 0: 1 ok + 2 err;  turn 1: 1 ok)
turn_count           3
stop_reason          final (plain prose, no code block)
```

Authoritative verdicts (hand-judged against each criterion, NOT the generous
first-pass keyword scan in `evidence.json`):

```text
L1  failed-effect reservation + open investigation        HIT
L2  failed enrichment run + open investigation            HIT
C1  Northwind cohort: refusal rate rising over time       HIT  (computed trend)
C2  post-promotion regression cluster                     HIT  (computed before/after)
C3  stale confirmations bound to v1, current v2           HIT  (computed date gap)
C5  engine concentration (60/70 on one executor)          MISS
C6  hidden inbox exceptions absent from pending_exceptions HIT  (computed set difference)
```

## What it chose to compute (the primary research variable)

The bench runs in a fresh restricted namespace per call — only `snapshot` is
bound; `json`, `math`, `re`, `collections`, `pandas` are available; nothing
else. The model was never told any of this in the prompt; `core.py`'s tool
protocol describes it. Its four calls:

**Turn 0, call 1 (ok).** A cross-worker *status categorization* — the thing
inspection cannot do at 70 workers. It flagged every worker by
`EXCEPTION` / `OPEN_INVESTIGATION` / `EXCEPTION_NO_INVESTIGATION` and by recent
refusal load (`REFUSALS_recent5`), then dumped detail for each exception worker
(investigation state, last-run problems, inbox `exception_files`). This single
sweep surfaced the `hidden-exception-*` cluster (all flagged
`EXCEPTION_NO_INVESTIGATION`) and the `northwind-orders-*` / `promo-regress-*`
refusal clusters in one pass.

**Turn 0, calls 2 & 3 (err).** Both failed with `NameError: name 'workers' is
not defined`. In call 1 the model had bound `workers = snapshot["workers"]`; it
then assumed that binding *persisted* into the next bench call. It does not —
each call is a fresh namespace. This is a genuine tool-use error, not a planted
one, and it recovered (see turn 1).

**Turn 1, call 1 (ok).** It re-bound `workers = snapshot["workers"]` and ran
five targeted computations:

1. **promo-regress before/after promotion** — `v1(5 runs, 0 refused) -> v2(5
   runs, 40 refused)` for all five. (C2.)
2. **northwind refusal trend, chronological** — `[0,0,0,0,0,0,0,1,2,3,4,5]` for
   all eight. (C1.)
3. **confirm-stale confirmation date vs promotion date** —
   `confirmed v1 @ 2026-01-16, promoted v2 @ 2026-02-05`. (C3.)
4. **hidden-exception investigation status** — all six `last_status=exception,
   investigation=none, inbox exception_files=1`. (C6.)
5. **the set difference** — `actual_exc - pe_workers` = the six
   `hidden-exception-*` workers in exception state but NOT in
   `pending_exceptions`. (C6 — the D-001 visibility gap, quantified.)

**Turn 2.** Plain prose final response, no code block. Run ends on `final`.

So the computations it chose were: a fleet-wide status sweep, two per-worker
time-series/segmented refusal comparisons, a confirmation-vs-promotion date
comparison, and a set difference between actual and reported exceptions. It did
**not** count workers per engine.

## The signals, judged

### L1 / L2 — local (HIT, by inspection + the sweep)

Both open investigations appear in `pending_exceptions` and were surfaced by the
turn-0 sweep (`OPEN_INVESTIGATION`). The final report lists them under "Two open
investigations still unresolved": `enrich-fazerish-open-inv`
(`field_not_in_source: price_list.Article`) and `reserv-acme-failed-effect`
(`PermissionError` on `append_to_reservations`). Expected HIT without
computation; confirmed.

### C1 — Northwind refusal trend (HIT, computed)

It extracted the chronological refusal series for all eight workers and the
final report names the *trend*, not just "some refusals":

> "an identical, steadily increasing refusal pattern: 0 refusals for the first 7
> runs, then climbing by exactly 1 per run to the current 5 out of 10 rows
> refused. This synchronized trend across all eight workers points to a shared
> source — the Northwind price list catalogue is losing article coverage over
> time."

It went beyond the criterion and inferred a shared cause. This is exactly the
finding that requires reading a per-worker time series across a cohort.

### C2 — post-promotion regression (HIT, computed)

It computed the before/after-promotion refusal delta for all five
(`v1: 0 -> v2: 40`) and reported the cluster as a regression:

> "before promotion, zero refusals across all v1 runs. After promotion, 8 out of
> 10 rows refused every single run... The promotion likely introduced a
> regression and should be reviewed."

A cross-worker finding that requires correlating a promotion with a current-
version refusal rate — not eyeballable.

### C3 — stale confirmations (HIT, with a rigour note)

It computed the confirmation-date vs promotion-date gap for `confirm-stale-01`
(`break` after one) and reported all ten:

> "All ten `confirm-stale-*` workers carry an operator-held fact... confirmed...
> against version 1. They were promoted to version 2... but the confirmations
> were never re-confirmed against the new version."

**Rigour note.** It computed the gap for *one* worker and generalised to ten
without iterating. Here the generalisation is correct (all ten share
`confirmation.version=1`, `current_version=2`), but it did not verify that — a
sampled-then-assumed step. Credited HIT because it identified the cross-worker
pattern and named all ten; flagged because a stricter run would have iterated.

### C5 — engine concentration (MISS, preserved)

The supervisor **never surfaced engine concentration**. The first-pass scan in
`evidence.json` marked C5 "HIT" — that is a **false positive**: it matched the
substring "share" inside "a **shared** source" in the C1 section, which is about
a data source, not the executor. Hand-judged, C5 is a clean MISS. 60 of 70
workers share `execute_enrichment.py`; the supervisor did not count workers per
engine and did not mention concentration. This is the simplest cross-worker
count in the set, and the one it skipped — a real, preserved miss, not hidden.

### C6 — hidden inbox exceptions / D-001 at scale (HIT, computed — the headline)

It computed the set difference `actual exceptions - pending_exceptions` and led
the report with it:

> "Six `hidden-exception-*` workers are in active exception state but have
> `investigation: "none"` and are absent from the `pending_exceptions` list...
> The system reports only 2 pending exceptions, but 8 workers are actually in
> exception state."

This is the S1 fleet defect `pending_exceptions` (which misses inbox exceptions
when no formal investigation is opened), planted across six workers so it is a
*pattern*. Cold, with no memory of S1/S2/S3, the supervisor re-derived it at
scale **and proposed its remedy** as a system improvement:

> "The system should surface all workers with `last_status: "exception"`
> regardless of investigation state — the current filter misses silently failing
> workers."

## Two system improvements it re-derived cold

The final report's "System improvement suggestions" are unprompted and worth
recording, because both independently reproduce earlier rounds' findings without
any memory of them:

1. **"Fix the exception-tracking gap"** — this *is* D-001's remedy, the defect
   S1 found and S2/S3 carried. Re-derived from the fleet state alone.
2. **"Re-confirmation after promotion"** — this *is* the S3 **T4** mirror
   proposal (prompt re-confirmation on promotion because confirmations do not
   carry forward). S3 registered T4 against rule `R-CONFIRM-VERSION`; S4's
   supervisor, with no rulebook, reinvented T4 from the stale-confirmation
   pattern.
3. **"Refusal-rate alerting"** — a new synthesis from C1+C2: alert on refusal-
   rate trends, not just exceptions.

The supervisor did not know about D-001, R-CONFIRM-VERSION, or T4. It
reconstructed the same conclusions from scale. (This is descriptive, not a claim
of generality — one run, one seed, standing constraint.)

## What this round does NOT do

- **No rule creation or promotion** (still deferred from S3). The supervisor's
  improvement suggestions are suggestions to the operator, not enacted.
- **No memory, no rulebook, no personality.** Cold run. S2/S3 machinery absent.
- **One run, one model, one seed.** GLM-5.2 only (standing constraint). A single
  run is evidence, not a distribution — re-running would say something about
  variance, and is a natural next step.
- **The first-pass scan is not the verdict.** `evidence.json` is a reproducible
  keyword hint; the authoritative verdicts above are hand-judged (the C5
  false positive is the reason this distinction matters).

## Observations

- **Scale triggered computation, and computation found the cross-worker
  signals.** C1, C2, C3, and C6 were all *computed* (time series, before/after,
  date gap, set difference), not eyeballed. The local L1/L2 were read from the
  sweep. The one cross-worker count it did not perform (C5) was the one it
  missed.
- **It erred and recovered.** The `NameError` calls show genuine iterative tool
  use: it assumed bench state persisted, was corrected by the error, re-bound
  the variable, and continued. Not a canned answer.
- **The miss is the cheap count.** It reached for *analytic* computations
  (trends, regressions, gaps) but did not reach for the *trivial* count
  (workers per engine). Suggests the bench is triggered by an analytic question
  the model forms, not by "summarise the fleet" — and engine concentration was
  not a question it thought to ask.
- **It generalised from a sample once (C3).** A minor rigour gap: it computed
  one confirm-stale worker and asserted all ten. Correct here; worth watching.

## Preserved artefacts

```text
s4/build_snapshot.py        generator (deterministic; reference-asserts signals)
s4/fixtures/fleet/          the frozen fleet (hash a38f6a5a1382ab03)
s4/oracle.json              frozen expectations (stamped before the model call)
s4/spec.md                  frozen experiment spec
s4/run.py                   cold run harness; records every tool call
s4/results/run.json         full run record: 3 turns, 4 python calls, final response
s4/results/evidence.json    first-pass keyword scan (non-authoritative; C5 false +)
s4/results/run.log          console transcript
s4/results/FINDINGS.md      this file (authoritative hand-judged verdicts)
```

## Next

S4 is frozen as-is. Natural next steps, in order of dependence:

1. **Variance.** Re-run S4 a few times (same frozen fleet, same cold prompt) to
   see whether the bench use and the C5 miss are stable or run-to-run. One run
   answered the primary question; a handful would say how reliably.
2. **Prompt the count?** If the C5 miss is stable, test whether a *minimal*
   nudge ("consider fleet composition") surfaces it — without changing the broad
   prompt's supervision framing. This separates "didn't think to ask" from
   "can't compute it".
3. **Re-introduce memory/rulebook at scale.** Now that cold scale works, add S2
   memory and the S3 rulebook back and ask whether they change what gets
   surfaced or proposed — e.g., does the rulebook suppress the (correct) T4
   re-confirmation proposal, or does knowing R-CONFIRM-VERSION sharpen it?
4. **Rule creation/promotion at scale** (the deferred S3 mechanism), now with
   enough volume to test rule-interaction conflicts and duplicate drift.