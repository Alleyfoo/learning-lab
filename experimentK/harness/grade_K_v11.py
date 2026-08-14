#!/usr/bin/env python3
"""Experiment K — C3-fix replay: dispatch both recipe formats over 13 cases.

Grading frozen in `expected_v11.json`, committed before this file existed.
A SEPARATE measurement: K's `results/K.json` is a frozen input here, and the v1
arm must reproduce it exactly or the run is VOID.
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

EXPECTED = json.loads((ROOT / "expected_v11.json").read_text(encoding="utf-8"))
K_RESULT = json.loads((ROOT / "results" / "K.json").read_text(encoding="utf-8"))
ORDER = [f"C{i}" for i in range(1, 14) if i != 13] + ["C13"]

V1_STORE = {"approved": "recipes/W1_sales_approved.json",
            "edited_after_approval": "recipes/W1_sales_edited_after_approval.json",
            "open_ambiguity": "recipes/W1_sales_open_ambiguity.json"}
V11_STORE = dict(V1_STORE, approved="recipes/W1_sales_v11_approved.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    problems: list[str] = []
    for name, spec in EXPECTED["recipes"].items():
        actual = _sha256(ROOT / spec["path"])
        if actual != spec["sha256"]:
            problems.append(f"recipe {name}: {actual} != frozen {spec['sha256']}")

    v1 = {k: load_recipe(ROOT / p) for k, p in V1_STORE.items()}
    v11 = {k: load_recipe(ROOT / p) for k, p in V11_STORE.items()}

    rows: dict[str, dict] = {}
    for cid in ORDER:
        spec = EXPECTED["per_case"][cid]
        wb_path = ROOT / spec["workbook"]
        actual_hash = _sha256(wb_path)
        if actual_hash != spec["sha256"]:
            problems.append(f"{cid}: {actual_hash} != frozen {spec['sha256']}")
        view = WorkbookView(wb_path)

        a1 = dispatch(view, [v1[n] for n in spec["store"]])
        a11 = dispatch(view, [v11[n] for n in spec["store"]])
        gt = spec["ground_truth"]
        rows[cid] = {
            "changed": spec["changed"],
            "ground_truth": gt,
            "v1": a1.outcome,
            "v1_expected": spec["v1_measured"],
            "v1_reproduces_K": a1.outcome == spec["v1_measured"],
            "v11": a11.outcome,
            "v11_predicted": spec["v11_predicted"],
            "v11_fidelity": a11.outcome == spec["v11_predicted"],
            "v1_agree": a1.outcome == gt,
            "v11_agree": a11.outcome == gt,
            "v11_reason": a11.reason,
            "v11_delta": a11.delta[:3],
        }

    # The v1 arm must also reproduce K's own recorded run on C1-C12.
    for cid, krow in K_RESULT["per_case"].items():
        if rows.get(cid) and rows[cid]["v1"] != krow["actual"]:
            problems.append(f"{cid}: v1 arm {rows[cid]['v1']} != K's recorded {krow['actual']}")

    if problems:
        raise SystemExit("VOID:\n  " + "\n  ".join(problems))

    def sets(arm: str) -> tuple[list[str], list[str]]:
        fe = [c for c in ORDER
              if rows[c][arm] == "EXECUTE" and rows[c]["ground_truth"] != "EXECUTE"]
        oe = [c for c in ORDER
              if rows[c]["ground_truth"] == "EXECUTE" and rows[c][arm] != "EXECUTE"]
        return fe, oe

    v1_fe, v1_oe = sets("v1")
    v11_fe, v11_oe = sets("v11")
    v1_agree = sum(1 for c in ORDER if rows[c]["v1_agree"])
    v11_agree = sum(1 for c in ORDER if rows[c]["v11_agree"])
    fidelity = all(rows[c]["v11_fidelity"] for c in ORDER)
    pred = EXPECTED["predicted_totals"]

    if rows["C3"]["v11"] != "EXECUTE":
        outcome = "FAIL_FIX"
    elif [c for c in v11_fe if c not in pred["v11_false_execute"]]:
        outcome = "FAIL_UNSAFE"
    elif fidelity and v11_fe == pred["v11_false_execute"] and v11_oe == pred["v11_over_escalation"]:
        outcome = "PASS_AS_PREDICTED"
    else:
        outcome = "RESULT_MISPREDICTED"

    return {
        "probe": "K-c3fix", "llm_invoked": False, "n_cases": len(ORDER),
        "per_case": rows,
        "v1": {"agree": v1_agree, "false_execute": v1_fe, "over_escalation": v1_oe},
        "v11": {"agree": v11_agree, "false_execute": v11_fe, "over_escalation": v11_oe},
        "v11_fidelity_all": fidelity,
        "fidelity_deviations": [
            {"case": c, "predicted": rows[c]["v11_predicted"], "actual": rows[c]["v11"]}
            for c in ORDER if not rows[c]["v11_fidelity"]],
        "predicted_totals": pred,
        "outcome": outcome,
    }


if __name__ == "__main__":
    result = run()
    out = ROOT / "results" / "K_v11.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"wrote {out}  outcome={result['outcome']}  "
        f"v1 {result['v1']['agree']}/13  v11 {result['v11']['agree']}/13\n")
    raise SystemExit(0 if result["outcome"].startswith(("PASS", "RESULT")) else 1)
