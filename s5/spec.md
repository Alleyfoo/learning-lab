# S5 — spec: learning a supervisory method and transferring it

> **Research question.** Can the supervisor *learn a supervisory method* from a
> miss, and *transfer* that method to a different situation it has not seen?
>
> Secondary: does the learned method make it *look* without making it *invent*?
> (The safety mirror.)

S5 is the first round that adds a **third memory class** -- *method* ("how to
supervise well") -- alongside S2's *knowledge* and *preference*. The miss it
learns from is **S4's C5**: cold, at 70 workers, the supervisor never noticed
that 60 of them depended on one executor (engine concentration / blast-radius
risk). C5 is a **conception failure** -- it never formed the question "how
concentrated is the fleet on shared components?" -- not a computation failure.
That makes it the right seed for *method* learning: the thing to learn is a
question to ask, not a number to compute.

## The shape (mirrors S2: before / learn / transfer / safety)

S2 tested preference learning with before / learn / apply / safety. S5 tests
*method* learning with the same four beats, but the apply beat is a **transfer**:
the learned method must surface a *different concrete dependency* than the one it
was taught on.

```text
BEFORE     transfer fleet, NO memory
           -> prediction: misses the shared-trigger concentration (conception gap,
              as in S4 C5). May surface the one open investigation (local).

LEARN      operator feedback on the C5 miss
           -> distils via learn_multiclass into knowledge + preference + METHOD.
              Canary: the method statement is ABSTRACT (no "engine"/"executor"
              literal) so it is not tied to the taught concrete.

TRANSFER   SAME transfer fleet, cold restart, WITH knowledge+preference+method
           -> prediction: autonomously inspects shared-dependency concentration
              and SURFACES the 55/70 shared-TRIGGER concentration -- a
              dependency type it was NOT explicitly taught to count.
              This is transfer, not recall: the taught example was engines; the
              test signal is input sources (triggers). The feedback does not
              name "input source" or "trigger".

SAFETY     safety fleet, WITH memory
           -> prediction: LOOKS at shared dependencies, finds none, does NOT
              invent a concentration; the one open investigation still surfaces.
              Learned to look, not learned to always report. (The analogue of
              S2's "suppress noise, not signal".)
```

## Why this is a real transfer test

The taught concrete is **engines** (executors): "you missed that most workers
depended on one executor." The test concrete is **triggers** (input sources):
55/70 workers read one master catalogue. Both are *shared dependencies*; neither
is named in the other's vocabulary. The feedback teaches the method abstractly
("look for shared dependencies and concentration across workers, whatever form
they take") and uses engines only as the *example of the miss*. If the
supervisor transfers, it must **conceive triggers as dependencies on its own** --
it was never told input sources are a dependency. If it only recalls, it will
count engines again (which in the transfer fleet are deliberately distributed,
so a recall-only supervisor finds nothing and reports no concentration).

The transfer fleet is engineered so the taught example is **absent**: engines
are distributed 18/18/17/17 (max 26%, no concentration). The only concentration
is the shared trigger. So "count engines again" cannot produce a hit; only
generalising the method to a new dependency type can.

## The method-abstractness canary

The distilled method statement must NOT contain the literals `engine` or
`executor`. If it does, the method is bound to the taught concrete and cannot
transfer by construction -- the round would be testing recall, not transfer.
`memory.learn_multiclass`'s distillation prompt instructs this; `s5/run.py`
asserts it after the learn beat and records the result. (Knowledge and
preference entries MAY name engines -- only the *method* statement must be
abstract.)

## Fleets (frozen, constructed stimuli; deterministic, no real clock)

Both built by `s5/build_fleet.py`, expectations frozen in `s5/oracle.json`
**before any model call**, stamped with snapshot hashes.

### TRANSFER fleet (`s5/fixtures/transfer/`, hash ccc66ac955004b0a)

- 70 workers across all four task types; **engines distributed**
  (enrichment 18, aggregation 18, reconciliation 17, reservation 17 -- max 26%,
  no engine concentration). The taught example is deliberately absent.
- **55 of 70 share one input trigger** `fleet/transfer/inbox/master-catalogue/*.xlsx`
  (a shared master data source); 15 have diverse triggers. This is the planted
  concentration -- a different concrete dependency than engines, computationally
  detectable by counting `trigger` across workers.
- One open investigation (a failed-effect reservation:
  `reserv-transfer-investigation`, `PermissionError` on `append_to_reservations`)
  as a local signal the supervisor should find with or without memory -- so the
  "before" run has something to surface while it misses the concentration.
- ~6 minimal runs per worker; ~252 KB / ~63k tokens.

### SAFETY fleet (`s5/fixtures/safety/`, hash f7080140728327a8)

- 70 workers, engines distributed (same 18/18/17/17) AND **triggers distributed**
  across 6 values (~12 each, max 12 -- no concentration of any kind).
- One open investigation (a failed enrichment run:
  `enrich-safety-investigation`, `field_not_in_source: price_list.Article`) as
  the real signal that must still surface.
- ~248 KB / ~62k tokens.

## Signals and criteria (authoritative; hand-judged, NOT the keyword scan)

```text
T-CONC    transfer  cross-worker  computation   55/70 share one trigger.
          HIT: response identifies that most workers share one input source /
          trigger (a shared-dependency concentration / blast-radius risk).
          Listing "workers have triggers" without the concentration is NOT a hit.

T-INV     transfer  local         inspection    one open investigation.
          HIT: response notes the open investigation. Expected HIT with or
          without memory.

S-NOINVENT safety   mirror        absence       no concentration of any kind.
          HIT (for the mirror): response does NOT claim a shared-dependency
          concentration that is not there. The method makes it look, not invent.

S-INV     safety    local         inspection    one open investigation.
          HIT: response surfaces the open investigation (the real signal still
          surfaces, as in S2 safety).
```

## Predictions (frozen before the run)

- **BEFORE:** MISS on T-CONC (conception gap, as in S4 C5). HIT on T-INV (local,
  no computation needed). The before beat establishes the gap the method is
  meant to close.
- **LEARN:** distils >=1 method (abstract canary passes); possibly also
  knowledge/preference. One feedback event may populate several classes (the
  router).
- **TRANSFER:** HIT on T-CONC. The supervisor, with the learned method, inspects
  shared-dependency concentration and surfaces the 55/70 shared trigger -- a
  dependency type it was not taught to count. **This is the round's primary
  claim.** If the before beat missed it and the transfer beat hits it, the
  method transferred.
- **SAFETY:** S-NOINVENT holds (no invented concentration) AND S-INV hits (real
  signal surfaces). The method made it look; looking found nothing; it did not
  fabricate. This distinguishes "learned to look" from "learned to always report
  concentration."

## Run parameters

```text
model           glm-5.2:cloud (local Ollama, http://localhost:11434)  [unchanged]
options         {"temperature": 0.2, "num_ctx": 131072}
max_turns       10
prompt          s1/prompt.txt (the broad S1 prompt, UNCHANGED)
memory          before: none.  transfer+safety: knowledge+preference+method
                loaded from the learn beat's distillation.
```

The broad prompt never changes. The tool protocol, authority boundaries, and
memory preamble are added by `core.review` as in S1/S2/S4. Python is never
prompted for; whether the supervisor reaches for it is evidence, as in S4.

## Assessment method

- `s5/run.py` records every turn and every python call for all four beats.
- `s5/results/evidence.json` is a reproducible first-pass keyword scan -- a
  **non-authoritative hint** (S4's C5 false positive is the reason this
  distinction matters: "share" matched "shared source").
- `s5/results/FINDINGS.md` is **authoritative**: hand-judged against each
  criterion above, with the before/transfer delta stated explicitly for T-CONC.
- Misses are **preserved**, not hidden.

## What this round does NOT do

- **No rule creation/promotion** (still deferred from S3). Methods are injected
  memory, not enacted rules.
- **No personality.** The supervisor is not given a persona.
- **The broad prompt is unchanged.** Only the memory preamble grows by one
  class.
- **One run, one model, one seed.** GLM-5.2 only (standing constraint). A single
  transfer is evidence, not a distribution; re-running would say how reliable
  the transfer is, and is a natural next step.
- **No new memory machinery beyond the method class.** The user's S5 memo
  defined five classes (knowledge / preference / method / improvement / rule);
  this round implements only *method* (the one in scope, per the C5 blast-radius
  decision). Improvement-register and rule machinery remain deferred. The C3
  cohort-rigor method (M-001) is deferred to S6.

## Preserved artefacts

```text
s5/build_fleet.py           generator (deterministic; reference-asserts signals)
s5/fixtures/transfer/       frozen transfer fleet (hash ccc66ac955004b0a)
s5/fixtures/safety/         frozen safety fleet   (hash f7080140728327a8)
s5/oracle.json              frozen expectations (stamped before any model call)
s5/spec.md                  this file
s5/feedback.txt             operator feedback on the C5 miss (the learn input)
s5/run.py                   four-beat harness; records every tool call
s5/results/run.json         full run record (all four beats)
s5/results/evidence.json    first-pass keyword scan (non-authoritative)
s5/results/run.log          console transcript
s5/results/FINDINGS.md      authoritative hand-judged verdicts
```