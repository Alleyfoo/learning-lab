# Experiment Z — RESULT: the lifecycle closes. 9/9.

Frozen at `23d89aa`. Three worlds, three probes each, no retries.

```text
cond  detect  decision      gate      v2 = oracle   v1 history
A     3/3     propose 3/3   passed    3/3           intact 3/3
B     3/3     block   3/3   n/a       -             intact
C     3/3     block   3/3   n/a       -             intact
```

## The full lifecycle ran

```text
v1 established, 4 healthy runs      318.750  1520.00  633.9375  1615.00
reality changes                     staff_id renamed
run 5 fails the contract            field_not_in_source@...:lookup.match_right
deterministic exception packet      no LLM involved
investigator wakes                  reads only the packet
evidence sufficient (A)             proposes one replacement
v2 established                      SAME numbers on the changed world
```

The worker refused rather than degrading, in all three worlds, with no
investigator involved. DETECT was already free: the enrichment validator reports
`field_not_in_source` on `lookup.match_right`, so a worker whose join target
vanished has always stopped.

## A: proposed the repair, and only the repair

```json
{"REPLACEMENTS": [{"source": "staff", "from": "staff_id", "to": "employee_id"}]}
```

All three probes, identical, no prose. v2 executes on the changed world to v1's
exact numbers — `318.750, 1520.00, 633.9375, 1615.00` — and `outputs` is
byte-identical to v1's. Nothing was renamed, dropped or re-policied on the way
past, which is what the narrow replacement shape exists to guarantee.

## B: refused, and said exactly why

```json
{"source": "staff", "field": "staff_id",
 "binding": "join key matching timesheets.staff_ref",
 "question": "Both staff.employee_id and staff.staff_code are mechanically
              sufficient join keys against timesheets.staff_ref (4/4 coverage,
              unique right keys). Which one is the correct replacement for
              staff_id?"}
```

The question quotes the measurement. Not *"I'm not sure"* — *"these two are
equally supported and the measurement cannot separate them."*

## C: refused with nothing to repair from, and asked the right thing

No candidate relationship exists at all: `staff.record` holds `R1, R2, R3`,
which match `timesheets.staff_ref` nowhere. All three probes asked whether
`record` is the identifier that used to be `staff_id` — a human question, not a
guess. None proposed anything.

## Versions did not reach backwards

```text
v1   version 1, 5 runs (4 successes + the exception)   unchanged after promotion
v2   version 2, supersedes 1, 0 runs
```

`promote()` starts a fresh record. The 4 successful runs stay v1's, which is the
rule `scripts/agent_binding.py` fixed for agent definitions — adopting now
certifies nothing about a past run.

## The honest gap: the gate never fired on a real proposal

`check_replacement` refuses any repair the measurements do not support. It was
exercised **only by handcrafted canary**:

```text
B with a proposal            refused for ambiguity        canary only
C with a proposal            refused, nothing to repair   canary only
A proposing `name`           refused, not the candidate   canary only
```

No probe ever produced a proposal the gate had to stop, because B and C blocked
before reaching it and A's three proposals were correct. So Z shows the
investigator behaved *and* that the gate is sound in isolation; it does not show
the gate catching a model that tried. Same shape as Experiment V's headline, and
reported the same way rather than merged into the 9/9.

## What Z establishes

Naming is not what settled A. `employee_id` looks like an identifier, and that
resemblance is exactly the laundering T exhibited and U2 closed. What settled it
was that the values still line up 4/4 with unique right-side keys — **the same
measurement that established the binding originally, reused for the repair.** A
repair rests on no weaker evidence than an original binding.

```text
DISCOVER    modeller           done
DEFINE      modeller           done
ESTABLISH   worker             done
RUN         worker, no LLM     done
DETECT      validator          done
INVESTIGATE                    done -- 9/9 on structured data
```

## Stated limitation

One worker, one job, three probes per condition, `glm-5.2`, no seed control, and
**one kind of change**: a renamed join target. Untested — a changed value
convention, a split or merged field, a new required column, a change that breaks
something other than the join, and any second hop (v2 -> v3). The statistical
signal is deliberately absent: *"normally 0.2% fail, today 17% did"* needs
baselines and windows and is a different mechanism.

Input adapters are also untouched. Z runs on JSON collections; whether the same
lifecycle holds when the input is a PDF or a spreadsheet is a separate and much
larger problem, and nothing here bears on it.
