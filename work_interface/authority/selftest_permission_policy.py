#!/usr/bin/env python3
"""Fail-closed permission policy self-test. NO Goose, NO model.

Requests are built in the EXACT wire shape recorded by the A1 calibration
(`a1_calibration/FINDINGS.md`), including the real four-option list.

    python work_interface/authority/selftest_permission_policy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from permission_policy import (PermissionPolicy, choose_option,  # noqa: E402
                               ALLOW, DENY, KIND_READ, KIND_WRITE,
                               KIND_SHELL, KIND_UNKNOWN)

WI = HERE.parent
RUN = WI / "w1e" / "runs" / "M1"
SKILL = RUN / "SKILL.md"
ART = RUN / "work_definition.json"
FIX1 = WI / "w1a" / "fixtures" / "supplier-statement.txt"
FIX2 = WI / "w1a" / "fixtures" / "ledger-book.txt"

OPTIONS = [{"optionId": "allow_always", "name": "allow_always", "kind": "allow_always"},
           {"optionId": "allow_once", "name": "allow_once", "kind": "allow_once"},
           {"optionId": "reject_once", "name": "reject_once", "kind": "reject_once"},
           {"optionId": "reject_always", "name": "reject_always", "kind": "reject_always"}]

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def req(raw: dict, title: str = "t") -> dict:
    return {"jsonrpc": "2.0", "id": "abc", "method": "session/request_permission",
            "params": {"sessionId": "s1",
                       "toolCall": {"toolCallId": "c1", "kind": "other",
                                    "status": "pending", "title": title,
                                    "rawInput": raw},
                       "options": OPTIONS}}


def main() -> int:
    print("=" * 72)
    print("FAIL-CLOSED PERMISSION POLICY -- self-test (no Goose, no model)")
    print("=" * 72)
    P = PermissionPolicy(RUN, readable=[SKILL, FIX1, FIX2], writable=[ART])

    print("\n[1] the three ALLOW clauses")
    for label, raw in [
        ("read authorized SKILL.md", {"path": str(SKILL)}),
        ("read fixture 1", {"path": str(FIX1)}),
        ("read fixture 2", {"path": str(FIX2)}),
        ("read via 'source' field", {"source": str(SKILL)}),
        ("relative read of own SKILL.md", {"path": "SKILL.md"}),
    ]:
        d = P.decide(req(raw))
        check(d.verdict == ALLOW and d.kind == KIND_READ, label, d.reason)
    d = P.decide(req({"path": str(ART), "content": '{"ok": true}'}))
    check(d.verdict == ALLOW and d.kind == KIND_WRITE,
          "write the designated artifact", d.reason)

    print("\n[2] shell is denied unconditionally")
    for label, raw in [
        ("harmless read via shell", {"command": "type SKILL.md"}),
        ("the L1 recovery route", {"command": 'type "%s"' % SKILL}),
        ("powershell read", {"command": "powershell -Command \"Get-Content -Raw '%s'\"" % FIX1}),
        ("shell writing the artifact", {"command": 'echo {} > "%s"' % ART}),
    ]:
        d = P.decide(req(raw))
        check(d.verdict == DENY and d.kind == KIND_SHELL, label, d.reason)

    print("\n[3] arbitrary writes are denied")
    for label, raw in [
        ("write todo.md (the L3 shape)", {"path": str(RUN / "todo.md"),
                                          "content": "notes"}),
        ("write temp_skill.txt (the H2 shape)", {"path": str(RUN / "temp_skill.txt"),
                                                 "content": "x"}),
        ("edit SKILL.md", {"path": str(SKILL), "content": "tampered"}),
        ("edit via after-payload", {"path": str(SKILL), "after": "tampered"}),
    ]:
        d = P.decide(req(raw))
        check(d.verdict == DENY and d.kind == KIND_WRITE, label, d.reason)

    print("\n[4] reads of undeclared resources are denied")
    for label, raw in [
        ("human_answers.md", {"path": str(WI / "w1a" / "human_answers.md")}),
        ("the validator", {"path": str(WI / "work_definition.py")}),
        ("a sibling run", {"path": str(WI / "w1e" / "runs" / "M2" / "SKILL.md")}),
        ("prior pack output", {"path": str(WI / "w1d2" / "runs" / "L1"
                                           / "work_definition.json")}),
        ("traversal to the answer file", {"path": r"..\..\..\w1a\human_answers.md"}),
    ]:
        d = P.decide(req(raw))
        check(d.verdict == DENY and d.kind == KIND_READ, label, d.reason)

    print("\n[5] unknown / unparseable requests are denied")
    for label, r in [
        ("no rawInput", {"jsonrpc": "2.0", "id": "x",
                         "method": "session/request_permission",
                         "params": {"toolCall": {"title": "t"}, "options": OPTIONS}}),
        ("no params", {"jsonrpc": "2.0", "id": "x",
                       "method": "session/request_permission"}),
        ("rawInput with no path at all", req({"foo": "bar"})),
        ("two path fields", req({"path": str(SKILL), "destination": str(ART)})),
        ("empty path", req({"path": "   "})),
    ]:
        d = P.decide(r)
        check(d.verdict == DENY and d.kind == KIND_UNKNOWN, label, d.reason)

    print("\n[6] title and prose can never grant permission")
    d = P.decide(req({"command": "type SKILL.md"},
                     title="read · SKILL.md (authorized)"))
    check(d.verdict == DENY, "an allow-sounding title does not allow a shell call",
          d.reason)
    d = P.decide(req({"path": str(WI / "w1a" / "human_answers.md")},
                     title="read · SKILL.md"))
    check(d.verdict == DENY, "a misleading title does not allow a forbidden read",
          d.reason)

    print("\n[7] option selection uses the agent's own offered options")
    check(choose_option(OPTIONS, True) == "allow_once",
          "allow -> allow_once, never allow_always")
    check(choose_option(OPTIONS, False) == "reject_once",
          "deny -> reject_once, never reject_always")
    check(choose_option([], True) is None,
          "no options offered -> no identifier is invented")

    print("\n[8] the policy teaches nothing")
    src = (HERE / "permission_policy.py").read_text(encoding="utf-8")
    for banned in ("read_image", "text_editor", "developer", "use tool",
                   "instead try"):
        check(banned not in src.lower(),
              f"policy source never names a tool or a route ({banned!r})")

    print("\n" + "=" * 72)
    if FAILS:
        print(f"PERMISSION POLICY SELF-TEST FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("PERMISSION POLICY SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
