#!/usr/bin/env python3
"""The PROGRAM half of inspection. Boring on purpose.

Everything here is measured off the source representation. Nothing here
interprets. The rule that keeps it honest:

> The program emits the measurable facts from which a modeller may reason. It
> does NOT emit `orders.item joins products.sku` — that remains interpretation.

## Fixed here: the defect Experiment X exposed

X's observer characterised `price` (`"19.99"`) as decimal-shaped and said nothing
at all about `quantity` (`"3"`, `"7"`, `"2"`), because its regex required a
decimal point. It described one operand of a declared multiplication and not the
other, and all three probes correctly blocked on the gap.

`value_kind` now covers integer-looking and decimal-looking numeric strings under
one kind, with examples, so a modeller can see what a field holds instead of
inferring it from a shape that may not have been reported.

## Candidate relationships

For every field pair across two sources, the program reports what a join on that
pair would mechanically do:

```text
left_coverage   how many of the left field's values are present on the right
right_unique    whether the right field identifies at most one row per value
```

Both are counting. Neither says which pairing is *intended* — that is a binding,
and a binding is a modelling decision.
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_EXAMPLES = 3


def value_kind(values: list) -> str:
    """One of `numeric_string`, `date_string`, `text`, `mixed`.

    `numeric_string` covers "3" and "19.99" alike -- X's defect was treating
    those as different kinds of thing, so one operand of a multiplication was
    described and the other was not.
    """
    if not values:
        return "text"
    if not all(isinstance(v, str) for v in values):
        return "mixed" if len({type(v).__name__ for v in values}) > 1 else "text"
    if all(ISO_DATE.match(v) for v in values):
        return "date_string"
    for v in values:
        try:
            Decimal(v.strip())
        except (InvalidOperation, ValueError, ArithmeticError):
            return "text"
    return "numeric_string"


def _examples(values: list) -> list:
    seen, out = set(), []
    for v in values:
        key = str(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
        if len(out) == MAX_EXAMPLES:
            break
    return out


def collections_in(fixtures: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(fixtures.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = next(k for k in data if not k.startswith("_"))
        out[name] = data[name]
    return out


def observed_claims(fixtures: Path) -> list[dict]:
    collections = collections_in(fixtures)
    claims: list[dict] = []

    for name, items in collections.items():
        claims.append({"claim": {"source": name, "fields": sorted(items[0]),
                                 "row_count": len(items)},
                       "status": "OBSERVED", "basis": "source_structure"})
        for field in sorted(items[0]):
            values = [item[field] for item in items if field in item]
            claims.append({"claim": {
                "source": name, "field": field,
                "type": type(values[0]).__name__,
                "distinct_values": len(set(map(str, values))),
                "value_kind": value_kind(values),
                "examples": _examples(values)},
                "status": "OBSERVED", "basis": "measured_from_values"})

    for left_name, left_items in collections.items():
        for right_name, right_items in collections.items():
            if left_name == right_name:
                continue
            for lf in sorted(left_items[0]):
                lvals = [str(i[lf]) for i in left_items if lf in i]
                for rf in sorted(right_items[0]):
                    rlist = [str(i[rf]) for i in right_items if rf in i]
                    hits = sum(1 for v in lvals if v in set(rlist))
                    if not hits:
                        continue
                    claims.append({"claim": {"candidate_relationship": {
                        "left": f"{left_name}.{lf}",
                        "right": f"{right_name}.{rf}",
                        "left_coverage": f"{hits}/{len(lvals)}",
                        "right_unique": len(set(rlist)) == len(rlist)}},
                        "status": "OBSERVED", "basis": "value_containment"})
    return claims


def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- the X defect, directly -------------------------------------------
    check(value_kind(["3", "7", "2"]) == "numeric_string",
          "REGRESSION: integer strings must be numeric_string -- X described "
          "price and not quantity, and every probe blocked on the gap")
    check(value_kind(["19.99", "0.10"]) == "numeric_string",
          "decimal strings are the same kind")
    check(value_kind(["3", "19.99"]) == "numeric_string",
          "a field mixing both is still numeric")
    check(value_kind(["2026-01-01", "2026-12-25"]) == "date_string",
          "ISO dates are their own kind")
    check(value_kind(["A", "B", "C"]) == "text",
          "CANARY: A/B/C must NOT become numeric -- V's `tier`")
    check(value_kind(["A-100", "B-200"]) == "text", "CANARY: SKUs are text")
    check(value_kind([]) == "text", "an empty field does not crash")
    check(value_kind([3, 7]) == "text" and value_kind([3, "7"]) == "mixed",
          f"non-strings: {value_kind([3, 7])}, {value_kind([3, '7'])}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "orders.json").write_text(json.dumps({"orders": [
            {"item": "A-100", "quantity": "3"},
            {"item": "B-200", "quantity": "7"},
            {"item": "C-300", "quantity": "2"}]}), encoding="utf-8")
        (base / "products.json").write_text(json.dumps({"products": [
            {"sku": "A-100", "code": "Z-900", "price": "1.00"},
            {"sku": "B-200", "code": "A-100", "price": "2.00"},
            {"sku": "C-300", "code": "C-300", "price": "5.00"}]}), encoding="utf-8")
        claims = observed_claims(base)

        quantity = next(c["claim"] for c in claims
                        if c["claim"].get("field") == "quantity")
        check(quantity["value_kind"] == "numeric_string"
              and quantity["examples"] == ["3", "7", "2"],
              f"quantity must be described, with examples: {quantity}")

        rels = {(r["left"], r["right"]): r for r in
                (c["claim"]["candidate_relationship"] for c in claims
                 if "candidate_relationship" in c["claim"])}
        sku = rels[("orders.item", "products.sku")]
        code = rels[("orders.item", "products.code")]
        check(sku["left_coverage"] == "3/3" and sku["right_unique"],
              f"complete coverage must be reported as such: {sku}")
        check(code["left_coverage"] == "2/3" and code["right_unique"],
              f"partial coverage must be reported as such: {code}")

        # --- THE LINE THE PROGRAM MUST NOT CROSS ---------------------------
        text = json.dumps(claims)
        for forbidden in ("join", "foreign_key", "meaning", "matches",
                          "intended", "INFERRED"):
            check(forbidden not in text,
                  f"CANARY: the program emitted {forbidden!r} -- it reports "
                  f"measurements, never a binding")
        check(all(c["status"] == "OBSERVED" for c in claims),
              "the program emits OBSERVED and nothing else")

        # --- a repeated right-hand key cannot identify a row ---------------
        (base / "products.json").write_text(json.dumps({"products": [
            {"sku": "A-100", "code": "X", "price": "1.00"},
            {"sku": "A-100", "code": "Y", "price": "2.00"},
            {"sku": "C-300", "code": "Z", "price": "5.00"}]}), encoding="utf-8")
        rels = {(r["left"], r["right"]): r for r in
                (c["claim"]["candidate_relationship"] for c in observed_claims(base)
                 if "candidate_relationship" in c["claim"])}
        dup = rels[("orders.item", "products.sku")]
        check(dup["right_unique"] is False,
              f"CANARY: a duplicated right key must report right_unique false: {dup}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (integer AND decimal strings are numeric_string, "
          "closing X's defect / A-B-C and SKUs stay text / dates are their own "
          "kind / fields carry examples / complete and partial coverage are "
          "reported as measured / a duplicated right key reports right_unique "
          "false / the program never emits a join, a meaning or an inference)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    if not argv:
        sys.stderr.write("usage: observe.py <fixtures-dir> | --self-test\n")
        return 2
    print(json.dumps(observed_claims(Path(argv[0])), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
