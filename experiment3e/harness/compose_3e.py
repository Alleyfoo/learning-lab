"""Experiment 3E — deterministic comparison gate + grader.

Replays the 3A G3 chain with:
  - frozen 3A G3 classifier outputs (specialist classifications, NOT re-run)
  - symmetric A/B/C reviewer verdicts (recorded in judgements/3e.json)
  - a deterministic comparison gate (this module; code, not LLM; authoritative)
  - a secondary, non-authoritative orchestrator-disposition comparison

Comparison gate (per column), specialist in {month, not_month}, reviewer in {A,B,C}:
    reviewer == C                              -> HUMAN  (insufficient warrant)
    specialist == month     and reviewer == A  -> ACCEPT month
    specialist == not_month and reviewer == B  -> ACCEPT not_month
    otherwise (disagreement / parse failure)   -> HUMAN

Aggregate:
    month_columns = sorted(columns ACCEPTed as month)
    human_columns = sorted(columns routed to HUMAN)
    ask_human     = bool(human_columns)

Usage:
    python compose_3e.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "judgements" / "3e.json"
RESULTS = ROOT / "results"
EXPECTED = ROOT / "expected.json"

VALID_SPEC = {"month", "not_month"}
VALID_REV = {"A", "B", "C"}


def comparison_gate(specialist: str, reviewer: str) -> tuple[str, str]:
    """Return (disposition, reason). disposition in {accept_month, accept_not_month, human}."""
    spec = specialist if specialist in VALID_SPEC else None
    rev = reviewer if reviewer in VALID_REV else None
    if rev is None or spec is None:
        return ("human", "parse_failure")
    if rev == "C":
        return ("human", "insufficient_warrant")
    if spec == "month" and rev == "A":
        return ("accept_month", "agree_month")
    if spec == "not_month" and rev == "B":
        return ("accept_not_month", "agree_not_month")
    return ("human", "specialist_reviewer_disagreement")


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    data = json.loads(JUDGE.read_text(encoding="utf-8"))
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))

    specialist = {int(k): v["classification"] for k, v in data["frozen_specialist"].items()}
    reviewers = {r["column"]: r.get("established") for r in data["reviewer_verdicts"]}

    exp_reviewer = {int(k): v for k, v in exp["expected_reviewer_verdicts"].items()}
    exp_gate = exp["expected_gate_output"]

    per_column = {}
    for col in sorted(specialist.keys() | reviewers.keys()):
        spec = specialist.get(col)
        rev = reviewers.get(col)
        disp, reason = comparison_gate(spec, rev)
        per_column[col] = {
            "cell": data["frozen_specialist"].get(str(col), {}).get("cell"),
            "specialist": spec,
            "reviewer": rev,
            "specialist_parse_ok": spec in VALID_SPEC,
            "reviewer_parse_ok": rev in VALID_REV,
            "disposition": disp,
            "reason": reason,
        }

    month_columns = sorted(c for c, v in per_column.items() if v["disposition"] == "accept_month")
    human_columns = sorted(c for c, v in per_column.items() if v["disposition"] == "human")
    ask_human = bool(human_columns)

    # --- Reviewer verdict grading ---
    reviewer_ok = {}
    for col in sorted(exp_reviewer.keys()):
        got = reviewers.get(col)
        want = exp_reviewer[col]
        reviewer_ok[col] = {"got": got, "expected": want, "ok": got == want}

    # --- Gate grading ---
    gate_ok = {
        "month_columns": month_columns == exp_gate["month_columns"],
        "human_columns": human_columns == exp_gate["human_columns"],
        "ask_human": ask_human == exp_gate["ask_human"],
    }
    resolvable = {1, 2, 3, 5, 6}
    resolvable_all_accept = all(per_column[c]["disposition"] != "human" for c in resolvable
                                if c in per_column)
    jakso_escalated = (4 in human_columns)

    passed = (ask_human is True and month_columns == exp_gate["month_columns"]
              and human_columns == exp_gate["human_columns"] and resolvable_all_accept
              and jakso_escalated)

    # Decision row
    if passed:
        decision = "PASS_failure_blocked"
    elif ask_human is False:
        decision = "FAIL_fix_did_not_block"
    elif jakso_escalated and not resolvable_all_accept:
        decision = "FAIL_paranoid"
    elif jakso_escalated and month_columns != exp_gate["month_columns"]:
        decision = "FAIL_partial"
    else:
        decision = "FAIL_other"

    # --- Secondary: orchestrator disposition vs gate ---
    orch = data.get("orchestrator_disposition", {})
    orch_month = sorted(orch.get("month_columns", []))
    orch_ask = orch.get("ask_human")
    orch_agrees = (orch_ask == ask_human and orch_month == month_columns)

    result = {
        "probe": "3E",
        "description": "Architectural replay of 3A G3 with frozen specialist + symmetric reviewer + deterministic comparison gate",
        "frozen_specialist_source": data.get("frozen_specialist_source",
                                              "experiment3a/judgements/G3.json (verbatim)"),
        "reviewer_model": "glm-5.2:cloud",
        "reviewer_contract": "symmetric A/B/C (3D framing), no handed proposal",
        "per_column": per_column,
        "gate_output": {
            "month_columns": month_columns,
            "human_columns": human_columns,
            "ask_human": ask_human,
        },
        "expected_gate_output": exp_gate,
        "reviewer_verdict_ok": reviewer_ok,
        "gate_ok": gate_ok,
        "resolvable_all_accept": resolvable_all_accept,
        "jakso_escalated": jakso_escalated,
        "decision": decision,
        "passed": passed,
        "pass_criterion": exp["pass_criterion"],
        "secondary_orchestrator": {
            "orchestrator_ask_human": orch_ask,
            "orchestrator_month_columns": orch_month,
            "gate_ask_human": ask_human,
            "gate_month_columns": month_columns,
            "orchestrator_agrees_with_gate": orch_agrees,
            "non_authoritative": True,
        },
    }
    (RESULTS / "3e.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[3E] per-column gate:")
    for c in sorted(per_column.keys()):
        v = per_column[c]
        print(f"   col {c} {v['cell']:<9} spec={v['specialist']:<9} rev={v['reviewer']!s:<5} -> {v['disposition']:<18} ({v['reason']})")
    g = result["gate_output"]
    print(f"[3E] gate: month_columns={g['month_columns']} human_columns={g['human_columns']} ask_human={g['ask_human']}")
    print(f"[3E] reviewer verdicts ok: {all(v['ok'] for v in reviewer_ok.values())}  "
          f"resolvable_all_accept={resolvable_all_accept}  jakso_escalated={jakso_escalated}")
    print(f"[3E] decision={decision}  passed={passed}")
    orch_s = result["secondary_orchestrator"]
    print(f"[3E] secondary: orchestrator ask_human={orch_s['orchestrator_ask_human']} "
          f"months={orch_s['orchestrator_month_columns']} agrees_with_gate={orch_s['orchestrator_agrees_with_gate']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())