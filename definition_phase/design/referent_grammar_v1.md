# Referent grammar v1 — spec

**STATUS: FROZEN 2026-08-14, tag `referent-grammar-v1`.** Both decisions settled
by the designer: A1 surface form (§2), 0-based indices in code (§5). Self-test
passing. Step 1 of plan v1 §10, complete.

Every layer speaks this, so it is frozen before the recipe format is built on
top of it. **See §10 for what may and may not change.**

A **referent** is a deterministic address into a workbook. It is the primitive
the whole definition phase is built on: the browser emits them, evidence
describes them, the LLM must resolve prose to them, the recipe binds them, the
validator resolves them, the pipeline executes over them, the grader compares
them.

## 1. Grammar

```text
referent    := "workbook:"
             | "sheetset:" name
             | "sheet:" sheetref
             | "sheet:" sheetref "!" span

sheetref    := bare | "'" quoted "'"
bare        := any run without space, "!", ":", "'"
quoted      := any text; a literal "'" is doubled ("''"), Excel convention

span        := cell | cellrange | row | rowrange | col | colrange | namedcol
cell        := COL ROW                    D5
cellrange   := COL ROW ":" COL ROW        D5:P96
row         := ROW                        5
rowrange    := ROW ":" ROW                5:96
col         := COL                        D
colrange    := COL ":" COL                D:P
namedcol    := "@" header-text            @Myynti

COL         := 1-3 letters, A..XFD        ROW := positive integer
```

The **surface text** is A1, so `ROW` is a positive integer and there is no row 0
— that is what A1 means. Every **index in code** is 0-based. See §5.

## 2. Why A1 and not a structured form (**DECIDED by the designer, 2026-08-14**)

A1-style wins on the two things that matter here:

- **The human reads recipes.** A recipe is an approval artifact; `sheet:Sales!D5`
  is legible to anyone who has used a spreadsheet, `sheet:Sales/col:D/row:5` is
  not more legible, only longer.
- **The LLM already speaks it.** A1 notation is ubiquitous in training data, so
  the model emits it natively instead of being taught a bespoke encoding.

The parse-difficulty objection is answered by keeping both: **A1 is the surface
form, a typed object is the internal form.** Text is parsed to a frozen
dataclass, compared structurally, and rendered back to canonical A1. Code diffs
the object; humans and models read the string.

**Approved 2026-08-14**, together with the 0-based-indices decision in §5.

## 3. Binding mode is explicit, and that is the point

A column can be addressed two ways, and they fail in opposite directions:

```text
sheet:Sales!D          POSITIONAL   survives a rename, breaks on insert/move
sheet:Sales!@Myynti    NAMED        survives insert/move, breaks on rename
```

Neither is correct in general. `repo_reuse_map.md` records what happens when the
choice is implicit — defect D1 in `data-frame-tool`: mapping by positional index
means *one inserted column silently shifts every mapping and the run still
succeeds*. A false-apply generator.

So the grammar refuses to hide the choice. A recipe's drift-sensitivity becomes
**declared rather than accidental**, and the dispatch predicate (plan §8.5) can
read it: a recipe of positional refs and a recipe of named refs are not equally
robust to the same file change, and the predicate should know which it is holding.

**Deliberate restriction:** named addressing is single-column only. There is no
`@Myynti:@Kate` range, because a range over names presumes an ordering the
headers do not guarantee. A recipe needing a contiguous block uses positional
(`D:P`); a recipe needing a named set lists the columns. Stated boundary, not an
oversight.

## 4. Normalisation and canonical form

Two distinct operations, deliberately not the same function:

- **`key(ref)`** — comparison key: casefold, collapse internal whitespace,
  column letters uppercased. Two referents are *the same referent* iff their keys
  match. This is design v0's matcher, extended, and it is what the grader uses.
- **`render(ref)`** — canonical display: column letters uppercase, sheet name
  quoted iff it contains a space, `!`, `:` or `'`, embedded `'` doubled.

Ranges normalise to (min, max), so `D5:B2` and `B2:D5` are one referent.

Sheet and header lookup is **case-insensitive**; resolution reports the
workbook's actual spelling, so canonicalisation against a real workbook is a
resolution result, not a string operation.

## 5. Two number spaces, one boundary (designer, 2026-08-14)

**Decision: A1 on the surface, 0-based everywhere in code.**

These are not in conflict, but they are easy to conflate, so the rule is exact:

- **A1 notation is 1-based by definition.** `D5` is the cell Excel shows in row
  5, column D. The string is what a human reads and what they see when they
  click that cell in Excel.
- **Every index in code is 0-based**, because the consumers are Python, pandas
  and openpyxl — and because `Data-agents-demo`'s existing `manual_recipe`
  pointers are 0-based too.

```text
"sheet:Sales!D5"  --parse-->  row0=4, col0=3  --render-->  "sheet:Sales!D5"
```

The conversion happens in exactly two functions, `parse()` and `render()`.
Nothing between them ever sees a 1-based number.

**What was explicitly NOT done:** reinterpreting the A1 *string* as 0-based
(so that `D5` would mean pandas row 5). That would make a recipe disagree with
what the human sees in Excel by exactly one row, silently, on every binding —
the precise failure class this programme exists to study.

Three mechanisms keep the boundary from leaking:

