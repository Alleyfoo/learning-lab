# S2 — findings: can correction and preference change supervision?

> **Research question.** Can this LLM become a better supervisor through
> experience, without changing the workers underneath it?

S1's failure was reframed: the supervisor did not mainly lack memory, it lacked
**meaning** — it misread real fleet fields (`committing:false` → "dry-run mode";
`ledger_lines:2` vs `rows:3` → "dropped data"). S2 splits the fix into two
classes that must not collapse into one memory, and tests whether they
**transfer** to a worker the supervisor has never seen, without blunting real
failure.

## Headline

**All three predictions pass.** A two-line system-knowledge store and a
one-line operator-preference store, loaded verbatim into the prompt, changed the
supervisor's behaviour on a *different* healthy enrichment worker it had never
seen — and did not suppress a genuine effect failure.

```text
PREDICTION                            RESULT
correction -> changes interpretation  PASS  (dry-run + ledger-vs-rows gone, on a new worker)
preference -> changes threshold       PASS  (thin-history + unexercised-refusal gone, on a new worker)
neither     -> keeps real failure      PASS  (B's PermissionError led the safety review)
```

## The four runs

All runs use the frozen S1 broad prompt (`s1/prompt.txt`), `glm-5.2:cloud`, six
turns max, bench available but never prompted. Python was unused in every review
(0/3) — consistent with S1's 0/4; the bench is not reached at this snapshot
scale (deferred to S4).

| step | worker | memory | turns | python | outcome |
|---|---|---|---|---|---|
| before | fazerish-invoicing (S1-A) | none | 1 | no | reproduced all four misreads |
| learn | — (distillation) | — | — | — | 2 knowledge + 1 preference |
| transfer | acme-order-cost (NEW) | 2+1 | 1 | no | calm; memory invoked by name |
| safety | room-reservation (S1-B) | 2+1 | 1 | no | led with the failed effect |

### 1. Before — reproduced the misreads (no memory)

On `fazerish-invoicing` with no memory, the supervisor raised exactly the four
concerns the operator feedback targets:

1. **dry-run misread** — "The worker is not committing (`committing: false`)…
   If dry-run/observation mode is intentional, then this is fine — but it's
   worth confirming the intent." By-design non-committing enrichment framed as a
   mode whose intent needs confirming.
2. **ledger-vs-rows misread** — "`ledger_lines: 2` but `items_seen: 1`… worth a
   quick sanity check to make sure the ledger isn't double-counting lifecycle
   states." Comparing ledger lifecycle lines to item counts and suspecting a
   bug.
3. **thin-history advisory** — "Very thin run history — only one run, ever…
   I'd treat this as still in validation rather than proven production."
4. **unexercised-refusal advisory** — "With only 3 rows processed and 0
   refusals, none of those guardrails have been exercised yet… the
   matching/quality logic is untested against bad data so far."

This is the baseline the feedback is meant to correct.

### 2. Learn — distilled into two classes correctly

`memory.learn(feedback)` classified the frozen operator feedback into:

- **knowledge.jsonl** (2 entries, basis `operator_correction`)
  - "Enrichment workers are non-committing by design." — scope `{task_type: enrichment}`
  - "Ledger lines are not output rows and their counts should not be compared." — scope `{applies: inbox_ledger}`
- **preferences.jsonl** (1 entry, basis `operator_feedback`)
  - "Do not warn merely because a new healthy worker has little history or hasn't exercised every refusal condition." — scope `{applies: supervision}`

Classification is correct: the two system facts landed in knowledge, the
supervision-taste item landed in preferences, and the two files are separate.

**Observation — distillation granularity.** The distiller merged the two
distinct preference ideas (thin history, unexercised refusals) into a single
statement, where the self-test stub had split them. It was sufficient here —
the merged statement suppressed both in the transfer run — but it shows
distillation is not guaranteed to put each distinct idea in its own entry. For
Memory v0 this is acceptable; if later rounds need per-idea granularity, the
distillation prompt can require one idea per entry.

### 3. Transfer — memory applied, not recalled (PASS)

Cold restart: conversation context wiped, memory reloaded from disk, and the
supervisor reviewed **`acme-order-cost`** — a genuinely different worker
(different name, customer `Acme Oy`, purpose; same clean shape: non-committing
enrichment, inbox ledger, one run, zero refusals). It responded:

