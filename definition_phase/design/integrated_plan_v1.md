# Definition phase — integrated plan v1

**STATUS: PLAN for designer review. Nothing frozen, no probe run, no probe
authorized.** Supersedes the *scope* of `grading_design_v0.md`; the referent
mechanism in v0 survives intact and is promoted to the architecture's spine.

Source inspection is read-only. Neither `Data-agents-demo` nor
`data-frame-tool-main` was modified.

## 0. What changed, in one line

Design v0 graded **an inventory of suspicious regions**. The target is **an
executable interpretation of an unknown workbook**. The grading mechanism does
not need replacing — it needs a bigger object to grade.

## 1. The unification: one vocabulary end to end

The reuse pass turned up something that decides the architecture.
`Data-agents-demo`'s `manual_recipe.json` binds a target to a **source pointer**:

```json
{"target": "product_code", "source_type": "column",
 "source_pointer": {"column": "Product Code"}, "data_type": "string"}
```

That `source_pointer` is the same object as design v0's `referent`. Which means
the referent is not a grading trick — it is the load-bearing primitive of every
layer:

```text
browser        a click PRODUCES a referent          (sheet:Sales, cell:B2, cols:D-O)
evidence       deterministic facts ABOUT referents  (types, density, month tokens)
LLM ↔ human    prose freely, but any schema change RESOLVES TO referents
recipe         a list of referent -> role bindings  (this IS the definition)
validator      every referent RESOLVES, and the bound set COVERS the sheet
pipeline       executes over referents, deterministically, on all rows
grader         compares PRODUCED referent bindings to FROZEN expected ones
```

Prose is the human interaction surface. Referents are the consequential output.
That is your distinction, and it holds at every layer without special-casing.

**Consequence for grading:** a recipe is *executable*, so grading gains a level
design v0 could not have — run it and compare the output table. See §7.

## 2. Reuse pass — findings

### 2.1 `Data-agents-demo` — the main starting point, confirmed

Real, working, and closer to the target than expected. `runtime/excel_flow.py`
(1031 lines) already implements a definition→approval→execution loop:

| Piece | Where | Verdict |
| --- | --- | --- |
| Artifact envelope: `run_id`, `artifact_key`, `confidence`, `alternatives`, `evidence_keys`, **`refusal_reason`** | every artifact | **Reuse unchanged.** `refusal_reason` is "I cannot establish this" as a typed field — the lab's `ask_human` in artifact form |
| `evidence_packet.json`: `preview_rows` + `file_path` + `file_hash` | `excel_flow.py` | **Reuse, extend** (§4) |
| `header_spec.json`: candidates + confidence + `needs_human_confirmation` | `_build_header_candidates` | **Reuse the structure** (candidates + alternatives), regenerate the heuristic |
| `human_confirmation.json` as a typed gate artifact | `write_human_confirmation` | **Reuse unchanged.** The human gate is an object, not a chat turn |
| `shadow.jsonl` append-only event log | `_append_shadow` | **Reuse unchanged** |
| `manual_recipe.json` — target ← source_pointer bindings | `_apply_manual_recipe` | **Adapt — this is the seed of the recipe format** (§5) |
| `table_region.json` — start/end row, include/exclude columns, sheet | `_apply_table_region` | **Adapt — fold INTO the recipe.** Two overlapping definition objects is one too many |
| **Recipe recall by structural hash** → replay with no agent | `_lookup_recipe_for_hash` | **Adapt — this is the macro-saver already built.** The predicate is wrong (§2.2) but the mechanism is right |
| `data_investigator.py` — header-density scan, column inventory | 66 lines, clean | **Reuse unchanged** as a *candidate generator*, never as a decision |
| `data_janitor.py` — multi-row header flatten (ffill+join), `clean_series` | 61 lines | **Reuse** |
| Streamlit `simple_schema_builder.py` — click a cell in `st.dataframe` → `add_field(source_pointer=…)` | 367 lines | **Adapt.** The interaction is exactly right; it needs sheets, regions and roles |
| Streamlit `streamlit_mapping_studio.py` — sheet selector, table-region editor, header override | 642 lines | **Adapt / harvest.** Has the pieces, spread across five tabs |
| Tests: `test_manual_recipe`, `test_recipe_recall`, `test_header_override`, end-to-end | `tests/` | **Reuse as regression anchors** for anything adapted |

