#!/usr/bin/env python3
"""Experiment K — run the 12 frozen cases and grade against expected.json.

Grading is frozen in `expected.json`, committed before `dispatch.py` existed.
Pass criteria are not relaxed after the fact.

    agree            dispatch == ground_truth
    fidelity         dispatch == predicted   (a check on the AUTHOR, not the
                                              algorithm)
    false_execute    EXECUTE where ground truth is not EXECUTE   <- unsafe
    over_escalation  not EXECUTE where ground truth is EXECUTE   <- noise
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

EXPECTED = json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))
ORDER = [f"C{i}" for i in range(1, 13)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    recipes_spec = EXPECTED["recipes"]
    hash_failures: list[str] = []

    for name, spec in recipes_spec.items():
        actual = _sha256(ROOT / spec["path"])
        if actual != spec["sha256"]:
            hash_failures.append(f"recipe {name}: {actual} != frozen {spec['sha256']}")

    store = {name: load_recipe(ROOT / spec["path"]) for name, spec in recipes_spec.items()}

    rows: dict[str, dict] = {}
    for cid in ORDER:
        spec = EXPECTED["per_case"][cid]
        wb_path = ROOT / spec["workbook"]
        actual = _sha256(wb_path)
        if actual != spec["sha256"]:
            hash_failures.append(f"{cid}: {actual} != frozen {spec['sha256']}")

        view = WorkbookView(wb_path)
        selected = [store[n] for n in spec["store"]]
        result = dispatch(view, selected)

        gt, pred = spec["ground_truth"], spec["predicted"]
        rows[cid] = {
            "changed": spec["changed"],
            "store": spec["store"],
            "ground_truth": gt,
            "predicted": pred,
            "actual": result.outcome,
            "agree": result.outcome == gt,
            "fidelity": result.outcome == pred,
            "reason": result.reason,
            "delta": result.delta[:4],
            "recipe_id": result.recipe_id,
        }

    if hash_failures:
        raise SystemExit("VOID: frozen input hash mismatch:\n  " + "\n  ".join(hash_failures))

    false_execute = [c for c in ORDER
                     if rows[c]["actual"] == "EXECUTE" and rows[c]["ground_truth"] != "EXECUTE"]
    over_escalation = [c for c in ORDER
                       if rows[c]["ground_truth"] == "EXECUTE" and rows[c]["actual"] != "EXECUTE"]
    fidelity_all = all(rows[c]["fidelity"] for c in ORDER)
    agree_n = sum(1 for c in ORDER if rows[c]["agree"])
    baseline_ok = rows["C1"]["actual"] == "EXECUTE" and rows["C2"]["actual"] == "EXECUTE"

    predicted = EXPECTED["predicted_totals"]
    if not baseline_ok:
        outcome = "FAIL_BASELINE"
    elif [c for c in false_execute if c not in predicted["false_execute"]]:
        outcome = "FAIL_UNSAFE"
    elif [c for c in over_escalation if c not in predicted["over_escalation"]]:
        outcome = "FAIL_NOISE"
    elif (fidelity_all
          and false_execute == predicted["false_execute"]
          and over_escalation == predicted["over_escalation"]):
        outcome = "PASS_AS_PREDICTED"
    else:
        outcome = "RESULT_MISPREDICTED"

    return {
        "probe": "K",
        "llm_invoked": False,
        "n_cases": len(ORDER),
        "per_case": rows,
        "agree": agree_n,
        "predicted_agree": predicted["agree"],
        "false_execute": false_execute,
        "over_escalation": over_escalation,
        "fidelity_all": fidelity_all,
        "fidelity_deviations": [
            {"case": c, "predicted": rows[c]["predicted"], "actual": rows[c]["actual"]}
            for c in ORDER if not rows[c]["fidelity"]
        ],
        "baseline_ok": baseline_ok,
        "predicted_totals": predicted,
        "outcome": outcome,
    }


if __name__ == "__main__":
    result = run()
    # Written here rather than via shell redirection: the Windows console
    # codepage mangles non-ASCII on the way out, and these deltas name Finnish
    # headers.
    out = ROOT / "results" / "K.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(f"wrote {out}  outcome={result['outcome']}  agree={result['agree']}/12\n")
    raise SystemExit(0 if result["outcome"].startswith(("PASS", "RESULT")) else 1)
