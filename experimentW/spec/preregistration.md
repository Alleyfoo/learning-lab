# Experiment W — can an inspector's own uncertainty stop an unsupported binding?

**STATUS: FROZEN before any run.**

## The one bug V found

V's boundary held for inference and leaked for uncertainty:

```text
OBSERVED   machine-owned   structured   addressable
INFERRED   LLM-owned       structured   addressable
UNKNOWN    LLM-owned       free text    NOT addressable
```

So *"tier is probably a service level, but I don't know what tier means"* had its
first half attached to `reservations.tier` and its second half floating. 0 of 23
unknowns were machine-addressable. Carrying epistemic status forward is pointless
if half of it cannot be associated with a subject.

## The fix, and nothing else

`UNKNOWN` becomes structurally parallel to `INFERRED`. `source` is required;
`field` is required but may be `null` for a whole-collection question; `source`
may be a list where a question genuinely spans collections. An unaddressed
unknown is rejected at the boundary — `unknown_without_referent`.

V's own output is the canary: the verbatim floating unknown from
`V1_probe1_raw.txt` is now refused, and both halves of the `tier` pair now share
one address.

Confirmation also becomes referent-based and works on `UNKNOWN` as well as
`INFERRED` — a human answering *"what does tier mean?"* settles it, and V's
confirm could only promote inferences.

## The chain

```text
raw data
  -> PROGRAM produces OBSERVED claims                 U's claims.py, unchanged
  -> LLM produces INFERRED + UNKNOWN, addressed       stage 1
  -> MODELLER receives all three, referents intact    stage 2, U2's rule verbatim
  -> load-bearing INFERRED/UNKNOWN -> block BY REFERENT
  -> human confirms exactly those referents           mechanical, no hand-picking
  -> MODELLER resumes                                 stage 3
```

**What separates this from U2:** U2's report was hand-built, so the load-bearing
claims were known to the experimenter in advance and the confirmation step was
written before the run. Here the modeller receives whatever the inspector
actually produced, and stage 3 confirms exactly what stage 2 asked for. If the
inspector produces a report that is useless to the modeller, W will show it.

The block is structured for the same reason the claims are. A modeller blocking
in prose cannot have its question answered mechanically, and V established what
happens to anything left in prose.

## Checks — structural, and each able to fail

```text
W-1  addressed          every accepted claim has a machine-addressable referent
W-2  blocked            stage 2 returns a block, not a node
W-3  load-bearing       the block names reservations.date and/or holidays
W-4  no over-block      the block does not name tier, ref, created or name
W-5  confirmation exact the promoted claims are exactly those at named referents
W-6  resumes            stage 3 yields a node, valid and oracle-equivalent
```

W-5 and W-6 reuse `grade_U.grade_phase2` and `grade_T` unchanged. `tier` is the
over-block probe: genuinely unsettled, and irrelevant to a date decision.

## On grading, revised

The methodology claim this programme was leaning on — *prefer structural grading
because prose grading is unreliable* — is too strong. V-D was fully structural
and still encoded the wrong success criterion.

The defensible version:

> Prefer explicit representations because they make both system behaviour and
> grader assumptions inspectable. **The grader still needs falsification.**

That fits all four grader failures. Every check here has a canary that makes it
fail on a constructed input.

## Expected results

```text
W-1  3/3   the boundary enforces it; a failure means a defect in the boundary
W-2  3/3   the binding rests on an INFERRED naming claim, as in U2
W-3  3/3
W-4  3/3   U2 got this 3/3 with a hand-built report
W-5  3/3   mechanical
W-6  2-3/3 U2 got 2/3, the miss being an ordinary modelling error
```

## What would be informative failure

```text
stage 1 emits unaddressed unknowns    the instruction is not enough and the
                                      schema must carry it -- a real finding
                                      about where a constraint has to live
W-2 fails                             the inspector's own report is weaker than
                                      the hand-built one. THE most interesting
                                      outcome: it would mean U2's result
                                      depended on a report an experimenter wrote
W-4 fails                             a real inspector produces more unknowns
                                      than a hand-built report, and the modeller
                                      drowns. Practical unusability
W-2 passes but W-6 fails              blocking works, confirmation does not
                                      unblock, the mechanism stalls
```

## Decision rules

```text
W-1..W-6 broadly pass   the chain works end to end on real inspection output.
                        Record and stop; the next question is a different job,
                        not more of this one.
W-2 fails               do not patch the prompt. Report that the hand-built
                        report was doing work, and say what work.
stage 1 unaddressed     record where the constraint had to live. Do not re-run.
```

Three probes, three stages, no retries, `glm-5.2:cloud` over the HTTP API with
`stream: false`. Boundary self-test passes before the freeze.

## Stated limitation

One job, one purpose, three probes, two data collections plus a request fixture,
`glm-5.2`, no seed control. W tests whether uncertainty created by an inspection
processor survives into modelling strongly enough to stop an unsupported binding.
It does not test a job whose correct rule order is unconventional, and it does not
test the chain on a job the fixtures were not built for.
