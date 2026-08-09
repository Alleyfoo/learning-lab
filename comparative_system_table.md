# Comparative System Table

One row per external system, plus one row for our current `Data-tool`.

The workorder specifies 19 columns. A 19-column Markdown table is unreadable, so the **same
table is split into four panels sharing the `System` key column**. No content is dropped.

`unknown/not established` is used wherever the source material did not establish the fact.
It is never inferred.

Systems: **AWM** = Agent Workflow Memory · **ASR** = Towards Agentic Schema Refinement ·
**Harmonia** = Harmonia / bdi-kit · **ADCW** = AutoDCWorkflow · **DeepPrep** ·
**ESC** = Executable Schema Contracts · **SLLM** = SpreadsheetLLM / SheetCompressor ·
**Flatfile** · **Meta-map** = Meta-Mappings for Schema Mapping Reuse (added: closest prior art
to adapter inheritance) · **Data-tool** = `Alleyfoo/Data-tool` @ `ab10b8c`.

---

## Panel 1 — Input and what the system is told

| System | Initial input | Business intent supplied? | Source discovery? | Structural modelling? | Semantic modelling? |
| --- | --- | --- | --- | --- | --- |
| **AWM** | Web task query + environment observations | Yes — task query in natural language | No — environment is given | No (web DOM actions, not tables) | No |
| **ASR** | Existing relational schema (61 tables) + analytics tasks | Yes — analytics tasks drive view formulation | No — database given | Yes, but of an *already relational* schema | Yes — semantic layer of coherent views |
| **Harmonia** | Source table + target/canonical vocabulary (e.g. GDC) | Yes — as a **target schema**, plus chat commands | No — table given | Minimal — assumes a clean tabular source | Yes — schema and value matching |
| **ADCW** | Raw dirty table + column schema + first 15 cells/column | Yes — **NL purpose question** (67 hand-written) | **No — paper states the relevant table is provided** | Column-level quality only | Partial — target-column selection from purpose |
| **DeepPrep** | Multiple raw source tables + NL specification | Yes — NL specification | No — sources given | Yes — via operators over materialized states | Partial — implicit in operator choice |
| **ESC** | Raw multi-source documents/records | **No** at ingestion; intent arrives at query time | Partial — profiles all sources into a field catalog | Yes — identity keys, FKs, cardinality, source hierarchy | Yes — LLM entity/relationship discovery, field-constrained |
| **SLLM** | Raw spreadsheet grid (cells, values, formats) | No | **Yes — table region detection is the task** | Yes — anchors, table boundaries | Only downstream via Chain of Spreadsheet QA |
| **Flatfile** | Customer-uploaded file + host application's target schema | Yes — as a target schema | Partial — file/sheet selection is user-driven | Yes — header/column handling for inconsistent files | Yes — ML field matching |
| **Meta-map** | Prior concrete schema mappings + a new source schema | Yes — implicitly via the target schema | No | Yes — generalized to meta-schemas | unknown/not established |
| **Data-tool** | Excel/CSV/SQL source + a `.df-template.json` | **Partially** — only as `column_mappings` targets + `required_fields`; no measure definition, grain or period semantics | No — path/sheet must be specified in the template | Yes — header row, skiprows, merged headers, multi-sheet, numeric blocks | Weak — synonym dictionary only (`config.yaml`) |

---

## Panel 2 — What survives, and what remembers

