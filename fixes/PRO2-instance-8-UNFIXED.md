# PRO-2 instance 8 — found by grammar-derived generation. **NOT FIXED.**

**Status: frozen unfixed, deliberately.** The designer's instruction, and the
right one: *if this run finds an eighth instance, don't immediately fix it before
freezing the result.* The chronology is the scientific content here, and a fix
committed in the same breath would blur what was known when.

## The defect

A declared `unpivot` transform on a field whose role is **not**
`period_measure` is accepted by the validator and **silently discarded** by the
executor. The declared `var_target` column never appears in the output.

```text
DECLARED
  {"target": "tuote", "source": "sheet:S!@Tuote", "role": "id", "type": "string",
   "transform": {"op": "unpivot", "var_target": "kuukausi", "value_target": "tuote"}}

validator : valid=True   codes=[]
executor  : columns=['tuote']   rows=[['E1'], ['E2']]
            declared var_target 'kuukausi' present? False
```

Same family, same shape as every predecessor: **the format permits a combination
one layer honours and another ignores, and nothing compares the two.** The
executor branches on `role == "period_measure"` to apply an unpivot; for any
other role the transform is read and dropped.

It reaches **seven** distinct combinations in the enumeration — `id`, `measure`
and `metadata` roles, across `namedcol`, `col`, `colrange` and `cell` sources.

## Why this one matters more than "an eighth bug"

The point is not the count. It is **which method found it**, and when.

```text
author-written property generation   720 cases, 5 seeds   -> 0 novel defects
                                     (frozen at b84f902, BEFORE this existed)
grammar-derived generation           606 combinations     -> 1 novel defect,
                                                             on first application
```

The baseline was frozen *before* the grammar generator was written, precisely so
this comparison could be made honestly. That ordering is the whole point: it
distinguishes a method result from a lucky find.

And the reason is the one predicted in advance: an author-written generator
explores *the shapes its author believes matter*. **Nobody would sit down and
write a test for an `id` field carrying an unpivot transform** — it is not a
sensible thing to write. The language permits it anyway, and a generator
traversing `role × transform` mechanically has no sense of what is sensible.

That is the same reason the seventh instance (the unexecutable sheetset) was
missed: it was a *valid structure nobody had forced through the whole machine*.

## The finding is independent of this generator's own defect

Worth stating plainly, because it would be easy to overclaim.

The grammar run also produced **177 disagreements between my oracle and the
system, and all 177 are my oracle being wrong.** Every one has
`sheet_role=ignore`, where the generator degenerates: it strips the sheet entry
down to `{sheet, role, reason}` and discards the fields, while the oracle
continues to evaluate field-pairing rules for a field the recipe no longer
contains. **Zero disagreements occur on `data` sheets.**

So the agreement figure (429/606) is not a clean measure of anything, and is not
reported as one. The generator needs that degenerate case fixed before its
oracle-vs-system comparison means much.

**The eighth instance does not depend on any of that.** It was found by
`no_partial_honour`, which is oracle-independent — it compares declared targets
against output columns and never consults my model of the language. The universal
property survived my modelling error, which is an argument for having a universal
property that does not route through the author's understanding.

## What must NOT be concluded

- Not *"grammar-derived generation is better."* One comparison, one defect, one
  codebase.
- Not *"the author-written suite is inadequate."* It has a canary proving it can
  detect the class; it simply generates from a different distribution.
- Not *"No Partial Honour is now established."* This is a **counterexample** to
  it. The claim was already `guarded`; it stays there, now with an instance
  showing the guard was right to be provisional.

## The ladder, extended

```text
Does it exist?                         format enums
Does every layer recognise it?         executor contract  (instances 2,3,4)
Do the layers mean the same thing?     semantic parity    (instance 7)
Does that meaning survive variation?   property suite     (0 new)
How much of the domain did we vary?    grammar-derived    (instance 8)
```

Each rung was forced by the rung below turning out not to be enough. This run
extends that pattern by one, and the next question is the same one as before:
*how much of the domain did we vary over?* Grammar-derived enumeration covers the
composition axes; it does not cover value domains, multiplicities beyond two, or
interactions across sheets.

## When it is fixed

The fix belongs in the executor contract, not in the executor: a transform is
only meaningful for certain field roles, and that pairing should be declared and
enforced the way every other pairing now is. A parity invariant should follow it:

> a declared transform is either honoured for the role it is attached to, or the
> recipe is refused.

That work is **not started**, so that this record describes only what was known
at the time it was written.
