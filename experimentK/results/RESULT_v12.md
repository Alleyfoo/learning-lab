# Experiment K — v1.2 row-shape: PASS_AS_PREDICTED (on the second run)

```text
ID   truth            v1               v1.1             v1.2
C1   EXECUTE          EXECUTE          EXECUTE          EXECUTE          ok
C2   EXECUTE          EXECUTE          EXECUTE          EXECUTE          ok
C3   EXECUTE          REDEFINE_SCOPED  EXECUTE          EXECUTE          ok
C4   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C5   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C6   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C7   DEFINE           DEFINE           DEFINE           DEFINE           ok
C8   REDEFINE_SCOPED  EXECUTE ✗        EXECUTE ✗        EXECUTE ✗
C9   DEFINE           DEFINE           DEFINE           DEFINE           ok
C10  AMBIGUOUS        AMBIGUOUS        AMBIGUOUS        AMBIGUOUS        ok
C11  BLOCKED          BLOCKED          BLOCKED          BLOCKED          ok
C12  BLOCKED          BLOCKED          BLOCKED          BLOCKED          ok
C13  REDEFINE_SCOPED  REDEFINE_SCOPED  EXECUTE ✗        REDEFINE_SCOPED  ok

v1    11/13   over_escalation {C3}   false_execute {C8}
v1.1  11/13   over_escalation {}     false_execute {C8, C13}
v1.2  12/13   over_escalation {}     false_execute {C8}
```

`fidelity_all = True`. Every v1.2 cell matched the frozen prediction, and the v1
and v1.1 arms reproduced their recorded results exactly.

## Two runs, and why both are recorded

**Run 1: `FAIL_FIX`.** C13 executed. The validator raised `row_shape_violation`
correctly — the self-test proved that — but `dispatch.py`'s `COVERAGE_CODES`
tuple did not list the new code, so the front door read the problem and ignored
it.

The frozen spec says plainly that a row-shape violation *"the front door treats
as a coverage problem → `REDEFINE_SCOPED`"*. So this was **code deviating from
frozen text, which the fidelity policy classifies as a bug**: fix the code,
re-run, and record both runs. Run 1 is preserved verbatim at
`results/superseded/K_v12_run1_spec_deviation.json`.

It is worth naming what went wrong, because it is a category the architecture
should be able to catch and did not: **a new problem code was added in one layer
and silently not consumed by another.** The validator's self-test asserts that
every declared code is exercised; nothing asserts that every *coverage-class*
code is acted on by the dispatcher. A one-line omission turned a detection into
a silent pass — the exact failure shape this project studies, arriving in our
own control plane rather than in a model.

**Run 2: `PASS_AS_PREDICTED`**, unchanged in every other respect.

## The corrected prediction held

`RESULT_c3fix.md` speculated a row-shape rule "would plausibly recover C13 and
C8 both". The v1.2 preregistration corrected that **before building**:

```text
C13  footnote   Tuote non-blank ✓   measures BLANK   ✗  -> caught
C8   subtotal   VÄLISUMMA  ✓        17 / 21 / 19     ✓  -> NOT caught
```

Both landed as corrected. C13's delta names the cells:

```text
row_shape_violation: row0 9 (A1 row 10): sheet:Sales!B:D col0 1 is not numeric ('')
row_shape_violation: row0 9 (A1 row 10): sheet:Sales!B:D col0 2 is not numeric ('')
row_shape_violation: row0 9 (A1 row 10): sheet:Sales!B:D col0 3 is not numeric ('')
```

The self-test asserts the negative case too — that `row_shape_violation` does
**not** fire on C8 — so the boundary is a tested property rather than an
observed accident.

## What the three formats bought

```text
v1    absolute anchoring      escalates the ordinary monthly case
v1.1  + relative anchoring    fixes that, absorbs anything unexpected
v1.2  + row-shape expectation fixes that too, at the cost of reading cell types
```

**v1.2 is the first format that is unambiguously better than its predecessor**,
and the trajectory is the finding: each fix arrived with a cost, and two of the
three costs were only visible because they were predicted and measured rather
than assumed.

The one remaining failure is C8, and it is **not a gap to be closed by a better
structural rule**. A subtotal row is shape-identical to a data row. Catching it
requires knowing what `VÄLISUMMA` *means*, which is a different kind of evidence
and a different threat model.

## Read as a security result

v1.2 widens what the validator reads: v1 and v1.1 touched structure and the
header row; v1.2 reads **every cell in the data region**. That is a real
increase in untrusted-input surface and it was named in the freeze.

It is bounded on purpose. The validator learns only **blank / numeric / neither**
per cell and never branches on what a cell says — no patterns, no regex, no
value lists, the same refusal that kept transforms a closed enum and `label_in`
literal. The consequence is that a hostile or manipulated workbook can make rows
fail the shape check, which causes an **escalation to a human**, and nothing
else. It cannot cause a wrong recipe to execute, and it cannot widen anyone's
authority.

**Escalation is the safe direction, so the widened surface buys detection
without buying authority** — the Agent-Security-Lab distinction (semantic
compromise ≠ authority compromise) applied to a deterministic component instead
of a model.

And the honest limit, unchanged by v1.2: the front door certifies *"this file
has the structure the approved recipe describes, and its data rows have the
declared shape."* It still cannot certify *"the rows mean what they meant last
month."* C8 is that sentence made concrete.

## Limitations

- 13 in-lab candidates from one workbook; a controlled replay, not a prevalence
  estimate.
- `require_numeric` reuses Experiment J's frozen `is_number`, which accepts a
  comma decimal separator and rejects thousands separators. A provider emitting
  `1 000` would fail the shape check — an escalation, i.e. the safe direction,
  but noise rather than signal. Untested here.
- The shape rule is declared per data sheet, not per field role. A recipe with
  several measure blocks of different types cannot express that yet.
- Deterministic and fully repeatable: no LLM, no seeds, no sampling.
