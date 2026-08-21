# W1-I disposition — tokenization line PARKED

Additive. Evidence `6ce7bd1`, closure `a32db47`. **No W1-I evidence, reporter
output or closure is changed by this record.**

## Preregistered conclusion, accepted

```text
tokenization primary measure   EXACT in all six U/V runs
                               padded 0, collapsed 0, other 0
the experiment                 did NOT discriminate r2 from r3
no evidence                    that r3 is unnecessary
no observed                    r3 over-normalization or regression
fidelity findings              secondary; they do not bear on tokenization
```

Both reporter defects — `CONSUMPTION_MARKERS` pinned to the W1-A fixture titles,
and `skill_match` pinned to the r2 hash — are **preserved as produced** in the
evidence, with corrections recorded additively in `CLOSURE.md` §3 and fixes
applied for future packs only.

## Line status

```text
tokenization line   PARKED / NON-DISCRIMINATING
r3                  RETAINED, frozen, no causal claim
issue B             PROMOTED to the next research line
```

**r3 is retained on its merits as a contract clarification**, not on evidence of
behavioural effect. It closes a real gap that causal analysis identified and
W1-G showed to be reachable. No further runs will be spent trying to make the
whitespace slip recur: the padding must stay ordinary to remain plausible, and
ordinary padding is what this worker already handles correctly.

## Why issue B takes over

`../census/confirmation_preservation/CENSUS.md` — read-only, 9 runs, W1-H and
W1-I only.

```text
row  settles              slot   not individually preserved
0    match key            YES    0/9
1    compare              YES    2/9
2    currency / tax band  NO     4/9
3    source of truth      NO     6/9
4    report fields        NO     6/9
5    context fields       NO     6/9

rows WITH a provenance slot      2 / 18 observations lost
rows WITHOUT a provenance slot  22 / 36 observations lost
```

The asymmetry is real and it is not noise. It survives across two packs and both
skill revisions.

## The census also found the reason not to build Surface C yet

**Order and provenance surface are perfectly confounded in this corpus.** The two
rows that carry a slot are also the first two rows delivered, and **6 of the 6
lossy runs lost a contiguous suffix**:

```text
P2  preserved 0..1, lost 2..5      V1  preserved 0..1, lost 2..5
U1  preserved 0..2, lost 3..5      V2  preserved 0..0, lost 1..5
U2  preserved 0..0, lost 1..5      V3  preserved 0..2, lost 3..5
```

Every lossy run. That is precisely what a truncation effect predicts, and the
provenance-slot reading predicts loss on slot-less rows *regardless of position*
— which this corpus cannot show, because no slot-less row is ever delivered
early.

```text
A  loss concentrates where a decision has no place to cite authority
B  loss is a suffix effect: record the first few confirmations, then stop
```

Both readings fit the data equally well.

**Consequence for the proposed W1-J.** Adding `output.provenance` keys alone
cannot separate A from B. If preservation improves, it may be the new slot — or
it may be that those rows moved earlier in whatever the worker truncates. The
one-variable discipline is right, but the variable has to be chosen so the
result is interpretable.

The cheapest way to make it interpretable is to **vary the delivery order of the
canonical rows independently of which rows carry a slot** — for instance, a
control arm that delivers rows 4 and 5 first, with no schema change at all. If
loss follows position, it is B and the schema change is not the lever. If loss
follows the slot-less rows wherever they appear, it is A, and Surface C is
exactly right.

That is a design question for the next roundtable, not a decision to take here.
No fix is proposed, and the schema is unchanged.

## Not done here

- No model execution.
- No change to r2, r3, the validator, the fidelity instrument, the capability
  box, the policy, or any pack's evidence.
- No efficacy claim for r3, and no statistical inference from 9 census runs.
