"""Experiment 3A — deterministic composition, gate, and grading.

The LLM never constructs the final month-column list. This module takes the
orchestrator's recorded per-cell judgements (transcribed verbatim from subagent
outputs) and produces the gated result by ordinary code.

Gate (authoritative; the orchestrator cannot override it):
    ask_human = any classification == "unknown"
             or any warrant == "insufficient_evidence"
    month_columns = columns where classification == "month" AND warrant == "supported"

For comparison we also compute the *orchestrator's* disposition under the 2B.5 rule
(classification only, no warrant check). Any divergence — orchestrator wants PROCEED
but the gate says ASK_HUMAN — is exactly the contribution the warrant reviewer is meant
to make, and is recorded visibly.

Usage:
    python compose.py <test>            # reads judgements/<test>.json, writes results/<test>.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "judgements"
RESULTS = ROOT / "results"
EXPECTED = ROOT / "expected.json"

VALID_CLASS = {"month", "not_month", "unknown"}
VALID_WARRANT = {"supported", "insufficient_evidence"}


def _norm_class(c):
    return c if c in VALID_CLASS else "unknown"  # parse failure -> conservative escalate


def _norm_warrant(w):
    return w if w in VALID_WARRANT else "insufficient_evidence"  # parse failure -> conservative


def compose(judgements: dict, expected_spec: dict) -> dict:
    test = judgements["test"]
    fixture = judgements["fixture"]
    cells = judgements.get("cells", [])

    located = judgements.get("header_located", False)
    header_row = judgements.get("header_row")

    # Per-cell normalization (parse failures -> conservative direction at the gate).
    per_cell = []
    for c in cells:
        cls = _norm_class(c.get("classification"))
        war = _norm_warrant(c.get("warrant"))
        per_cell.append({
            "column": c["column"],
            "cell": c["cell"],
            "classification": cls,
            "classification_parse_ok": c.get("classification") in VALID_CLASS,
            "warrant": war,
            "warrant_parse_ok": c.get("warrant") in VALID_WARRANT,
        })

    # --- Deterministic gate (with warrant) --- the authoritative result ---
    if not located or header_row is None:
        gate_ask_human = True
        gate_months = []
        gate_unknowns = []
        gate_reason = "header_not_located"
    else:
        gate_unknowns = sorted(
            cc["column"] for cc in per_cell
            if cc["classification"] == "unknown" or cc["warrant"] == "insufficient_evidence"
        )
        gate_months = sorted(
            cc["column"] for cc in per_cell
            if cc["classification"] == "month" and cc["warrant"] == "supported"
        )
        gate_ask_human = bool(gate_unknowns)
        gate_reason = "unknown_or_insufficient_warrant" if gate_ask_human else "all_warranted"

    # --- Orchestrator disposition under the 2B.5 rule (classification only, no warrant) ---
    if not located or header_row is None:
        orch_ask_human = True
        orch_months = []
    else:
        orch_ask_human = any(cc["classification"] == "unknown" for cc in per_cell)
        orch_months = sorted(cc["column"] for cc in per_cell if cc["classification"] == "month")

    # --- Grading against frozen expected ---
    exp = expected_spec
    exp_header = exp["expected_header_row"]
    exp_months = exp["expected_month_columns"] if "expected_month_columns" in exp else exp.get("expected_month_columns_info")
    exp_ask = exp["expected_ask_human"]

    header_ok = (header_row == exp_header)
    if "expected_month_columns" in exp:
        months_ok = (gate_months == exp["expected_month_columns"])
    else:
        months_ok = None  # G3: month set is informational, not a pass criterion
    ask_ok = (gate_ask_human == exp_ask)

    # Test-specific pass criterion.
    if "pass_criteria" in exp and "expected_month_columns" in exp:
        passed = header_ok and months_ok and ask_ok
    else:  # G3
        passed = header_ok and ask_ok

    divergence = (orch_ask_human != gate_ask_human) or (set(orch_months) != set(gate_months))

    return {
        "test": test,
        "fixture": fixture,
        "header_row": header_row,
        "header_located": located,
        "header_row_correct": header_ok,
        "per_cell": per_cell,
        "orchestrator_disposition": {
            "rule": "2B.5 classification-only (no warrant)",
            "month_columns": orch_months,
            "ask_human": orch_ask_human,
        },
        "deterministic_gate": {
            "rule": "classification + warrant; insufficient_evidence or unknown -> ask_human",
            "month_columns": gate_months,
            "unknown_columns": gate_unknowns,
            "ask_human": gate_ask_human,
            "reason": gate_reason,
            "diverges_from_orchestrator": divergence,
        },
        "expected": {
            "header_row": exp_header,
            "month_columns": exp_months,
            "unknown_columns": exp.get("expected_unknown_columns"),
            "ask_human": exp_ask,
        },
        "verdict": {
            "passed": passed,
            "header_ok": header_ok,
            "months_ok": months_ok,
            "ask_human_ok": ask_ok,
            "criterion": exp.get("pass_criteria"),
        },
    }


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: compose.py <test>", file=sys.stderr)
        return 2
    test = argv[1]
    RESULTS.mkdir(exist_ok=True)
    judgements = json.loads((JUDGE / f"{test}.json").read_text(encoding="utf-8"))
    expected_all = json.loads(EXPECTED.read_text(encoding="utf-8"))
    spec = expected_all["tests"][test]

    # Record fixture sha256 for the freeze audit.
    fp = Path(judgements["fixture_path"])
    judgements["fixture_sha256"] = hashlib.sha256(fp.read_bytes()).hexdigest()

    result = compose(judgements, spec)
    result["fixture_sha256"] = judgements["fixture_sha256"]
    result["fixture_sha256_matches_frozen"] = (
        judgements["fixture_sha256"] == expected_all["fixtures"][test]["sha256"]
    )

    (RESULTS / f"{test}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    g = result["deterministic_gate"]
    v = result["verdict"]
    print(f"[{test}] header={result['header_row']} "
          f"months={g['month_columns']} unknown={g['unknown_columns']} "
          f"ask_human={g['ask_human']}  -> {'PASS' if v['passed'] else 'FAIL'}")
    if g["diverges_from_orchestrator"]:
        print(f"  DIVERGENCE: orchestrator wanted "
              f"{result['orchestrator_disposition']['ask_human']=} "
              f"{result['orchestrator_disposition']['month_columns']} ; "
              f"gate overrode -> ask_human={g['ask_human']}")
    return 0 if v["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))