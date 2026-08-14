# PRO-2 instance 8 — found by grammar-derived generation

> **FIXED 2026-08-14, after this record was frozen.** The freeze below is unedited; the fix and its staged measurement are appended at the end. The file name keeps its `-UNFIXED` suffix because that is what it was called when the finding was recorded, and renaming it would quietly tidy the chronology this document exists to preserve.

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


---

# The fix, and the staged correction that followed

## Legal composition, not supported atoms

Instance 8 is the clearest argument yet that a supported *token* was never
enough. `unpivot` is supported. `id` is supported. **`id × unpivot` has no defined
meaning** — the language admitted a sentence the executor only understood half of.

So the contract now declares support per **pairing**:

```python
ROLE_TRANSFORM_PAIRS = {
    "id":             {None},
    "measure":        {None},
    "metadata":       {None},
    "period_measure": {"unpivot"},
    "derived":        {"derive"},
}
```

and enforces one rule:

> every declared transform must either be valid for the role it is attached to and
> be fully honoured, or validation must refuse the recipe

There is deliberately **no** "ignore a meaningless transform because it probably
wasn't intended" branch. That is exactly how partial honour sneaks back in.
`assert_contract_total()` now also fails if a supported role has no pairing
decision — the hole instance 8 came through.

## The frozen counterexample now refuses

```text
field role=id, transform=unpivot

before:  valid=True    executes         declared target 'kuukausi' missing
after:   valid=False   BLOCKED          executor not authoritative
```

## The class, not the specimen

A parity invariant covers **all 20 role × transform pairs**, not the seven
observed to fail:

```text
ok  composition:role_x_transform   all 20 role x transform pairs: honoured in
                                   full, or refused
```

## The staged correction — and why it was staged

Two changes were pending at once: a contract fix and an oracle correction.
Measuring between them keeps attribution possible.

```text
stage                                     disagreements   partial honour
A  run 1, before anything                      177              7
B  contract fixed, oracle untouched            191              0
C  oracle learns the pairing rule              191              0
D  oracle stops applying data rules to
   non-data entries (both sites)                 0              0
```

**Stage B is the load-bearing measurement.** Partial honour went 7 → 0, so the
fix works — and disagreements *rose* by 14, because the system began correctly
refusing pairings the oracle did not yet know were illegal. A rise is the
evidence that the oracle was not being tuned toward green.

**Stage C** fixed those 14 and the total held at 191, because the same
degeneracy widened by 14 on `ignore` sheets: the oracle now evaluated a pairing
rule against a field the recipe does not contain.

**Stage D** closed the degeneracy at both sites. The second was the sheetset
restriction: the contract places it on **data** entries, and the oracle applied
it unconditionally. An *ignored* sheetset is coherent — its members are covered
and never read — so the system was right and the oracle was wrong.

Both oracle corrections were modelled from the contract, not from the system's
behaviour. That distinction is the whole difference between correcting a model
and rewriting it until it agrees.

## What is deliberately NOT done

**Grammar coverage is not widened.** The same 606 combinations reproduce cleanly
first. Expanding now would change two things at once again, and the next result
would be unattributable.

## No Partial Honour stays guarded

It does **not** graduate because the counterexample is closed. If anything this
result argues harder for keeping it provisional: grammar-derived exploration
found exactly the sort of weird legal composition that hand-authored generation
missed. Its evidence is now:

> Guarded by validation and exercised by generated invariants; two historical
> counterexamples demonstrate the class remains reachable when composition rules
> are incomplete.

## The test layers, named

Instance 8 was found by the weakest-assumption layer, which is why it survived
the oracle being wrong in 177 places:

```text
rich oracle         understands intended language semantics
                    powerful, and vulnerable to author misunderstanding
metamorphic oracle  understands only expected change / invariance
                    narrower assumptions
primitive invariant compares a declaration against its observable consequence
                    weakest semantic assumptions -- "you declared this output
                    effect; did it exist?"
```

The bottom layer does not route through the author's understanding of the
language, and that is precisely why it kept working when the top layer did not.
