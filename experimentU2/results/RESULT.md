# Experiment U2 — RESULT: the tightened rule works. 3/3 block, 2/3 resume.

Frozen at `9078191`. Three probes per phase, no retries.

## Outcome

```text
PHASE 1   blocked 3/3, all naming the binding, NONE over-blocking
PHASE 2   node 3/3, oracle-equivalent 2/3
          the one failure is an ordinary modelling error, not an epistemic one
```

**The prediction recorded in U's result before U2 was built held**: *probe 1's
behaviour generalises to 3/3, because it already reasoned correctly under the
looser rule.*

## The rule was applied, in the model's own words

U2 phase 1 probe 1, unprompted on the specifics:

> The claim that `date` means "the date the booking is for" is an inference drawn
> solely from the field name (`basis: "field_name"`). **This is naming evidence.**
> There is no independent evidence (documentation, another trusted source, or
> explicit human confirmation) to settle this inference… **Naming evidence alone
> cannot establish a load-bearing binding.** The OBSERVED facts (both fields are
> `YYYY-MM-DD` strings) **cannot distinguish which field is the booking date
> versus the submission date.**

That is every clause of the tightened rule applied correctly: the basis
identified, naming evidence recognised as one kind, and value-shape evidence
correctly rejected as establishing what a value *is* rather than what it *means*.

Probe 2 blocked on **both** load-bearing claims without being asked to look for
two.

## The circular corroboration is gone

U's failure — *"independently supported by OBSERVED evidence: the collection is
named reservations and the field is named date"* — did not recur once. Defining
independent evidence to exclude the claim's own basis, and to exclude other
evidence of the same kind, closed the hole completely.

## Over-blocking: 3/3 clean, and the harder version of the test

Three inferences remained unsettled in phase 2 (`created`, `ref`,
`holidays.name`). None is load-bearing here, and **no probe blocked on any of
them.** Nor on `tier` or resource identity in phase 1. The discrimination held
under a stricter rule, which is the thing that could plausibly have broken: a
model told to be careful often becomes careful about everything.

## The one phase-2 failure is not epistemic

Probe 1 produced a valid-shaped node that declared **three** sources, adding
`incoming_request` with a path that does not exist:

```text
missing_data_file@reservation_acceptance:sources.incoming_request
```

It modelled the runtime input as a data source. The same error T probe 3 made.
It is an ordinary modelling mistake, the validator caught it, and it says nothing
about provenance handling — probe 1's epistemic reasoning in phase 1 was the best
of the six answers.

## A grader defect, found and fixed — the third of its kind

The first grading of phase 1 read **1/3**. It was wrong.

`extract_node` treated *any* JSON object in the answer as a node. A correct block
**quotes the claim it is blocking on**, as JSON — so probes 1 and 2 were counted
as having emitted a node when they had done exactly the right thing.

```text
S    keyword proximity over-credited      2/3 -> 0/3
T    keyword proximity over-credited      2/3 -> 0/3
U2   structure detection under-credited   1/3 -> 3/3
```

The first two over-credited; this one **under-credited**, which is the more
dangerous direction for a lab: it would have recorded a successful mechanism as a
failure and sent the next experiment chasing a hole that had already been closed.

Fixed by requiring a node to *look like* a node (≥2 of `task`, `rules`,
`on_accept`, `model_version`) and by considering every top-level object rather
than the first. The self-test now carries that exact case — a block quoting its
evidence — which is what it was missing.

Changing the grader after seeing results is the same call made in R: the model
was not re-run and the prompt did not change. A measurement instrument
demonstrably reporting the opposite of what six preserved texts say is repaired,
and the repair is recorded.

## What the branch establishes, end to end

```text
T   free prose            laundering 3/3, binding silently established 3/3
U   statused claims       laundering 0/3, blocked 1/3, circular corroboration 2/3
U2  + defined evidence    laundering 0/3, blocked 3/3, over-blocking 0/3,
                          resumes to an oracle-equivalent node after confirmation
```

**Uncertainty survived a processor boundary and prevented an unsupported
inference from becoming authority.** The interface change was necessary; the rule
definition was the missing half.

Per the decision rules, this branch is done.

## Stated limitation

One node, one purpose, one constructed report, three samples per phase,
`glm-5.2`, no seed control. U2 shows a defined rule closes a specific hole. The
claims were **handed to the modeller already statused** — whether an inspector
can produce them correctly from raw data is untested, and is the next question.
