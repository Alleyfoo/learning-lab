# Reservation Model — v1

A minimal calendar-reservation task, used to ask a question the definition-phase
line has only ever asked about spreadsheets:

> can the system MODEL a real data task, and then EXECUTE it deterministically?

Deliberately small. Not a security exercise, and no new mechanisms are borrowed
from the frozen authority path.

## The task

Accept a requested date only if it is **valid**, **not a holiday**, and **not
already reserved**. Otherwise refuse, naming the reason. On acceptance, append it
to the reservation list.

## The separation this exists to test

```text
MODEL        declares WHAT counts as acceptable, and in what order the
             questions are asked. Data, rules, refusal vocabulary, and what
             happens on acceptance. No control flow, no evaluation.

EXECUTOR     deterministic. Evaluates the declared rules in the declared order
             against the declared data. Contributes NO judgement of its own.
```

The test of the separation is not that both exist — it is that the executor
**refuses a model it cannot honour** rather than doing something reasonable. A
rule the executor does not implement must stop the run, exactly as an unsupported
construct does in the recipe line.

## Model shape

```json
{
  "model_version": 1,
  "model_id": "reservation_v1",
  "holidays": "fixtures/holidays.json",
  "reservations": "fixtures/reservations.json",
  "rules": [
    {"rule": "date_well_formed", "refusal": "INVALID_DATE"},
    {"rule": "not_holiday",      "refusal": "HOLIDAY"},
    {"rule": "not_reserved",     "refusal": "ALREADY_RESERVED"}
  ],
  "on_accept": "append_to_reservations"
}
```

### Rule order is DECLARED, not incidental

The `rules` list order is the precedence. A date that is both a holiday and
already reserved has two true reasons, and which one is reported must be a
property of the model rather than of the order the executor happens to evaluate
in. "Whichever check ran first" is authority by accident — the same defect
cross-sheet law 5 is named after.

### `date_well_formed` must come first

Enforced, not assumed. `not_holiday` and `not_reserved` compare a date against a
set; neither has a defined answer for a string that is not a date. A model that
orders them before well-formedness is refused rather than being silently
reordered.

## Refusal vocabulary — closed

```text
INVALID_DATE       not a well-formed calendar date (ISO 8601, YYYY-MM-DD)
HOLIDAY            falls on a declared holiday
ALREADY_RESERVED   already present in the reservation list
```

A model may not invent a refusal reason. A rule may not be declared without one.

## What a decision carries

```text
ACCEPT    the date, and the NEW reservation list
REFUSE    the decisive reason, plus every rule that was evaluated
```

The evaluated-rules trace is there so a refusal can be checked against the
declared order rather than taken on trust. It is not a degradation record and
makes no claim from the frozen authority path.

## Fixtures first

`fixtures/holidays.json` and `fixtures/reservations.json` are plain ISO date
lists. Real calendar sources, recurrence, ranges, capacity and time zones are all
absent on purpose — the question is whether the split works at all, not whether
this model is complete.
