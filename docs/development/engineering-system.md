# Learning Lab engineering system

**Status:** authoritative for development process.
**Owner:** Roundtable. Changing this document is an architecture decision and requires an ADR.

This is the single normative description of how development work moves through Learning Lab. It names existing mechanisms in established software-engineering terms rather than inventing project-specific process language.

It is authoritative for **process**. It is not authoritative for product direction (`PRODUCT.md`), roadmap (`docs/roadmap/`), or system behaviour (the code and its evidence).

---

## Quick answers

A new development worker should be able to answer these from the repository alone.

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the current product/architecture authority? | `PRODUCT.md` for product direction and the live/research split; accepted ADRs in [`docs/decisions/`](../decisions/) for durable architecture decisions; the code and frozen evidence for what actually exists. |
| 2 | What work is currently allowed to start? | Only what Manager has **dispatched** to you (§4.2, §10). `Ready` means an item is eligible to be pulled, not that anyone may start it. Today the only item in `Ready` is the work-interface line's next step — executing the frozen, preregistered `work_interface/w1l/` baseline pack — per [`.handoff.md`](../../.handoff.md) and backlog item B-4. |
| 3 | Who may change the roadmap? | Roundtable only (§2). |
| 4 | Who may dispatch implementation? | Manager only (§2, §4.2). |
| 5 | Who accepts implementation as technically complete? | Manager, against the Definition of Done (§6). |
| 6 | Who closes the roadmap/architecture loop? | Roundtable (§2, §4.2). |
| 7 | Where does a new discovery go if it is outside scope? | [`docs/development/initiatives.md`](initiatives.md) — intake only, no authority. Work-interface infrastructure smells may instead go to [`work_interface/BACKLOG.md`](../../work_interface/BACKLOG.md). |
| 8 | What must be true before work starts? | The Definition of Ready (§5). |
| 9 | What must be true before work is done? | The Definition of Done (§6). |
| 10 | Which modelling notation should be used for a given question? | [`docs/architecture/modelling-guide.md`](../architecture/modelling-guide.md). |
| 11 | Where is a durable architecture decision recorded? | An ADR in [`docs/decisions/`](../decisions/). Its [index](../decisions/README.md) gives each ADR's current status, and each ADR states its own. |
| 12 | Which document wins when two documents disagree? | The precedence order in §7. |
| 13 | Which parts of the repository are live system and which are frozen research evidence? | `PRODUCT.md` § "What is live code vs research record" and `README.md` § "Repository map" name the split; [`docs/architecture/uml/05-package-dependencies.puml`](../architecture/uml/05-package-dependencies.puml) is the measured live structure, checked by `scripts/check_architecture_grounding.py`. |
| 14 | Where does durable development context live? | The repository, plus the issue, the PR and its review (§10). Not chat. |
| 15 | What does an issue represent, and what does a PR represent? | The issue is one authorised work item — purpose, bounds, acceptance criteria. The PR is the implementation state of that work item (§10). |
| 16 | Where does Manager correction and acceptance live? | In the PR's reviews and comments (§10). |
| 17 | Who decides which work item a worker may start? | Manager, by dispatching it. A worker does not choose its own from the repository (§10). |
| 18 | Do I need chat to recover the previous worker's state? | No. Read the instructions, the issue, the PR and its commits, then the latest Manager review (§10). |

---

## 1. Existing-system-first rule

Before introducing a new development or process mechanism, identify the established software-engineering concept that already covers the problem, and use it.

A Learning Lab-specific mechanism is justified only when all four hold:

1. the established concept is identified by name;
2. its specific limitation for the observed problem is demonstrated, not asserted;
3. the new mechanism has a narrower, explicitly stated purpose;
4. it does not create a second authority for something already owned elsewhere.

This mirrors the lab's existing research discipline: a new instrument needs an observed failure of the old one, not merely an available idea.

---

## 2. Roles and authority

```text
Roundtable  ->  Manager  ->  Coder  ->  Manager review  ->  Roundtable closure
```

| Role | Established analogue | Owns | Must not |
| --- | --- | --- | --- |
| **Roundtable** | Product owner + architecture review board | Roadmap priority, durable architecture/product decisions, disposition of discoveries, closure of completed work. | Use closure as a second code review. |
| **Manager** | Delivery lead + integrating reviewer | Turning accepted, roadmapped work into bounded work orders; dispatch; review against the work order and the DoD; acceptance. | Add roadmap scope; accept work that changed authority it was not commissioned to change. |
| **Coder** | Implementer | Implementing the bounded work order; producing tests/evidence; reporting findings. | Redefine roadmap, architecture or authority to make the task easier or larger. |
| **Intake** | Backlog / initiative box | Holding discoveries until Roundtable disposition. | Confer authority. A finding is not work. |

