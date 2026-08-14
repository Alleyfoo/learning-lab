#!/usr/bin/env python3
"""Experiment M — classify each shape as EXPRESSIBLE or GAP.

Mechanical facts only: does a recipe written in frozen format v1.3 validate,
execute, and produce the row count the shape obviously implies? The
classification follows from those facts by the rule frozen in the spec:

    EXPRESSIBLE  a valid recipe exists AND executes to the correct table
    GAP          otherwise; the missing capability is named in expected.json

`SILENT_WRONG` is flagged separately: the recipe validated and executed, and the
table is wrong anyway. That is categorically worse than a refusal and the freeze
requires it to be reported on its own.

Note the stated limitation: M froze CLASSIFICATIONS, not expected tables. The
row counts below are derivable from each fixture by inspection (2 products x 3
months, and so on) and are asserted here; anything subtler is judged in
RESULT.md with the reasoning shown.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
sys.path.insert(0, str(LAB / "definition_phase" / "harness"))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import load_recipe  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

EXPECTED = json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))

# Row counts implied by each fixture, by inspection of the generator.
IMPLIED_ROWS = {
    "S1_clean_wide": 6,           # 2 products x 3 months
    "S2_stacked_header": 6,       # 2 products x 3 months
    "S3_two_measure_blocks": 8,   # 2 products x 2 months x 2 measures
    "S4_already_long": 3,         # already one row per product-month
    "S5_formatted_numbers": 4,    # 2 products x 2 months
    "S6_interleaved_note": 4,     # 2 REAL products x 2 months
}
RECIPES = {s: f"M_{s.split('_')[0]}" for s in IMPLIED_ROWS}


def run() -> dict:
    shapes: dict[str, dict] = {}
    for stem, spec in EXPECTED["per_shape"].items():
        wb = WorkbookView(ROOT / spec["fixture"])
        recipe = load_recipe(ROOT / "recipes" / f"{RECIPES[stem]}.json")
        report = validate(recipe, wb)

        row = {
            "predicted": spec["predicted"],
            "predicted_missing_capability": spec["predicted_missing_capability"],
            "predicted_silent_wrong": spec["predicted_silent_wrong"],
            "valid": report.valid,
            "problem_codes": sorted(report.codes()),
            "implied_rows": IMPLIED_ROWS[stem],
        }
        if not report.valid:
            row.update({"executed": False, "classification": "GAP",
                        "silent_wrong": False,
                        "behaviour": "recipe INVALID -- the system refuses rather "
                                     "than producing a wrong table"})
        else:
            try:
                ex = execute(recipe, wb)
            except InsufficientRecipe as exc:
                row.update({"executed": False, "classification": "GAP",
                            "silent_wrong": False,
                            "behaviour": f"executor refused: {exc}"})
            else:
                unhonoured = [t["target"] for t in ex.unhonoured_types]
                correct = (len(ex.rows) == IMPLIED_ROWS[stem]) and not unhonoured
                row.update({
                    "executed": True,
                    "columns": ex.columns,
                    "n_rows": len(ex.rows),
                    "unhonoured_types": ex.unhonoured_types,
                    "classification": "EXPRESSIBLE" if correct else "GAP",
                    "silent_wrong": not correct,
                    "behaviour": ("correct table" if correct else
                                  f"validated and executed, but produced "
                                  f"{len(ex.rows)}/{IMPLIED_ROWS[stem]} rows"
                                  + (f" and left {unhonoured} untyped" if unhonoured else "")),
                    "sample": ex.rows[:4],
                })
        row["as_predicted"] = row["classification"] == spec["predicted"]
        row["silent_wrong_as_predicted"] = row["silent_wrong"] == spec["predicted_silent_wrong"]
        shapes[stem] = row

    expressible = [s for s, r in shapes.items() if r["classification"] == "EXPRESSIBLE"]
    gaps = [s for s, r in shapes.items() if r["classification"] == "GAP"]
    silent = [s for s, r in shapes.items() if r["silent_wrong"]]
    pred = EXPECTED["predicted_totals"]

    more_capable = [s for s, r in shapes.items()
                    if r["predicted"] == "GAP" and r["classification"] == "EXPRESSIBLE"]
    less_capable = [s for s, r in shapes.items()
                    if r["predicted"] == "EXPRESSIBLE" and r["classification"] == "GAP"]
    unpredicted_silent = [s for s in silent if s not in pred["silent_wrong"]]

    if unpredicted_silent:
        outcome = "RESULT_UNPREDICTED_SILENT_WRONG"
    elif less_capable:
        outcome = "RESULT_LESS_CAPABLE"
    elif more_capable:
        outcome = "RESULT_MORE_CAPABLE"
    elif all(r["as_predicted"] and r["silent_wrong_as_predicted"] for r in shapes.values()):
        outcome = "PASS_AS_PREDICTED"
    else:
        outcome = "RESULT_MISPREDICTED"

    return {
        "probe": "M", "llm_invoked": False,
        "per_shape": shapes,
        "n_expressible": len(expressible), "n_gap": len(gaps),
        "expressible": expressible, "gaps": gaps,
        "silent_wrong": silent,
        "more_capable_than_predicted": more_capable,
        "less_capable_than_predicted": less_capable,
        "unpredicted_silent_wrong": unpredicted_silent,
        "predicted_totals": pred,
        "outcome": outcome,
    }


if __name__ == "__main__":
    result = run()
    out = ROOT / "results" / "M.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(f"wrote {out}  outcome={result['outcome']}  "
                     f"{result['n_expressible']} expressible / {result['n_gap']} gaps\n")
    raise SystemExit(0)
