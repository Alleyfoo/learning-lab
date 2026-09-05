# ADR-0001: Development governance and authority loop

**Status:** Accepted  
**Date:** 2026-09-05

## Context

Learning Lab already has strong evidence discipline, explicit authority boundaries, frozen experiment packs, closures, dispositions, backlogs and product/roadmap documents. What it lacks is a single established engineering vocabulary for how development work moves between discovery, authority, implementation, review and closure.

That gap creates a predictable failure mode: transient handoffs, experiment conclusions, backlog notes and product/roadmap statements can drift and appear to compete for authority. The repository currently demonstrates this directly: `.handoff.md` still describes W1-J as current even though later commits closed W1-K and froze W1-L.

The project also wants to avoid inventing custom process machinery for problems already addressed by established software-engineering practice.

## Decision

Learning Lab adopts the following governance loop for development work:

```text
Roundtable -> Manager -> Coder -> Manager -> Roundtable
```

- **Roundtable** owns roadmap priority and durable architecture/product decisions.
- **Manager** owns delivery integration: bounded work orders, dispatch, implementation review and acceptance against the commissioned work.
- **Coder** owns implementation of the bounded work order.
- Discoveries and findings enter an **initiative/backlog** and do not become authorized development merely because they were found.
- Manager-accepted work returns to Roundtable for roadmap/authority closure.

The delivery workflow uses **Kanban**, with a Definition of Ready (**DoR**), Definition of Done (**DoD**) and explicit Work In Progress (**WIP**) limits.

Work items move through an explicit state model with a **named owner for every transition**, so that a transition nobody is authorised to make is visibly illegal rather than merely unusual:

```text
Discovered -> Initiative / Backlog -> Roundtable accepted -> Roadmapped
           -> Ready -> Dispatched -> In progress -> Manager review
           -> Implemented -> Roundtable closed
```

The states, their transition owners and the transitions that are always illegal are defined in `docs/development/engineering-system.md` §4, which is normative for them.

Durable architecture decisions use **Architecture Decision Records (ADRs)**. Substantial proposals that require discussion before decision may use **Requests for Comments (RFCs)**.

Repository-grounded architecture discovery uses the appropriate established modelling notation, primarily **UML (Unified Modeling Language)**, with DFD/ERD/BPMN where those answer the question better.

`.handoff.md` is explicitly non-authoritative: it is a transient navigation aid and must yield to repository behaviour/evidence, accepted ADRs, product authority and roadmap state.

## Consequences

### Positive

- discoveries cannot silently turn into scope;
- implementation review and roadmap closure have separate owners and meanings;
- stale handoffs cannot override architecture or roadmap authority;
- established terminology makes the process easier to inspect and transfer to other repositories;
- architecture changes gain durable rationale instead of being reconstructed from commit history;
- the process can remain small because established engineering mechanisms provide the vocabulary.

### Costs

- some current bespoke labels must be mapped to standard terms;
- roadmap/backlog/handoff drift has to be repaired when found;
- architecture-changing work gains a small documentation obligation;
- WIP limits deliberately reduce parallel implementation even when more agents are available.

## Alternatives considered

### Keep the current informal artifact set

Rejected. The current artifacts are individually useful, but their authority relationship is not explicit enough. The stale handoff is a concrete counterexample.

### Build a new Learning-Lab-specific development protocol

Rejected. The required mechanisms are already covered by Kanban, DoR/DoD, ADR/RFC and established modelling notations. A bespoke protocol would add vocabulary without adding capability.

### Let Manager own roadmap updates as well as delivery

Rejected. This collapses product/architecture authority into execution and reintroduces the failure mode where implementation discoveries silently become roadmap scope.

## Related

- `docs/development/engineering-system.md` — the normative process description
- `docs/development/initiatives.md` — where a discovery goes
- `docs/development/discrepancy-register.md` — documentation/repository disagreements and their dispositions
- `docs/architecture/modelling-guide.md` — which notation answers which question
- `docs/decisions/ADR-0002-architecture-model-grounding.md` — how architecture views are kept honest
- `docs/architecture/uml/04-development-workflow.puml` — this loop as a state machine
- `PRODUCT.md`
- `docs/roadmap/work-interface-lab-roadmap.md`
- `work_interface/BACKLOG.md`
- `.handoff.md`
