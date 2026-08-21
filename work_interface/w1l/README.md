# W1-L — fixed-configuration repeatability baseline

**Frozen. Not executed.** Design, measures and interpretation branches in
`PREREGISTRATION.md`.

> **There is no treatment.** Twelve runs of one configuration, to measure how
> much this worker moves when we deliberately change nothing.

## Why this, and why now

Every pack since W1-F asked *"what intervention explains this?"* W1-L asks the
prerequisite question. W1-H and W1-K ran the identical configuration and got:

```text
W1-H   P1 = 6/6 rows EXACT   P2 = 2/6   P3 = 6/6
W1-K   A1 = 1/6              A2 = 2/6   A3 = 1/6
```

No declared variable between them. If variation is that large, the three-run
arms of W1-I, W1-J and W1-K could not have resolved the effects they were built
to measure — which is consistent with all three returning ambiguous results.

## Configuration

```text
model              qwen3.5:9b        skill      frozen r2
validator          frozen v0         delivery   canonical 0->5
fixtures / block   the W1-H/W1-K control inputs, unchanged
capability server  corrected UTF-8 two-verb box
lifecycle, permission policy, fidelity checker   unchanged
runs               R01..R12          N = 12     treatment   NONE
```

Provider configuration is pinned and recorded per run — `temperature 1`,
`top_k 20`, `top_p 0.95`, `presence_penalty 1.5` — and asserted identical across
all twelve. **Observation only.** The sampling configuration is part of the
system being characterised, not a knob to remove the variance the pack exists to
measure.

## Two fingerprints

```text
1  PRESERVATION   rows 0-5 as EXACT | BUNDLED | NONVERBATIM | ABSENT
                  + preserved_prefix_length, number_exact,
                    number_individually_preserved
2  TOKENIZATION   EXACT | SINGLE_FIELD_PAD | SYSTEMATIC_PAD |
                  UNSPLIT_HEADER | COLLAPSED | OTHER
                  offending tokens preserved verbatim, so OTHER is never opaque
```

Both are validated against known historical artifacts *before* any run: W1-H P1
→ `EEEEEE`, W1-H P2 → `EE----`, W1-K A1 → `E-----`/UNSPLIT_HEADER.

## Infrastructure closed with this pack

**B-1 — the verifier is observational.** `verify_prep` refuses a pack that
already holds evidence, runs any reporter against a temporary copy, and
fingerprints the pack before and after itself, failing if one byte moved. A
verifier that mutates what it verifies is the same class of authority defect
this lab exists to design out of workers.

**B-2 — constants are declared, not cloned.** `manifest.json` is the single
source for the run set, fixtures, revisions, markers and denominators.
Reporters derive from it and never glob `runs/`, so a stray directory cannot
change a denominator quietly. Regressions in
`harness/selftest_pack_infra.py` reproduce each shipped defect — the W1-I stale
markers, the W1-I/W1-K revision pin, the silent-denominator risk — and prove the
new infrastructure catches them.

Also resolved: `../w1k/CONSUMPTION_NOTE.md`, where a `3/3` in prose meant *three
of three resources* in a six-run pack. Consumption is now reported as a
runs × resources matrix with both denominators named.

## Discipline

N = 12, fixed. Twelve observations reported as twelve observations — no
reliability percentage, no population claim. N=12 characterises **this frozen
setup only**.

Do not tune the provider configuration. Do not introduce any treatment. The
tokenization line stays parked; Surface C stays deferred until this baseline is
closed.
