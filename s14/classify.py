#!/usr/bin/env python3
"""S14 classification worksheet generator.

Reads the per-rep run.json files and emits:
  - classification_worksheet.md : one row per session with the verbatim
    tool_invocations, route_chosen, the frozen expected route/tool, and a
    route_correct slot pre-filled with the AUTO hint (route_chosen == expected).
    The auto hint is NON-authoritative (mirrors S13); the human verdict is
    written into FINDINGS.md.
  - summary.json : per-cell route distribution + auto route_correct rate +
    lifecycle/canary pass rates + cross-cell aggregates.

Run:  python s14/classify.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(LAB / "supervisor"))

ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
CELLS = ORACLE["cells"]
CELL_NAMES = [c["cell"] for c in CELLS]
CELL_BY_NAME = {c["cell"]: c for c in CELLS}
N_REPS = ORACLE["run"]["replicates_per_cell"]

ROUTE_TOOL_TO_ROUTE = {
    "file_measurement": "MEASUREMENT", "file_skill": "SKILL_WORKFLOW",
    "file_duplicate_rule": "DUPLICATE_RULE", "propose_rule": "NEW_RULE",
    "reject_conflict": "REJECT_CONFLICT",
}


def _load_reps() -> dict:
    reps = {}
    for cell in CELL_NAMES:
        reps[cell] = []
        for rep in range(1, N_REPS + 1):
            p = RESULTS / cell / f"{rep:02d}" / "run.json"
            if p.exists():
                reps[cell].append(json.loads(p.read_text(encoding="utf-8")))
            else:
                reps[cell].append(None)
    return reps


def _auto_route_correct(rec: dict) -> bool:
    if rec is None:
        return False
    return rec.get("route_chosen") == rec.get("expected_tool")


def _summarize_route(rec) -> str:
    """Compress tool_invocations into one readable line."""
    if rec is None:
        return "(missing)"
    parts = []
    for inv in rec.get("tool_invocations", []):
        t = inv["tool"]
        ok = "ok" if inv["ok"] else "FAIL"
        # one key arg hint
        arg = ""
        a = inv.get("args", {})
        if t == "file_measurement":
            arg = f'metric={a.get("metric")!r}'
        elif t == "file_skill":
            arg = f'procedure={a.get("procedure")!r}'
        elif t == "file_duplicate_rule":
            arg = f'restates={a.get("restated_rule")!r}'
        elif t == "reject_conflict":
            arg = f'conflicts={a.get("conflicts_with")!r}'
        elif t == "propose_rule":
            arg = f'evidence={a.get("evidence")!r}'
        elif t == "approve_rule":
            arg = f'id={a.get("rule_id")!r}'
        parts.append(f"{t}({arg})[{ok}]")
    return " ; ".join(parts) if parts else "(no tool calls)"


def _worksheet(reps: dict) -> str:
    lines = []
    lines.append("# S14 — routing classification worksheet")
    lines.append("")
    lines.append("One row per session. `route_chosen` is the filing tool the model "
                 "called; `expected` is the frozen ground truth. `auto_correct` is "
                 "the NON-authoritative hint (route_chosen == expected_tool). The "
                 "human verdict (route_correct + sub-outcome notes) goes in "
                 "FINDINGS.md. Tool calls are compressed: tool(keyarg)[ok|FAIL].")
    lines.append("")
    for cell in CELL_NAMES:
        c = CELL_BY_NAME[cell]
        lines.append(f"## {cell}  — expected route {c['expected_route']} "
                     f"({c['expected_tool']}); emergence {c['emergence_count']}")
        lines.append("")
        for i, rec in enumerate(reps[cell], 1):
            if rec is None:
                lines.append(f"- rep{i:02d}: MISSING (not run / errored)")
                continue
            rc = rec.get("route_chosen")
            auto = _auto_route_correct(rec)
            lines.append(
                f"- rep{i:02d}: route_chosen={rc}  expected={rec.get('expected_tool')}  "
                f"auto_correct={auto}")
            lines.append(f"    calls: {_summarize_route(rec)}")
            lines.append(
                f"    sub: restated={rec.get('restated_rule_named')}  "
                f"conflicts={rec.get('conflicts_named')}  "
                f"compatible={rec.get('compatible_flag')}  "
                f"evidence={rec.get('evidence_cited')!r}")
            lines.append(
                f"    life: reached_proposed={rec.get('reached_proposed')}  "
                f"reached_active={rec.get('reached_active')}  "
                f"called_approve_rule={rec.get('called_approve_rule')}  "
                f"stop={rec.get('stop_reason')}  ollama_calls={rec.get('ollama_call_count')}")
            ni = rec.get("canary_no_interpretation")
            lines.append(f"    canary: no_interpretation={ni}"
                         + (f"  bad={rec.get('canary_no_interpretation_bad')}" if not ni else ""))
        lines.append("")
    return "\n".join(lines) + "\n"


def _summary(reps: dict) -> dict:
    s = {"schema": "supervisor.s14.summary/v1", "cells": {}, "overall": {}}
    all_correct = []
    all_present = 0
    for cell in CELL_NAMES:
        rs = [r for r in reps[cell] if r is not None]
        n = len(rs)
        routes = {}
        correct = 0
        proposed = 0
        active = 0
        approve_called = 0
        no_interp_ok = 0
        for r in rs:
            rc = r.get("route_chosen")
            routes[rc] = routes.get(rc, 0) + 1
            if _auto_route_correct(r):
                correct += 1
            if r.get("reached_proposed"):
                proposed += 1
            if r.get("reached_active"):
                active += 1
            if r.get("called_approve_rule"):
                approve_called += 1
            if r.get("canary_no_interpretation"):
                no_interp_ok += 1
        s["cells"][cell] = {
            "expected_route": CELL_BY_NAME[cell]["expected_route"],
            "expected_tool": CELL_BY_NAME[cell]["expected_tool"],
            "n_present": n,
            "route_distribution": routes,
            "auto_route_correct": correct,
            "auto_route_correct_rate": (correct / n) if n else None,
            "reached_proposed": proposed,
            "reached_active": active,
            "called_approve_rule": approve_called,
            "no_interpretation_ok": no_interp_ok,
        }
        all_correct.append(correct)
        all_present += n
    s["overall"] = {
        "n_present": all_present,
        "n_expected": N_REPS * len(CELL_NAMES),
        "auto_route_correct_total": sum(all_correct),
        "auto_route_correct_rate": (sum(all_correct) / all_present) if all_present else None,
        "headline_test": {
            "measurement_routed_to_measurement_not_new_rule":
                s["cells"]["measurement"]["route_distribution"].get("file_measurement", 0)
                - s["cells"]["measurement"]["route_distribution"].get("propose_rule", 0),
            "only_new_rule_reaches_active":
                s["cells"]["new_rule"]["reached_active"]
                and not any(s["cells"][c]["reached_active"]
                            for c in CELL_NAMES if c != "new_rule"),
            "conflicting_probe_never_active":
                s["cells"]["conflicting_probe"]["reached_active"] == 0,
            "mirror_routed_to_duplicate_not_new_rule":
                s["cells"]["compatible_mirror_probe"]["route_distribution"]
                .get("file_duplicate_rule", 0)
                - s["cells"]["compatible_mirror_probe"]["route_distribution"]
                .get("propose_rule", 0),
        },
    }
    return s


def main() -> int:
    reps = _load_reps()
    (RESULTS / "classification_worksheet.md").write_text(
        _worksheet(reps), encoding="utf-8")
    summary = _summary(reps)
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote classification_worksheet.md + summary.json")
    print(f"  sessions present: {summary['overall']['n_present']}/{summary['overall']['n_expected']}")
    for cell in CELL_NAMES:
        cs = summary["cells"][cell]
        print(f"  {cell:<26} n={cs['n_present']}  routes={cs['route_distribution']}  "
              f"auto_correct={cs['auto_route_correct']}/{cs['n_present']}  "
              f"proposed={cs['reached_proposed']} active={cs['reached_active']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())