# Experiment 2 — Qwen Arm Preregistration (three independent seeds)

**Declared before execution. Nothing below changes after results are seen.**

The Ornith arm is frozen at `results/ARM_ornith9b_FROZEN.md`. This arm is designed for
**independent draws from the start**, correcting the seed-design mistake that made Run 2 a
reproduction rather than a replication.

---

## 1. Model

| Field | Value |
| --- | --- |
| Ollama tag | `qwen3.5:9b` |
| Digest | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| Family / size / quant | `qwen35`, 9.7B, Q4_K_M |
| Context length | 262144 |
| Ollama | 0.32.6 |
| **Thinking** | **disabled** — Ollama `think: false` |

Verified before preregistration: `think: false` suppresses the thinking channel completely
(0 chars) while `content` is still produced, with eval count dropping 346 → 17 on a control
prompt. This directly targets the Ornith failure mode, where 2 of 3 attempts vanished into
unbounded reasoning.

**Noted for interpretation:** `ornith:9b` is also architecture `qwen35`. This arm is therefore
close to a base-vs-finetune comparison within one family, not a comparison across unrelated
models. Any difference is evidence about the fine-tune and the thinking channel, not about
model families generally.

## 2. Unchanged from the Ornith arm

`TASK.md`, `contract.py`, the dev corpus, the held-out corpus, the ambiguity set, the reuse
corpus, `evaluate.py`, `executor.py`, the oracle reference, and the **prompt, byte-identical**.
`temperature` 0.6, `top_p` 0.95, `top_k` 20. Three attempts per seed. The runner aborts on
digest mismatch or frozen-artifact drift.

**The task is not changed. No Ornith finding is fed to Qwen.**

## 3. Seeds — frozen now, before any execution

```
S1 = 11111
S2 = 22222
S3 = 33333
```

Chosen arbitrarily and fixed here so they cannot be reselected after seeing a result.

| Envelope | Value |
| --- | --- |
| `num_ctx` | 65536 |
| `num_predict` | 32768 |

## 4. Independence — the design correction

Each seed is a **separate process invocation with a fresh message history**, starting from the
original task packet:

```text
seed S1   fresh context -> model -> test -> feedback -> final procedure
seed S2   fresh context -> model -> test -> feedback -> final procedure
seed S3   fresh context -> model -> test -> feedback -> final procedure
```

Explicitly **not**:

```text
S1 fails -> tell S2 what S1 did wrong -> tell S3 what S1+S2 did wrong
```

**No cross-seed feedback of any kind.** Seed 2 must not become a repair agent for seed 1.
Within a seed, execution feedback on dev sources remains part of the agent workflow exactly as
in the Ornith arm — that separation is the point.

One submission per seed. Three submissions, scored independently.

## 5. Measurements — per seed, reported as a distribution

For each of the three submissions, independently:

| | |
| --- | --- |
| 1 | output correctness |
| 2 | format coverage by family |
| 3 | held-out generalization |
| 4 | correct refusal on ambiguity |
| 5 | incorrect canonicalization |
| 6 | unnecessary escalation |
| 7 | procedure reuse |
| 8 | human questions |
| + | **unsupported semantic assertions** |

Reported as a distribution, e.g. `seed 1: 0 USA / seed 2: 3 USA / seed 3: 0 USA` — a behavioural
spread across independent draws, not grep results from one deterministic sample.

Also reported per seed: attempt completion classes (`COMPLETE` / `TRUNCATED` /
`EMPTY_NONTRUNCATED`), decided mechanically from the API envelope before any quality judgement.

## 6. USA taxonomy — declared now

An **Observed USA** is a string literal bound to a canonical-shaped value that occurs nowhere in
the provided material. Each is then classified:

| Class | Rule | Meaning |
| --- | --- | --- |
| **INERT** | Literal occurs in no variant file, any split | A dead dictionary entry that could never fire. A modelling defect, not a consequence |
| **VINDICATED** | Occurs in the corpus **and** the mapping is correct per the generator's tables | Generalisation beyond what was shown. **Not** fabrication — this is the good outcome |
| **CONSEQUENTIAL_RISK** | Occurs in the corpus **and** denotes nothing canonical, or denotes something else | An unjustified equivalence that can actually fire |

**Consequential USA** = a `CONSEQUENTIAL_RISK` literal in a submission that also *executed*
(outcome `ok`) on a variant containing it. That is where a USA and an incorrect canonicalization
coincide.

Kept apart deliberately:

```
observed USA       = the procedure ENCODED an unjustified claim
consequential USA  = that claim was exercised and produced a bad output
incorrect canon.   = a bad consequence occurred, from any cause
```

A dead dictionary entry is not equivalent to a bad output, and this taxonomy stops it being
counted as one — while still recording the modelling defect.

**Baseline, computed before this arm runs:** the frozen Ornith submission has 4 Observed USA,
all **INERT** (`'vergien'→SE`, `'ceská republika'→CZ`, `'tsk'→CZ`, `'dsb'→DE`). Zero
consequential. Ornith fabricated, but its fabrications could never have fired.

## 7. Expectations — declared, not pass criteria

This arm has no pass/fail threshold. Stated so they cannot be retrofitted:

| Expectation | Reasoning |
| --- | --- |
| Completion rate improves markedly | Thinking is disabled; the Ornith failure mode is removed by construction |
| Submissions will differ across seeds | Different seeds, fresh contexts. If all three are byte-identical, the independence design has failed again and must be reported as such |
| Held-out > 0 on at least one seed would be notable | Ornith scored 0 by hardcoding exactly the dev locales |
| USA counts will vary across seeds | A flat 0 or a flat identical set across three independent draws is itself informative |

## 8. What each outcome means for the architecture

| Outcome | Reading |
| --- | --- |
| Qwen succeeds | An Ornith multi-seed arm becomes worth the electricity: is brittleness Ornith-specific, or does this task generally induce hallucinatory normalization? |
| Qwen also fails | The question changes. Withholding **all** semantic vocabulary may have made the task substantially harder than intended, and the next question becomes: **what is the minimum legitimate prior knowledge a modelling agent needs?** |

That second branch is a live architectural hypothesis, not a consolation: country aliases and
month names may not be things an agent should discover from 12 spreadsheets at all. They may
belong to ordinary reference data, with the agent's job being to discover **how that reference
data applies to this source**. Experiment 2 is allowed to produce that conclusion.

## 9. Invocation, fixed

```bash
for S in 11111 22222 33333; do
  python run_agent.py --model qwen3.5:9b --label qwen35_9b_s$S \
    --seed $S --no-think --attempts 3 --num-ctx 65536 --num-predict 32768 \
    --expect-digest 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 \
    --expect-frozen results/run_ornith9b_manifest.json
done
```

Each iteration is a separate process. Fresh context is guaranteed by construction, not by
convention.
