# RFCs — Requests for Comments

An RFC is a **proposal**. It is written when a substantial change needs discussion before it can become authority.

An RFC is never implementation authority by itself. An accepted RFC produces one of:

- an **ADR** in [`../decisions/`](../decisions/), when the outcome is a durable architecture decision; or
- a **roadmap item** in [`../roadmap/`](../roadmap/), when the outcome is authorised direction.

The RFC itself stays as the record of the discussion, not as the record of the decision.

## When to write one

Write an RFC when at least one is true:

- the change would alter an authority boundary, an established interface, or the product's shape;
- more than one reasonable design exists and the choice is not obvious;
- the change would make several later pieces of work necessary;
- it would change what an existing accepted ADR decided.

Do not write one for bounded, well-understood work. That goes to [`../development/initiatives.md`](../development/initiatives.md) and, if accepted, through the ordinary lifecycle.

## Index

| RFC | Title | Status | Date |
| --- | --- | --- | --- |
| _(none yet)_ | | | |

## Status values

| Status | Means |
| --- | --- |
| `Draft` | Being written. Not ready for discussion. |
| `In discussion` | Open for comment. |
| `Accepted` | Roundtable agreed. Points to the ADR or roadmap item it produced. |
| `Rejected` | Declined. Kept, because the reasoning is the useful part. |
| `Withdrawn` | The author withdrew it. |

## Numbering

Sequential, zero-padded to four digits, never reused: `RFC-0001-short-slug.md`.

## Template

```markdown
# RFC-NNNN: <short title>

**Status:** Draft | In discussion | Accepted | Rejected | Withdrawn
**Date:** YYYY-MM-DD
**Author:** <who>

## Problem

What is wrong or missing today, grounded in the repository — files, evidence, or an
observed failure. Not a general concern.

## Proposal

What to do. Specific enough to disagree with.

## Alternatives

What else was considered, and why this one.

## What this would change

Authority boundaries, interfaces, existing ADRs, roadmap items, and any evidence that
would need re-running.

## Open questions

What is genuinely undecided, and who would have to decide it.

## Outcome

Filled in when the RFC is closed: the ADR or roadmap item it produced, or the reason
it was rejected.
```
