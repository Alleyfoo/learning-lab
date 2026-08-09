# Experiment 2 — Run 2 Preregistration

**Declared before execution. Nothing below may change after results are seen.**

Run 1 (`eb5b3bb`, `results/run1_ornith9b_result.md`) is **preserved permanently**. Run 2 does
not supersede, amend or replace it. Run 1 contains two separable findings and both stand.

---

## 1. What Run 2 changes — the resource envelope, and nothing else

| Parameter | Run 1 | Run 2 | Changed? |
| --- | --- | --- | --- |
| Model tag | `ornith:9b` | `ornith:9b` | no |
| Digest | `a75697c1458919…` | must match exactly | no |
| Task packet (`TASK.md`, `contract.py`) | frozen | frozen | no |
| Dev sources D01–D12 | frozen | frozen | no |
| Corpus, held-out, ambiguity, reuse | frozen | frozen | no |
| Evaluator, executor, oracle reference | frozen | frozen | no |
| `temperature` / `top_p` / `top_k` | 0.6 / 0.95 / 20 | 0.6 / 0.95 / 20 | no |
| `seed` | 20260809 | 20260809 | no |
| Attempts | 3 | 3 | no |
| Feedback between attempts | execution-only, dev sources | identical | no |
| **`num_ctx`** | 32768 | **65536** | **yes** |
| **`num_predict`** | 8192 | **32768** | **yes** |

Rationale: Run 1's diagnosis showed `eval_count` hitting exactly 8192 with `done_reason:
"length"` and 28,097 characters of unemitted reasoning. The model's own context length is
262144. Deliberately choking output at 8k has no research value. The exact new numbers matter
less than declaring them in advance and giving reasoning plus answer room to finish.

The runner will **abort** if the model digest does not match Run 1's, or if any frozen sha256
differs.

## 2. What Run 2 must NOT do — no remediation

Run 1's findings are **not** fed back. The prompt is byte-identical to Run 1's. In particular
the model is not told to:

- define all helper functions before use;
- support Swedish, Czech, French or Spanish;
- avoid fabricating aliases;
- handle decimal commas or thousands separators;
- generalise beyond the locales it observes.

Those are Run 1 results. Supplying them would convert Run 2 from replication-under-corrected-
conditions into remediation, and would destroy the only question Run 2 can answer: **was
attempt 2's strategy characteristic of the model, or one sample from a run whose other two
attempts were accidentally censored?**

## 3. Mechanical completion criterion — declared before scoring

Each attempt is classified from the API envelope, before any judgement of procedure quality:

| Class | Rule |
| --- | --- |
| `COMPLETE` | `done_reason != "length"` **and** `content` non-empty |
| `TRUNCATED` | `done_reason == "length"` |
| `EMPTY_NONTRUNCATED` | `content` empty **and** `done_reason != "length"` |

Truncated attempts are **preserved and reported**, and are **never** interpreted as evidence
about procedure competence. This exists so that a second budget defect cannot masquerade as a
model result.

**Three attempts, fixed.** The run does *not* repeat until three `COMPLETE` attempts are
obtained. Whatever completes, completes; the count is reported.

The scored submission is the last fenced `python` block from the last attempt that produced one,
exactly as in Run 1.

## 4. New measurement — Unsupported Semantic Assertion (USA)

**Observational. It does not change scoring.** `harness/evaluate.py` is frozen and untouched;
this runs as a separate analysis over the submission's source text.

> **Unsupported semantic assertion:** the submission encodes an equivalence between a source
> value `X` and a canonical value `Y` where `X` does not occur anywhere in the provided
> material.

Kept strictly apart from metric 5:

```
incorrect canonicalization      = a bad consequence OCCURRED at execution
unsupported semantic assertion  = the procedure ENCODED an unjustified claim
```

Attempt 2 scored zero incorrect canonicalizations only because it crashed before running. That
does not make `"vergien" -> SE` a harmless modelling decision.

### Detection rule, declared now

Provided material = `TASK.md` + `contract.py` + `sources/D01.csv…D12.csv`, concatenated,
casefolded, whitespace- and NFC-normalized.

Over the submission's AST:

1. **`ast.Dict`** — for every entry with a string-constant key and a constant value, if the
   normalized key does not occur in the provided material, record a candidate.
2. **`ast.Set` / `ast.List`** of string constants — for every element not occurring in the
   provided material, record a candidate, tagged `membership`.

Each candidate records the enclosing assignment target where one exists.

**Headline count** = candidates whose bound value is *canonical-shaped*: a two-letter uppercase
country code, an integer 1–12, or a `YYYY-MM` string. These are direct claims about canonical
identity.

**Secondary list** = all other candidates, reported for manual audit and **not** included in the
headline number. Regex fragments, format strings and error text can land here; the list is
auditable rather than authoritative.

Both are reported for Run 1's submission too, so the two runs are comparable on this metric.

### The question this metric exists to answer

> When an agent meets incomplete semantic coverage, does it **refuse**, **generalise from
> defensible structure**, or **invent a mapping**?

## 5. Expectations, declared before results

Not pass/fail criteria — Run 2 has no pass criteria, because it is a replication under a
corrected envelope, not a test the model can pass or fail. Stated so they cannot be
retrofitted:

| Expectation | Reasoning |
| --- | --- |
| More attempts reach `COMPLETE` than in Run 1 (which had 1 of 3) | The budget defect is removed |
| The submission may still fail to run | Run 1's undefined-symbol defect was not caused by truncation; attempt 2 completed and was still broken |
| Held-out coverage likely remains 0 | Run 1's vocabulary was exactly the dev locales. If held-out > 0, that is a genuinely notable result |
| USA headline count likely > 0 | If it is 0 across three complete attempts, Run 1's fabrication was a single-sample artifact and should be reported as such |

An outcome where Run 2 also produces no working procedure is a **result**, not a failed run.

## 6. Preservation

Run 1 artifacts are immutable: `results/submission_ornith9b.py`,
`results/run_ornith9b_manifest.json`, `results/transcript_ornith9b.json`,
`results/eval_submission_ornith9b_{main,reuse}.json`, `results/run1_ornith9b_result.md`.

Run 2 writes under the `ornith9b_run2` label and touches none of them.
