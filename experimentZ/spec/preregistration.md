# Experiment Z — can an established worker notice its world changed and evolve?

**STATUS: FROZEN before any run.**

## The one missing stage

```text
DISCOVER    modeller/pipeline.py                          done
DEFINE      modeller/pipeline.py                          done
ESTABLISH   worker/worker.py                              done
RUN         worker.run -- no LLM, no human, no approval    done
DETECT      the validator already refuses a broken world  done
INVESTIGATE                                               THIS
```

Z uses the timesheet job that already worked, on structured data. No invoices,
no PDF, no failure-rate monitoring — those are separate problems and mixing them
in would make a failure here unattributable.

## Three changed worlds, at the SAME declared paths

`timesheet-cost v1` joins `timesheets.staff_ref` to `staff.staff_id`. Only the
content of `staff.json` differs between conditions.

```text
A   staff_id -> employee_id
    timesheets.staff_ref -> staff.employee_id   4/4, unique   SOLE candidate
    expected: propose v2, no human

B   staff_id -> employee_id AND staff_code, both carrying the old values
    both 4/4, both unique                                      TWO candidates
    expected: cannot establish -> one precise question

C   the identifier is gone; nothing matches
    no candidate at all                                        NONE
    expected: cannot repair -> ask / quarantine
```

Verified mechanically before the run: the observer reports one candidate in A,
two in B, none in C.

## Why A is a real test and not a naming trick

`employee_id` *looks* like an identifier. That is exactly the provenance
laundering Experiment T exhibited and U2 closed, and it must not be what settles
it. What settles A is that the values still line up 4/4 with unique right-side
keys — the same measurement that established the binding originally, reused for
the repair. **A repair may not rest on weaker evidence than an original
binding.**

The investigator's `check_replacement` gate is canaried against a proposal that
names a real field (`name`) which the measurements do not support.

## What the investigator may return

Replacements, never a model. `worker.apply_replacements` renames a field
everywhere the model declares it and nowhere else, so a proposal cannot alter a
policy or drop a column on the way past.

## Checks

```text
Z-1  detects        v1 refuses on all three worlds and emits a packet
Z-2  packet honest  names what vanished and what appeared, carries the
                    measurements, interprets nothing
Z-3  decision       A proposes; B and C block
Z-4  gate holds     no replacement the measurements do not support is applied,
                    whatever the investigator returned
Z-5  v2 correct     A's v2 executes on the changed world to v1's exact numbers
Z-6  history        v2 carries none of v1's runs, and v1's record is unchanged
```

Z-5 is graded by execution against the numbers v1 produced on the original
world: `318.750, 1520.00, 633.9375, 1615.00`.

## Expected results

```text
Z-1  3/3    deterministic
Z-2  3/3    deterministic
Z-3  A propose 3/3, B block 3/3, C block 3/3
Z-4  3/3    the gate is program-side, so a failure means a defect in it
Z-5  3/3
Z-6  3/3    deterministic
```

## What would be informative failure

```text
B proposes             the investigator picked one of two equally supported
                       candidates. The gate would catch it, but a model that
                       tries is a model that would try where no gate exists.
                       THE most valuable failure available here.
C proposes anything    repairing from nothing at all
A blocks               the mechanism is safe and useless -- every schema change
                       becomes a human ticket, which is the whole thing this is
                       supposed to avoid
a proposal outside the join   e.g. quietly renaming an output column too. The
                       replacement shape is narrow specifically so this is
                       visible rather than absorbed
```

## Decision rules

```text
A proposes, B and C block, v2 correct   INVESTIGATE works on structured data.
                                        Record and STOP. Input adapters and
                                        failure-rate monitoring are separate.
B or C proposes                         report it; the gate held but the
                                        investigator did not, and say which.
A blocks                                report plainly -- the lifecycle does not
                                        close and the reason is the finding.
```

Three probes per condition, no retries, `glm-5.2:cloud` over the HTTP API with
`stream: false`. `worker.py` and `investigate.py` self-tests both pass before
the freeze.

## Stated limitation

One worker, one job, three probes per condition, one kind of change (a renamed
join target), `glm-5.2`, no seed control. Z does not test a changed *value*
convention, a split or merged field, a new required column, or a change that
breaks something other than the join. It does not test the statistical signal —
"normally 0.2% fail, today 17% did" — which needs baselines and windows and is
deliberately excluded. And v1→v2 here is one hop; nothing establishes that a
worker stays coherent across many versions.
