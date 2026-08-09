# Experiment 2 — Run 1: `ornith:9b`

**Result: no working procedure. 0.0 across every measurement family, on all four sets.**

Preserved as measured. Nothing was repaired before scoring. Frozen-artifact hashes verified
unchanged after the run: task packet, corpus manifest, canonical data, evaluator, executor and
oracle reference all match their pre-run sha256.

---

## Run identity

| Field | Value |
| --- | --- |
| Model | `ornith:9b` |
| Digest | `a75697c145891910e312c95e4a9fc1ccb8653e5ef543b23b0403a4665b82fd91` |
| Family / size / quant | `qwen35`, 9.0B, Q4_K_M |
| Context length | 262144 |
| Ollama | 0.32.6 |
| Sampling | temperature 0.6, top_p 0.95, top_k 20 (model defaults), seed 20260809 |
| Budget | `num_ctx` 32768, `num_predict` **8192** |
| Attempts | 3 allowed, 3 used |
| Submission sha256 | `c4672e03b7c5af22…` |

## Scores — unchanged submission, all four sets

| Measurement | main | reuse |
| --- | --- | --- |
| 1 Output correctness (equivalent) | **0.0** | **0.0** |
| 2 Format coverage | 0.0 on all 32 families | 0.0 on all 32 |
| 3 Generalization dev / held-out | 0.0 / 0.0 | 0.0 / 0.0 |
| 4 Correct refusal on ambiguity | **0.0** | 0.0 |
| 5 Incorrect canonicalization | 0 | 0 |
| 6 Unnecessary escalation | 0 | 0 |
| 7 Procedure reuse | n/a — nothing executed | n/a |
| 8 Human questions | 0 | 0 |
| Outcomes | `error` × 25 | `error` × 25 |

Metrics 5 and 6 are both zero for the same trivial reason: the module never ran. They are
reported anyway, as a pair, because suppressing them would misrepresent a crash as caution.

---

## Two distinct failures, and they must not be conflated

### A. A run-configuration defect that is mine, not the model's

Attempts 1 and 3 returned **literally empty content** — zero characters.

Diagnosed by replaying attempt 1's exact prompt and inspecting the API envelope:

```
prompt_eval_count : 20329
eval_count        : 8192      <- exactly num_predict
done_reason       : "length"
content           : 0 chars
thinking          : 28097 chars
```

The model spent its **entire** generation budget in the `thinking` channel and was cut off
before emitting any answer. `num_predict: 8192` — a number I chose — was too small for this
model's reasoning behaviour on a 20k-token prompt.

A control probe confirms the runner reads the right field: on a short prompt the model puts code
in `content` and reasoning in `thinking`, and the runner extracted it correctly. So this is a
budget defect, not a plumbing defect.

**Consequence: 2 of 3 attempts produced nothing for reasons unrelated to the model's ability to
do the task.** Run 1 therefore under-measures `ornith:9b`. That is stated plainly rather than
buried, and the run is preserved rather than re-run in place.

### B. What the model actually produced, when it produced anything

Attempt 2 emitted a 225-line module. It is genuinely informative, and it is bad in ways that
matter more than the crash:

| Defect | Evidence |
| --- | --- |
| **Does not run at all** | Calls `h_index_by_content(headers)` at four sites (lines 139, 161, 176, 193). The function is never defined. `NameError` on all 12 dev files |
| **Memorised exactly the development locales** | Wrote `_MONTH_NAMES` (English), `_FINNISH_MONTHS`, `_GERMAN_MONTHS`. Those are precisely the three month languages in the dev set. No Swedish, Czech, French or Spanish — so it would have scored 0 on held-out even had it run |
| **Fabricated equivalences** | Country map contains `"vergien": "SE"`, `"dsb": "DE"`, `"som": "FI"`, `"tsk": "CZ"`, `"ceská republika"`. **None of these strings appears in any source file.** Verified by grep across all 12 dev sources: zero occurrences each |
| **Number handling broken for most styles** | `_parse_sales` does `re.sub(r"[^0-9.\-]", "", s)`, stripping commas unconditionally. `1 234,50` → `123450` (1000× too large); `1.234,50` → `1.23450`. Correct only for `plain`, `us` and `ch` |

The fabricated aliases are the most significant finding available from this run. `"vergien"` is
not a word in any language present in the data; it was invented and mapped to Sweden. Had the
module run, that is the **incorrect canonicalization** hazard the experiment exists to catch —
a source value silently normalized to a canonical value it does not denote.

Metric 5 reads 0 only because the code crashed first. **The disposition toward fabricated
equivalence is present in the artifact even though the metric could not fire.**

---

## What this does and does not answer

**Does not answer** the main research question. A run in which two thirds of attempts were
truncated by my own budget setting cannot support a claim about whether this model can discover
a reusable normalization procedure.

**Does answer, on the evidence of the one produced artifact:**

1. The instrument works end to end against a real model — packet built, prompt assembled,
   execution feedback returned, submission extracted, scored on four sets, artifacts verified
   unchanged.
2. Execution feedback alone did not rescue the attempt. The model received a precise
   `NameError` naming the undefined function, on all 12 files, and attempt 3 produced nothing
   rather than a fix.
3. The one artifact produced generalised to nothing: its vocabulary is exactly the development
   locales, which is the memorisation failure mode the held-out split was designed to expose.
4. The model fabricated country aliases absent from the data. Asking it not to invent meaning
   is, on this evidence, not sufficient.

---

## Status and what a Run 2 requires

Run 1 stands. It is not superseded, deleted or amended.

A corrected run needs its own preregistration before execution, on the RUN A / RUN B pattern:
declare the corrected `num_predict` (and any thinking-budget handling) **and the pass
expectations**, commit that, then run. Reusing this document's numbers or adjusting the budget
until a score improves would be exactly the failure the whole project is disciplined against.

The task packet, corpus, evaluator and oracle reference are unchanged and will stay unchanged.
