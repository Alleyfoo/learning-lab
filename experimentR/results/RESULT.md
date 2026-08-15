# Experiment R — RESULT: G1_FAIL_3_OF_3, preserved

Frozen at `78fe651`. Probes run after the freeze, graded by the criteria fixed in
it. **No retries and no prompt changes were made after seeing a result**, per the
preregistration's decision rules.

## Outcome

```text
probe 1   G1 INVALID  unparseable_by_floor          G2 not run   PASSED False
probe 2   G1 INVALID  unparseable_by_floor          G2 not run   PASSED False
probe 3   G1 INVALID  unknown_rule, unknown_on_accept  G2 not run  PASSED False
```

Pass criterion was G2 (equivalent to the hand-written oracle). No definition
reached it, because none was valid.

## The failure is uniform, and it is NOT one of the predicted modes

Every probe got the **semantics right** and the **encoding wrong**, in the same
three ways:

```text
CORRECT in 3/3     the three rules, IN THE RIGHT ORDER
                   date_well_formed -> not_holiday -> not_reserved
CORRECT in 3/3     each rule's refusal: INVALID_DATE / HOLIDAY / ALREADY_RESERVED
CORRECT in 3/3     both sources, both collections, a sensible purpose

WRONG in 3/3       rules[].name  instead of  rules[].rule
WRONG in 3/3       on_accept as a LIST  instead of a string
WRONG in 2/3       sources as a LIST  instead of a map keyed by source name
```

**F1 did not occur.** The predicted most-likely failure was rule ORDER — putting
`not_holiday` before `date_well_formed`. All three probes ordered the rules
correctly. The thing the format was built to catch structurally is the thing the
model did not get wrong.

## Diagnosis: the prompt invited the error

The vocabulary was supplied to the model as JSON:

```json
"rules": ["date_well_formed", "not_holiday", "not_reserved"],
"on_accept": ["append_to_reservations"],
"source_spec": {"path": "<file path>", "collection": "<key in that file>"}
```

The model **echoed the shape of the vocabulary listing** rather than the shape of
a definition. `rules` was shown as a list of names, so it produced a list of
`{name, refusal}`. `on_accept` was shown as a list of allowed values, so it
produced a list. `source_spec` was shown as a single spec with no indication that
sources are keyed by name, so two probes produced an array of specs.

That is at least as much the prompt's fault as the model's. The preregistration
justified supplying the vocabulary — a node's world includes what it may say —
but it supplied the *permitted values* without the *required shape*, and the
model reasonably inferred the shape from the only example it had.

## What this experiment can and cannot claim

```text
CAN     the semantic mapping looks reachable: from a plain description and a
        data structure, this model chose the correct rules, in the correct
        order, with the correct refusals, three times out of three.

CANNOT  that the loop closes. Not one definition was runnable, so G2 -- the
        only criterion that compares against the oracle -- was never exercised
        on a model-produced artifact.

CANNOT  separate "can it choose the rules" from "can it emit our JSON shape".
        The probe conflated them, and the prompt biased the second.
```

## A floor defect this exposed

`task_model.parse()` assumes `sources` is a map and raises `AttributeError` on a
list, **before any validator runs**. A malformed proposal from outside this repo
therefore crashes rather than being refused with a problem code.

Recorded, not fixed: the floor is deliberately unchanged, and fixing it mid-run
would have altered the instrument during the experiment. The grader catches it
and reports `unparseable_by_floor`.

Worth noting what the right fix is not: this is a robustness gap, not a missing
abstraction. `parse()` should produce a `Problem`, not an exception.

## Probes 1–3 (the first capture) — NON-EVIDENTIAL, preserved

The first three probes used `ollama run < prompt.txt`. That CLI re-renders lines
at wrap boundaries and a shell redirect captures both renders, so the saved text
contains duplicated fragments mid-JSON:

```text
"purpose": "...unless the date is malfo
malformed, a holiday..."
```

They measured the recording, not the model. `probe{1,2,3}_raw.txt` are kept.
The re-run used the HTTP API with `stream: false` and a **byte-identical prompt**
— repairing an instrument that never produced a legible result, which is not the
retry the preregistration forbids.

## What R2 would need — proposed, NOT run

A second experiment, with its own freeze, that isolates the variable this one
conflated:

```text
give the model an empty definition SKELETON -- the exact shape with values
blanked -- instead of a vocabulary listing, and grade the same way
```

If the semantics survive that change, the loop closes and R's diagnosis was
right. If they do not, the semantic result above was an artifact of a prompt that
happened to list the rules in the correct order — which is the alternative
explanation R cannot currently rule out, and R2 should be designed to.

## Stated limitation

One node, one job, one model family (`glm-5.2`), three samples, one run each. No
seed control. Three samples agreeing is three samples, not a reliability
measurement.
