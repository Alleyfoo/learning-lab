# Experiment R2 — Does it MODEL the node, or copy the prompt? Preregistration

**STATUS: FROZEN before any run.** No probe has been run.

## The correction R2 exists to answer

R's result was recorded as "the semantics were right 3/3". **That claim was too
strong.** The sharper statement (designer):

> The model preserved the correct semantic content and order **that were
> available in the prompt**. R cannot show that it independently derived them.

R's vocabulary listed the rules already in the required order —
`date_well_formed, not_holiday, not_reserved` — so a correct answer is equally
consistent with reasoning and with copying. R could not separate those.

R2 separates them.

## The design

Two changes from R, and only two.

### 1. The socket shape is given; the answer is not

R supplied *permitted values* without the *required shape*, and the model
reasonably inferred shape from the only example it had. R2 supplies an empty
skeleton with the real key names and blanked values:

```json
{"model_id": "...", "model_version": "...", "purpose": "...",
 "sources": {"...": {"path": "...", "collection": "..."}},
 "rules": [{"rule": "...", "refusal": "..."}],
 "on_accept": "..."}
```

The designer's sketch used `file` and `on_fail`; the real keys are `path` and
`refusal`, and the skeleton uses the real ones — a skeleton that teaches the
wrong socket teaches nothing.

### 2. The vocabulary order is PERMUTED between probes

Same job description, same skeleton. Only the order in which permitted rule
names and refusal codes are listed changes:

```text
probe A   rules: not_reserved, date_well_formed, not_holiday
          refusals: HOLIDAY, ALREADY_RESERVED, INVALID_DATE
probe B   rules: not_holiday, not_reserved, date_well_formed
          refusals: ALREADY_RESERVED, INVALID_DATE, HOLIDAY
probe C   rules: date_well_formed, not_holiday, not_reserved
          refusals: INVALID_DATE, HOLIDAY, ALREADY_RESERVED
```

Required answer, every time:

```text
date_well_formed -> INVALID_DATE
not_holiday      -> HOLIDAY
not_reserved     -> ALREADY_RESERVED
```

Rules and refusals are listed **separately and independently permuted**, so no
probe shows the pairing pre-assembled. The model must construct it.

**Probe C is the one to distrust.** Its vocabulary happens to match the required
order, so a correct answer from C alone proves nothing — it is R's condition
again. A and B are where the evidence is.

## What is measured

```text
G1  VALID        the task's own validator accepts it
G2  EQUIVALENT   run against the hand-written oracle: same decisions AND same
                 final state over the frozen six-request sequence
G3  ORDER        is the emitted rule order the REQUIRED one, or the order the
                 probe's vocabulary happened to list?
G4  PAIRING      is each rule paired with the right refusal, given that no probe
                 showed the pairing?
```

G2 remains the pass criterion. **G3 across the three probes is the discriminator
this experiment exists for.**

## Expected answers, frozen

```text
if the model MODELS the task
    A, B, C all emit date_well_formed -> not_holiday -> not_reserved
    all three G1 VALID, G2 EQUIVALENT, G4 correct
    -> the loop closes, and R's semantic result was real

if the model COPIES the prompt
    A emits not_reserved first, B emits not_holiday first
    both refused by the validator (wellformedness_not_first)
    C passes alone
    -> R's semantic result was an artifact of prompt order
```

These two predictions are **mutually exclusive on A and B**, which is what makes
the run informative either way.

### Predicted mixed outcomes, named in advance

```text
M1  order correct, pairing wrong -> understands sequence, not mapping
M2  order correct in A and B but shape still wrong -> the skeleton was not
    enough, and the interface problem is deeper than R suggested
M3  order varies BETWEEN probes without following vocabulary order -> neither
    modelling nor copying; unstable. Three samples cannot tell which.
```

## Decision rules, fixed before the run

```text
A, B, C all correct order + G2 pass   the loop is demonstrated FOR THIS NODE.
                                      Record and stop.
order tracks vocabulary order         R's semantic result was an artifact.
                                      Record it plainly; it is the more
                                      valuable finding of the two.
mixed / unstable                      preserve all three. Do not re-run to get
                                      a cleaner story.
any outcome                           raw output written verbatim before
                                      grading, never edited.
```

**No retries and no prompt changes after seeing a result.** A third experiment
needs its own freeze.

## Instrument

The floor was repaired and pinned before this freeze (`cc29502`): a malformed
proposal — `sources` as a list, as R produced — is now refused as
`malformed_sources` rather than raising. R2's instrument therefore starts from a
floor where external malformed output is an expected input class. 76 artifacts
hash-verified.

Grader: `experimentR/harness/grade_R.py`, reused unchanged, plus the cross-probe
order analysis which is new here. Its self-test passes with no model and its
canaries fire.

Model: `glm-5.2` via ollama, HTTP API with `stream: false` — the transport R had
to repair. One run per probe, no seed control.

## Stated limitation

One node, one job, one model family, three probes with three different
vocabulary orders. Three permutations of three rules is half the possible
orderings; A and B were chosen because each places a *different* wrong rule
first. If all three agree this is evidence, not proof, and it remains a single
sample per condition.
