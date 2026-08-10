"""Experiment 3B.1 — grade the isolated evidence-burden reviewer test.

Reads judgements/3b1.json (the three recorded reviewer outputs, transcribed
verbatim from the agent calls) and grades against the preregistered decision
table. The pass criterion is the first row only: both controls `supported`
AND the target `insufficient_evidence`.

Usage:
    python grade_3b1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "judgements" / "3b1.json"
RESULTS = ROOT / "results"

VALID = {"supported", "insufficient_evidence"}


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    data = json.loads(JUDGE.read_text(encoding="utf-8"))
    props = {p["id"]: p for p in data["propositions"]}

    def w(pid: str) -> str:
        v = props[pid].get("warrant")
        return v if v in VALID else f"INVALID({v!r})"

    c1, c2, t = w("C1"), w("C2"), w("T")
    parse_ok = all(props[p["id"]].get("warrant") in VALID for p in data["propositions"])

    # Decision table (frozen in preregistration / expected.json).
    if c1 == "supported" and c2 == "supported" and t == "insufficient_evidence":
        row, action, passed = "policy_fix_works", "run 3B.1-replay", True
    elif c1 == "supported" and c2 == "supported" and t == "supported":
        row, action, passed = "still_overconfident", "run 3B.2", False
    elif c1 == "insufficient_evidence" and c2 == "insufficient_evidence" and t == "insufficient_evidence":
        row, action, passed = "paranoid", "run 3B.2", False
    elif c1 == "supported" and c2 != "supported":
        row, action, passed = "control_broken_non_month_direction", "inspect contract", False
    elif c2 == "supported" and c1 != "supported":
        row, action, passed = "control_broken_month_direction", "inspect contract", False
    else:
        row, action, passed = "ambiguous_mix", "inspect trace", False

    result = {
        "probe": "3B.1",
        "contract": "evidence-burden reviewer (same GLM, agent tool)",
        "propositions": data["propositions"],
        "pattern": {"C1_Tammi": c1, "C2_Tuote": c2, "T_JaksoA": t},
        "all_parse_ok": parse_ok,
        "decision_row": row,
        "passed": passed,
        "next_action": action,
        "pass_criterion": "C1=supported AND C2=supported AND T=insufficient_evidence",
    }
    (RESULTS / "3b1.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[3B.1] C1 Tammi=month      -> {c1}")
    print(f"[3B.1] C2 Tuote=not_month  -> {c2}")
    print(f"[3B.1] T  Jakso A=not_month -> {t}")
    print(f"[3B.1] decision_row={row}  passed={passed}  next={action}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())