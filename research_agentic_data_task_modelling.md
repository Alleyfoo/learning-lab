# Research Report — Agentic Data Task Modelling

**Status:** Research only. Build authorization NOT granted at time of writing.
**Working title:** Data Task Modelling Lab
**Date:** 2026-08-09
**Amended by:** [workorder_amendment_001.md](workorder_amendment_001.md) — read that first.
It renames L4, adds non-claim N1, defines the memory object as a triple, adds evidence
provenance tiers, and revises the build sequence. Where this report and the amendment differ,
**the amendment wins**.

**Scope:** Answers Workorder sections 6–12. Companion deliverables:
[comparative_system_table.md](comparative_system_table.md),
[repo_reuse_map.md](repo_reuse_map.md),
[falsification_ledger.md](falsification_ledger.md),
[unanswered_questions.md](unanswered_questions.md),
[experiment_001_drift_discrimination.md](experiment_001_drift_discrimination.md).

---

## 0. Headline finding

The study set out to test whether an agentic modelling network can leave behind a reusable
executable task model. The literature answers that sub-question already, and answers it
positively: **five of the eight external families surveyed persist an agent-independent,
re-executable artifact**, and have done so since before LLMs (corpus-based schema matching,
2005). Producing a rerunnable transformation from messy input is not the open problem.

The open problem, restated from the evidence:

> A one-off transformation is roughly 70–80% correct in current published systems
> (AutoDCWorkflow workflow-operation F1 ≈ 0.71; SpreadsheetLLM table detection F1 = 78.9).
> That is adequate for a **human-reviewed** workflow and inadequate for **unattended
> publication**. What converts an 80%-correct one-off procedure into a publishable model is
> not better generation. It is **verification, applicability and drift classification** —
> and those three are the parts no surveyed system implements.

This reframes Hypothesis H6. The hard problem is not "task modelling rather than one-off
transformation." It is **the publication boundary**: the evidence under which a procedure is
allowed to run again, and the machinery that detects when that evidence has stopped holding.

Stated as the research object (per [amendment A1](workorder_amendment_001.md)):

> The interesting problem is not whether agents can learn an executable schema. It is
> **deciding when that learned schema is allowed to run again.**

And the boundary of what any such machinery can achieve, stated as a non-claim
([amendment A3](workorder_amendment_001.md)):

> **N1 — Structural and statistical agreement cannot prove semantic continuity.**
> Some semantic changes are observationally indistinguishable from the available data. The
> system may therefore never output "semantically unchanged" — only *"no evidence of change,
> at detection floor X."*

Second headline finding, from repository inspection: **none of the four existing repositories
contain any LLM code at all.** `Data-agents` "agents" are Markdown role specifications for
Copilot/Codex plus a deterministic Python runtime. This is materially better news than
expected — the deterministic scaffolding exists and the modelling plane is genuinely a
greenfield decision rather than a rewrite.

---

## 1. Q1 — What is the persistent artifact?

### 1.1 What the field actually persists

| System | Persisted artifact | Executable without the agent? |
| --- | --- | --- |
| Agent Workflow Memory | NL workflow description + abstracted action trajectory | **No** — injected into the LLM prompt |
| Agentic Schema Refinement | Materialized SQL views (1,146 from a 61-table schema) | Yes |
| Harmonia / bdi-kit | Declarative JSON mapping specification | Yes — replayed via `materialize_mapping()` |
| AutoDCWorkflow | OpenRefine operation list (JSON) | Yes |
| DeepPrep | Ordered operator pipeline `P = (S, o₁→…→o_k)` | Yes |
| Executable Schema Contracts | Versioned YAML schema `Σ = (ℱ, 𝒯, ℛ, ℐ)` | Mostly — LLM only for optional schema extension |
| SpreadsheetLLM | **Nothing** — per-call encoding | n/a |
| Flatfile | Learned per-customer mappings + corpus-trained model | Yes |
| Meta-mappings (Atzeni et al.) | Meta-mapping over meta-schemas | Yes |

The convergent answer across the data-preparation literature is **a declarative mapping
specification plus an ordered list of deterministic primitives**. Only the web-agent line of
work (AWM) prefers an agent-dependent artifact, and it does so for a defensible reason: web
UIs are non-stationary in a way spreadsheet exports from a stable ERP are not. That design
should not be imported into this problem.

### 1.2 What is missing from every one of them

None of the nine persist **the conditions under which the artifact is allowed to apply**.

