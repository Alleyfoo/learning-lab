# Experiment 1 — Drift Discrimination Harness

**No agents. No LLM. No schema learning.**
Build the instrument first, then try to prove the instrument lies about what it can see.

Protocol: [../experiment_001_drift_discrimination.md](../experiment_001_drift_discrimination.md).
Integrity rules: [../operating_procedure.md](../operating_procedure.md).

---

## Commit gate

The ordering **is** the integrity mechanism. It is verifiable from `git log` by anyone.

```text
1. baseline + frozen generator/seeds          <- no floor, no drift corpus
2. warrant/evidence engine + floor calculation
3. PRE-DRIFT detection-floor artifact         <- HARD GATE, must be on the remote
--------------------------------------------------  only now:
4. semantic drift corpus + sweep
5. runs, stress, expiry, results
```

> If a drift variant exists in the repository before commit 3 is on the remote, **the run is
> void and restarts.**

## Status

| Step | State |
| --- | --- |
| 1. Frozen baseline history | **done** `0a26063` — [spec](spec/baseline_spec.md) |
| 2. Warrant/evidence structures + L4 | **done** `52904d9` |
| 3. Detection-floor artifact (pre-drift) | **done** `a038a2e` — **gate closed** |
| 4–9. Corpus, runs, stress, expiry, results | not started — gate is now open |

### Declared capability (committed `a038a2e`, before any drift existed)

| | |
| --- | --- |
| single-period floor | **22.44%** of period total |
| sustained (k=6) floor | **10.78%** |
| α / power / assumption | 0.05 / 0.80 / iid |
| method | `l4/1.1.0` |

Preregistered variant magnitudes follow from this: **S-invisible ≈ 3.37%**
(0.15× floor — which lands almost exactly on the generator's natural 3.09% freight share),
**S-obvious ≈ 56%** (2.5× floor).

### Findings already on record, pre-drift

1. **Method correction before preregistration.** `l4/1.0.0` used a normal reference with an sd
   estimated from 12 periods; validation on data satisfying the model exactly gave a null alarm
   rate of 0.076 against a declared α of 0.05. The contract would have misstated its own Type I
   rate. `l4/1.1.0` uses the t reference and a noncentral-t power solve — empirical power 0.800
   (k=1) and 0.802 (k=6), null alarm 0.052.
2. **The single-period floor is large.** At a realised baseline CV of 7.0%, one incoming period
   cannot resolve anything below a 22% shift at 80% power. This is structural to single-observation
   testing, not a tuning artefact, and it is why the sustained test was declared up front.
3. **One false escalation in 12 unchanged periods** (a 16.19% period, p≈0.048). A genuine Type I
   error, and the first O2 datapoint.

## Layout

```text
experiment1/
  spec/        frozen specifications
  generator/   baseline (step 1); drift corpus (step 5, after the gate)
  warrant/     warrant + evidence structures, L4 statistics, decision path
  artifacts/   generated data, manifests, the committed detection floor
  results/     run outputs and the results memo
```

## Standing constraint on the warrant layer

It must never emit "semantically unchanged." The strongest statement it is permitted to make is
*"no evidence of change, at detection floor X, declared with α and power."*
