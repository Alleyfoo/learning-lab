# Falsification Ledger

Each hypothesis is stated as given in the workorder, then tested against evidence. Contrary
evidence is recorded even where it weakens the proposed architecture. No hypothesis was
rewritten to fit results; where a hypothesis is *nearly* right but misframed (H6), the
misframing is recorded rather than repaired.

Verdict scale: **Falsified** · **Not established** · **Supported** · **Supported but not novel**

---

## H1 — `Data-tool.Template` is rich enough to serve as persistent task memory

### Verdict: **FALSIFIED (as-is).** Adequate as a transformation recipe; fails as task memory.

**Evidence against:**

1. **No applicability conditions are declared.** The only thing resembling one is
   `warn_on_schema_diff` (`src/api/v1/engine.py:94-110`), which is *computed at runtime* from
   header names, not *declared in the artifact*. A template cannot state which files it fits.
2. **No grain declaration.** `dedupe_on` and `combine_on` are operations, not invariants.
   Nothing in the artifact asserts that a key must be unique, so a grain change — the highest
   consequence failure mode — cannot be detected.
3. **No business-intent layer.** `var_name: "report_date"` and `value_name: "sales_amount"`
   are string defaults. `report_date` and `sales_amount` are additionally hardcoded into the
   transform (`engine.py:186-197`), so the canonical model lives in code, not in an artifact.
4. **Identity by filename.** `provider_id` falls back to `template.source_file` when
   `provider_name` is unset (`engine.py:160-163`). An undeclared semantic assumption is
   written into output data.
5. **No instance versioning or provenance.** `template_version: 3` is a *format* version
   (`templates.py:131`). There is no model version, author, approving evidence, effective date
   or supersedes-link — so the artifact cannot cross a publication boundary.
6. **Positional fragility produces silent false-apply.** When `headers` is populated,
   `filter_and_rename` renames by positional index and `read_excel_with_template` passes
   integer positions to pandas `usecols` (`templates.py:484-500`, `:555-566`). A single
   inserted source column shifts every mapping — and the run succeeds.
7. **Validation cannot fail on a wrong-but-well-formed table.** `OutputSchema` declares four
   columns, all `required=False`, with `strict=False` (`src/schema.py:12-22`). At the default
   `coerce` level, almost anything validates.

**Evidence for (recorded fairly):**

- The template *does* round-trip losslessly and is tested (`tests/test_templates_roundtrip.py`).
- It carries genuinely non-trivial structural knowledge — sheet set, header row, skiprows,
  merged-header handling, per-cell `HeaderCell` positions with `is_metadata` flags, unpivot
  configuration, cleanup switches, dedupe/aggregation keys, field types, required fields.
- Against the comparative table, it is *richer* than AutoDCWorkflow's operation list and
  comparable to Harmonia's mapping specification as a **transformation** artifact.

**Conclusion:** the defect is not in what `Template` encodes about *how to transform*. It is
in the total absence of everything the publication boundary needs — applicability, invariants,
canonical separation, provenance. Amend, do not replace.

---

## H2 — An executable schema/procedure can replace the agent for repeated work

### Verdict: **SUPPORTED — and not novel.**

**Evidence for:** five surveyed systems already do this.

- **bdi-kit / Harmonia**: a declarative JSON mapping plan replayed through
  `materialize_mapping()` recreates harmonized data without re-running the LLM. The authors
  name reproducibility as the explicit advantage of the declarative representation.
- **AutoDCWorkflow**: workflows stored in OpenRefine JSON, re-applied via the OpenRefine API.
- **DeepPrep**: the output is an ordered operator pipeline `P = (S, o₁→…→o_k)`; execution
  requires no LLM.
- **Executable Schema Contracts**: after the contract exists, extraction uses deterministic
  extractors, dedup is exact-key grouping, cross-source linking is hash-index based, routing is
  schema-conditioned. LLM involvement is limited to *optional* schema extension and answer
  synthesis.
- **Agentic Schema Refinement**: materialized SQL views are standard database objects.

**Contrary evidence:**

