# Learning Lab

A working research system for turning messy data work into **explicit deterministic workers**, then studying what an LLM is useful for **around** those workers: understanding new work, supervising established work, investigating novelty, and proposing improvements.

The central design idea is:

> **The AI designs, supervises, investigates and improves the workers. The workers do the work.**

This repository contains both a functioning deterministic task/fleet implementation and the research record that produced it. It is a research lab, not a production framework.

## Current product direction

The product is not meant to be an “AI incident dashboard” over an abstract fleet. The intended top-level object is a **company and the work being understood for that company**:

```text
company
  ↓
incoming files / workbooks / sheets / tables
  ↓
program measures what is actually present
  ↓
LLM helps interpret purpose and load-bearing unknowns
  ↓
explicit task model
  ↓
deterministic worker
  ↓
company system map: sources → modelled work → outputs/effects
  ↓
normal deterministic operation
  ↓
supervisor explains what matters, investigates novelty and proposes improvements
```

The repository contains all of these pieces. The live workspace (`supervisor/app.py`) describes itself as already recentred on this flow — the Fleet System Map is its primary surface, the incoming-data browser sits beside it, and the modeller is reachable from an unmodelled data directory as a "Define work" flow.

**`PRODUCT.md` has not been updated to reflect that**, and still lists the recentring among the next priorities. That disagreement is recorded as [discrepancy D3](docs/development/discrepancy-register.md) and raised as [initiative I-1](docs/development/initiatives.md); only Roundtable may resolve it. Until it does, read `PRODUCT.md`'s priority list knowing the code has moved past parts of it.

See [PRODUCT.md](PRODUCT.md) for the product/system map and the distinction between what exists now and what is still missing.

## What is implemented now

### Deterministic task floor

Established work runs without an LLM. The current floor includes:

- immutable model/task version history;
- deterministic task execution;
- committing effects with read-back verification;
- explicit refusals distinct from exceptions;
- inbox item identity and duplicate handling;
- crash/recovery distinctions between safe retry, already-landed and indeterminate effects;
- confirmations bound to exact model versions;
- investigations and exception handling;
- a read-only fleet/system map derived from authoritative worker state.

Four task families are represented in the current system:

- reservation;
- enrichment;
- aggregation;
- reconciliation.

### Task modeller

`modeller/` is the current DEFINE path. The operator selects data and describes the job in ordinary language. The program owns mechanically observed facts; the LLM interprets purpose and proposes the task model; load-bearing unknowns are asked only when evidence cannot settle them.

```bash
python -m streamlit run modeller/app.py
```

### Fleet and system map

`fleet/` owns established-worker state, operations views, investigation routing and the existing system map. The map is derived from authoritative state rather than storing a second description of the system. It already represents declared customer/scope lanes, inputs, modelled sources, workers, shared executors, effects and exception paths.

```bash
python -m streamlit run fleet/app.py
```

Choose **System map** in the fleet console to inspect the existing map.

### Supervisor workspace

`supervisor/` contains the explicit supervisory harness and the current Streamlit workspace. The supervisor has read/analysis/proposal authority but no silent production authority.

The workspace has advanced through several versions since this section was written; `supervisor/app.py`'s module docstring is the current description of what the surface does and which product priorities it closes. The floor it established, and still provides:

- a persisted supervisor-authored assessment;
- findings, priorities and normal/no-action context;
- improvement proposals with provenance;
- on-demand institutional routing;
- mandatory duplicate-before-conflict checking for proposed rules;
- human-gated rule activation;
- reconstructable supervisor sessions and bounded tool use.

On Windows:

```text
run-supervisor.bat
```

or directly:

```bash
python -m streamlit run supervisor/app.py
```

The supervisor workspace is **supporting machinery, not the final product shell**. Its integration with the company/data/map workspace described in [PRODUCT.md](PRODUCT.md) is the work that has since landed in `supervisor/app.py` — see the note under "Current product direction".

## The authority boundary

The project deliberately separates fact, interpretation and authority.

```text
PROGRAM / SOURCE
  owns mechanically observed facts

LLM
  may interpret, ask, analyse, explain and propose

HUMAN / INSTITUTIONAL MECHANISM
  controls changes to production authority
```

Important examples:

- a program may establish `left_coverage = 3/3`; it does not thereby establish “this is the intended join”;
- a declared refusal is a healthy outcome when the worker is following its policy;
- `effect_applied=True` means the effect was applied **and verified**;
- human confirmation resolves an exact claim for an exact model version; inference does not silently become observation;
- the supervisor may propose a rule, but it cannot silently activate one.

