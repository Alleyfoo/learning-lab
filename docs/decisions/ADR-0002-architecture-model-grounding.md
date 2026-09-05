# ADR-0002: Architecture models are measured, not asserted

**Status:** Accepted
**Date:** 2026-09-05

## Context

Learning Lab now keeps architecture views under `docs/architecture/uml/`. Architecture documentation has a well-known failure mode: a diagram is drawn once from intent, the code moves, and the diagram keeps being read as if it described the system. The next contributor then plans against a structure that does not exist.

This repository is unusually exposed to that failure for two reasons.

First, the live packages do not use package-qualified imports. They put sibling directories on `sys.path` and import bare module names (`import task_model`, `import worker as W`, `import observe`). The dependency structure is therefore invisible to a casual reading of the import lines, and easy to guess wrongly.

Second, the first architecture package drawn for this repository (`02-live-component-map.puml`, in its original form) did guess wrongly. Measuring the actual imports against its fifteen drawn edges gives:

```text
 2  drawn in the direction the code depends
 8  drawn in the opposite direction to the real dependency
 5  do not exist in either direction
13  real edges absent from the drawing entirely
```

Two of fifteen. The diagram was not describing dependencies at all; it was describing intended data flow, drawn in a component diagram's notation. Both are legitimate views, and as a flow view it was largely right. Presenting one as the other is what made it wrong.

The lab already holds the corresponding research position: a claim worth stating is worth making checkable (`operating_procedure.md` §2.1, and `scripts/check_surfaced.py`, which exists because of exactly that rule).

## Decision

Every architecture view in this repository declares, in its own header, which of two kinds it is:

- **MEASURED** — every edge was extracted from the repository. An edge that does not exist in the code is a defect in the view.
- **INTENDED** — responsibility, data flow or journey as an authority document describes it. Edges are conceptual and are explicitly not import edges.

A single view may not mix the two.

At least one MEASURED view of the live package structure is maintained, and it is **checkable by a script rather than by review**. `scripts/check_architecture_grounding.py` re-derives the live package dependency edges from the source and compares them with the edges declared in `docs/architecture/uml/05-package-dependencies.puml`, reporting any edge that exists in code but not in the diagram, or in the diagram but not in code.

When the check fails, the resolution order is fixed by the engineering system's precedence rule: the code is what exists, so the diagram is corrected — unless the code is what looks wrong, in which case the disagreement is recorded in `docs/development/discrepancy-register.md` and dispositioned by Roundtable. The check is never satisfied by deleting the assertion.

## Alternatives considered

### Review diagrams by eye at change time

Rejected. This is what already failed. The wrong edges in the first package were plausible, and the `sys.path` import style makes the real edges hard to see without measuring them.

### Generate all diagrams from code

Rejected. Generated views answer only the questions a generator can ask. The useful views here — the product journey, the responsibility split, the authority boundary — are intentional and cannot be derived. The decision keeps hand-drawn views, and makes the one structural claim they rest on checkable.

### Drop the component view and keep only prose

Rejected. The dependency structure is genuinely hard to see in this repository, which is the argument for drawing it, not against.

## Consequences

### Positive

- a diagram/repository disagreement is detected mechanically rather than believed;
- a conceptual arrow can no longer be silently read as a dependency;
- the architecture package can be trusted enough to plan against;
- the check is cheap, read-only, and runs without the LLM or any network access.

### Costs

- a live package rename or a new cross-package import fails the check until the diagram is updated — which is the intended behaviour, but is a real obligation;
- the check understands the current `sys.path` bare-module import style. If the repository moves to package-qualified imports, the measurement has to be updated with it;
- two views are now needed where one was drawn before: the intended responsibility map and the measured dependency map.

## Related

- `docs/architecture/modelling-guide.md` — which notation answers which question
- `docs/architecture/uml/05-package-dependencies.puml` — the measured view
- `docs/architecture/uml/02-live-responsibility-map.puml` — the intended view it was split from
- `scripts/check_architecture_grounding.py` — the check
- `docs/development/discrepancy-register.md` — D4, the discrepancy that motivated this ADR
- `operating_procedure.md` §2.1 — the existing "a rule is only worth stating if it is checkable" position
