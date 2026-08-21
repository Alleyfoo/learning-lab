# W1-J preregistration — confirmation-order disposition

Frozen before execution. **Not executed.**

## Question

The confirmation-preservation census
(`../census/confirmation_preservation/CENSUS.md`) found loss concentrated on
rows whose decisions have no provenance slot — **and** that all six lossy runs
lost a contiguous suffix. In that corpus the two rows carrying a slot are also
the first two delivered, so the readings are perfectly confounded:

```text
A  PROVENANCE-SURFACE   loss falls where a decision has no place to cite authority
B  ORDER / TRUNCATION   the worker records the first few confirmations, then stops
```

W1-J separates them the cheapest way available: **reverse the delivery order and
change nothing else.**

```text
delivered first  ->  last          slot
W1-H   0  1  2  3  4  5            YES YES NO NO NO NO
W1-J   5  4  3  2  1  0            NO  NO  NO NO YES YES
```

## Design — order only

```text
CONTROL     W1-H P1/P2/P3   delivery order 0->5   (already executed)
TREATMENT   W1-J Q1/Q2/Q3   delivery order 5->0   (three fresh runs)
```

Identical: Qwen3.5:9b, **r2** (r3 did not target this behaviour), the corrected
UTF-8 capability server, the same two verbs, the same lifecycle, the same
authority policy, the same validator, the same frozen fidelity checker, the same
W1-A fixtures, and the same six canonical answers from the same answer table at
the same pinned hash.

**No wording change. No new provenance fields. No "record all six"
reinforcement.** The prompt differs from W1-H's only in pack name, run id,
sibling list, and the forbidden-inspection list.

`verify_prep` check 19 asserts mechanically that the reversed block has an
**identical part multiset** to W1-H's — same 693 bytes, same six parts, exactly
reversed — so no answer text moved.

This is a **cross-pack differential**, not simultaneously randomized arms: the
packs ran at different times. Every other input of the worker system is pinned,
which is adequate for a disposition question and is stated rather than glossed.

## No second control arm

W1-H already provides a clean same-system control at the canonical order. W1-I
is excluded from the primary comparison because it used different fixtures.
Three fresh runs, not six.

## Primary measure

`preservation_report.py`. **Overall FIDELITY PASS is deliberately not the
result** — it collapses six independent observations into one bit, and the
question is *which* rows survive.

Every row, every run, reported independently:

```text
row   delivery_position   provenance_slot   preservation
```

```text
EXACT_INDIVIDUAL  one confirmation carries this row, and only this row
BUNDLED           a confirmation carries this row together with others
NONVERBATIM       a confirmation carries this row but not verbatim
ABSENT            no confirmation carries this row
```

Plus one mechanical descriptor per run — a **measurement, not a gate**:

```text
preserved_prefix_length = 0..6
```

counted from the **start of delivery**, so it is comparable across packs that
deliver in different sequences. Control values, already computed:

```text
W1-H P1 = 6    P2 = 2    P3 = 6
```

## Interpretation branches, fixed in advance

```text
loss moves toward the NEW suffix
  rows 1/0 become vulnerable, rows 5/4/3 tend to survive
  -> evidence for the ORDER / TRUNCATION mechanism

rows 0/1 remain preferentially preserved despite being delivered LAST,
while 4/5 remain lossy despite being delivered FIRST
  -> evidence for the PROVENANCE-SURFACE mechanism

both patterns visible
  -> likely mixed mechanism

no meaningful loss in Q1/Q2/Q3
  -> the reordered block did not discriminate.
     Do NOT infer either mechanism absent.
```

The strongest qualitative signal available: if a run preserves rows **5,4,3**
and then loses **2,1,0**, the *identity* of the preserved rows has changed while
the prefix shape survived. That is direct evidence for truncation, and it needs
no statistic to read.

## Reporting rule

- Report the three runs, row by row, against W1-H's three.
- **No percentages, no rates, no reliability estimate, no statistical
  inference.**
- Do not treat 3-versus-3 as an efficacy comparison.
- Do not pool with W1-I: different fixtures.
- Fidelity, structural, authority, consumption and production remain secondary
  and are reported after the primary measure.

## Discipline

N = 3, fixed. Do not increase N after seeing the outcome. Do not rescue a run,
repair an artifact, or rerun an individual run. Do not modify r2, r3, the
schema, the validator or the fidelity instrument. **Surface C stays deferred**
until this disposition is closed.

## Execution — not yet authorized

```bash
python work_interface/authority/selftest_authorized_capabilities.py && python work_interface/authority/selftest_permission_policy.py && python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1j/harness/run_batch.py --run all && python work_interface/w1j/preservation_report.py && python work_interface/w1j/grade.py && python work_interface/w1j/fidelity_gate.py && python work_interface/w1j/authority_report.py
```
