"""Build the Condition B warm-up task. TRAINING MATERIAL, NOT EVIDENCE.

Deliberately trivial: already long-form, already ISO periods, already ISO
country codes, already plain numbers. The only work is recognising the canonical
contract and renaming four columns. No reshaping, no locale, no separator
ambiguity, no missing values.

Kept disjoint from the graded corpus:
  - product ids ART-9xxx (graded corpus uses ART-0001..0005)
  - year 2025      (graded corpus uses 2026)
  - no held-out locale appears anywhere
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
ROWS = [
    ("FI", "ART-9001", "2025-01", 10.00), ("FI", "ART-9001", "2025-02", 11.50),
    ("FI", "ART-9002", "2025-01", 8.25),  ("SE", "ART-9001", "2025-01", 12.00),
    ("SE", "ART-9002", "2025-01", 6.75),  ("SE", "ART-9002", "2025-02", 9.00),
    ("DE", "ART-9003", "2025-01", 21.40), ("DE", "ART-9003", "2025-02", 19.95),
]

def main() -> int:
    truth = pd.DataFrame(ROWS, columns=["country", "product_id", "period", "sales"])
    truth.to_csv(ROOT / "warmup_truth.csv", index=False, lineterminator="\n")

    # The source: same information, four differently-named columns, different order.
    src = pd.DataFrame({
        "Country": truth["country"],
        "Product": truth["product_id"],
        "Month": truth["period"],
        "Sales": truth["sales"].map(lambda v: f"{v:.2f}"),
    })
    src.to_csv(ROOT / "warmup_source.csv", index=False, lineterminator="\n")

    (ROOT / "warmup_manifest.json").write_text(json.dumps({
        "role": "TRAINING MATERIAL - NOT EVIDENCE",
        "disjoint_from_graded_corpus": {
            "product_ids": "ART-9xxx vs graded ART-0001..0005",
            "year": "2025 vs graded 2026",
            "locales": "none beyond plain ISO / English",
        },
        "n_rows": len(truth),
        "difficulty": "rename four columns; no reshape, no locale, no ambiguity",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"warm-up: {len(truth)} rows")
    print(src.head(3).to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
