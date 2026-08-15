# Experiment W — RESULT: the chain runs end to end on real inspection output

Frozen at `4db27bd`. Three probes, three stages each, no retries.

```text
probe    W1     W2     W3     W4     W5     W6
probe1   pass   pass   pass   pass   pass   pass
probe2   pass   pass   pass   pass   pass   pass
probe3   pass   pass   pass   pass   pass   pass
```

## The fix worked, and it needed the schema as well as the instruction

```text
V   unknowns machine-addressable    0 / 23
W   unknowns machine-addressable    8 / 8
```

Every claim across all three probes carried a referent; the boundary rejected
nothing. V's own floating unknown — quoted verbatim from `V1_probe1_raw.txt` —
is refused by W's boundary, and the `tier` pair now shares one address:

```json
{"claim": {"source": "reservations", "field": "tier",
           "meaning": "a service or priority tier"},
 "status": "INFERRED", "basis": ["field_name"]}
{"claim": {"source": "reservations", "field": "tier",
           "question": "What does a tier actually represent here?"},
 "status": "UNKNOWN"}
```

The candidate interpretation and its uncertainty are now two claims about one
subject, which is what the model was already trying to say in V.

## The modeller blocked on the inspector's own report — and blocked harder

This is the result W existed to get. U2's report was hand-built, so its
load-bearing claims were known to the experimenter before the run. Here the
modeller received whatever the inspector produced, and all three blocked:

```json
{"source": "reservations", "field": "date",
 "binding": "The field holds the date the reservation is for",
 "claim_status": "INFERRED",
 "question": "Does the 'date' field in 'reservations' represent the date the
              reservation is for?"}
```

Each probe blocked on **three** bindings, not one. U2's hand-built path asked
about `reservations.date` and the meaning of `holidays`. Every W probe added
`holidays.date` and `incoming_request.requested_date` — two date bindings the
experimenter had never thought to include. The real report produced a **more**
careful modeller than the constructed one, which is the opposite of the failure
the preregistration named as most interesting.

And no probe blocked on `tier`, `ref`, `created`, `name` or `reason`. More
unknowns did not mean more blocking; discrimination survived contact with a
report nobody curated.

## Probe 3 exercised the part V could not do

V's `confirm` could only promote `INFERRED`. Probe 3 blocked on
`("holidays", None)` — a collection-level **UNKNOWN**, the whole-collection
question `field: null` exists for:

```text
probe1   promoted 3, was ['INFERRED']
probe2   promoted 3, was ['INFERRED']
probe3   promoted 3, was ['INFERRED', 'UNKNOWN']
```

A human answering *"what does this collection mean?"* settled it, the claim
became `CONFIRMED` and remembered it was `UNKNOWN`, and the modeller resumed.
That path was written from V's failure and canaried; probe 3 reached it with no
prompting toward it.

## Confirmation stayed exact, and all three nodes were oracle-equivalent

```text
3 claims promoted, 3 claims changed, observations byte-identical    3/3
bound_field: date                                                  3/3
rules: date_well_formed, not_holiday, not_reserved                 3/3
G1 valid, G2 behaviourally equivalent to the hand-written oracle    3/3
```

W-6 is 3/3 where U2 was 2/3 — U2's miss was probe 1 declaring
`incoming_request` as a data source with a path that does not exist. Here every
probe raised `incoming_request.requested_date` as a *question* in stage 2 rather
than modelling it as a source in stage 3. Suggestive, but three probes on one
job; not a claim that the chain fixed that error.

## What this establishes

> An uncertainty created by the inspection processor survived into modelling
> strongly enough to stop an unsupported binding from becoming authority, and a
> human answer at exactly that address released it.

```text
see something            PROGRAM emits 13 OBSERVED claims from the fixtures
describe / infer it      LLM emits INFERRED with a closed-vocabulary basis
preserve what is unknown UNKNOWN with a referent, 8/8 addressable
task depends on it       three date bindings are load-bearing
modeller stops           3/3 block, by referent, in machine-readable form
human supplies truth     confirmation at exactly the named referents
continue                 3/3 nodes, valid, oracle-equivalent
```

## Stated limitation

One job, one purpose, three probes, `glm-5.2`, no seed control. The blocks were
all about date bindings, which is the case the fixtures were built around — a job
whose load-bearing claim is not a date, or whose correct rule order is
unconventional, is untested. W shows the chain carries status end to end on
inspection output it did not curate; it does not show the chain is robust to a
job it was not designed for.

`incoming_request.requested_date` being treated as load-bearing is arguably
correct and arguably a category error — it is the runtime input, not a modelled
source. W does not settle which, and the graded checks deliberately do not score
it either way.
