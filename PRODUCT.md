# Product map

This document describes the **current product direction** of Learning Lab: what the system is trying to become, which parts already exist, and which gaps are still product work rather than research questions.

It is intentionally different from the chronological experiment record. The experiments explain **why** the machinery exists. This document explains **what the user should eventually experience**.

## The product in one sentence

> A company brings messy operational data; the system helps understand that data and the work around it, turns established work into explicit deterministic workers, shows the resulting company flow as a map, and uses an LLM to interpret, supervise and improve that explicit system without giving the LLM silent production authority.

The top-level object is therefore **the company and its work**, not “the AI supervisor” and not “a fleet of agents.”

## The mental model

```text
COMPANY
  │
  ├── incoming data
  │     files
  │     workbooks
  │     sheets
  │     tables / collections
  │     columns / values / structure
  │
  ├── understanding
  │     mechanically observed facts
  │     inferred meaning
  │     load-bearing unknowns
  │     human confirmations
  │
  ├── modelled work
  │     source bindings
  │     task purpose
  │     deterministic model
  │     versioned worker
  │
  ├── operations
  │     runs
  │     refusals
  │     effects
  │     exceptions
  │     investigations
  │
  └── supervision / improvement
        what matters now?
        what changed?
        what should be investigated?
        what keeps recurring?
        what should become explicit machinery?
```

The product should make this structure understandable **without requiring the operator to know the repository architecture**.

## The intended journey

### 1. A company arrives with data

The starting point is not an established worker. It is an incoming company world:

```text
Acme Oy

incoming/
├── supplier_statement_aug.xlsx
│   ├── Statement
│   └── Notes
├── ledger_export.xlsx
│   ├── Transactions
│   └── Accounts
├── product_master.csv
└── old_report.xlsx
```

At this point the system must not pretend to know:

- which files are relevant;
- which sheets matter;
- which columns have business meaning;
- which datasets belong together;
- whether a file is master data, a transaction source, a lookup, an output or historical noise;
- what work the company actually wants done.

The first product surface therefore needs to be an **incoming-data browser**, not a JSON editor and not a supervisor dashboard.

The program can safely measure structure and contents. Meaning remains inferred until grounded.

### 2. The program observes; the LLM interprets

The core evidence boundary is:

```text
PROGRAM
  "field X exists"
  "coverage is 3/3"
  "right side is unique"
  "A + B reconciles to C"

LLM
  "these fields probably play these business roles"
  "this candidate binding best fits the stated job"
  "this question is load-bearing"
```

The LLM is useful because an unknown company cannot be reduced to a fixed schema in advance. It should be allowed to discuss the data with the operator and propose an understanding, while the system keeps observed fact, inferred meaning and human confirmation structurally separate.

### 3. The operator describes the work

The user should be able to say something ordinary, for example:

> We need to see which supplier invoices don't match our ledger.

The system can then combine the observed data with the purpose and propose an explicit flow:

```text
Supplier statement ─┐
                    ├── Reconciliation ──→ Differences
Ledger transactions ┘
```

Only unknowns that change the executable model or authoritative output should become questions.

### 4. Establish a deterministic worker

Once the relevant truths are established:

```text
understanding
  ↓
explicit task model
  ↓
deterministic preview
  ↓
human establishment / confirmation where required
  ↓
versioned worker
```

Ordinary repeated work should then execute locally/deterministically without needing an LLM to rediscover the task each time.

### 5. The flow becomes part of the company map

An established worker should not disappear into a table of worker IDs. It becomes a visible part of how the company is handled:

```text
Acme Oy

supplier_statement.xlsx ─┐
                         ├── supplier reconciliation ──→ discrepancy report
ledger_export.xlsx ──────┘

product_master.csv ────────→ order enrichment ─────────→ ERP upload
```

This map is the operator's main mental model of the system.

### 6. The supervisor interprets the map and its current state

The supervisor sits **over the explicit company system**, rather than replacing it with prose.

For example:

```text
ledger_export.xlsx
       │
       ▼
supplier reconciliation
       │
       !  exception
       │
       ▼
discrepancy report
```

Supervisor:

> Today's ledger source changed structure. The reconciliation worker did not run because the field it is bound to is absent. The supplier-statement side is unchanged.

