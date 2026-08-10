"""Experiment 3B.1-replay — grade the full frozen-G3 replay with the evidence-burden reviewer.

The G3 classifier outputs are frozen (reused verbatim from 3A). Only the six warrant
values are new (from fresh evidence-burden reviewer calls). The gate is 3A's exact
compose() function, imported so there is no logic drift.

Pass criterion: ask_human=true AND warrants for cols 1,2,3,5,6 = supported AND
warrant col 4 = insufficient_evidence.

Usage:
    python replay_grade.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Reuse 3A's gate logic verbatim.
sys.path.insert(0, str((ROOT.parent / "experiment3a" / "harness").resolve()))
from compose import compose as gate_compose  # noqa: E402

JUDGE = ROOT / "judgements" / "G3_replay.json"
RESULTS = ROOT / "results"
EXPECTED = ROOT / "expected.json"


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    judgements = json.loads(JUDGE.read_text(encoding="utf-8"))
    exp_all = json.loads(EXPECTED.read_text(encoding="utf-8"))
    replay_exp = exp_all["probe_3b1_replay"]

    # Build the expected_spec in the shape 3A's compose() expects.
    expected_spec = {
        "expected_header_row": exp_all["fixture"]["header_row"],
        "expected_month_columns_info": replay_exp["expected_gate"]["month_columns"],
        "expected_unknown_columns": replay_exp["expected_gate"]["unknown_columns"],
        "expected_ask_human": replay_exp["expected_gate"]["ask_human"],
        "pass_criteria": replay_exp["pass_criterion"],
    }

    result = gate_compose(judgements, expected_spec)
    result["probe"] = "3B.1-replay"
    result["contract"] = "evidence-burden reviewer (same GLM); classifier outputs frozen from 3A G3"

    # Per-warrant grading against the replay expectation.
    exp_warrants = replay_exp["expected_warrants"]
    per_warrant_ok = {}
    for c in judgements["cells"]:
        ok = c.get("warrant") == exp_warrants[str(c["column"])]
        per_warrant_ok[c["column"]] = {"warrant": c.get("warrant"), "expected": exp_warrants[str(c["column"])], "ok": ok}
    result["per_warrant_ok"] = per_warrant_ok

    all_warrants_ok = all(v["ok"] for v in per_warrant_ok.values())
    gate_ok = result["deterministic_gate"]["ask_human"] is True
    result["replay_passed"] = bool(all_warrants_ok and gate_ok)

    (RESULTS / "G3_replay.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    g = result["deterministic_gate"]
    print(f"[3B.1-replay] gate: months={g['month_columns']} unknown={g['unknown_columns']} ask_human={g['ask_human']}")
    print(f"[3B.1-replay] per-warrant ok: {all_warrants_ok}  gate ask_human=true: {gate_ok}  -> {'PASS' if result['replay_passed'] else 'FAIL'}")
    for col, v in sorted(per_warrant_ok.items()):
        print(f"   col {col}: warrant={v['warrant']} expected={v['expected']} {'ok' if v['ok'] else 'XX'}")
    return 0 if result["replay_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())