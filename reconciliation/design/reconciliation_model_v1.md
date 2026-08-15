# Reconciliation Model — v1

The fourth task shape, chosen for one reason above the others: **it has no
numeric semantics at all**, so it declares no `on_non_numeric` policy and had no
reason to.

## Why that matters

Enrichment and aggregation each carry an `on_non_numeric` policy, and the
suspicion was that this might be common structure belonging in the shared
envelope — or merely a family resemblance between tasks written by one hand in
one week. A shape with no reason to need one is the independent evidence.

**The tally is not what was assumed.** Counting rather than remembering:

```text
reservation      NO on_non_numeric   -- handles a malformed value as a RULE in
                                        its ordered list (date_well_formed ->
                                        INVALID_DATE), not as a policy field
enrichment       has on_non_numeric
aggregation      has on_non_numeric
reconciliation   NO on_non_numeric   -- no numeric semantics at all
```

Two of four, not three. And the split is sharper than a 3-of-1 would have been:
**the policy appears exactly where numeric coercion happens and nowhere else.**
It tracks a property of the task's DATA, not of task-hood, so it does not belong
in the envelope. The absence here is asserted by the run
(`no_non_numeric_policy`) rather than left to be noticed.

## The shape

```text
reservation      sequential predicates over ONE value
enrichment       one-sided lookup: a driving source and a REFERENCE
aggregation      many rows -> one grouped row
reconciliation   two PEER sources -> classify the UNION by relationship
```

Enrichment has a subordinate side: the reference table is consulted, never
iterated. **Here neither source is subordinate.** An output row can originate
from either side, and that is the whole difficulty.

## The task

```text
expected: alice, bob, carol        actual: alice, carol, dave

alice   BOTH
bob     ONLY_EXPECTED
carol   BOTH
dave    ONLY_ACTUAL
```

## The two foils

Both are plausible wrong answers with nothing visibly wrong about them, computed
from the fixtures and required to differ from the real output:

```text
left_join_foil      alice BOTH, bob ONLY_EXPECTED, carol BOTH
                    -- what an implementation that walked the LEFT side and
                    looked up the right would emit. `dave` simply vanishes.
intersection_foil   alice BOTH, carol BOTH
                    -- keeping only matching keys. `bob` AND `dave` vanish:
                    the two rows a reconciliation exists to surface.
```

## Declarations, and the permutations that prove they are followed

```text
match_on        user_id -> email repartitions the union entirely. The fixtures
                are built so the two keys DISAGREE: carol matches by id but not
                email, dave matches bob by email but not id. Identical
                partitions would make the permutation a no-op.
classify        the output labels are the model's words. Renaming `only_right`
                must change what dave's row says.
output_order    the union of two sources has no natural order, so it is
                declared. `left_then_right` or `sorted_by_key`, with a fixture
                (zoe before alice) where the two genuinely differ.
```

## Duplicate keys — declared, never invented

A key appearing twice on one side has no single right answer:

```text
refuse_run   the whole reconciliation refuses
refuse_key   that key is excluded and LISTED as refused; the rest proceeds
```

`deduplicate` and `separate_records` are **deliberately absent**. Both silently
change what the data says, and following the enrichment precedent, a policy that
quietly discards or multiplies rows must be a NAMED policy with its own evidence
before it exists.

## A row with no match key

Refused, with no policy offered. It cannot be classified by a key it does not
carry, and filing it under the empty string would pool every keyless row into one
phantom key and classify it as though it were real.

## What this model cannot say

Recorded because it is the most likely thing to be mistaken for a bug:
**`carol`'s email differs between the two sources and this model has no way to
express that.** It classifies by key presence only, so carol is `BOTH`.
Comparing non-key ATTRIBUTES is a different question and would need its own
declaration.

Also absent: composite match keys, fuzzy or normalised matching, three-way
reconciliation. Three users a side, string keys only. This says the shape works,
not that the model is complete.