The recurring principle is:

> **Intelligence may discover useful questions. Repeated useful questions can become explicit machinery.**

## Repository map

The root intentionally contains both live system code and frozen research history. Start here:

| Path | Role |
| --- | --- |
| `adapters/` | input adapters, including workbook/data ingestion support |
| `inspector/` | mechanical observation / evidence production |
| `modeller/` | DEFINE path from observed data + purpose to task model |
| `taskmodel/` | shared task-model structures/contracts |
| `worker/` | deterministic worker/runtime machinery |
| `fleet/` | established fleet, operations, investigations and system map |
| `supervisor/` | supervisory harness, memory, improvements/rules and the Streamlit workspace |
| `reservation/` | reservation task family |
| `enrichment/` | enrichment task family |
| `aggregation/` | aggregation task family |
| `reconciliation/` | reconciliation task family |
| `calendar_job/` | established reservation/unattended runtime path |

The following are primarily **research record / frozen experimental evidence**, not the normal product entry point:

- `experiment*/`;
- `definition_phase/`;
- `s1/` … `s15/`;
- `uq1_audit/`;
- root research reports, falsification ledgers and historical work-order documents.

Do not “clean up” those directories merely because they are old. Negative results, frozen fixtures, grader corrections and counterexamples are part of the evidence trail.

## Research status

The early data-task modelling sequence established the deterministic/evidence floor. The later supervisory sequence S1–S15 is complete and frozen.

In very compressed form:

```text
S1–S5   what a supervisor notices, learns and computes
S6      explicit reconstructable harness + authority boundary
S7–S10  useful-question → measurement; method/measurement/authority interaction
S11     ordinary SUPERVISION separated from deliberate AUDIT
S12     harness enforcement and tool-budget closure
S13     operator desk: real supervisory findings and improvement suggestions
S14     routing suggestions to measurement / skill / rule / conflict / duplicate
S15     mandatory duplicate gate at the rule-authority boundary
```

Workspace v0/v0.1 then moved proven machinery out of the experiment folders into the live `supervisor/` product path.

No S16 laboratory is planned. The current goal is to use the established machinery inside a more coherent company-centric product rather than manufacturing additional governance puzzles without an observed need.

## Evidence discipline

The lab tries not to turn one successful model run into a universal claim. Repeated practices include:

- freeze expectations before model calls;
- preserve misses and negative results;
- mirror/counterexample cases;
- permutation tests where ordering could confound a result;
- falsify the grader as well as the model;
- distinguish mechanically observed facts from LLM inference;
- distinguish operator correction from mechanical truth;
- keep historical experiments frozen;
- record model/tool transcripts and provenance;
- state explicitly when evidence is narrow, n=1, model-specific or incomplete.

## Known engineering cleanup

A recent external review correctly identified several cheap maintainability improvements that remain useful but are secondary to product integration:

- share LLM client/configuration across **live product paths** while leaving frozen experiments pinned to what they actually ran;
- provide one runner for the many module `--self-test` entry points;
- add an explicit dependency manifest;
- split task-specific modeller prompts/policies out of the large `modeller/pipeline.py` when doing so can be kept behavior-preserving.

These are engineering tasks, not new research claims.

## Where to read next

- [`docs/development/engineering-system.md`](docs/development/engineering-system.md) — **how development works here**: roles, work-item states, Definition of Ready/Done, and which document wins when two disagree. It opens with the answers a new worker needs.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contributor entry point. [`CLAUDE.md`](CLAUDE.md) — the same for agents.
- [`docs/architecture/uml/`](docs/architecture/uml/) — architecture views, each marked MEASURED or INTENDED.
- [PRODUCT.md](PRODUCT.md) — current product mental model, live components, missing integration and next direction.
- [`.handoff.md`](.handoff.md) — what is being worked on right now. **Navigation only, never authority**: it ranks last in the precedence order and has been stale before.
- [`falsification_ledger.md`](falsification_ledger.md) — historical falsification/correction record.
- [`research_agentic_data_task_modelling.md`](research_agentic_data_task_modelling.md) — earlier research framing.
- [`MIGRATION.json`](MIGRATION.json) — repository migration authority/history.

## Repository history

This repository inherited the history and tags of `Alleyfoo/Data-Task-Modelling-Lab`. The old source was frozen at the migration boundary; active development continues in `Alleyfoo/learning-lab` on `main`.
