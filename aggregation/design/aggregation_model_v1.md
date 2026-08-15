# Aggregation Model — v1

The third modelled/executed task, and the first written **on** the shared floor
(`taskmodel/task_model.py`) rather than migrated onto it.

> Can GROUPING and AGGREGATION ACROSS ROWS be declared by the model and
> faithfully executed?

## Why this shape was chosen

The two earlier tasks decide each unit independently:

```text
reservation   one requested value  -> accept / refuse
enrichment    each row, against a reference table -> an enriched row
aggregation   MANY rows collapse into one, so a row's contribution lands in an
              accumulator shared with the other rows of its group
```

That last line is the point. **State across rows** makes a class of failure
available that neither earlier task could have, and the corpus is built around
it.

## The hazard that is new here

An accumulator serving every group instead of one per group. It produces totals
that are plausible, wrong, and the sum of everything:

```text
correct   South 2 rows 3.50   North 2 rows 0.30
leaked    South 4 rows 3.80   North 4 rows 3.80
```

Nothing about that output looks malformed. It is registered as a canary
(`shared_accumulator`), and if it stops firing the baseline has stopped being
evidence.

## Model shape

```json
{
  "driving_source": "sales",
  "group_by": ["region"],
  "group_order": "first_appearance",
  "aggregates": [
    {"target": "n_rows", "op": "count"},
    {"target": "total_quantity", "op": "sum", "field": "quantity"}
  ],
  "on_non_numeric": "refuse_row"
}
```

### Group ORDER is declared

`first_appearance` or `sorted_by_key`. Emitting groups in whatever order the
accumulator happened to fill is order-by-accident — cross-sheet law 4's subject,
and not acceptable even when it happens to look stable. The fixture puts `South`
before `North` deliberately so the two orderings **differ** and the declared
choice is observable; identical orderings would make the permutation a no-op.

### `op` and `field` are a PAIRING, not two enums

`sum` without a field has nothing to add; `count` with one implies a filter it
does not apply. Both directions are refused as `op_field_mismatch`. This is
PRO-2 instance 8 from the recipe line, where `id` and `unpivot` were each
supported and the pair meant nothing.

### A refused row forms no group

`on_non_numeric: refuse_row` removes the row **before** grouping, so a group
exists only if a surviving row contributed to it. The East row is refused and
named; no empty `East` group is invented. Every operand a row will contribute is
checked before any accumulator is touched, so a row cannot add to some totals and
then fail — partial honour inside a single row.

## Arithmetic

`Decimal`, as in the enrichment task, and for the same reason: `0.10 + 0.20` in
float is `0.30000000000000004`. The `float_sum` canary re-sums the same fixture in
float and requires the result to differ.

## Refusal vocabulary — closed

```text
NON_NUMERIC_OPERAND   a field being summed is not a number
```

Registered with the floor, so an executor emitting anything else raises.

## Fixtures

Five sale lines, one source. Row order is deliberate (South first). The East row
carries a non-numeric quantity on purpose.

## Multi-key grouping — tested (2026-08-15)

The format has always taken a *list* of keys while the corpus passed one, which
is the "declared wider than demonstrated" state PRO-2 instance 7 sat in before
semantic parity found it. `fixtures/sales_multikey.json` closes it, and is built
so that **grouping by the first key alone gives a plausible but wrong answer**:

```text
group_by [region, product]   South|A 1.50   South|B 2.00   North|A 3.00
group_by [region] alone      South   3.50                  North   3.00
```

The second table is what an executor silently using `keys[0]` would emit —
nothing about it looks malformed, South's A and B are simply conflated. Both are
run, and the check requires the multi-key result to match the first table AND to
differ from the second. That is what makes the pass evidence rather than a
coincidence.

## What remains absent on purpose

Three or more grouping keys (still expressible, still untested — though the
two-key case carried the discriminator), having/filter, ordering of rows within a
group, and `min`/`max`/`avg`. This says the shape works, not that the model is
complete.
