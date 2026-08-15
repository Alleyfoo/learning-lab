# Experiment U2 — the same probes, with independent evidence DEFINED

**STATUS: FROZEN before any run.** A tightening of U, not a new question.

## What U left open

U stopped T's provenance laundering outright (0/3) and preserved load-bearing
discrimination (3/3 declined to block on irrelevant unknowns). It did not stop an
unsupported binding being established: 2/3 argued

> rests on an INFERRED claim … but independently supported by OBSERVED evidence:
> the collection is named "reservations" and the field is named "date"

The field name is exactly what that claim lists as its `basis`. **The basis of an
inference was re-used as corroboration of it.** That was a defect in the rule as
written — "independent evidence" was undefined, so the model defined it.

## The two changes, and nothing else

```text
1  independent evidence is DEFINED, excluding the claim's own basis AND any
   other evidence of the SAME KIND:
     naming evidence is ONE kind -- a field name and a collection name are not
       independent of each other, and two hints do not add up to a fact
     value-shape evidence establishes what a value IS, never what it MEANS
     independent means documentation, another trusted source, or human
       confirmation
2  phase 2 confirms BOTH load-bearing inferred claims
```

Change 2 exists because **U probe 1 caught the experiment short**, blocking a
second time on the `holidays` meaning, which was still INFERRED. That was correct
behaviour and it demonstrated the property the design depends on:

> **Confirmation resolves claims, not workflows.** Confirming which field is the
> reservation date establishes nothing about what the holidays collection means.

Verified mechanically: of 22 claims, exactly 2 are promoted, and **3 inferences
remain unsettled** (`created`, `ref`, `holidays.name`). None of those three is
load-bearing for this job, so they are a live over-blocking test.

## Expected results

```text
PHASE 1   3/3 BLOCK, naming reservations.date, and NOT over-blocking on tier
          or resource identity
PHASE 2   3/3 produce a node, valid and behaviourally equivalent to the oracle,
          and NOT blocking on the three remaining non-load-bearing inferences
```

**This prediction was recorded in U's result before U2 was built:** *probe 1's
behaviour generalises to 3/3, because it already reasoned correctly under the
looser rule.* It is repeated here unchanged.

## Why a predicted pass is still worth running

The informative outcome is a failure. If a probe still argues past the tightened
rule, the problem is not the rule's precision and the approach needs rethinking
rather than sharpening. If phase 1 blocks 3/3 but phase 2 then over-blocks on
`created` or `ref`, confirmation has unblocked nothing and the mechanism is
unusable in practice.

## Decision rules

```text
phase 1 3/3 block + phase 2 3/3 equivalent   the branch is done. Record and
                                             STOP. Next question is the
                                             inspector side, which is different.
any probe argues past the rule               the rule is not the fix. Quote it.
phase 2 blocks on non-load-bearing claims    confirmation does not unblock;
                                             the signal would be ignored in
                                             practice.
```

No retries. Grader reused from U unchanged.

## Stated limitation

Same as U: one node, one purpose, one constructed report, three samples per
phase, `glm-5.2`, no seed control. U2 tests whether a **defined** rule closes a
**specific** hole. It says nothing about an inspector producing statused claims
in the first place — that is the untested half and a separate experiment.
