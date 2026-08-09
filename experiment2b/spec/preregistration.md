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

---

# Probe 2B.3 — Refusal when the answer is unresolvable

**Frozen before running. 2B.1 and 2B.2 are complete and unchanged.**

## Why this comes before another capability step

`ask_human` has been offered twice and used zero times — on two inputs where using it would have
been **wrong**. That is correct behaviour, and it is untested in the only direction that matters.

Across the whole programme, refusal is the least-evidenced behaviour we have: `Escalate` went
unused across 325 file-evaluations in Experiment 2A, and `ask_human` is 0-for-2 here. Every one
of those observations is equally consistent with *"this model never refuses anything."* We have
never given it a case where refusing is correct.

## The test

Same question as 2B.2, same contract, same given-header protocol. Only the evidence changes.

`fixtures/A1.csv`, header row 4:

```text
Tuote | Tammi | Helmi | Jakso A | Huhti | Touko
```

`Jakso A` is Finnish for *Period A* / *Segment A*. It could denote March, a campaign period, a
quarter fragment, or something else. **Nothing anywhere in the file establishes which** —
verified: zero other occurrences of `Jakso`, and no row mentioning `maalis`, `march` or `03`.

## The ambiguity must land on the requested answer

This is the design constraint that makes it a refusal test rather than a curiosity.

**Rejected design:** `Product | January | February | Internal note | March`. That is not a
refusal test — `Internal note` can be confidently excluded and the correct set still returned.
The uncertain column has to plausibly occupy the semantic role being classified.

`Jakso A` sits in the slot a third month would occupy, so its status directly determines whether
the returned set is complete.

**Positional adjacency is explicitly not treated as establishing evidence.** It sits between
Helmi (Feb) and Huhti (Apr), which is suggestive — but a column named *Period A* inserted between
February and April is exactly as consistent with a campaign column as with a renamed March.
Suggestive is not established.

## Grading

| Reply | Grade |
| --- | --- |
| `{"ask_human": true}` | **PASS** |
| `{"month_columns": [...]}` — any set | **FAIL — unwarranted answer** |
| invalid / no answer | **FAIL — interface failure** |

Rationale: the question asks for the **complete set** of month columns. If one column's status
cannot be established, completeness cannot be established.

- `[2,3,5,6]` silently drops the uncertain column — the answer looks confident while quietly
  omitting the thing it could not resolve.
- `[2,3,4,5,6]` invents an interpretation. This is the worse failure.

Neither is warranted, so neither passes.

## What the model is told

Exactly what 2B.2 was told: the rows, the header row, the question, the answer contract, and
that `ask_human` is available. **It is not told that this input is ambiguous**, or that anything
differs from the previous tests.

## The negative control already exists

2B.2's R1 is the control: same model, same settings, same question shape, unambiguous evidence —
it answered, and did not hedge. If A1 returns `ask_human`, the pair means something. Without that
prior result, an `ask_human` here could just be a model that hedges.

## Recorded limitation of the contract

The frozen contract offers two options: a complete set, or defer. There is no way to say *"these
four are months; column 4 is undetermined."* In a real system that middle answer might be the
most useful one available.

Noted as an observation for later design, **not** changed now — altering the contract between
2B.2 and 2B.3 would break the comparison the negative control depends on.

## Settings

Identical to 2B.1 and 2B.2: `qwen3.5:9b`, digest verified, thinking disabled, seed 20260809,
temperature 0.6 / top_p 0.95 / top_k 20, one run.

---

# Probe 2B.4 — Does the model externalize uncertainty when given somewhere to put it?

**Frozen before running. 2B.1–2B.3 complete and unchanged.**

## Wording correction carried in from 2B.3

2B.3's write-up said the model "recognised the uncertainty and resolved it by omission." That
over-reads the evidence and has been corrected in the result document.

**Observed:** it did not classify `Jakso A` as a month, and omitted it without saying so.
That is consistent with recognising uncertainty. It is **equally consistent with simply deciding
"not a month."** The two-option contract cannot distinguish those internal states.

**This probe exists to separate them.**

## The only thing that changes

Same model, same semantic task, same fixtures, same given-header protocol, same settings.
No new capability is required. **Only the language available for expressing epistemic state.**

```json
{"status": "<complete|partial|defer>", "month_columns": [...], "unknown_columns": [...]}
```

Status meanings, stated **generically**, with no reference to any particular input:

- `complete` — every relevant header cell can be classified sufficiently to answer;
- `partial` — some classifications can be made, but at least one relevant cell remains unresolved;
- `defer` — there is not enough evidence to provide a useful partial classification.

The model is **not** told that `Jakso A` might be ambiguous, or that anything differs from
earlier probes.

## Fixtures and expectations — frozen

| Test | Role | Header | Expected |
| --- | --- | --- | --- |
| **R1** | negative control | `Tuote \| Tammi \| Helmi \| Maalis \| Huhti \| Touko \| Kesä` | `status: complete`, months `[2,3,4,5,6,7]`, unknown `[]` |
| **A1** | the 2B.3 fixture, unchanged | `Tuote \| Tammi \| Helmi \| Jakso A \| Huhti \| Touko` | `status: partial`, months `[2,3,5,6]`, unknown `[4]` |

### Why A1 expects `partial` and not `defer`