- Harmonia's plan is rerunnable but says nothing about which future file it fits.
- DeepPrep's pipeline is rerunnable and the paper states no cross-task memory at all.
- AutoDCWorkflow is scoped to one `(purpose, table)` pair.
- Executable Schema Contracts comes closest, with **sufficiency gating** — a cheap check of
  whether the current schema resolves a query's entity types — but that is a *query-side*
  check, not a *source-side* applicability predicate.
- Meta-mappings is the only line of work explicitly about applying a mapping to a
  *different* source schema, via generalization to meta-schemas. It is relational, not
  workbook-shaped, and pre-dates the messy-Excel setting.

### 1.3 Recommended artifact: five linked objects, not one

`Data-tool.Template` is a single flat dataclass that collapses several distinct lifetimes into
one file. The evidence says these should be separated, because they change at different rates
and require different authority to change:

| Object | Contents | Changes when | Who may change it |
| --- | --- | --- | --- |
| **A. Canonical model** | Target fields, measures + their business definitions, grain, identity rule, period semantics | Business definition changes | Human, explicitly |
| **B. Source adapter** | Fingerprint, structural locator (sheet/region/header), source→canonical mapping, ordered transformation primitives | Source layout changes | Modelling plane, after replay |
| **C. Applicability predicates** | Evidence under which B may run (see §5) | With B | Modelling plane |
| **D. Verification suite** | Invariants, historical replay cases, expected aggregate bands | With A or B | Control plane |
| **E. Provenance record** | Why each semantic assignment was made, on what evidence, by whom, effective from when | Append-only | Never mutated |

`Template` today is a partial **B** with none of **A**, **C**, **D** or **E**.
See [repo_reuse_map.md](repo_reuse_map.md) for the field-level assessment.

Note that Data-agents already names the A/B split correctly — its Schema Agent spec requires
declaring `schema_layer: "core"` or `schema_layer: "adapter"`. That distinction is the single
most reusable idea in the existing repositories and should be preserved verbatim.

---

## 2. Q2 — What is the smallest business intent required?

Two viable minimal-intent forms exist in the literature and they are not equivalent:

- **(a) Target canonical vocabulary supplied** — Harmonia maps clinical data to the GDC
  standard. Intent arrives as a *schema*, not as prose. Cheapest and most verifiable.
- **(b) Natural-language purpose question** — AutoDCWorkflow supplies purposes as questions
  ("Identify the main facility types that are inspected"); 67 were hand-written across four
  datasets. The LLM then selects target columns. Weaker, and it still assumes the relevant
  table is already known.

For recurring provider sales the receiver already knows what it wants, so form (a) applies.
The minimum set, from the evidence and from what verification requires:

1. **Measured entity** — what a row is about (article/SKU identity, and what counts as the
   same article across providers).
2. **Measure(s) and their business definition** — not "revenue" but "net sales, excluding
   freight, excluding VAT, in EUR, credit notes as negative rows."
3. **Time semantics** — period vs. event; invoice date vs. posting date vs. delivery date.
4. **Grain** — one row per (article, period, provider), or whatever the true grain is.
5. **Identity expectation** — what makes a row unique; whether returns are negative rows or a
   separate dataset.

**Is anything less viable?** No, and the reason is verification, not extraction. You can
extract without (2) and (4). You cannot *verify* without them, and an unverified procedure
cannot cross a publication boundary — it is a transformation, not a task model. Items 1, 4
and 5 are largely inferable from data (Executable Schema Contracts infers identity keys from
uniqueness ratios and naming patterns deterministically). Item 3 is partly inferable. **Item 2
is never inferable from data alone**, and neither is the scope rule for what counts as a sale.
That is the load-bearing answer to Q8.

---

## 3. Q3 — What happens before schema inference?

Coverage of the eight pre-mapping stages by existing work:

| Stage | Coverage | Evidence |
| --- | --- | --- |
| 1. Business intent | **Partial** | AutoDCWorkflow (NL purpose), Harmonia (target vocabulary) |
| 2. Candidate-data discovery | **Thin** | SpreadsheetLLM/TableSense find *tables*; nothing decides which table is the business-relevant one |
| 3. Structural interpretation | **Dense** | SpreadsheetLLM, TableSense, semantic table structure identification; Data-tool header detection |
| 4. Semantic interpretation | **Dense** | Schema matching literature, Harmonia, Flatfile |
| 5. Grain determination | **Essentially absent** | Closest: identity-key inference in Executable Schema Contracts |
| 6. Relationship / join discovery | **Handled deterministically** | Executable Schema Contracts: FK inference by field value overlap with confidence scoring, cardinality from distribution asymmetry |
| 7. Normalization (wide→long) | **Dense** | DeepPrep/Text-to-Pipeline operators; Data-tool unpivot |
| 8. Canonical mapping | **Very dense** | COMA++, corpus-based matching, meta-mappings, Harmonia, Flatfile |

