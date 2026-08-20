#!/usr/bin/env python3
"""Regressions for structured forbidden-path detection. NO Goose, NO model.

The first five cases are driven by the EXACT frozen W1-D evidence that voided
that experiment (`work_interface/w1d/CLOSURE.md`): the real tool updates recorded
in K1/K2/K3's transcripts. They are read, never modified.

    python work_interface/harness/selftest_path_guard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from path_guard import PathGuard, extract_paths, canonicalize  # noqa: E402

LAB = HERE.parent.parent
WI = LAB / "work_interface"
W1D_RUNS = WI / "w1d" / "runs"

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def frozen_updates(run: str) -> list[dict]:
    """Real tool_call / tool_call_update objects from the frozen W1-D transcript."""
    out = []
    p = W1D_RUNS / run / "acp_transcript.jsonl"
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = json.loads(line)
        if m.get("dir") != "in":
            continue
        u = (m.get("msg") or {}).get("params", {}).get("update") or {}
        if u.get("sessionUpdate") in ("tool_call", "tool_call_update"):
            out.append(u)
    return out


def guard_for(run: str) -> PathGuard:
    """The forbidden set W1-D2 will use, expressed as PATHS."""
    run_dir = W1D_RUNS / run
    siblings = [W1D_RUNS / r for r in ("K1", "K2", "K3") if r != run]
    protected = [
        WI / "w1a" / "human_answers.md",
        WI / "work_definition.py",
        WI / "cases",
        WI / "census",
        WI / "fidelity",
        WI / "authority",
        WI / "w1a" / "runs", WI / "w1a2" / "runs", WI / "w1a3" / "runs",
        WI / "w1a4" / "runs", WI / "w1a5" / "runs", WI / "w1b" / "runs",
        WI / "w1c" / "runs",
    ]
    return PathGuard(run_dir, siblings + protected)


def main() -> int:
    print("=" * 72)
    print("STRUCTURED PATH GUARD -- regressions from frozen W1-D evidence")
    print("No Goose, no model. Transcripts are read, never modified.")
    print("=" * 72)

    print("\n[1] the W1-D defect: authorized SKILL.md reads must NOT violate")
    for run in ("K1", "K2", "K3"):
        ups = frozen_updates(run)
        viol = guard_for(run).check_all(ups)
        check(not viol, f"{run}: {len(ups)} real tool updates -> no violation",
              "; ".join(str(v) for v in viol)[:150])

    print("\n[2] the word 'authority' in FILE CONTENT is never matched")
    g = guard_for("K1")
    contenty = {"sessionUpdate": "tool_call_update", "toolCallId": "x",
                "content": [{"type": "content", "content": {"type": "text",
                             "text": "the evidence/authority basis of each "
                                     "load-bearing decision"}}]}
    check(not g.check_all([contenty]),
          "tool_call_update carrying SKILL.md text -> no violation")
    check(extract_paths(contenty) == [],
          "no candidate path is extracted from content at all",
          str(extract_paths(contenty)))

    print("\n[3] K3's TODO prose containing ANALYSIS must NOT violate")
    todo = {"sessionUpdate": "tool_call", "title": "todo: todo write",
            "rawInput": {"content": "## define-lab-process run k3 analysis\n"
                                    "### fixture observation ..."}}
    check(not g.check_all([todo]), "todo write -> no violation")
    check(extract_paths(todo) == [],
          "title and content yield no candidate paths", str(extract_paths(todo)))

    print("\n[4] REAL forbidden path access MUST violate")
    cases = [
        ("sibling run dir", {"sessionUpdate": "tool_call",
                             "rawInput": {"path": str(W1D_RUNS / "K2" / "SKILL.md")}}),
        ("human_answers.md", {"sessionUpdate": "tool_call",
                              "rawInput": {"path": str(WI / "w1a" / "human_answers.md")}}),
        ("validator", {"sessionUpdate": "tool_call",
                       "rawInput": {"path": str(WI / "work_definition.py")}}),
        ("oracle cases", {"sessionUpdate": "tool_call",
                          "rawInput": {"path": str(WI / "cases" / "W0B_corrected.json")}}),
        ("prior pack run", {"sessionUpdate": "tool_call",
                            "rawInput": {"path": str(WI / "w1c" / "runs" / "H1"
                                                     / "work_definition.json")}}),
        ("fidelity instrument", {"sessionUpdate": "tool_call",
                                 "rawInput": {"path": str(WI / "fidelity"
                                                          / "fidelity_check.py")}}),
    ]
    for label, u in cases:
        check(bool(guard_for("K1").check_all([u])), f"{label} -> VIOLATION")

    print("\n[5] shell commands that name a forbidden path MUST violate")
    sh = {"sessionUpdate": "tool_call",
          "rawInput": {"command": 'type "%s"' % (WI / "w1a" / "human_answers.md")}}
    check(bool(guard_for("K1").check_all([sh])),
          "shell naming human_answers.md -> VIOLATION")
    sh_ok = {"sessionUpdate": "tool_call", "rawInput": {"command": "type notes.txt"}}
    check(not guard_for("K1").check_all([sh_ok]),
          "shell reading a local file -> no violation")
    sh_prose = {"sessionUpdate": "tool_call",
                "rawInput": {"command": 'echo "checking authority and fidelity"'}}
    check(not guard_for("K1").check_all([sh_prose]),
          "shell echoing the words authority/fidelity -> no violation")

    print("\n[6] adversarial path formats")
    run_dir = W1D_RUNS / "K1"
    g1 = guard_for("K1")
    # The run dir is <...>/w1d/runs/K1, so reaching work_interface/ needs THREE
    # "..". An earlier draft used two and landed in w1d/w1a/, which is correctly
    # NOT forbidden -- the expectation was wrong, not the guard.
    adversarial = [
        ("windows .. traversal", r"..\..\..\w1a\human_answers.md", True),
        ("posix .. traversal", "../../../w1a/human_answers.md", True),
        ("mixed slashes", "..\\..\\../w1a/human_answers.md", True),
        ("dot-segments", r"..\.\..\.\..\w1a\.\human_answers.md", True),
        ("sibling relative", r"..\K2\work_definition.json", True),
        ("own skill relative", r".\SKILL.md", False),
        ("own skill bare", "SKILL.md", False),
        ("own artifact", "work_definition.json", False),
    ]
    for label, raw, should in adversarial:
        u = {"sessionUpdate": "tool_call", "rawInput": {"path": raw}}
        got = bool(g1.check_all([u]))
        check(got == should,
              f"{label}: {raw!r} -> {'VIOLATION' if should else 'allowed'}",
              canonicalize(raw, run_dir))

    print("\n[7] case-insensitivity on Windows")
    upper = {"sessionUpdate": "tool_call",
             "rawInput": {"path": str(WI / "w1a" / "human_answers.md").upper()}}
    check(bool(g1.check_all([upper])), "upper-cased forbidden path still violates")

    print("\n[8] fields that must never be scanned")
    for field in ("content", "before", "after", "output", "text", "title",
                  "description", "thought"):
        u = {"sessionUpdate": "tool_call_update",
             "rawInput": {field: str(WI / "w1a" / "human_answers.md")}}
        check(not g1.check_all([u]),
              f"a forbidden path appearing in {field!r} is NOT a path reference")

    print("\n" + "=" * 72)
    if FAILS:
        print(f"PATH GUARD REGRESSIONS FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("PATH GUARD REGRESSIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
