# W1-L preregistration — fixed-configuration repeatability baseline

Frozen before execution. **Not executed.**

## Question

Every pack since W1-F has asked *"what intervention explains this?"* W1-L asks
the prerequisite question:

> **How much does this worker move when we deliberately change nothing?**

W1-H and W1-K ran the identical configuration and disagreed sharply
(`../w1k/CLOSURE.md` §3):

```text
W1-H   P1 = 6/6 rows EXACT   P2 = 2/6   P3 = 6/6
W1-K   A1 = 1/6              A2 = 2/6   A3 = 1/6
```

Two perfect runs in one pack, none in the other, **with no declared variable
between them**. If run-to-run variation is of that size, the three-run arms of
W1-I, W1-J and W1-K could not have resolved the effects they were built to
measure. That must be established before any further treatment.

## Design

```text
model              qwen3.5:9b        skill      frozen r2
validator          frozen v0         delivery   canonical 0->5
fixtures / block   the W1-H/W1-K control inputs, unchanged
capability server  corrected UTF-8 two-verb box
lifecycle          unchanged         permission policy   unchanged
fidelity checker   frozen
runs               R01..R12          N = 12     treatment   NONE
```

**No r2c, no r3, no Surface C slots, no reordered block, no tokenization
instruction change, no new worker-facing prose.** `verify_prep` check 4 asserts
each of these mechanically.

Prompts differ from the W1-K control prompt only in pack name, run id, sibling
list and the forbidden-inspection list.

## Provider configuration — pinned, preserved, not tuned

Recorded per run and asserted identical across all twelve:

```text
model        qwen3.5:9b
parameters   temperature 1, top_k 20, top_p 0.95, presence_penalty 1.5
context      262144        quantization Q4_K_M
```

**Observation only.** Nothing here is adjusted — the sampling configuration is
part of the system being characterised, not a knob to remove the variance the
pack exists to measure.

It is read from the **declared** provider configuration, not intercepted
traffic: a tee would sit in the worker's request path and would itself change
the configuration this pack reproduces.

## Primary measurement 1 — preservation fingerprint

Every run, all six rows independently:

```text
EXACT | BUNDLED | NONVERBATIM | ABSENT
```

plus, derived mechanically:

```text
preserved_prefix_length          from the START OF DELIVERY
number_exact
number_individually_preserved    carried by a confirmation carrying ONLY
                                 that row, verbatim or not
```

These are **descriptors**, not assumptions about mechanism.

## Primary measurement 2 — tokenization fingerprint

Classified independently of preservation:

```text
EXACT | SINGLE_FIELD_PAD | SYSTEMATIC_PAD | UNSPLIT_HEADER | COLLAPSED | OTHER
```

The **offending declared tokens are preserved verbatim** alongside the class, in
`BASELINE.json`, so `OTHER` never becomes an opaque bucket.

Both fingerprints are validated against known historical artifacts before any
run: W1-H P1 → `EEEEEE`/EXACT, W1-H P2 → `EE----`/EXACT, W1-K A1 →
`E-----`/UNSPLIT_HEADER (`verify_prep` check 8).

## Secondary layers

Reported separately, **every denominator derived from the manifest**:

```text
RESOURCE DISCOVERY     RESOURCE CONSUMPTION     ARTIFACT PRODUCTION
AUTHORITY              STRUCTURAL               FIDELITY
```

No hard-coded `3/3` anywhere. Resource consumption is reported as a
runs × resources matrix with both denominators named — the ambiguity recorded
in `../w1k/CONSUMPTION_NOTE.md` cannot recur.

**The run set is authoritative.** Reporters read `R01..R12` from
`manifest.json` and never glob `runs/`, so a stray or debug directory cannot
quietly change a denominator later.

## Preregistered interpretation

```text
substantial fingerprint variation across identical runs
  -> fixed-configuration worker variability is confirmed at a scale relevant
     to the earlier N=3 comparisons

one or two fingerprints dominate
  -> a repeatable baseline shape exists and is worth designing against

multiple tokenization failure forms recur
  -> supports treating tokenization as a broader producer-instability family
     rather than a single defect

all twelve nearly identical
  -> the earlier W1-H/W1-K divergence requires another explanation.
     Do NOT retroactively label it noise.
```

## Reporting rule

N=12 characterises **this frozen setup only**. No model reliability percentage
and no population claim follows from it. Report the twelve fingerprints as
twelve observations.

## Discipline

N = 12, fixed. Do not increase or decrease N after seeing the outcome. Do not
rescue a run, repair an artifact, or rerun an individual run. Do not tune the
provider configuration. Do not introduce any treatment. **The tokenization line
stays parked** and Surface C stays deferred.

`verify_prep` is observational: it refuses an executed pack, runs reporters only
against a temporary copy, and fails if it mutates a single byte of the pack.

## Execution — not yet authorized

```bash
python work_interface/harness/selftest_pack_infra.py && python work_interface/authority/selftest_authorized_capabilities.py && python work_interface/authority/selftest_permission_policy.py && python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1l/harness/run_batch.py --run all && python work_interface/w1l/baseline_report.py && python work_interface/w1l/grade.py && python work_interface/w1l/fidelity_gate.py && python work_interface/w1l/authority_report.py
```