Two stages are assumed away almost universally:

- **Stage 2 in its real form.** AutoDCWorkflow states outright that the raw table is provided.
  SpreadsheetLLM detects table regions at 78.9 F1 — meaning roughly one in five is wrong —
  and detection does not answer "is this the sales data or the summary tab that double-counts
  it." The bookkeeping-export case, where fourteen sheets arrive and three are traps, is not
  addressed by anyone surveyed.
- **Stage 5, grain.** Nobody declares grain as a checked invariant. This matters
  disproportionately: a grain error does not raise an exception, it silently multiplies
  revenue. It is the highest-consequence undetected failure in the whole pipeline.

---

## 4. Q4 — What should memory contain?

**The hypothesis under test:** published executable models should be the primary long-term
memory; conversational memory should not be the production source of truth.

**Verdict: supported, with one system providing evidence by way of its own weakness.**

- *Agentic Schema Refinement* persists strong artifacts (SQL views) but implements
  cross-session memory as **retained conversation history**, and reports no quantitative
  measurement of whether it prevents rediscovery — across 1,146 generated views. That is the
  anti-pattern, demonstrated in a peer-reviewed system, unmeasured.
- *AWM* persists procedural memory that is genuinely reusable but is bound to the LLM by
  construction (prompt injection). Its reported failure mode is instructive: workflows break
  on unexpected intermediate states, because the workflow encodes a trajectory rather than
  the conditions under which the trajectory is valid. That is the applicability gap again,
  arriving from a different direction.
- *Flatfile* is the strongest real-world evidence for the hypothesis: memory is mapping
  decisions at corpus scale, not conversations, and it is reused per customer.
- *Corpus-based schema matching* (2005) and *meta-mappings* (2019) establish the principle
  pre-LLM.

**The memory object is a triple, not a mapping file** ([amendment A4](workorder_amendment_001.md)):

```text
MEMORY OBJECT =
      executable procedure
    + applicability contract
    + evidence / history
```

At 2,000-company scale you do not retrieve company 947's conversation. You retrieve a versioned
model stating: *I know how to process this source when these conditions hold, and here is the
evidence supporting that claim.* The third element is what the survey found missing everywhere —
without it the contract is an assertion rather than something auditable.

**Recommended memory composition:**

1. **Primary** — versioned published task models (canonical + adapters + applicability contract + backing evidence). Production source of truth.
2. **Retrieval index** — source fingerprints → candidate adapters. Enables the 10→2,000 story.
3. **Semantic decision records** — which human answered what, when, on what evidence, effective from when. Required both to avoid re-asking and to make semantic drift detectable at all.
4. **Failure / negative memory** — candidate models that were *rejected* and why they failed replay. **Absent from every system surveyed.** Without it the modelling plane re-proposes known-bad hypotheses.
5. **Conversational memory** — debugging aid only; explicitly not a production input.

---

## 5. Q5 — How is applicability represented?

Almost absent from the literature. The nearest things found:

- `expected_headers` in our own `Pipe-transformation` config (a crude but real predicate).
- `warn_on_schema_diff` + `fail_on_missing` / `fail_on_extra` in `Data-tool` — a rudimentary
  applicability check, already implemented, but computed at runtime rather than declared, and
  name-set-based only.
- Sufficiency gating in Executable Schema Contracts (query-side).

Proposed layered representation, ordered cheap → expensive, all levels except L5 decidable by
the work plane with no intelligence:

| Level | Predicate | Detects |
| --- | --- | --- |
| **L0 Fingerprint** | Sender, filename pattern, sheet-name set, sheet count, workbook structure hash, producing application metadata | Source family membership; ERP change |
| **L1 Structural** | Expected sheet(s), header row location, column-name multiset, column count, position of key columns | Cosmetic + structural drift |
| **L2 Typing** | Per-column dtype/format profile, null-rate bands, cardinality bands | Format changes, column reuse |
| **L3 Grain** | Declared key must be exactly unique; row-count band per period | **Grain change** — the silent killer |
| **L4 Statistical evidence relevant to applicability** | Aggregate magnitude bands per period, share of negative rows, cross-field consistency (e.g. `amount ≈ qty × unit_price` within historical tolerance) | *Evidence that something changed.* **Not** evidence that meaning is unchanged — see N1 |
| **L5 Semantic assertions** | Recorded claims ("amount excludes freight") with evidence source and confidence | Not decidable from data — triggers escalation on external evidence only |

