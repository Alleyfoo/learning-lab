# Experiment J — Macro v2: compiling a human-reviewed failure

**STATUS: FROZEN before any implementation.** This document, `expected.json`
and `fixtures/` are committed **before** `harness/macro_v2.py` exists. The v2
rule text below is the specification the implementation must satisfy; the
ground-truth labels and the *predicted* v2 outputs in `expected.json` are
frozen at the same moment. Nothing here is revised after the replay runs.

## The framed question (designer's words, 2026-08-10)

> Can a human-reviewed failure be compiled into macro v2 without regressing
> previously supported provider shapes?

## Why this experiment exists

Experiment I ended with a located boundary and no agent-supplied correction:

```text
I1/I2/I3   PASS 3/3   clean wide / long / quarterly-unknown   (f3c3a9a)
I4         FAIL       word-definition contract     GLM -> wide,  expected unknown
I5         FAIL       English prototypes           GLM -> wide,  expected unknown
I6         FAIL       Finnish prototypes           GLM -> wide,  expected unknown  (748e4d3)
```

Three contract variants failed to make the agent return `unknown` on a
transposed monthly layout. Per the designer's stop rule, tightening the
contract stopped. The designer's clarified position: **the macro-saver model
does not require the agent to be the sole inventor.** A human reviewing the
failed case and amending the saved recipe is still macro-saver behaviour.

So J does the amendment — deterministically, with no LLM anywhere — and then
asks whether the amendment cost anything.

## The circularity this design must avoid

v2 is hand-designed **knowing I4**. Replaying it on I1–I6 and reporting "v2
fixes I4" is therefore near-tautological: the rule was written to fix I4. Such
a replay measures nothing except that the author can write an `if`.

Three mechanisms make the result non-tautological:

1. **Held-out fixtures.** J1–J7 are new shapes, authored in this freeze. They
   include shapes the v2 predicate was *not* designed around, and at least one
   shape where the simple predicate is expected to be **wrong**.
2. **Ground truth is set by definition, not by v2.** Each fixture's expected
   label follows from the wide/long/unknown definitions below, decided as a
   representation question, *not* by asking what v2 would output. Where the
   two disagree, the fixture is frozen against v2 and v2 takes the miss.
3. **Predicted v2 output is frozen too.** `expected.json` records, per fixture,
   what the author predicts v2 will emit — including one preregistered
   regression. This separates *"the rule is correct"* from *"the author
   understands the rule they wrote."* A surprise is a result, not a bug to be
   patched away.

## Definitions (carried from I, unchanged)

```text
WIDE:    one row per entity; the month axis runs ACROSS the header
         (Tuote | Tammi | Helmi | Maalis ...)
LONG:    one row per (entity, month); the month axis runs DOWN one column,
         and the measure lives in its own column
         (Tuote | Kuukausi | Myynti)
UNKNOWN: neither cleanly holds — including transposed layouts (months down a
         column, entity instances spread across columns) and non-monthly
         granularities.
```

`unknown` is a **refusal**, i.e. escalate to a human. This matters for reading
the result: a wrong `unknown` is a false refusal (safe direction, costs human
time); a wrong `wide`/`long` is a false assertion (unsafe direction, the
failure mode the whole 3A–3E programme is about). J scores them the same but
reports them separately.

## Macro v1 (frozen, unchanged, the comparison arm)

The saved recipe as it stands, imported **verbatim** from
`experimentI/harness/gate_I.py` (sha256
`da76ed982614a7874b0272f390f9b898cef47b64b2983645a21feb25ff95a941`). J does
not modify it.

```text
hw = distinct reference months matched in the HEADER row      (tolerant match)
dl = max over data columns of distinct reference months matched
K_w = K_l = 3

hw >= K_w  -> wide
dl >= K_l  -> long
else       -> unknown
```

Falsified by I4 as a general long-test: `dl = 12` on the transposed fixture,
correct label `unknown`.

## Macro v2 (FROZEN RULE TEXT — the specification)

Same reference vocabulary (`experimentH/reference/months.json`, sha256
`6393181b...`), same frozen `tolerant_match`, same thresholds `K_w = K_l = 3`.
The thresholds are **not** retuned in J; only the long-branch is amended.

```text
Inputs: header (list of cells), data (list of rows).

hw          = distinct reference months matched in the header row
month_cols  = [ c : distinct reference months matched in data column c >= K_l ]
other_cols  = data columns not in month_cols
numeric(c)  = column c has at least one non-empty cell and EVERY non-empty
              cell parses as a number
n_num       = count of c in other_cols with numeric(c)

R1  if hw >= K_w                    -> "wide"
R2  elif len(month_cols) == 1
      R2a  if n_num >= 2            -> "unknown"   # month axis down a column AND
                                                   # values spread across >= 2
                                                   # columns: transposed / out of
                                                   # contract
      R2b  elif n_num == 1          -> "long"      # exactly one measure column:
                                                   # canonical long
      R2c  else                     -> "unknown"   # no measure column found
R3  elif len(month_cols) >= 2       -> "unknown"   # ambiguous month axis
R4  else                            -> "unknown"
```

