# Experiment L — does working only with the schema actually work?

**STATUS: FROZEN before any executor exists.** Deterministic — **no LLM
anywhere.** Plan v1 §10 step 6, deferred four times and now the load-bearing
question.

## The question (designer, 2026-08-14)

> Another question to answer is if only working with schema really works —
> that's what we are relying on in the end.

The architecture's whole security argument is that an agent never needs to touch
untrusted content at runtime, because a human-approved **recipe** carries the
task. Everything built so far protects that artifact. **Nothing has ever run
one.**

Four experiments validated recipes, dispatched on them, and hash-bound their
approval. `--dry-run` proves referents resolve; it does not prove the output is
correct. If a recipe cannot actually do the job, the containment machinery is
guarding something nobody would use, and people will reach past it.

## Two claims, and this experiment tests one

```text
(A) can an AGENT define the frame from structure alone?   untested; needs the
                                                          step-4 structure view
(B) is a RECIPE sufficient to do the job?                 NEVER TESTED -- this
```

L tests (B). (A) is a separate freeze and depends on (B) being answered first:
there is no point asking whether an agent can produce a recipe until we know a
recipe can produce a table.

## L1 — execute the approved recipe on the workbook it was written for

Executor: validated + approved recipe + workbook → table. Deterministic, no
model. It honours exactly the frozen format: `remainder` regions, rule-based
exclusions, `id` / `measure` / `period_measure` / `metadata` / `derived` roles,
and the `unpivot` transform.

Input: `experimentK/recipes/W1_sales_v13_approved.json` against
`definition_phase/fixtures/W1_multisheet.xlsx`.

**Frozen expected output** — 4 products × 3 months = 12 rows, columns
`paivitetty, tuote, kuukausi, myynti`:

```text
3.2.2026  ART-001  Tammi   10      3.2.2026  ART-003  Tammi    5
3.2.2026  ART-001  Helmi   12      3.2.2026  ART-003  Helmi    7
3.2.2026  ART-001  Maalis   8      3.2.2026  ART-003  Maalis   6
3.2.2026  ART-002  Tammi    7      3.2.2026  ART-004  Tammi    8
3.2.2026  ART-002  Helmi    9      3.2.2026  ART-004  Helmi   11
3.2.2026  ART-002  Maalis  11      3.2.2026  ART-004  Maalis   7
```

The `YHTEENSÄ` row, the `Yhteensä` total column, the `Kommentti` column and the
three preamble rows must all be absent. That is the whole definition working.

## L2 — execute the SAME recipe on next month's file

`experimentK/fixtures/C3_more_rows.xlsx` — six products, the total row moved.
K established that dispatch returns `EXECUTE` on it under v1.1+. L2 asks whether
the execution is also *correct*.

**Frozen expected: 18 rows** (6 products × 3 months), same four columns,
`ART-005` at 6/8/9 and `ART-006` at 4/5/3, and the `YHTEENSÄ` row still absent.

L2 is the payoff claim of the entire architecture stated as a testable sentence:
**define once, run on next month's file, with no model in the loop.**

## Preregistered gap G1 — a declared type that cannot be honoured

The recipe declares `{"target": "paivitetty", "type": "date"}` and the cell holds
the string `3.2.2026`. **The format has no way to say how a date is written**
— no format string, no locale — so the executor cannot honour the declaration
without guessing `dd.mm.yyyy`, and guessing is exactly what this programme does
not do.

The expected table therefore freezes `paivitetty` as the **raw string**, and the
run separately records `declared_types_honoured = False` for that field. A pass
that silently ignored the declared type would hide the gap; this makes the table
match *and* the gap visible.

**G1 is the first concrete answer to the designer's question.** Working only with
the schema does work — up to the point where the schema cannot say something the
job needs. Counting those points is the measurement.

## Grading (frozen)

```text
L1_pass   executor output == frozen expected table, exactly (order included)
L2_pass   same, on C3, 18 rows
gaps      declared_types_honoured recorded per field; G1 predicted False
```

| Condition | Outcome |
| --- | --- |
| L1 and L2 both match, gaps == {G1} | **PASS_AS_PREDICTED** — a recipe does the job, and one named thing the schema cannot say |
| L1 or L2 mismatches | **FAIL** — record the diff; do not adjust the expected table |
| a gap appears beyond G1 | **RESULT_MORE_GAPS** — record each; this is the measurement, not a failure |
| the executor needs information the recipe does not carry | **FAIL_INSUFFICIENT** — the honest negative answer to the question, and the most important possible result |

## Hard stop

Execution only. No LLM. No changes to the frozen grammar, to recipe format
v1.1/v1.2/v1.3, to any recorded K result, or to any frozen fixture. **If the
executor needs something the format lacks, that is recorded as a gap — never
patched into the format mid-run.** Patching would convert the measurement into a
tautology, which is exactly how J and K would have gone wrong.

## Standing traps

- **Do not adjust the expected table to match the output.** It is frozen from the
  fixture by hand, above.
- **Do not implement date parsing to make G1 disappear.** G1 is a result.
- **The executor must not read anything the recipe does not name.** If it needs
  to peek at a cell no referent points at, that is `FAIL_INSUFFICIENT`.
- No model may be invoked, including for "just" parsing a date.
