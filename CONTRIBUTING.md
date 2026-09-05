# Contributing to Learning Lab

Learning Lab uses established software-engineering mechanisms rather than a project-specific development protocol. Before adding a new process mechanism, find the established concept that already covers the problem and use it — see the existing-system-first rule.

**Read first:** [`docs/development/engineering-system.md`](docs/development/engineering-system.md). It is the normative description of how development work moves, and it opens with the answers to the thirteen questions a new worker needs.

## Where things are

| You need | Go to |
| --- | --- |
| The development process — roles, states, DoR, DoD, WIP, precedence | [`docs/development/engineering-system.md`](docs/development/engineering-system.md) |
| Why the governance loop is what it is | [`docs/decisions/ADR-0001-development-governance.md`](docs/decisions/ADR-0001-development-governance.md) |
| Durable architecture decisions | [`docs/decisions/`](docs/decisions/) |
| A proposal that needs discussion first | [`docs/rfcs/`](docs/rfcs/) |
| Which diagram notation answers which question | [`docs/architecture/modelling-guide.md`](docs/architecture/modelling-guide.md) |
| What the live system actually looks like | [`docs/architecture/uml/`](docs/architecture/uml/) |
| Product direction and the live/research split | [`PRODUCT.md`](PRODUCT.md) |
| Authorised direction | [`docs/roadmap/`](docs/roadmap/) |
| Somewhere to put a discovery that is out of scope | [`docs/development/initiatives.md`](docs/development/initiatives.md) |
| Known documentation-vs-repository disagreements | [`docs/development/discrepancy-register.md`](docs/development/discrepancy-register.md) |
| The work item you were dispatched, and its state | its GitHub issue, then its PR, branch and review |
| What is being worked on right now | [`.handoff.md`](.handoff.md) — navigation only, never authority |

## The flow

```text
Discovered
  -> Initiative / Backlog     anyone may record a discovery
  -> Roundtable accepted      Roundtable decides it is real work
  -> Roadmapped               Roundtable gives it a priority
  -> Ready                    Manager: Definition of Ready satisfied
  -> Dispatched               Manager: bounded work order, WIP respected
  -> In progress              Coder implements
  -> Manager review           Coder returns implementation + evidence
  -> Implemented              Manager: Definition of Done satisfied
  -> Roundtable closed        Roundtable updates roadmap/architecture status
```

Three rules carry most of the weight:

1. **A discovery is not work.** Found something outside your task? Write it to `docs/development/initiatives.md` and keep going. It becomes work when Roundtable says so, not when you found it.
2. **Manager acceptance and Roundtable closure are different gates.** Manager answers "was the commissioned work implemented correctly?" Roundtable answers "what does this mean for the roadmap and architecture?" Neither may perform the other.
3. **A Coder does not change roadmap, architecture or authority** to make the task easier or larger.

Transitions each have exactly one authorised actor, and some are always illegal — `Discovered -> In progress` most of all. See the engineering system, §4.2 and §4.2.1.

## Where development state lives

| Object | Carries |
| --- | --- |
| Repository | Persistent engineering context and authority |
| Issue | One authorised work item: purpose, bounds, acceptance criteria |
| Branch + PR | Implementation state for that work item |
| PR review and comments | Manager feedback, corrections, technical acceptance |
| Issue closure | Roundtable's roadmap/architecture closure |
| Chat | Discussion aid — not the durable transport for development state |

To pick up work already in flight, read the instructions, then the issue, then the PR and its commits, then the latest Manager review. Anything the next person needs belongs in one of those, not in a chat thread. See the engineering system, §10.

Manager dispatches the exact work item. `Ready` means an item is eligible to be pulled, not that anyone may start it.

## Which document wins

```text
live code + frozen evidence
  > accepted product / architecture / ADR authority
  > roadmap
  > backlog / initiatives
  > transient handoff / notes
```

If `.handoff.md` disagrees with the repository, the handoff is stale. Repair it; never plan from it.

## Research evidence

Frozen experiments, negative results, corrections and historical defects are **evidence**. Do not clean them up in place because a newer mechanism exists. `authorized_reader.py` keeps a cp1252 defect on purpose — it is W1-F evidence, and backlog item B-3 says so. Correct current and future machinery additively; preserve what motivated the correction.

Where an experiment design calls for preregistration, freeze the question, variable, baseline, measurement and interpretation branches **before** execution.

## Architecture documentation

Use the notation that answers the question; UML is a language, not one diagram type.

Every architecture view declares whether it is **MEASURED** (every edge extracted from the repository) or **INTENDED** (responsibility and flow as an authority document describes it). Do not mix them in one file — that is how a conceptual arrow gets read as a dependency. The convention is [ADR-0002](docs/decisions/ADR-0002-architecture-model-grounding.md).

If you change the live package structure, the measured view has to change with it:

```bash
python scripts/check_architecture_grounding.py
```

When a diagram disagrees with code, the diagram is wrong. When code disagrees with accepted authority, record a discrepancy and route it through the loop — do not redraw until the contradiction disappears.
