# Repo Reuse Map

Direct source inspection, read-only. No repository was modified.

| Repo | Commit inspected | Date | Files (excl. `__pycache__`) |
| --- | --- | --- | --- |
| `Alleyfoo/Data-tool` | `ab10b8c` | 2025-12-25 | 99 tracked |
| `Alleyfoo/Data-agents` | `22ec1dd` | 2025-12-19 | 59 tracked |
| `Alleyfoo/Pipe-transformation` | `3f7c941` | 2025-10-11 | 10 tracked |
| `Alleyfoo/data-frame-tool` | `60c5127` | 2026-01-03 | 78 tracked |

**Repository-wide finding: there is no LLM code in any of the four repositories.**
A search for `openai|anthropic|ollama|llm|gpt-|copilot` across all tracked files returns hits
only in `Data-agents` Markdown (Copilot/Codex orientation text). `Data-agents`' "agents" are
role *specifications*; `runtime/excel_flow.py` is deterministic Python. The modelling plane is
genuinely greenfield.

---

## 1. `Data-tool` — the work-plane candidate

### 1.1 Reusable machinery (concrete)

| Capability | Location | Assessment |
| --- | --- | --- |
| `Template` dataclass v3 (30 fields) + JSON/YAML persistence | `src/templates.py:99-296`, `load_template`/`save_template` `:365-384` | **Reuse.** Round-trip tested (`tests/test_templates_roundtrip.py`) |
| `HeaderCell` with `is_metadata` / `metadata_type` | `src/templates.py:63-95` | **Reuse.** Newer than `data-frame-tool`; the beginning of a metadata-vs-data distinction |
| Merged-header normalization (expands merged ranges, generates placeholders) | `src/templates.py:406-465` | **Reuse.** Real Excel-messiness handling that most surveyed systems lack |
| Header-row heuristic (string-ratio > 0.8 and width-ratio > 0.5) | `src/services/header_detection.py:16-26` | Reuse as a *candidate generator*, not as a decision |
| Header cache keyed on path+mtime+sheet+offsets | `src/services/header_detection.py:29-69` | **Reuse** |
| Multi-sheet read + combine with `source_sheet` provenance column | `src/templates.py:532-583` | **Reuse** |
| Synonym-based auto-mapping (substring + `difflib` cutoff 0.82) | `src/core.py:253-282` | Reuse as a *proposal* mechanism. Note: greedy, first-match-wins, one target per file |
| **Learned synonym persistence** → `config.user.yaml` | `src/core.py:190-235` | **Reuse — this is the only real cross-run memory in any repo.** Currently unversioned and global |
| Base synonym dictionary (8 canonical fields, fi/en terms) | `src/config.yaml:17-103` | Reuse as seed data |
| Schema-candidate ranking: numeric-block detection, year-like exclusion, texty-column detection | `src/services/schema_candidates.py:10-236` | **Reuse.** `find_numeric_blocks` + left-adjacent key-column heuristic is directly the wide-monthly-sheet case |
| Multilingual month-token normalization (fi/sv/de/en → `YYYY-mmm`) | `src/services/schema_candidates.py:71-117` | **Reuse.** Genuinely useful, hard-won, and absent from every external system surveyed |
| Unpivot / melt with `id_columns`, `var_name`, `value_name` | `src/api/v1/engine.py:144-158` | Reuse. See defect D3 |
| Cleanup: trim, drop-empty-rows, null-column threshold, strip thousands | `src/api/v1/engine.py:165-184` | Reuse |
| `dedupe_on` with dropped-row count; `combine_on` groupby-sum | `src/api/v1/engine.py:199-231` | Reuse. See defect D4 |
| Typed coercion with per-column failure counts | `src/api/v1/engine.py:18-52` | **Reuse.** Failure counts are exactly the execution feedback the modelling plane needs |
| pandera `OutputSchema` + 3 validation levels | `src/schema.py:12-22`, `src/api/v1/engine.py:55-80` | Reuse the *shape*; see defect D2 |
| `warn_on_schema_diff` → (missing, extra) vs. template | `src/api/v1/engine.py:94-110` | **Reuse — this is a proto-applicability check.** Promote from runtime warning to declared predicate |
| `fail_on_missing` / `fail_on_extra` hard-fail | `src/pipeline.py:143-153` | **Reuse.** The escalation trigger already exists |
| Quarantine: copy source + `.error.log` + validation report | `src/pipeline.py:61-84`, `:120-184` | **Reuse.** This is the escalation object in embryo |
| `_build_validation_report` (rows/cols before→after, unpivot shape, dedupe dropped, parse failures, missing/extra) | `src/pipeline.py:87-117` | **Reuse.** Already close to the feedback contract in §7 of the report |
| `DataEngine` headless API | `src/api/v1/engine.py:113-309` | **Reuse.** UI-free entry point for a work plane |
| SQL sources + connectors | `src/connectors.py`, `Template.sql_table`/`sql_query` | Reuse if needed |
| Template Library batch runner | `streamlit/pages/06_Template_Library.py` | Reuse concept |

