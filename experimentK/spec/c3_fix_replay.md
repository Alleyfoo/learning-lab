# Experiment K — C3-fix replay (recipe format v1.1): preregistration

**STATUS: FROZEN before `grade_K_v11.py` exists.** A **separate measurement**,
not a revision of K. K's result (`PASS_AS_PREDICTED`, `5510240`) stands as
measured against recipe format v1 and is not re-graded.

Deterministic — **no LLM anywhere.**

## What changed and why

K measured two costs. C3 — the *ordinary monthly case*, two more products — came
out `REDEFINE_SCOPED` when it should be `EXECUTE`, because recipe format v1
anchors the data region absolutely (`sheet:Sales!5:8`) and the total row
positionally (`sheet:Sales!9`). That is an escalation on the one case saved
recipes exist for.

**Format v1.1 (the C3 fix):**

```text
data_region: "remainder"     data = every row the header and exclusions
                             leave behind, so the region grows with the file

exclude by RULE              {"rule": {"op": "label_in",
                                       "column": "sheet:Sales!@Tuote",
                                       "values": ["YHTEENSÄ"]}}
```

The principle: **anchor positionally from the stable end, by rule from the
unstable one.** A preamble sits at the top and does not move; a grand total sits
at the bottom and moves every month.

`label_in` takes a **literal value list — no patterns, no regex.** That is a
security choice, not a simplification: a rule is a predicate over untrusted cell
content, and a pattern language would be an expression language arriving through
the back door. Literal lists stay inspectable by the human who approves them.

## The cost this replay exists to measure

`remainder` absorbs **whatever is left over** — which is exactly why C3 works,
and exactly what makes it dangerous. Under v1, an unexplained row was caught as
`row_unclassified`. Under v1.1 it silently becomes data.

**C13** is authored for this: a footnote row (`Huom: sisältää palautukset`)
appended below the grand total.

```text
v1    rows 5:8 are data, row 9 is excluded, row 10 is claimed by nothing
      -> row_unclassified -> REDEFINE_SCOPED      (correct)
v1.1  preamble excluded, YHTEENSÄ excluded by rule, EVERYTHING ELSE is data
      -> the footnote becomes a data row -> EXECUTE   (wrong)
```

So the fix is predicted to **trade a safe-direction failure for an unsafe one**.
That is the measurement, and it is named before the run.

## Predicted outcomes (FROZEN)

Both arms over 13 cases. `truth` is what a careful human would want.

| ID | truth | v1 (measured in K) | v1.1 predicted |
| --- | --- | --- | --- |
| C1 | `EXECUTE` | `EXECUTE` | `EXECUTE` |
| C2 | `EXECUTE` | `EXECUTE` | `EXECUTE` |
| C3 | `EXECUTE` | `REDEFINE_SCOPED` ✗ | **`EXECUTE`** ✓ *the fix* |
| C4 | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` |
| C5 | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` |
| C6 | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` |
| C7 | `DEFINE` | `DEFINE` | `DEFINE` |
| C8 | `REDEFINE_SCOPED` | `EXECUTE` ✗ | `EXECUTE` ✗ *unchanged blind spot* |
| C9 | `DEFINE` | `DEFINE` | `DEFINE` |
| C10 | `AMBIGUOUS` | `AMBIGUOUS` | `AMBIGUOUS` |
| C11 | `BLOCKED` | `BLOCKED` | `BLOCKED` |
| C12 | `BLOCKED` | `BLOCKED` | `BLOCKED` |
| C13 | `REDEFINE_SCOPED` | `REDEFINE_SCOPED` ✓ | **`EXECUTE`** ✗ *the cost* |

```text
predicted   v1    11/13   over_escalation {C3}   false_execute {C8}
            v1.1  11/13   over_escalation {}     false_execute {C8, C13}
```

**The scores are predicted to tie.** v1.1 is not "better" — it moves one failure
from the safe direction to the unsafe one. Under the security framing that is the
whole point: relative anchoring buys automation and pays in detection.

C4 note: v1.1's exclusion rule references `sheet:Sales!@Tuote`, so renaming that
header breaks the rule as well as the field. Both surface as
`unresolvable_referent`; the dispatch is unchanged.

## Decision table

| Condition | Outcome |
| --- | --- |
| every v1.1 cell matches the prediction | **PASS_AS_PREDICTED** — the fix works and its cost is exactly the one named |
| C3 is not `EXECUTE` under v1.1 | **FAIL_FIX** — the fix does not fix the case it was written for |
| a false EXECUTE appears outside `{C8, C13}` | **FAIL_UNSAFE** — record, do not tune |
| any v1 cell differs from K's measured result | **VOID** — the v1 arm must reproduce K exactly |
| v1.1 differs from prediction but the code matches this spec | a **result**: the author mis-predicted. Record; amend nothing |

## Hard stop

Replay only. No execution of any recipe, no LLM, no changes to the frozen
referent grammar, no changes to K's `expected.json` or its recorded result, and
**no v1.2** — in particular, no row-shape expectation to catch C13. That is the
obvious next fix and it must be measured, not assumed.

## Standing traps

- **v1.1 is not an improvement to be assumed.** The predicted tie is the finding.
- **Do not regenerate fixtures.** `.xlsx` output is not byte-reproducible; see the
  erratum in `preregistration.md`. `make_candidates.py` now takes a single stem.
- **Do not fix C8 or C13 during this replay.**
- K's `expected.json`, fixtures C1–C8 and `results/K.json` are frozen inputs here.
