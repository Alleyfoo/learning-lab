# Observable Error — v1 (designer, 2026-08-15)

## The rule

> A diagnostic counts as **surfaced** only if it is presented alongside the
> authoritative result or the review. Internal logging alone does not turn a
> silently degraded output into a successful one.

## What it governs

Everything that can produce a result the consumer would otherwise read as clean:
gap G1 (`date` with no format string), gap G2 (ambiguous thousands/decimal
separator), any future unhonoured declaration, and every later gap of the same
shape. It is the standard the programme had been answering two ways.

## The distinction that makes it operable: DEGRADED vs INCOMPLETE-BY-FACT

The rule bites on **degraded** output, not on output that is merely smaller than
someone expected.

```text
DEGRADED             the result does not deliver what the recipe DECLARED.
                     A field declared `number` delivering strings is degraded:
                     the table looks complete while a column is not what it
                     claims. A diagnostic is OWED, and must travel with the
                     result.

INCOMPLETE-BY-FACT   the result delivers exactly what was declared, and the
                     source simply had less in it. A sheetset member with a
                     header and no data rows contributes zero: every value is
                     right, nothing is misrepresented. NOTHING is owed.
```

This is why the two rulings of 2026-08-15 are consistent rather than opposed:

- **Cross-sheet law 2, "a silent zero is acceptable."** A zero-contribution
  member is incomplete-by-fact. The table is correct.
- **Experiment M's `S5_formatted_numbers`, graded `silent_wrong`.** The declared
  type was not honoured, so the output is degraded — and M was right to call it
  silent, because a consumer reading 4/4 rows never saw the side channel.

## Enforcement — the rule is only worth stating if it is checkable

Following `operating_procedure.md` §2.1, the rule is not left as prose.

1. **`Execution` computes `degraded` and `degradation` from its own state.** They
   are derived, not set by callers, so a result cannot be constructed that is
   degraded and does not say so.
2. **`Execution.as_dict()` places `degraded` alongside `columns` and `rows`.** The
   authoritative table and the fact that it is degraded are the same artifact. A
   consumer that serialises the result cannot obtain the table without the flag.
3. **`scripts/check_surfaced.py` verifies the invariant and registers a canary.**
   A degraded execution whose flag is suppressed must be detected; if that canary
   ever stops firing, the check has stopped checking.

### What this does NOT claim

The mechanism binds the *result object*. It cannot force a downstream consumer to
read the field it is handed — no in-process mechanism can. What it removes is the
case where the degradation was never in the artifact at all, which is the case
that actually occurred: `unhonoured_types` existed, and M still correctly graded
the output as silent because the table was separable from it.

## Open: the REVIEW surface

The rule names "result **or review**". This document and its check cover the
result. The review surface is `definition_phase/harness/approval.py`, whose
renderer is already versioned for exactly this kind of change (`review-v1` →
`review-v2` added hidden-content findings, and `meets_current_review_policy`
already refuses to confer a newer renderer's protections on an older approval).

A `review-v3` showing declared types the executor cannot honour **on this
workbook** is the natural next step and belongs in its own freeze. It is not done
here, and until it is, the rule is enforced at the result surface only.