The useful supervisor output points back to observable company objects: files, sheets, workers, runs, effects, exceptions, versions and measurements.

## The central workspace

The current UI pieces should eventually converge into one company workspace rather than remain independent applications.

A useful target shape is:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Company: Acme Oy                                                         │
├───────────────────┬─────────────────────────────────┬─────────────────────┤
│ DATA              │ COMPANY MAP                     │ SUPERVISOR          │
│                   │                                 │                     │
│ Incoming          │ orders.xlsx                     │ One flow needs      │
│ ├ orders.xlsx     │      │                          │ attention.          │
│ │ ├ Orders        │      ▼                          │                     │
│ │ └ Customers     │ Order enrichment ──→ ERP       │ Today's ledger      │
│ ├ ledger.xlsx     │                                 │ changed structure.  │
│ └ products.csv    │ ledger.xlsx                     │                     │
│                   │      │                          │ [Ask about this...] │
│ Established       │      ▼                          │                     │
│ ├ Task A          │ Reconciliation ──→ Differences │                     │
│ └ Task B          │                                 │                     │
└───────────────────┴─────────────────────────────────┴─────────────────────┘
```

This is a product direction, not a claim that the integrated shell already exists.

## Existing pieces

### Incoming-data / adapter floor — exists, integration incomplete

`adapters/` and the earlier ingestion work provide structural ingestion support, including spreadsheet/workbook handling. The current modeller, however, still starts from prepared/selectable sources rather than presenting the full incoming company file tree as the primary object.

**Product gap:** expose incoming files/workbooks/sheets/tables directly and preserve the distinction between “received but not understood” and “bound into modelled work.”

### Mechanical observation — exists

`inspector/` and modeller observation logic establish program-owned facts and evidence. This is a core product asset: it prevents the LLM from laundering plausible semantic claims into observations.

### Modeller — exists as a separate surface

`modeller/app.py` currently provides the DEFINE journey:

```text
Data
→ What do you want?
→ Understanding
→ Missing truth when necessary
→ Proposed task
→ Preview
```

This is close to the intended modelling interaction, but it needs to become part of the company workspace and start from the company's incoming data rather than feeling like a separate laboratory tool.

### Deterministic worker/runtime — exists

`worker/`, `taskmodel/` and the task-family packages contain the deterministic execution floor. Established work does not require an LLM at runtime.

Task families currently represented:

- reservation;
- enrichment;
- aggregation;
- reconciliation.

### Fleet map — exists and should be restored to the center

`fleet/system_map.py` + `fleet/map_component.py` already implement a read-only deterministic system map. Important properties are already correct:

- map state is derived, never an independent source of truth;
- declared customer/scope creates lanes;
- inputs, modelled sources, workers, effects and exception paths are typed nodes;
- shared executors live outside customer lanes;
- the investigator is not drawn as part of normal deterministic processing;
- status is recomputed from authoritative fleet state;
- worker nodes are clickable navigation.

The existing map begins **after modelling**. It sees sources that an established model declares.

**Product gap:** extend the visual mental model leftward so the operator can also see incoming company files/workbooks/sheets that have not yet been modelled or whose role is still unknown.

### Supervisor — exists as a separate supporting surface

`supervisor/` now contains the proven harness and Workspace v0.1:

- read-only fleet context;
- restricted Python / skills analysis;
- reconstructable sessions;
- authority boundaries and tool budgets;
- knowledge, preference and method memory;
- supervisor-authored current assessments;
- improvement backlog;
- on-demand improvement routing;
- duplicate/conflict guards for rules;
- human-gated rule activation.

This work is useful, but the current standalone Dashboard is **not the product center**.

The supervisor should become the communication/interpretation layer beside the company map:

```text
objective company map + state
          ↓
supervisor investigates / interprets
          ↓
what matters now?
why?
what should I do?
what could the system improve?
```

### Improvements and Rulebook — exist as institutional support

The Improvement backlog and Rulebook are not meant to dominate normal operation. They are how useful supervisory experience can become durable system change without giving the LLM self-modification authority.

A useful repeated factual question may become a deterministic measurement. A repeated investigation may become a skill. A repeated relevance judgment may become a preference/method. A normative constraint may become a proposed rule.

The important authority rule is:

> An LLM may suggest freely; an authority-bearing mechanism must enforce its own prerequisites.

For proposed rules that means, at minimum:

```text
proposal
→ evidence gate
→ mandatory duplicate/restatement check
→ conflict check
→ PROPOSED
→ human activation
```

## What the supervisor should communicate

A supervisor assessment is interpretation, not new machine truth.

Useful assessment language should therefore be attached to referents whenever possible:

```text
Finding
  "Ledger structure changed"

