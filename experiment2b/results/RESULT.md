# Experiment 2B — Header Row Discovery: Result

**Both tests pass. E1 correct, R1 correct.**

First non-zero result in the entire Experiment 2 programme.

---

## Results

| Test | Expected | Reported | Correct | API finished | Content | JSON parseable | Valid structured output |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **E1** easy | 4 | **4** | **yes** | `stop` | yes | yes | yes |
| **R1** regular | 5 | **5** | **yes** | `stop` | yes | yes | yes |

Raw replies, in full:

```
E1:  {"header_row": 4}
R1:  { "header_row": 5 }
```

Nothing else. No prose, no fence, no explanation — the exact shape requested.

## Run identity

| | |
| --- | --- |
| Model | `qwen3.5:9b`, digest `6488c96fa5faab64…` |
| Family / size / quant | `qwen35`, 9.7B, Q4_K_M |
| Ollama | 0.32.6 |
| Thinking | disabled |
| Seed | 20260809 |
| Sampling | temperature 0.6, top_p 0.95, top_k 20 |
| Budget | `num_ctx` 8192, `num_predict` 2048 |
| Runs | one per test |

Digest verified against the frozen value before each call. Fixtures committed at `cff2004`
before either test ran.

## What R1 required

R1 was not a restatement of E1. Getting row 5 meant stepping over:

- a Finnish title row (`Myyntiraportti`);
- a metadata row with two cells (`Asiakas: Esimerkki Oy | Vuosi: 2026`);
- a free-text generation-date row containing a date (`Raportti muodostettu 31.12.2026`);
- a blank row;

and then selecting a header row whose cells are **Finnish abbreviated month names** —
`Tuote | Tammi | Helmi | Maalis | Huhti | Touko | Kesä`.

The model was told nothing about month names, locale, numeric rows, keyword lists, type
inference or position. It was given the rows, the question, and the output shape.

## Why this matters against Experiment 2A

Experiment 2A concluded that the binding constraint was *emitting syntactically valid Python of
the required size*, not data understanding — and that the intended question was never actually
reached.

**This result supports that reading. It does not confirm it.** The same model, at the same
quantization, with the same sampling settings, correctly located a header row inside cluttered,
Finnish-localized business input on the first attempt, and returned perfectly-formed JSON while
doing it.

What is demonstrated: the model possesses **at least this** source-understanding capability when
the output burden is tiny.

What is **not** demonstrated: that code emission was the *only* thing preventing 2A from
succeeding. 2A required structure inference, semantic mapping, locale normalization, generalization
and refusal on top of module synthesis. Showing that one of those sub-abilities survives a
low-output-burden setting does not establish that the others would have.

## What this establishes

Only this: **the header row is identified correctly in the easy and the regular example.**

It does **not** establish schema understanding, locale normalization, wide/long recognition,
semantic mapping, procedure synthesis, or Excel competence generally. Two samples, one seed,
one model. It is a capability check, not a measurement of reliability — a single run cannot
distinguish "can do this" from "did this once."

## Decision rule — which branch fires

Preregistered options were: E1 fails → stop; E1 passes and R1 fails → vary header difficulty
only; both pass → proceed exactly one step.

> **Both pass. Proceed one step: *which columns represent months?***

Explicitly **not** a return to full normalization. One more fact.

## Recommended shape for the next probe

Same discipline, unchanged:

- same two fixtures, so the input is a constant and only the question moves;
- the header row **given** this time, since 2B established it can be found;
- one question: which columns are months;
- a tiny structured answer, e.g. `{"month_columns": [1, 2, 3, 4]}`;
- **no** hint about how — no month lists, no locale detection, no positional rules;
- frozen expected answers before running;
- one seed, thinking disabled, digest-verified.

R1 is the interesting case there for the same reason it was here: the month names are Finnish
abbreviations, and nothing tells the model that.

Worth deciding in advance, because it will otherwise be decided after seeing the answer: whether
the expected column indices are 0-based or 1-based, and whether the product column is expected
to be excluded. Both must be fixed in the preregistration.

---

# Probe 2B.2 — Month-column identification: Result

**Both tests pass.**

| Test | Given header | Expected | Reported | Correct | API | JSON | Valid | ask_human |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **E1** | row 4 | `[2,3,4,5]` | **`[2,3,4,5]`** | **yes** | `stop` | yes | yes | no |
| **R1** | row 5 | `[2,3,4,5,6,7]` | **`[2,3,4,5,6,7]`** | **yes** | `stop` | yes | yes | no |

Raw replies, in full:

```
E1:  {"month_columns": [2, 3, 4, 5]}
R1:  {"month_columns": [2, 3, 4, 5, 6, 7]}
```

Exact set match, correct 1-based numbering, identifier column correctly excluded in both. No
prose, no fence, no escape hatch taken.

## The R1 result is the substantive one

R1's header is `Tuote | Tammi | Helmi | Maalis | Huhti | Touko | Kesä`.

The model was given **no month vocabulary in any language**, no locale hint, no positional rule
and no type inference guidance. It identified all six Finnish abbreviated month names as months,
and correctly excluded `Tuote` — a Finnish word for *product* it was equally never taught.

This is a stronger claim than 2B.1. Locating row 5 could in principle rest on structural cues:
the first row followed by numeric data, the widest row, the row after the blank. Identifying
which of its cells are months, and which one is not, requires recognising the **semantic role**
of header cells in a language the model was given nothing about.

## Capability boundary so far

```text
2B.1  locate header            PASS  (E1, R1)
2B.2  identify month columns   PASS  (E1, R1)
```

Four probes, four passes, four perfectly-formed structured answers, zero escape hatches.

## What this does and does not establish

**Establishes:** on these two fixtures, this model locates the header row and identifies which of
its columns are months, including Finnish abbreviations, without being taught how.

**Does not establish:** reliability. Two fixtures, one seed, one run per probe. A single run
cannot separate *can do this* from *did this once*. Nor does it establish wide/long recognition,
value normalization, grain reasoning, procedure synthesis, or refusal behaviour — the escape
hatch was available and never exercised, so nothing has been learned about whether the model
would decline a genuinely undecidable case.

**On Experiment 2A:** this continues to *support* the reading that 2A's failures landed on code
emission rather than data understanding. It still does not confirm it. Two sub-abilities
surviving a low-output-burden setting is not evidence that the remaining ones would have.

## Recommended next step

The escape hatch has now been offered twice and never used, on two tests where using it would
have been wrong. That is the right behaviour but it is untested in the direction that matters.

The natural next probe is therefore either:

1. **the same question on an undecidable input** — a header row where a column genuinely cannot
   be classified from the evidence, where `{"ask_human": true}` is the *correct* answer; or
2. **one more capability step** — e.g. which column holds the identifier, or what period a given
   month column denotes.

Option 1 is more valuable. Four passes in a row on resolvable inputs tell us the model answers;
they tell us nothing about whether it knows when not to. Given that `Escalate` went unused across
325 file-evaluations in Experiment 2A, refusal is the least-evidenced behaviour in the entire
programme.
