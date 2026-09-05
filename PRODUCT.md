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

This shape is now **partly real**: `supervisor/app.py` is a single workspace whose primary tab already places the incoming-data browser, the company system map and the supervisor's assessment together. What the sketch still shows and the workspace does not is the **company header** — the workspace is fleet-wide rather than scoped to one company. See "Current product priorities", remaining gap 1.

## Existing pieces

### Incoming-data / adapter floor — exists, integrated to sheet level

`adapters/` and the earlier ingestion work provide structural ingestion support, including spreadsheet/workbook handling.

The incoming company file tree is now a primary object: `supervisor/incoming.py` scans the `data/` library and every worker's inbox/processed/exceptions, and the browser renders it beside the map. Each directory is marked `worker:<name>` / `no worker link` / `model exists`, which is the “received but not understood” versus “bound into modelled work” distinction this section asked for. Modelling starts from that tree rather than from prepared sources.

**Remaining product gap:** the tree stops at file and sheet names. Columns and sample rows appear only inside the Define-work flow, and only for a directory with no worker and no model.

### Mechanical observation — exists

`inspector/` and modeller observation logic establish program-owned facts and evidence. This is a core product asset: it prevents the LLM from laundering plausible semantic claims into observations.

### Modeller — exists, and is now embedded in the company workspace

`modeller/app.py` remains available as its own surface, and provides the DEFINE journey:

```text
Data
→ What do you want?
→ Understanding
→ Missing truth when necessary
→ Proposed task
→ Preview
```

That journey is now also reachable from inside the company workspace: selecting an unmodelled directory in the incoming browser opens a Define-work panel that drives this same floor through `supervisor/define.py` — a glue layer over `modeller/pipeline.py` and `modeller/builder.py`, not a second modeller — and ends at an explicit human-gated Establish, after which the worker appears on the map. Modelling therefore starts from the company's incoming data rather than from a separate laboratory tool.

### Deterministic worker/runtime — exists

`worker/`, `taskmodel/` and the task-family packages contain the deterministic execution floor. Established work does not require an LLM at runtime.

Task families currently represented:

- reservation;
- enrichment;
- aggregation;
- reconciliation.

### Fleet map — exists and is now the center

`fleet/system_map.py` + `fleet/map_component.py` already implement a read-only deterministic system map. Important properties are already correct:

- map state is derived, never an independent source of truth;
- declared customer/scope creates lanes;
- inputs, modelled sources, workers, effects and exception paths are typed nodes;
- shared executors live outside customer lanes;
- the investigator is not drawn as part of normal deterministic processing;
- status is recomputed from authoritative fleet state;
- worker nodes are clickable navigation.

The map is now the workspace's primary surface: first tab, centre column, with the incoming-data browser to its left and the supervisor's assessment on top. A company known only from an `intake.json` sidecar appears as a scope node before any worker exists, so a company with data but no modelled work is visible.

For **data**, the map still begins after modelling: it sees sources that an established model declares.

**Remaining product gap:** extend the visual mental model leftward for data as well — incoming files/workbooks/sheets that have not yet been modelled, or whose role is still unknown, are not nodes on the map, and nothing draws the edge from an arriving file to the modelled work it became. Today they are visible beside the map rather than on it.

### Supervisor — exists, and now sits beside the map

`supervisor/` contains the proven harness and the workspace built on it. `supervisor/app.py`'s module docstring is the current description of that surface. The floor it established:

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

The Dashboard is no longer the centre: the workspace opens on the System Map, the supervisor's current assessment renders on top of that company context, and the Dashboard is the fuller supporting read.

**Remaining product gap:** a filed assessment is plain text — findings, priorities and normal-context strings, with suggestions carrying free-text evidence. Nothing binds a finding to the worker, company or map node it interprets, so the operator cannot move from a finding to the object it is about.

The interpretation layer beside the company map:

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

The six priorities below were written before the v0.2–v0.6 integration work landed. They were re-grounded against the live repository in issue #5; this section now records the measured state rather than the original intent.

Two are delivered. Four are partially delivered, and the remaining gap in each is the actual next product work. None was found undelivered.

### Delivered

**4. Embed the modeller in the company context.** Selecting an unmodelled `data/` directory in the incoming browser opens a Define-work panel that runs the existing modeller floor one stage at a time — inspect, declare workbook sheets, observe, interpret, propose, answer a load-bearing question, deterministic preview — and ends at an explicit, human-gated **Establish worker**, after which the new worker appears on the map in its company's lane. `supervisor/app.py` `_render_define_panel` / `_render_discover_stage`, over `supervisor/define.py`, which is a glue layer on `modeller/pipeline.py` + `modeller/builder.py` rather than a second modeller. The LLM proposes; only the operator establishes.

**6. Keep Improvements/Rules secondary.** The workspace opens on **System Map**; Improvements and Rules are separate later tabs, and the Dashboard is explicitly the fuller supporting read rather than the centre. `supervisor/app.py` tab order.

### Partially delivered — these gaps are the next product work

**1. Company as the top-level object.** *Delivered:* a company is a typed, clickable object on the map, its lanes derived from each worker's declared `customer`; selecting one opens a panel gathering that company's established work, incoming/known data, declared destinations and an "add a data source" action. Pre-worker company identity exists through an `intake.json` sidecar, so a company with data but no worker still appears.
*Remaining gap:* the workspace is not **scoped** to one company. The map renders every scope at once and nothing selects a company as the container for the whole workspace, so the single-company shell sketched under "The central workspace" is not the current shape.

**2. Incoming-data browser.** *Delivered:* the browser lists the `data/` library and every worker's inbox/processed/exceptions, down to **file and sheet names**, and marks each directory `worker:<name>` / `no worker link` / `model exists` / `adapter` — the "received but not understood" versus "bound into modelled work" distinction this section asked for.
*Remaining gap:* it stops at the sheet. Columns and sample rows are visible only inside the Define-work flow, which opens only for a directory that has no worker and no model. A directory that is already modelled has no column or sample view anywhere.

**3. System map as the primary surface.** *Delivered:* the map is the primary surface — first tab, centre column, browser to its left and the supervisor's assessment on top — and it stays derived from authoritative fleet state and writes nothing. Pre-worker companies now appear on it.
*Remaining gap:* the leftward extension asked for under "Fleet map" below is still open for *data*. The graph is built from workers, scopes and shared executors; no incoming file, workbook or sheet is a node, and no edge connects an arriving file to the modelled work it became. The map still begins after modelling; the browser sits beside it rather than the map reaching into it.

**5. Put the supervisor beside the map.** *Delivered:* it is beside it. The current assessment renders on top of the company context in the same tab, "Review fleet" runs from there, and the Dashboard is the supporting full read.
*Remaining gap:* findings do not yet **point to** the company objects they interpret. A filed assessment is plain text — findings, priorities and normal-context strings, with suggestions carrying free-text evidence — so nothing binds a finding to the worker, company or map node it is about, and there is no way to click a finding and land on that node.

### How to read this section

Each "remaining gap" is a bounded piece of product work, not a restatement of the original priority. The relative order above is the original one; Roundtable owns any re-ordering.

The measured evidence behind each disposition is recorded in [`docs/development/discrepancy-register.md`](docs/development/discrepancy-register.md) D3.

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