- **AWM deliberately keeps procedures agent-dependent.** Workflows are injected into the LLM
  prompt, and the agent may deviate. The paper's reported failure mode is that a workflow
  executes into an unexpected intermediate state (an unanticipated pop-up) and "is not flexible
  enough" to adapt. If provider workbooks were as non-stationary as web UIs, agent-independence
  would be the wrong choice.
- **The rebuttal is an assumption, not a measurement.** The claim that ERP exports are more
  stationary than web UIs is plausible and unmeasured for our providers. Recorded in
  [unanswered_questions.md](unanswered_questions.md) as UQ-2.

**Consequence for the workorder:** H2 should be removed from the research agenda. It is an
engineering decision with established prior art, not an open question. Effort should move to
applicability and verification.

---

## H3 — Previous schemas provide useful memory for new source variations

### Verdict: **SUPPORTED — and established well before LLMs.**

**Evidence for:**

- **Corpus-Based Schema Matching** (Madhavan et al., ICDE 2005): a corpus of known schemas and
  mappings improves matching on unseen schemas. Twenty years old.
- **Meta-Mappings for Schema Mapping Reuse** (Atzeni et al., PVLDB 12(5), 2019): concrete
  mappings are generalized into meta-mappings over meta-schemas, which "capture enterprise
  knowledge from previously defined schema mappings" and "use this knowledge to suggest new
  mappings for different scenarios."
- **Flatfile**, in production: a model trained on billions of mapping decisions plus retained
  past selections predicts >90% of matching actions; the explicit design target is recurring
  partners sending the same data slightly differently each week.
- Our own `Data-tool` already implements a primitive version:
  `learn_synonyms_from_mapping` (`src/core.py:190-235`) persists newly mapped header names to
  `config.user.yaml` for future auto-mapping.

**Contrary evidence:**

- No surveyed source reports reuse *failing*, but nothing establishes that reuse is **safe**
  unattended. Flatfile's residual ~10% error is tolerable only because a human confirms in a
  UI before import. Useful memory ≠ safe automation.
- The pre-LLM literature reuses *relational schemas*. Whether the same reuse behaviour holds
  over workbook structure (sheet layouts, header offsets, metadata blocks) is unestablished.
  Recorded as UQ-5.

**Consequence:** H3 should also leave the research agenda as a *question*, and re-enter as a
*design commitment* — with the open work being the retrieval key (fingerprint) and the
false-match rate, not whether reuse helps.

---

## H4 — Most source changes can be resolved without human semantic input

### Verdict: **NOT ESTABLISHED, and partly contradicted.** The top data need.

**Evidence against:**

- The drift literature is explicit that **no pipeline test catches semantic drift**, and that
  pipelines complete successfully while loading misaligned or NULL-filled records. Semantic
  drift "gets the least attention" of the drift classes.
- Semantic drift is *definitionally* undetectable from structure: the workorder's own example
  (`Revenue` changing from product revenue excluding freight to invoice total including
  freight) leaves every structural, typing and grain predicate satisfied.
- **No surveyed system measures the human-intervention rate at all.** Not one of the nine
  reports questions-per-dataset, escalation rate, or drift-class distribution.
- Flatfile — the only production system in the set — resolves the residual by asking the human
  *on every import*, which is the opposite of the hypothesis.

**Evidence for:**

- Cosmetic drift (renames, reorder, sheet rename, date format) is plausibly resolvable without
  humans, given corroborating type and value-overlap evidence. `Data-tool`'s synonym store plus
  `schema_candidates` typing heuristics already covers much of this class.
- Structural drift is detectable given declared invariants, and repairable by the modelling
  plane rather than by a human in many cases (wide→long, sheet split).
- Executable Schema Contracts reports that on stable datasets, sufficiency gating "suppresses
  extension entirely" — i.e. when nothing changed, nothing escalated. That is encouraging for
  the *stable* case, which is the common case.

**What is actually unknown:** the **class distribution** of real provider changes — what
fraction are cosmetic vs. structural vs. semantic. That single number determines whether the
whole architecture pays for itself, and it cannot be read out of any paper. It requires a
longitudinal corpus of real provider files. Recorded as UQ-1, the highest-priority open item.

