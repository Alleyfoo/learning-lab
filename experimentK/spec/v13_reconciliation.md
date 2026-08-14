# Experiment K — v1.3 reconciliation (the C8 attack): preregistration

**STATUS: FROZEN before any v1.3 implementation exists.** Fourth separate
measurement. K (v1), the C3-fix replay (v1.1) and the row-shape replay (v1.2)
stand as measured. Deterministic — **no LLM anywhere.**

## Why this does not violate the v1.2 standing trap

The v1.2 trap reads: *"Do not add patterns, regex or value lists to
`data_row_shape` to catch C8… catching it needs a different kind of evidence,
and that is a separate question."*

v1.3 adds **no shape constraint and no content predicate**. It adds a
*relational* check: does the file's own declared total equal the sum of the rows
the recipe treats as data?

```text
C8 data rows (as the recipe sees them)   10 + 7 + 17 + 5  = 39
C8 stated YHTEENSÄ                                        = 22
                                                     ✗ does not reconcile
```

The subtotal is caught **without knowing what `VÄLISUMMA` means** — the evidence
is arithmetic the provider themselves put in the file. This is the different kind
of evidence the trap pointed at, taken as its own freeze, as the trap required.

Security-wise it is *narrower* than what already exists: `label_in` compares
strings, reconciliation only adds numbers. Nothing branches on what a cell says.

## v1.3 (FROZEN)

One optional key per data-sheet entry:

```json
"reconcile": [
  {"total_row": {"op": "label_in", "column": "sheet:Sales!@Tuote",
                 "values": ["YHTEENSÄ"]},
   "columns": "sheet:Sales!B:D",
   "reason": "the stated grand total must equal the sum of the data rows"}
]
```

For each column in `columns`: sum the data-region rows, compare to the total
row's cell. A mismatch raises `reconciliation_failure`, which the front door
treats as a coverage problem → `REDEFINE_SCOPED`.

- Blank cells contribute 0; non-numeric cells are already caught by v1.2's shape
  check, so reconciliation assumes numeric and skips what it cannot parse.
- Comparison uses an absolute tolerance of `1e-9` (float noise only, not a
  rounding allowance).
- If the total row is not found, the check is **skipped, not failed** — many real
  sheets have no total, and a missing total is not evidence of anything.

**`COVERAGE_CODES` in `dispatch.py` must list `reconciliation_failure`.** This is
stated explicitly because v1.2 run 1 failed exactly here: a new code was added in
one layer and silently not consumed by the other.

## The residual, authored in advance: C14

Reconciliation catches C8 because C8's sheet **stops adding up**. It cannot catch
a subtotal that the provider also folded into the grand total, because that sheet
adds up perfectly and is merely double-counted.

`C14_reconciling_subtotal.xlsx`: the same `VÄLISUMMA` row, with `YHTEENSÄ`
updated to `39 / 49 / 44` — the sum of all four data rows *including* the
subtotal. Internally consistent, semantically wrong.

```text
C8   stated total disagrees with the rows  -> caught by arithmetic
C14  stated total agrees with the rows     -> arithmetic has nothing to say
```

C14 is frozen as a **predicted false EXECUTE**. Each format has narrowed the
residual; none has removed it, and this one names where it now sits.

## Predicted outcomes (FROZEN)

| ID | truth | v1 | v1.1 | v1.2 | **v1.3 predicted** |
| --- | --- | --- | --- | --- | --- |
| C1 | `EXECUTE` | ✓ | ✓ | ✓ | `EXECUTE` |
| C2 | `EXECUTE` | ✓ | ✓ | ✓ | `EXECUTE` |
| C3 | `EXECUTE` | ✗ | ✓ | ✓ | `EXECUTE` |
| C4 | `REDEFINE_SCOPED` | ✓ | ✓ | ✓ | `REDEFINE_SCOPED` |
| C5 | `REDEFINE_SCOPED` | ✓ | ✓ | ✓ | `REDEFINE_SCOPED` |
| C6 | `REDEFINE_SCOPED` | ✓ | ✓ | ✓ | `REDEFINE_SCOPED` |
| C7 | `DEFINE` | ✓ | ✓ | ✓ | `DEFINE` |
| C8 | `REDEFINE_SCOPED` | ✗ | ✗ | ✗ | **`REDEFINE_SCOPED` ✓ recovered** |
| C9 | `DEFINE` | ✓ | ✓ | ✓ | `DEFINE` |
| C10 | `AMBIGUOUS` | ✓ | ✓ | ✓ | `AMBIGUOUS` |
| C11 | `BLOCKED` | ✓ | ✓ | ✓ | `BLOCKED` |
| C12 | `BLOCKED` | ✓ | ✓ | ✓ | `BLOCKED` |
| C13 | `REDEFINE_SCOPED` | ✓ | ✗ | ✓ | `REDEFINE_SCOPED` (shape) |
| C14 | `REDEFINE_SCOPED` | ✗ | ✗ | ✗ | **`EXECUTE` ✗ the residual** |

```text
predicted   v1    11/14   v1.1  11/14   v1.2  12/14   v1.3  13/14
            v1.3  over_escalation {}    false_execute {C14}
```

C13 note: the footnote reconciles (blanks contribute 0), so v1.3 catches it via
v1.2's shape rule, not via arithmetic. The two checks are independent and both
must remain.

## Decision table

| Condition | Outcome |
| --- | --- |
| every v1.3 cell matches the prediction | **PASS_AS_PREDICTED** |
| C8 not recovered | **FAIL_FIX** |
| C1, C2 or C3 regresses from `EXECUTE` | **FAIL_REGRESSION** — reconciliation must not fire on clean files |
| **C14 is caught** | **RESULT_BETTER_THAN_PREDICTED** — investigate before banking; arithmetic cannot distinguish a consistent double-count, so a catch means something other than the stated rule is doing the work |
| a false EXECUTE outside `{C14}` | **FAIL_UNSAFE** |
| any earlier arm differs from its recorded result | **VOID** |

## Hard stop

No LLM. No changes to the frozen grammar or to any recorded result. No patterns,
regex or value lists added to `data_row_shape`. Reconciliation compares numbers
only — **any check that branches on what a cell says needs its own freeze.**

## Recorded, not built: the white-text asymmetry

The designer's point (2026-08-14): a spreadsheet cell can carry text a human
does not see — white font, hidden rows or columns, a very narrow column, a
custom number format.

This is the original reservation-calendar injection with a better hiding place.
The name field carrying *"forget your instructions"* was at least visible to
whoever looked; **white text is visible to the agent and invisible to the human
approving the recipe.** That breaks an assumption the architecture currently
rests on — that the human and the machine are reviewing the same document.

Nothing in v1–v1.3 addresses it, and nothing here pretends to:

- The **validator** reads values, so white text is non-blank and can satisfy
  `require_non_blank` while a human sees an empty cell.
- The **definition agent** reads values too, so hidden text is injection surface
  with no visual tell for the reviewer.
- The **approval** binds a content hash of the *recipe*, not of the workbook
  region a human looked at.

**Design requirement it generates for step 4 (the browser):** the browser must
render *what the agent sees* — raw cell values, with formatting-hidden content
flagged rather than reproduced faithfully — so that human review and machine
reading cannot silently diverge. A pixel-accurate Excel rendering is the wrong
target and would actively hide the attack.

That is a separate experiment (detecting and surfacing formatting-hidden
content), and it is **not authorized here**.
