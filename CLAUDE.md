# Agent entry point

Read [`docs/development/engineering-system.md`](docs/development/engineering-system.md) before doing development work here. It is the normative process description and opens with the answers to the questions you would otherwise ask.

This file is a pointer, not a second copy of the rules. Where it seems to disagree with the engineering system, the engineering system wins.

## The four that agents get wrong here

1. **A discovery is not work.** If you find something outside your task, record it in [`docs/development/initiatives.md`](docs/development/initiatives.md) and continue with the task you were given. `Discovered -> In progress` is an illegal transition. Do not fix it "while you are in there".

2. **`.handoff.md` is not authority.** It is a transient navigation aid and ranks last in the precedence order. It has been stale before. Check it against the repository — the git log, `work_interface/BACKLOG.md`, the code — before believing it.

3. **Frozen evidence is never edited.** Experiment packs, fixtures and historical harnesses stay as they are, including their defects. `authorized_reader.py` keeps a cp1252 defect on purpose; backlog item B-3 explains why. Corrections are additive and apply to new work, not to the record of old work.

4. **Diagrams do not create architecture.** Views under `docs/architecture/uml/` are reverse-engineered. Each declares MEASURED or INTENDED — a convention proposed in ADR-0002, not yet accepted. If you change the live package structure, run:

   ```bash
   python scripts/check_architecture_grounding.py
   ```

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
