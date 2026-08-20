#!/usr/bin/env python3
"""Offline calibration of the W1-G capability box. No model, no network.

Establishes, mechanically, that the worker's entire capability surface is two
verbs and that neither can be widened by any argument.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import authorized_capabilities as C  # noqa: E402
from permission_policy import PermissionPolicy, ALLOW, DENY  # noqa: E402

WI = HERE.parent
R2 = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}"
          + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def fixture_run_dir() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="w1g_caps_"))
    run = tmp / "O1"
    run.mkdir(parents=True)
    shutil.copyfile(WI / "skill" / "r2" / "skill.md", run / "SKILL.md")
    return run


def main() -> int:
    print("[1] the capability box is exactly two verbs")
    names = [t["name"] for t in C.TOOLS]
    check(names == ["read_authorized_resource", "write_work_definition"],
          "exactly two tools, in order", str(names))

    print("\n[2] the writer takes content only -- no path is representable")
    props = C.WRITE_INPUT_SCHEMA["properties"]
    check(list(props) == ["content"], "one argument", str(list(props)))
    check(props["content"]["type"] == "string",
          "content is a string, not a parsed object "
          "(malformed JSON must reach the structural gate)")
    check(C.WRITE_INPUT_SCHEMA.get("additionalProperties") is False,
          "additional properties are rejected")
    check(C.WRITE_INPUT_SCHEMA.get("required") == ["content"],
          "content is required")
    for banned in ("path", "file", "filename", "destination", "dir", "target",
                   "mode", "append", "encoding"):
        check(banned not in props, f"no {banned!r} argument exists")

    print("\n[3] the server imports no execution or filesystem-walk route")
    src = (HERE / "authorized_capabilities.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for banned in ("subprocess", "os", "shutil", "glob", "socket", "requests"):
        check(banned not in imported, f"does not import {banned}")
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check("eval" not in called and "exec" not in called, "no eval/exec")
    check("open" in called, "opens exactly one file -- the fixed destination",
          "the writer's only side effect")
    check(src.count("open(") == 1, "and `open` appears exactly once")

    print("\n[4] the writer writes verbatim, to the fixed destination")
    run = fixture_run_dir()
    try:
        payload = '{"work_definition_version": 0, "x": "\u00e4\u00f6 \\n"}'
        info = C.write_work_definition(payload, run)
        art = run / "work_definition.json"
        check(art.is_file(), "work_definition.json created")
        check(art.read_text(encoding="utf-8") == payload,
              "content is byte-identical -- no reformatting")
        check(info["bytes"] == len(payload.encode("utf-8")),
              "reported byte count is the UTF-8 length")
        check(sorted(p.name for p in run.iterdir())
              == ["SKILL.md", "work_definition.json"],
              "no other file was created")

        print("\n[5] single-shot: a second call refuses, and does not mutate")
        before = art.read_text(encoding="utf-8")
        try:
            C.write_work_definition('{"second": true}', run)
            check(False, "second write must refuse")
        except C.WriteRefused as e:
            check("already exists" in str(e), "second write refused by name",
                  str(e)[:70])
        check(art.read_text(encoding="utf-8") == before,
              "the existing artifact is untouched by the refusal")

        print("\n[6] malformed JSON is written unchanged, never repaired")
        run2 = fixture_run_dir()
        broken = '{"unterminated": '
        C.write_work_definition(broken, run2)
        check((run2 / "work_definition.json").read_text(encoding="utf-8")
              == broken,
              "malformed payload survives verbatim to the structural gate")
        try:
            json.loads(broken)
            check(False, "the payload really is malformed")
        except json.JSONDecodeError:
            check(True, "the payload really is malformed")

        print("\n[7] non-string content is refused")
        run3 = fixture_run_dir()
        for bad in ({"a": 1}, 5, None, ["x"]):
            try:
                C.write_work_definition(bad, run3)
                check(False, f"must refuse {type(bad).__name__}")
            except C.WriteRefused:
                check(True, f"refuses {type(bad).__name__} content")
        check(not (run3 / "work_definition.json").exists(),
              "and no file is created by a refused write")

        print("\n[8] the reader is unchanged -- frozen bytes, unknown ids refused")
        run4 = fixture_run_dir()
        check(C.sha256_of("skill", run4) == R2, "skill is the frozen r2 skill")
        for rid in C.RESOURCE_IDS:
            check(isinstance(C.read_resource(rid, run4), str)
                  and C.read_resource(rid, run4) != "",
                  f"{rid} returns text")
        for bad in ("human_answers", "work_definition.json", "../etc/passwd"):
            try:
                C.read_resource(bad, run4)
                check(False, f"must refuse {bad!r}")
            except C.UnknownResource:
                check(True, f"refuses unknown resource_id {bad!r}")

        print("\n[9] the stdio MCP surface offers both, and only both")
        proc = subprocess.Popen(
            [sys.executable, str(HERE / "authorized_capabilities.py"),
             str(run4)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        try:
            def rpc(obj):
                proc.stdin.write(json.dumps(obj) + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-11-25"}})
            check(init["result"]["serverInfo"]["name"]
                  == "authorized-capabilities", "handshake identifies server")
            listed = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                          "params": {}})
            got = [t["name"] for t in listed["result"]["tools"]]
            check(got == ["read_authorized_resource", "write_work_definition"],
                  "tools/list offers exactly the two verbs", str(got))
            call = rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "write_work_definition",
                                   "arguments": {"content": "{}"}}})
            check("wrote" in call["result"]["content"][0]["text"],
                  "writer works over the wire")
            again = rpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                         "params": {"name": "write_work_definition",
                                    "arguments": {"content": "{}"}}})
            check(again["result"].get("isError") is True,
                  "and refuses the second call over the wire")
            unknown = rpc({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "shell",
                                      "arguments": {"command": "dir"}}})
            check(unknown["result"].get("isError") is True,
                  "an unknown tool name is refused, not executed")
        finally:
            proc.terminate()

        print("\n[10] policy: the writer clause is opt-in and cannot be widened")

        def rq(raw):
            return {"params": {"toolCall": {"rawInput": raw},
                               "options": [
                                   {"optionId": "allow_once",
                                    "kind": "allow_once"},
                                   {"optionId": "reject_once",
                                    "kind": "reject_once"}]}}

        off = PermissionPolicy(run4, readable=[run4 / "SKILL.md"],
                               writable=[run4 / "work_definition.json"],
                               resource_ids=C.RESOURCE_IDS)
        check(off.decide(rq({"content": "{}"})).verdict == DENY,
              "with the capability OFF the writer call is DENIED "
              "(W1-E/W1-F policies unchanged)")

        on = PermissionPolicy(run4, readable=[run4 / "SKILL.md"],
                              writable=[run4 / "work_definition.json"],
                              resource_ids=C.RESOURCE_IDS,
                              writer_capability=True)
        d = on.decide(rq({"content": "{}"}))
        check(d.verdict == ALLOW and d.kind == "WRITE",
              "with it ON the writer call is ALLOWED", d.reason)
        check(on.decide(rq({"resource_id": "skill"})).verdict == ALLOW,
              "the reader still works alongside it")

        print("\n     and the fail-closed floor still holds with it ON:")
        check(on.decide(rq({"command": "powershell -c dir"})).verdict == DENY,
              "shell is STILL denied unconditionally")
        check(on.decide(rq({"content": "{}", "path": "C:/other.json"})).verdict
              == DENY,
              "content + a path does NOT reach the writer clause")
        check(on.decide(rq({"content": 5})).verdict == DENY,
              "non-string content is denied")
        check(on.decide(rq({"path": str(WI / "w1a" / "human_answers.md")}))
              .verdict == DENY, "undeclared reads are STILL denied")
        check(on.decide(rq({"path": str(run4 / "todo.md"), "content": "x"}))
              .verdict == DENY, "arbitrary writes are STILL denied")
        check(on.decide(rq({})).verdict == DENY, "an empty rawInput is denied")
    finally:
        for d in (run, run4):
            shutil.rmtree(d.parent, ignore_errors=True)

    print("\n" + "=" * 70)
    if FAILS:
        print(f"CAPABILITY BOX CALIBRATION FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("CAPABILITY BOX CALIBRATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
