# Fix — LIM-4 and PRO-2: one executor contract, enforced from both sides

**Status: fixed and verified 2026-08-14** (`16c392f`). Not an experiment — a
defect repair, with the audit that found it and the verification that it holds.

## LIM-4 was an instance of PRO-2, not a separate bug

The ledger listed both as live defects. Auditing every capability the recipe
format declares against what actually consumes it showed they are the same
defect wearing four faces. Three of the four were **previously unrecorded**, and
all four were verified empirically before anything was changed.

| # | Declared by | Not honoured by | Observed behaviour |
| --- | --- | --- | --- |
| 1 | two `period_measure` fields | executor keeps one unpivot | validates, executes, **4 of 8 rows**, no signal (Experiment M, S3) |
| 2 | transform op `coerce` | implemented nowhere | `valid=True`, `EXECUTE`, ran, **transform silently dropped** |
| 3 | sheet role `metadata` | executor reads only data sheets | `valid=True`, ran, **sheet contributed nothing**, nothing said so |
| 4 | 15 of 23 validator problem codes | dispatcher classified 8 | **`valid=False` → `dispatch=EXECUTE`** |

Number 4 is the worst and was the least visible. Demonstrated with three
separate structural defects — `unknown_transform_op`, `missing_exclude_reason`,
`unknown_type` — each reported invalid by the validator and each authorised by
the front door:

```text
unknown_transform_op     valid=False   dispatch=EXECUTE
missing_exclude_reason   valid=False   dispatch=EXECUTE
unknown_type             valid=False   dispatch=EXECUTE
```

The executor happened to refuse afterwards, because it re-checks validity — so no
wrong data reached an output. But the component whose entire job is to decide was
returning the wrong decision, and anything downstream that trusted it (a UI, a
scheduler, a queue) would have acted on `EXECUTE`.

## The pattern, and why four patches would have been the wrong fix

Every instance is the same shape: **one layer declares a capability, another does
not implement it, and nothing compares the two.** Patching each site would have
left the fifth instance to be discovered the same way — by accident, in an
experiment aimed at something else.

## The fix

**`definition_phase/harness/executor_contract.py`** declares once what the
executor can honour, and requires every format enum value to be classified:

```python
SUPPORTED_TRANSFORM_OPS   = {"unpivot", "derive"}
UNSUPPORTED_TRANSFORM_OPS = {"coerce": "implemented nowhere; would be dropped"}
SUPPORTED_SHEET_ROLES     = {"data", "ignore"}
UNSUPPORTED_SHEET_ROLES   = {"metadata": "executor reads only data sheets"}
MAX_UNPIVOTS_PER_SHEET    = 1
```

`assert_contract_total()` runs at import and fails if a value is neither
supported nor explicitly unsupported, or if an unsupported entry has no reason.
**Adding a capability without deciding is now impossible to do quietly.**

**The validator** imports the contract and emits `executor_cannot_honour` for an
unsupported transform op, an unhonoured sheet role, an unsupported derive source,
or more unpivots per sheet than the executor keeps.

**The dispatcher** gains `STRUCTURAL_CODES` and `APPROVAL_CODES`, routes a
non-validating recipe to `BLOCKED` — a broken recipe is not a drifted file, and
telling a human to "scope a redefinition" would misdescribe it — and calls
`assert_codes_classified()` **at import**, which fails if any validator code is
unclassified *or* if the dispatcher classifies a code the validator never emits.
Both directions, so the two cannot drift apart in either.

## Verification

```text
defect                        valid  dispatch  executor
two unpivots                  False  BLOCKED   refused
coerce transform              False  BLOCKED   refused
metadata sheet role           False  BLOCKED   refused
unknown_transform_op          False  BLOCKED   refused
unknown_type                  False  BLOCKED   refused

control: unmodified approved recipe  ->  EXECUTE
```

The control matters as much as the five: a rule that also refused good recipes
would be worse than the defect.

**No regression.** All four Experiment K arms and Experiment L reproduce
**byte-identically** after the change.

**Experiment M is deliberately not re-graded.** Its numbers measured the pre-fix
code and stand as recorded; an erratum in `experimentM/results/RESULT.md` says so
and warns against overwriting `results/M.json` with a post-fix run. Re-running it
now reports S3 as `GAP, silent_wrong=False` — *"recipe INVALID: the system refuses
rather than producing a wrong table"* — which is the fix working, not a
correction to the measurement.

## What this does and does not change in the ledger

**LIM-4** moves from *live defect* to *fixed*: the format still cannot express two
measure blocks, but it now **refuses** instead of silently producing half a table.
The expressiveness gap remains and is still a gap (Experiment M's classification
is unchanged).

**PRO-2** moves from *live defect* to *guarded*. The three instances found before
this fix, plus the fourth found by the audit, are all closed, and the assertions
make a fifth instance loud rather than silent.

**It does not make the class impossible.** The assertions compare *declarations*.
A capability that both layers claim to support but implement differently would
pass both — the contract checks that the executor was *told* about a capability,
not that it implements it correctly. That is the next weakness in this line, and
it is untested.