### 1.2 Defects found (evidence for H1)

| # | Defect | Location | Consequence |
| --- | --- | --- | --- |
| **D1** | `filter_and_rename` maps by **positional index** when `template.headers` is populated; `read_excel_with_template` passes integer positions as pandas `usecols` | `src/templates.py:484-500`, `:555-566` | One inserted column silently shifts every mapping. The run **succeeds**. This is a false-apply generator |
| **D2** | `OutputSchema` declares 4 columns, all `required=False`, with `strict=False` | `src/schema.py:12-22` | At `coerce` level a structurally wrong but well-formed table passes validation. Only `contract` level enforces `required_fields`/`field_types` |
| **D3** | Unpivot uses `id_vars = list(template.column_mappings.values())` rather than `template.id_columns` | `src/api/v1/engine.py:145` | `id_columns` — the field the template author sets — is not used by the melt path |
| **D4** | `combine_on` sums *all* numeric columns not in the group key | `src/api/v1/engine.py:210-216` | Aggregating unit prices or year columns is possible and silent |
| **D5** | `provider_id` falls back to `template.source_file` when `provider_name` is unset | `src/api/v1/engine.py:160-163` | Filename becomes business identity. An undeclared semantic assumption written into output |
| **D6** | `template_version: 3` is a **format** version; no model instance version, author, approval, evidence or effective date | `src/templates.py:131` | The artifact cannot participate in a publication boundary as-is |
| **D7** | `report_date` / `sales_amount` are hardcoded canonical names in transform | `src/api/v1/engine.py:186-197` | The canonical model is embedded in the engine rather than declared in an artifact |
| **D8** | `src/processor.py`, `src/prototype.py`, `src/ui.py` **fail to compile** (`python -m py_compile`) | — | Dead code carrying duplicated, divergent template logic. `processor.py` self-describes as legacy |

### 1.3 Verdict on H1

`Template` is a competent **reader/transformer configuration**. It is not task memory:
no applicability, no grain, no canonical/adapter separation, no instance versioning, no
provenance, no evidence. **AMEND rather than replace** — the transformation core is sound and
tested; everything around it is missing.

---

## 2. `Data-agents` — the modelling/publication-plane donor

### 2.1 Reusable scaffolding (concrete)

| Capability | Location | Assessment |
| --- | --- | --- |
| **Core vs. adapter schema layer** — outputs must declare `schema_layer: "core" \| "adapter"` | `agent-base/docs/agent-roles.md` (Schema Agent) | **The single most reusable idea in any repo.** Adopt verbatim as objects A and B |
| Artifact contract: `run_id`, `artifact_key` = `artifacts/{run_id}/{name}@{content_hash}`, immutability, required metadata (`created_at`, `producer_role`) | `agent-base/contracts/artifacts.md` | **Reuse.** Immutability + content hashing is what makes provenance real |
| "Agents exchange **keys, not payloads**" | same | **Reuse.** Keeps the modelling plane auditable and cheap |
| Role boundaries with hard non-goals (Header: no schema logic; Schema: never delete columns; Transform: no file writes; Validation: detect only; Save: allowlist roots) | `agent-base/docs/agent-roles.md` | **Reuse.** These are the write-isolation boundaries H5 needs |
| Numeric stop conditions: header confidence < 0.70 → human; `product_code`/`quantity` unmappable → more evidence; missing `product_code` > 5% → stop | `agent-base/docs/excel-schema-flow.md` | **Reuse.** Already the right *shape* for a human gate; thresholds are unvalidated guesses |
| Shadow log (JSONL, append-only, never alters plans) | `agent-base/docs/philosophy.md`, `runtime/excel_flow.py:_append_shadow` | **Reuse** as object E (provenance) |
| **Resume guard** — re-hashes the input file on continue and refuses if it changed | `runtime/excel_flow.py:puhemies_continue` | **Reuse.** A working applicability check, at file-hash granularity |
| `human_confirmation.json` as an explicit gate artifact | `runtime/excel_flow.py:write_human_confirmation` | **Reuse.** The human gate as a *typed object*, not a chat turn |
| `header_override.json`, `table_region.json` (start/end row, include/exclude columns) | `runtime/excel_flow.py:_apply_table_region`, `_apply_header_override` | **Reuse.** Region selection is the missing stage-2 primitive |
| Header candidate generation with confidence + `_header_looks_like_data` penalty | `runtime/excel_flow.py:_build_header_candidates` | Overlaps `Data-tool`; keep the *confidence + alternatives* structure, drop the duplicate heuristic |
| Plan → Delegate → Review → Merge; Diverge → Converge | `agent-base/docs/orchestration-patterns.md` | Reuse as process, not as code |
| Refusal channel — every artifact carries `refusal_reason` and `alternatives` | `runtime/excel_flow.py` schema/header specs | **Reuse.** "I cannot establish this" is a first-class output |

### 2.2 The critical limitation

**Every artifact is run-scoped.** `artifacts/<run_id>/…` is written, never retrieved.
`adapter_schema_spec.json` is *read* from the run directory if present but is never *produced*
by a prior run, indexed, versioned or matched to a new file — an operator must place it there.

