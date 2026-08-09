# Experiment 2 — A′ + B′ Preregistration: the 2×2 completion study

**Declared before execution of either arm. Nothing below changes after results are seen.**

Conditions A and B are frozen. A′ and B′ are preregistered **together**, because running B′
alone would not isolate anything.

---

## 1. The design

```text
                    12 SOURCES        1 SOURCE
NO WARM-UP              A                A′
WARM-UP                 B                B′
```

A and B are done. A′ and B′ complete the cell set, giving four comparisons:

```text
B  − A    warm-up effect under large prompt      (measured: worse)
B′ − A′   warm-up effect under small prompt
A′ − A    prompt-size effect without warm-up
B′ − B    prompt-size effect with warm-up
```

Without A′, a working B′ would be uninterpretable: warm-up or fewer sources, no way to tell.

## 2. The single source — selected by rule, committed before running

**Rule:** the first development profile in manifest order that is information-preserving
(`equivalent = true`) and differs from the warm-up in **both** naming (`header_lang`) and
representation (any of `shape` / `month_style` / `country_style` / `number_style`).

Applied mechanically. D01–D03 and D08–D12 are skipped for English headers (no naming
difference); D01 additionally matches the warm-up on every representation axis.

> **Selected: `D04`** — Finnish headers (`maa`, `tuote`, `kausi`, `myynti`), `period_value`
> shape, `MM/YYYY` periods, endonym countries (`Suomi`, `Česko`, `Sverige`, `Deutschland`),
> EU-dot numbers (`1.234,50`).

Not chosen by eyeballing which looked easiest. The derivation is reproducible from
`corpus_manifest.json`.

Prompt sizes, verified: full **30,052 chars**, D04-only **7,061 chars** — a **77% reduction**.
The full prompt hash is unchanged from A and B (`3c286bad748b27a7…`).

## 3. One-source input does **not** mean one-source scoring

A′ and B′ expose one source. The unchanged evaluator still runs the submitted procedure against
**all 25 variants** — dev, held-out, ambiguity — plus the full reuse corpus. Scoring is identical
to A and B in every respect.

That is the point: does a procedure induced from a single example generalise?

## 4. Held constant across all four cells

| | |
| --- | --- |
| Model | `qwen3.5:9b`, digest `6488c96fa5faab64…` |
| Thinking | disabled |
| Seeds | **11111, 22222, 33333** — same three, paired across all cells |
| `num_ctx` / `num_predict` | 65536 / 32768 |
| temperature / top_p / top_k | 0.6 / 0.95 / 20 |
| Attempts (real phase) | 3 |
| Warm-up (B′ only) | identical file, identical instructions, identical boundary message |
| Independence | one process per seed-condition, fresh context, no cross-seed feedback |
| Task packet, corpus, evaluator, executor, oracle | frozen, hash-guarded |

**Six runs:** A′ × 3 seeds, B′ × 3 seeds.

## 5. Completion-classifier correction — recorded, prior results annotated not rewritten

The binary `COMPLETE` / `TRUNCATED` classifier is retired. Condition B seed 33333 returned
`done_reason = "stop"` on attempts whose content ended **inside an identifier** with an unclosed
code fence. The API said finished; the artifact was not. One boolean cannot carry both facts.

Replaced by a six-stage pipeline, each stage an independent fact:

```text
API_FINISHED          stop vs length
CONTENT_PRESENT       yes/no
SUBMISSION_EXTRACTED  yes/no          (strict and lenient both recorded)
PYTHON_PARSEABLE      yes/no          (strict and lenient both recorded)
MODULE_LOADABLE       yes/no
PROCEDURE_EXECUTABLE  yes/no
```

`harness/completion_pipeline.py` runs post hoc from a transcript plus its submission, so it
applies to **every run already recorded**. Prior outcomes are annotated, never rewritten.

It already earns its place: `qwenB_s22222` shows `api=stop`, legacy `COMPLETE`, and
`PYTHON_PARSEABLE = False` on all three attempts. The legacy label said the model finished; the
pipeline says it never produced parseable Python.

Both strict and lenient extraction are recorded at every stage so that an extractor limitation
can never again be mistaken for a model result.

## 6. Measurements

Per seed-condition: the six-stage pipeline, then — unchanged — output correctness, format
coverage by family, held-out generalization, correct refusal, incorrect canonicalization,
unnecessary escalation, reuse, human questions, and the USA taxonomy
(INERT / VINDICATED / CONSEQUENTIAL_RISK).

Warm-up pass/fail recorded for B′. Warm-up-failed seeds reported separately, never pooled.

USA is reported **unmeasurable** where a submission does not parse — not zero.

## 7. Decision rules, declared in advance

| Outcome | Reading | Next |
| --- | --- | --- |
| A′ **and** B′ improve markedly | Context load was a major bottleneck | Prompt size is a first-class design variable; revisit A and B at reduced load |
| A′ works, B′ worse | The warm-up itself interferes or anchors | Guided experience is not free; investigate anchoring |
| B′ beats A′ | **Guided experience genuinely transfers when context is manageable** | The strongest positive result available; then run C |
| Both still fail | Stop squeezing this 9B setup | Move to a stronger model or a different agent scaffold **before** testing reference knowledge |

That last row matters most. **Condition C is not run yet**, deliberately: if C ran now it would
have to carry three unresolved explanations at once — reference knowledge, context load, and
task induction. This study removes two of them.

## 8. Standing interpretation of B, unchanged by this study

Two seeds received the treatment successfully — the warm-up passed and the boundary message was
delivered — and both then produced worse artifacts. B cannot be explained away as "they never
understood the example."

> Under the large-context condition, a demonstrated successful example did not improve transfer
> and may have increased procedural ambition faster than code reliability.

The second clause remains a **hypothesis** until A′/B′ reports whether context size is
responsible.

Separately: seed 11111 failed an eight-row ISO long-form rename, with explicit instructions and
feedback. Until that is understood, locale semantics should not be blamed for this model's
ceiling.
