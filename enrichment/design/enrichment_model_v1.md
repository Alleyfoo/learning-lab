# Enrichment Model — v1

The second modelled/executed task, deliberately a **different shape** from the
reservation one. Reservation is a sequence of boolean rules over a single value
producing accept/refuse. This is a **join plus a computation** producing rows.

> Can a RELATIONSHIP and a COMPUTATION be declared by the model and faithfully
> executed?

Not a broadening of the reservation task, and nothing is borrowed from the frozen
authority path.

## The task

For each order line, look up its product by `product_id` in a reference table,
and emit an enriched row including `line_total = quantity × unit_price`.

## The two claims under test, and how each can fail

```text
RELATIONSHIP   the executor joins on the key the MODEL declares, and handles a
               missing or ambiguous match the way the MODEL declares --
               not the way its code happens to.

COMPUTATION    the executor computes what the model declares, on the operands
               the model names, and the arithmetic is FAITHFUL.
```

Both are tested by permuting the declaration and requiring the output to follow.
A run where declaration and implementation coincide proves nothing — that is the
blindness cross-sheet law 4 was VOID for.

## Numbers are strings in the fixtures, and that is not fussiness

A decimal written as a JSON float is already a binary approximation before any
executor sees it. `7 × 0.1` in float is `0.7000000000000001`.

For a task whose stated purpose is a *deterministic computed output*, silently
emitting `0.7000000000000001` for `0.70` is the same failure family as gap G2 —
a number that is wrong, looks fine, and nothing records it. So values arrive as
strings and arithmetic is `Decimal`. Order `O-2` (7 × 0.10) exists specifically
to make that observable, and a canary runs the same case in float to prove the
test can detect the unfaithful version.

## Model shape

```json
{
  "sources": {"orders": {...}, "products": {...}},
  "driving_source": "orders",
  "lookup": {
    "into": "products",
    "match_left": "product_id", "match_right": "product_id",
    "on_missing": "refuse_row", "on_ambiguous": "refuse_run"
  },
  "outputs": [
    {"target": "product_name", "from": "products", "field": "name"},
    {"target": "line_total", "compute": {"op": "multiply",
       "left":  {"from": "orders",   "field": "quantity"},
       "right": {"from": "products", "field": "unit_price"}}}
  ],
  "on_non_numeric": "refuse_row"
}
```

### Policies are DECLARED, never defaulted

```text
on_missing     refuse_row | refuse_run    key not present in the reference
on_ambiguous   refuse_row | refuse_run    key denotes MORE THAN ONE reference row
on_non_numeric refuse_row | refuse_run    an operand is not a number
```

There is deliberately no `emit_null` and no `skip`. A row that quietly disappears
or arrives half-filled is the partial-honour shape the cross-sheet work spent
five laws on; if it is ever wanted it must be added as a named policy with its
own evidence.

`on_ambiguous` exists because a key matching two reference rows has two different
right answers. Picking the first is authority by accident — cross-sheet law 5 by
another name, and here the two rows carry different prices so the choice is
worth money.

## Refusal vocabulary — closed

```text
MISSING_PRODUCT       the declared key matched no reference row
AMBIGUOUS_PRODUCT     the declared key matched more than one reference row
NON_NUMERIC_OPERAND   a compute operand is not a number
```

## Fixtures

Minimal and deliberate: three products, four orders. `O-3` names a product that
does not exist, `O-4` carries a non-numeric quantity, and
`products_ambiguous.json` duplicates `P-100` at a different price for the
ambiguity case alone.

Absent on purpose: multi-key joins, many-to-many, nested lookups, currency, units,
rounding policy, and any operation other than `multiply`. This asks whether the
shape works, not whether the model is complete.
