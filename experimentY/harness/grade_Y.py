#!/usr/bin/env python3
"""Grade Y by EXECUTION. Naming the right key is not the test.

```text
Y-1  addressed        every accepted claim has a machine-addressable referent
Y-2  decision         A and B proceed; C blocks
Y-3  correct output   the produced model executes to that condition's oracle
Y-4  no needless ask  A and B do not request confirmation of the join binding
Y-5  C resumes        after one human answer, C executes to its oracle
```
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "enrichment" / "harness"))
sys.path.insert(0, str(LAB / "taskmodel"))

import run_Y  # noqa: E402
from execute_enrichment import execute  # noqa: E402
from task_model import parse  # noqa: E402

boundary, w_run = run_Y.boundary, run_Y.w_run
EXPECT_BLOCK = {"A": False, "B": False, "C": True}
JOIN_REFERENTS = {("orders", "item"), ("products", "sku"), ("products", "code"),
                  (("orders", "products"), "item"), (("orders", "products"), None)}


def _rows(model_dict):
    try:
        return execute(parse(model_dict), ROOT).as_dict(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def oracle(cond: str):
    return _rows(json.loads((ROOT / "models" / f"{cond}_oracle.json")
                            .read_text(encoding="utf-8")))[0]["rows"]


def grade_probe(cond: str, tag: str) -> dict:
    out = {"probe": tag, "condition": cond}
    report = json.loads((RESULTS / f"{tag}_stage1_report.json").read_text(encoding="utf-8"))
    llm = [c for c in report if c["status"] in boundary.LLM_STATUSES]
    out["Y1_addressed"] = {"passed": bool(llm) and
                           not [c for c in llm if boundary.referent(c) is None],
                           "llm_claims": len(llm)}

    text2 = (RESULTS / f"{tag}_stage2_model_raw.txt").read_text(encoding="utf-8")
    block, node2 = w_run.block_of(text2), run_Y.node_of(text2)
    blocked = block is not None and node2 is None
    out["Y2_decision"] = {"passed": blocked == EXPECT_BLOCK[cond],
                          "blocked": blocked, "expected_block": EXPECT_BLOCK[cond]}

    if not blocked:
        refs = set()
        result, error = _rows(node2) if node2 else (None, "no model produced")
        out["Y3_correct_output"] = {
            "passed": bool(result) and result["rows"] == oracle(cond)
                      and not result["refused"] and not result["run_refused"],
            "match_right": (node2 or {}).get("lookup", {}).get("match_right"),
            "error": error, "refused": len((result or {}).get("refused", [])),
            "line_totals": [r[-1] for r in (result or {}).get("rows", [])]}
    else:
        refs = {(tuple(b["source"]) if isinstance(b.get("source"), list)
                 else b.get("source"), b.get("field")) for b in block}
        text3 = (RESULTS / f"{tag}_stage3_resume_raw.txt").read_text(encoding="utf-8")
        node3 = run_Y.node_of(text3)
        result, error = _rows(node3) if node3 else (None, "no model after confirmation")
        ok = (bool(result) and result["rows"] == oracle(cond)
              and not result["refused"] and not result["run_refused"])
        out["Y3_correct_output"] = {
            "passed": ok, "match_right": (node3 or {}).get("lookup", {}).get("match_right"),
            "error": error, "line_totals": [r[-1] for r in (result or {}).get("rows", [])]}
        out["Y5_resumes"] = {"passed": ok, "blocked_on": sorted(map(str, refs))}

    if cond in ("A", "B"):
        out["Y4_no_needless_ask"] = {"passed": not (refs & JOIN_REFERENTS),
                                     "asked_about_join": sorted(map(str, refs & JOIN_REFERENTS))}
    return out


def main(argv: list[str]) -> int:
    graded = {}
    for cond in ("A", "B", "C"):
        for p in (1, 2, 3):
            tag = f"{cond}_probe{p}"
            graded[tag] = grade_probe(cond, tag)
    (RESULTS / "graded.json").write_text(
        json.dumps(graded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    keys = ("Y1_addressed", "Y2_decision", "Y3_correct_output",
            "Y4_no_needless_ask", "Y5_resumes")
    print(f"{'probe':11} " + " ".join(f"{k.split('_')[0]:6}" for k in keys) + "  key    totals")
    for tag, g in graded.items():
        row = " ".join(f"{str(g.get(k, {}).get('passed', '-')):6}" for k in keys)
        y3 = g.get("Y3_correct_output", {})
        print(f"{tag:11} {row}  {str(y3.get('match_right')):6} {y3.get('line_totals')}")
    print(f"\noracles: A={oracle('A')[0][-1]},{oracle('A')[1][-1]},{oracle('A')[2][-1]} "
          f"B={oracle('B')[0][-1]},{oracle('B')[1][-1]},{oracle('B')[2][-1]} "
          f"C={oracle('C')[0][-1]},{oracle('C')[1][-1]},{oracle('C')[2][-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
