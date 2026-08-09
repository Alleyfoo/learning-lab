# Data Task Modelling Lab

Research output for the workorder **Agentic Data Task Modelling** (2026-08-09).

**Status: research only. No implementation is authorized beyond Experiment 1.**

## The research object, restated

> The interesting problem is not whether agents can learn an executable schema. It is
> **deciding when that learned schema is allowed to run again.**

```text
MODELLING → candidate procedure → VERIFICATION
   → published procedure + applicability contract
   → future input → APPLICABILITY CHECK
        ├── match            → deterministic work
        └── mismatch/unknown → escalation
```

**Non-claim N1 — structural and statistical agreement cannot prove semantic continuity.**
Some semantic changes are observationally indistinguishable from the available data. The system
may never output "semantically unchanged" — only *"no evidence of change, at detection floor X,
declared with α and power."*

### A published task model

```text
  executable procedure
+ applicability contract              (L0-L5)
+ statistical detection capability    (floor: alpha, power, variance basis, assumptions)
+ evidence vector                     (semantic / aggregate / structural, each dated)
+ anchor freshness                    (per-dimension staleness)
+ known undecidable assumptions       (explicitly not checkable)
```

The last component is what separates this from "schema memory." A model that cannot enumerate
what it *cannot* establish is making an implicit claim of completeness it has no basis for.

### Three reasons to escalate

```text
1. observed mismatch        structure/statistics changed
2. epistemic insufficiency  question is below the detection floor
3. evidence expiry          NOTHING LOOKS WRONG - the independent anchor is stale
```

Reason 3 is a legitimate terminal state, not a failure:
`VALIDATION PASSES / APPLICABILITY VALID / EVIDENCE TOO STALE -> RE-ANCHOR REQUIRED`.
Ordinary monitoring has no state for this and reports it as health.

## Decision

### AMEND, then BUILD (narrow)

- **AMEND** — `Data-tool.Template` must gain declared applicability, grain/invariants, a
  separated canonical layer, instance versioning and provenance before any modelling network
  is built. It is a reader configuration, not a task model.
- **BUILD** — Experiment 1 only ([Drift Discrimination Harness](experiment_001_drift_discrimination.md)).
  No agents, no LLM, no new architecture.
- **DO NOT BUILD YET** — the agentic modelling network, the retrieval index, the escalation
  protocol, or any cross-repo merge.

## Headline findings

1. Producing a rerunnable, agent-independent transformation is **already established prior
   art** — five of eight surveyed external systems do it, and schema-mapping reuse dates to
   2005. It is not the open problem.
2. One-off transformation generation is **~70–80% accurate** in published systems
   (AutoDCWorkflow ops F1 ≈ 0.71; SpreadsheetLLM table detection F1 = 78.9). Adequate for
   human-reviewed work, inadequate for unattended publication.
3. The open problem is therefore **verification, applicability and drift classification** —
   which no surveyed system implements.
4. **Semantic change is undetectable from structure by definition, and frequently undetectable
   from statistics too** (N1). The contribution available here is *honest quantification of what
   cannot be known* — a published detection floor per contract — not detection.
5. **The memory object is a triple**: executable procedure + applicability contract +
   evidence/history. Not `mapping.json`. Historical agreement counts as evidence only to the
   extent the history is independently trustworthy, so baselines are tiered T0–T3 and carry
   `periods_since_independent_anchor`.
6. **None of the four existing repositories contain any LLM code.** The modelling plane is
   greenfield; the deterministic scaffolding already exists.
7. `Data-tool` has a persistent artifact and no publication boundary. `Data-agents` has the
   publication shape and no memory. Neither has applicability. That is the missing middle.

## Deliverables

| # | Document | Contents |
| --- | --- | --- |
| 1 | [research_agentic_data_task_modelling.md](research_agentic_data_task_modelling.md) | Main report — answers Q1–Q10, gap analysis, decision |
| 2 | [comparative_system_table.md](comparative_system_table.md) | 10 systems × 19 columns, split into 4 readable panels |
| 3 | [repo_reuse_map.md](repo_reuse_map.md) | Field- and line-level inventory of the four repositories |
| 4 | [falsification_ledger.md](falsification_ledger.md) | H1–H6 tested, with contrary evidence recorded |
| 5 | [unanswered_questions.md](unanswered_questions.md) | 11 open questions, tiered; plus questions closed by this study |
| 6 | [experiment_001_drift_discrimination.md](experiment_001_drift_discrimination.md) | The single recommended first experiment |
| 7 | Decision | §13 of the main report; summarized above |
| 8 | [workorder_amendment_001.md](workorder_amendment_001.md) | Amendment 001 — renames L4, adds N1, memory triple, revised sequence |
| 9 | [workorder_amendment_002.md](workorder_amendment_002.md) | **Amendment 002 — read first.** Detection power (α + power), evidence dimensions replacing tiers, three escalation reasons, preregistration protocol |

## Sequence

```text
1. Amend research WO                                    <- done
2. Define applicability levels (L0-L5) + evidence tiers
3. Build deterministic drift corpus
4. Measure false-apply / false-escalate
5. Determine what applicability evidence is actually useful
6. THEN give agents the job of producing
   procedures + applicability claims + backing evidence
```

Step 6 is last because before step 5, "build a schema" is an underspecified instruction.

## Method

- Four repositories cloned read-only and inspected at pinned commits (`Data-tool` `ab10b8c`,
  `Data-agents` `22ec1dd`, `Pipe-transformation` `3f7c941`, `data-frame-tool` `60c5127`).
  Nothing was modified or merged.
- Eight external system families researched from primary sources where available
  (arXiv full texts, project repositories, vendor documentation).
- Unknowns are marked `unknown/not established` rather than inferred. Two PDFs that could not
  be text-extracted are flagged in [unanswered_questions.md](unanswered_questions.md).

## Highest-priority action that is not software

Start the **UQ-1 retrospective audit**: classify 12–24 months of archived provider deliveries
into cosmetic / structural / semantic change events. That distribution determines whether the
proposed architecture pays for itself, cannot be obtained from any paper, and requires no code.