| System | Persistent artifact | Persistent memory | Deterministic primitives | Reuse mechanism |
| --- | --- | --- | --- | --- |
| **AWM** | Workflow = NL description + trajectory of (state, reasoning, action) with contexts abstracted to `{variables}` | Workflow library (offline-induced or online-induced) | Actions are programmatic (`click()`, `type()`) but the workflow itself is prose+trace | Retrieved and **injected into the LLM prompt** |
| **ASR** | Materialized SQL views (1,146 from 61 tables) | **Conversation history across sessions** + the views themselves | SQL / `CREATE VIEW` | Views referenced by later queries; redundancy avoidance via retained transcripts |
| **Harmonia** | **Declarative JSON mapping specification** (source ↔ target pairs) | Provenance DB (detail limited in paper) | `match_schema`, `top_matches`, `match_values`, `materialize_mapping` | Feed plan + source data to `materialize_mapping` to recreate output without re-running the LLM |
| **ADCW** | OpenRefine operation list, stored in OpenRefine JSON | None across tasks | 6 OpenRefine ops: `upper`, `trim`, `numeric`, `date`, `mass_edit`, `regexr_transform` | Re-apply stored JSON workflow |
| **DeepPrep** | Ordered operator pipeline `P = (S, o₁→…→o_k)` | **None — paper states no cross-task memory** | Operator library over materialized tables | Re-execute the pipeline; within a task, valid operator prefixes are reused after backtracking |
| **ESC** | **Versioned YAML schema** `Σ = (ℱ field catalog, 𝒯 entity types, ℛ relationships, ℐ structural intelligence)` | Σ persisted to disk; monotonic augmentation `Σ′ ⊇ Σ` | Deterministic extractors; O(n) key hashing; value-overlap FK detection; hash-index cross-source linking; exact-key dedup | Σ conditions both ingestion (extraction, dedup, linking) and query-time routing |
| **SLLM** | **None** — encoding is per-call | None | Anchor extraction, inverted-index translation, format-aware aggregation (all deterministic pre-processing) | None across workbooks |
| **Flatfile** | Learned mappings per customer/import | **Corpus of ~5B mapping decisions** + colleagues' past selections | Rule/validation layer (not enumerated publicly) | Model + remembered selections predict >90% of matching actions on repeat imports |
| **Meta-map** | Meta-mapping over meta-schemas | Corpus of previously defined schema mappings ("enterprise knowledge") | Relational mapping formalism | Generalize a concrete mapping → instantiate it on a new source schema |
| **Data-tool** | `Template` (v3) as `<stem>.df-template.json`; `HeaderCell` list | **Learned synonyms** appended to `src/config.user.yaml` via `learn_synonyms_from_mapping`; template files on disk; Template Library page | `read_excel_with_template`, `normalize_excel_headers`, `filter_and_rename`, unpivot/melt, trim/strip/dropna, `dedupe_on`, `combine_on` groupby-sum, `_coerce_field_types`, pandera `OutputSchema` | Point a template at another file; batch-run a directory from the Template Library |

---

## Panel 3 — Feedback, verification, applicability

| System | Execution feedback | Verification method | Applicability representation |
| --- | --- | --- | --- |
| **AWM** | Online mode: an LM-based evaluator judges whether a trajectory solved the query before induction. Offline: none | LM-evaluator only (online); training examples assumed successful (offline) | **None.** Documented failure: workflow executes into unexpected intermediate states (pop-ups) and cannot adapt |
| **ASR** | Verifier agent executes `CREATE VIEW` in the engine; "View successfully defined" | In-engine materialization = syntactic + semantic validity | **None** — a view either compiles against the schema or does not |
| **Harmonia** | Interactive: user in the loop; LLM generates custom code when primitives are insufficient | Human review; reproducibility via plan replay | **None** — plan does not state which future source it fits |
| **ADCW** | Column-level Data Quality Report drives next operation choice | Ops: P/R/F1 vs. silver annotations. Output: purpose-answer correctness + cell-level `Average_Match_Ratio` vs. curated table | **None** — scoped to one (purpose, table) pair |
| **DeepPrep** | **Richest surveyed**: materialized intermediate tables, execution errors propagated, runtime exceptions (column mismatch, type error), sample outputs. Tree search with backtracking + prefix reuse; ≤5 turns | Ground-truth target tables used **for evaluation only**, never shown to the agent | **None** — no cross-task applicability |
| **ESC** | Field-validity ratio rejects hallucinated field references; two-stage deterministic confidence gating pre/post retrieval | Schema planning recall, schema execution fidelity, KG structural integrity, type utilization (50–89%), controlled ablations, 3 model families | **Closest surveyed**: *sufficiency gating* — does Σ resolve the query's entity types. Query-side, not source-side. Suppresses extension entirely on stable datasets |
| **SLLM** | None (single-shot encoding + prediction) | F1 on table detection: 78.9 fine-tuned; +25.6% over vanilla in GPT-4 ICL; ~25× compression | n/a |
| **Flatfile** | Human confirms/corrects mappings in-UI; corrections feed the model | Human-in-the-loop review and approval before import | Per-customer remembered mapping keyed to the host schema; details not public |
| **Meta-map** | unknown/not established | unknown/not established | Generalization to meta-schemas is the applicability mechanism; the matching procedure detail is unknown/not established from sources consulted |
| **Data-tool** | `ProcessResult.metrics`: unpivot before/after shape, `dedupe_dropped`, `date_parse_failures`, `numeric_parse_failures`; `.validation.txt` report; quarantine `.error.log` | pandera `OutputSchema` (3 levels: `off` / `coerce` / `contract`) — **but all 4 fields are `required=False`, `strict=False`**, so a well-formed wrong table passes; `required_fields` + `field_types` enforced only at `contract` level | **Rudimentary and undeclared**: `warn_on_schema_diff` computes missing/extra vs. template header names at runtime; `fail_on_missing` / `fail_on_extra` can hard-fail. No grain, typing, statistical or semantic predicate |

