# W1-H — accepted

Additive. Evidence `9c078c2`, closure `b6b79ae`. **No W1-H evidence, reporter
output or closure is changed by this record.** W1-H is closed.

## Accepted findings

```text
RESOURCE DISCOVERY      3/3   accepted
RESOURCE CONSUMPTION    3/3   accepted
ARTIFACT PRODUCTION     3/3   accepted
AUTHORITY               3/3   CLEAN, accepted
STRUCTURAL              3/3   PASS, accepted
FIDELITY                2/3   PASS, MEASURED, accepted
```

P2's two `FID-5 UNRECORDED_HUMAN_ANSWER` findings are accepted as a **genuine
fidelity-preservation finding, separate from tokenization.**

The fidelity layer did the job it was built for: it caught P2 while STRUCTURAL
stayed 3/3. A structurally valid Work Definition silently lost the provenance of
four of six settled decisions, and only the independent layer could see it.

## State of the line

```text
capability box      established
transport           established
authority           established
structural          independently measurable
fidelity            independently measurable

remaining known producer issues
A.  header token boundary                 -> W1-I
B.  preservation of all supplied confirmations  -> its own later line
```

**A and B are separate experiments.** B is close to the inverse of A: r2 already
says "record each answer verbatim", yet the worker sometimes treats
`human_confirmations` as a selective audit log rather than a complete record.
That is a different failure than an unstated tokenization rule, and it is not to
be addressed by adding another sentence to r3.

## Explicitly not done here

- r2 is not modified.
- r3 does not address P2.
- No W1-H run is repeated, repaired or rescued.
- W1-H's `2/3` is not converted into a rate, and does not pool with W1-G's
  recomputed `3/3` — the transport differs between them.