The two approvals answer different questions and are not interchangeable:

- **Manager acceptance:** *was the commissioned work implemented correctly?*
- **Roundtable closure:** *what does this result mean for the roadmap, product and architecture?*

### Findings discovered during implementation

A Coder or Manager finding outside the current work order does **not** become roadmap work by being found. It is written to intake (§4.1, `Discovered`) and waits for Roundtable disposition. The current task continues against its original bounds.

---

## 3. Delivery model: Kanban

Kanban is used rather than Scrum because the work is discovery- and evidence-driven: items are pulled when they are ready, not committed to a fixed-length sprint. There are no sprints, story points or ceremonies.

The two Kanban mechanisms that are load-bearing here are **explicit states with named transition owners** (§4.2) and **WIP limits** (§4.3).

---

## 4. Work-item lifecycle

### 4.1 States

```text
Discovered
  -> Initiative / Backlog
  -> Roundtable accepted
  -> Roadmapped
  -> Ready
  -> Dispatched
  -> In progress
  -> Manager review
  -> Implemented
  -> Roundtable closed
```

Off-path dispositions: `Parked`, `Rejected`, `Superseded`.

| State | Means |
| --- | --- |
| `Discovered` | Someone observed something. No authority, no commitment. |
| `Initiative / Backlog` | Recorded in intake as a candidate. Still not work. |
| `Roundtable accepted` | Roundtable agrees this is real work worth doing. Not yet prioritised. |
| `Roadmapped` | It has a place and a priority in the roadmap. |
| `Ready` | The Definition of Ready (§5) is satisfied. Eligible to be pulled. |
| `Dispatched` | A bounded work order exists and has been assigned. Counts against WIP. |
| `In progress` | A Coder is implementing it. |
| `Manager review` | Implementation and evidence returned; Manager is reviewing against the work order and the DoD. |
| `Implemented` | Manager accepted it. The commissioned work is correct. **Not closed.** |
| `Roundtable closed` | Roundtable has updated roadmap/architecture status from what actually landed. Terminal. |
| `Parked` | Real, but deliberately not now. Reason recorded. |
| `Rejected` | Will not be done. Reason recorded. Terminal. |
| `Superseded` | Replaced by another item or by a changed direction. Terminal. |

The same model is drawn as a UML state machine in [`04-development-workflow.puml`](../architecture/uml/04-development-workflow.puml). That diagram is a view of this section; where they disagree, this section is normative.

### 4.2 Transition ownership

Only the named actor may perform the transition.

| From | To | Who | Gate |
| --- | --- | --- | --- |
| — | `Discovered` | Anyone — Coder, Manager, Roundtable, operator, a tool | Observation is free. |
| `Discovered` | `Initiative / Backlog` | Anyone | Written to intake with its evidence. |
| `Initiative / Backlog` | `Roundtable accepted` | **Roundtable** | It is real work. |
| `Initiative / Backlog` | `Parked` / `Rejected` | **Roundtable** | Reason recorded. |
| `Roundtable accepted` | `Roadmapped` | **Roundtable** | Priority and roadmap placement decided. |
| `Roadmapped` | `Ready` | **Manager** | DoR (§5) satisfied. Roundtable may reject the readiness claim. |
| `Ready` | `Dispatched` | **Manager** | Bounded work order written; WIP limit respected. |
| `Dispatched` | `In progress` | **Coder** | Work actually started. |
| `In progress` | `Manager review` | **Coder** | Implementation and evidence returned. |
| `Manager review` | `In progress` | **Manager** | Rejected; corrections required. Does not create a new item. |
| `Manager review` | `Implemented` | **Manager** | DoD (§6) satisfied. |
| `Implemented` | `Roundtable closed` | **Roundtable** | Roadmap/architecture status updated from what landed. |
| `Roundtable closed` | `Initiative / Backlog` | **Roundtable** | Follow-up authorised as a **new** item, never as a continuation of a closed one. |
| any | `Superseded` | **Roundtable** | Direction changed or replaced. |
| `Parked` | `Initiative / Backlog` | **Roundtable** | Reactivated. |

### 4.2.1 Transitions that are always illegal

These are not judgement calls. If one appears to have happened, the work is out of process and returns to the last legal state.

