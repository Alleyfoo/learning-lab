# Experiment R — Can an LLM define the node? Preregistration

**STATUS: FROZEN before any run.** No probe has been run. Expected answers,
grading and decision rules below are fixed before the model is called.

## The question

Everything downstream of a node definition is now demonstrated: a declared
definition, an unattended deterministic runtime with no LLM, and equivalence
against a hand-written ten-minute Python oracle on both **decisions and final
state** (`calendar_job`, `ff33068`). One step is still done by hand.

> Given only this node's local world — the programmatically extracted data
> structure plus a human description of the job — can an LLM produce a node
> definition that does the same job as the oracle?

If it can, the loop closes:

```text
human describes job + supplies data  ->  LLM proposes definition
                                     ->  validator + oracle grade it
                                     ->  ESTABLISHED node, LLM gone at runtime
```

## What the LLM is given, and what it is NOT

**Given** (the node's whole world — nothing else exists):

```text
1. an EXTRACTED data structure, not raw files: for each source, its collection
   name, element type, count, and up to three example values
2. the request shape: one field, `request_date`
3. the human description, verbatim:
     "Incoming requests contain a date. This reservation list contains booked
      dates. This holiday list contains dates that cannot be booked. Add a
      request unless the date is invalid, a holiday or already booked."
4. the closed vocabularies it may use: rule names, refusal names, on_accept
   values, and the required envelope keys
```

Point 4 is deliberate and is the capability framing, not a giveaway: a node's
world includes **what it is allowed to say**. Withholding the vocabulary would
measure whether the model can guess this repo's private token names, which is
not the question. The question is whether it can map a described job onto an
available vocabulary correctly — including the ORDER, which is the part carrying
real semantics.

**Not given:** the existing `calendar_job.json`, any file from `reservation/`,
any prose from this repo's design docs, the oracle, or the request sequence used
for grading.

## Grading — deterministic, and NOT string comparison

A definition may differ textually from the hand-written one and still be right.
It is graded on what it DOES:

```text
G1  VALID          the task's own validator accepts it
G2  EQUIVALENT     run through calendar_job/equivalence.py against the
                   hand-written oracle: same decisions AND same final state
                   over the frozen six-request sequence
G3  STRUCTURAL     (reported, not a pass criterion) does its rule set, rule
                   ORDER, refusal mapping and on_accept match the established
                   definition?
```

**G2 is the pass criterion.** G3 is recorded because a definition that passes G2
by a different route is interesting and should not be silently scored as
identical.

## Expected answers, frozen

```text
G1  PASS expected   the vocabularies are supplied, so an invalid definition
                    means the model could not follow a closed enum
G2  PASS expected   the job has three rules and one effect; if the model orders
                    them correctly this must hold
G3  MATCH expected  with one predicted deviation: `purpose` wording will differ,
                    and `model_id` may differ. Neither affects G1 or G2.
```

### Predicted failure modes, named before the run

```text
F1  rule ORDER wrong -- `not_holiday` or `not_reserved` placed before
    `date_well_formed`. The validator refuses this (wellformedness_not_first),
    so it would show as G1 FAIL, not as a wrong answer. This is the single most
    likely failure and the most interesting one: it is a real semantic error
    that the format catches structurally.
F2  invented refusal names (e.g. BAD_DATE) -> G1 FAIL, unknown_refusal
F3  `on_accept` omitted or invented -> G1 FAIL
F4  extra rules not in the description
F5  a rule dropped -- most likely `date_well_formed`, since the human
    description mentions "invalid" only in passing
```

## Decision rules, fixed before the run

```text
G1 and G2 PASS          the loop is demonstrated FOR THIS NODE. Record and
                        stop; do not generalise to other node types.
G1 PASS, G2 FAIL        preserve. A valid definition that does a DIFFERENT job
                        is the most informative outcome available and must not
                        be retried away.
G1 FAIL                 preserve the raw output and the validator's codes. Which
                        code fired is the finding.
any outcome             the raw model output is written verbatim to
                        results/ before grading, and never edited.
```

**No retries, no prompt-tuning after seeing a result.** If the first probe fails,
that is the recorded result; a second probe with a changed prompt is a new
experiment with its own freeze.

## Model and reliability

`glm-5.2` via ollama — the same family used by experiments 3A–3E, so the
reliability caveats there carry over unchanged:

> one run per probe, no seed control. A single sample cannot distinguish
> *always* from *once*.

Three probes are run against the SAME input to observe stability, and all three
are recorded. Agreement across three is not a reliability measurement; it is
three samples, reported as three.

## Harness self-test before any probe

The grader must be shown to be able to FAIL before it is trusted:

```text
canary_wrong_definition   a definition with the holiday rule removed must
                          grade G2 NOT_EQUIVALENT
canary_bad_order          a definition with the rules reordered must grade
                          G1 INVALID (wellformedness_not_first)
```

Both are asserted by the harness self-test, which runs with no model.

## Stated limitation

One node, one job, one model family, three samples. It asks whether an LLM can
produce THIS definition from THIS description — not whether it can define nodes
in general. Concurrency, retries and mid-write arrival remain out of scope and
are a normal engineering problem, not a modelling one.
