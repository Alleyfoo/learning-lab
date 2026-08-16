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