---

## Panel 4 — Versioning, drift, humans, and fit to the proposed architecture

| System | Schema/workflow versioning | Drift handling | Human gate | Requires agent during future execution? | Closest correspondence to our architecture | Important difference |
| --- | --- | --- | --- | --- | --- | --- |
| **AWM** | unknown/not established | None; brittle to environment change | None automatic | **Yes** — workflows are prompt context | Modelling plane's *procedural induction* step | Procedure never leaves the LLM; no publication boundary |
| **ASR** | unknown/not established | None | None automatic | No for views; **yes** for memory (conversation) | Control plane's *Verifier*; Analyst/Critic/Verifier role split | Operates on an already-clean relational schema; skips the entire source-interpretation problem |
| **Harmonia** | unknown/not established | None | Interactive by design — chat-driven throughout | No — plan replays deterministically | Work plane's *replay* semantics (`materialize_mapping`) | Human is in the loop continuously, not at a minimal gate; no applicability |
| **ADCW** | Workflows stored in OpenRefine JSON; instance versioning unknown/not established | None | None | No | Modelling plane's *primitive-sequence* output; the separate workflow-vs-output metrics are directly adoptable | Assumes the relevant table is already identified; 6-operation vocabulary |
| **DeepPrep** | unknown/not established | None | None | No | Modelling plane's *discover → test → revise* loop; the feedback contract | Single-task; no memory, no applicability, no publication |
| **ESC** | **Yes** — versioned YAML; monotonic augmentation invariants (`𝒯′⊇𝒯`, `ℛ′⊇ℛ`, `𝒜′(t)⊇𝒜(t)`) so prior queries stay answerable | Handled as *schema extension*, not as source drift; extension fires 85.3% on per-query KBs, ~0% on stable datasets | None | **Mostly no** — LLM only for optional extension and answer synthesis; per-field `hybrid` flags escalate selectively | **Closest overall** to the published-executable-model concept | Extension is query-driven, not source-driven; no notion of a source that changed under a fixed intent |
| **SLLM** | n/a | n/a | None | **Yes** — every workbook re-encoded and re-inferred | Modelling plane's *structural sketch* step, done well | Persists nothing; a pure perception component |
| **Flatfile** | unknown/not established | Handled by re-prompting the human in-UI | **Human confirms mappings on every import** | No | Work plane + memory at real operational scale; the "partners won't fix their files" premise | ~10% residual mapping error is safe only *because* a human confirms; unattended operation is out of scope |
| **Meta-map** | unknown/not established | unknown/not established | unknown/not established | No | Memory plane's *adapter inheritance* / source-family reuse | Relational schemas, not workbooks; pre-dates messy-Excel and semantic-drift concerns |
| **Data-tool** | `template_version: 3` is a **format** version, not an instance version. No model version, author, approval, effective date or provenance | `warn_on_schema_diff` detects header-name drift only; quarantine + `.error.log` on failure; no drift classification | None formalized (the Streamlit UI is the de facto gate) | **No** — fully deterministic, no LLM anywhere in the repo | The **work plane**, largely already built | No applicability, no grain invariant, no canonical/adapter separation, no provenance; **maps columns by position when `headers` is populated**, so an inserted column silently shifts every mapping and still succeeds |

---

## Notes on unknowns

Fields marked `unknown/not established` were not determinable from the sources consulted
(abstracts, HTML full texts, repository READMEs). Two PDFs (Meta-Mappings PVLDB, SheetEncoder
EMNLP camera-ready) could not be text-extracted; the Meta-Mappings row is therefore
deliberately sparse and should be completed before any design decision depends on it.

The `Data-tool` row is derived from direct source inspection at commit `ab10b8c`, not from
documentation. Line-level references are in [repo_reuse_map.md](repo_reuse_map.md).
