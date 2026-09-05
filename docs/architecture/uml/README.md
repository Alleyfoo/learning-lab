# Architecture views

Repository-grounded discovery artifacts. They describe the system; they do not create it by being drawn.

Which notation answers which question is decided in [`../modelling-guide.md`](../modelling-guide.md). Why these views are split into two kinds is **proposed** in [ADR-0002](../../decisions/ADR-0002-architecture-model-grounding.md), which is awaiting Roundtable and is not yet authority.

## The two kinds

Every file states its kind in its own header, and no file mixes them.

| Kind | Means | How it is kept true |
| --- | --- | --- |
| **MEASURED** | Every edge was extracted from the repository. An edge that is not in the code is a defect in the view. | `python scripts/check_architecture_grounding.py` |
| **INTENDED** | Responsibility, flow or journey as an authority document describes it. Arrows are conceptual, **not** import edges. | Reviewed against the document it renders |

## Views

| File | Kind | Notation | Question answered |
| --- | --- | --- | --- |
| `01-system-context.puml` | INTENDED | UML component / context | What are the major live parts, the external actors, and the frozen research estate? |
| `02-live-responsibility-map.puml` | INTENDED | UML component / package | How do the live packages divide observation, definition, deterministic execution, fleet state and supervision? |
| `03-product-journey-sequence.puml` | INTENDED | UML sequence | What is the journey from incoming data to established deterministic work and supervision? |
| `04-development-workflow.puml` | INTENDED | UML state machine | How does a **development** work item move, and who may move it? |
| `05-package-dependencies.puml` | **MEASURED** | UML component / package | What actually depends on what among the twelve live packages? |
| `06-domain-model.puml` | **MEASURED** | UML class | What are the durable objects of established work, and what invariants do they carry? |
| `07-inbox-item-state.puml` | **MEASURED** | UML state machine | What states can a **runtime** work item occupy, including recovery? |
| `08-operational-data-flow.puml` | **MEASURED** | DFD level 1 | How does data move once work is established, and where is it stored? |

Two state machines exist deliberately. `04` is the development work item; `07` is the runtime work item. They are different objects and must not be read as one.

## Checking the measured views

```bash
python scripts/check_architecture_grounding.py
python scripts/check_architecture_grounding.py --self-test
```

The first re-derives the live package dependency edges from the source and compares them with `05-package-dependencies.puml`, reporting drift in both directions. The second exercises the checker itself against a synthetic fixture, including both the bare `sys.path`-style import and the package-qualified one.

`06`, `07` and `08` are measured by reading, not by script: their content is the shape of dataclasses, ledger literals and file paths. Their headers name the exact sources so a reader can re-check any claim.

## Rendering

Any PlantUML renderer. Nothing here depends on a hosted service, and no rendered images are committed.

## Reading rules

1. When a diagram disagrees with the code, **the diagram is wrong**.
2. When the code disagrees with accepted architecture or product authority, that is a **discrepancy**. Record it in [`../../development/discrepancy-register.md`](../../development/discrepancy-register.md); do not silently redraw until the contradiction disappears.
3. An INTENDED arrow is not a dependency. Eight of the fifteen arrows in `02` deliberately run opposite to the real import direction, and five describe a hand-off that no import performs at all, because flow and dependency are different questions.

## What this package established

Building it produced five findings. The three that are actual disagreements are recorded with their evidence in the [discrepancy register](../../development/discrepancy-register.md) as D1–D4; the other two are confirmations.

1. **The live/research split is already explicit** in `README.md` and `PRODUCT.md`; the root mixes them physically but the authority documents name the twelve live packages. Confirmed as-is.
2. **The product roadmap and product authority are deliberately different documents.** `docs/roadmap/work-interface-lab-roadmap.md` labels itself a hypothesis and says so.
3. **The first component diagram's edges did not match the code** — of its fifteen arrows, 2 matched a real dependency in the direction drawn, 8 ran the opposite way, and 5 existed in neither direction; 13 of the 22 real edges appeared nowhere in it. That is D4, and it is why `02` and `05` are now separate files.
4. **`modeller/` is the most load-bearing live package**, not a UI surface: it composes all four task families, and both `worker/` and `fleet/` depend on it. This is visible only in the measured view.
5. **Documentation lagged the code by one day and several versions** — the stale handoff (D1), the v0.1 supervisor label (D2) and the product priorities that appear already delivered (D3).
