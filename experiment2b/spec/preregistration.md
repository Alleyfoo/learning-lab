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