Observed support
  file: ledger_export.xlsx
  sheet: Transactions
  expected binding: Amount EUR
  observed field set: ...
  run: ...

Interpretation
  "This is why reconciliation is blocked."
```

The map and evidence make the prose understandable and contestable.

The product should avoid presenting unsupported supervisor prose as if it were another deterministic dashboard metric.

## Product authority model

```text
LLM CAN
  inspect permitted context
  analyse copied data
  interpret
  ask questions
  explain
  propose models
  propose investigations
  propose improvements
  propose rules

LLM CANNOT SILENTLY
  rewrite source truth
  promote worker versions
  execute production effects
  mutate customer/source data
  activate rules
  broaden its own authority
```

The deterministic platform is always alive. The LLM can be episodic: new-work definition, operator request, exception/investigation, scheduled review or later reflection.

## What is live code vs research record

### Live / current system path

| Path | Purpose |
| --- | --- |
| `adapters/` | input adapters / structural ingestion |
| `inspector/` | mechanically observed claims/evidence |
| `modeller/` | task definition/modelling path |
| `taskmodel/` | shared model contracts |
| `worker/` | deterministic execution machinery |
| `fleet/` | established workers, operations, investigations, system map |
| `supervisor/` | supervisory harness/workspace, memory, improvements, rules |
| `reservation/` | reservation task semantics/runtime |
| `enrichment/` | enrichment task semantics/runtime |
| `aggregation/` | aggregation task semantics/runtime |
| `reconciliation/` | reconciliation task semantics/runtime |
| `calendar_job/` | established unattended reservation path |

### Research evidence / history

The many `experiment*`, `definition_phase/`, `s1/`–`s15/`, `uq1_audit/` and historical root documents are not alternate live implementations. They are frozen evidence, failed hypotheses, mirrors, graders, corrections, intermediate architectures and handoffs that established the current floor.

They should remain available, but a new contributor should not have to infer the live product path from them.

## Research that is considered closed for now

The S11–S15 Rulebook laboratory sequence is intentionally closed:

```text
S11  SUPERVISION ≠ AUDIT
S12  authority/tool-budget enforcement closes the harness floor
S13  ordinary operator desk produces real findings and suggestions
S14  suggestions route to different institutional mechanisms
S15  duplicate checking becomes mandatory at the rule-authority boundary
```

The lesson is already sufficient for product use. More synthetic governance experiments should be triggered by an observed product failure, not by the availability of another test idea.

## Current product priorities

The next meaningful product work is not another supervisor laboratory or another dashboard polish pass. It is integration around the company:

1. **Company as the top-level object.** Give data, modelled tasks, runs, effects and supervision a clear owner/context.
2. **Incoming-data browser.** Show files → workbooks → sheets/tables → columns/samples before the system knows what they mean.
3. **Restore the system map as a primary surface.** Existing established-worker map is the base; extend it to connect incoming/unmodelled data to understood/modelled work.
4. **Embed the modeller in that context.** Select/inspect incoming data, discuss the job, establish a model, and see the new flow appear on the company map.
5. **Put the supervisor beside the map.** Supervisor findings should point to the company objects/evidence they interpret.
6. **Keep Improvements/Rules secondary.** They support institutional learning; they are not the user's main mental model of the company.

## Engineering cleanup worth doing alongside product work

These are useful and comparatively cheap, but should remain behavior-preserving:

- central LLM client/config for live product paths only;
- dependency manifest;
- aggregate runner for module `--self-test`s;
- task-specific prompt/policy extraction from `modeller/pipeline.py` when the modeller is next being changed.

Frozen experiment harnesses should keep the model/configuration they actually ran so historical evidence stays reproducible.

## Product test

The eventual usability test is simple to state:

> A new operator should be able to open a company and understand what data came in, what the system thinks it knows, what work has been established, where that data flows, what is wrong now, and what the supervisor is inferring — without reading repository internals.

That is the product target the current components should now converge on.
