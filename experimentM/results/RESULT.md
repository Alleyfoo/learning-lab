# Experiment M — Result: RESULT_UNPREDICTED_SILENT_WRONG

```text
shape                   predicted    actual       silent  behaviour
S1_clean_wide           EXPRESSIBLE  EXPRESSIBLE  no      correct table
S2_stacked_header       GAP          EXPRESSIBLE  no      correct table
S3_two_measure_blocks   GAP          GAP          YES     validated, executed, 4/8 rows
S4_already_long         EXPRESSIBLE  EXPRESSIBLE  no      correct table
S5_formatted_numbers    GAP          GAP          yes*    executed, types unhonoured
S6_interleaved_note     GAP          GAP          no      recipe INVALID -- refuses

3 expressible / 3 gaps          (predicted 2 / 4)
```

Three of six predictions were wrong: two in the safe direction, one in the
dangerous one.

## The finding — S3 loses half the data with no signal at all

A sheet with two measure blocks over the same months (units *and* euros). The
recipe declares two `period_measure` fields, each with its own `unpivot`. It
**validates**, it is **approvable**, and the executor honours only the **last**
one:

```text
expected  2 products x 2 months x 2 measures  = 8 rows
produced  cols ['tuote', 'kuukausi_eur', 'eur'] = 4 rows
```

Half the data is gone. No problem code, no unhonoured declaration, no refusal —
nothing anywhere says so. A human approving this recipe sees a valid,
hash-bound artifact; the pipeline produces a clean-looking table missing every
unit figure.

**This is the failure class the whole architecture is built to prevent, arriving
through a hole nobody was watching.** The format's closed enum *permits* a
combination the executor cannot honour, and no layer checks that it can. It is
the same shape as Experiment K's v1.2 run 1 — a capability added in one layer and
silently not consumed by another — which means it is a *recurring* structural
weakness in this codebase, not a one-off.

The freeze forbade patching during M, so it is recorded, not fixed. The fix is
not "support two unpivots": it is that **the validator must reject what the
executor cannot honour**, which is a general obligation rather than a feature.

### S5 is silent-*ish*, and the difference matters

`1 234,50` and `12 %` come out as strings under a declared `type: number`. The
grader calls that not-correct, but unlike S3 it **leaves a trace**:
`unhonoured_types` names the field and the reason. S3 leaves nothing.

```text
S5  wrong, and says so     -> a human or a downstream check can see it
S3  wrong, and says nothing -> nothing to see
```

A gap that reports itself is a different risk class from one that does not, and
the grading rule used here does not distinguish them. Future breadth arms should.

## Where the format was better than predicted

**S2 — a two-row stacked header is expressible.** Naming the *lower* row as
`header_row` and excluding the year band above it produces the correct table. The
prediction assumed a two-row header needs flattening; it only does if the target
schema needs **both** rows. Here `2026` is redundant with the file, so it can be
excluded rather than merged. Honest caveat: a schema needing `2026-Tammi` would
still be a gap, and this shape does not test that.

**S6 — the interleaved note is caught, not absorbed.** The prediction was that a
note in the *middle* of the data escapes a shape rule "because it is not at the
bottom where a shape rule catches it". That reasoning was **false about my own
implementation**: `data_row_shape` checks every row in the data region, not the
last one. The note has blank measures, so it raises `row_shape_violation`, the
recipe is invalid, and the system refuses.

That is v1.2 generalising past the case it was designed for — and it is the one
place in this experiment where the architecture behaved better than its author
expected.

## What M says about the schema-only question

L established that a recipe *can* do the job. M puts a number on how far that
carries: **three of six plausible provider shapes worked; three did not.**

More useful than the ratio is the classification of the failures:

```text
S5  gap that reports itself       tolerable -- a human sees it
S6  gap that refuses              the good failure -- the system stops
S3  gap that stays silent         the dangerous one
```

Two of three gaps are safe. The third is not, and it is not a gap in
expressiveness at all — the format could express the intent fine. It is a gap in
**enforcement**: nothing checks that the executor can honour what the validator
accepted.

### And the security reading

Each gap is pressure to add an escape hatch, and an escape hatch is where an
expression language — and the injection surface — comes back. On this evidence
the pressure is real but modest: S2 needed no new capability, S6 needs none (a
refusal is the correct outcome), and S5 needs a *declaration* (a number-format
string), not an expression. Only S3 asks for genuine new expressiveness, and it
asks for a bounded thing — more than one unpivot per sheet.

**Nothing here needed arbitrary computation.** That is the closed enum holding up
better than expected under breadth pressure, which is the result the containment
argument actually needed.

## Limitations

- Six in-lab shapes chosen by the author. They are plausible, not sampled.
- M froze *classifications*, not expected tables; row counts were derived from
  each fixture by inspection and asserted in the grader. A subtler wrong table
  with the right row count would pass.
- The grading rule treats "reports its failure" and "stays silent" identically.
  S3 and S5 land in the same bucket and should not.
- One recipe per shape, written by the author who knew the prediction.
- Deterministic and fully repeatable: no LLM, no seeds, no sampling.
