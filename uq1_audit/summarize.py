"""Summarise the UQ-1 register. Runs only once real rows exist.

Computes the drift-class distribution, the reachability ratio and anchor
availability. Deliberately dumb -- this is arithmetic over a manually
classified register, not inference.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CLASSES = ["unchanged", "cosmetic", "structural",
           "possible_semantic", "semantic_confirmed", "unknown"]


def main() -> int:
    path = ROOT / "register.csv"
    if not path.exists():
        print("register.csv not found.")
        print("Copy register_template.csv to register.csv, delete the EXAMPLE rows,")
        print("and classify real transitions per classification_protocol.md.")
        return 1

    df = pd.read_csv(path)
    df = df[~df["provider_id"].astype(str).str.startswith("EXAMPLE")]
    if df.empty:
        print("register.csv contains no real rows yet.")
        return 1

    bad = sorted(set(df["classification"]) - set(CLASSES))
    if bad:
        print(f"Unknown classification values: {bad}")
        return 1

    n = len(df)
    dist = (df["classification"].value_counts().reindex(CLASSES).fillna(0).astype(int))
    semantic_total = int(dist["possible_semantic"] + dist["semantic_confirmed"])

    out = {
        "n_transitions": n,
        "n_providers": int(df["provider_id"].nunique()),
        "distribution": dist.to_dict(),
        "distribution_pct": {k: round(100 * v / n, 2) for k, v in dist.to_dict().items()},
        "semantic_reachability": {
            "possible_semantic": int(dist["possible_semantic"]),
            "semantic_confirmed": int(dist["semantic_confirmed"]),
            "reachable_fraction": (
                None if semantic_total == 0
                else round(dist["semantic_confirmed"] / semantic_total, 4)
            ),
            "note": "Fraction of semantic events for which external evidence existed. "
                    "The remainder is unreachable by any amount of detection (N1).",
        },
        "anchor_availability": df["anchor_available"].value_counts().to_dict(),
        "anchor_types": df["anchor_type"].value_counts().to_dict(),
        "by_provider": (
            df.groupby("provider_id")["classification"]
            .value_counts().unstack(fill_value=0).to_dict(orient="index")
        ),
        "unknown_rate": round(float(dist["unknown"]) / n, 4),
    }

    (ROOT / "uq1_summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"transitions: {n}   providers: {out['n_providers']}\n")
    for k in CLASSES:
        print(f"  {k:20s} {dist[k]:4d}  {out['distribution_pct'][k]:6.2f}%")
    r = out["semantic_reachability"]["reachable_fraction"]
    print(f"\nsemantic reachability: {'n/a' if r is None else f'{r:.1%}'} "
          f"({dist['semantic_confirmed']} confirmed / {semantic_total} semantic)")
    print(f"anchor availability  : {out['anchor_availability']}")
    print(f"unknown rate         : {out['unknown_rate']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
