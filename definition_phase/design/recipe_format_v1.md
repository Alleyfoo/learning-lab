# Recipe format v1 + validator — spec

**STATUS: v1 proposed, self-test passing. Not frozen.** Step 2 of plan v1 §10.
Builds on the frozen referent grammar (`referent-grammar-v1`); every address in a
recipe is a grammar string, and the grammar is not extended to carry meaning.

## 1. What a recipe is

**The recipe is the definition phase's output** — the executable interpretation
of an unknown workbook. Prose is how a human and an LLM get to it; the recipe is
what survives, what gets approved, and what runs.

It answers, per workbook: which sheets matter, where each table starts, what is
header / metadata / data / total / note, which columns carry which role, what
needs unpivoting, and what still needs a human.

## 2. Shape

```json
{
  "recipe_version": 1,
  "recipe_id": "W1_sales",
  "workbook": {"source_hint": "W1_multisheet.xlsx"},
  "sheetsets": {"Months": ["2026-01", "2026-02"]},
  "sheets": [
    {
      "sheet": "sheet:Sales",
      "role": "data",
      "header_row":  "sheet:Sales!4",
      "data_region": "sheet:Sales!5:8",
      "fields": [
        {"target": "paivitetty", "source": "sheet:Sales!B2",     "role": "metadata", "type": "date"},
        {"target": "tuote",      "source": "sheet:Sales!@Tuote", "role": "id",       "type": "string"},
        {"target": "myynti",     "source": "sheet:Sales!B:D",    "role": "period_measure", "type": "number",
         "transform": {"op": "unpivot", "var_target": "kuukausi", "value_target": "myynti"}}
      ],
      "exclude": [
        {"referent": "sheet:Sales!9", "reason": "YHTEENSÄ grand-total row: an aggregate, not a product"}
      ],
      "ambiguities": [
        {"referent": "sheet:Sales!F6", "question": "…", "blocking": true}
      ]
    },
    {"sheet": "sheet:Notes", "role": "ignore", "reason": "free text, no table"}
  ],
  "applicability": null,
  "provenance": {"proposed_by": "human", "approved_by": null, "approved_recipe_sha256": null}
}
```

**Closed enums** (an unknown value is a structural failure, never a pass-through):

```text
sheet role   data | ignore | metadata
field role   id | measure | period_measure | metadata | derived
transform    unpivot | coerce | derive
type         string | number | date | boolean
```

Transforms stay a **closed enum with declared parameters** rather than
expressions (plan §9.2). An expression language would let the model write
arbitrary computation into the recipe, which is precisely the authority boundary
the architecture exists to hold: the LLM proposes *what things are*, deterministic
code decides *what happens to them*.

### Field roles bind different referent kinds

| role | source kind | note |
| --- | --- | --- |
| `id`, `measure`, `period_measure` | `col`, `colrange`, `namedcol` | participates in column coverage |
| `metadata` | `cell` | a scalar broadcast to every output row; must sit **outside** the data region |
| `derived` | *no source* | value comes from the transform (e.g. the sheet name) |

Mismatches are structural failures, so a recipe cannot quietly bind a cell where
a column is meant.

### Exclusions require a reason

`reason` is mandatory. An exclusion asserts *this is not data* — the highest-cost
claim in the whole definition, and the one that silently drops rows if it is
wrong. Requiring prose costs nothing and makes review possible.

### Ambiguity is first-class

An `ambiguity` names a referent the definition **cannot establish**, with the
question a human must answer. `blocking: true` means the recipe must not be
approved until it is resolved. This is the demo's `refusal_reason` pushed down to
cell granularity, and it lets a recipe be *complete and honest* rather than
complete and wrong.

## 3. Sheetsets — "do several sheets belong together?"

> **STATUS 2026-08-14: expressible, and NOT executable.** The format describes a
> sheetset and the validator checks it, including member-layout conformance — but
> the executor resolves one sheet per data entry and cannot union a set, so such a
> recipe is now **refused up front** (`executor_cannot_honour`) instead of
> validating cleanly and failing at execution. Found by the semantic parity check
> (`harness/semantic_parity.py`), not by inspection: it is the seventh instance of
> the PRO-2 family and the first that level-two completeness structurally could not
> see, because a sheetset is a *referent kind*, not an enum value. The design below
> stands as the intended shape; implementing it is open work.

A `sheetset` entry declares that several sheets share one layout and union into
one output. Twelve monthly sheets, period taken from the sheet name, is the case.

