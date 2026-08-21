# W1-K preregistration — Surface C provenance-affordance differential

Frozen before execution. **Not executed.**

## Question

W1-J ruled out the simple model `delivery position → preservation`. It did
**not** establish `provenance slot → preservation`: row 1 carries a slot and
lost its identity in 3 of 3 reversed runs. So the question narrows:

> Under the **stable canonical delivery order**, does adding the same
> provenance affordance to rows 4/5 change their evidence preservation, without
> broadly changing the other rows?

## Design — one variable

```text
Arm A — control    Qwen3.5:9b + r2  + v0     canonical order 0->5   A1 A2 A3
Arm B — treatment  Qwen3.5:9b + r2c + v0+C   canonical order 0->5   B1 B2 B3
```

A **fresh paired control**, not a cross-pack comparison: the behaviour is now
too sporadic for W1-H to serve as the baseline.

Identical in both arms: model, fixture pair, canonical answer block and its
order, UTF-8 capability box, the two verbs, lifecycle, permission policy, and
the frozen fidelity instrument. Prompts differ only by run id and sibling list
and never name the variable.

The **only** arm-level difference is the output provenance surface: r2c is r2
plus the `output.provenance` shape and one evidence bullet requiring it, and
v0+C is v0 plus five named codes enforcing it. Arm A is graded against v0, arm B
against v0+C — each arm judged by its own contract, since grading B with v0
would make the treatment unobservable and grading A with v0+C would refuse it
for lacking a surface its skill never offered.

**No reminder prose.** `verify_prep` check 19 asserts the added lines contain
none of "all six", "every answer", "one answer per", "make sure", "be sure to",
"remember to", "do not omit" — and that r2c carries no r3 text.

## Within-artifact controls

```text
row 0  match key        existing slot   POSITIVE CONTROL
row 1  compare          existing slot   POSITIVE CONTROL   <- live, see below
row 2  currency         no slot         NEGATIVE CONTROL
row 3  source of truth  no slot         NEGATIVE CONTROL
row 4  report fields    NEW slot in B   TARGET
row 5  context fields   NEW slot in B   TARGET
```

Row 1 is a **live** control, not a formality: it was EXACT in 0 of 3 W1-J runs.
If it collapses again under the canonical order, the Surface C interpretation is
weakened whatever rows 4/5 do.

## Primary measure — the ladder

`surface_c_report.py`. **Overall FIDELITY PASS is not the result.**

```text
slot offered
   -> slot populated
   -> confirmation exists
   -> confirmation is individually attributable
   -> confirmation is byte-exact
   -> slot points to that confirmation
```

Per row, per run:

```text
row   slot class   confirmation preservation   provenance populated   binding valid
```

`preservation` is `EXACT_INDIVIDUAL | BUNDLED | NONVERBATIM | ABSENT`.
`binding valid` requires both that the cited id exists in `human_confirmations`
**and** that the confirmation it names actually carries that canonical row — a
citation pointing at the wrong confirmation is not provenance.

## Interpretation branches, fixed in advance

```text
4/5 improve while 0/1 remain stable, and 2/3 do not show the same improvement
  -> evidence consistent with a provenance affordance affecting preservation

4/5 slots populated but confirmations still ABSENT / BUNDLED / NONVERBATIM
  -> the provenance surface is NOT sufficient

4/5 improve, but 0/1/2/3 also shift substantially
  -> broad treatment effect; cannot attribute specifically to the new slots

0/1 collapse again under canonical order
  -> positive-control instability; Surface C interpretation weakened

treatment does not populate the required provenance correctly
  -> the producer failed to use the new interface;
     no clean preservation conclusion

both arms mostly clean
  -> the experiment did not discriminate
```

## Reporting rule

- Report the six runs row by row. **No percentages, no rates, no reliability
  estimate, no statistical inference.**
- Do not pool with W1-H, W1-I or W1-J.
- Structural, fidelity, authority, consumption and production are secondary and
  reported after the ladder.
- A refusal in arm B caused by the *new* codes is a producer-interface finding,
  not a preservation finding, and must be reported as such.

## Discipline

N = 3 per arm, fixed. Do not increase N after seeing the outcome. Do not rescue
a run, repair an artifact, or rerun an individual run. Do not modify r2, r2c,
r3, v0 or the fidelity instrument. **The tokenization line stays parked**; Q3's
systematic padding is not to be addressed here.

## Execution — not yet authorized

```bash
python work_interface/schema_c/work_definition_c.py --self-test && python work_interface/authority/selftest_authorized_capabilities.py && python work_interface/authority/selftest_permission_policy.py && python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1k/harness/run_batch.py --run all && python work_interface/w1k/surface_c_report.py && python work_interface/w1k/grade.py && python work_interface/w1k/fidelity_gate.py && python work_interface/w1k/authority_report.py
```
