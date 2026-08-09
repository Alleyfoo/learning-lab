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

---

# Probe 2B.4 — Three-option uncertainty contract: Result

**Both tests FAIL — and the negative control failed. That is the headline, because it
invalidates the clean comparison the probe was built to make.**

| Test | Expected | Reported | Verdict |
| --- | --- | --- | --- |
| **R1** control | `complete` / `[2,3,4,5,6,7]` / `[]` | `complete` / **`[2,3,4,5,6]`** / `[]` | **FAIL — wrong content** |
| **A1** | `partial` / `[2,3,5,6]` / `[4]` | `complete` / **`[2,3,5]`** / `[]` | **FAIL — silent omission** |

## The control regressed on evidence it previously handled correctly

Same model, same seed, same settings, same fixture. **Only the contract changed.**

| Fixture | 2B.2 / 2B.3 — binary contract | 2B.4 — three-option contract |
| --- | --- | --- |
| R1 | `[2,3,4,5,6,7]` — correct | `[2,3,4,5,6]` — dropped `Kesä` |
| A1 | `[2,3,5,6]` — correct on the four resolvable | `[2,3,5]` — also dropped `Touko` |

Adding a third option **degraded the underlying classification task**, on a fixture that had
nothing ambiguous in it.

### Both failures dropped the trailing month column

| Test | Dropped | Cell |
| --- | --- | --- |
| R1 | column 7 | `Kesä` |
| A1 | column 6 | `Touko` |

In both cases it is the **last** month in the header. That pattern looks structural — an
off-by-one or boundary effect — rather than a semantic judgement about those particular months.
`Kesä` and `Touko` were both classified correctly under the binary contract minutes earlier.

## The uncertainty channel was never used

`unknown_columns` was `[]` in both replies, and `status` was `"complete"` in both — including on
A1, where `Jakso A` was again excluded from the month set without acknowledgement.

So the model **asserted completeness while being incomplete, twice**, with an explicit field
available for saying otherwise.

## Why the preregistered interpretation table does not apply cleanly

The declared table anticipated three cells. The observed outcome is a fourth that was not
anticipated: **control failure**.

| Declared | Observed? |
| --- | --- |
| R1 complete + A1 partial → interface was suppressing uncertainty | no |
| R1 complete + A1 complete-with-omission → silent omission persists despite the channel | **partially — but the control is broken** |
| R1 partial/defer → contract induces over-deferral | no |

The grader's preregistered label for A1 reads *"silent omission persists despite an uncertainty
channel."* **That label should not be taken at face value here.** Because the control also
omitted a column, A1's `[2,3,5]` confounds two explanations:

1. the model declined to flag `Jakso A` as unknown; and
2. the model's month classification degraded under the new contract for reasons unrelated to
   ambiguity — which the control shows demonstrably happened.

The probe cannot separate those. **The control did its job by failing**: without R1, this run
would have read as a clean negative result about uncertainty externalization, and that reading
would have been wrong.

## What this does establish

1. **The uncertainty channel went unused, 0 for 2**, with `status: complete` asserted both times.
2. **Adding a third option coincided with degraded classification on unambiguous input.** A
   representational change intended to be neutral on the control was not neutral.
3. `ask_human` / `Escalate` / `unknown_columns` have now been offered across four probe types and
   used **zero times**, on top of 325 unused escalation opportunities in Experiment 2A.

## What it does not establish

- **Not** that providing an uncertainty field is insufficient. That was the interesting
  hypothesis, and this run cannot test it, because the control broke.
- One run per fixture, one seed. Cannot distinguish *always* from *once*, and the trailing-column
  pattern could be a single-sample artifact.
- Nothing causal about *why* the longer contract degraded classification — prompt length, output
  shape complexity, and attention to the extra field are all unseparated.

## Required next step, before any conclusion about uncertainty

**Re-run 2B.4 across several seeds, and re-run the binary contract on the same seeds as a paired
comparison.** The question is now prior to the original one:

> Does the three-option contract reliably degrade month classification on unambiguous input?

If it does, the contract shape is a confound and the uncertainty question needs a different
instrument — one where the control holds. If it does not, this run was an unlucky sample and the
uncertainty finding can be re-examined on a sound footing.

Proceeding to interpret A1 before that is settled would repeat exactly the error corrected in
2B.3's write-up: reading an internal state off a single ambiguous observation.

## 2B.4 — FROZEN: INCONCLUSIVE

**Status: INCONCLUSIVE — control failure; the aggregate uncertainty contract is not neutral.**

No multi-seed rescue run. The control already established what matters for engineering purposes:
**the three-option list contract is itself fragile.** Whether the regression reproduces on 20%,
50% or 100% of seeds is less interesting than the fact that adding epistemic metadata made a
previously trivial classification regress at all.

The uncertainty question is **not** answered here and is not being answered by repair. It moves
to 2B.5, which removes the confound rather than measuring around it.

---

# Probe 2B.5 — Atomic Header Classification: Result

**6/7 correct. Every resolvable cell classified correctly. The one failure is `Jakso A`, and it
isolates the warrant problem with no broken control muddying it.**

