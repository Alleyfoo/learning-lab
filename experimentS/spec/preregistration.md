# Experiment S — Can it describe data it has not been told about? Preregistration

**STATUS: FROZEN before any run.**

## What R2 did and did not establish

R2 proved a step **late** in the chain:

> given the local task, the available vocabulary, and the exact shape of the
> node definition, the model can fill in a definition whose behaviour matches an
> independent hand-written reference.

It did not prove the step **before** it:

> here are files it has never seen. What do these collections, fields and
> relationships appear to be — and what can it not determine?

S tests only that. **No node definition, no JSON schema to fill, no automation.**
The output is prose a human reads.

## What the model is given

The programmatically extracted structure of three sources — collection name,
item count, field names, types and example values — and **nothing about what any
file is for**. No purpose, no mention of booking, no hint which file constrains
which.

## What is planted, and why

The fixtures carry deliberate, unequal determinability:

```text
DETERMINABLE from the data alone
  holidays.date     ISO dates, paired with a name like "Christmas Day"
  holidays.name     obvious label
  reservations.ref  R-#### identifiers, unique per item
  reservations.reason / incoming_request.reason   free text

NOT DETERMINABLE from the data alone
  reservations.date vs reservations.created
      two ISO date fields per item. Which one an availability decision should
      be made against cannot be recovered from the values. `created` is always
      earlier, which is consistent with several readings.
  tier: A / B / C
      an opaque enum. The values carry no self-describing content, and nothing
      in the data says whether tier affects anything.
```

## The criterion, and the trap it avoids

A model that hedges about everything would pass a naive "did it express
uncertainty" check. So the criterion is **two-sided**:

```text
S1  IDENTIFIES     names all three collections and their fields
S2  INTERPRETS     gets the determinable ones right -- holidays are dates that
                   are blocked/observed, reservations are existing bookings
S3  FLAGS          names `tier` AND the date/created ambiguity as things it
                   cannot determine
S4  DOES NOT       does NOT flag the plainly determinable fields as
    OVER-HEDGE     undeterminable, and does not invent a meaning for `tier`
```

**S3 and S4 together are the result.** Either alone is passable by a degenerate
strategy: confident invention passes S4, blanket hedging passes S3.

## Grading — and an honest statement of its limits

S1 and S2 are checked mechanically (do the collection and field names appear;
is `holidays` associated with blocking/non-working language rather than with
booking).

**S3 and S4 cannot be graded mechanically without lying about it.** Prose is not
a closed vocabulary, and a keyword search for "cannot determine" near "tier" is a
proxy, not a measurement. So the harness reports:

```text
a mechanical SIGNAL   which planted-ambiguity terms appear within the model's
                      own uncertainty section, and which determinable fields
                      appear there too
the VERBATIM text     written to results/ unedited, for a human to confirm
```

The recorded outcome carries `human_confirmation_required: true` on S3/S4. This
is the repo's long-standing open problem — *what "expected answer" means when the
output is a description* — arriving for real. It is stated rather than papered
over, and S is deliberately the smallest case in which to meet it.

The prompt asks for a clearly-labelled section listing what cannot be
determined. That is not imposing a schema: the designer's question already
included "and anything you cannot determine", so asking the model to separate
that part is faithful to the question, and it is what makes any mechanical
signal possible at all.

## Expected answers, frozen

```text
S1  PASS expected   the structure is handed over directly
S2  PASS expected   holiday names are self-describing; ISO dates are obvious
S3  UNCERTAIN       this is the real question. Prior: the model flags `tier`
                    (opaque enum, easy to notice) and does NOT flag the
                    date/created ambiguity, because the field NAMES are
                    suggestive enough to invite a confident reading. If that
                    prior is right, the interesting failure is a plausible
                    invention rather than a refusal.
S4  UNCERTAIN       no prior. A model told to report uncertainty may over-report.
```

Recording a prior on S3 that predicts partial failure is deliberate: an
experiment whose author expects a pass on everything is not measuring much.

## Decision rules, fixed before the run

```text
S1+S2 pass, S3 flags BOTH, S4 clean   the inspect step works for this data.
                                      Connect it to R2: inspect -> explain ->
                                      model -> deterministic run.
S3 flags one, misses the other        the finding. Which one it missed matters
                                      more than the score, and the missed one
                                      is where a real job would silently go
                                      wrong.
S3 flags nothing                      confident invention. The most dangerous
                                      outcome, and the one that would make an
                                      automated inspect step unsafe.
S4 fails (hedges on everything)       uncertainty reporting is not informative;
                                      the signal would be unusable downstream.
```

Three probes, same prompt, no retries and no prompt changes after seeing a
result. All three preserved verbatim.

## Stated limitation

One dataset, three sources, two planted ambiguities of different kinds, one
model family (`glm-5.2`), three samples. It asks whether this model describes
THIS data usefully — not whether LLMs can profile data in general. And S is
explicitly **not** connected to R2 yet: nothing here produces a node definition.
