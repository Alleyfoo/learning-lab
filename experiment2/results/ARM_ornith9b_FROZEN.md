# Ornith-9B Arm — FROZEN

**Tag:** `exp2-ornith9b-arm` . Both runs immutable. No seed sweep performed.

```text
ORNITH-9B ARM

Run 1  (eb5b3bb)
  - 2/3 non-convergent
  - 1 broken procedure

Run 2  (838a27a)
  - 2/3 non-convergent despite 4x budget
  - completed procedure reproduced because seed was fixed

Conclusion
  - fixed-seed replication succeeded
  - independent strategy distribution NOT measured
  - ornith:9b is poorly suited to this task/protocol as currently configured
```

## Both runs, side by side

| | Run 1 | Run 2 |
| --- | --- | --- |
| `num_ctx` / `num_predict` | 32768 / 8192 | 65536 / 32768 |
| Attempt classes | 1 COMPLETE, 2 empty | 1 COMPLETE, 2 TRUNCATED |
| Attempt 1 thinking / content | 28,097 ch / 0 | 118,722 ch / 0 |
| Attempt 3 thinking / content | (empty) | 103,621 ch / 0 |
| Submission sha256 | `c4672e03b7c5af22…` | `c4672e03b7c5af22…` (identical) |
| Output correctness, all 4 sets | 0.0 | 0.0 |
| Held-out / reuse | 0.0 / 0.0 | 0.0 / 0.0 |
| Correct refusal | 0.0 | 0.0 |
| Observed USA | 4 | 4 (same file) |

## What is and is not established

**Established:**

- The harness is bit-reproducible under a fixed seed.
- `ornith:9b` fails to emit an answer on 2 of 3 attempts, and this is **robust to a 4× budget
  increase** — the budget was the proximate cause of truncation, never the root cause.
- The single completed procedure does not run, hardcodes exactly the development locales,
  mishandles most numeric conventions, and encodes 4 unsupported semantic assertions.
- Execution feedback did not help: a precise `NameError` naming the undefined function, on all
  12 files, produced no fix in either run.

**Not established — and explicitly not claimed:**

- **The invented aliases are NOT replicated evidence.** They are *one reproducible sample*, not
  two independent observations. Run 2 reproduced Run 1's submission byte-for-byte because the
  seed was fixed and the effective conversation state was identical. Counting the same file
  twice would be double-counting a single draw.
- Whether the attempt-2 strategy is characteristic of the model or a single draw. Answering that
  needs varying seeds, which was **not** done.
- Anything about task solvability by other models.

## Why no seed sweep

A sweep would measure how variable `ornith:9b` is. That is a question about one model's variance,
not about whether an agentic modelling system can discover a reusable normalization procedure.
The compute is better spent on an arm designed for independent draws from the start.

Ornith may return later for comparison: if the Qwen arm succeeds, an Ornith multi-seed arm tells
us whether the failure is Ornith-specific. If the Qwen arm also fails, the question changes
shape — see the Qwen preregistration, section 8.
