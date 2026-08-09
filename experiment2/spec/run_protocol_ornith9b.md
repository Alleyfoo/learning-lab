# Experiment 2 — Run Protocol: `ornith:9b`

**Declared before the run. Nothing below may change after results are seen.**

---

## Model identity

| Field | Value |
| --- | --- |
| Ollama tag | `ornith:9b` |
| Digest | `a75697c145891910e312c95e4a9fc1ccb8653e5ef543b23b0403a4665b82fd91` |
| Ollama version | 0.32.6 |
| Architecture / family | `qwen35`, 9.0B parameters |
| Quantization | Q4_K_M |
| Context length | 262144 |
| Local `modified_at` | 2026-07-01T14:16:15+03:00 |

## Generation settings

The model's own packaged defaults are used as its designed operating point, plus a fixed seed
for reproducibility. No prompt-side sampling tuning.

| Parameter | Value | Source |
| --- | --- | --- |
| `temperature` | 0.6 | model default |
| `top_p` | 0.95 | model default |
| `top_k` | 20 | model default |
| `seed` | 20260809 | fixed for reproducibility |
| `num_ctx` | 32768 | set; packet is ~9k tokens |
| `num_predict` | 8192 | set |
| system prompt | the model's own packaged system prompt | unchanged |

## What the model receives — and nothing else

`artifacts/task_packet/` in full, verbatim:

- `TASK.md` — business objective, canonical output schema, interface, judging summary
- `contract.py` — `CANONICAL_COLUMNS`, `Escalate`, `AskHuman`
- `sources/D01.csv … D12.csv` — **complete files, untruncated** (29 KB total, fits the context)

It does **not** receive: `canonical.csv`, `canonical_manifest.json`, `corpus_manifest.json`,
any held-out (`H*`) or ambiguity (`A*`) source, the reuse corpus, `generator/vocabulary.py`, or
`harness/reference/oracle_reference.py`.

## Iteration and feedback — declared limits

Up to **3 attempts** (1 initial + 2 revisions).

Between attempts the model receives execution-grounded feedback **from development sources
only**:

| Fed back | Withheld |
| --- | --- |
| Did the module import | Any comparison to ground truth |
| Whether `normalize()` ran per dev file | Whether the output is *correct* |
| Python error type and message | Any held-out, ambiguity or reuse file |
| Shape and first 3 rows of **its own** output | Any label from the corpus manifest |
| Escalations it raised, with its own reason text | Any hint about strategy |

This mirrors the execution-feedback contract established in the research: the environment
materialises intermediate state and returns runtime errors, and ground truth exists only for
evaluation.

## Extraction

The submission is the **last fenced `python` block** in the final response, written verbatim to
`results/submission_ornith9b.py`.

If no fenced Python block is present, or the module fails to import, **that is the result.** It
is recorded and scored as-is.

## No-repair rule

The submitted procedure is evaluated **unchanged** on dev, held-out, ambiguity and reuse sets.
Failures are preserved, not fixed. No post-hoc edits to the submission, the task packet, the
corpus, the evaluator or the oracle reference.

## Frozen artifact hashes

Recorded so any later modification to a graded artifact is detectable:

See `results/run_ornith9b_manifest.json`, field `frozen_sha256`, written by the runner before
the model is called.

## What a result means

| Outcome | Reading |
| --- | --- |
| High dev, low held-out | Memorised the development tokens. A one-off transformation, not a reusable rule |
| High dev and held-out, low reuse | Procedure depends on something incidental to these files |
| Normalizes ambiguity cases | **The dangerous failure.** Reported separately and prominently |
| Escalates equivalent variants | Too conservative. Reported as the paired cost |
| Fails to produce a procedure at all | A legitimate and informative result for a 9B local model |

A low score is an answer to the research question, not a failure of the experiment.
