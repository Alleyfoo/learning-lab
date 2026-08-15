# Is the numeric-failure policy a reusable capability? — 2026-08-15

Asked after reconciliation acquired numeric semantics **because the job needed
them** (tolerance comparison of balances), giving a third data point arrived at
by need rather than by writing another sibling in the same style.

**Answer: it is a shared PATTERN, not shared machinery. Nothing moves — not into
the envelope, and not into a shared body helper either.**

## The evidence

### 1. Where the policy appears

```text
reservation      reservation_v1     none
enrichment       enrichment_v1      refuse_row
aggregation      aggregation_v1     refuse_row
reconciliation   reconciliation_v1  none      key presence only
reconciliation   reconciliation_v2  none      string comparison
reconciliation   reconciliation_v3  refuse_key  <- tolerance comparison
```

The sharpest line is the last three: **within one task, held otherwise constant,
the policy is absent until a numeric comparison is declared.** And it is not
merely observed — the model validator *requires* it once `within` appears and
*refuses* it when nothing is compared numerically
(`policy_comparison_mismatch`, enforced both directions).

That is much stronger than the earlier cross-task tally, because the confound —
same author, same week, same style — is held fixed.

### 2. The allowed values differ

```text
enrichment       ("refuse_row", "refuse_run")
aggregation      ("refuse_row", "refuse_run")
reconciliation   ("refuse_run", "refuse_key")
```

Not a naming quibble. `refuse_row` names a thing that **does not exist** in
reconciliation: its output is one row per key in the union of two peers, so
there is no driving-source row to drop. `refuse_row` is refused there as
`unknown_policy`, and that refusal is tested.

### 3. What is actually common, and what is not

```text
COMMON      the SHAPE: a declared policy naming what happens when an operand
            the model called numeric is not one, offering "refuse the unit" or
            "refuse the run", with the failure named rather than coerced.

NOT COMMON  the unit. row / row / key.
NOT COMMON  whether it is required. Always, always, conditionally.
NOT COMMON  what triggers it. Computing / summing / comparing.
```

## Why nothing moves

**Not into the envelope.** The envelope owns identity, sources, and the task
registry — things every task has regardless of its data. A policy about numbers
is about the DATA, and reservation and reconciliation-v1/v2 are complete tasks
without one.

**Not into a shared body helper either**, which is the more tempting error. A
helper would have to be parameterised by the unit name, by whether the policy is
required, and by what makes it required — at which point it carries no
knowledge the three call sites do not already state more clearly in eleven lines
each. It would centralise a *coincidence of shape* while the three meanings
stayed different, and the next task with a fourth unit would either bend the
helper or quietly adopt the wrong vocabulary.

Recording the pattern is the useful move; extracting it is not.

## What would change this answer

A fifth task whose numeric-failure unit is **also** a row, and which is required
unconditionally, would make enrichment/aggregation/it a genuine three-of-a-kind
with one meaning. That is the evidence to wait for — and, as with this round, it
should arrive because a job needed it.

## Method note

This re-examination was run by **counting**, not remembering. The previous tally
in this programme was stated from memory as 3-of-4 and was actually 2-of-4; the
correction changed the conclusion's strength. The evidence above is regenerated
by `run_reconciliation.py`'s `policy_appears_only_with_numeric_comparison` check
on every run, so it cannot quietly go stale.
