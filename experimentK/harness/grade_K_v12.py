#!/usr/bin/env python3
"""Experiment K — v1.2 row-shape replay. Grading frozen in `expected_v12.json`.

The v1 and v1.1 arms are frozen INPUTS: they must reproduce their recorded
results exactly or the run is VOID.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dispatch import dispatch  # noqa: E402
from recipe import load_recipe  # noqa: E402
from referents import WorkbookView  # noqa: E402

EXPECTED = json.loads((ROOT / "expected_v12.json").read_text(encoding="utf-8"))
ORDER = [f"C{i}" for i in range(1, 14) if i != 13] + ["C13"]
STORE = {"approved": "recipes/W1_sales_v12_approved.json",
         "edited_after_approval": "recipes/W1_sales_edited_after_approval.json",
         "open_ambiguity": "recipes/W1_sales_open_ambiguity.json"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    problems: list[str] = []
    for name, spec in EXPECTED["recipes"].items():
        actual = _sha256(ROOT / spec["path"])
        if actual != spec["sha256"]:
            problems.append(f"recipe {name}: {actual} != frozen {spec['sha256']}")
    store = {k: load_recipe(ROOT / p) for k, p in STORE.items()}

    rows: dict[str, dict] = {}
    for cid in ORDER:
        spec = EXPECTED["per_case"][cid]
        wb_path = ROOT / spec["workbook"]
        if _sha256(wb_path) != spec["sha256"]:
            problems.append(f"{cid}: workbook hash != frozen")
        result = dispatch(WorkbookView(wb_path), [store[n] for n in spec["store"]])
        gt = spec["ground_truth"]
        rows[cid] = {
            "changed": spec["changed"], "ground_truth": gt,
            "v1": spec["v1_measured"], "v11": spec["v11_measured"],
            "v12": result.outcome, "v12_predicted": spec["v12_predicted"],
            "agree": result.outcome == gt,
            "fidelity": result.outcome == spec["v12_predicted"],
            "reason": result.reason, "delta": result.delta[:3],
        }
    if problems:
        raise SystemExit("VOID:\n  " + "\n  ".join(problems))

    fe = [c for c in ORDER if rows[c]["v12"] == "EXECUTE" and rows[c]["ground_truth"] != "EXECUTE"]
    oe = [c for c in ORDER if rows[c]["ground_truth"] == "EXECUTE" and rows[c]["v12"] != "EXECUTE"]
    agree = sum(1 for c in ORDER if rows[c]["agree"])
    fidelity = all(rows[c]["fidelity"] for c in ORDER)
    pred = EXPECTED["predicted_totals"]

    if rows["C13"]["v12"] != "REDEFINE_SCOPED":
        outcome = "FAIL_FIX"
    elif rows["C3"]["v12"] != "EXECUTE":
        outcome = "FAIL_REGRESSION"
    elif rows["C8"]["v12"] != "EXECUTE":
        outcome = "RESULT_BETTER_THAN_PREDICTED"
    elif [c for c in fe if c not in pred["v12_false_execute"]]:
        outcome = "FAIL_UNSAFE"
    elif fidelity and fe == pred["v12_false_execute"] and oe == pred["v12_over_escalation"]:
        outcome = "PASS_AS_PREDICTED"
    else:
        outcome = "RESULT_MISPREDICTED"

    return {"probe": "K-v12", "llm_invoked": False, "n_cases": len(ORDER),
            "per_case": rows, "agree": agree, "false_execute": fe, "over_escalation": oe,
            "fidelity_all": fidelity,
            "fidelity_deviations": [{"case": c, "predicted": rows[c]["v12_predicted"],
                                     "actual": rows[c]["v12"]}
                                    for c in ORDER if not rows[c]["fidelity"]],
            "predicted_totals": pred, "outcome": outcome}


if __name__ == "__main__":
    r = run()
    out = ROOT / "results" / "K_v12.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(f"wrote {out}  outcome={r['outcome']}  v12 {r['agree']}/13\n")
    raise SystemExit(0 if r["outcome"].startswith(("PASS", "RESULT")) else 1)
