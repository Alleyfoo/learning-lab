# W1-D2 — closed. Surface B operationally accepted.

Executed exactly as frozen at `84dc126`; evidence at `bc1b02e`.

```text
run   lifecycle/completion                        structural   fidelity        A4 shadow
L1    COMPLETED 2 turns, 1 block, 0 cont, 0 silent  PASS       FIDELITY PASS   CLEAN
L2    COMPLETED 2 turns, 1 block, 0 cont, 0 silent  PASS       3 findings      CLEAN
L3    COMPLETED 2 turns, 1 block, 0 cont, 1 silent  REFUSED    3 findings      WOULD_CONTEST
```

## Recorded

- **The lifecycle reached its normal path in all three runs.** No CONTESTED
  lifecycle, no timeout, no turn-limit, no forbidden-path trip.
- **The canonical information block was delivered exactly once in every run**,
  byte-identical (`46158afa4b7e682a…`, 693 bytes).
- **Zero neutral continuations were required.** `"Continue."` was never sent.
- **L1 — STRUCTURAL PASS + FIDELITY PASS.** Six confirmations, one per delivered
  canonical row, each byte-exact and exclusively attributed.
- **L2 — STRUCTURAL PASS + FIDELITY FINDINGS.** FID-6 `TRAILING_CONTENT` on the
  Amount confirmation, cascading to FID-1 on `body.compare[Amount]`, plus FID-2
  on a bundled rows-4+5 confirmation.
- **L3 — structural refusal after failure to consume the frozen skill.** Its
  `read image` on `SKILL.md` failed with *"unsupported image format"* and it
  never re-read the file, producing an invented non-v0 schema. Refusal codes:
  `unknown_work_definition_version`, `unknown_task_family`,
  `missing_source_fixture` ×2, `match_key_not_declared`.
- **A4 shadow: L3 WOULD_CONTEST** for creating `todo.md` (`62bb446a21f4`, 1010
  bytes). Descriptive only; it did not influence any run, and it is **not** the
  cause of L3's refusal, which has an independent and sufficient cause.
- **No population-level reliability conclusion is drawn from N=3.** The
  differences from W1-C are attributable to the lifecycle stimulus under two
  frozen configurations, nothing more.

## What this established

Not "single-block lifecycle improves Qwen" — N=3 cannot support that. What it
established is narrower and more useful:

> **Single information delivery is sufficient for completion.**

All three runs completed in two turns on one delivery, with no continuation ever
needed. The repeated block in W1-C was therefore **unnecessary as lifecycle
machinery**, and that design is retired.

Second, and independently: **the full desired path is demonstrably reachable.**
L1 is an untouched artifact in which a 9B local worker consumed r2, used the
complete information block, produced structurally valid v0, preserved all six
supplied answers independently and byte-exactly, and passed the frozen fidelity
slice. The target state is no longer hypothetical.

## Operational acceptance

**Surface B is accepted.** Future Work-interface harnesses use **single
information delivery, followed by neutral activation only if needed.**

## Why L1 and L3 together matter

Both began identically — `read image(SKILL.md)` → *"unsupported image format"* —
and then diverged: L1 recovered with a shell `type` and produced the cleanest
artifact in the line; L3 did not recover and invented a schema. Same model, same
frozen conditions, opposite admissibility.

That is the case for this architecture rather than against it. The system does
not need the worker to be predictable; it needs to recognise which output is
admissible and which is not — and it did, in both directions, without being told
which run was which.

## Carried into W1-E

L1's recovery route was **shell**. Surface A removes it. W1-E therefore asks a
strictly harder question: *can the worker succeed without exercising authority it
does not have?* A worker that gets `read_image` wrong, receives a denial, and
never finds the authorized reader is legitimate worker evidence — not a harness
defect, and not something the prompt should be edited to prevent.
