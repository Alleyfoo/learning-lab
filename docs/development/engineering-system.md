# Learning Lab engineering system

This document names the development mechanisms Learning Lab uses in established software-engineering terms. It is intentionally small. The goal is to reuse proven systems rather than create a project-specific process language.

## Authority and roles

Learning Lab keeps the existing three-role governance loop:

```text
Roundtable -> Manager -> Coder -> Manager -> Roundtable
```

The names are project names; the responsibilities map onto established engineering roles.

| Learning Lab role | Established analogue | Authority |
| --- | --- | --- |
| **Roundtable** | Product Owner + Architecture Review Board | Owns roadmap priority and durable architecture decisions. May accept, reject, park, split, supersede or close roadmap items. |
| **Manager** | Delivery lead + integrating reviewer | Pulls Ready work, creates bounded work orders, dispatches implementation, reviews evidence, and accepts or rejects implementation against the work order. Does not silently add roadmap scope. |
| **Coder** | Implementer | Implements the bounded work order and returns code/tests/evidence. Does not redefine roadmap or architecture to make the task easier. |
| **Initiative box / backlog** | Intake backlog | Holds discoveries, defects, proposals and research questions until Roundtable disposition. A finding is not automatically work. |

Two approvals answer different questions:

- **Manager acceptance:** was the commissioned work implemented correctly?
- **Roundtable closure:** what does the accepted result mean for roadmap/product/architecture authority?

Roundtable closure is not a second code review.

## Work flow: Kanban

**Kanban** is used as the delivery model because Learning Lab work is discovery- and evidence-driven rather than naturally sprint-shaped.

Canonical states:

```text
Discovered
  -> Backlog
  -> Ready
  -> In Progress
  -> Manager Review
  -> Implemented
  -> Roundtable Closure
  -> Closed
```

Additional dispositions are `Parked`, `Rejected`, and `Superseded`.

Rules:

1. Only Roundtable may move a discovery into roadmap/backlog authority or materially change roadmap scope.
2. `Ready` means the Definition of Ready is satisfied.
3. Manager pulls from `Ready`; work is not pushed directly from a discovery into implementation.
4. A failed Manager review returns to `In Progress`; it does not create a new roadmap item unless a genuinely new finding is discovered.
5. Manager-accepted work becomes `Implemented`, then returns to Roundtable for roadmap/authority closure.
6. Keep Work In Progress (**WIP**) low. Default: one active implementation per Manager unless Roundtable explicitly authorizes parallel work.

## DoR — Definition of Ready

A work item is **Ready** only when all applicable items below are known:

- authoritative roadmap/decision it serves;
- repository-grounded current state;
- bounded scope and explicit non-scope;
- acceptance criteria;
- relevant invariants/authority boundaries;
- required tests or evidence;
- dependencies and frozen artifacts that must not change;
- unresolved architecture questions are either answered or explicitly delegated to Roundtable, not silently delegated to Coder.

Research work additionally requires the question, controlled variable, comparison/baseline, measurement, and interpretation branches to be frozen before execution where the experiment design calls for preregistration.

## DoD — Definition of Done

Manager may mark an item **Implemented** only when all applicable conditions hold:

- commissioned implementation is complete;
- acceptance criteria are demonstrated;
- tests/self-tests pass or failures are explicitly dispositioned;
- no unauthorized scope or authority change was introduced;
- documentation describing changed behaviour is updated;
- architecture diagrams/ADRs are updated when architecture changed;
- evidence and negative results are preserved where relevant;
- frozen historical experiment evidence remains untouched;
- repository status is coherent: roadmap/backlog/handoff do not contradict the implemented state.

`Implemented` is not the same as `Closed`. Roundtable owns closure.

## ADR — Architecture Decision Record

An **ADR** records a durable architecture decision and why it was made. Use an ADR when a future contributor would otherwise have to rediscover a choice from commits, experiments or prose.

An ADR normally contains:

- context/problem;
- decision;
- alternatives considered;
- consequences/trade-offs;
- status (`Proposed`, `Accepted`, `Superseded`, `Deprecated`).

Do not use ADRs for ordinary implementation details or experimental observations that have not become architecture authority.

## RFC — Request for Comments

Use an **RFC** for a substantial proposed change that needs Roundtable discussion before it becomes authority. An RFC is a proposal; an accepted architecture decision becomes an ADR or an explicit roadmap decision.

Small, well-understood work does not need an RFC.

## UML — Unified Modeling Language

UML is used for repository-grounded architecture discovery and communication. It is not itself product authority.

Use the diagram type that matches the question:

| Question | UML view |
| --- | --- |
| What major parts exist and depend on each other? | Component / package diagram |
| What calls or hands data to what over time? | Sequence diagram |
| What states may an object/work item occupy? | State-machine diagram |
| What workflow/branching process occurs? | Activity diagram |
| What domain types and relationships exist? | Class diagram |
| What runs on which runtime nodes? | Deployment diagram |

Other established notations may be used when they fit better: **DFD** (Data Flow Diagram) for pure data movement, **ERD** (Entity Relationship Diagram) for relational data structure, and **BPMN** (Business Process Model and Notation) for business/process orchestration. Do not force every question into UML.

## Authority precedence

Documents have different jobs; they must not become accidental competing authorities.

1. **Repository behaviour and frozen evidence** establish what actually exists or happened.
2. **Accepted ADRs and explicit product/architecture authority** establish durable architectural choices.
3. **Roadmap** establishes authorized future direction and priority.
4. **Backlogs/initiative boxes** contain uncommitted candidate work.
5. **Handoffs** describe current operational context only. They are disposable navigation aids, never product/architecture/roadmap authority.

If a handoff disagrees with the repository, roadmap or accepted ADR, the handoff is stale.

## Existing Learning Lab artifacts in standard terms

| Existing artifact | Engineering interpretation |
| --- | --- |
| `PRODUCT.md` | product/architecture authority and product direction |
| `docs/roadmap/` | roadmap / research contract |
| `work_interface/BACKLOG.md` | bounded technical/research backlog |
| experiment `CLOSURE.md` / disposition files | experiment result + disposition records |
| `.handoff.md` | transient operational handoff |
| frozen experiment packs | immutable research evidence |
| self-tests / graders / verifiers | verification and acceptance evidence |

The rule is simple: prefer an established term when one already describes the mechanism. Add a bespoke mechanism only when the existing engineering model genuinely cannot express the requirement.
