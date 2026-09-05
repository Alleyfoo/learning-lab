# Architecture Decision Records

An ADR records a **durable** architecture or engineering-system decision and the reasoning behind it. It exists so a future contributor does not have to reconstruct the choice from commit history.

Use an ADR when the decision constrains future work. Do not use one for ordinary implementation detail, or for an experimental observation that has not become authority — those belong in an experiment closure or in [`../development/initiatives.md`](../development/initiatives.md).

## Index

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](ADR-0001-development-governance.md) | Development governance and authority loop | Accepted | 2026-09-05 |
| [0002](ADR-0002-architecture-model-grounding.md) | Architecture models are measured, not asserted | Proposed | 2026-09-05 |

## Status values

| Status | Means |
| --- | --- |
| `Proposed` | Written, not yet decided. Not authority. |
| `Accepted` | Decided. Authority, at precedence rank 2 (see the engineering system, §7). |
| `Rejected` | Considered and declined. Kept, because the reasoning is the useful part. |
| `Superseded by ADR-NNNN` | Replaced. Kept unchanged; the successor explains what changed. |
| `Deprecated` | No longer applies, with nothing replacing it. |

An accepted ADR is **never edited to reflect a later decision**. It is superseded by a new one. The record of what was decided, and when, is the point.

## Numbering

Sequential, zero-padded to four digits, never reused: `ADR-0003-short-slug.md`.

## Template

```markdown
# ADR-NNNN: <short decision title>

**Status:** Proposed | Accepted | Rejected | Superseded by ADR-NNNN | Deprecated
**Date:** YYYY-MM-DD

## Context

The problem, and what in the repository makes it a problem. Ground it: name files,
evidence or observed failures rather than describing a general concern.

## Decision

What was decided, stated so that a future contributor can tell whether a change
complies with it.

## Alternatives considered

Each material alternative and why it was not chosen. Omit only when there genuinely
were none.

## Consequences

What this makes easier, and what it costs. A decision with no costs listed is usually
under-examined.

## Related

Documents, code paths and evidence this decision depends on or affects.
```
