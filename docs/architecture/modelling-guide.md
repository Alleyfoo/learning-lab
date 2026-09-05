# Modelling and notation guide

**Status:** authoritative for which notation to use.
**Owner:** Roundtable, via ADR-0001.

> The MEASURED/INTENDED split described in §3 is **proposed** in ADR-0002 and has not been
> accepted. The views in the repository already carry those headers, which is evidence for
> the proposal; §3 is not yet authority.

Learning Lab uses established modelling notations. This document says which notation answers which question, and what a model may and may not claim.

---

## 1. The rule that comes first

> A model is a **reverse-engineered discovery artifact grounded in the repository**. It never becomes authority by being drawn.

Three consequences:

- **Diagram vs code: the code wins.** A diagram that disagrees with the repository is wrong and is corrected.
- **Code vs accepted authority: neither is silently redrawn.** That is a discrepancy. Record it in [`../development/discrepancy-register.md`](../development/discrepancy-register.md) and let Roundtable disposition it.
- **A view states its grounding.** Every diagram in [`uml/`](uml/) names the files it was derived from, and says whether its edges were *measured* or are *intended*. Those are different claims and must not be mixed in one view.

---

## 2. Which notation answers which question

| Question | Notation | Where it lives here |
| --- | --- | --- |
| What components/packages exist? | UML component / package diagram | `uml/01-system-context.puml`, `uml/02-live-responsibility-map.puml`, `uml/05-package-dependencies.puml` |
| What calls or communicates with what, over time? | UML sequence diagram | `uml/03-product-journey-sequence.puml` |
| What states can an object or work item occupy? | UML state-machine diagram | `uml/04-development-workflow.puml` (development item), `uml/07-inbox-item-state.puml` (runtime work item) |
| What is the workflow? | UML activity diagram, or BPMN when several organisational actors and handoffs dominate | none yet; the development workflow is currently expressed as a state machine, which is the better fit for an item that has states |
| How does information move? | DFD (Data Flow Diagram) | `uml/08-operational-data-flow.puml` |
| What is the domain / data model? | UML class diagram, or ERD for relational structure | `uml/06-domain-model.puml` |
| Why was an architecture choice made? | ADR | [`../decisions/`](../decisions/) |
| What larger change needs discussion before adoption? | RFC | [`../rfcs/`](../rfcs/) |

UML is the default architecture modelling language, and it is a **language**, not one diagram type. Do not force a data-movement question into a component diagram, or a state question into a sequence.

Use a non-UML notation when it genuinely answers the question better:

- **DFD** when the interesting content is what data moves between processes and stores, and control flow is a distraction.
- **ERD** when the structure is relational and cardinality is the point. This repository's durable state is JSON/JSONL under `fleet/workers/`, so the domain is currently drawn as a UML class diagram; an ERD would be the right choice if that state ever becomes relational.
- **BPMN** when a business process crosses organisational roles with explicit handoffs, gateways and events.

The purpose is shared understanding, not notation purity.

---

## 3. Measured versus intended edges

Every architecture view in this repository is one of two kinds, and says which it is in its header:

| Kind | Means | Checked how |
| --- | --- | --- |
| **Measured** | Every edge was extracted from the repository. Adding an edge that does not exist in code is a defect. | `scripts/check_architecture_grounding.py` re-measures and fails on drift |
| **Intended** | Responsibility, data flow or journey as `PRODUCT.md` and `README.md` describe it. Edges are *conceptual*, not import edges. | Reviewed against the authority document it claims to render |

Mixing the two is what makes architecture diagrams quietly untrue: a conceptual arrow gets read as a dependency, and the next contributor plans against a structure that does not exist. See ADR-0002.

---

## 4. ADR — Architecture Decision Record

An ADR records a durable architecture or engineering-system decision and why it was made. Use one when a future contributor would otherwise have to rediscover the choice from commits, experiments or prose.

Contents: context/problem; decision; alternatives considered where material; consequences and trade-offs; status (`Proposed`, `Accepted`, `Superseded`, `Rejected`, `Deprecated`).

Do **not** use an ADR for ordinary implementation detail, or for an experimental observation that has not become architecture authority.

Index and template: [`../decisions/README.md`](../decisions/README.md).

---

## 5. RFC — Request for Comments

Use an RFC when a substantial proposed change needs discussion before it becomes authority.

An RFC is a **proposal**, not implementation authority. An accepted RFC produces either an ADR (a durable decision) or a roadmap item (authorised direction) — the RFC itself never becomes the authority record.

Small, well-understood work does not need an RFC.

Index and template: [`../rfcs/README.md`](../rfcs/README.md).

---

## 6. Keeping models honest

1. Derive the view from the repository, not from an earlier diagram.
2. State the grounding sources in the file header.
3. Mark the view `MEASURED` or `INTENDED`.
4. For measured views, add the check that re-derives them, and run it.
5. When a model and the repository disagree, fix the model, or record a discrepancy if the repository is the thing that looks wrong. Never adjust the model to hide the disagreement.
