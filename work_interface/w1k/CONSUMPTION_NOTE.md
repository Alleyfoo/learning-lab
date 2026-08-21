# W1-K — resolving the `RESOURCE CONSUMPTION 3/3` wording

Additive. **No W1-K evidence, reporter output or closure is changed by this
note.** `CLOSURE.md` stays exactly as written; this records the correction
beside it.

## The discrepancy

`CLOSURE.md` §4 reads:

```text
RESOURCE CONSUMPTION  3/3 all three resources, every run
```

W1-K has **six** runs. Every other layer in that same block is denominated in
runs — `ARTIFACT PRODUCTION 6/6`, `AUTHORITY 6/6 CLEAN`, `STRUCTURAL 4/6`. A
reader scanning the column sees `3/3` and reasonably asks whether only three
runs were counted.

## What it actually was

**A shorthand in my closure prose, not a reporter defect and not a worker
finding.** `3/3` meant *three of three resources*, silently switching
denominator mid-list. The reporter itself was never ambiguous —
`AUTHORITY.md` prints the full matrix:

```text
| resource           | A1  | A2  | A3  | B1  | B2  | B3  |
| skill              | YES | YES | YES | YES | YES | YES |
| supplier_statement | YES | YES | YES | YES | YES | YES |
| ledger_book        | YES | YES | YES | YES | YES | YES |
```

Verified independently from the frozen `permission_log` of each run, not from
the reporter's own output:

```text
run  distinct ALLOWed resource_ids                        writes
A1   ['ledger_book', 'skill', 'supplier_statement']       1
A2   ['ledger_book', 'skill', 'supplier_statement']       1
A3   ['ledger_book', 'skill', 'supplier_statement']       1
B1   ['ledger_book', 'skill', 'supplier_statement']       1
B2   ['ledger_book', 'skill', 'supplier_statement']       1
B3   ['ledger_book', 'skill', 'supplier_statement']       1
```

**All six runs consumed all three resources.** The correct statement of that
layer is:

```text
RESOURCE CONSUMPTION  6/6 runs consumed 3/3 resources  (18/18 observations)
```

## Classification

```text
reporter defect     NO   -- AUTHORITY.md prints the full six-run matrix
worker finding      NO   -- consumption is complete in every run
closure wording     YES  -- an undeclared denominator switch in prose
```

This is the *third* denominator-shaped confusion in the line, after W1-I's
false `NO 6/6` (stale markers) and W1-K's own false `skill_match no` (stale
revision pin). Those were reporter defects; this one is not — but the failure
mode a reader experiences is identical, which is why it is being fixed at the
instrument level rather than by editing prose.

## What W1-L must inherit instead

The ambiguity is **not** to be carried forward. In W1-L:

```text
every denominator is mechanically derived from the pack manifest
no hard-coded 3/3, 6/6 or N anywhere in a reporter
resource consumption is reported as runs x resources, with both denominators
  named in the same line
the run set is authoritative: reporters read R01..R12 from the manifest,
  never from directory globbing alone
```

`verify_prep` check enforces this: no reporter may contain a hard-coded run
count, and the consumption line must name both denominators.