**L4 was originally named "Statistical" and described as the "only automatic semantic-drift
signal."** That overstated it, and the label has been corrected
([amendment A2](workorder_amendment_001.md)). L4 produces evidence *relevant to* applicability;
it does not validate semantics.

**Each contract must publish its detection floor** ([amendment A3.1](workorder_amendment_001.md)).
Given the historical variance of a measure, the size of definitional shift L4 would catch at a
stated confidence is computable, and should be carried as a property of the contract:

```jsonc
"L4_detection_floor": {
  "period_total": { "min_detectable_shift_pct": 3.2, "confidence": 0.95, "baseline_periods": 14 }
}
```

This turns N1 from a disclaimer into a number. "Could freight have been folded into this
measure?" becomes: *freight is ~0.4% of revenue here, below our 3.2% floor — undecidable from
the data; only external evidence settles it.*

The critical design consequence: **L5 is not checkable**, so the fingerprint at L0 must carry
source-*system* identity markers (producing application, export template version, sheet naming
style). A provider switching ERP is the cheapest available proxy for "the semantics may have
moved," and it is observable in file metadata.

---

## 6. Q6 — How is drift classified?

| Class | Automatically detectable? | Automatically repairable? |
| --- | --- | --- |
| **Cosmetic** (rename, reorder, sheet rename, date format) | Yes — L1/L2 | Yes, with bounded risk: require agreement of synonym match **+** type profile **+** value-overlap before accepting a rename |
| **Structural** (sheet split, wide→long, grain change, new join, returns separated) | Yes, **provided the invariant was declared** — wide→long shows as period-like column names; grain change is visible *only* if L3 declared a uniqueness key | Sometimes; escalate to modelling, not necessarily to a human |
| **Semantic** (`Revenue` structurally identical, now includes freight) | **No.** Structure is unchanged by definition | No |

Semantic drift has exactly three possible signals, and only the first is automatic:

1. **Statistical discontinuity vs. history (L4)** — necessary but not sufficient; a genuinely
   good sales month looks identical to a definition change.
2. **External evidence** — provider announces an ERP migration; file creator application
   changes; sheet naming style shifts.
3. **Cross-field consistency breaks** — `amount ≠ qty × unit_price` at a tolerance that
   previously held.

The industry literature independently converges on this: semantic drift "gets the least
attention" of the drift classes, and no pipeline test catches it — pipelines complete
successfully while loading misaligned data.

**Conclusion, corrected.** Semantic change can sometimes be detected as an *anomaly*, never
*classified*, without external evidence — and **often it cannot be detected at all**. Where the
magnitude of a definitional change falls below the natural variation of the measure, it is
observationally indistinguishable from a normal period. That is non-claim **N1**, and it is a
permanent property of the problem rather than a limitation of current methods.

The architecture must therefore carry historical statistical baselines, recorded semantic
assertions, a published detection floor, and a cheap external-evidence channel — and it must
never report "semantically unchanged." The strongest permitted statement is *"no evidence of
change, at detection floor X."*

This remains the strongest candidate for genuine contribution in the workorder, but the
contribution is **honest quantification of what cannot be known**, not detection.

---

## 7. Q7 — What is the feedback contract?

DeepPrep gives the clearest empirical answer, and it is directly transferable. Its environment
returns, per operator execution:

- materialized **intermediate table states**;
- **execution errors**, propagated to the agent;
- **runtime exceptions** recorded as failure annotations (column mismatch, type error);
- **sample outputs** to ground the next decision.

Revision is tree-structured: nodes are environment states, edges are operator executions;
on failure the agent backtracks to the state where the wrong decision was made, expands an
alternative branch, and **reuses the valid operator prefix**. Exploration is capped at 5 turns.
Crucially, ground-truth target tables exist only for *evaluation* — the agent never sees them.
That matches the workorder's constraint exactly.

The minimum feedback contract for this problem, extending DeepPrep with what a recurring
source makes available:

