# Experiment U — RESULT: the laundering stopped; a subtler failure replaced it

Frozen at `6943db8`. Three probes per phase, no retries, raw preserved.

## Headline

```text
U1  blocks on the binding      1/3
U2  does not over-block        3/3
U3  no laundering              3/3   <- T's failure did NOT recur
U4  resumes after confirmation  1/3 clean, 1/3 blocked again (correctly),
                                1/3 invalid
```

**The core question is answered yes: epistemic status survived the boundary.**
Not one probe claimed the binding was established by the data. T probe 3's
provenance laundering — *"established in the inspection report from the actual
data"* — did not recur in any form. The mechanical `laundering=['observed']` flag
was a **false positive** in all three: the word appears because the probes are
reasoning *about* the status vocabulary.

## Probe 1 did exactly the thing the architecture is for

```text
CANNOT ESTABLISH
Binding: reservations.date is the field that holds the date a reservation is
  booked for
Claim it would rest on: source reservations, field date, meaning "the date the
  booking is for", basis field_name
Status: INFERRED
Why load-bearing: the not_reserved rule must compare requested_date against the
  correct field. The source contains TWO date-shaped fields — date and created —
  and without the inferred meaning there is no OBSERVED evidence distinguishing
  which is the booked date. Picking the wrong one would silently break the check.
Question: does `date` hold the date the booking is for, rather than `created`?
```

That is the whole mechanism working: it located the binding, traced it to a
claim, read the claim's status, judged load-bearing-ness, and stopped.

## The new failure: circular corroboration

Probes 2 and 3 did not block. Neither laundered. They invoked the escape hatch in
the rule as written — *"without either independent evidence or explicit human
confirmation"* — and supplied their own reading of *independent evidence*:

> rests on an INFERRED claim … but independently supported by OBSERVED evidence:
> the collection is named "reservations" and the field is named "date"

**The field name is exactly what the claim says it was inferred FROM**
(`basis: field_name`). The basis of the inference was re-used as independent
corroboration of the inference. That is circular, and it lets any
name-derived inference bootstrap itself into support.

Probe 3 went further and cited the human purpose — *"the job says 'already
reserved'"* — as independent evidence. More defensible, and still does not
establish **which of two date fields** is the reservation date.

**This is a defect in the rule I wrote, not only in the model's reading.**
"Independent evidence" was left undefined, so the model defined it. A usable
version has to exclude the claim's own basis:

```text
evidence is independent only if it does not appear in the claim's `basis`
```

## U2: the load-bearing discrimination works, 3/3

Nobody blocked on `tier` or on what resource is being reserved. Probe 2 stated it
explicitly: the UNKNOWN claims *"are not load-bearing: the job checks holiday
status and reservation status independently, does not identify a resource, and
treats each date as a single value."* This was the degenerate strategy the
two-sided design existed to catch, and it did not occur.

## Phase 2, and a flaw in my own experiment

```text
probe 1   blocked AGAIN -- on `holidays` meaning, still INFERRED
probe 2   node valid, oracle EQUIVALENT
probe 3   node INVALID: invented a third source `incoming_request` pointing at a
          file that does not exist (missing_data_file)
```

Probe 1's second block is **correct behaviour, and it caught a mistake in the
experiment.** The report contains *two* load-bearing inferred claims —
`reservations.date`'s meaning and the `holidays` collection's meaning — and I
confirmed only one. Probe 1 applied the rule consistently and stopped at the
next unsupported one. Probes 2 and 3 did not, because they had already accepted
name-evidence as sufficient in phase 1.

Scored as U4 1/3, but the honest reading is that probe 1 was the only one being
consistent, and my confirmation step was incomplete.

Probe 3's invalid node is a separate, ordinary error: it modelled the incoming
request as a data source. The validator caught it.

## What U establishes

```text
YES   attaching status to each claim STOPS provenance laundering. T's exact
      failure did not recur once.
YES   load-bearing discrimination works: no probe blocked on irrelevant unknowns.
NO    it does not by itself stop an unsupported binding being established. Two of
      three talked themselves past it via circular corroboration.
```

The interface change was necessary and is not sufficient. The missing piece is a
definition of independent evidence that excludes the claim's own basis — which is
cheap, checkable, and now motivated by an observed failure rather than by
anticipation.

## Next, and it is small

Re-run U with the rule tightened to exclude the claim's basis, and with **both**
load-bearing claims confirmed in phase 2. That is a different prompt, so it is a
new freeze. Prediction to record now, before it is run: probe 1's behaviour
generalises to 3/3, because probe 1 already reasoned correctly under the looser
rule.

## Stated limitation

One node, one purpose, one constructed report, three samples per phase, one model
family (`glm-5.2`), no seed control. U1–U3 are a human reading of six texts,
preserved verbatim so the reading can be disputed.
