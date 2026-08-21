# Confirmation-preservation census

**Read-only.** Built from frozen artifacts and the frozen fidelity instrument. No pack was modified.

## Corpus

```text
W1-H  P1 P2 P3           corrected UTF-8 transport
W1-I  U1 U2 U3 V1 V2 V3  corrected UTF-8 transport

EXCLUDED
W1-G       transport known invalid (cp1252 double-encoding voided its fidelity layer)
W1-A..W1-F no capability box and no valid measured fidelity
```

## Provenance surface per row (read from the v0 schema)

| row | settles | provenance slot | where |
|---|---|---|---|
| 0 | match key | **YES** | body.match_on.basis + .confirmation |
| 1 | compare | **YES** | body.compare[].basis + .confirmation |
| 2 | currency / tax band | **NO** | an exclusion: the decision's effect is a field's ABSENCE from compare[], and an absence cannot carry a basis |
| 3 | source of truth | **NO** | no source-of-truth/peer key exists in the v0 shape |
| 4 | report fields | **NO** | output.reports_fields has no provenance keys |
| 5 | context fields | **NO** | output.context_fields has no provenance keys |

## Per-run classification

| pack | run | rev | row 0 | row 1 | row 2 | row 3 | row 4 | row 5 |
|---|---|---|---|---|---|---|---|---|
| W1-H | P1 | r2 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL |
| W1-H | P2 | r2 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | ABSENT | ABSENT | ABSENT | ABSENT |
| W1-H | P3 | r2 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL |
| W1-I | U1 | r2 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | ABSENT | ABSENT | ABSENT |
| W1-I | U2 | r2 | EXACT_INDIVIDUAL | NONVERBATIM | ABSENT | ABSENT | BUNDLED | BUNDLED |
| W1-I | U3 | r2 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL |
| W1-I | V1 | r3 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | ABSENT | ABSENT | ABSENT | ABSENT |
| W1-I | V2 | r3 | EXACT_INDIVIDUAL | BUNDLED | BUNDLED | BUNDLED | BUNDLED | BUNDLED |
| W1-I | V3 | r3 | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | EXACT_INDIVIDUAL | ABSENT | ABSENT | ABSENT |

## Per-row tallies

| row | provenance slot | EXACT_INDIVIDUAL | BUNDLED | NONVERBATIM | ABSENT | not individually preserved |
|---|---|---|---|---|---|---|
| 0 (match key) | YES | 9 | 0 | 0 | 0 | **0/9** |
| 1 (compare) | YES | 7 | 1 | 1 | 0 | **2/9** |
| 2 (currency / tax band) | NO | 5 | 1 | 0 | 3 | **4/9** |
| 3 (source of truth) | NO | 3 | 1 | 0 | 5 | **6/9** |
| 4 (report fields) | NO | 3 | 2 | 0 | 4 | **6/9** |
| 5 (context fields) | NO | 3 | 2 | 0 | 4 | **6/9** |

## Concentration

```text
rows WITH a provenance slot     [0, 1]
  not individually preserved    2 / 18 observations
rows WITHOUT a provenance slot  [2, 3, 4, 5]
  not individually preserved    22 / 36 observations
```

**Descriptive only.** This is a census of 9 runs, not a statistical test. No causal claim is drawn from it, and the concentration above is reported as an observation about where loss occurs, not as evidence of why.

## CONFOUND — order and provenance surface are not separable here

In this corpus the two rows that have a provenance slot are also **the first two rows delivered**. "Has a slot" and "comes early" are therefore perfectly confounded, and the concentration above supports two readings equally well:

```text
A  loss concentrates on rows whose decisions have no place to cite authority
B  loss is a suffix effect: the worker records the first few confirmations and stops
```

6 of the 6 lossy runs lost a **contiguous suffix** of the delivered rows:

```text
P2   preserved rows 0..1, lost 2..5
U1   preserved rows 0..2, lost 3..5
U2   preserved rows 0..0, lost 1..5
V1   preserved rows 0..1, lost 2..5
V2   preserved rows 0..0, lost 1..5
V3   preserved rows 0..2, lost 3..5
```

That is what reading B predicts. Reading A predicts loss on the slot-less rows **regardless of their position**, which this corpus cannot show because no slot-less row is ever delivered early.

**Design consequence.** An experiment that only adds provenance keys to `output` cannot separate A from B: if preservation improves, it may be the new slot, or it may be that the rows moved earlier in whatever the worker is truncating. Separating them needs the delivery ORDER of the canonical rows varied independently of which rows carry a slot.
