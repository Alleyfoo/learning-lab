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
| 1. Frozen baseline history | **done** — [spec](spec/baseline_spec.md) |
| 2. Warrant/evidence structures + L4 | pending |
| 3. Detection-floor artifact (pre-drift) | pending |
| 4–9. Corpus, runs, stress, expiry, results | not started |

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
