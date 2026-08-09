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
