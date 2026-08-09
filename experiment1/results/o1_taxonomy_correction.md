# O1 Taxonomy Correction — O1a / O1b / O1c

**RUN A numbers are not changed. The contract is not changed.** This is a re-labelling of
already-measured events under a corrected taxonomy.

---

## Why a third category was needed

Amendment C8 split O1 into two: `O1a` unwarranted execution (system failure) and `O1b`
warranted but wrong (the N1 boundary, not a system failure). RUN A produced events that fit
neither.

`COS_case_whitespace` and `COS_period_format` are authorized while producing non-equivalent
output. They are not O1a — the warrant was fully current. They are not O1b either: **the change
is not below the detection floor.** The period total is *unchanged* (0.00% shift), so the floor
is irrelevant to them. They pass because the contract has **no predicate of the right kind at
all** — L2 checks dtype, null rate and cardinality, and a case fold changes none of those.

Filing these under O1b would let a genuine contract gap hide behind N1. That is precisely the
move the non-claim exists to prevent: N1 excuses what is *too small to see*, never what is
*not looked at*.

---

## Corrected taxonomy

| Metric | Definition | Owner | Excusable? |
| --- | --- | --- | --- |
| **O1a — unwarranted execution** | Procedure ran while warrant was absent or expired | Authorization logic | **No.** System failure |
| **O1b — warranted but wrong, below declared capability** | Ran with valid warrant; output non-equivalent; the change is smaller than the declared detection floor | Epistemic limit (N1) | **Yes** — declared in advance |
| **O1c — warranted but wrong, NOT below declared capability** | Ran with valid warrant; output non-equivalent; the change is **not** excused by the floor because no predicate covers its class | Contract coverage | **No.** System failure |

The discriminator between O1b and O1c is: *would the declared capability have excused this?*
If the change is invisible to every declared predicate for a reason the contract never stated,
it is O1c.

---

## RUN A re-labelled (same events, same counts)

| Metric | Count | Events |
| --- | --- | --- |
| **O1a** | **0** | Evidence held fresh throughout RUN A by design. Measured properly in the expiry run |
| **O1b** | **7** | `SEM_invisible` 1/1, `SEM_creep` 6/12 — sub-floor measure redefinition |
| **O1c** | **22** | `COS_case_whitespace` 11/12, `COS_period_format` 11/12 — value-level identity drift |
| **O2** false escalation | 0.0833 | 1 of 12 unchanged control periods |
| **O3** above-floor miss | 0 | — |
| **O4** correct undecidability | 7 | Same event set as O1b |

Previously the 22 O1c events were reported as "O1b system failure" and the label was
self-contradictory — O1b is by definition *not* a system failure. The 22 are real failures;
they are now filed where they can be counted as such.

### O1b and O4 are the same events under two lenses

Deliberate, not double counting:

- **O1b** counts the *event*: the procedure ran and the output was wrong.
- **O4** judges the *conduct*: the system did not overclaim, and reported "no evidence of
  change at floor X" rather than "unchanged".

Both are true of the same seven rows. Reporting only O4 would hide that wrong output was
produced; reporting only O1b would hide that the system behaved correctly given what it had
declared.

---

## Consequence for the identity gap

O1c = 22 is now the headline defect from RUN A. Per instruction, **no value-level identity
predicate is implemented yet.** Whether it warrants Experiment 2 or a contract amendment is
decided after Experiment 1 closes, not during it.