| Signal | Source | Purpose |
| --- | --- | --- |
| Executability + error trace | Runtime | Repair syntax/type errors |
| Intermediate state (schema, shape, sample) | Runtime | Ground the next operator choice |
| Mapping coverage | Adapter vs. observed columns | Detect unmapped/dropped source data |
| Identity coverage | Declared key vs. observed | Detect grain violation |
| Invariant results | Verification suite (D) | Detect structural + statistical drift |
| Aggregate disagreement **vs. the previously accepted period** | Historical replay | Detect semantic drift candidates |
| Transformation trace | Runtime | Provenance + human review |

**The one advantage this problem has over everything surveyed:** because the source recurs,
*previously accepted outputs are candidate ground truth*. No surveyed system uses this, because
none of them operate on a recurring source.

**But historical agreement is evidence only to the extent the historical result is
independently trustworthy** ([amendment A5](workorder_amendment_001.md)). Otherwise the system
manufactures its own certainty:

```text
wrong model → wrong output → output becomes memory
           → future wrong model matches memory → "verified"
```

Baselines must therefore be tiered by provenance, and **the tiers are not one ranking** — T2
and T3 are strong on different axes and each is blind where the other is strong:

| Tier | Source | Strong on | Blind to |
| --- | --- | --- | --- |
| **T0** | Procedure-generated, unreviewed | Nothing — self-referential | Everything |
| **T1** | Procedure-generated, passed declared invariants | Internal consistency | Anything the invariants don't encode |
| **T2** | Independently reconciled to an external artifact (provider's stated total, ERP control total, settlement figure) | **Aggregate correctness** | **Meaning** — a total reconciles while a small definitional shift hides inside it |
| **T3** | Human-confirmed against business meaning | **Meaning** | **Coverage** — humans check samples, not populations |

**Reconciliation freshness** follows directly and is cheap to implement: if period N was
T2-anchored and N+1…N+6 were T0, the trailing baseline is self-generated regardless of its
length. Each contract carries `periods_since_independent_anchor`, and exceeding a declared
maximum is an escalation trigger *even when nothing has drifted*. This is the only mechanism
identified in the study that breaks the self-certification loop without external supervision on
every period.

---

## 8. Q8 — What is the minimum human gate?

Genuinely requires human semantic input:

1. **Two or more plausible interpretations survive the evidence.**
2. **A genuinely new business concept** appears.
3. **A consequential reinterpretation would alter previously accepted historical results.**
4. **Required meaning is external to the supplied data** — e.g. whether freight belongs in
   the measure, whether internal transfers count as sales.
5. **(Added from §6)** **Statistical discontinuity with no structural explanation.** This must
   be a trigger, because it is the *only* automatic semantic-drift alarm. It will produce
   false positives; that is the price of catching the class at all.

Explicitly should **not** reach a human: header location, column renames with corroborating
type and value evidence, wide/long form, dedupe keys, join discovery, type coercion — all
decidable from data or from memory.

**On the proposed metric.** "Human semantic questions per 1,000 incoming datasets" is a
reasonable headline but is dominated by the file-to-family ratio rather than by system
quality: a system serving 2,000 files from 40 families looks ten times better than the same
system serving 2,000 files from 400 families. Report it alongside two companions:

- questions **per new source family** (onboarding cost);
- questions **per drift event** (maintenance cost);
- and a safety counterpart: **false-apply rate** — files processed successfully under a model
  that should not have applied. This is the metric that actually matters, because it is the
  one whose failures are invisible.

A cautionary data point from §5.8: Flatfile reports predicting >90% of matching actions
correctly. That residual ~10% is entirely tolerable because a human confirms in a UI, and
would be catastrophic unattended. Automation quality and gate design are not separable.

---

## 9. Q9 — Does the learned artifact require the agent?

| Agent-dependent | Agent-independent |
| --- | --- |
| AWM (workflows are prompt context) | bdi-kit mapping spec (`materialize_mapping`) |
| SpreadsheetLLM (per-call encoding, nothing persisted) | AutoDCWorkflow (OpenRefine JSON) |
| Agentic Schema Refinement's *cross-session memory* (conversation history) — though its *views* are independent | DeepPrep operator pipeline |
| | Executable Schema Contracts (deterministic extractors, hash-index FK linking, exact-key dedup; LLM only for optional extension) |
| | Agentic Schema Refinement's materialized SQL views |
| | Flatfile learned mappings |
| | `Data-tool.Template` |

The preferred position — agent-independent whenever the work has stabilized — is the majority
position in the data-preparation literature and is well supported. The dissent (AWM) is
domain-specific to non-stationary web environments.

One caveat worth stating precisely, from Executable Schema Contracts: agent-independence is
not binary. That system marks specific fields as `hybrid`, and LLM extraction fires *only* for
those. A production design should adopt the same idea — per-field escalation flags — rather
than an all-or-nothing plane boundary.

---

## 10. Q10 — What scales from 10 companies to 2,000?

Established and reusable:

- **Corpus-based schema matching** (2005): a corpus of prior schemas improves matching on new
  ones. Pre-LLM, well studied.
- **Meta-mappings** (Atzeni et al., VLDB 2019): generalize concrete mappings into
  meta-mappings over meta-schemas, capturing enterprise knowledge from previously defined
  mappings and suggesting mappings for new scenarios. This is the closest formal prior art to
  "adapter inheritance."
- **Flatfile**: corpus of ~5B mapping decisions plus per-customer remembered mappings; the
  recurring-partner case ("same partners, same data, slightly different every week") is
  explicitly the design target.

The scaling architecture the evidence supports:

```
incoming file
   → L0 fingerprint
   → retrieve candidate adapters from index (family, then provider delta)
   → replay-verify candidate against the file + historical invariants
        ├── passes → publish provider-variant adapter, run deterministically
        └── fails  → escalate to modelling with the failing predicate as the brief
```

Two things keep memory sublinear in provider count:

- **Adapter inheritance** — one family adapter (e.g. "SAP sales export, wide monthly") plus a
  small per-provider delta, rather than 2,000 independent adapters.
- **Fingerprint indexing** — retrieval must be structural, not conversational. Nobody needs
  2,000 chat histories.

**The dominant risk at scale is not a miss, it is a false match**: a wrong adapter that runs
successfully and produces plausible wrong numbers. Structural similarity alone will produce
these, because adjacent providers in the same family look nearly identical. The mitigation is
that publication must depend on L3 grain invariants and L4 statistical bands, not on L1
structural match. This risk grows with scale exactly as reuse benefit does.

---

## 11. Gap analysis

### A. What already exists (do not claim as novel)

- Agent-independent, re-executable artifacts produced by LLM reasoning — bdi-kit,
  AutoDCWorkflow, DeepPrep, Executable Schema Contracts.
- Execution-grounded feedback with backtracking and prefix reuse — DeepPrep.
- Deterministic structural inference: identity keys from uniqueness ratios, foreign keys from
  value overlap, cardinality from distribution asymmetry — Executable Schema Contracts.
- Constraining LLM schema output to attested fields, with a validity ratio that rejects
  hallucinated field references — Executable Schema Contracts.
- Spreadsheet table/region detection and structural sketching before feeding the model —
  SpreadsheetLLM (structural anchors, inverted-index translation, format-aware aggregation),
  TableSense.
- Mapping reuse across sources — corpus-based matching, meta-mappings, Flatfile.
- Analyst / Critic / Verifier role decomposition with in-engine verification — Agentic Schema
  Refinement.
- Immutable, content-hashed, provenance-carrying artifacts — our own Data-agents contract;
  Harmonia's provenance DB.

### B. What `Data-tool` already provides

Detailed inventory in [repo_reuse_map.md](repo_reuse_map.md). Summary of genuinely reusable
machinery: `Template`/`HeaderCell` persistence with round-trip tests; merged-header
normalization; header-row heuristic; synonym-based auto-mapping **with learned synonym
persistence** to `config.user.yaml`; schema-candidate ranking including numeric-block
detection and multilingual (fi/sv/de/en) month-token normalization; unpivot; cleanup rules;
dedupe and aggregation; typed coercion with per-column failure counts; three-level pandera
validation; `warn_on_schema_diff`; quarantine with error log and a real validation report;
`DataEngine` headless API; Template Library batch runner.

### C. What `Data-agents` already provides

Role boundaries with explicit `schema_layer: core|adapter` declaration; artifact contract
(`run_id`, content-hashed `artifact_key`, immutability, "agents exchange keys, not payloads");
numeric stop conditions (header confidence < 0.70; unmappable `product_code`/`quantity`;
missing `product_code` > 5%); JSONL shadow/audit log; a **resume guard** that re-hashes the
input file and refuses to continue if it changed; `human_confirmation.json` as an explicit
human-gate object; `table_region.json` and `header_override.json` as human override objects;
and a working deterministic runtime with no LLM in it.

**Critical caveat:** every Data-agents artifact is *run-scoped*. Nothing is retrieved across
runs; `adapter_schema_spec.json` has to be placed into the run directory by hand. Data-agents
has the publication *shape* and no memory.

### D. What is actually missing

Distinguishing "not implemented here" from "not solved anywhere":

| Gap | Status |
| --- | --- |
| Applicability predicates as a first-class artifact bound to a published model | Partly served (expected_headers, warn_on_schema_diff, sufficiency gating). **Engineering gap** at L0–L2; **unserved** at L3–L4 |
| Grain declared and verified as an invariant | **Unserved anywhere surveyed.** Highest-consequence gap |
| Semantic drift detection under structural stability | **Unserved**, and the drift literature concurs it is the least-addressed class |
| Escalation object + feedback contract for a *recurring* source (replay against previously accepted output) | **Unserved** — no surveyed system has a recurring source |
| Negative/failure memory (rejected models and why) | **Unserved** |
| Source-family discovery over workbook structure + adapter inheritance | Partly served by meta-mappings (relational only); **unserved for workbooks** |
| Cost-bounded escalation policy | **Unserved** |
| Candidate-data discovery in a full bookkeeping export | **Unserved** |

### E. The narrowest first experiment

**One experiment. No agents in it.** Full protocol in
[experiment_001_drift_discrimination.md](experiment_001_drift_discrimination.md).

*Drift Discrimination Harness.* Extend `Template` with declared `applicability` (L0–L4) and
`invariants` blocks. Generate a controlled drift corpus from one real provider layout spanning
cosmetic, structural and semantic variants — including the decisive case: `Revenue`
redefined to include freight, with the workbook structurally identical. Then, deterministically,
for every variant: does the model claim to apply, which predicate fails first, and does the
failing predicate identify the true drift class?

Primary measurement is the **false-apply rate on semantically drifted input**. The expected
result is that it is 100% without L4 statistical baselines — and demonstrating that cleanly is
the point, because it converts an architectural argument into a measurement.

Why this and nothing else first: it tests H1 and H4 directly, needs no LLM, needs no new
architecture, costs days rather than weeks, and its *negative* result is as informative as its
positive one. If declared applicability cannot discriminate drift classes, no amount of agent
sophistication helps, because the work plane cannot tell when to call for help.

---

## 12. Falsification summary

Full ledger with evidence in [falsification_ledger.md](falsification_ledger.md).

| # | Hypothesis | Verdict |
| --- | --- | --- |
| H1 | `Data-tool.Template` is rich enough to serve as persistent task memory | **Falsified as-is** (adequate as a transformation recipe; fails as task memory) |
| H2 | An executable schema/procedure can replace the agent for repeated work | **Supported — and not novel** |
| H3 | Previous schemas provide useful memory for new source variations | **Supported — established pre-LLM** |
| H4 | Most source changes can be resolved without human semantic input | **Not established; partly contradicted.** Top data need |
| H5 | The modelling network can be isolated from production without losing capability | **Supported, with a caveat**: isolate *writes*, not *reads* |
| H6 | The hard problem is task modelling rather than one-off transformation | **Supported but requires restatement** — the hard problem is verification + applicability |

The most important contrary finding: H6 as written is slightly wrong in a way that matters.
One-off transformation generation is *not* solved either (≈0.71–0.79 F1 in published systems).
Framing the work as "modelling instead of transformation" would let an 80%-correct generator
through the publication boundary unexamined. The correct frame is that modelling is what
supplies the *verification* that an 80%-correct generator requires.

---

## 13. Decision

### **AMEND, then BUILD (narrow).**

**AMEND** — the representation must change before any modelling network is built.
`Template` is a reader configuration, not a task model. Specifically it must gain declared
applicability, declared grain/invariants, a separated canonical layer, instance-level
versioning, and provenance. Two concrete defects make this non-optional rather than
aesthetic:

1. `filter_and_rename` renames by **positional index** when `headers` are present, and
   `read_excel_with_template` passes integer column positions to pandas `usecols`. A single
   inserted column silently shifts every mapping and the run still *succeeds*. This is a
   false-apply generator sitting in the current work plane.
2. `provider_id` falls back to the **source filename** when `provider_name` is unset. That is
   an undeclared semantic assumption written into output data.

**BUILD** — only Experiment 1, the Drift Discrimination Harness. No agents, no new
architecture, no production integration.

**Do NOT build yet** — the agentic modelling network, the retrieval index, the escalation
protocol, or any cross-repo merge. Those depend on answers Experiment 1 produces.

### Revised sequence ([amendment A6](workorder_amendment_001.md))

```text
1. Amend research WO                                    <- done
   |
2. Define applicability levels (L0-L5) + evidence tiers
   |
3. Build deterministic drift corpus
   |
4. Measure false-apply / false-escalate
   |
5. Determine what applicability evidence is actually useful
   |
6. THEN give agents the job of producing
   procedures + applicability claims + backing evidence
```

Step 6 is last for a precise reason: **before step 5, "build a schema" is an underspecified
instruction.** After step 5, the agent's output contract is known — a procedure, an
applicability contract, and the evidence backing each clause of that contract at a stated
evidence tier. That is specifiable. "Build a schema" is not.

**Explicitly rejected options and why:**
- *Use an existing framework* — bdi-kit is the closest fit and is biomedical-schema oriented;
  its `materialize_mapping` replay model is worth copying, the library is not worth adopting.
- *Replace Template outright* — unnecessary. Its transformation core is sound and tested;
  the deficiency is everything *around* the transformation.
- *Reuse `data-frame-tool`* — it is a strict subset of `Data-tool` with committed merge
  conflict markers in seven files and zero unique definitions. Archaeology found nothing lost.
- *Do not build* — not warranted; the gap analysis identifies unserved problems and a cheap
  experiment that discriminates between them.

---

## 14. Success condition check

The workorder's success condition asks for six statements with evidence. Current status:

| Required statement | Answered? |
| --- | --- |
| What agents must discover | **Yes** — §3 stages, with 2 and 5 identified as unserved |
| What artifact they should leave behind | **Yes** — §1.3, five linked objects |
| How that artifact is tested | **Yes** — §7, replay against previously accepted periods + declared invariants |
| When it is reused | **Partially** — §5 gives the representation; the *thresholds* are unmeasured (Experiment 1) |
| What causes escalation | **Yes** — §6 drift classes, §8 gate triggers |
| What genuinely still requires a human | **Yes** — §2 item 2 and scope rules; §8 triggers 1–5 |

Five of six are answered from evidence. The sixth requires a measurement, not more reading —
which is precisely what Experiment 1 supplies. A build workorder for the modelling plane
should not be activated until it reports.

---

## Sources

- [Agent Workflow Memory (arXiv:2409.07429)](https://arxiv.org/abs/2409.07429) · [code](https://github.com/zorazrw/agent-workflow-memory) · [ICML 2025 poster](https://icml.cc/virtual/2025/poster/45496)
- [Towards Agentic Schema Refinement (arXiv:2412.07786)](https://arxiv.org/html/2412.07786v1)
- [Interactive Data Harmonization with LLM Agents — Harmonia (arXiv:2502.07132)](https://arxiv.org/html/2502.07132v2) · [harmonia](https://github.com/VIDA-NYU/harmonia/) · [bdi-kit](https://github.com/VIDA-NYU/bdi-kit)
- [AutoDCWorkflow (arXiv:2412.06724)](https://arxiv.org/html/2412.06724v1)
- [DeepPrep (arXiv:2602.07371)](https://arxiv.org/abs/2602.07371)
- [Executable Schema Contracts (arXiv:2606.05415)](https://arxiv.org/html/2606.05415v1)
- [SpreadsheetLLM (arXiv:2407.09025)](https://arxiv.org/abs/2407.09025) · [Microsoft Research](https://www.microsoft.com/en-us/research/publication/encoding-spreadsheets-for-large-language-models/) · [review](https://www.themoonlight.io/en/review/spreadsheetllm-encoding-spreadsheets-for-large-language-models)
- [TableSense](https://www.semanticscholar.org/paper/TableSense:-Spreadsheet-Table-Detection-with-Neural-Dong-Liu/1b01dea77e9cbf049b4ee8b68dc4d43529d06299) · [Semantic Table Structure Identification in Spreadsheets](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/08/Semantic-Table-Structure-Identification-in-Spreadsheets.pdf)
- [Flatfile — mapping](https://flatfile.com/product/mapping/) · [data onboarding platform](https://flatfile.com/platform/data-onboarding/)
- [Meta-Mappings for Schema Mapping Reuse (PVLDB 12(5))](http://www.vldb.org/pvldb/vol12/p557-atzeni.pdf) · [Corpus-Based Schema Matching (ICDE 2005)](https://dl.acm.org/doi/10.1109/ICDE.2005.39)
- [Drift Detection: Schema, Logic and Metric Changes](https://medium.com/@manik.ruet08/drift-detection-monitoring-schema-logic-and-metric-changes-in-real-time-a2398428ccc1) · [Context Drift Detection](https://atlan.com/know/context-drift-detection/) · [Understanding Schema Drift](https://www.acceldata.io/blog/schema-drift)
