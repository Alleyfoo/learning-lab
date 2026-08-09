# RUN A — Notes and Caveats

Corpus: 14 variants x 12 held-out periods = 168 evaluations.
Floor read from the committed artifact `a038a2e` and used unchanged.

## Preregistered outcomes

| Outcome | Result |
| --- | --- |
| **O1a** unwarranted execution | 0 — evidence held fresh by design in RUN A; measured properly in the expiry run (O5) |
| **O1b** warranted but wrong (system failure) | **22** — `COS_case_whitespace`, `COS_period_format` |
| **O2** false escalation on controls | **0.0833** (1 of 12 unchanged periods) |
| **O3** detectable-drift miss (above declared floor) | **0** |
| **O4** correct undecidability | **7** — `SEM_invisible` (1/1), `SEM_creep` (6/12) |
| N1 guard | passed on all 168 evaluations |

## Structural discrimination: 5/5 variants, 12/12 periods, correct level attribution

| Variant | Escalated | First failing level |
| --- | --- | --- |
| `STR_insert_column` (the D1 trap) | 12/12 | L1 |
| `STR_wide` | 12/12 | L1 |
| `STR_drop_column` | 12/12 | L1 |
| `STR_header_offset` | 12/12 | L1 |
| `STR_grain_split` | 12/12 | **L3** |

`STR_grain_split` is the one that matters: the period total is preserved **exactly**, so
every statistical check passes. It is caught only because L3 declares a uniqueness key.
Without a declared grain it would have been authorized silently — which is the failure mode
that doubles revenue.

## O1b: two genuine system failures

`COS_case_whitespace` and `COS_period_format` are authorized, and should not be. Both mutate
**values in key columns** (`ART-0001` → `  art-0001 `; `2025-07` → `07/2025`). Structure,
dtypes, row counts and totals are all unchanged, so L1–L4 see nothing. Downstream this
produces 150 phantom articles or an unjoinable period label.

**The contract has no value-level predicate for identity columns.** L2 checks dtype, null rate
and cardinality — cardinality is unchanged by a case fold. This is a real gap found by the
experiment, not a tuning artefact.

## Caveat on `SEM_creep` — the detection is confounded

`SEM_creep` escalated in 6 of 12 periods, 4 of those from the sustained test. That is **not**
evidence that the sustained test catches sub-floor creep.

The unchanged held-out periods already sit **+4.76%** above the baseline mean by chance
(baseline 36,210 vs held-out 37,935). Sustained shift ranges:

| | range | sustained alarms |
| --- | --- | --- |
| `C0_unchanged` | −0.69% … +6.26% | **0/12** |
| `SEM_creep` | −0.11% … +9.64% | 4/12 |

The injected creep is 3.37%, well below the 10.78% sustained floor. It alarms only because it
rides on top of a pre-existing baseline/hold-out offset. On its own it would not be detected.
Reporting this as "the sustained test catches creep" would be false.

It is also a finding in its own right: a baseline window that happens to sit below the
subsequent regime produces sustained alarms that look like drift and are not. This is the
false-escalation direction of the paired calibration metric (C6).

## Analysis definition refined after RUN A — disclosed

O1b was first computed as "authorized on any variant where something changed." That scored
`COS_reorder` (column order reversed, name-based access, byte-identical canonical output) as a
system failure, and would have rewarded escalating on everything — the pathological
conservatism C8 warns about.

Refined to: authorized while ground-truth `output_equivalent` is False, excluding sub-floor
semantic variants. `output_equivalent` is determined **by construction**, never by whether the
harness detects the change (operating_procedure.md 2.2).

**The floor was not touched. The corpus data was not touched.** Only the analysis predicate
changed, and both versions are recorded here.

## Not yet run

Steps 6 (sweep), 7 (AR(1)/seasonal stress), 8 (expiry/O5), 9 (results memo).
