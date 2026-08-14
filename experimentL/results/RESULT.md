# Experiment L — Result: PASS_AS_PREDICTED

**A recipe does the job.** L1 12/12 rows, L2 18/18 rows, columns exact, order
exact, one gap — the one named before the run.

Deterministic. **No model was invoked.** Fully repeatable.

## L2 — the payoff claim, executed

The *same* recipe, approved against February's file, run against next month's
file with two extra products and the total row moved:

```text
paivitetty | tuote   | kuukausi | myynti
3.2.2026   | ART-001 | Tammi    | 10
3.2.2026   | ART-001 | Helmi    | 12
…
3.2.2026   | ART-006 | Tammi    |  4
3.2.2026   | ART-006 | Helmi    |  5
3.2.2026   | ART-006 | Maalis   |  3          18 rows
```

Absent, as frozen: the `YHTEENSÄ` grand-total row (wherever it moved to), the
`Yhteensä` derived total column, the `Kommentti` free-text column, and the three
preamble rows. The wide monthly block was unpivoted and the timestamp broadcast.

**Define once, run on next month's file, with no model in the loop.** That
sentence is now measured rather than asserted.

## The answer to the question

> *Does working only with the schema really work?*

**Yes, and here is exactly where it stops.**

The recipe carried everything the executor needed: which sheet, where the header
sits, which rows are data (via `remainder` plus a label rule that found the total
row at its new position), which column is the id, which columns are periods, what
to exclude and why, and what to broadcast. `FAIL_INSUFFICIENT` — the honest
negative answer, and the one this experiment was built to be able to give — did
not fire.

The executor also never needed to read outside the recipe. It reuses the
validator's own coverage map to decide what a data row is, so the checker and the
executor cannot disagree about that; and every cell it touched was named by a
referent.

## Gap G1 — the first thing the schema cannot say

```json
{"target": "paivitetty", "declared": "date", "gap": "G1",
 "reason": "the recipe format has no date format string or locale, so the
            declared type cannot be honoured without guessing"}
```

The recipe says `type: date`; the cell holds `3.2.2026`. The format has no way to
say **how** a date is written — no format string, no locale — so honouring the
declaration means guessing `dd.mm.yyyy` over `mm.dd.yyyy`. On 3 February that
guess is invisible; on 5 March it silently produces the wrong date.

The executor passed the value through unchanged and recorded the unhonoured
declaration. The expected table was frozen with the **raw string** precisely so
the table could match while the gap stayed visible — a pass that quietly ignored
the declared type would have hidden it.

**This is the shape of the real answer.** Working only with the schema works
until the schema cannot express something the job needs, and the useful
measurement is not "does it work" but *how many such points there are, and how
bad each one is*. G1 is one, it is small, and its fix is obvious (a declared
format string). What matters is that it was **found by executing**, not by
argument.

## What this establishes, and what it does not

**Establishes:** a recipe is sufficient to produce a correct table on the file it
was written for *and* on a later file of the same format, with no model at any
point; and the format's insufficiencies are detectable by execution rather than
by inspection.

**Does not establish:** that the format covers the space of real provider files.
One recipe, two workbooks, one sheet, one transform. The expressiveness question
— *how many shapes need something the closed enum lacks* — is a breadth
measurement and is not attempted here. Every such gap is also a security
question, because an escape hatch is exactly where an expression language comes
back.

## Limitations

- One recipe, two workbooks, a single data sheet and a single `unpivot`. The
  `sheetset`, `coerce` and multi-measure paths are unexercised.
- Row order is the recipe's field order and the sheet's row order. A different
  but equally correct ordering would fail this grading; the frozen table takes
  order as part of the contract.
- `type: number` was honoured on clean integers only; thousands separators and
  currency symbols are untested and would surface as unhonoured declarations
  rather than as wrong numbers.
- Deterministic and fully repeatable: no LLM, no seeds, no sampling.