### 2.2 Three defects in `Data-agents-demo` that the plan must fix

- **DA-1 — the loader assumes sheet 0.** `_read_preview_rows` takes
  `excel.sheet_names[0]` unconditionally; the whole evidence path is bound to it.
  The mapping-studio UI *does* have a sheet selector, so the capability exists
  but sits downstream of an assumption already made. This is precisely your
  point: *"which of these 12 sheets matter?"* is a definition decision, and today
  the loader answers it silently before anyone is asked.
- **DA-2 — the applicability predicate is wrong in both directions.**
  `_compute_structural_hash` = sha256 of the first **5** normalised preview rows
  **plus `os.path.basename(file_path).lower()`**. Too strict: next month's
  `sales_2026_02.xlsx` misses the hash and the recipe never recalls — which is
  exactly the repeat case the whole macro idea exists for. Too shallow: blind to
  sheet identity and to everything below row 5. This is the single highest-value
  fix in the reuse set, and the lab has already studied what a good applicability
  gate looks like (H: `coverage == 12 → accept, else ask_human`).
- **DA-3 — the recipe cannot express the definition.** No sheet dimension, no
  data region (that lives in a second file), no transform (unpivot), no
  exclusions, no per-field ambiguity or refusal. It binds targets to pointers and
  stops.

### 2.3 `data-frame-tool-main` — your warning confirmed, with a useful wrinkle

Unresolved conflict markers **on the checked-out main**, not only in worktrees:

```text
src/app.py        64 markers        src/templates.py   28 markers
src/pipeline.py   26 markers        src/core.py        16 markers
src/config.yaml    2 markers
```

The wrinkle: the conflicts are **not** evenly spread. These are clean and
compile:

```text
src/schema.py                        src/services/header_detection.py
src/cli.py                           src/services/io.py
src/services/__init__.py             src/services/mapping.py
                                     src/services/schema_candidates.py
```

