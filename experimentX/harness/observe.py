#!/usr/bin/env python3
"""PROGRAM observations for the enrichment sources. Computed, never written.

Same discipline as U's `claims.py`: everything here is read off the source
representation — names, types, distinct counts, value shapes. Nothing that
requires interpretation is OBSERVED.

## The one new observation kind, and why it is still mechanical

X's load-bearing claim is a **join binding**, so the program must be able to
report what a join key would actually do. `value_containment` measures, for every
field pair across two sources, what fraction of the left field's values appear in
the right field's values. Counting set membership is not interpretation.

It is also what makes X honest. The fixtures are built so that

```text
orders.item within products.sku    3/3
orders.item within products.code   3/3
```

Both are complete. Both joins succeed with nothing missing and nothing
ambiguous — and they select different products, because `sku` and `code` are
crossed on the first two rows. So the program can establish that **two candidate
keys are equally supported**, which is exactly the fact an inspector needs in
order to know it cannot settle the binding.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = ROOT / "fixtures"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECIMALISH = re.compile(r"^-?\d+\.\d+$")


def _collections() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = next(k for k in data if not k.startswith("_"))
        out[name] = data[name]
    return out


def observed_claims() -> list[dict]:
    collections = _collections()
    claims: list[dict] = []

    for name, items in collections.items():
        claims.append({"claim": {"source": name, "fields": sorted(items[0]),
                                 "row_count": len(items)},
                       "status": "OBSERVED", "basis": "source_structure"})
        for field in sorted(items[0]):
            values = [item[field] for item in items if field in item]
            entry = {"source": name, "field": field,
                     "type": type(values[0]).__name__,
                     "distinct_values": len(set(map(str, values)))}
            if all(isinstance(v, str) and ISO_DATE.match(v) for v in values):
                entry["value_shape"] = "YYYY-MM-DD"
            elif all(isinstance(v, str) and DECIMALISH.match(v) for v in values):
                entry["value_shape"] = "decimal written as a string"
            claims.append({"claim": entry, "status": "OBSERVED",
                           "basis": "measured_from_values"})

    # --- cross-source containment: what a join key would actually do ---------
    for left_name, left_items in collections.items():
        for right_name, right_items in collections.items():
            if left_name == right_name:
                continue
            for lf in sorted(left_items[0]):
                lvals = [str(i[lf]) for i in left_items if lf in i]
                for rf in sorted(right_items[0]):
                    rlist = [str(i[rf]) for i in right_items if rf in i]
                    rvals = set(rlist)
                    hits = sum(1 for v in lvals if v in rvals)
                    if not hits:
                        continue
                    claims.append({
                        "claim": {"left": f"{left_name}.{lf}",
                                  "right": f"{right_name}.{rf}",
                                  "values_of_left_found_in_right": f"{hits}/{len(lvals)}",
                                  # A key that repeats cannot identify one row.
                                  "right_values_are_unique": len(rvals) == len(rlist)},
                        "status": "OBSERVED", "basis": "value_containment"})
    return claims


def main(argv: list[str]) -> int:
    claims = observed_claims()
    counts: dict[str, int] = {}
    for c in claims:
        counts[c["basis"]] = counts.get(c["basis"], 0) + 1
    print(f"{len(claims)} OBSERVED claims: {counts}\n")
    for c in claims:
        if c["basis"] == "value_containment":
            print("  " + json.dumps(c["claim"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
