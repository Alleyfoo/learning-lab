# Experiment K — v1.2 row-shape expectation: preregistration

**STATUS: FROZEN before any v1.2 implementation exists.** A third separate
measurement. K (format v1) and the C3-fix replay (v1.1) stand as measured and
are not re-graded. Deterministic — **no LLM anywhere.**

## Correction to a claim already on the record

`results/RESULT_c3fix.md` speculated that a row-shape expectation "would
plausibly recover C13 and C8 both." **Working it through before building shows
that is wrong, and only C13 is recoverable this way.**

```text
C13  footnote      Tuote cell "Huom: sisältää palautukset"  -> non-blank ✓
                   Tammi/Helmi/Maalis                        -> BLANK    ✗
                   fails a shape rule                        -> caught

C8   subtotal      Tuote cell "VÄLISUMMA"                    -> non-blank ✓
                   17 / 21 / 19                              -> numeric  ✓
                   passes every shape rule                   -> NOT caught
```

A subtotal row has exactly the shape of a data row. It differs only in what the
label *means*, and meaning is what a structural predicate cannot reach. The
speculation was optimistic; the corrected prediction is frozen below.

This matters beyond bookkeeping: it is the point where the security claim stops.

## v1.2 (FROZEN)

One optional key per data-sheet entry:

```json
"data_row_shape": {
  "require_non_blank": ["sheet:Sales!@Tuote"],
  "require_numeric":   ["sheet:Sales!B:D"]
}
```

Every row in the data region must satisfy every constraint. A row that does not
raises `row_shape_violation`, which the front door treats as a coverage problem
→ `REDEFINE_SCOPED`.

**Closed enum: `require_non_blank`, `require_numeric`.** Both are *type-level*
predicates — they ask what **kind** of value sits in a cell, never what it says.
No patterns, no regex, no value lists. That is the same boundary that kept
transforms an enum and `label_in` literal: a predicate language over untrusted
cell content is an expression language arriving through the back door.

`require_numeric` reuses the frozen `is_number` from macro v2 (Experiment J).

### What this costs, and it is not nothing

v1.2 makes the **validator read data-row content**, where v1/v1.1 read only
structure plus the header row. The untrusted-input surface grows from "shape and
headers" to "shape, headers, and the type of every cell in the data region."

It is bounded deliberately: the validator learns only *blank / numeric / neither*
per cell. It never branches on what a cell says. A compromised or malicious
workbook can therefore make rows fail the shape check — causing an **escalation
to a human** — and nothing else. Escalation is the safe direction, so the
widened surface buys detection without buying authority.

## Predicted outcomes (FROZEN)

| ID | truth | v1 | v1.1 | **v1.2 predicted** |
| --- | --- | --- | --- | --- |
| C1 | `EXECUTE` | `EXECUTE` | `EXECUTE` | `EXECUTE` |
| C2 | `EXECUTE` | `EXECUTE` | `EXECUTE` | `EXECUTE` |
| C3 | `EXECUTE` | `REDEFINE_SCOPED` ✗ | `EXECUTE` | `EXECUTE` — fix preserved |
| C4 | `REDEFINE_SCOPED` | ✓ | ✓ | `REDEFINE_SCOPED` |
| C5 | `REDEFINE_SCOPED` | ✓ | ✓ | `REDEFINE_SCOPED` |
| C6 | `REDEFINE_SCOPED` | ✓ | ✓ | `REDEFINE_SCOPED` |
| C7 | `DEFINE` | ✓ | ✓ | `DEFINE` |
| C8 | `REDEFINE_SCOPED` | `EXECUTE` ✗ | `EXECUTE` ✗ | **`EXECUTE` ✗ — still** |
| C9 | `DEFINE` | ✓ | ✓ | `DEFINE` |
| C10 | `AMBIGUOUS` | ✓ | ✓ | `AMBIGUOUS` |
| C11 | `BLOCKED` | ✓ | ✓ | `BLOCKED` |
| C12 | `BLOCKED` | ✓ | ✓ | `BLOCKED` |
| C13 | `REDEFINE_SCOPED` | ✓ | `EXECUTE` ✗ | **`REDEFINE_SCOPED` ✓ — recovered** |

```text
predicted   v1    11/13   over_escalation {C3}   false_execute {C8}
            v1.1  11/13   over_escalation {}     false_execute {C8, C13}
            v1.2  12/13   over_escalation {}     false_execute {C8}
```

**v1.2 is predicted to be the first format that is unambiguously better**: it
keeps the C3 fix and pays back the C13 cost, leaving exactly one failure — and
that one is semantic, not structural.

C5 note: v1.2 may flag C5 through *either* `column_unclassified` (as before) or
`row_shape_violation` (the shifted `B:D` now includes `Maa`, whose values are
`FI`). The dispatch is `REDEFINE_SCOPED` either way; the delta may name both.

## Decision table

| Condition | Outcome |
| --- | --- |
| every v1.2 cell matches the prediction | **PASS_AS_PREDICTED** — the boundary is where the security claim says it is |
| C13 is not recovered | **FAIL_FIX** |
| C3 regresses from `EXECUTE` | **FAIL_REGRESSION** — the fix was traded away |
| **C8 is caught** | **RESULT_BETTER_THAN_PREDICTED** — investigate *why* before celebrating; a structural rule catching a semantic difference means the fixture, not the rule, is doing the work |
| a false EXECUTE appears outside `{C8}` | **FAIL_UNSAFE** — record, do not tune |
| any v1/v1.1 cell differs from its recorded result | **VOID** |

The C8 row is the interesting one. If a shape rule catches a row that is
shape-identical to a data row, the rule is not doing what it claims and the
result must be explained, not banked.

## Hard stop

No LLM. No changes to the frozen referent grammar, to K's or the replay's
recorded results, or to any frozen fixture. **No patterns, regex or value lists
in `data_row_shape`** — if C8 is ever to be caught it needs a different kind of
evidence, and that is a separate question.

## Standing traps

- **Do not add a pattern to catch C8.** The refusal is the security boundary,
  not laziness.
- **v1.2 reads data content.** Keep it to blank/numeric. Any check that branches
  on what a cell *says* changes the threat model and needs its own freeze.
- Run `python scripts/verify_frozen.py` before and after; the fixtures here are
  frozen by K and by the replay.