> "Everything in this fleet looks healthy and there is nothing that requires
> your attention. … `acme-order-cost`, enrichment task, **non-committing by
> design**. … the inbox reports 2 ledger lines… **ledger lines are not output
> rows, so there is nothing to reconcile** against the 3 enriched rows. … newly
> established with only one run, but **per your preferences I am not treating
> that as a concern** since it is healthy and functioning as designed. No
> action needed."

Three things make this a clean pass rather than a lucky quiet answer:

- The supervisor **named the knowledge** ("non-committing by design", "ledger
  lines are not output rows") — exact phrasing from the two knowledge entries —
  on a worker it had never seen. That is *application*, not recall of worker X.
- It **named the preference** ("per your preferences I am not treating that as
  a concern") — explicitly citing the operator-preference store as the reason
  it stayed quiet about the single run.
- It **did not raise** the unexercised-refusal advisory (zero refusals noted
  calmly, not flagged as "untested guardrails").

All four before-concerns are gone, on a different worker, from disk-loaded
memory. That is the strongest form of the S2 claim.

### 4. Safety — real failure still surfaces (PASS)

Same memory loaded, now the S1-B fixture (`room-reservation`, effect failure).
The supervisor led with:

> "## Action required: PermissionError on the last run
> The most recent run (`req-005.json`…) failed with a `PermissionError` when
> the worker tried to append to its reservations file… the reservation for
> 2026-05-05 was **not persisted**. … fix the filesystem permissions on that
> `reservations.json` file… then reprocess `req-005.json`."

The correction ("non-committing is fine") and the preference ("don't nag about
thin history") did not blunt a genuine operational failure: the failed effect
led the review, with the concrete cause and a concrete fix. Memory suppresses
*noise*, not *signal*.

**Bonus — a pre-existing discovery re-surfaced.** The safety review also noted:

> "top-level `pending_exceptions` is empty despite an exception in the inbox…
> it may be worth investigating whether the exception is being tracked at the
> fleet level as intended."

This is the same defect recorded in `s1/discoveries.jsonl` as **D-001**
(`pending_exceptions` misses inbox exceptions), which S2 deliberately did not
fix. The supervisor independently re-surfaced it under memory — confirming the
improvement-box experiment (S3) has real, pre-existing material to encounter,
and that operator preferences did not train it to ignore genuine defects.

## What this round does NOT show

- **No retrieval, no scoring, no decay.** Memory v0 loads every line verbatim.
  Ten lines is a luxury; whether the approach survives tens or hundreds of
  lines is an S3/S4 question, not answered here.
- **No Rulebook.** The two knowledge entries are operations-manual facts, not
  learned-practice conflict rules. Rulebook (e.g. "carry confirmations v1→v2"
  vs "confirmations are version-bound") is still held for S3.
- **No bench use.** Python was unused in all three reviews (0/3). The bench is
  available but never prompted; reaching it likely needs a much larger
  snapshot (S4: ~100 workers, ~2000 runs).
- **Single distillation sample.** Granularity (merged preferences) is observed
  once; not yet a pattern.
- **One model.** GLM-5.2 only, per the standing constraint (do not rerun S1 on
  another model).

## Preserved artefacts

```text
s2/results/before/run-*.json       baseline, no memory (misreads reproduced)
s2/results/learn.json              distillation record (2 knowledge + 1 preference)
s2/results/transfer/run-*.json     cold restart + memory, new worker (PASS)
s2/results/safety/run-*.json       cold restart + memory, effect failure (PASS)
s2/results/run.log                 console transcript of the four-step run
supervisor/knowledge.jsonl         2 entries, basis operator_correction
supervisor/preferences.jsonl       1 entry,  basis operator_feedback
```

## Next

S2 is frozen as-is. The natural next experiment is **S3 — the improvement box**:
give the supervisor the two pre-existing fleet discoveries
(`s1/discoveries.jsonl` D-001, D-002) plus the one it re-surfaced here, and ask
whether it can reason about *fixing the system* (not just supervising it) — and
whether a Rulebook for conflict detection (e.g. confirmation versioning) becomes
necessary at that point. S4 remains the large-snapshot/bench-reached round.