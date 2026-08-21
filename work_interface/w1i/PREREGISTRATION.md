# W1-I preregistration — r2 vs r3 token-boundary differential

Frozen before execution. **Not executed.**

## Question

Not *"did the whitespace slip happen again?"* — three more copies of the W1-G
fixture would answer almost nothing, since that slip was 1-in-3 and sporadic and
did not recur in W1-H without any amendment.

Instead:

> **Does explicitly defining delimiter syntax change how the worker represents
> header tokens under the same deliberately boundary-sensitive input?**

## Design

```text
Arm U (control)    Qwen3.5:9b + skill r2 + fixture T    U1 U2 U3
Arm V (treatment)  Qwen3.5:9b + skill r3 + fixture T    V1 V2 V3
```

The **only** arm-level variable is the skill revision.

```text
r2  0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a
r3  ea259e1a2af8663987d1dd5bed333a0a1ae33701752166a39f1c17446be3d5d5
```

Identical across both arms: model, capability box, UTF-8 transport, lifecycle,
authority policy, validator family, frozen fidelity instrument, fixture pair,
canonical answer block, and prompt text (which differs between runs only by run
id and sibling list, and never names a revision, a verb, or the word
*whitespace*, *delimiter* or *trim*).

## Fixture T

```text
vendor-charge-summary.txt    Header: Charge Period, Client Ref, Net Value, Tax Band, Settlement State
internal-charge-ledger.txt   Header: Charge Period, Internal Key, Client Ref, Net Value, Settlement State, Remarks
answers                      human_answers.md, canonical block 715 bytes
                             sha256 abf50c549d25d905…
```

Properties, all asserted by `verify_prep` check 4:

- field names occur authoritatively in `Header:` declarations;
- delimiter-adjacent whitespace is present (`, ` throughout);
- **every token but `Remarks` contains a significant internal space**, so
  "discard the padding" and "remove the spaces" are distinguishable outcomes;
- neither r2 nor r3 names any fixture-T token, so **neither arm is handed the
  canonical spelling** by its own skill text (r3's worked example deliberately
  reuses `Supplier Name`, vocabulary r2 already carries, plus `Region Code`);
- both arms read the same two files, declared by role in `fixtures.json`.

The fixture is a plausible member of its input class. It is **not** malformed and
not adversarial; the padding is the ordinary `, ` of the existing fixtures.

## Primary measure — preregistered, mechanical

Reported by `tokenization_report.py`, which **never consults the structural
verdict** (asserted by check 19). Per run:

```text
1  canonical header-token set derived by the input contract (_fixture_headers)
2  every worker-declared observed_fields token, verbatim
3  whether delimiter-adjacent separator whitespace survives in ANY token
4  whether legitimate INTERNAL whitespace is preserved
```

Each declared token is classified against its source's canonical set:

```text
EXACT      == canonical                      'Client Ref'
PADDED     separator whitespace retained     ' Client Ref'
COLLAPSED  internal whitespace altered       'ClientRef'
OTHER      renamed, merged, or absent
```

`tokenization = CLEAN` only when a run has zero PADDED, zero COLLAPSED and zero
OTHER.

**Overall structural PASS is explicitly NOT the tokenization measure.** An
artifact can pass or fail for reasons unrelated to field tokenization, and either
would contaminate the comparison.

## Secondary, observational only

Reported but **not used to judge the token-boundary hypothesis**:

```text
RESOURCE DISCOVERY / CONSUMPTION / ARTIFACT PRODUCTION / AUTHORITY
STRUCTURAL     the full validator verdict
FIDELITY       the frozen instrument, incl. confirmation preservation
```

W1-H P2's `FID-5 UNRECORDED_HUMAN_ANSWER` behaviour remains visible through the
frozen fidelity gate. It is a **separate producer-contract problem**
(`../w1h/ACCEPTANCE.md`), r3 does not address it, and it must not be used to
judge tokenization or to justify widening r3.

## Reporting rule, fixed in advance

Report the **six actual runs descriptively**. Specifically:

- **Do not** convert 3 + 3 into a reliability estimate, rate, or probability.
- **Do not** claim r3 "solves", "fixes" or "eliminates" the behaviour.
- **Do not** pool W1-I with W1-G or W1-H; different fixture, different transport.
- A clean arm V is consistent with the amendment working **and** with the slip
  simply not occurring; a clean arm U would show the fixture did not elicit the
  behaviour at all, which is itself an informative and reportable outcome.
- If both arms are clean, the honest conclusion is that **this fixture did not
  discriminate**, not that r3 is unnecessary.

## Discipline

**N = 3 per arm, fixed.** Do not increase N after seeing the outcome. Do not
rescue a run, repair an artifact, or rerun an individual run. Do not amend r2 or
r3 in this pack. Do not add the fixture's canonical tokens to either skill. A
denial is worker evidence, never a harness failure.

## Execution — not yet authorized

```bash
python work_interface/authority/selftest_authorized_capabilities.py && python work_interface/authority/selftest_permission_policy.py && python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1i/harness/run_batch.py --run all && python work_interface/w1i/tokenization_report.py && python work_interface/w1i/grade.py && python work_interface/w1i/fidelity_gate.py && python work_interface/w1i/authority_report.py
```
