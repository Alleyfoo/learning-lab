#!/usr/bin/env python3
"""Experiment L — execute and grade against the frozen expected tables."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import load_recipe  # noqa: E402
from referents import WorkbookView  # noqa: E402

EXPECTED = json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    rpath = (ROOT / EXPECTED["recipe"]["path"]).resolve()
    actual = _sha256(rpath)
    if actual != EXPECTED["recipe"]["sha256"]:
        raise SystemExit(f"VOID: recipe hash {actual} != frozen "
                         f"{EXPECTED['recipe']['sha256']}")
    recipe = load_recipe(rpath)

    cases: dict[str, dict] = {}
    insufficient: list[str] = []
    for cid, spec in EXPECTED["cases"].items():
        wb_path = (ROOT / spec["workbook"]).resolve()
        try:
            result = execute(recipe, WorkbookView(wb_path))
        except InsufficientRecipe as exc:
            insufficient.append(f"{cid}: {exc}")
            cases[cid] = {"insufficient": str(exc)}
            continue

        expected_rows = [list(r) for r in spec["expected_rows"]]
        got_rows = [list(r) for r in result.rows]
        match = got_rows == expected_rows
        diff = []
        if not match:
            for i in range(max(len(expected_rows), len(got_rows))):
                e = expected_rows[i] if i < len(expected_rows) else None
                g = got_rows[i] if i < len(got_rows) else None
                if e != g:
                    diff.append({"row": i, "expected": e, "got": g})
        cases[cid] = {
            "workbook": spec["workbook"],
            "columns": result.columns,
            "expected_columns": EXPECTED["output_columns"],
            "columns_match": result.columns == EXPECTED["output_columns"],
            "n_expected": len(expected_rows), "n_got": len(got_rows),
            "rows_match": match,
            "diff": diff[:6],
            "unhonoured_types": result.unhonoured_types,
            "rows": got_rows,
        }

    if insufficient:
        outcome = "FAIL_INSUFFICIENT"
    else:
        ok = all(c["rows_match"] and c["columns_match"] for c in cases.values())
        gaps = sorted({t.get("gap") for c in cases.values()
                       for t in c.get("unhonoured_types", []) if t.get("gap")})
        untyped = [t for c in cases.values() for t in c.get("unhonoured_types", [])
                   if not t.get("gap")]
        if not ok:
            outcome = "FAIL"
        elif gaps == ["G1"] and not untyped:
            outcome = "PASS_AS_PREDICTED"
        else:
            outcome = "RESULT_MORE_GAPS"

    return {
        "probe": "L", "llm_invoked": False,
        "recipe": EXPECTED["recipe"]["path"], "recipe_sha256": actual,
        "cases": cases,
        "insufficient": insufficient,
        "gaps_found": sorted({t.get("gap") or t["declared"]
                              for c in cases.values()
                              for t in c.get("unhonoured_types", [])}),
        "predicted_gaps": list(EXPECTED["predicted_gaps"]),
        "outcome": outcome,
    }


if __name__ == "__main__":
    result = run()
    out = ROOT / "results" / "L.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    sys.stdout.write(f"wrote {out}  outcome={result['outcome']}\n")
    raise SystemExit(0 if result["outcome"].startswith(("PASS", "RESULT")) else 1)
