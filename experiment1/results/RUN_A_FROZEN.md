# RUN A — FROZEN

**Tag:** `exp1-runA-final` at commit `2e89405`.

RUN A is closed. Its floor, corpus, code and results are frozen and must not be modified.
Any correction to the method produces a **new** floor artifact under a new version, certified
by a separately preregistered run. It does not edit these.

## Frozen artifacts

| Artifact | Value / path |
| --- | --- |
| Baseline history | `artifacts/baseline_history.csv`, sha256 `1f2575bebadce618be3d5553b05461f259f9ae0529d6dc53ffd9a45950366d03` |
| Detection floor (v1) | `artifacts/detection_floor.json` — 22.4367% single, 10.7782% sustained, α 0.05, power 0.80, iid, method `l4/1.1.0` |
| Floor commit (pre-drift gate) | `a038a2e` |
| Drift corpus | `artifacts/drift_corpus/` + manifest, 14 variants × 12 periods |
| RUN A results | `results/run_a_summary.json`, `run_a_detail.csv`, `run_a_notes.md` |
| Sweep + stress | `results/sweep_summary.json`, `sweep_detail.csv` |
| Expiry / O5 | `results/expiry_summary.json` |
| Result memo | `results/experiment_1_result.md` |
| Taxonomy correction | `results/o1_taxonomy_correction.md` |

## Frozen headline numbers

| Metric | Value |
| --- | --- |
| O1a unwarranted execution | 0 |
| O1b warranted-but-wrong, below capability | 7 |
| **O1c warranted-but-wrong, NOT below capability** | **22** |
| O2 false escalation on controls | 0.0833 |
| O3 above-floor miss | 0 |
| O4 correct undecidability | 7 |
| O5 expiry while all checks pass | 5 of 5 |
| N1 guard | passed 168/168 |
| Structural discrimination | 5/5 variants, 12/12 periods, 100% level attribution |
| Power at declared floor (iid) | 0.7685 vs declared 0.80 |

## Known defects carried forward, not fixed here

1. **Floor v1 is ~6% optimistic** — the MDE formula assumes an additive location shift; a
   measure redefinition is multiplicative and inflates variance. Addressed by RUN B.
2. **O1c value-level identity gap** — no predicate over identity-column *values*. Deferred to a
   scoping decision after UQ-1 has evidence.
3. **`SEM_creep` detection is confounded** by a +4.76% baseline/hold-out offset. Not a finding
   about the sustained test's power.
4. **Cosmetic self-heal was never implemented**, so that decision rule is not-tested rather than
   failed.
