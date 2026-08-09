# Data Task Modelling Lab

Research output for the workorder **Agentic Data Task Modelling** (2026-08-09).

**Status: research only. No implementation is authorized beyond Experiment 1.**

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
4. **Semantic drift is undetectable from structure by definition**, and is the least-addressed
   drift class in both research and industry. It is the strongest candidate for genuine
   contribution.
5. **None of the four existing repositories contain any LLM code.** The modelling plane is
   greenfield; the deterministic scaffolding already exists.
6. `Data-tool` has a persistent artifact and no publication boundary. `Data-agents` has the
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