`services/schema_candidates.py` is the valuable one — `find_numeric_blocks`,
`is_year_like`, `is_texty_col`, `_normalize_month` (fi/sv/de/en month map,
broader than the lab's Finnish-only `months.json`), `schema_diff`. Numeric-block
detection with a left-adjacent key column *is* the wide-monthly-sheet detector,
and `schema_diff` is a proto-applicability check.

**But the pieces you named for downstream — templates, column mappings,
unpivoting, coercion, validation, quarantine, repeat processing — live mostly in
the conflicted files** (`pipeline.py`, `core.py`, `templates.py`). So:

> **`data-frame-tool` is source material for the downstream stage, not a code
> dependency.** Read the ideas, re-implement. The earlier `repo_reuse_map.md`
> already documents defects in exactly those files (positional column mapping
> that silently shifts on an inserted column; `OutputSchema` with every field
> `required=False` and `strict=False`, so a structurally wrong table validates;
> unpivot ignoring `id_columns`; `combine_on` summing every numeric column).
> Importing them would import those.

## 3. Target architecture

```text
unknown workbook
   |
 (1) WORKBOOK BROWSER  sheet inventory first; raw regions; selection -> referents
   |
 (2) EVIDENCE          deterministic facts about referents; no interpretation
   |
 (3) DEFINITION DIALOGUE   LLM proposes, human clarifies. Prose is the surface;
   |                        every schema change emits recipe OPERATIONS
 (4) RECIPE DRAFT      the definition, as one executable object
   |
 (5) VALIDATE + APPROVE    structural check, resolvability, coverage,
   |                        applicability predicate; human_confirmation
 (6) DETERMINISTIC PIPELINE   executes the frozen recipe over all rows
   |
 (7) VALIDATED OUTPUT + quarantine on failure
```

**Authority boundary (your rule, made structural):** the LLM's *only* write
surface is recipe operations, and every operation must name referents. It cannot
touch a dataframe. Steps 6–7 never call a model. That is not a policy note in a
prompt — it is enforced by giving the model no other tool.

## 4. Evidence and referent representation

Sheets are first-class from the start, which is what DA-1 breaks today.

```text
sheet:<name>                      workbook:<file>        sheetset:<name>
row:<sheet>!<n>                   rows:<sheet>!<a>-<b>
col:<sheet>!<letter|header>       cols:<sheet>!<a>-<b>
cell:<sheet>!<A1>                 region:<sheet>!<A1:P97>
```

Every referent normalises to a canonical string (the v0 matcher, extended) and
must **resolve** against the workbook — a referent that does not resolve is a
hard error, not a warning. Evidence per referent is deterministic and carries no
interpretation: fill density, type mix, numeric ratio, month-token hits, blank
runs, merged ranges, formula presence. `schema_candidates.py` and
`data_investigator.py` supply most of this today.

**Evidence proposes; it never decides.** That distinction is the H result: the
month reference list is supplied, the model locates, deterministic code verifies.

## 5. Recipe / schema format

Your sketch, read as a decision list, maps cleanly onto one executable object.
**Sketch, not frozen** — §9 lists what needs deciding:

```json
{
  "recipe_version": 1,
  "workbook": {"file_hash": "sha256:…"},
  "sheets": [
    {"referent": "sheet:Sales", "role": "data",
     "header": {"referent": "row:Sales!4"},
     "data_region": {"referent": "rows:Sales!5-96"},
     "fields": [
       {"target": "product_code", "source": "col:Sales!A", "role": "id",   "type": "string"},
       {"target": "report_month", "source": "cell:Sales!B2", "role": "metadata", "type": "date"},
       {"target": "amount",       "source": "cols:Sales!D-O", "role": "period_measure",
        "transform": {"op": "unpivot", "var": "period", "value": "amount"}}
     ],
     "exclude": [{"referent": "row:Sales!97", "reason": "total row"},
                 {"referent": "col:Sales!P",  "reason": "derived total"}],
     "ambiguities": [{"referent": "cell:Sales!C2", "question": "…", "blocking": true}]
    },
    {"referent": "sheet:Notes", "role": "ignore", "reason": "free-text notes"}
  ],
  "applicability": { "…": "see §6" },
  "provenance": {"proposed_by": "llm|human", "approved_by": null, "shadow_key": "…"}
}
```

Four things this must do that `manual_recipe.json` cannot (DA-3):

1. **Sheets, including sheet *roles*** — `data` / `ignore` / `metadata` / member
   of a `sheetset`. "Do several sheets belong together?" (twelve monthly sheets
   unioned, with the period derived from the sheet name) is a definition
   decision, so `sheetset` is part of the format, not a later feature.
2. **Regions and exclusions**, folded in from `table_region.json`.
3. **Transforms** as declared operations (`unpivot`, `coerce`, `derive`) — named
   and validated, never free-form code.
4. **Ambiguity as a first-class field**, with `blocking` — the recipe can say *"I
   cannot establish this"* about one cell without failing wholesale. This is the
   demo's `refusal_reason` pushed down to field granularity.

## 6. Validation, approval, and the applicability predicate

Validation is three checks, all deterministic, all before approval:

- **Structural** — schema-valid, roles from the enumerated set, transforms known.
- **Resolvable** — every referent resolves against this workbook.
- **Coverage** — every sheet has a role, and within a data sheet every column and
  row falls under exactly one of field / exclude / region. This is design v0's
  **totality** requirement, and it does the same work: an unclassified object is
  a hole where something can be silently dropped or silently included.

Approval writes `human_confirmation.json` (reuse unchanged) over a **content
hash of the recipe**, so approval binds to an exact object.

**The applicability predicate replaces DA-2's structural hash** and deserves its
own design pass, because it is the macro-saver gate: it decides when a saved
recipe may run with no agent. It must be **declared in the recipe** and checked
before every replay — H's shape: *establish the condition, or refuse*. Candidate
signature: sheet name (or a declared pattern) + header-row cell sequence +
column count + declared key-column type profile. Explicitly **not** the filename.
When it fails, the answer is `ask_human`, never a best-effort run.

## 7. How the SILENCE / NOISE grader attaches

Design v0 survives; the frozen inventory becomes a **frozen expected recipe**,
and grading gains a third, stronger level:

```text
level 1  BINDING   did the recipe bind the right referents?      (v0 "located")
level 2  ROLE      did it assign the right roles/transforms?     (v0 "characterized")
level 3  OUTCOME   does executing the recipe produce the frozen expected table?
```

Level 3 is new and only possible because the object is executable. It is fully
deterministic, it is what actually matters, and it cannot be gamed by pointing.
It is also coarse — it says *wrong*, not *why* — so all three are reported, and
levels 1–2 remain the diagnostic.

The two error directions carry over and sharpen:

```text
SILENCE  a definition decision not made, or made by omission
         -> the total row enters the data; the ignored sheet was needed
         -> and it VALIDATES, because the output is well-formed
NOISE    ordinary columns excluded; resolvable things escalated as blocking
         ambiguities -> a human is asked about what the material answers
```

Silence remains the unsafe direction here, and level 3 shows why in a way v0
could not: a silent mis-definition produces **wrong data that passes
validation** — a false-apply, the failure mode `repo_reuse_map.md` already
identified in the downstream tool.

Unchanged from v0: unknown-unknowns are recorded, never scored, adjudicated by a
human, and absorbed into the *next* frozen expectation.

## 8. Reuse verdicts

**Unchanged** — artifact envelope incl. `refusal_reason`; `human_confirmation`;
`shadow.jsonl`; `data_investigator.py`; `data_janitor.py` header flattening;
`services/schema_candidates.py` + `services/header_detection.py` (clean, compile).

**Adapt** — `manual_recipe.json` → recipe format (§5); `table_region.json` folded
in; recipe recall mechanism kept, predicate redesigned (§6); `header_spec`
candidate structure kept, heuristic regenerated; `simple_schema_builder` cell
selection → referent binding; `streamlit_mapping_studio` sheet + region editors →
merged into the browser.

**Source material only, re-implement** — everything in `data-frame-tool`'s
conflicted files: templates, column mappings, unpivot, coercion, validation,
quarantine, repeat processing. Ideas yes; code no (§2.3).

**Fresh** — sheet-first workbook browser; referent grammar + resolver; recipe
validator (structural / resolvable / coverage); applicability predicate; the
definition dialogue's tool surface (recipe operations only); grader levels 1–3.

## 8.5 Front-door dispatch (designer, 2026-08-14)

The designer's control flow:

> is there a schema for the file → yes, use it if it's current → no, prompt the
> user to help create the schema first

This is right, and it is the H-shape at the entry point: *establish
applicability, or refuse.* It also relocates recall from an optimisation to
**the front door** — which is where it belongs, because it decides whether a
model is invoked at all. Two things in it need sharpening.

### 8.5.1 The key is the FORMAT, not the file

"A schema for the file" must mean *a schema for this provider format*, of which
the file is one instance. Twelve monthly files from one provider share one
recipe. Keying on the file is exactly DA-2's bug: the filename is in the hash, so
`sales_2026_02.xlsx` misses the recipe built for `sales_2026_01.xlsx` — recall
fails on the only case it exists for.

### 8.5.2 "Current" is three questions, and they fail differently

Collapsing them is how a false-apply happens:

```text
EXISTS      does a recipe claim this format?            -> lookup
MATCHES     does THIS file still satisfy that recipe's
            declared applicability predicate?           -> structural check
APPROVED    is the recipe's content hash still the
            human-approved one, and not revoked?        -> governance check
```

`MATCHES` is not a timestamp and `APPROVED` is not a match. A recipe edited after
approval must not execute even though it matches perfectly — the approval binds
to a **content hash**, so a post-approval edit invalidates it. That is 3E's
principle (the deterministic gate owns authority) applied to governance.

### 8.5.3 The middle branch — yes/no is one branch short

The consequential case is neither "matches" nor "doesn't": it is **drifted**. A
recipe matching 11 of 12 signals must not be run ("close enough" is the
false-apply that produces wrong data which validates), but sending the human back
to a blank definition is also wrong — they would redo work that is still correct.

The third branch is **scoped redefinition**: carry the recipe forward, mark the
delta, and open the dialogue **only on what changed** (a renamed column, one new
sheet). That is where an agent genuinely earns its keep, and it is the cheapest
possible human interaction — the J lesson, that refusal should be *bounded* and
name what it cannot establish, rather than escalating wholesale.

```text
file arrives
  |
 [1] resolve candidates        by FORMAT signature, never by filename
  |
  +-- 0 candidates  ------------------------------> DEFINE            (cold start)
  +-- >= 2 candidates ----------------------------> AMBIGUOUS         (human picks)
  +-- 1 candidate
        |
      [2] applicability predicate re-evaluated on THIS file
        |
        +-- core signals fail -----------------> DEFINE                (format changed)
        +-- passes with exceptions ------------> REDEFINE_SCOPED       (drift)
        +-- passes fully
              |
            [3] approval: content hash == approved hash, not revoked?
              |
              +-- no -------------------------> BLOCKED                (never run)
              +-- yes ------------------------> EXECUTE                (NO model)
```

**In the `EXECUTE` branch no model is invoked at all.** That is the macro-saver
outcome made economic: intelligence is paid for once at definition time, not per
file.

### 8.5.4 This is the first experiment, and it needs no open-ended grading

The dispatch decision is **a label** — `EXECUTE` / `REDEFINE_SCOPED` / `DEFINE` /
`AMBIGUOUS` / `BLOCKED` — with a frozen expected value per fixture. So it grades
exactly the way every probe in this repo already grades (`decision == expected`),
and the open-ended grading problem does not have to be solved first. It only has
to be solved for the dialogue branch.

The two error directions are the sharpest in the programme so far:

```text
false EXECUTE      runs a stale recipe on a changed file -> wrong data that
                   VALIDATES. The unsafe direction, and the exact failure
                   repo_reuse_map.md found downstream (positional mapping)
over-escalation    DEFINE on a file the recipe still handles -> the macro never
                   pays off; the human is consulted about nothing
```

Fixtures are cheap and deterministic: one approved recipe plus files that are
identical / renamed-file / column-renamed / column-inserted / sheet-added /
materially restructured / edited-after-approval. **No LLM, fully repeatable** —
the same character as Experiment J, and directly continuous with H's
`coverage == 12 → accept, else ask_human`.

## 9. Open decisions

1. **Referent syntax** — `sheet:Sales!D5` (A1-style) vs `sheet:Sales/col:D/row:5`.
   A1 is familiar to spreadsheet users and compact; the structured form is easier
   to parse and diff. This choice propagates everywhere, so it is worth an hour.
2. **Recipe format** — confirm §5's shape, especially `sheetset` and whether
   transforms stay a closed enum (recommended) or gain expressions (risk: the
   authority boundary erodes).
3. **Where the lab boundary sits.** Building all seven layers is an application,
   not an experiment. Recommended split: build layers 1, 2, 4, 5 (browser,
   evidence, recipe, validator) as *lab instrument*, and treat layer 3 (the
   dialogue) as the thing under study.
4. **Which model** for the dialogue — local per project convention (Ollama /
   GLM-5.2, as in every probe so far).
5. **First fixture** — a real multi-sheet `.xlsx` is needed; the lab's current
   fixtures are single-sheet CSVs. Authored in-lab, or archive-derived under the
   UQ-1 ordering rule?

## 10. Suggested sequence (revised after §8.5 — no probe yet)

1. Freeze the **referent grammar + resolver**, with a self-test on a real
   multi-sheet workbook. Nothing else can be built honestly first.
2. Define the **recipe format + validator** (§5–6), and prove it by expressing an
   existing `manual_recipe.json` in it and executing both to the same output.
3. Design the **applicability predicate + dispatch** (§8.5, fixes DA-2). This is
   now the **first experiment**, not plumbing: its output is a frozen label, so
   it grades the way the repo already grades and does not wait on the open-ended
   grading question. Needs a preregistration.
4. Build the **sheet-first browser** over the resolver — sheet inventory before
   any loading decision (fixes DA-1). Harvest from the two Streamlit demos.
   Instrument, not experiment.
5. Only then design the **definition-dialogue probe**, with grading levels 1–3
   and the v0 SILENCE/NOISE controls attached to a frozen expected recipe.

Steps 1, 2 and 4 are instrument-building and need no preregistration. Steps 3 and
5 are experiments and need freezes. The reordering is the point: §8.5 made a real
experiment available *before* the hard grading problem is solved.
