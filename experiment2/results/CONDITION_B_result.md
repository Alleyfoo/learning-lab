# Experiment 2 — Condition B: guided warm-up, then unseen task

**Result: every Condition-B submission is syntactically invalid Python. Not one loaded.
Condition B is worse than Condition A on all three paired seeds.**

Executed exactly as preregistered (`83ce437`). All three seeds run, no early stopping, no
intervention. Phase-2 prompt hash verified identical to Condition A's per seed. Frozen artifacts
verified before every seed.

---

## 1. Per-seed report, paired against Condition A

| | **seed 11111** | **seed 22222** | **seed 33333** |
| --- | --- | --- | --- |
| **Warm-up** | **FAIL** (3/3 attempts) | **PASS** (attempt 1) | **PASS** (attempt 3) |
| Boundary message delivered | no | yes | yes |
| Phase-2 completion | 1 COMPLETE, 2 TRUNCATED | 3 COMPLETE | 1 TRUNCATED, 2 COMPLETE |
| Submission produced | 284 lines | 217 lines | **none** |
| Loads? | **No** — `IndentationError` line 164 | **No** — `SyntaxError` line 123 | n/a |
| Non-empty output | **no** (`load_error` ×25) | **no** (`load_error` ×25) | n/a |
| dev / held-out / ambiguity / reuse | 0.0 / 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 / 0.0 | n/a |
| `Escalate` / `AskHuman` used | **0** | **0** | n/a |
| USA taxonomy | **unmeasurable** (won't parse) | **unmeasurable** (won't parse) | n/a |

### Delta against the same seed in Condition A

| Seed | Condition A | Condition B | Δ |
| --- | --- | --- | --- |
| 11111 | 30 lines, loaded, returned `None` → `schema_error` ×25 | 284 lines, **won't load** | **worse** |
| 22222 | 192 lines, loaded, ran on 13/25, empty frames | 217 lines, **won't load** | **worse** |
| 33333 | 171 lines, loaded, ran on **25/25**, empty frames | **no submission at all** | **worse** |

Condition A's best seed ran on every file. Its Condition-B counterpart produced nothing usable.

## 2. Which of the four predicted outcomes occurred

Not the interesting ones. **One demonstrated success did not transfer** — and it did worse than
that. For the two seeds where the warm-up genuinely passed and the boundary message was
delivered, phase 2 produced *longer, more ambitious, syntactically broken* code.

- Phase 2 never produced meaningful rows.
- Refusal never appeared. `Escalate` and `AskHuman` remain unused across **every run of this
  experiment** — now 175 file-evaluations spanning three conditions and two models.
- Rambling and truncation persisted: 3 of 9 phase-2 attempts truncated, one at 142,143 chars.

## 3. The seed-33333 non-submission — verified, not assumed

Seed 33333 produced no submission because all three phase-2 replies **open a ```python fence and
never close it**, ending mid-identifier (`period_col_name`, `cn_str`) — including on attempts
where `done_reason = "stop"`.

My extractor requires a closing fence. That is a real limitation, and after Run 1's `num_predict`
mistake I tested it rather than assuming: a **lenient** extractor that takes everything after the
opening fence yields

```
attempt 1: SyntaxError, expected an indented block, line 230
attempt 2: SyntaxError, invalid syntax, line 95
attempt 3: SyntaxError, invalid syntax, line 95
```

**Lenient extraction would not have salvaged this seed.** The content is syntactically incomplete
regardless of how it is delimited. The extractor limitation is real and did not affect this
result.

## 4. A confound I introduced, stated plainly

The preregistration says phase-1 context is retained and "that retention is the treatment." True
as designed — but it means **Condition B's phase-2 context is strictly larger than Condition A's**:
the warm-up exchange *plus* the byte-identical 20k-token prompt.

So B − A is not purely "guided experience." It is "guided experience **and** a longer context."
Given that both models' dominant failure mode is unbounded generation on a long prompt, context
load is a live competing explanation for B being worse.

**This makes Condition B′ necessary rather than optional.** B′ — warm-up then a *single* unseen
source — reduces context instead of enlarging it, and separates the two effects.

## 5. Warm-up failure on seed 11111 is itself a finding

Seed 11111 failed the warm-up on all three attempts. The warm-up is an 8-row file that is already
long-form, already ISO periods, already ISO country codes, already plain numbers. The entire task
is renaming four columns.

A model that cannot reliably pass that is not going to normalize wide Finnish month headers, and
this reframes the Condition-A result: the ceiling is lower than "couldn't discover the locale
mapping."

Its Condition-B result is reported here but **is not pooled** with the warmed-up seeds, per the
preregistration — a failed warm-up is not a warm-up.

## 6. USA taxonomy — unmeasurable this condition

Both Condition-B submissions fail to parse, so the AST-based analysis cannot run. Reported as
**unmeasurable**, not as zero. A syntactically invalid file has not been shown to contain no
unsupported assertions; it has not been shown to contain anything.

## 7. What Condition B establishes

1. **Task induction from one worked example did not help this model.** On paired seeds, with the
   graded prompt and data byte-identical, results got worse.
2. **The failure has moved earlier in the pipeline.** Condition A failed at *extraction* —
   loadable code that returned nothing. Condition B fails at *syntax* — code that will not load.
   The warm-up appears to have encouraged more ambitious code than the model can emit validly.
3. **The refusal channel remains completely unused**, across every condition, model and seed.
   Teaching phase-1 the words "use Escalate or AskHuman", and confirming success, changed nothing.
4. **Non-termination is not explained by thinking**, and is now not explained by lack of a worked
   example either.

## 8. What it does not establish

- **Not that guided warm-up is useless in general.** The context-size confound (§4) is
  unresolved, and B′ is the way to resolve it.
- Nothing about larger models. Three conditions have now been run on 9B local models only.
- The USA question for this condition is open, not answered.

## 9. Status of the three-condition programme

```text
A  CLOSED BOOK          done  - zero rows everywhere, both models
B  GUIDED WARM-UP       done  - worse than A on all three paired seeds
B' WARM-UP + 1 SOURCE   not run - now REQUIRED to separate warm-up from context load
C  REFERENCE-AUGMENTED  not run
```

The reference-data hypothesis from the Qwen arm is **untouched by this result** — Condition B
tested task induction, not reference knowledge. Condition C remains the test of that hypothesis,
and B′ should precede it so that the context-load explanation is closed off first.
