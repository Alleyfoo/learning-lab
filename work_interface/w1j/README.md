# W1-J — confirmation-order disposition

**Frozen. Not executed.** Full design, primary measure and interpretation
branches in `PREREGISTRATION.md`.

> **One intentional change relative to W1-H: the six canonical answers are
> delivered in reversed order.** Nothing else moves.

## Why

The census found loss concentrated on rows without a provenance slot — and
found that all six lossy runs lost a contiguous suffix. Those two rows are also
the first two delivered, so the readings are confounded:

```text
A  PROVENANCE-SURFACE   loss falls where a decision cannot cite authority
B  ORDER / TRUNCATION   record the first few confirmations, then stop
```

Reversing the order gives them sharply different predictions.

```text
delivered first  ->  last          slot
W1-H   0  1  2  3  4  5            YES YES NO NO NO NO
W1-J   5  4  3  2  1  0            NO  NO  NO NO YES YES
```

## Design

```text
CONTROL     W1-H P1/P2/P3   order 0->5   already executed
TREATMENT   W1-J Q1/Q2/Q3   order 5->0   three fresh runs
```

Same Qwen3.5:9b, **r2**, corrected UTF-8 capability server, same two verbs, same
lifecycle, same authority policy, same validator, same frozen fidelity checker,
same W1-A fixtures, same six answers from the same table at the same hash.

A **cross-pack differential**, not simultaneously randomized arms — stated
plainly rather than glossed. No second control arm is cut: W1-H already provides
one at the canonical order, and W1-I is excluded because it used different
fixtures.

## Primary measure

`preservation_report.py`. Overall FIDELITY PASS is **not** the result — it
collapses six independent observations into one bit.

```text
row   delivery_position   provenance_slot   preservation
```

plus `preserved_prefix_length` (0..6), counted from the start of delivery so it
compares across packs. Control values: P1 = 6, P2 = 2, P3 = 6.

The signal to watch: a run that preserves **5,4,3** then loses **2,1,0** has
changed *which* rows survive while keeping the prefix shape — direct evidence
for truncation, readable without any statistic.

## Verification

`verify_prep.py` passes **19 checks**, including check 19: the reversed block
has an identical part multiset to W1-H's — same 693 bytes, same six parts,
exactly reversed — so no answer text moved, only its position.

Check 11 was also made **structural** while building this pack. It located each
answer with `block.index()`, a substring scan; row 0's answer `InvoiceNumber`
also occurs inside row 4's answer, so reversing the order made it report a false
position. Same defect class that voided W1-D. It now compares whole delivered
parts.

## Discipline

N = 3, fixed. No percentages, no rates, no statistical inference, no pooling
with W1-I. Do not modify r2, r3, the schema, the validator or the fidelity
instrument.

**Surface C stays deferred** until this disposition is closed. Only then decide
whether `output.provenance` is the next lever.