> `Data-agents` has the publication **shape** and no memory. `Data-tool` has a persistent
> artifact and no publication boundary. Neither has applicability. That is precisely the
> missing middle.

### 2.3 Missing pre-schema roles (workorder §4.2)

Confirmed absent from the role set (Orchestrator, Header, Schema, Transform, Validation, Save,
Shadow, Compassion):

- **Task/concept modelling** — nothing represents the business task; intent enters only as an optional canonical `schema_spec.json`.
- **Source discovery** — `_read_preview_rows` takes `excel.sheet_names[0]`. Sheet 1, unconditionally.
- **Semantic interpretation** — the Schema Agent maps names; nothing reasons about meaning.
- **Model comparison** — no role compares a candidate model with a prior published one.
- **Replay / verification** — the Validation Agent inspects *this run's* output only; no historical replay.
- **Memory retrieval** — no role, no index, no store.

Those six are the modelling-plane roles that would have to be created.

---

## 3. `Pipe-transformation` — downstream reference

Small (10 files, one 130-line toolkit + a playbook notebook). Treat as a **worked example**,
not an implementation base — consistent with the workorder's instruction.

| Concept | Location | Assessment |
| --- | --- | --- |
| **`expected_headers` per source** | `config/pipeline.example.yaml` | **Reuse — the only declared applicability predicate anywhere in the four repos.** Promote to L1 of the applicability model |
| `primary_key` per source | same | **Reuse.** Closest existing thing to a declared grain; currently unenforced |
| Per-source `rename_map` (source → canonical) | same | Confirms the adapter pattern; note three sources map to one canonical shape (`OrderID`, `CustomerID`, `Amount`, `UpdatedAt`) — a **source family** in the wild |
| `idempotent_upsert_key` | `src/pipeline/toolkit.py` | Reuse — reprocessing must be safe |
| `snowflake_merge_sql` MERGE-on-PK | same | Reuse pattern |
| fsspec URI reader (csv/json/ndjson/parquet), connector stubs (Azure Blob, S3, SFTP) | same | Reuse concept only |

**Answer to the workorder's question** — what a deliberately boring downstream system needs
once interpretation is solved: a stable canonical shape, a declared primary key, idempotent
upsert, and a per-source rename map. That is all. Note the YAML defines `sources:` three times
at the same nesting level — later keys overwrite earlier ones in any YAML load. It is
illustrative, not runnable.

---

## 4. `data-frame-tool` — archaeology

**Finding: nothing was lost. Do not build from it, and do not mine it further.**

Evidence:

1. **Zero unique definitions.** Comparing all top-level `def`/`class` names, the set unique to
   `data-frame-tool` is **empty**. Every symbol it defines also exists in `Data-tool`.
2. **File set is a strict subset.** 28 files exist in `Data-tool` and not in `data-frame-tool`
   (the whole `src/api/v1/` engine, `src/core/`, the Streamlit app, `tests/test_engine_api.py`);
   **zero** exist the other way round.
3. **Unresolved merge conflict markers are committed** in seven Python files:
   `src/app.py` (64 marker lines), `src/templates.py` (28), `src/pipeline.py` (26),
   `src/core.py` (16), `samples/generate_samples.py` (4), `src/processor.py` (2),
   `src/prototype.py` (2). The `main` branch does not import.
4. `Data-tool` is strictly ahead where they differ — e.g. `HeaderCell.is_metadata` /
   `metadata_type` exist only in `Data-tool`.

One historical note worth keeping: an older `TARGET_SCHEMA` visible inside the conflict blocks
in `data-frame-tool/src/core.py` used an **invoice-centric** canonical model
(`invoice_id`, `date`, `amount`, `provider_name`) rather than the current sales-centric one
(`article_sku`, `report_date`, `sales_amount`, `sales_qty`). That is not lost machinery, but it
is evidence that **the canonical model itself has already drifted once** — which is exactly the
Q6 semantic-drift problem occurring inside our own repository history, and a good argument for
making the canonical model a versioned, provenanced artifact (object A).

---

## 5. Consolidated reuse decision

| Plane | Source | What to take |
| --- | --- | --- |
| **Work plane** | `Data-tool` | `DataEngine`, `templates.py` read/normalize path, cleanup/unpivot/dedupe primitives, coercion with failure counts, quarantine + validation report. Fix D1 before any reuse |
| **Publication/control plane** | `Data-agents` | Artifact contract (immutability, content hashes, keys-not-payloads), refusal channel, `human_confirmation.json`, shadow log, stop-condition shape, core/adapter layer declaration |
| **Applicability** | `Pipe-transformation` | `expected_headers` + `primary_key` as declared predicates; extend to L0–L4 |
| **Memory** | `Data-tool` | `learn_synonyms_from_mapping` as the seed of a synonym store — needs versioning, provenance and per-family scoping |
| **Modelling plane** | *none* | Greenfield. No LLM code exists in any repo |
| **Archaeology** | `data-frame-tool` | Nothing. Close the question |
