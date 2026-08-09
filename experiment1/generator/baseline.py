"""Frozen baseline history generator for Experiment 1.

Generates a synthetic monthly sales history from a KNOWN distribution with NO
drift of any kind. This is the instrument's calibration input.

Declared world model for the baseline: **iid across periods.**
No seasonality, no autocorrelation. Stress models (AR(1), seasonal) are
introduced in step 7 and are NOT part of this file.

The generator emits a `freight` column that is deliberately NOT included in the
`amount` measure. That column is the lever used later to inject semantic drift
(redefining `amount` to include freight). It exists in the baseline so that the
baseline and drifted worlds differ only in the measure definition, not in the
data available.

Nothing in this module knows about drift, detection floors, or variants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA_VERSION = "baseline/1"


@dataclass(frozen=True)
class BaselineParams:
    """Every number that affects the generated history. Committed verbatim."""

    seed: int = 20260809
    n_periods: int = 24
    first_period: str = "2024-01"
    n_articles: int = 150

    # Article-level structure
    article_presence_prob: float = 0.85
    qty_lognorm_mean: float = 2.4          # log-space
    qty_lognorm_sigma: float = 0.55
    price_lognorm_mean: float = 3.0        # log-space, ~EUR 20
    price_lognorm_sigma: float = 0.45
    price_jitter_sigma: float = 0.01       # per-period price wobble

    # Period-level multiplicative factor. NOTE: this is only ONE contributor to the
    # coefficient of variation of period totals; article-level presence and quantity
    # noise contribute more. The realised CV is measured from the generated data and
    # recorded in the manifest -- the detection floor is computed from the realised
    # baseline, never from this knob.
    period_factor_sigma: float = 0.04

    # Freight is generated but NOT added to `amount` in the baseline.
    freight_rate_mean: float = 0.031
    freight_rate_sigma: float = 0.004


def _periods(first: str, n: int) -> list[str]:
    start = pd.Period(first, freq="M")
    return [str(start + i) for i in range(n)]


def generate(params: BaselineParams) -> pd.DataFrame:
    rng = np.random.default_rng(params.seed)
    periods = _periods(params.first_period, params.n_periods)

    article_ids = [f"ART-{i:04d}" for i in range(params.n_articles)]
    base_qty = rng.lognormal(params.qty_lognorm_mean, params.qty_lognorm_sigma, params.n_articles)
    base_price = rng.lognormal(params.price_lognorm_mean, params.price_lognorm_sigma, params.n_articles)

    # iid period factors -- no trend, no season, no autocorrelation.
    period_factor = rng.normal(1.0, params.period_factor_sigma, params.n_periods)

    rows: list[dict] = []
    for t, period in enumerate(periods):
        present = rng.random(params.n_articles) < params.article_presence_prob
        price_jit = rng.normal(1.0, params.price_jitter_sigma, params.n_articles)
        qty_noise = rng.lognormal(0.0, 0.25, params.n_articles)
        freight_rate = rng.normal(
            params.freight_rate_mean, params.freight_rate_sigma, params.n_articles
        ).clip(0.0, None)

        for a in range(params.n_articles):
            if not present[a]:
                continue
            qty = max(1, int(round(base_qty[a] * qty_noise[a] * period_factor[t])))
            unit_price = round(float(base_price[a] * price_jit[a]), 2)
            amount = round(qty * unit_price, 2)
            rows.append(
                {
                    "report_period": period,
                    "article_sku": article_ids[a],
                    "quantity": qty,
                    "unit_price": unit_price,
                    # `amount` EXCLUDES freight in the baseline. This is a semantic
                    # assertion, recorded in the manifest, not derivable from the data.
                    "amount": amount,
                    "freight": round(amount * float(freight_rate[a]), 2),
                }
            )

    return pd.DataFrame(rows)


def realised_stats(df: pd.DataFrame) -> dict:
    totals = df.groupby("report_period")["amount"].sum()
    freight = df.groupby("report_period")["freight"].sum()
    return {
        "n_periods": int(totals.size),
        "n_rows": int(len(df)),
        "period_total_mean": float(totals.mean()),
        "period_total_sd": float(totals.std(ddof=1)),
        "period_total_cv": float(totals.std(ddof=1) / totals.mean()),
        "rows_per_period_mean": float(df.groupby("report_period").size().mean()),
        "freight_share_of_amount": float(freight.sum() / totals.sum()),
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the frozen Experiment 1 baseline history")
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parents[1] / "artifacts")
    args = ap.parse_args()

    params = BaselineParams()
    df = generate(params)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "baseline_history.csv"
    df.to_csv(csv_path, index=False, lineterminator="\n")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": "experiment1/generator/baseline.py",
        "params": asdict(params),
        "declared_world_model": "iid",
        "semantic_assertions": [
            {
                "claim": "amount excludes freight",
                "source": "generator construction",
                "checkable_from_data": False,
            },
            {
                "claim": "amount excludes VAT",
                "source": "generator construction",
                "checkable_from_data": False,
            },
            {
                "claim": "one row per (article_sku, report_period)",
                "source": "generator construction",
                "checkable_from_data": True,
            },
        ],
        "realised": realised_stats(df),
        "artifact_sha256": {"baseline_history.csv": sha256(csv_path)},
    }
    (args.out_dir / "baseline_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    r = manifest["realised"]
    print(f"periods={r['n_periods']} rows={r['n_rows']}")
    print(f"period_total mean={r['period_total_mean']:,.0f} sd={r['period_total_sd']:,.0f}")
    print(f"period_total CV={r['period_total_cv']:.4f}")
    print(f"freight share of amount={r['freight_share_of_amount']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
