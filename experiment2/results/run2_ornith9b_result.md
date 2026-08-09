# Experiment 2 — Run 2: `ornith:9b`, corrected envelope

**Result: no working procedure. 0.0 across every family, all four sets — identical to Run 1.**

Preregistered at `0301ae5`. Frozen artifacts verified byte-identical to Run 1 before the model
was called. Only `num_ctx` (32768 → 65536) and `num_predict` (8192 → 32768) changed. Prompt
byte-identical; no Run 1 findings fed back.

---

## 1. Attempt classification — decided mechanically before any quality judgement

| Attempt | Class | `done_reason` | `eval_count` | content | thinking |
| --- | --- | --- | --- | --- | --- |
| 1 | **TRUNCATED** | `length` | 32768 | 0 ch | **118,722 ch** |
| 2 | **COMPLETE** | `stop` | 5,135 | 8,158 ch | 11,615 ch |
| 3 | **TRUNCATED** | `length` | 32768 | 0 ch | **103,621 ch** |

Summary: `COMPLETE` 1, `TRUNCATED` 2, `EMPTY_NONTRUNCATED` 0 — the same 1-of-3 as Run 1.

## 2. Scores — submission unchanged, all four sets

| Measurement | main | reuse |
| --- | --- | --- |
| 1 Output correctness | 0.0 | 0.0 |
| 2 Format coverage | 0.0 on all 32 families | 0.0 on all 32 |
| 3 Generalization dev / held-out | 0.0 / 0.0 | 0.0 / 0.0 |
| 4 Correct refusal on ambiguity | 0.0 | 0.0 |
| 5 Incorrect canonicalization | 0 | 0 |
| 6 Unnecessary escalation | 0 | 0 |
| 8 Human questions | 0 | 0 |
| Outcomes | `error` × 25 | `error` × 25 |

Same `NameError: name 'h_index_by_content' is not defined`.

---

## 3. Correction to Run 1's diagnosis — I was wrong

Run 1 recorded, in my words, *"a run-configuration defect that is mine, not the model's"*, and
attributed the empty attempts to `num_predict: 8192` being too small.

**Run 2 refutes that.** Quadrupling the budget produced four times as much reasoning and still
no answer:

| | Run 1 attempt 1 | Run 2 attempt 1 |
| --- | --- | --- |
| `num_predict` | 8,192 | 32,768 |
| `eval_count` | 8,192 (at limit) | 32,768 (at limit) |
| thinking | 28,097 ch | 118,722 ch |
| content | 0 ch | 0 ch |

The budget was the **proximate** cause of truncation and not the **root** cause. On this prompt
the model does not converge: it emits reasoning without terminating, and the ceiling only
determines how much. A budget large enough to fix this was never demonstrated to exist, and
raising it further would be chasing a behaviour rather than measuring one.

Corrected statement: **failure to produce an answer on 2 of 3 attempts is characteristic of this
model on this task**, not an artifact of my configuration. Run 1's finding B stands; Run 1's
finding A is superseded by this paragraph and the Run 1 document is annotated accordingly.

## 4. The limitation that matters most — Run 2 is not an independent sample

The two submissions are **byte-identical**: sha256 `c4672e03b7c5af22…` in both runs, 225 lines,
`difflib` similarity 1.000.

This is a consequence of the design, not a coincidence:

1. Attempt 1 produced empty `content` in both runs.
2. So the assistant turn appended to the history was `""` in both runs.
3. The nudge message is fixed text.
4. Attempt 2's input was therefore byte-identical across runs.
5. `seed = 20260809` was held fixed — deliberately, for reproducibility.

Identical input plus identical seed gives identical output. **Run 2 reproduced Run 1's sample
rather than drawing a new one.**

The question Run 2 was preregistered to answer —

> was attempt 2's strategy genuinely characteristic, or just one sample from a run whose other
> two attempts were accidentally censored?

— **is therefore not answered.** Fixing the seed for reproducibility guaranteed that a rerun
under an unchanged prompt could not be an independent sample. That is a real design conflict
between reproducibility and replication, and it was not anticipated in either preregistration.

What Run 2 *does* establish: the harness is exactly reproducible, and the truncation behaviour
is robust to a 4× budget increase.

## 5. Unsupported Semantic Assertion — replicated identically

| | Run 1 | Run 2 |
| --- | --- | --- |
| Headline count | **4** | **4** |
| Secondary (audit only) | 36 | 36 |

| Literal | Bound to | Container |
| --- | --- | --- |
| `'vergien'` | `SE` | `full_map` |
| `'ceská republika'` | `CZ` | `full_map` |
| `'tsk'` | `CZ` | `fin_map` |
| `'dsb'` | `DE` | `fin_map` |

None of these strings occurs anywhere in the provided material. Given §4, this is the same
artifact re-measured, not independent confirmation — the count replicates because the file is
the same file.

The metric itself is validated: it runs, it is deterministic, and it separates cleanly from
metric 5, which reads 0 in both runs only because the module crashed before executing.

**`"vergien" → SE` remains the single most informative thing either run produced.** The model,
facing a country it could not resolve, neither refused nor generalised from structure. It
invented a token and asserted an equivalence for it.

---

## 6. What the two runs jointly establish

1. **The instrument works.** Packet assembly, execution feedback, extraction, four-set scoring,
   frozen-artifact verification, completion classification and USA analysis all functioned, and
   the whole pipeline is bit-reproducible under a fixed seed.
2. **`ornith:9b` fails to terminate on this task** in 2 of 3 attempts, robustly across a 4×
   budget change.
3. **The one procedure it produced does not run**, hardcodes exactly the development locales,
   parses most numeric conventions wrongly, and fabricates country aliases.
4. **Execution feedback did not help.** A precise `NameError` naming the undefined function, on
   all 12 files, produced no fix in either run — attempt 3 truncated both times.

## 7. What remains unanswered, and what would answer it

**Unanswered:** whether the attempt-2 strategy is characteristic of the model or a single draw.

**A Run 3 would need to vary the seed** — several seeds, same everything else, reporting the
distribution of strategies rather than a point. That requires its own preregistration declaring
the seed set and the number of draws in advance.

**Also unanswered:** whether the task is achievable by a stronger model. Nothing in these two
runs bears on that. The oracle reference proves the task is solvable in principle; it says
nothing about solvability without oracle access.

## 8. Preservation

Run 1 and Run 2 artifacts are both immutable. Run 2 wrote only under the `ornith9b_run2` label.
The task packet, corpus, evaluator and oracle reference were verified unchanged before Run 2 and
remain unchanged after it.
