# Experiment 2 — A′ / B′ 2×2 completion study

**Result: all four cells fail. Not one submission in A′ or B′ loads. Zero rows everywhere,
across every condition, seed and model in the entire experiment.**

Executed exactly as preregistered (`e42ffe8`). Six seed-conditions, no early stopping, no
intervention. Frozen artifacts and digest verified before every run.

---

## 1. The 2×2, filled in

| | **12 sources** | **1 source (D04, 77% smaller prompt)** |
| --- | --- | --- |
| **No warm-up** | **A** — 2/3 loaded, ran, returned empty frames | **A′** — **0/3 load** |
| **Warm-up** | **B** — 0/3 load | **B′** — **0/3 load** |

### The four preregistered deltas

| Comparison | Measures | Result |
| --- | --- | --- |
| **B − A** | warm-up effect, large prompt | **worse** (2 loadable → 0) |
| **B′ − A′** | warm-up effect, small prompt | **no difference** (0 → 0) |
| **A′ − A** | prompt-size effect, no warm-up | **worse** (2 loadable → 0) |
| **B′ − B** | prompt-size effect, with warm-up | **no difference** (0 → 0) |

## 2. Which decision rule fires

Preregistered options were: both improve → context was the bottleneck; A′ works and B′ worse →
warm-up anchors; B′ beats A′ → guided experience transfers.

**None of those. The fourth rule fires:**

> **Both still fail → stop squeezing this 9B setup and move to a stronger model or a different
> agent scaffold before testing reference knowledge.**

And the study delivered what it was built for: **context load is not the explanation.** Cutting
the prompt by 77% did not help. It coincided with A getting *worse*, not better.

## 3. Per-cell detail

| Cell / seed | Warm-up | Pipeline (final submission) | Outcomes | Correctness |
| --- | --- | --- | --- | --- |
| A′ 11111 | n/a | parses **False** | `load_error` ×25 | 0.0 |
| A′ 22222 | n/a | parses **False** | `load_error` ×25 | 0.0 |
| A′ 33333 | n/a | parses **False** | `load_error` ×25 | 0.0 |
| B′ 11111 | **FAIL** 3/3 | parses **False** | `load_error` ×25 | 0.0 |
| B′ 22222 | **PASS** att.1 | parses **False** | `load_error` ×25 | 0.0 |
| B′ 33333 | **PASS** att.3 | parses **False** | `load_error` ×25 | 0.0 |

Held-out, ambiguity and reuse are 0.0 throughout. `Escalate` and `AskHuman` remain unused —
now across **325 file-evaluations**, four conditions, two models, and every seed.

USA taxonomy: **unmeasurable** in all six cells. No submission parses, so the AST analysis cannot
run. Not zero — unmeasurable.

## 4. The six-stage pipeline earns its place again

`api = stop` on 16 of 18 attempts across these six runs, while `PYTHON_PARSEABLE = False` on 17
of 18. The retired binary classifier would have logged almost every attempt as `COMPLETE`.

Two attempts (A′ 22222, attempts 2–3) show `SUBMISSION_EXTRACTED = False` with
`lenient = True` — an unclosed fence again. Lenient extraction also fails to parse, so the
extractor limitation is again real and again not the cause.

## 5. An artifact-selection finding, reported without changing the rule

**A′ seed 11111 attempt 2 produced parseable Python. Attempt 3 replaced it with code that does
not parse.**

The protocol takes the last attempt that yields a block, so the parseable intermediate was
overwritten. That rule was fixed in advance and is **not** being changed retroactively — doing so
would be post-hoc artifact selection.

Reported as a labelled **off-protocol diagnostic**, because "was it ever close?" is worth
answering: running that intermediate against all 25 variants gives `error ×25`, **max rows 0**.

So the iteration loop degraded a parseable artifact into an unparseable one, and the parseable
one would have scored zero anyway. The feedback loop is not merely failing to help — on this
seed it actively destroyed the best artifact the model produced.

## 6. What the whole experiment now establishes

Across **four conditions, two models, twelve modelling runs**:

1. **Zero rows of correct canonical output. Ever.** No condition, seed or model produced a single
   correct canonical row.
2. **Context load is not the bottleneck.** A 77% prompt reduction changed nothing, and coincided
   with degradation.
3. **A worked example is not the bottleneck.** Warm-up passed for 4 of 6 seeds that attempted it;
   phase 2 failed regardless.
4. **The refusal channel is never used.** 325 file-evaluations, including inputs built to be
   unresolvable. Offering `Escalate` in the contract and demonstrating it in the warm-up
   instructions changed nothing.
5. **The binding constraint is emitting syntactically valid Python of the required size.** The
   failure has moved steadily earlier: A failed at extraction, B/A′/B′ fail at *parsing*.

## 7. What it does not establish

- **Nothing about the task's tractability for capable models.** The oracle reference solves it;
  it has vocabulary access no submission gets. Twelve failed runs on 9B local models bound the
  models, not the task.
- **The reference-data hypothesis is still untested.** It was never in scope for A/B/A′/B′.
- **Nothing about scaffolding.** A single-shot "write the whole module" protocol may be the wrong
  shape. An agent that could run code itself, inspect one file at a time, and build incrementally
  is a different experiment.

## 8. Recommendation

**Do not run Condition C on this setup.** It would measure reference knowledge against a model
that cannot reliably emit a parseable module, and a null result would be uninterpretable.

The preregistered next step is the one the evidence selects: **a stronger model, or a different
agent scaffold.** Only once some configuration clears the syntactic floor does testing reference
knowledge measure reference knowledge.

Seed 11111's repeated failure on the eight-row warm-up — a four-column rename with explicit
instructions and execution feedback — remains the cleanest single indicator that this ceiling is
not about locale semantics.
