# Experiment 2B — Header Row Discovery: Preregistration

**Both fixtures frozen and committed before either test runs.**

## Question

> Which row contains the headers for the actual data table?

Nothing else is tested. This is the lowest useful source-understanding capability, isolated.

## Why

Experiment 2A asked for structure inference, semantic mapping, locale normalization, module
synthesis, debugging, generalization and refusal — all at once. Across four conditions, two
models and twelve runs it produced zero rows of correct output, and the failures landed on
*emitting parseable Python* rather than on data understanding. The intended question was never
reached.

## Scope

Two single-table inputs. Explicitly excluded: multiple sheets, joins, wide-to-long, country
normalization, numeric normalization, schema generation, Python module generation, reusable
procedures, reference datasets. **The experiment ends at header-row identification.**

## Model

`qwen3.5:9b`, thinking disabled, one seed. A capability check, not a statistical comparison.
Exact tag, digest, Ollama version, seed and generation settings recorded with each result.

## Input representation

Harness converts CSV to a neutral row listing deterministically (`harness/render_rows.py`).
Row numbers are 1-based file positions; blank rows are counted and rendered `(empty)`.
The model never needs to write code to inspect anything. That conversion is infrastructure,
not part of the agent task.

## Tests — both frozen now

| Test | Role | Expected `header_row` |
| --- | --- | --- |
| **E1** | easy positive control | **4** |
| **R1** | regular / realistic | **5** |

Taken verbatim from the workorder. R1 is fixed here so it cannot be designed after seeing E1's
result. Expected answers live in `fixtures/expected.json`, never shown to the model.

## What the model is told

The rows, the question, and the required output shape:

```json
{"header_row": <integer>}
```

**Nothing about how to find a header row.** No mention of month names, numeric rows, keyword
lists, locale detection, type inference or positional rules. Those are candidate strategies;
choosing one is the model's job.

Only `header_row` is scored. A `confidence` field is accepted if offered and ignored.

## Recorded per test

`expected_header_row`, `reported_header_row`, `correct`, `valid_structured_output`, plus
`api_finished`, `content_present`, `json_parseable`.

The Experiment 2A module pipeline is deliberately absent — no code artifact is requested.

## Decision rule — declared before running

| Outcome | Action |
| --- | --- |
| **E1 fails** | **STOP.** The model/scaffold does not clear the simplest positive control. Do not run R1, do not make anything harder, and infer nothing about multilingual or irregular spreadsheets |
| **E1 passes, R1 fails** | Basic header identification exists but does not transfer to ordinary cluttered/localized input. Next experiment varies header-location difficulty only |
| **Both pass** | Proceed exactly one step: *which columns represent months?* Do not jump back to full normalization |

## Success criterion

Success means only that the header row is identified correctly in both examples. It establishes
nothing about schema understanding, locale normalization, wide/long recognition, semantic
mapping, procedure synthesis, or Excel competence generally.

## Principle

Increase responsibility one fact at a time.

```text
INPUT -> Where are the headers? -> ANSWER
```

---

# Probe 2B.2 — Month-column identification

**Frozen before running. 2B.1 is complete and unchanged.**

## Question

> The data header is row N. Which columns in that header represent months?

**The header row is given.** 2B.1 established it can be found; rediscovering it is not part of
this test. That keeps the capability boundary clean:

```text
2B.1  locate header           PASS
2B.2  identify month columns  ?
```

## Answer contract — both grading ambiguities removed in advance

- **Column numbering is 1-based from the leftmost displayed column.** Chosen because it matches
  how a human reading the rendered table counts columns.
- **Return only columns representing calendar months.** Do not include identifier, metadata,
  total, or other non-month columns.
- Scoring is an **order-insensitive exact set match**.

```json
{"month_columns": [2, 3, 4, 5]}
```

These are contract statements — they disambiguate what counts as an answer. They say nothing
about how to recognise a month, and no month-name list, locale hint, positional rule or type
inference is provided.

## Escape hatch, retained

```json
{"ask_human": true}
```

Same interpretation as before: on these two deliberately resolvable tests it **does not count as
a capability pass**, but it remains preferable to confidently selecting the wrong columns. It is
recorded distinctly from a wrong answer.

## Expected answers — frozen, never shown to the model

| Test | Given header row | Header cells | Expected |
| --- | --- | --- | --- |
| **E1** | 4 | `Product \| January \| February \| March \| April` | **[2, 3, 4, 5]** |
| **R1** | 5 | `Tuote \| Tammi \| Helmi \| Maalis \| Huhti \| Touko \| Kesä` | **[2, 3, 4, 5, 6, 7]** |

Excluded in both cases: column 1 (`Product` / `Tuote`), the identifier.

Same two fixtures as 2B.1, unchanged, so the input is a constant and only the question moves.

## Why R1 is the interesting case

The month names are **Finnish abbreviations** — `Tammi`, `Helmi`, `Maalis`, `Huhti`, `Touko`,
`Kesä` — and nothing tells the model that. Getting `[2,3,4,5,6,7]` would show it can identify the
**semantic role** of header cells in a language it was never given vocabulary for.

That is a materially stronger claim than "it can find row 5". A failure is equally useful: it
locates the first capability boundary precisely, with no traceback required.

## Settings

Identical to 2B.1: `qwen3.5:9b`, digest verified, thinking disabled, seed 20260809,
temperature 0.6 / top_p 0.95 / top_k 20, one run per test.
