# Experiment Y — selective autonomy: proceed when the evidence settles it

**STATUS: FROZEN before any run.**

## The question has flipped

W and X established that the chain **stops** when a load-bearing fact is
unsupported. A system that only ever stops is not useful. Y asks the other half:

> Does authority proceed when the declared local evidence is sufficient, and stop
> only when it is not?

## Three conditions, one job, one rule

```text
A   orders.item -> products.sku   3/3 unique     products.code  2/3 unique
    expected: PROCEED on sku, NO human confirmation

B   orders.item -> products.sku   2/3 unique     products.code  3/3 unique
    expected: PROCEED on code, NO human confirmation

C   orders.item -> products.sku   3/3 unique     products.code  3/3 unique
    expected: BLOCK and ask which relationship is intended
```

A and B are **mirrors**, which is the point: the field name cannot be the answer.
The same model must move its binding when the evidence moves. A system that
always picks `sku` passes A and fails B, and one that always blocks passes C and
fails both others. Only correct discrimination passes all three.

Verified mechanically before the run: the sufficiency rule applied to the
program's own measurements yields `['sku'] -> PROCEED`, `['code'] -> PROCEED`,
`['code','sku'] -> BLOCK`.

## The sufficiency rule is preregistered, not improvised

> A candidate relationship is MECHANICALLY SUFFICIENT when it is the SOLE
> candidate for that left field having BOTH complete left coverage AND unique
> right-side keys. A mechanically sufficient candidate IS established, by
> OBSERVED evidence — use it and do not ask a human to confirm it. If two or more
> are sufficient, or none is, block.

This is not the model deciding what counts as enough evidence on the fly. The
policy says so in advance; the model applies it to measurements the program made.

## The instrument was repaired FIRST, separately

X found a real observer defect: `"19.99"` was characterised and `"3"` was not, so
one operand of a declared multiplication was described and the other was not.
That is fixed and frozen on its own at `eb3a036` (`inspector/observe.py`), with
its own self-test, **before** this experiment — a repaired instrument is not
reported alongside the results it enables.

The observer now also emits `candidate_relationship` measurements. It still may
not emit a join, a meaning, or an intention; that line is canaried.

## Why C is the condition that matters

```text
A   wrong key (code)  refuses a row      the mistake is detectable at runtime
B   wrong key (sku)   refuses a row      the mistake is detectable at runtime
C   wrong key (code)  runs CLEAN         3 rows, 0 refusals, wrong money
```

Incomplete coverage is self-announcing. In C both keys cover everything, so a
wrong choice is silent and blocking is the only protection. That is also why
complete coverage is the right discriminator rather than an arbitrary one.

## Checks

```text
Y-1  addressed        every accepted claim has a machine-addressable referent
Y-2  decision         A and B proceed; C blocks
Y-3  correct output   the produced model EXECUTES to that condition's oracle
Y-4  no needless ask  A and B do not request confirmation of the join binding
Y-5  C resumes        after one human answer, C executes to its oracle
```

Y-3 is graded by execution, as in X. Naming the right key is not the test.

## Expected results

```text
Y-1  9/9
Y-2  A 3/3 proceed, B 3/3 proceed, C 3/3 block
Y-3  9/9
Y-4  6/6
Y-5  3/3
```

## What would be informative failure

```text
B blocks or picks sku      the binding is following the field NAME, not the
                           evidence. The single most valuable failure available:
                           it would mean A's success was a naming coincidence and
                           X's block may have been too
A or B asks anyway         the system is merely cautious, not selective. It
                           would stop on every real job and be switched off
C proceeds                 the sufficiency rule was read as "pick the best
                           candidate" rather than "the sole sufficient one"
proceeds with wrong output the rule was applied to the wrong measurement
```

## Decision rules

```text
all three discriminate     selective autonomy is demonstrated. STOP the
                           provenance branch here; the property is the useful
                           one and further date/join variants add little.
B fails while A passes     report plainly that the binding tracked the name.
                           A and X would both need re-reading.
A or B over-asks           report as over-blocking; the mechanism is unusable in
                           practice even though it is safe.
```

Three probes per condition, no retries, `glm-5.2:cloud` over the HTTP API with
`stream: false`. Observer self-test passes and is frozen separately.

## Stated limitation

One job, three conditions, three probes each, three rows, two candidate keys,
`glm-5.2`, no seed control. The sufficiency rule is deliberately crude — sole
candidate with complete coverage and unique keys — and real data will present
cases it does not settle (two partial candidates, a unique key with 99%
coverage). Y tests whether a **stated** policy is applied to **measured** facts,
not whether this particular policy is the right one for production.

A job whose correct rule ORDER is unconventional remains untested and is still
the sharpest open limit on R2.
