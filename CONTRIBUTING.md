# Contributing to Learning Lab

Learning Lab uses established software-engineering mechanisms rather than a project-specific development protocol.

Start with:

- [`docs/development/engineering-system.md`](docs/development/engineering-system.md) — Kanban flow, Roundtable/Manager/Coder authority, DoR, DoD, WIP, ADR/RFC/UML terminology and document precedence;
- [`docs/decisions/ADR-0001-development-governance.md`](docs/decisions/ADR-0001-development-governance.md) — accepted governance decision;
- [`docs/architecture/uml/README.md`](docs/architecture/uml/README.md) — repository-grounded architecture discovery views;
- [`PRODUCT.md`](PRODUCT.md) — current product/architecture direction;
- [`docs/roadmap/`](docs/roadmap/) — authorized roadmap/research contracts;
- [`.handoff.md`](.handoff.md) — transient current-work navigation only, never authority.

## Development flow

```text
Discovery -> backlog/initiative intake
          -> Roundtable disposition
          -> Ready (DoR satisfied)
          -> Manager dispatch
          -> Coder implementation
          -> Manager review (DoD / acceptance)
          -> Implemented
          -> Roundtable roadmap/authority closure
          -> Closed
```

A discovery does not become development scope automatically. Coder does not change roadmap authority. Manager does not silently expand roadmap scope. Manager acceptance and Roundtable closure are different gates.

## Research evidence

Frozen experiments, negative results, corrections and historical defects are evidence. Do not clean them up in place merely because a newer mechanism exists. Correct current/future machinery additively and preserve the evidence that motivated the correction.

## Architecture documentation

Use the established notation that answers the question. UML is the default architecture modelling language, not a requirement to force everything into one diagram type. Use ADRs for durable decisions; use RFCs for substantial proposals that need discussion before a decision.

When a diagram disagrees with code or frozen evidence, the diagram is wrong. When repository reality disagrees with accepted architecture/product authority, record the discrepancy and route it through the governance loop.
