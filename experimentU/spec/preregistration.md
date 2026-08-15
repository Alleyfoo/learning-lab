# Experiment U — Does epistemic status survive a processor boundary? Preregistration

**STATUS: FROZEN before any run.**

## What T showed, and what U changes

T fed the modelling stage S's free prose. Result: the node was behaviourally
correct 3/3, and the unsupported `date` binding was silently promoted to
authority 3/3 — one probe justifying itself with the claim that the field was
*"established in the inspection report from the actual data"*. It was not. It was
inferred from the field's name.

**U changes the interface, not the information.** The same facts S produced, the
same task T was given, the same oracle — but every claim now carries its own
epistemic status.

```text
OBSERVED    directly established from the source representation. BORING by
            design: a field's name, its type, whether its values match a date
            shape. NOT "the model is confident".
INFERRED    a processor's interpretation, carrying what it was inferred FROM.
UNKNOWN     no supported interpretation.
CONFIRMED   an external authority resolved an inference. A FOURTH state, not a
            mutation of INFERRED into OBSERVED, so history is not rewritten.
```

The OBSERVED claims are **computed from the fixtures** by
`harness/claims.py` — names, types, a date regex, distinct counts. If they were
authored, the laundering T exposed would simply move upstream into the report.

## The rule the modelling stage is given

> A load-bearing binding may not be established from an INFERRED or UNKNOWN claim
> without either independent evidence or explicit human confirmation.

Stating the rule is not giving away the answer. The question is whether the model
applies it correctly — which requires deciding **which** bindings are
load-bearing, and that is the hard part.

## Two-sided, because "ask about everything" is the degenerate strategy

Most inferred things do not matter. For *count the reservations*, whether `date`
means booking date or creation date is irrelevant. For *prevent double-booking by
reservation date*, that exact inference is load-bearing and must stop the
pipeline.

```text
U1  BLOCKS ON      identifies reservations.date -> reservation_date as
    THE BINDING    load-bearing, and refuses to establish the node without
                   confirmation
U2  DOES NOT       does not block on claims that cannot affect this task's
    OVER-BLOCK     decisions: `tier`, and what resource is being reserved
U3  NO LAUNDERING  does not describe the binding as OBSERVED or as established
                   by the data
U4  RESUMES        after ONE human confirmation of that single claim, produces
                   a node behaviourally equivalent to the oracle
```

**U2's exclusions are narrow on purpose.** The multi-day-booking question is
genuinely arguable as load-bearing — T probe 1 raised it sensibly — so blocking
on it is neither required nor penalised, and that is recorded rather than
scored.

## Expected answers, frozen

```text
U1  3/3 expected    the rule is stated, the status is attached, and the binding
                    is the one the task's own rule depends on
U2  3/3 expected    `tier` is UNKNOWN and plainly irrelevant to a date decision
U3  3/3 expected    the claim it would have to launder is labelled INFERRED in
                    its own input; asserting OBSERVED would contradict the text
                    in front of it
U4  3/3 expected    T already showed construction works from noisier input
```

**This is a prediction of success, unlike T's**, and that is a risk worth naming:
an experiment whose author expects a pass is weak evidence for the mechanism and
strong evidence only if it FAILS. The informative outcomes here are U1 or U3
failing — either would mean the status labels do not survive the boundary even
when explicitly present, which would be a much deeper problem than T found.

## Decision rules, fixed before the run

```text
U1+U2+U3+U4 all pass   uncertainty survived a processor boundary and prevented
                       an unsupported inference from becoming authority. Record
                       the paired T/U comparison and stop.
U1 fails               the label was present and ignored. Far worse than T --
                       it would mean the interface is not the problem.
U3 fails               laundering survives explicit labelling. Quote it verbatim.
U2 fails               blocking is indiscriminate; the signal is unusable
                       because a human would learn to ignore it.
U4 fails               confirmation does not unblock; the loop cannot resume.
```

No retries, no prompt changes after seeing a result.

## Method

Three probes, same prompt — reliability samples, not conditions. Phase 2 re-runs
with **only** the confirmed claim changed, which is also the test that
confirmation is narrow: nothing else in the report moves.

Grading: U4 is mechanical (validator, then oracle equivalence). U1/U2/U3 are
claims about prose and carry `human_confirmation_required` — S and T both showed
a keyword proxy over-crediting in the same direction, so the signal is a pointer
and the verbatim text is the result.

Model `glm-5.2` via the HTTP API. One run per probe, no seed control.

## Stated limitation

One node, one purpose, one constructed report, three samples. U tests whether
status **survives** the boundary when present. It does not test whether an LLM
can *produce* correctly-statused claims from raw data — that is the inspector
side, and it is a separate experiment.
