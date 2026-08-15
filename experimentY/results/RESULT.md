# Experiment Y — RESULT: selective autonomy, 9/9

Frozen at `1f8cb3b`, on the observer floor frozen separately at `eb3a036`.
Three conditions, three probes each, no retries.

```text
probe        Y1     Y2     Y3     Y4     Y5      key    line totals
A_probe1     pass   pass   pass   pass    -      sku    3.00, 14.00, 10.00
A_probe2     pass   pass   pass   pass    -      sku    3.00, 14.00, 10.00
A_probe3     pass   pass   pass   pass    -      sku    3.00, 14.00, 10.00
B_probe1     pass   pass   pass   pass    -      code   3.00, 14.00, 10.00
B_probe2     pass   pass   pass   pass    -      code   3.00, 14.00, 10.00
B_probe3     pass   pass   pass   pass    -      code   3.00, 14.00, 10.00
C_probe1     pass   pass   pass    -     pass    sku    3.00, 14.00, 10.00
C_probe2     pass   pass   pass    -     pass    sku    3.00, 14.00, 10.00
C_probe3     pass   pass   pass    -     pass    sku    3.00, 14.00, 10.00
```

Every model executed to its condition's oracle, with zero refusals.

## The binding moved with the evidence, not the name

This is the result Y was built to get, and B is the load-bearing half. A and B
are mirrors — identical field names, identical purpose, coverage swapped — so a
system that follows the name passes A and fails B.

```text
A   sku 3/3, code 2/3   ->  chose sku    3/3
B   sku 2/3, code 3/3   ->  chose code   3/3
```

B's inspector did the interesting thing unaided: it inferred the binding **and**
kept the residual as an addressed unknown, without blocking on it.

```json
{"claim": {"source": "orders", "field": "item",
           "meaning": "A foreign key referencing products.code, identifying the
                       product being ordered."},
 "status": "INFERRED", "basis": ["field_name", "cross_source_similarity",
                                 "value_examples"]}

{"claim": {"source": ["orders", "products"], "field": "item",
           "question": "Whether orders.item could also correspond to
                        products.sku, given the partial overlap in values."},
 "status": "UNKNOWN",
 "note": "While orders.item has full coverage in products.code, it only has 2/3
          coverage in products.sku. It is unclear if this overlap is incidental
          or represents a secondary reference."}
```

An honest residual that does not stop the job is exactly the behaviour a usable
system needs, and it is the thing V's floating unknowns could not express.

## C blocked, and asked the right question

```json
{"source": ["orders", "products"], "field": "item",
 "binding": "which field in products (code or sku) the orders.item foreign key
             joins to",
 "claim_status": "UNKNOWN",
 "question": "Which field in 'products' is the intended target of the
              'orders.item' foreign key?"}
```

3/3 blocked, 3/3 resumed to the oracle after one human answer. And C is the
condition where blocking is the only protection:

```text
A   wrong key   refuses a row     the mistake announces itself
B   wrong key   refuses a row     the mistake announces itself
C   wrong key   runs CLEAN        3 rows, 0 refusals, wrong money
```

Incomplete coverage is self-announcing; complete coverage on two candidates is
not. That is why complete coverage is the discriminator rather than an arbitrary
threshold.

## Y-4: it did not ask when it did not need to

Six probes across A and B, **zero** requests to confirm the join binding. The
failure this rules out is the one that would make the mechanism useless in
practice: a system safe enough to stop on everything is a system that gets
switched off.

## What the branch now establishes

```text
W   unsupported semantic binding    -> blocks           3/3
X   unsupported relational binding  -> blocks           3/3
X   missing observation             -> blocks           3/3
Y   sufficient relational evidence  -> proceeds         6/6
Y   insufficient evidence           -> blocks, resumes  3/3
```

> **Authority proceeds when the declared local evidence is sufficient, and stops
> when it is not.**

That is stronger than "the system is cautious", and it is the property these
nodes actually need. Per the decision rules, the provenance branch stops here.

## On the instrument

X's observer defect was repaired and frozen **before** this experiment, on its
own commit with its own self-test, so a repaired instrument is not reported
alongside the results it enables. The observer now emits `value_kind` covering
integer and decimal strings alike, plus `candidate_relationship` measurements —
and is canaried against ever emitting a join, a meaning or an intention.

X probe 2's second block is corrected in interpretation without rewriting its
frozen score: it resolved the join, found another load-bearing uncertainty, and
blocked again. Not a chain failure — another instance of *confirmation resolves
claims, not workflows*.

## Stated limitation

One job, three conditions, three probes each, three rows, two candidate keys,
`glm-5.2`, no seed control. The sufficiency rule is deliberately crude — sole
candidate, complete coverage, unique keys — and real data will present cases it
does not settle: two partial candidates, a unique key at 99% coverage, a
composite key. Y shows a **stated** policy being applied to **measured** facts.
It does not show that this policy is the right one for production, and the
9/9 says nothing about how the system behaves where the policy is silent.

A job whose correct rule ORDER is unconventional remains untested and is still
the sharpest open limit on R2.
