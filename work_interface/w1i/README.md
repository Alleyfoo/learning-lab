# W1-I — token-boundary differential (r2 vs r3)

**Frozen. Not executed.** See `PREREGISTRATION.md` for the full design, the
preregistered primary measure, and the reporting rule.

```text
Arm U (control)    Qwen3.5:9b + skill r2 + fixture T    U1 U2 U3
Arm V (treatment)  Qwen3.5:9b + skill r3 + fixture T    V1 V2 V3
```

The only arm-level variable is the skill revision. Everything else — model,
capability box, UTF-8 transport, lifecycle, authority policy, validator family,
frozen fidelity instrument, fixture pair, canonical block, prompt text — is
identical.

## Why differential

Running three more copies of the W1-G fixture would tell us almost nothing: that
slip was 1-in-3, sporadic, and did not recur in W1-H with no amendment at all.

This pack asks instead: **does explicitly defining delimiter syntax change how
the worker represents header tokens under the same deliberately
boundary-sensitive input?**

## Fixture T

```text
vendor-charge-summary.txt   Header: Charge Period, Client Ref, Net Value, Tax Band, Settlement State
internal-charge-ledger.txt  Header: Charge Period, Internal Key, Client Ref, Net Value, Settlement State, Remarks
```

Every token but `Remarks` carries a significant internal space, so "discard the
padding" and "remove the spaces" are distinguishable outcomes. Neither r2 nor r3
names any of these tokens, so neither arm is handed the canonical spelling by its
own skill text. The padding is the ordinary `, ` of the existing fixtures — the
fixture is a plausible member of its input class, not an adversarial one.

## Primary measure

`tokenization_report.py`, independent of the structural verdict:

```text
EXACT      == canonical                      'Client Ref'
PADDED     separator whitespace retained     ' Client Ref'
COLLAPSED  internal whitespace altered       'ClientRef'
OTHER      renamed, merged, or absent
```

Overall structural PASS is explicitly **not** the tokenization measure.

## Verification

`verify_prep.py` passes **19 checks**, including:

```text
check 2   each arm pinned to its own revision; r2 unchanged by the promotion
check 4   fixture T is boundary-sensitive, and NEITHER revision names any of
          its canonical tokens
check 18  the corrected UTF-8 transport
check 19  arm symmetry, and that the tokenization measure never consults the
          structural verdict
```

## Discipline

N = 3 per arm, fixed. Report the six runs descriptively; do not convert 3+3 into
a reliability estimate, and do not claim r3 "solves" the behaviour. If both arms
come back clean, the honest conclusion is that this fixture did not
discriminate — not that r3 is unnecessary.

W1-H P2's dropped-confirmation behaviour stays visible through the frozen
fidelity gate as a **secondary observation only**. It is a separate
producer-contract problem, r3 does not address it, and it must not be used to
judge the token-boundary hypothesis.
