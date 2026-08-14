# Referent grammar v1 — spec

**STATUS: v1 proposed, self-test passing. Ready to freeze pending the designer's
call on §2.** Step 1 of plan v1 §10. Nothing downstream should be built until
this is frozen, because every layer speaks it.

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

**1-based, like A1 and like what the user sees in Excel.** See §5 — this is a
real hazard against the existing code.

## 2. Why A1 and not a structured form (open decision §9.1, decided provisionally)

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

Reject if you disagree — it propagates everywhere, so it is worth the argument
now rather than after step 2.

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

## 5. Off-by-one hazard — 1-based here, 0-based there

`Data-agents-demo`'s `manual_recipe.json` uses **0-based** pointers:

```json
{"source_pointer": {"row": 1, "col": 1}}     -> this grammar: sheet:X!B2
```

This grammar is **1-based**. Any adapter between them must convert explicitly, and
a silent off-by-one would mis-bind every field in a recipe while still producing
a plausible-looking table — the exact class of failure the programme is about.
`from_legacy_pointer()` exists so the conversion has one implementation and one
test, rather than being open-coded at each call site.

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

Parser, renderer, comparison key, resolver and `from_legacy_pointer` are
implemented in `harness/referents.py` with a self-test covering round-trips,
canonicalisation, quoting, range ordering, 1-based enforcement, legacy
conversion, and every failure reason including `header_ambiguous` against the
real workbook.

**Awaiting: the §2 decision, then freeze.**
