# define-lab-process (r2c frozen revision)

A reusable Goose skill that helps a human define a candidate **reconciliation** process
and produces a **Work Definition v0** artifact — the structural contract Learning Lab
validates deterministically, without reading prose.

> This revision is **frozen** for the W1-A experiment. It must not be edited between
> runs A1–A5. Its sha256 is recorded in `work_interface/w1a/skill/PROVENANCE.md`.
> Five fresh Goose sessions (A1–A5) each use this exact skill, the same frozen fixtures,
> and the same frozen human-answer script.

## When to use

Use this skill when a human has two source files that describe overlapping records
(e.g. a supplier statement and an internal ledger) and wants to define how to
reconcile them. The output is one JSON artifact, `work_definition.json`, that Learning
Lab can validate against the structural Work Definition v0 contract.

## What this skill produces — the Work Definition v0 contract

A Work Definition is an **envelope over a task-family body**. v0 supports exactly one
task family: `reconciliation`. The envelope owns identity, source roles, the
evidence/authority basis of each load-bearing decision, unresolved questions, and the
requested destination/authority. The body owns the reconciliation semantics and
reuses Learning Lab's **closed vocabularies** — you do not invent new field names,
comparisons, or policies.

### The exact shape

Produce exactly this structure. Values in `«…»` are decisions you must derive from the
fixtures or ask the human for. Do not copy the placeholder text into the artifact.

```json
{
  "work_definition_version": 0,
  "task_family": "reconciliation",
  "model_id": "«a short stable id for this process»",
  "provenance": {
    "producer": "«your model name»",
    "skill": "define-lab-process",
    "produced_at": "«ISO date»"
  },
  "purpose": "«one sentence: what this reconciliation is for»",
  "sources": {
    "«role_a»": {
      "role_label": "«human name for this source»",
      "fixture": "«basename of the sample file, e.g. supplier-statement.txt»",
      "observed_fields": ["«exact header strings, comma-separated, in order»"],
      "basis": "observed"
    },
    "«role_b»": {
      "role_label": "«human name for this source»",
      "fixture": "«basename of the sample file»",
      "observed_fields": ["«exact header strings»"],
      "basis": "observed"
    }
  },
  "body": {
    "left": "«role_a»",
    "right": "«role_b»",
    "match_on": {
      "left_field": "«field in left that identifies a record»",
      "right_field": "«field in right that identifies the same record»",
      "basis": "human_confirmed",
      "confirmation": "«id of the human confirmation that settled this»"
    },
    "compare": [
      {
        "field": "«field present in BOTH sources to compare»",
        "comparison": "«one of the comparison vocabulary»",
        "tolerance": "«decimal string, only when comparison is within»",
        "basis": "human_confirmed",
        "confirmation": "«confirmation id»"
      }
    ],
    "classify": {
      "both_same": "«label when records match on key and compare is equal»",
      "both_different": "«label when records match on key but compare differs»",
      "only_left": "«label when a record is in left but not right»",
      "only_right": "«label when a record is in right but not left»"
    },
    "output_order": "«one of the output-order vocabulary»",
    "on_duplicate_key": "«one of the duplicate-key policy vocabulary»",
    "on_non_numeric": "«one of the non-numeric policy vocabulary, required when a numeric compare is declared»"
  },
  "output": {
    "reports_fields": ["«fields the report row names — must be the match key, a compared field, or a declared context field»"],
    "context_fields": ["«extra fields carried for context — these become declared, so reports_fields may name them»"],
    "provenance": {
      "reports_fields": {
        "basis": "human_confirmed",
        "confirmation": "«id of the human confirmation that settled the report fields»"
      },
      "context_fields": {
        "basis": "human_confirmed",
        "confirmation": "«id of the human confirmation that settled the context fields»"
      }
    }
  },
  "human_confirmations": [
    {
      "id": "«stable id, e.g. Q_match_key»",
      "question": "«the exact question you asked the human»",
      "answer": "«the human's answer, verbatim»",
      "basis": "human_confirmed"
    }
  ],
  "open_questions": [
    {
      "id": "«stable id»",
      "question": "«a fact that remains unknown»",
      "load_bearing": false,
      "status": "unresolved"
    }
  ],
  "requested_destination": "review_only",
  "requested_delivery": { "format": "«e.g. json_discrepancy_report»" },
  "requested_authority": null
}
```

### Closed vocabularies (use these EXACT values, no others)

| Slot | Allowed values |
|---|---|
| `work_definition_version` | `0` |
| `task_family` | `reconciliation` |
| `sources.<role>.basis` | `observed` (the fixture header is read mechanically) |
| `match_on.basis`, `compare[].basis` | `observed` or `human_confirmed` (these are **executable** choices; `proposed` and `unresolved` are NOT authority and will be refused) |
| `compare[].comparison` | `exact`, `trim`, `casefold`, `trim_casefold`, `within` |
| `compare[].tolerance` | a non-negative decimal **string** (e.g. `"0.01"`); present **only** when `comparison` is `within`; absent for all other comparisons |
| `classify` keys | exactly `both_same`, `both_different`, `only_left`, `only_right` when any `compare` is declared |
| `output_order` | `left_then_right`, `sorted_by_key` |
| `on_duplicate_key` | `refuse_run`, `refuse_key` |
| `on_non_numeric` | `refuse_run`, `refuse_key` (required whenever a `within` compare is declared) |
| `open_questions[].status` | `unresolved` only — `open_questions` holds only UNRESOLVED facts, so there is no "resolved" state. A settled fact is removed from `open_questions` and recorded in `human_confirmations` instead |
| `requested_authority` | `null` only |