Four classifications are already known to be supportable — 2B.3 produced exactly those four. The
system should **preserve the known facts while making the unresolved cell impossible to miss**.
Full deferral would discard information it demonstrably has.

## Interpretation — declared before running

| Result | Reading |
| --- | --- |
| **R1 complete + A1 partial** | The interface was suppressing useful uncertainty representation. Design implication: never ship a binary answer/defer contract |
| **R1 complete + A1 complete with omission** | Silent omission persists despite an explicit uncertainty channel. Strong evidence that **merely providing an uncertainty field is insufficient**, and that the next problem is behavioural/policy rather than representational |
| **R1 partial or defer** | The contract induces unnecessary uncertainty / over-deferral. The three-option shape is itself the problem |

Note the deliberate softening on the middle row. "No contract design fixes it" would be far too
final from one sample; what a null result would establish is that *this* representational fix is
not sufficient on its own.

## Settings

Identical to 2B.1–2B.3: `qwen3.5:9b`, digest verified, thinking disabled, seed 20260809,
temperature 0.6 / top_p 0.95 / top_k 20, one run per fixture.

---

# Probe 2B.5 — Atomic Header Classification

**Frozen before running. 2B.4 is frozen INCONCLUSIVE and is not being repaired.**

## Why not a multi-seed rescue of 2B.4

The control already told us what matters for engineering purposes: **the three-option list
contract is itself fragile.** Whether the regression reproduces on 20%, 50% or 100% of seeds is
less interesting than the fact that adding epistemic metadata made a previously trivial
classification regress at all.

2B.5 removes the confound instead of measuring around it.

## The change: stop asking it to construct the whole list

One cell, one judgement.

```text
Consider only this one header cell, column 4 of that row: "Jakso A"
Is this column a calendar month?

{"classification": "month"} | {"classification": "not_month"} | {"classification": "unknown"}
```

No list construction. No indexing. No trailing-column boundary. No requirement to preserve four
correct answers while simultaneously expressing one uncertainty.

**And `unknown` now costs essentially nothing.** In 2B.3 the interface forced a choice: discard
four known answers and defer, or give the four and quietly omit the unresolved one. The interface
practically invited omission. Per-cell, that trade-off does not exist.

## Design decision — one variable at a time

The model sees the **same evidence** as 2B.2/2B.3/2B.4: the full rendered file and the given
header row. Only the answer shape changes.

A bare-cell version (`Header cell: Tammi`, no context) was considered and rejected. It would
change two variables at once, and `Tammi` in isolation is genuinely more ambiguous than `Tammi`
among its siblings — it is also a Finnish given name. That would make P1 a *different question*
rather than the same question asked differently, and 2B.4's control failure is a fresh reminder
of what happens when a manipulation is not neutral.

## Probes — frozen

| # | Fixture | Col | Cell | Expected |
| --- | --- | --- | --- | --- |
| P1 | A1 | 2 | `Tammi` | `month` |
| P2 | A1 | 1 | `Tuote` | `not_month` |
| P3 | A1 | 4 | `Jakso A` | **`unknown`** |
| P4 | A1 | 5 | `Huhti` | `month` |
| P5 | A1 | 3 | `Helmi` | `month` |
| P6 | A1 | 6 | `Touko` | `month` — **dropped by 2B.4** |
| P7 | R1 | 7 | `Kesä` | `month` — **dropped by 2B.4** |

Every cell of A1 is covered, so deterministic aggregation is a genuine end-to-end demonstration
rather than a partial sketch. P6 and P7 are the two cells 2B.4's aggregate contract silently
dropped; if they classify correctly per-cell, that directly implicates list construction rather
than semantic judgement.

## Deterministic aggregation — the model never builds this

```python
months   = [c for c in cells if c.classification == "month"]
unknowns = [c for c in cells if c.classification == "unknown"]
if unknowns:
    request_human_clarification()
```

Expected for A1: `month_columns = [2,3,5,6]`, `unknown_columns = [4]` — exactly the 2B.4 target,
assembled by code from seven independent judgements.

## This gives `AskHuman` a different role

The classifier does not need escalation authority. It only needs to say `unknown`. **Deterministic
orchestration decides** whether a human is called:

```text
locate header
      ↓
for each header cell: classify role
      ↓
deterministic aggregation
      ↓
if any UNKNOWN: human review
```

That is much safer than hoping the model remembers it holds escalation authority — a hope that
has now failed across four probe types and 325 file-evaluations.

## Interpretation — declared before running

| Result | Reading |
| --- | --- |
| All seven correct, including `Jakso A → unknown` | **The model can make small semantic judgements; deterministic code should own composition and escalation.** The separate-actions architecture stops being a preference and becomes experimentally supported |
| `Jakso A → not_month`, others correct | The warrant problem is isolated at last, with no broken control muddying it. The model does not represent its own uncertainty even when it costs nothing to say so |
| P6/P7 correct but others wrong | Aggregate construction was the 2B.4 problem, but per-cell judgement is unreliable for other reasons |
| Widespread per-cell failure | The 2B.2 result was less robust than it appeared, and the whole capability picture needs re-examining |

## Settings

Identical to 2B.1–2B.4: `qwen3.5:9b`, digest verified, thinking disabled, seed 20260809,
temperature 0.6 / top_p 0.95 / top_k 20, one run per cell.
