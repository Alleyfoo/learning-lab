# W1-I frozen human-answer script (fixture T)

The **controlled variable** for W1-I. Both arms — r2 and r3 — receive this exact
block, built mechanically from the table below by the frozen
`w1b/harness/block_harness.py`. The operator invents nothing, corrects nothing,
and repairs nothing.

The answers are the business information for the fixture-T pair:

```text
work_interface/w1i/fixtures/vendor-charge-summary.txt
work_interface/w1i/fixtures/internal-charge-ledger.txt
```

They are **identical for both arms**. The only arm-level variable in W1-I is the
skill revision.

## Why this table exists separately from W1-A's

Fixture T is a different input, so its business answers name T's fields. The
table format is unchanged, so the frozen block builder and the frozen fidelity
checker both operate on it without modification: rows 0–5 are mandated and form
the canonical block; rows 6–8 are excluded and are delivered only if the worker
asks.

## The table

| Intent Goose is asking about | Canonical answer (say this verbatim) |
|---|---|
| Which field identifies the **same record / charge line** in both files? | `Client Ref` |
| Should **Net Value** be compared, and if so, how and with what tolerance? | Yes, compare Net Value numerically, within 0.01. |
| Is **Tax Band** part of the reconciliation rule? | No. Tax Band is recorded on the vendor side only; it is not compared and is not part of the rule. |
| Which file is the **source of truth** for matching? | Neither — both are peer sources. Report what is missing from either side and differences in the compared field. |
| Which fields should appear in the **report row**? | The match key (Client Ref) and the compared field (Net Value). |
| Which fields are **context** for the report? | Charge Period and Settlement State. |
| What should happen if the same key appears **more than once** in a source? | Refuse the run — do not silently pick or merge. |
| What should happen if a compared value is **not a number**? | Refuse the run — do not coerce. |
| Anything about the **Remarks** field in the ledger? | It is not load-bearing for now; leave it as an open, non-load-bearing question. Do not make it part of the rule. |

## Operator discipline

- Deliver the mandated block once, verbatim, exactly as the harness builds it.
- Do not paraphrase, expand, reorder or explain.
- Do not answer a question that is not in the table; excluded rows are delivered
  only if the worker asks for that specific thing.
- Do not comment on the worker's field names, spelling or whitespace under any
  circumstances. **That is the measurement.**