### Evidence / authority rules (load-bearing — these are what the validator checks)

- **`observed_fields` must be the EXACT strings from the fixture's `Header:` line, in
  order.** Do not normalize, merge, or rename. `Supplier Name` and `SupplierName` are
  different fields; if you write `SupplierName` when the header says `Supplier Name`,
  the artifact is refused. Read the header, copy each column name verbatim.
- **One `basis` per decision, as a single scalar string.** Never a list. The same
  decision must not be tagged two ways (e.g. both `observed` and `human_confirmed`).
- **Executable choices** (`match_on`, each `compare[]`) must rest on `observed` or
  `human_confirmed`. A `proposed` or `unresolved` basis on an executable choice is
  refused.
- **A `human_confirmed` basis must point at a confirmation id that exists in
  `human_confirmations`.** Every confirmation you reference must have a record there
  with a matching `id`, the question you asked, and the human's verbatim answer.
- **`compare` fields must be `observed_fields` on BOTH sources.** The match-key fields
  must be `observed_fields` on their own source.
- **`output.provenance` is required, with one entry for `reports_fields` and one for
  `context_fields`.** Each entry carries a single scalar `basis` and a `confirmation`
  id, exactly as `match_on` and `compare[]` do, and the id must be one that exists in
  `human_confirmations`.
- **`output.reports_fields` may name only:** a match-key field, a compared field, or a
  field listed in `output.context_fields`. Anything else is an undeclared semantic and
  is refused.
- **`human_confirmations` and `open_questions` are disjoint.** A fact the human
  settled belongs in `human_confirmations`; `open_questions` carries only what
  remains unresolved. The same fact must never appear in both, and a settled fact
  must not be left in `open_questions` under any status.

### Authority rules (the proposal is not authority)

- `requested_authority` must be `null`.
- Never set any of these keys to a truthy value: `established`, `is_established`,
  `approved`, `is_approved`, `validation_override`, `skip_validation`,
  `bypass_validation`. Their presence is refused — a proposal cannot self-authorize
  or bypass validation.
- `requested_destination` / `requested_delivery` are intent only. They are never read
  as authority. Do not write an `authority_status` prose field expecting it to be
  trusted — it will be ignored; only the structural fields above are checked.

## Procedure

1. **Load the skill**: call `load_skill(name: "define-lab-process")`.
2. **Inspect the two sample files** in your working directory. Read each file, find
   the `Header:` line, and record the column names **verbatim**. These become the
   `observed_fields` for that source. Record the fixture basename (e.g.
   `supplier-statement.txt`). Do not infer business rules the files do not state.
3. **Separate observed from inferred.** The fixture header and column values are
   `observed`. Which file plays which business role, which field identifies a record,
   which fields to compare, and with what tolerance, are **not** in the file — those
   are decisions a human must settle, so they carry `basis: human_confirmed`.
4. **Identify the two source roles.** Pick short role keys (e.g. `statement`,
   `ledger`) and a human-readable `role_label` for each. Use the roles as `body.left`
   and `body.right`.
5. **Ask the human only the minimum load-bearing questions.** Ask, do not assume:
   - Which field identifies the **same record** in both files? (→ `match_on`)
   - Which field(s) should be **compared**, and with what comparison and tolerance?
     (→ `compare[]`)
   - Is any other apparent field (e.g. a currency or status field) **part of the
     reconciliation rule**, or is it incidental? If a field looks load-bearing but the
     human says it is not, record that as a `human_confirmation` (it settled the
     question) rather than leaving it `unresolved`.
   - Which file, if either, is the **source of truth**? (If neither — both are peers —
     that is itself a decision worth confirming; it shapes the `classify` labels.)
   - Which fields should appear in the **report row**, and which are **context**?
   Record each answer verbatim in `human_confirmations` with a stable `id`, and
   reference that id from the `confirmation` slot of the decision it settled.
6. **Stop at a load-bearing unanswered question.** If a fact that would change the
   result cannot be settled from the files or the human, record it in
   `open_questions` with `load_bearing: true, status: "unresolved"`. The artifact will
   be refused for `load_bearing_unresolved` — that is the correct outcome; do not
   guess to make it pass. Non-load-bearing unknowns use `load_bearing: false`.

   **Settled facts have exactly one home.** Once the human answers, the fact is no
   longer an open question: **remove it from `open_questions`** and record it in
   `human_confirmations`. Do **not** leave it listed and mark it settled in place —
   `status` has one accepted value, `"unresolved"`, and any other value is refused
   for `open_question_status_invalid`. Any load-bearing entry in `open_questions`
   refuses whatever its `status` claims.
7. **Assemble the structural artifact** following the exact shape and the closed
   vocabularies above. Keep `purpose` and `role_label` as short prose (they are
   non-load-bearing description, not authority).
8. **Write exactly one file**: `work_definition.json` into your current run directory.
   The artifact must be valid JSON and self-contained — a fresh session should
   understand the proposed process from the JSON alone.

## Constraints (do not cross these)

> A completed definition is a **proposal** for Learning Lab validation. It is not an
> established process and carries no execution authority.

- Do not modify Learning Lab product code, tests, roadmap, README, PRODUCT.md, or
  worker state.
- Do not establish, run, or promote a Learning Lab worker.
- Do not call cloud models; use only the local Goose model that is currently selected.
- Do not infer business meaning the files do not give. If meaning is unknown, ask the
  human; if still unknown, mark it an open question.
- Do not treat filenames as authoritative business meaning.
- Do not normalize or "fix" field names. Copy header strings verbatim.
- Do not add `established`, `approved`, `validation_override`, or any
  self-authorization key.
- Keep all new artifacts inside your current run directory.