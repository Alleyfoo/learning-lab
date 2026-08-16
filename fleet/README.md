# Fleet

An operations console over established workers. No new task semantics, no input
adapters, no exception classes — it reads what the existing workers and
executors already produce.

```bash
python fleet/seed.py            # build fixture state by RUNNING the workers
python fleet/fleet.py --self-test
streamlit run fleet/app.py
```

## Layout

```text
fleet/workers/<name>/
  worker.json        purpose, task type, where its data lives
  versions/vN.json   the model as established. Never edited, never deleted
  history.jsonl      append-only: what was established, when, and why
  runs.jsonl         append-only: one line per run, TAGGED WITH ITS VERSION
  investigation.json present while an exception is unresolved
  last_packet.json   the deterministic exception packet, if there was one
```

## Two distinctions the console is built around

**A completed run is not an accepted outcome.** `orders-enrichment` refuses 8
rows across 4 healthy runs; `room-reservation` declines 4 of 5 requests. Neither
is a fault — those are workers applying their own declared policies. Rendering
them as failures would send an operator chasing healthy behaviour.

**A version's runs belong to that version.** Promoting appends; it never
restates what an earlier version did. This is `scripts/agent_binding.py`'s rule
— adopting now certifies nothing about a past run — and the self-test canaries
that v1's model, runs and history are byte-identical after a promotion.

## Two execution paths

**Preview stays non-committing.** `builder.preview` executes deterministically
and reports; it writes nothing. That is what the modeller uses and it must stay
safe to run against anything.

**`worker/runtime.py` is the committing path**, derived from
`calendar_job/unattended.py`: the executor returns the state as it *would*
stand and writes nothing, and persisting is the runtime's act, on acceptance
only. A worker takes it when it declares an effect and its task has a committing
runtime (`Worker.committing`).

### Three outcomes, not two

```text
REFUSED by policy          healthy. No effect attempted -- `effect_applied` is
                           None, because "not attempted" and "attempted and
                           failed" are different facts. State unchanged.
ACCEPTED, effect applied   healthy. State changed, and it was VERIFIED to have
                           changed by re-reading from disk.
ACCEPTED, effect FAILED    EXCEPTION. A decision was made, something downstream
                           is entitled to believe it, and the world does not
                           reflect it.
```

Applied means verified. A write that returned quietly and did not land is the
dangerous case, so the state is re-read and checked before the effect is called
applied.

`room-reservation` owns its state under `fleet/workers/room-reservation/state/`,
so its effect changes that worker and not a shared repo fixture.

## Inbox trigger

`fleet/inbox.py`. A file landing in a worker's `inbox/` is the trigger. No LLM
is reachable from any of it, and there is no clock logic — `poll()` is one
deterministic pass in sorted filename order.

```text
<worker>/
  inbox/        a file landing here is the trigger
  processed/    the run completed -- accepted, or refused by policy
  exceptions/   the run failed, or an accepted decision's effect did not land
  ledger.jsonl  append-only work-item state. This is the twice-protection.
```

**A file's location is a consequence, not a record.** If a process dies between
applying an effect and moving the file, the file is still in `inbox/` and a
naive poller reruns it — a duplicate booking, not a retry. So an item is
**claimed in the ledger before it runs**, and the ledger is what the next poll
consults.

**Item identity is content.** `item_id` is the sha256 of the file's bytes.
Renaming does not make it new work; re-dropping the same content is recognised
as the same item and is neither re-run nor re-applied.

`retry()` moves one exception back to the inbox. That is a person's decision,
not something the poller does on a timer. An item whose effect never landed
applies it on retry; one that completed is caught by the ledger.

## Recovery

An interrupted pass leaves a `claimed` line with no terminal line. `recover()`
resolves each one by reconciling against the worker's **verifiable state**,
never by guessing:

```text
already_landed   the effect is present and the claim recorded it ABSENT, so
                 this run applied it -> complete WITHOUT re-executing
safe_to_retry    the effect is definitely absent, or none was earnable
                 -> re-execute
indeterminate    the question cannot be answered -> exception queue
```

The **precondition recorded with the claim** is what makes this answerable.
Without it, "the date is in state" is ambiguous: this run may have put it there,
or it may have been there all along and the decision was a refusal.

`effect_landed()` deliberately does not reuse `runtime._landed`, which returns
`False` when state cannot be read. That is right for the commit path — an effect
that cannot be verified did not land — and wrong here, because "definitely
absent" and "cannot tell" lead to opposite actions.

### Demonstrated in both windows

```text
crash BEFORE the effect   nothing applied, file still in inbox
                          -> safe_to_retry -> applied once. No work lost.
crash AFTER the effect    effect landed, terminal line never written, file
                          never moved -- a naive poller would rerun it
                          -> already_landed -> completed with NO second effect
                             and no extra run
```

## Scope

Only `content_digest` work-item identity is implemented, and it is declared per
worker in `work_item_identity`. An unknown or absent policy is refused, not
defaulted. `payload_digest` is recorded separately on every ledger line — it is
a fact about the bytes, whereas identity is a policy, and they coincide for this
worker only.

## Investigation, wired to the exception queue

`fleet/investigation.py`. The two halves were built separately; this joins them.

```text
work -> deterministic worker -> EXCEPTION -> packet        (no LLM)
                                              |
                                    operator opens it
                                              v
        packet -> LLM -> Experiment Y sufficiency gate     (experimentZ)
                    |
        sufficient  |  ambiguous
                    v          v
              PROPOSAL     QUESTION -> one human answer -> PROPOSAL
                    |                                          |
                    +----> operator applies -> v2 -------------+
                                              |
                                  queued work retried under v2
```

**Nothing wakes a model on its own.** An exception sits in the queue until an
operator clicks *Investigate*. That is the only model call in the console.

**A sufficient repair is proposed, not applied.** Experiment Y settled the
*epistemic* question — whether the evidence establishes a replacement. It does
not settle the *operational* one, whether a live worker should change now. Those
are different axes, the same way an input contract is not a source
interpretation. The operator clicks once.

The gate still refuses a proposal the measurements do not support, and such a
refusal becomes a question rather than a change.
