#!/usr/bin/env python3
"""Experiment J — replay macro v1 and macro v2 over the frozen fixture set.

Grading is frozen in `expected.json` (committed before `macro_v2.py` existed).
Pass criteria are not relaxed after the fact.

For every fixture: verify sha256, run v1 (imported verbatim from Experiment I)
and v2, compare both against the frozen ground truth, and compare v2 against
the frozen PREDICTED output (fidelity — a check on the author's
hand-simulation, not on v2's correctness).

    repairs      = { f : v1 wrong, v2 right }
    regressions  = { f : v1 right, v2 wrong }
    outcome      = decision table in expected.json

Miss direction is recorded separately: `unknown` on a wide/long table is a
FALSE REFUSAL (safe direction — escalates to a human); `wide`/`long` on a table
that is something else is a FALSE ASSERTION (the unsafe direction the 3A-3E
programme is about).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from macro_v2 import classify_file, verify_v1_source  # noqa: E402

EXPECTED_PATH = ROOT / "expected.json"
ORDER = ("I1", "I2", "I3", "I4", "J1", "J2", "J3", "J4", "J5", "J6", "J7")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def miss_direction(label: str, ground_truth: str) -> str | None:
    if label == ground_truth:
        return None
    if label == "unknown":
        return "false_refusal"      # refused a table that has a clean answer
    if ground_truth == "unknown":
        return "false_assertion"    # asserted a shape the table does not have
    return "false_assertion"        # wide<->long confusion: also an assertion


def replay() -> dict:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    per_fixture = expected["per_fixture"]

    v1_hash = verify_v1_source()
    hash_failures: list[str] = []
    rows: dict[str, dict] = {}

    for fid in ORDER:
        spec = per_fixture[fid]
        path = (ROOT / spec["fixture"]).resolve()
        actual_hash = _sha256(path)
        if actual_hash != spec["sha256"]:
            hash_failures.append(f"{fid}: {actual_hash} != frozen {spec['sha256']}")

        r = classify_file(path)
        gt = spec["ground_truth"]
        v1, v2 = r["v1"], r["v2"]
        v1_ok, v2_ok = v1 == gt, v2 == gt
        rows[fid] = {
            "set": spec["set"],
            "shape": spec["shape"],
            "ground_truth": gt,
            "v1": v1,
            "v1_ok": v1_ok,
            "v1_expected": spec["v1_expected"],
            "v1_as_predicted": v1 == spec["v1_expected"],
            "v2": v2,
            "v2_ok": v2_ok,
            "v2_predicted": spec["v2_predicted"],
            "v2_as_predicted": v2 == spec["v2_predicted"],
            "rule_fired": r["rule"],
            "rule_predicted": spec["rule_predicted"],
            "rule_as_predicted": r["rule"] == spec["rule_predicted"],
            "hw": r["hw"],
            "month_cols": r["month_cols"],
            "n_num": r["n_num"],
            "v1_miss_direction": miss_direction(v1, gt),
            "v2_miss_direction": miss_direction(v2, gt),
        }

    if hash_failures:
        raise SystemExit("VOID: fixture hash mismatch:\n  " + "\n  ".join(hash_failures))

    repairs = [f for f in ORDER if not rows[f]["v1_ok"] and rows[f]["v2_ok"]]
    regressions = [f for f in ORDER if rows[f]["v1_ok"] and not rows[f]["v2_ok"]]
    shared_misses = [f for f in ORDER if not rows[f]["v1_ok"] and not rows[f]["v2_ok"]]
    fidelity = all(rows[f]["v2_as_predicted"] for f in ORDER)
    rule_fidelity = all(rows[f]["rule_as_predicted"] for f in ORDER)
    v1_fidelity = all(rows[f]["v1_as_predicted"] for f in ORDER)

    fixes_i4 = rows["I4"]["v2"] == "unknown"
    preserves = (
        rows["I1"]["v2"] == "wide"
        and rows["I2"]["v2"] == "long"
        and rows["I3"]["v2"] == "unknown"
    )

    if not fixes_i4:
        outcome = "FAIL_COMPILE"
    elif not preserves:
        outcome = "FAIL_CONTROLS_BROKEN"
    elif not regressions:
        outcome = "CLEAN_COMPILE"
    elif set(regressions) == {"J3"}:
        outcome = "COMPILE_WITH_PREDICTED_COST"
    else:
        outcome = "FAIL_UNPREDICTED_REGRESSION"

    predicted = expected["predicted_totals"]
    v1_correct = sum(1 for f in ORDER if rows[f]["v1_ok"])
    v2_correct = sum(1 for f in ORDER if rows[f]["v2_ok"])

    return {
        "probe": "J",
        "llm_invoked": False,
        "v1_source_sha256": v1_hash,
        "n_fixtures": len(ORDER),
        "per_fixture": rows,
        "v1_correct": v1_correct,
        "v2_correct": v2_correct,
        "repairs": repairs,
        "regressions": regressions,
        "shared_misses": shared_misses,
        "held_out_repairs": [f for f in repairs if rows[f]["set"] == "held_out"],
        "v2_false_refusals": [f for f in ORDER if rows[f]["v2_miss_direction"] == "false_refusal"],
        "v2_false_assertions": [f for f in ORDER if rows[f]["v2_miss_direction"] == "false_assertion"],
        "v1_false_assertions": [f for f in ORDER if rows[f]["v1_miss_direction"] == "false_assertion"],
        "fixes_i4": fixes_i4,
        "preserves_controls": preserves,
        "fidelity": fidelity,
        "rule_fidelity": rule_fidelity,
        "v1_fidelity": v1_fidelity,
        "fidelity_deviations": [
            {
                "fixture": f,
                "predicted": rows[f]["v2_predicted"],
                "actual": rows[f]["v2"],
                "rule_predicted": rows[f]["rule_predicted"],
                "rule_fired": rows[f]["rule_fired"],
            }
            for f in ORDER
            if not (rows[f]["v2_as_predicted"] and rows[f]["rule_as_predicted"])
        ],
        "predicted_totals": predicted,
        "totals_as_predicted": (
            v1_correct == predicted["v1_correct"]
            and v2_correct == predicted["v2_correct"]
            and repairs == predicted["repairs"]
            and regressions == predicted["regressions"]
            and shared_misses == predicted["shared_misses"]
        ),
        "outcome": outcome,
    }


if __name__ == "__main__":
    result = replay()
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if result["outcome"].startswith(("CLEAN", "COMPILE")) else 1)
