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

## Known limit: runs here do not commit effects

`builder.preview` executes deterministically and reports. For enrichment,
aggregation and reconciliation there is nothing to commit. `room-reservation`
declares `on_accept: append_to_reservations` and **that effect does not land** —
the fixture is byte-identical after five runs. The worker page says so rather
than implying otherwise. A committing runtime is `calendar_job/unattended.py`,
which is a different thing from this view.
