# PRO-2 instance 10 — found by cross-sheet law 1. **NOT FIXED.**

**Status: frozen unfixed**, per the discipline used for instances 8 and 9.

## The defect

One origin, reached through two referent spellings, contributes twice.

```text
workbook:  a single sheet named "Sales"
recipe:    entry 1 -> sheet:Sales
           entry 2 -> sheet:SALES     (the same sheet; lookup is case-folded)

baseline (entry 1 only)   2 rows   [['A', 1], ['B', 2]]
mutated  (both entries)   4 rows   [['A', 1], ['B', 2], ['A', 1], ['B', 2]]
```

The baseline output is repeated **verbatim**. This is exactly the `O + O` that
No Undeclared Duplicate Contribution forbids:

> A source atom may affect authoritative output through each explicitly
> authorised semantic relationship, but reaching the same atom through an
> additional undeclared/aliasing path must not silently duplicate its effect.

Neither branch of the permitted outcomes happened: validation did not refuse the
ambiguous relationship, and the two paths were not recognised as aliases.

## Why the existing guard missed it

`column_double_bound` **is** origin-based — the claim map is keyed by resolved
`col0`, not by referent text — and it correctly refuses the within-sheet
aliasing case (`@Tuote` vs `A:A`, also in this corpus). But the coverage map is
built **per sheet entry**, so two entries naming one sheet each get their own
map and neither can see the other. Origin identity was already the right idea;
it simply had no scope wide enough to notice.

`WorkbookView.actual_sheet()` resolves case-insensitively, which is what makes
`sheet:Sales` and `sheet:SALES` one origin. That is a reasonable resolver
behaviour on its own — the defect is that nothing downstream reconciles two
declarations that land on it.

## A second, separate observation

The mutated output's columns are `['tuote', 'myynti']` — the *first* entry's
targets. The second entry declared `tuote_b` / `myynti_b`, and its rows were
appended under the first entry's column names instead. So the duplication is not
merely "the same data twice": rows from one declaration are emitted under a
different declaration's schema.

That is arguably a distinct defect (`out.columns` is set once, from whichever
entry is first) and is recorded here rather than merged into instance 10,
because fixing the aliasing would leave it untouched.

## What made the case evidential

Run 1 reported *"law held"* and two thirds of it was worthless: both entries
declared the same field **target** names, so validation refused with
`duplicate_target` — a name collision — and the aliasing question was never
adjudicated. Identical failure mode to the sheetset axis in multiplicity run 1.

```text
run 1   refused: duplicate_target      correct refusal, WRONG REASON, no evidence
run 2   4 rows where 2 were declared   the intended question, actually asked
```

Run 1 is preserved unrepaired. The repair was to give the second entry distinct
target names — a **valid representation of the question**, which is the same
repair the sheetset generator needed.

## Reachability was checked before the result was believed

`assert_same_origin()` confirmed both paths resolve to the same `SourceAtom`
before any verdict was computed:

```text
sheet:Sales!A1 -> Sales[0:0,0:0] | sheet:SALES!A1 -> Sales[0:0,0:0]
```

Without that, a run can spend hours proving that a second path pointed at a
copied sheet.

## Source identity is origin, never content

The corpus carries a control in the other direction: two sheets (`Jan`, `Feb`)
holding byte-identical data, which are **two** sources and must both contribute.
The law correctly did not fire on them.

In run 2 that control was itself non-evidential — its baseline refused with
`sheet_unclassified` because the second sheet was not declared — so it did not
yet demonstrate what it was built to demonstrate. Repaired for run 3; this
record describes only what was known when it was written.

## When it is fixed

The fix is a recipe-level reconciliation over resolved origins, not a string
comparison over referents — the same lesson as `column_double_bound`, applied at
a wider scope. Either:

```text
refuse    two declarations resolving to the same sheet origin, unless the
          language explicitly authorises the relationship
or        recognise them as aliases and contribute once
```

Not started.