1. **Every index-bearing field and parameter is suffixed `0`** — `row0`,
   `col0`, `row0_last`, `col0_last`, `header_rows0`. The convention is visible
   at each call site rather than remembered. A header on the row Excel labels 4
   is `header_rows0={"Sales": 3}`.
2. **`WorkbookView.dims()` returns counts, not max indices** — `(9, 6)` for
   `Sales`, so bounds are `row0 < n_rows` with no off-by-one available. openpyxl
   is 1-based and that conversion is confined inside `WorkbookView`.
3. **`Resolution.row_slice()` / `col_slice()` return half-open `(start, stop)`**
   for `df.iloc`, so no caller writes `+1` by hand. Ranges are stored 0-based
   *inclusive*; the slice helpers are the only sanctioned conversion.

A welcome consequence: `from_legacy_pointer()` now does **no arithmetic at
all** — legacy pointers are already 0-based, so the indices carry across
unchanged. Choosing 0-based internals deleted that hazard rather than managing
it.

## 6. Resolution

```text
resolve(referent, workbook, header_rows) -> Resolution
```

A referent that does not resolve is a **hard error, never a warning** (plan §6).
Failure reasons are a frozen enum:

| reason | meaning |
| --- | --- |
| `malformed` | did not parse |
| `sheet_not_found` | no sheet of that name (case-insensitive) |
| `sheetset_not_declared` | no such declared sheet set |
| `out_of_bounds` | outside the sheet's used range |
| `header_row_not_declared` | a `@name` column was addressed without a declared header row for that sheet |
| `header_not_found` | no column with that header |
| `header_ambiguous` | **two or more columns carry that header** |

`header_ambiguous` refuses rather than taking the first match. Picking one would
be a claim the evidence does not establish — the failure 3A–3E is about, and the
same rule H's gate enforces. Duplicate headers are common in real exports, so
this fires in practice.

`header_row_not_declared` is not pedantry either: `@Myynti` is meaningless until
someone says which row the headers are on. The grammar forces the recipe to have
declared it.

## 7. What is out of scope for the grammar

Deliberately not here, to keep the primitive small:

- **Merged cells** — a merge is a fact *about* a region, so it belongs to the
  evidence layer. `W1_multisheet.xlsx` contains one so the later layer has a case.
- **Roles** (`id`, `metadata`, `period_measure`, `exclude`) — those are recipe
  bindings, not addresses. A referent says *where*, never *what it means*.
- **Transforms** — recipe layer.
- **Cross-workbook references** — `workbook:` addresses the workbook under
  definition; there is no external-file reference and there should not be one.

## 8. Fixture

`fixtures/W1_multisheet.xlsx`, generated reproducibly by `harness/make_w1.py`
(regenerating gives a byte-identical file; the generator is the fixture's source
of truth). Six sheets, each earning its place:

| Sheet | What it exercises |
| --- | --- |
| `Sales` | the realistic messy case: merged title, timestamp, blank row, header on row 4, data, a total row and a total column |
| `Myynti 2026` | a sheet name **with a space** → quoting |
| `Dup` | **two columns headed `Myynti`** → `header_ambiguous` |
| `Notes` | free text, no table → a sheet whose role is `ignore` |
| `2026-01`, `2026-02` | two monthly sheets → a `sheetset` is meaningful, and "do several sheets belong together?" is a real question on this file |

## 9. Status

Parser, renderer, comparison key, resolver, slice helpers and
`from_legacy_pointer` are implemented in `harness/referents.py` with a self-test
covering round-trips, the A1↔0-based boundary in both directions, comparison
keys, quoting including doubled apostrophes, range ordering, the absence of row 0
in A1, column-letter maths to XFD, legacy pointers carrying across without
arithmetic, `iloc` slice helpers, and every failure reason — including
`header_ambiguous` — against the real workbook.

```bash
python definition_phase/harness/referents.py --self-test
```

Both open decisions are settled. **Frozen; step 2 (recipe format + validator)
builds on it.**

## 10. Standing traps — what the freeze binds

- **The A1 string is 1-based and the code is 0-based. Do not "simplify" this to
  one convention.** Making the string 0-based breaks agreement with Excel;
  making the code 1-based breaks agreement with pandas. The boundary in
  `parse()`/`render()` is the design, not an accident.
- **Do not drop the `0` suffix** from `row0` / `col0` / `row0_last` /
  `col0_last` / `header_rows0`. It is what makes the convention visible at every
  call site.
- **Do not make `header_ambiguous` pick the first match.** Refusing is the
  point; it is the same rule as H's gate and 3E's comparison gate.
- **Do not add named column ranges** (`@A:@B`). The single-column restriction is
  deliberate (§3).
- **Do not add cross-workbook references.** `workbook:` addresses the workbook
  under definition; there is no external-file reference and there should not be.
- **Do not extend the grammar to carry roles or transforms.** A referent says
  *where*, never *what it means*. Roles belong to the recipe.
- **`W1_multisheet.xlsx` is generated by `make_w1.py`.** Change the generator,
  never the .xlsx, and re-run the self-test — the fixture's row/column
  expectations are asserted in it.
- Adding a new *failure reason* to `REASONS` requires adding a self-test that
  exercises it; the self-test asserts no reason is declared but untested.
