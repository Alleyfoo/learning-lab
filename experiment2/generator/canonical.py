"""Hidden canonical dataset -- the ground truth every equivalent variant must reduce to.

Canonical shape:

    country | product_id | period  | sales
    FI      | ART-0001   | 2026-01 | 10.00

Small and interpretable on purpose. The experiment wants legible failures, not
benchmark volume.

`artifacts/canonical.csv` is HIDDEN. It is never placed in the task packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from vocabulary import CANONICAL_COUNTRIES

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CANONICAL_COLUMNS = ["country", "product_id", "period", "sales"]


@dataclass(frozen=True)
class CanonicalParams:
    seed: int = 20260809
    year: int = 2026
    n_months: int = 6
    products: tuple[str, ...] = (
        "ART-0001", "ART-0002", "ART-0003", "ART-0004", "ART-0005",
    )
    presence_prob: float = 0.80          # sparsity: not every country sells every product
    sales_low: float = 3.0
    sales_high: float = 900.0


def generate(p: CanonicalParams) -> pd.DataFrame:
    rng = np.random.default_rng(p.seed)
    rows = []
    for country in CANONICAL_COUNTRIES:
        for product in p.products:
            if rng.random() > p.presence_prob:
                continue                                  # this pair never appears
            for m in range(1, p.n_months + 1):
                if rng.random() < 0.08:
                    continue                              # occasional missing month
                value = float(rng.uniform(p.sales_low, p.sales_high))
                rows.append({
                    "country": country,
                    "product_id": product,
                    "period": f"{p.year}-{m:02d}",
                    "sales": round(value, 2),
                })
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS).sort_values(
        CANONICAL_COLUMNS[:3]
    ).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=ARTIFACTS)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    params = CanonicalParams(seed=args.seed) if args.seed else CanonicalParams()
    df = generate(params)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"canonical{args.suffix}.csv"
    df.to_csv(path, index=False, lineterminator="\n")

    manifest = {
        "hidden": True,
        "note": "Ground truth. Never place this file, or any derivative, in the task packet.",
        "params": asdict(params),
        "columns": CANONICAL_COLUMNS,
        "n_rows": int(len(df)),
        "countries": sorted(df["country"].unique().tolist()),
        "products": sorted(df["product_id"].unique().tolist()),
        "periods": sorted(df["period"].unique().tolist()),
        "grain": "one row per (country, product_id, period)",
        "sales_total": round(float(df["sales"].sum()), 2),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (args.out_dir / f"canonical{args.suffix}_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"rows={len(df)}  countries={len(manifest['countries'])}  "
          f"products={len(manifest['products'])}  periods={len(manifest['periods'])}")
    print(f"grain unique: {not df.duplicated(subset=CANONICAL_COLUMNS[:3]).any()}")
    print(f"sha256 {manifest['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
