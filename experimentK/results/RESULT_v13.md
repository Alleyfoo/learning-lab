# Experiment K — v1.3 reconciliation: PASS_AS_PREDICTED

C8 is caught. Every frozen prediction held, and the residual landed where it was
authored to land.

```text
ID   truth            v1.2             v1.3
C1   EXECUTE          EXECUTE          EXECUTE          ok
C2   EXECUTE          EXECUTE          EXECUTE          ok
C3   EXECUTE          EXECUTE          EXECUTE          ok
C4   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C5   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C6   REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C7   DEFINE           DEFINE           DEFINE           ok
C8   REDEFINE_SCOPED  EXECUTE ✗        REDEFINE_SCOPED  ok   <- recovered
C9   DEFINE           DEFINE           DEFINE           ok
C10  AMBIGUOUS        AMBIGUOUS        AMBIGUOUS        ok
C11  BLOCKED          BLOCKED          BLOCKED          ok
C12  BLOCKED          BLOCKED          BLOCKED          ok
C13  REDEFINE_SCOPED  REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C14  REDEFINE_SCOPED  EXECUTE ✗        EXECUTE ✗             <- the residual

v1.3  13/14   over_escalation {}   false_execute {C14}   fidelity_all True
```

## How C8 was caught

Without knowing what `VÄLISUMMA` means:

```text
reconciliation_failure: col0 1: data rows sum to 39 but row0 8 (A1 row 9) states 22
```

The evidence is arithmetic the **provider themselves** put in the file. The
recipe treats four rows as data; the sheet's own grand total disagrees with their
sum; therefore the recipe's idea of "what is a data row" no longer matches the
file's. No pattern, no regex, no value list, no knowledge of Finnish accounting
vocabulary.

Security-wise it is *narrower* than machinery that already existed: `label_in`
compares strings, reconciliation only adds numbers.

## The four-format trajectory is the finding

```text
v1    absolute anchoring                     11/14   escalates the monthly case
v1.1  + relative anchoring                   11/14   fixes that, absorbs anything
v1.2  + row-shape expectation                12/14   fixes that, misses subtotals
v1.3  + reconciliation                       13/14   fixes that, misses C14
```

Every version fixed its predecessor's cost and arrived carrying a new one, and
**every cost was named before it was measured**. The residual has narrowed at
each step and has never closed:

```text
v1    an ordinary monthly file escalates
v1.1  any unexpected row is absorbed
v1.2  a row that LOOKS like data is absorbed
v1.3  a row that looks like data AND adds up is absorbed
```

Each residual is strictly smaller and strictly more contrived than the last. That
is what progress looks like here — not elimination.

## C14: where arithmetic stops

`C14_reconciling_subtotal.xlsx` is the same `VÄLISUMMA` row with the grand total
updated to `39 / 49 / 44` — the sum of all four rows *including* the subtotal. The
sheet adds up perfectly and is merely double-counted.

The self-test asserts `reconciliation_failure` does **not** fire on it, so the
limit is a tested property rather than an observed accident. Catching C14 needs
someone to know that a subtotal is not a product — which is not arithmetic, not
shape, and not structure.

## What this says about the project's actual question

The question is whether agents can be put beyond the line — never facing
untrusted human-side content at runtime — while the system stays useful.

**Everything after the schema is defined already runs with no model at all.**
Across 14 cases and four formats, every dispatch decision was made by
deterministic code. `EXECUTE` invokes nothing. `BLOCKED` is enforced by a content
hash. A refusal cannot be argued out of, and no amount of injected text in a cell
changes any of it, because nothing in that path is reading cell text as
instruction.

**And the residual is always semantic.** Four increasingly capable structural
checks have not produced one that decides what a row *means*. C14 is the current
edge and its successor will be more contrived still, but the shape of the
remaining failure has not changed once: *this file is structurally exactly what
was approved, and means something different.*

That is evidence for the designer's position rather than against it. A human has
to be the first reader — to establish what the task is and what the rows mean —
because that judgement is the one thing none of these checks reach. What follows
the definition does not need a human, and increasingly does not need an agent
either.

The white-text asymmetry (frozen in `spec/v13_reconciliation.md`) sharpens the
same point: if a cell can carry text the human reviewer cannot see, then "a human
reads it first" is only a real control when the human is shown **what the machine
reads**. That is a requirement on the browser, and it is not built.

## Limitations

- Reconciliation is skipped when no total row is found. Many real sheets have no
  total, and on those v1.3 degrades exactly to v1.2.
- A crafted file can make things reconcile that should not (C14 is the honest
  version of this). That hides an escalation; it cannot create authority.
- Coincidental sums could mask a wrong row set. Untested, and unlikely rather
  than impossible.
- 14 in-lab candidates from one workbook. A controlled replay, not a prevalence
  estimate.
- Deterministic and fully repeatable: no LLM, no seeds, no sampling.
