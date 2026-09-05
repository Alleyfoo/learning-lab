# Learning Lab UML grounding package

These diagrams are **architecture-discovery artifacts grounded in the repository**. They describe the current live system and its relationship to the research estate; they do not create architecture merely by being drawn.

## Grounding sources

Primary authority/evidence used for this first package:

- `README.md` — live vs research repository map and current entry points;
- `PRODUCT.md` — current product direction, live component roles and authority model;
- `docs/roadmap/work-interface-lab-roadmap.md` — Work-interface research hypothesis, explicitly not product authority;
- `work_interface/BACKLOG.md` — current bounded infrastructure/research backlog;
- `.handoff.md` plus current `main` history — operational-state drift check;
- live package layout under `adapters/`, `inspector/`, `modeller/`, `taskmodel/`, `worker/`, `fleet/`, `supervisor/` and task-family packages.

This package intentionally does **not** infer detailed call edges that were not inspected. Later diagrams should add source-file/function evidence when they claim a narrower execution path.

## Views

| File | UML type | Question answered |
| --- | --- | --- |
| `01-system-context.puml` | component/context | What are the major live parts, external actors and the frozen research estate? |
| `02-live-component-map.puml` | component/package | How do the live packages divide observation, modelling, deterministic execution, fleet state and supervision? |
| `03-product-journey-sequence.puml` | sequence | What is the intended high-level journey from incoming data to established deterministic work and supervision? |
| `04-development-workflow.puml` | state machine | How does authorized development move through Roundtable -> Manager -> Coder -> Manager -> Roundtable? |

## Reading rule

When a diagram disagrees with code or frozen evidence, **the diagram is wrong**.

When code/evidence disagrees with accepted architecture/product authority, record the discrepancy and send it through the governance loop; do not silently redraw the diagram to make the contradiction disappear.

## Notation rule

Use the established notation that matches the question. UML is not mandatory where another notation is clearer:

- DFD for pure data movement;
- ERD for relational data structure;
- BPMN for process orchestration when UML activity/state views become awkward.

The purpose is shared understanding, not notation purity.

## Initial findings exposed by this pass

1. **Live system and research estate are already explicitly distinct.** The root mixes them physically, but `README.md` and `PRODUCT.md` name the live product path and identify experiment/history directories as evidence rather than alternate implementations.
2. **Product authority and Work-interface roadmap are intentionally different.** The Work-interface roadmap labels itself a hypothesis/research contract and says it does not replace `PRODUCT.md` yet.
3. **The current live UI is split across modeller, fleet/map and supervisor surfaces.** `PRODUCT.md` says these should converge around the company as the top-level object.
4. **`.handoff.md` is stale relative to `main`.** It reports W1-J as current while later history closes W1-K and freezes W1-L. This is classified as operational-document drift, not an architecture contradiction.
5. **The repository already behaves like an evidence-driven Kanban system in places** — frozen packs, backlog, closure/disposition and bounded cleanup — but the states and authority transitions were implicit. ADR-0001 and the development state-machine make those transitions explicit without changing research semantics.