| Illegal transition | Why |
| --- | --- |
| `Discovered` -> `In progress` | Skips disposition, roadmap and readiness. A finding became work without anyone deciding it should. |
| `Discovered` or `Initiative` -> `Roadmapped` by anyone but Roundtable | Manager or Coder taking roadmap authority. |
| `Roadmapped` -> `Dispatched` | Skips `Ready`. The Coder will invent policy during implementation. |
| `Ready` -> `Implemented` | No review happened. |
| `Manager review` -> `Roundtable closed` | Collapses the two approvals into one. |
| `Implemented` -> `Roundtable closed` performed by Manager | Manager taking roadmap authority. |
| Editing a terminal state backwards so a later result looks intended | Rewriting the record. |

### 4.3 WIP limits

| Limit | Value |
| --- | --- |
| `Dispatched` + `In progress` + `Manager review`, per Manager | **1** |
| Research lines executing a frozen pack concurrently | **1** |
| Open `Initiative / Backlog` items | unlimited — intake is cheap; starting is not |

Parallel implementation requires an explicit Roundtable authorisation recorded with the roadmap item. The limit exists because the observed failure mode in this repository is many partially-understood fronts, not slow throughput.

---

## 5. Definition of Ready (DoR)

An item is `Ready` only when every applicable line is answered **in writing**, before dispatch.

| # | Ready condition |
| --- | --- |
| 1 | **Authority / source.** Which roadmap item, ADR or accepted decision authorises this work. |
| 2 | **Bounded scope.** What is in scope, and an explicit list of what is not. |
| 3 | **Repository grounding.** The files, packages and current behaviour the work starts from, named by path. |
| 4 | **Dependencies and architecture.** What it depends on, and which existing architecture it must fit. |
| 5 | **Acceptance criteria.** Observable conditions, not intentions. |
| 6 | **Expected evidence / tests.** What will be run, and which result counts as passing. |
| 7 | **Unresolved decisions.** Listed explicitly, with who decides — Roundtable by default, not the Coder. |
| 8 | **Not authorised to redesign.** The parts the Coder must not change: frozen evidence, authority boundaries, established interfaces. |

Research work additionally requires the question, the controlled variable, the comparison/baseline, the measurement and the interpretation branches to be **frozen before execution** where the design calls for preregistration. That is existing lab practice and is not weakened here.

If line 7 is empty because nobody looked, the item is not Ready. Unresolved policy silently delegated to implementation is the failure this gate exists to prevent.

---

## 6. Definition of Done (DoD)

Manager may move an item to `Implemented` only when every applicable line holds.

| # | Done condition |
| --- | --- |
| 1 | **Implementation landed.** The commissioned change exists in the repository. |
| 2 | **Tests / regression evidence pass**, or each failure is explicitly dispositioned rather than ignored. |
| 3 | **Acceptance criteria satisfied**, demonstrably, against the criteria as written at dispatch. |
| 4 | **No unauthorised architecture.** No new authority, interface or mechanism beyond the work order. |
| 5 | **Authority / roadmap / architecture documentation updated** where the change requires it, including an ADR when a durable decision was made. |
| 6 | **Frozen evidence unchanged.** Frozen packs, fixtures and historical harnesses are byte-identical unless the work order was explicitly a re-freeze. |
| 7 | **Repository state is understandable to the next worker.** Handoff, backlog and roadmap do not contradict what landed. |
| 8 | **Completion evidence is sufficient for Roundtable closure** — Roundtable can decide what the result means without re-reading the diff. |

`Implemented` is not `Roundtable closed`. Manager cannot perform closure.

---

## 7. Document authority precedence

Documents have different jobs. The order below decides which one wins when two disagree, so a stale note cannot masquerade as current authority.

```text
1. live code + frozen evidence
2. accepted product / architecture / ADR authority
3. roadmap
4. backlog / initiatives
5. transient handoff / notes
```

Concretely, in this repository:

| Rank | Artifact | What it establishes |
| --- | --- | --- |
| 1 | the live packages (`adapters/`, `inspector/`, `modeller/`, `taskmodel/`, `worker/`, `fleet/`, `supervisor/`, the four task families, `calendar_job/`); frozen experiment packs; `frozen_manifest.json`; per-pack `expected.json` | What the system actually does, and what actually happened. |
| 2 | `PRODUCT.md`; accepted ADRs in `docs/decisions/`; this document, for process only | Durable product and architecture choices. |
| 3 | `docs/roadmap/work-interface-lab-roadmap.md` — a **research contract**, explicitly not product authority until its gates pass | Authorised direction and priority. |
| 4 | `docs/development/initiatives.md`; `work_interface/BACKLOG.md` | Candidate work. No authority. |
| 5 | `.handoff.md`; root working notes | Navigation only. |

Rules that follow from the order:

