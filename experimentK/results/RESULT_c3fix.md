# Experiment K — C3-fix replay (format v1.1): PASS_AS_PREDICTED

Every frozen prediction held on all 13 cases, in both arms. The v1 arm
reproduced K's recorded run exactly (required, or the replay would be VOID).

```text
ID   changed                             truth            v1                 v1.1
C1   nothing                             EXECUTE          EXECUTE ok         EXECUTE ok
C2   the filename only                   EXECUTE          EXECUTE ok         EXECUTE ok
C3   two more products                   EXECUTE          REDEFINE_SCOPED ✗  EXECUTE ok
C4   Tuote -> Tuotekoodi                 REDEFINE_SCOPED  REDEFINE_SCOPED ok REDEFINE_SCOPED ok
C5   a Maa column inserted at B          REDEFINE_SCOPED  REDEFINE_SCOPED ok REDEFINE_SCOPED ok
C6   a new Kampanjat sheet               REDEFINE_SCOPED  REDEFINE_SCOPED ok REDEFINE_SCOPED ok
C7   Sales -> Myynnit                    DEFINE           DEFINE ok          DEFINE ok
C8   product row -> subtotal             REDEFINE_SCOPED  EXECUTE ✗          EXECUTE ✗
C9   empty recipe store                  DEFINE           DEFINE ok          DEFINE ok
C10  two recipes claim it                AMBIGUOUS        AMBIGUOUS ok       AMBIGUOUS ok
C11  recipe edited after approval        BLOCKED          BLOCKED ok         BLOCKED ok
C12  blocking ambiguity open             BLOCKED          BLOCKED ok         BLOCKED ok
C13  a footnote row below the total      REDEFINE_SCOPED  REDEFINE_SCOPED ok EXECUTE ✗

v1    11/13   over_escalation {C3}   false_execute {C8}
v1.1  11/13   over_escalation {}     false_execute {C8, C13}
```

## The fix works, and the score did not move

C3 — the ordinary monthly case — went from `REDEFINE_SCOPED` to `EXECUTE`.
`remainder` absorbed the two extra products and the `label_in` rule found the
`YHTEENSÄ` row at its new position. That is the whole economic argument for
saved recipes: next month's file runs with **no model involved at all**.

**And the totals tied at 11/13.** v1.1 is not better. It moved a failure from
the safe direction to the unsafe one:

```text
v1    1 over-escalation + 1 false execute
v1.1  0 over-escalations + 2 false executes
```

C13 is the cost, and it landed for the predicted reason: a footnote row
(`Huom: sisältää palautukset`) appended below the total. Under v1 it was caught
as `row_unclassified`. Under v1.1, `remainder` means *whatever is left over is
data* — so the footnote silently became a data row.

**The same property that makes the fix work is what makes it dangerous.** That
is not a flaw in the implementation; it is what relative anchoring *is*.

## Read as a security result

This lab's question is containment: can an agent be put beyond the line — never
facing untrusted human-side content at runtime — while the system stays useful?
The replay measures one point on that trade-off, and it is not free.

```text
v1    smaller automation envelope, larger detection surface
      more files escalate to a human; unexpected structure is caught
v1.1  larger automation envelope, smaller detection surface
      more files execute with no model present; unexpected structure is absorbed
```

**Every case in this replay is decided by deterministic code with no model in
the loop**, so nothing here depends on an agent behaving. That is the property
worth having: `EXECUTE` invokes nothing, `BLOCKED` is enforced by a content hash
(C11), and a refusal cannot be argued out of. Semantic compromise of a
definition-phase agent still cannot produce authority, because the recipe it
proposes must pass deterministic validation and a human approval bound to a hash
before anything runs.

But the guarantee is **structural, not semantic**, and C8 and C13 are exactly
that boundary: both are structurally clean and semantically wrong. A front door
built on shape can certify *"this file has the structure the approved recipe
describes"* — it cannot certify *"the rows mean what they meant last month."*
Widening the automation envelope widens what falls inside that gap.

## What this points at, unmeasured

The obvious v1.2 is a **row-shape expectation**: declare what a data row looks
like (a non-blank id, numeric measures) so a footnote or a subtotal fails to
qualify and escalates. It would plausibly recover C13 and C8 both.

It is deliberately **not built here** — the hard stop forbade it, and it is the
third time in this programme that "the obvious next fix" has arrived with a cost
that was only visible once measured (J's v2 → J3; K's C3 → C13). It should be
frozen and measured like the others, not assumed.

## Limitations

- 13 in-lab candidates from one workbook. A controlled replay, not a prevalence
  estimate of how providers actually change files.
- The two arms are compared on the same fixture set, chosen partly *because* it
  contains the failure modes at issue. The tie is a statement about this set.
- Deterministic and fully repeatable: no LLM, no seeds, no sampling.
- `label_in` matches literal values only, by design. A provider writing
  `Yhteensä yht.` instead of `YHTEENSÄ` would not match — that is a
  `REDEFINE_SCOPED`-shaped miss under v1.1's remainder (it would be absorbed as
  data), and it is untested here.
