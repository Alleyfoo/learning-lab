# Experiment S — RESULT: MIXED, and the grader is part of the finding

Frozen at `d77f687`. Three probes, no retries. Raw output preserved verbatim.

## Mechanical signal, then the human confirmation that overturns it

```text
probe   S1 identifies   S2 signal   S3 signal (tier / date-created)   S4 signal
1       PASS            FAIL        True / False                      clean
2       PASS            PASS        True / True                       'ref' hedged
3       PASS            PASS        True / True                       clean
```

**S3 and S4 carried `human_confirmation_required` for a reason, and reading the
text reverses three of those cells.**

```text
probe 2  S3 date_vs_created: the token `created` appeared in the uncertainty
         section -- inside a sentence about how a request BECOMES a reservation.
         It also raised a real question about the pair (lead time), but NOT the
         planted one.
probe 2  S4 'ref' over-hedged: `ref` appeared in that same workflow sentence,
         not as a claim that `ref` is unknowable. NOT over-hedging.
probe 3  S3 date_vs_created: `created` appeared in a TIME GRANULARITY item
         listing every date field. Not the planted question.
probe 1  S2 FAIL: it described holidays as "a specific holiday occurring on a
         specific calendar day" -- correct, and simply not phrased in my
         keyword list. A grader artifact, not a model failure.
```

**Human-confirmed result: not one of the three raised the planted question** —
*which of `date` and `created` should an availability decision run against.*

## What they did instead, and it is the interesting part

All three **confidently resolved** it in the body: `date` is when the booking is
for, `created` is when it was submitted. That reading is almost certainly right —
and it is an inference from **field names**, not from the values, which is
precisely what the preregistration said could not be determined from the data
alone.

So the frozen prior was correct:

> the model flags `tier` and does NOT flag the date/created ambiguity, because
> the field NAMES are suggestive enough to invite a confident reading

`tier` was flagged 3/3, with sensible candidate meanings and no invention.

## What they raised that was NOT planted — and one of them matters a lot

```text
3/3  what resource is actually being booked (room? venue? equipment?)
3/3  the scope of the holidays -- national, company-wide, or one venue's closure
2/3  the request -> reservation workflow, and how `ref`/`created` get populated
1/3  time granularity: all dates are day-level, so no time-of-day rules
1/3  lead-time constraints between `created` and `date`
1/3  "we cannot determine how the `date` in reservations interacts with the
     `date` in holidays -- whether a reservation can be made on a holiday"
```

That last one (probe 3) is **the core business rule of the entire calendar job**,
identified as undeterminable from data alone by a model that was told nothing
about what the job was. It is exactly the question a human must answer, and the
model asked it rather than assuming it.

## The reading of S4

Under human confirmation, **no probe hedged on a genuinely determinable field.**
Every uncertainty item in all three was a real open question. The one mechanical
S4 flag was a false positive.

## What S establishes

```text
CAN   from structure alone, with no statement of purpose, this model names the
      collections and fields, gives plausible readings of each, and produces
      uncertainty items that are genuine rather than padding -- including,
      once, the central rule of the job.

CANNOT  it does not reliably surface an ambiguity whose field NAMES suggest a
        confident answer. The one planted case of that kind was missed 3/3.
        A downstream step that trusted the description would inherit a
        plausible, unflagged assumption.
```

## And the grader is part of the finding

The mechanical proxy was **wrong in both directions**: it credited two probes
with flagging something they had not, and accused one of hedging when it had
not, and failed one on interpretation that was correct. The preregistration
refused to call it a measurement, and that refusal was load-bearing — a run that
reported the signal as a score would have concluded 2/3 flagged both planted
ambiguities. The truth is 0/3.

**Keyword proximity is not comprehension.** For a description-shaped output,
grading currently requires a human to read it, and the honest harness design is
one that says so and preserves the text.

## Decision-rule outcome

Per the frozen rules: *"S3 flags one, misses the other → the finding. Which one
it missed matters more than the score, and the missed one is where a real job
would silently go wrong."*

That is this outcome. The missed one is a field-name-suggestive ambiguity, and
the place a real job would silently go wrong is a system built on a confident
reading of which date drives availability.

## Not done

S is deliberately **not** connected to R2. Nothing here produced a node
definition. Whether a description like these, handed to the R2 step, yields a
correct node is the next question and needs its own freeze.

## Stated limitation

One dataset, three sources, two planted ambiguities, one model family
(`glm-5.2`), three samples, one run each. No seed control.
