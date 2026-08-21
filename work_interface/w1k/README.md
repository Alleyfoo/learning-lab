# W1-K — Surface C provenance-affordance differential

**Frozen. Not executed.** Full design, ladder and interpretation branches in
`PREREGISTRATION.md`.

> **One arm-level variable: the output provenance surface.**

```text
Arm A — control    Qwen3.5:9b + r2  + v0     canonical order 0->5   A1 A2 A3
Arm B — treatment  Qwen3.5:9b + r2c + v0+C   canonical order 0->5   B1 B2 B3
```

A **fresh paired control**, not another cross-pack comparison — the behaviour is
too sporadic now for W1-H to serve as the baseline.

## The question

W1-J ruled out `delivery position → preservation`. It did not establish
`provenance slot → preservation`, because row 1 has a slot and lost its identity
in 3 of 3 reversed runs. So:

> Under the stable canonical order, does adding the same provenance affordance
> to rows 4/5 change their evidence preservation, without broadly changing the
> other rows?

## Within-artifact controls

```text
row 0  match key        existing slot   POSITIVE CONTROL
row 1  compare          existing slot   POSITIVE CONTROL   <- live after W1-J
row 2  currency         no slot         NEGATIVE CONTROL
row 3  source of truth  no slot         NEGATIVE CONTROL
row 4  report fields    NEW slot in B   TARGET
row 5  context fields   NEW slot in B   TARGET
```

## Primary measure — a ladder, not a pass rate

```text
slot offered -> slot populated -> confirmation exists
             -> individually attributable -> byte-exact
             -> slot points to that confirmation
```

`binding valid` requires both that the cited id exists **and** that the
confirmation it names actually carries that canonical row. A citation pointing
at the wrong confirmation is not provenance.

## The treatment, precisely

`r2c` = r2 + the `output.provenance` shape + one evidence bullet requiring it.
`v0+C` = v0 + five named codes enforcing it. Both are new immutable revisions;
r2, r3 and v0 are byte-unchanged.

The slots are **required**, mirroring `match_on` and `compare[]`, which do not
offer an optional basis. An optional slot would test whether the worker
*volunteers* provenance — a weaker and less interpretable question.

Arm A is graded against v0 and arm B against v0+C: each arm by its own contract.

**No reminder prose.** Check 19 asserts the added lines contain none of "all
six", "every answer", "one answer per", "make sure", "be sure to", "remember
to", "do not omit" — and that r2c carries no r3 text.

## Verification

`verify_prep.py` passes **19 checks**, including per-arm revision pinning, the
byte-unchanged frozen v0, arm prompt symmetry, the declared control roles, and a
live probe that the ladder resolves correctly on a real v0 artifact (row 0's
slot binds; row 4 has none).

## Discipline

N = 3 per arm, fixed. No percentages or reliability estimates; no pooling with
W1-H, W1-I or W1-J. **The tokenization line stays parked** — Q3's systematic
padding is not addressed here, and r3 is deliberately absent from both arms.

A refusal in arm B caused by the *new* codes is a producer-interface finding,
not a preservation finding.
