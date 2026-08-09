# Experiment 1 — Baseline Specification (Step 1, frozen)

**Committed before:** the warrant engine, the detection floor, and any drift variant.
If a drift corpus exists in the repository before the detection-floor commit, **that run is
void and must be restarted** ([B6.2](../workorder_amendment_002.md),
[operating_procedure.md](../operating_procedure.md)).

---

## What this is

A synthetic monthly sales history from a known distribution with **no drift of any kind**.
It is the calibration input for the instrument, not a model of any real provider.

| Property | Value |
| --- | --- |
| Generator | [`generator/baseline.py`](../generator/baseline.py) |
| Seed | `20260809` (frozen) |
| Periods | 24 monthly (`2024-01` … `2025-12`) |
| Articles | 150 |
| Rows | 3,024 |
| Grain | one row per `(article_sku, report_period)` |
| Measure | `amount` |
| Declared world model | **iid across periods** — no trend, no seasonality, no autocorrelation |

## Realised baseline statistics

Measured from the generated data, not assumed:

| Statistic | Value |
| --- | --- |
| `period_total` mean | ≈ 37,072 |
| `period_total` sd | ≈ 2,410 |
| **`period_total` CV** | **≈ 0.0650** |
| Rows per period | 126 |
| Freight as share of `amount` | ≈ 0.0309 |

The CV is the property that determines how strong or weak the L4 instrument is. It is
**measured, not declared** — `period_factor_sigma` is only one contributor to it, and
article-level presence and quantity noise contribute more. The detection floor is computed from
the realised baseline.

## The freight column

`freight` is generated and written to every row but is **deliberately excluded from `amount`**
in the baseline.

This is the lever for the semantic-drift variants generated later (step 5): redefining `amount`
to include freight changes the measure's meaning while leaving structure, grain, dtypes, column
names and row counts byte-for-byte identical. Baseline and drifted worlds then differ *only* in
the measure definition — which is the condition non-claim **N1** is about.

At ≈3.1% of `amount`, the natural freight-inclusion event is small. Whether it falls above or
below the detection floor is not decided here; the floor has not been computed yet.

## Semantic assertions carried in the manifest

Recorded because they are true of the generator and **not derivable from the delivered data**:

| Claim | Checkable from data? |
| --- | --- |
| `amount` excludes freight | **No** |
| `amount` excludes VAT | **No** |
| one row per `(article_sku, report_period)` | Yes |

The first two are exactly the class of fact the human gate exists for. They are stated here so
that later runs cannot quietly assume the harness could have inferred them.

## Reproduction

```bash
python experiment1/generator/baseline.py
```

Deterministic. Rewriting the artifacts must produce an identical
`artifact_sha256.baseline_history.csv` in
[`artifacts/baseline_manifest.json`](../artifacts/baseline_manifest.json). A changed hash means
the generator or its parameters moved, and any downstream floor is invalidated.

## Explicitly not in this commit

- No detection floor.
- No warrant or evidence data structures.
- No drift variants (S-invisible, S-obvious, S-creep, sweep).
- No stress models (AR(1), seasonal).
- No agents, no LLM.
