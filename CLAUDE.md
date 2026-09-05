# Agent entry point

Read [`docs/development/engineering-system.md`](docs/development/engineering-system.md) before doing development work here. It is the normative process description and opens with the answers to the questions you would otherwise ask.

This file is a pointer, not a second copy of the rules. Where it seems to disagree with the engineering system, the engineering system wins.

## Where your work comes from

Manager dispatches one work item. To reconstruct it, read, in this order:

1. this file, [`CONTRIBUTING.md`](CONTRIBUTING.md) and the engineering system;
2. the **issue** — the authorised work item, its bounds and acceptance criteria;
3. the **PR and its commits**, if implementation already exists;
4. the **latest Manager review or PR comment**.

That is everything. You never need a chat transcript to recover the previous worker's state, and you must not rely on one: put whatever the next worker needs into the PR or the issue instead.

## The five that agents get wrong here

1. **A discovery is not work.** If you find something outside your task, record it in [`docs/development/initiatives.md`](docs/development/initiatives.md) and continue with the task you were given. `Discovered -> In progress` is an illegal transition. Do not fix it "while you are in there".

2. **`.handoff.md` is not authority.** It is a transient navigation aid and ranks last in the precedence order. It has been stale before. Check it against the repository — the git log, `work_interface/BACKLOG.md`, the code — before believing it.

3. **Frozen evidence is never edited.** Experiment packs, fixtures and historical harnesses stay as they are, including their defects. `authorized_reader.py` keeps a cp1252 defect on purpose; backlog item B-3 explains why. Corrections are additive and apply to new work, not to the record of old work.

4. **Diagrams do not create architecture.** Views under `docs/architecture/uml/` are reverse-engineered. Each declares MEASURED or INTENDED (ADR-0002). If you change the live package structure, run:

   ```bash
   python scripts/check_architecture_grounding.py
   ```

5. **You do not choose your own task.** `Ready` means an item is eligible to be pulled by Manager — not permission for whoever finds it. Do not scan the repository and start something because it looks next. If you think the wrong thing was dispatched, say so; record anything else you noticed as an initiative.

## Authority order

```text
live code + frozen evidence
  > accepted product / architecture / ADR authority   (PRODUCT.md, docs/decisions/)
  > roadmap                                           (docs/roadmap/)
  > backlog / initiatives
  > transient handoff / notes                         (.handoff.md)
```

Only Roundtable changes the roadmap or `PRODUCT.md`. If your task seems to require it, that is a signal to raise an initiative, not to edit.

## Contributor guide

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the same ground for humans, with the full map of where things live.