R1 keeps wide precedence exactly as in v1. R2's entry condition
(`len(month_cols) >= 1`, where a month column requires `>= K_l` distinct
months) is v1's `dl >= K_l` trigger unchanged — v2 amends only what happens
*after* the month axis is found in the data. R3/R4 make the rule total.

### What v2 deliberately does NOT do

The designer's sketch said *"months down one column **and multiple entity/value
columns across** → unknown."* `n_num >= 2` is the faithful **deterministic**
reading of "multiple entity/value columns": a column carrying numbers that is
not the month axis is a value-bearing column, and two or more of them means
the values are spread across a second axis.

A **stricter** reading — "unknown only if the spread columns are *entity
instances* (`ART-001`, `ART-002`, `Myymälä-A`) rather than distinct *measures*
(`Myynti`, `Kate`)" — would classify J3 correctly, but it requires deciding
whether a header names an entity instance or a measure. That is a semantic
judgement, not a token count. **It is deliberately not implemented.** J
measures what the simple reading costs; naming that cost precisely is the
point of the experiment, and it is where the next experiment (macro-discovery)
would ask whether an agent can supply that judgement.

## Fixtures

Retained (frozen Experiment I fixtures, referenced **by path**, sha256 verified
at run time — not copied, not modified):

| ID | Fixture | Shape | Ground truth |
| --- | --- | --- | --- |
| I1 | `experimentI/fixtures/I1.csv` | `Tuote │ Tammi…Kesä` + numeric rows | `wide` |
| I2 | `experimentI/fixtures/I2.csv` | `Tuote │ Kuukausi │ Myynti` | `long` |
| I3 | `experimentI/fixtures/I3.csv` | `Tuote │ Q1…Q4 │ Vuosi` | `unknown` |
| I4 | `experimentI/fixtures/I4.csv` | `Kuukausi │ ART-001 │ ART-002 │ ART-003`, months down | `unknown` |

Held out (authored in this freeze, `experimentJ/fixtures/`):

| ID | Fixture | Shape | Ground truth | Why it is here |
| --- | --- | --- | --- | --- |
| J1 | `J1_wide_with_total.csv` | `Tuote │ Tammi…Huhti │ Yhteensä` | `wide` | wide with a non-month numeric column: does the amendment disturb the wide branch? |
| J2 | `J2_long_extra_labels.csv` | `Tuote │ Maa │ Kuukausi │ Myynti` | `long` | **the regression trap for a naive "multiple columns across" rule** — a genuine long table with several columns beside the month axis |
| J3 | `J3_long_two_measures.csv` | `Tuote │ Kuukausi │ Myynti │ Kate` | `long` | two measures on a genuine long table — the shape where `n_num >= 2` is expected to be WRONG |
| J4 | `J4_transposed_two_entities.csv` | `Kuukausi │ Myymälä-A │ Myymälä-B` | `unknown` | **held-out repair**: transposed layout v2 never saw, different vocabulary, minimum spread (exactly 2) |
| J5 | `J5_transposed_single_series.csv` | `Kuukausi │ Myynti` | `long` | sharp boundary: months down a column with ONE measure is canonical 2-column long, NOT transposed. v2 must not over-refuse here |
| J6 | `J6_wide_two_months.csv` | `Tuote │ Tammi │ Helmi` | `wide` | below `K_w`: a known threshold limitation, carried unchanged into v2 |
| J7 | `J7_unknown_no_time.csv` | `Tuote │ Asiakas │ Määrä` | `unknown` | no time axis at all — unknown control in a second direction beyond I3's quarterly |

### Ground-truth judgement calls, stated before the run

- **J5 = `long`.** A single time series (`Kuukausi │ Myynti`) has one row per
  month and one measure column. By the frozen definition that is long — the
  entity dimension is simply absent. It is *not* transposed wide: nothing is
  spread across columns.
- **J3 = `long`.** One row per (product, month) with two measures is long in
  the time dimension. Additional measure columns do not make a table
  transposed. This is the call that puts v2 at risk, and it is made here, on
  the definition, before v2 runs.
- **J6 = `wide`.** Two month columns is a wide representation; `K_w = 3` is an
  evidence threshold, not part of the definition of wideness. v1 misses this
  and v2 is expected to miss it identically — a shared limitation, not a
  regression.

## Predicted outputs (frozen — author's hand-simulation)