- If `.handoff.md` disagrees with the repository, the roadmap or an accepted ADR, **the handoff is stale** and is repaired. It never wins.
- If an architecture diagram disagrees with the code, **the diagram is wrong**. See [`docs/architecture/modelling-guide.md`](../architecture/modelling-guide.md).
- If the code disagrees with accepted architecture or product authority, that is a **discrepancy**, not a licence to redraw. It is recorded in [`docs/development/discrepancy-register.md`](discrepancy-register.md) and dispositioned by Roundtable.
- **Historical experiment evidence is never rewritten** to make current architecture look cleaner. A defect preserved as evidence — for example `authorized_reader.py`, backlog item B-3 — stays as it is; the correction is additive.

---

## 8. Existing artifacts in standard terms

| Existing artifact | Established term |
| --- | --- |
| `PRODUCT.md` | Product/architecture authority |
| `docs/roadmap/work-interface-lab-roadmap.md` | Roadmap + research contract with decision gates |
| `work_interface/BACKLOG.md` | Backlog, work-interface infrastructure |
| `docs/development/initiatives.md` | Intake / initiative box |
| experiment `PREREGISTRATION.md` | Frozen test design (preregistration) |
| experiment `CLOSURE.md` and disposition files | Result + disposition record |
| `frozen_manifest.json`, per-pack `expected.json` | Baseline / regression fixtures |
| `.handoff.md` | Transient operational handoff |
| module `--self-test`, `scripts/check_*.py` | Verification / acceptance evidence |
| `docs/decisions/ADR-*.md` | Architecture Decision Records |
| `docs/rfcs/` | Requests for Comments |
| `docs/architecture/uml/` | Reverse-engineered architecture views |

---

## 9. Where the process is recorded

| Concern | Location |
| --- | --- |
| This process | `docs/development/engineering-system.md` (this file) |
| Governance decision | `docs/decisions/ADR-0001-development-governance.md` |
| Architecture-model grounding decision | `docs/decisions/ADR-0002-architecture-model-grounding.md` |
| Notation choice | `docs/architecture/modelling-guide.md` |
| Architecture views | `docs/architecture/uml/` |
| Discoveries awaiting disposition | `docs/development/initiatives.md` |
| Known documentation-vs-repository discrepancies | `docs/development/discrepancy-register.md` |
| Contributor entry point | `CONTRIBUTING.md` |
| Agent entry point | `CLAUDE.md` |
| Durable development state | the issue, the PR, and its review — see §10 |

---

## 10. Where development state lives

Development state lives in the repository and in the standard GitHub objects around it. Nothing here is a new mechanism; this section only says which existing object carries which part of the lifecycle in §4.

| Object | Carries |
| --- | --- |
| **Repository** | Persistent engineering context and authority — code, frozen evidence, `PRODUCT.md`, ADRs, roadmap, this process. |
| **Issue** | One authorised work item: its purpose, bounds and acceptance criteria. |
| **Branch + PR** | The implementation state of that work item, including its commit history. |
| **PR review and comments** | Manager feedback, requested corrections, and technical acceptance. |
| **Issue closure** | Roundtable's roadmap/architecture closure. |
| **Chat** | Discussion and thinking aid. **Not** the durable transport for development state. |

### Reconstructing a work item

A dispatched worker should be able to rebuild everything it needs from repository state, in this order:

1. the repository's agent/contributor instructions — [`CLAUDE.md`](../../CLAUDE.md), [`CONTRIBUTING.md`](../../CONTRIBUTING.md), and this document;
2. the governing **issue**;
3. the **PR and its commits**, if implementation already exists;
4. the latest **Manager review or PR comment**.

If any of those four is missing something the next worker needs, the fix is to write it into that object — not into a chat message, a side file, or a bespoke handoff format.

Anything a worker reports at the end of a task belongs in the PR or the issue, where the next worker will look for it.

### Why this is written down

The failure mode it removes is specific and was observed before this system existed: worker reports and continuation instructions lived only in long, unsearchable chat threads and had to be copy/pasted between agents by hand. Chat is not searchable by the next worker, not versioned, and not visible from the repository. Everything durable therefore lands in an object that is.

### Dispatch is not self-service

**Manager dispatches the exact work item.** A worker does not scan the repository, notice something that looks `Ready` or next, and start it.

`Ready` is a statement about the item — its Definition of Ready is satisfied, so it is *eligible to be pulled* — not permission for whoever finds it. The `Ready -> Dispatched` transition is Manager's (§4.2), and `Dispatched -> In progress` is the point at which a worker begins.

A worker who believes the wrong thing was dispatched says so, and records anything else it noticed in [`initiatives.md`](initiatives.md). It does not re-choose its own task.