**Status: hypothesis retained, unproven, and explicitly not assumed by the recommended design.**

---

## H5 — The modelling network can be isolated from production without losing necessary capability

### Verdict: **SUPPORTED, with an important caveat about what "isolated" means.**

**Evidence for:**

- `Data-agents` already specifies the boundary: Transform Agent — "no file writes"; Save Agent
  — "respect allowlist roots"; Validation Agent — "detect only; no rewriting data"; Shadow
  Agent — "never change plans or outputs."
- Harmonia keeps the LLM in an interactive loop but materialization is a separate deterministic
  call, so the agent never writes production data directly.
- Executable Schema Contracts writes `Σ′` to disk as a distinct persistence step, separate from
  ingestion.

**Contrary evidence — and the caveat:**

- **DeepPrep's central claim is that ungrounded decisions are worse.** It contrasts itself with
  methods that "make decisions without grounding in intermediate execution results." Its
  environment materializes intermediate tables and returns runtime feedback; that is what makes
  non-local revision possible.
- Therefore isolation must mean **write isolation, not read isolation**. A modelling plane that
  cannot execute candidate transformations against real data and observe the results loses the
  capability that makes revision work. It needs a real sandbox with real data, not a
  description of the data.
- A second refinement from Executable Schema Contracts: isolation need not be all-or-nothing at
  the plane boundary. That system marks individual fields `hybrid`, so LLM extraction fires
  only for those. Per-field escalation flags are a better design than a hard wall.

**Conclusion:** supported, restated as — *the modelling plane must have full read and full
sandbox-execute access, and zero production write access, with per-field escalation flags
rather than a binary boundary.*

---

## H6 — The hard problem is task modelling rather than one-off transformation generation

### Verdict: **SUPPORTED, but the framing is wrong in a way that matters.**

**Evidence for:**

- Every surveyed system produces adequate one-off transformations, and **none** of them
  provides: applicability predicates, declared grain invariants, semantic-drift detection,
  recurring-source verification, or negative memory.
- DeepPrep explicitly reports no cross-task memory. AutoDCWorkflow is scoped to one
  (purpose, table) pair. Harmonia's plan says nothing about which future file it fits. AWM's
  documented failure is precisely an applicability failure.

**Contrary evidence — the important part:**

- **One-off generation is not solved either.** AutoDCWorkflow reports operation-level F1 around
  0.71 and best answer-dimension scores around 0.71. SpreadsheetLLM reports 78.9 F1 on table
  detection — roughly one region in five is wrong. These are *good research results* and they
  are nowhere near unattended-publication quality.
- The workorder instructs the study not to spend time on "can an AI clean an Excel file,"
  assuming that capability exists. The measured evidence says it exists at ~70–80% accuracy,
  which is a materially different thing from "exists."

**Restatement that survives the evidence:**

> The hard problem is not *modelling instead of transformation*. It is **verification and
> applicability** — the machinery that determines whether a ~80%-correct generated procedure is
> allowed to become a published model, and the machinery that detects when a published model
> has stopped being valid.

Framing the work as "modelling, not transformation" carries a specific risk: it invites an
80%-correct generator through the publication boundary unexamined, because the interesting part
is assumed to be elsewhere. The publication boundary is not downstream of the hard problem.
It **is** the hard problem.

---

## Cross-cutting contrary finding

Three of six hypotheses (H2, H3, and half of H5) turned out to be **already established in the
literature**. That is contrary evidence against the *research framing itself*: a substantial
part of the proposed programme is engineering with known prior art, not open research.

The genuinely open items reduce to four:

1. Applicability predicates at grain and statistical level (L3–L4).
2. Semantic-drift detection under structural stability.
3. Replay against previously accepted periods as non-leaking ground truth for a recurring source.
4. The empirical drift-class distribution for real providers (UQ-1).

This narrowing is a positive outcome. It is also the reason the recommended first experiment
contains no agents at all.