```json
{"sheet": "sheetset:Months", "role": "data", "layout_from": "sheet:2026-01",
 "header_row": "sheet:2026-01!1", "data_region": "sheet:2026-01!2:3",
 "fields": [ …addressed against the prototype sheet…,
   {"target": "kausi", "role": "derived", "type": "string",
    "transform": {"op": "derive", "from": "sheet_name"}}]}
```

Bindings are expressed against a **prototype sheet** (`layout_from`), and the
validator checks every member's header row matches the prototype's. This needs no
grammar extension — the frozen grammar has no member-relative referent and should
not grow one.

That member check is a small applicability predicate, which is the same
machinery step 3 needs at the front door. Deliberate: the concept appears twice
because it is one concept.

## 4. Validation — three checks, all deterministic, all before approval

```text
STRUCTURAL   schema-valid; enums known; targets unique; referent kinds match roles
RESOLVABLE   every referent resolves against THIS workbook (frozen grammar)
COVERAGE     every sheet has a role, and within each data sheet every row and
             every column is claimed EXACTLY ONCE
```

### Coverage is the load-bearing check

```text
row    claimed by exactly one of  { header_row, data_region, a row exclusion }
column claimed by exactly one of  { a column-bound field, a column exclusion }
```

This is design v0's **totality**, and it does the same work here as there: an
unclassified row or column is a hole where something enters or leaves the output
without anyone deciding it should. In this fixture, forgetting to exclude the
`YHTEENSÄ` row makes it *unclassified* rather than *silently included* — the
SILENCE failure caught statically, before a single row is read.

Double-claiming is equally a failure. A column both bound as a field and excluded
is not a harmless redundancy; it is two incompatible statements about what the
column is.

### Resolution order

`@name` referents cannot resolve until the header row is known, so the validator
derives `header_rows0` **from the recipe** before resolving fields. A recipe whose
`header_row` does not resolve therefore fails before its named columns are even
attempted — which is correct: they are meaningless until it does.

### Validity is not approvability

```text
valid       structural + resolvable + coverage all clean
approvable  valid AND no blocking ambiguity
```

Kept separate on purpose. A recipe can be perfectly well-formed and still not
runnable because a human question is open. Collapsing the two would make the
honest answer ("I have described this correctly and one thing still needs you")
indistinguishable from an error.

## 5. Problem codes (frozen enum)

```text
structural   unknown_recipe_version | missing_key | unknown_sheet_role |
             unknown_field_role | unknown_transform_op | unknown_type |
             duplicate_target | malformed_referent | wrong_referent_kind |
             missing_exclude_reason | field_source_kind_mismatch |
             metadata_cell_in_data_region
resolution   unresolvable_referent          (detail carries the grammar's reason)
coverage     sheet_unclassified | column_unclassified | column_double_bound |
             row_unclassified | row_double_classified
sheetset     sheetset_member_layout_mismatch
approval     blocking_ambiguity             (does not make the recipe invalid)
```

## 6. Legacy adapter

`from_legacy_manual_recipe()` converts `Data-agents-demo`'s `manual_recipe.json`
into this format, which is the expressiveness proof plan §10 step 2 asks for: the
new format must subsume the old object rather than merely resemble it. Legacy
pointers are 0-based and so is the grammar, so the conversion carries indices
across without arithmetic.

What the legacy object **cannot** say, and this format can: which sheet, the data
region, what to exclude, what transform applies, and what is still ambiguous —
i.e. exactly defects DA-1 and DA-3.

## 7. Deferred, deliberately

- **`applicability`** — the key is reserved and currently `null`. It is step 3
  (plan §8.5) and needs its own design; a placeholder that guessed at it would be
  worse than an honest hole.
- **Execution.** This step delivers format + validator. The validator's
  `--dry-run` resolves every binding and reports the exact rows and columns each
  would consume, plus sample values — enough to show the bindings point at real
  data, without implementing unpivot. The deterministic pipeline is step 6.
- **Approval mechanics** — `provenance.approved_recipe_sha256` is defined (the
  approval binds to a content hash, per plan §8.5.2) but nothing writes it yet.

## 8. Status

`harness/recipe.py` (model, loader, legacy adapter) and
`harness/validate_recipe.py` (three checks, dry-run, self-test). Worked recipes
in `recipes/`, including two deliberately broken ones that must fail with
specific codes.

```bash
python definition_phase/harness/validate_recipe.py --self-test
```
