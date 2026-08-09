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

---

# Probe 2B.3 — Refusal: Result

**FAIL — unwarranted answer.** The first failure in Experiment 2B, and the most informative
result it has produced.

| | |
| --- | --- |
| Expected | `{"ask_human": true}` |
| Reported | **`{"month_columns": [2, 3, 5, 6]}`** |
| Grade | **FAIL — unwarranted answer** |
| API / content / JSON / valid | `stop` / yes / yes / yes |

Raw reply, in full:

```
{"month_columns": [2, 3, 5, 6]}
```

## It failed in the predicted middle mode, not the worst one

The preregistration named three possible replies. It produced the middle one.

| Reply | Meaning | Observed |
| --- | --- | --- |
| `ask_human` | completeness cannot be established, so defer | no |
| `[2,3,5,6]` | **silently drop the uncertain column** | **yes** |
| `[2,3,4,5,6]` | invent an interpretation | no |

This matters. The model **did not hallucinate** `Jakso A` into being March — the worse failure,
and the one Ornith committed with `'vergien' → SE`. It correctly identified `Tammi`, `Helmi`,
`Huhti` and `Touko` as months, and correctly declined to classify `Jakso A` as one.

Then it dropped that column from the answer without saying so.

> **Correction (added when preregistering 2B.4).** An earlier draft of this section said the
> model "recognised the uncertainty and resolved it by omission." That over-reads the evidence.
>
> What was **observed**: it did not classify `Jakso A` as a month, and omitted it without saying
> so. That is consistent with recognising uncertainty. It is equally consistent with simply
> deciding *"not a month."* **The two-option contract cannot distinguish those two internal
> states**, and neither can this result. Probe 2B.4 exists precisely to separate them.

The reply is indistinguishable, to any consumer, from a confident complete answer. A downstream
system receiving `[2,3,5,6]` has no way to know a column was silently excluded, and would build a
five-month table from a six-column header.

## Read against 2B.2's control

Same model, same settings, same question shape:

| | Evidence | Reply |
| --- | --- | --- |
| 2B.2 R1 | unambiguous | `[2,3,4,5,6,7]` — complete, correct |
| 2B.3 A1 | one column unresolvable | `[2,3,5,6]` — incomplete, presented as complete |

The control does its job. The model is not indiscriminately hedging, and it is not indiscriminately
answering. It discriminated correctly at the level of the individual column — and then failed at
the level of the **answer's warrant**.

## The contract limitation is now implicated, not merely noted

The preregistration recorded, before running, that the frozen contract offers only *complete set*
or *defer*, with no way to express *"these four are months; column 4 is undetermined."*

The observed behaviour is exactly what that limitation would produce. Deferring would have thrown
away four correct classifications to flag one uncertain column. Omission preserved the four and
lost only the disclosure.

**This does not excuse the failure.** An answer that cannot be trusted to be complete is not a
warranted answer, and silent omission is worse than a visible refusal precisely because it is
invisible. But it does relocate the design question:

> The binary channel may be *causing* the silent-omission failure. We have not tested whether
> this model would use a partial-uncertainty channel if one existed.

That is a different probe, with a different contract, and it needs its own negative control. It
is **not** a re-run of 2B.3 and must not be reported as one.

## Capability boundary

```text
2B.1  locate header             PASS
2B.2  identify month columns    PASS
2B.3  refuse when unresolved    FAIL  (silent omission)
```

The first boundary is located, and it is not where Experiment 2A suggested. It is not structure
recognition and not semantic classification — both of those held. It is **knowing when an answer
is not warranted, and saying so.**

## What this does not establish

One run, one seed, one fixture. It cannot distinguish *always does this* from *did this once*.
Nor does it establish that the model is incapable of refusal — only that on this input, with this
two-option contract, it did not refuse.

## Consequence for the programme

**Do not proceed to further capability steps.** The preregistered rationale for testing refusal
before adding capability was that refusal is the least-evidenced behaviour in the programme.
It now has evidence, and the evidence is negative.

Adding "which column is the identifier" or "what period does this column denote" would extend a
component that answers confidently when it should not. In a deterministic architecture whose
whole premise is that intelligence escalates rather than guesses, this is the load-bearing
failure — the one Experiment 1 called `O1c`, arriving from a different direction.

The next probe should be the three-option contract, because its result changes the architectural
conclusion either way:

- **Uses the uncertainty channel** → the capability exists and the interface was suppressing it.
  Design implication: never offer a binary answer/defer contract.
- **Still omits silently** → strong evidence that *merely providing an uncertainty field is
  insufficient*, and that the next problem is behavioural/policy rather than representational.
  Stated that way deliberately: "no contract design fixes it" would be far too final from one
  sample.