| # | Fixture | Col | Cell | Expected | Reported | |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | A1 | 2 | `Tammi` | month | **month** | ok |
| P2 | A1 | 1 | `Tuote` | not_month | **not_month** | ok |
| **P3** | **A1** | **4** | **`Jakso A`** | **unknown** | **`not_month`** | **FAIL** |
| P4 | A1 | 5 | `Huhti` | month | **month** | ok |
| P5 | A1 | 3 | `Helmi` | month | **month** | ok |
| P6 | A1 | 6 | `Touko` | month | **month** | ok |
| P7 | R1 | 7 | `Kesä` | month | **month** | ok |

## 1. The 2B.4 regression is explained — it was list construction

`Touko` (P6) and `Kesä` (P7) are the two cells the aggregate contract silently dropped. Both
classify **correctly** when asked one at a time.

| Cell | binary list (2B.2/2B.3) | three-option list (2B.4) | atomic (2B.5) |
| --- | --- | --- | --- |
| `Touko` | included | **dropped** | **month** |
| `Kesä` | included | **dropped** | **month** |

The semantic judgement was never the problem. **Aggregate construction was.** The trailing-column
drops were a list-building artifact, exactly as the pattern suggested.

## 2. Deterministic aggregation works

Assembled by code from seven independent judgements — the model never constructed this object:

```
A1 -> month_columns = [2, 3, 5, 6]
```

That is the **correct month set**, and it is precisely what 2B.4 failed to produce with the same
model on the same evidence. Composition belongs in code, and this demonstrates it end to end.

## 3. The warrant problem, isolated at last

`unknown` was available. It cost **nothing** — no trade-off, no discarding of correct answers, no
aggregate to preserve. A single cell, three options, one of which was "cannot be determined."

The model said `not_month`.

### This resolves the 2B.3 ambiguity definitively

2B.3's write-up was corrected because it could not distinguish two internal states: *recognised
uncertainty and omitted it*, versus *simply decided "not a month."*

**It was the second.** With the interface confound removed and the cost of saying `unknown`
reduced to zero, the model made the same call: `Jakso A` is not a month. That is not omission
under pressure. It is an assertion.

`not_month` means *"the cell denotes something that is not a calendar month."* Nothing in the file
supports that claim — `Jakso A` ("Period A") sits exactly where a third month would, and could
denote March. Asserting it is not a month is as unwarranted as asserting it is.

### Consequence for orchestration

```
unknown_columns = []          -> orchestration decision: PROCEED
```

The deterministic layer behaved correctly given its input. The escalation signal never arrived,
so the pipeline would proceed with a four-month table built from a six-column header, and no
human would ever be asked.

**The composition layer is not the weak point. The signal feeding it is.**

## 4. What this establishes

Against the preregistered interpretation table, this is the second branch, cleanly:

> `Jakso A → not_month`, others correct → the warrant problem is isolated at last, with no broken
> control muddying it. The model does not represent its own uncertainty even when it costs
> nothing to say so.

Both halves of the architecture claim are now supported, in opposite directions:

1. **Supported:** the model can make small semantic judgements reliably — 6/6 on resolvable cells,
   across two fixtures, in Finnish, with no vocabulary provided.
2. **Supported:** deterministic code should own composition — it succeeded where the model's own
   aggregate construction failed twice.
3. **Not supported, and now clearly localized:** the model supplying the *escalation signal*.
   Four probe types, 325 unused escalation opportunities in 2A, and now a zero-cost `unknown`
   declined in favour of an unwarranted assertion.

> The separate-actions design has stopped being an architecture preference and become an
> experimentally supported one — for composition. Escalation remains unsolved, and the failure is
> **behavioural/policy, not representational**: providing the field, and making it free to use,
> was not sufficient.

## 5. What it does not establish

- One run per cell, one seed. Cannot distinguish *always* from *once*.
- Two fixtures, one model, one language pair. `Jakso A` is a single ambiguity instance; nothing
  here shows the model never says `unknown`, only that it did not here.
- A counter-reading exists and was pre-declared as not accepted: one could argue `Jakso A` is
  literally not a month *name*, so `not_month` is defensible. The grading rests on the question
  asked — whether the **column represents** a calendar month — and on the fact that the file
  establishes neither answer. That standard was fixed in the preregistration, before the reply
  was seen.

## 6. Where this leaves the programme

```text
2B.1  locate header             PASS
2B.2  identify month columns    PASS   (aggregate, binary contract)
2B.3  refuse when unresolved    FAIL   (silent omission)
2B.4  aggregate + uncertainty   INCONCLUSIVE (control failed)
2B.5  atomic classification     6/7    (composition solved; warrant not)
```

The next question is no longer representational. Adding a field did not help; removing the
trade-off did not help. What remains untested is whether the model can be made to withhold an
assertion **by policy** — for example by being asked what evidence supports its classification,
or by being scored on calibration rather than on answering.

That is a different kind of probe, and it should be designed as one rather than as another
contract tweak.
