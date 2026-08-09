# Experiment 2 — Condition B Preregistration: guided warm-up, then unseen task

**Declared before execution. Nothing below changes after results are seen.**

Condition A (closed book) is complete and frozen: `ARM_ornith9b_FROZEN.md`,
`ARM_qwen35_9b_result.md`. Six independent modelling runs across two 9B models produced zero
rows of correct canonical output.

---

## 1. The question, restated

Condition A asked: *can it invent the whole method from nothing?* Answer: no.

Condition B asks something more realistic:

> **Can an agent learn the shape of the job from one guided example, then generalize the method
> to a materially different input without being told the solution again?**

## 2. Two phases with a hard boundary

```text
PHASE 1 — WARM-UP / TEACHING          <-- TRAINING, NOT EVIDENCE
  trivial file
  explicit instructions
  execution feedback
  correctness confirmation

  ============ HARD BOUNDARY ============

PHASE 2 — REAL                        <-- THE ONLY SCORED PHASE
  the standard condition-A task packet
  no solution instructions
  agent decides what to do
```

**Phase 1 is labelled training and is never scored.** Only the phase-2 submission is evaluated.
This is stated first because it is the thing most likely to be forgotten later.

## 3. Phase 1 — the warm-up

Source: `warmup/warmup_source.csv`, 8 rows.

```
Country,Product,Month,Sales
FI,ART-9001,2025-01,10.00
SE,ART-9001,2025-01,12.00
...
```

Already long-form, already ISO periods, already ISO country codes, already plain numbers. The
only work is recognising the canonical contract and renaming four columns. No reshaping, no
locale, no separator ambiguity.

Kept **disjoint from the graded corpus**: product ids `ART-9xxx` (graded uses `ART-0001..0005`),
year 2025 (graded uses 2026), no locale beyond plain ISO/English. Nothing here leaks a graded
value, a held-out locale, or an ambiguity pattern.

Explicit instructions given in phase 1 only:

- inspect the source;
- map it into the required canonical columns;
- preserve every business row;
- if the source uses a different shape, reshape it as needed;
- if a value is ambiguous, do not guess — use `Escalate` or `AskHuman`;
- return a reusable `normalize(source_path)` procedure, not merely the transformed data.

**Phase 1 is the only place correctness is revealed**, because it is teaching. Up to 3 attempts,
with the normal execution-feedback loop plus a pass/fail verdict against `warmup_truth.csv`.

## 4. The boundary message

On warm-up success, exactly this, and nothing more:

> That procedure passed the supplied example. Use what you learned from this task when handling
> the next source, but do not assume the next source has the same layout or naming.

Operational, not praise: *you found a viable pattern; retain it; do not over-fit it.*

If the warm-up **fails** after 3 attempts, phase 2 still runs, and the seed is recorded as
`warmup_failed`. Its phase-2 result is reported separately and **not** pooled with warmed-up
seeds — a failed warm-up is not a warm-up.

## 5. Phase 2 — identical to condition A

The phase-2 prompt is the **byte-identical condition-A prompt**: same `TASK.md`, same
`contract.py`, same 12 dev sources, same trailing instruction. Conversation context from phase 1
is retained; that retention is the treatment.

**Design decision, and the one place this departs from the sketch.** An alternative was to give
phase 2 a *single* source rather than all 12. That would change two things at once — the warm-up
*and* the prompt size — and an improvement could not be attributed to either. Since condition A
used all 12, phase 2 uses all 12, so **B − A isolates exactly the warm-up**.

The single-source variant is worth running, but as its own condition:

> **B′ — guided warm-up, then a single unseen source.** Isolates prompt size. Not run here.

Phase 2 gets **no** solution instructions, no reminder to unpivot, no locale hints, no mention of
any condition-A finding.

## 6. Model, seeds, envelope — unchanged from the Qwen arm

| | |
| --- | --- |
| Model | `qwen3.5:9b`, digest `6488c96fa5faab64…` |
| Thinking | disabled (`think: false`) |
| Seeds | **11111, 22222, 33333** — the same three, so B pairs against A seed-for-seed |
| `num_ctx` / `num_predict` | 65536 / 32768 |
| temperature / top_p / top_k | 0.6 / 0.95 / 20 |
| Phase-2 attempts | 3 |
| Independence | one process per seed, fresh context, **no cross-seed feedback** |

Reusing A's seeds is deliberate: it makes B a paired comparison rather than two unrelated
samples.

Task packet, corpus, evaluator, executor and oracle reference are frozen and guarded by hash.

## 7. Measurements

Phase 2 only, per seed, identical to condition A: output correctness, format coverage by family,
held-out generalization, correct refusal, incorrect canonicalization, unnecessary escalation,
reuse, human questions, plus Observed USA with the INERT / VINDICATED / CONSEQUENTIAL_RISK
taxonomy.

Additionally recorded, not scored: whether the warm-up passed, on which attempt, and the
phase-2 completion classes.

## 8. Expectations — declared, not pass criteria

| Expectation | Reasoning |
| --- | --- |
| Warm-up should pass for most seeds | It is a four-column rename |
| Phase 2 producing **non-zero rows** would already be a change | Every condition-A seed returned zero rows on every file |
| Held-out > 0 on any seed would be a strong result | No condition-A seed managed it |
| Escalation appearing at all would be notable | Zero escalations across 125 file-evaluations in condition A |

**If B goes from zero rows everywhere to competent normalization, that is the headline finding:**
the agent did not need a locale database, it needed **task induction from a successful example**.

If B also returns zero rows, that strengthens the reference-data hypothesis and makes
**condition C — reference-augmented** the next step.

## 9. Contamination guards

- Warm-up data disjoint from the graded corpus (§3), verified by construction.
- Warm-up truth is revealed **only** in phase 1, and concerns only warm-up rows.
- No condition-A finding is fed to any seed.
- Phase-2 prompt byte-identical to condition A's; asserted by hash at runtime.
- Phase 1 is never scored, and warm-up-failed seeds are reported apart.