| ID | Ground truth | v1 | v1 ok | v2 predicted | v2 ok | Note |
| --- | --- | --- | --- | --- | --- | --- |
| I1 | `wide` | `wide` | ✓ | `wide` | ✓ | R1, `hw=6` |
| I2 | `long` | `long` | ✓ | `long` | ✓ | R2b, `n_num=1` (Myynti) |
| I3 | `unknown` | `unknown` | ✓ | `unknown` | ✓ | R4 |
| I4 | `unknown` | `long` | ✗ | `unknown` | ✓ | **repair** — R2a, `n_num=3` |
| J1 | `wide` | `wide` | ✓ | `wide` | ✓ | R1, `hw=4` |
| J2 | `long` | `long` | ✓ | `long` | ✓ | R2b — labels are not numeric |
| J3 | `long` | `long` | ✓ | `unknown` | ✗ | **PREREGISTERED REGRESSION** — R2a, `n_num=2` |
| J4 | `unknown` | `long` | ✗ | `unknown` | ✓ | **held-out repair** — R2a, `n_num=2` |
| J5 | `long` | `long` | ✓ | `long` | ✓ | R2b, `n_num=1` |
| J6 | `wide` | `unknown` | ✗ | `unknown` | ✗ | shared threshold limitation |
| J7 | `unknown` | `unknown` | ✓ | `unknown` | ✓ | R4 |

Predicted totals: **v1 8/11, v2 9/11. Repairs {I4, J4}. Regressions {J3}.
Shared misses {J6}.**

## Grading (frozen)

For each fixture: `v1_ok = (v1 == ground_truth)`, `v2_ok = (v2 == ground_truth)`.

```text
repairs      = { f : not v1_ok(f) and v2_ok(f) }
regressions  = { f : v1_ok(f) and not v2_ok(f) }
fidelity     = for all f: v2(f) == predicted_v2(f)
fixes_i4     = v2(I4) == "unknown"
preserves    = v2(I1),v2(I2),v2(I3) == wide,long,unknown
```

`fidelity` is a check on the *author*, not on v2's correctness: it asks whether
the frozen rule text, hand-simulated, predicted what the code actually does.

### Decision table

| Condition | Outcome |
| --- | --- |
| `fixes_i4 and preserves and regressions == {}` | **CLEAN COMPILE** — the answer to the framed question is *yes, without regression* |
| `fixes_i4 and preserves and regressions == {J3}` (exactly the preregistered one) | **COMPILE WITH PREDICTED COST** — *yes on the located shape, at a named and predicted cost*; the cost identifies the v3 question |
| `fixes_i4 and preserves and regressions ⊅ {J3}` (any unpredicted regression) | **FAIL — regression not understood.** The amendment broke a shape its author did not anticipate; record it, do not patch and re-run |
| `not fixes_i4` | **FAIL — compile failed.** The hand-written rule does not do what it claims on the very case it was written for |
| `not preserves` | **FAIL — controls broken** |
| `not fidelity` | Recorded separately: see below. Does not by itself decide the outcome |

### Fidelity failures — the one legitimate repair path

If the code's output differs from `predicted_v2`, exactly one distinction
decides what happens:

- **The code does not implement the frozen rule text** → a bug. Fix the code,
  re-run, and record *both* runs and the diff in `results/RESULT.md`. The rule
  text is authority; the code must match it.
- **The code implements the frozen rule text faithfully, and the author's
  hand-simulation was wrong** → **a result, not a bug.** The rule text stands
  as frozen, the output stands as measured, and `RESULT.md` records that the
  author did not correctly predict their own rule. Do NOT amend the rule text
  to match the prediction, and do NOT amend the prediction.

## Hard stop (carried, unchanged)

Classification only. **No LLM is invoked anywhere in J** — no probes, no
judgements, no fallback. No unpivot/reshape/transformation code, no
normalization, no country mappings, no numeric-format parsing beyond the
`numeric()` predicate above, no multiple sheets, no joins, no procedure
synthesis, no production architecture. No fourth label (`transposed_wide` is
NOT added; the contract's three labels are unchanged). No retuning of `K_w`
/ `K_l`. `gate_I.py`, the I fixtures, and `months.json` are not modified.

## Standing traps (J-specific)

- **"v2 fixes I4" is not a finding.** v2 was written to fix I4. The findings
  are J4 (held-out repair), J3 (predicted cost) and the regression count.
- **Do not tune a fixture, a ground-truth label, or the rule text after the
  replay.** J3 in particular exists to be gotten wrong; "fixing" v2 to pass J3
  after seeing the result would destroy the only load-bearing measurement here.
- **Do not let J retroactively change Experiment I.** I1/I2/I3 PASS and
  I4/I5/I6 FAIL stand as measured; J replays fixtures, not verdicts.
- **v1 is not modified.** It is imported from `gate_I.py` and its sha256 is
  verified at run time. If that hash changes, the run is void.
- **`unknown` is a refusal, not an answer.** Do not report a v2 `unknown` on a
  long table as "correct because conservative"; it is a miss. Report the
  direction separately.
