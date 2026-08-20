#!/usr/bin/env python3
"""Calibration of `read_authorized_resource`. NO Goose, NO model.

Proves the reader returns exactly the authorized bytes, refuses everything else,
and offers no path, listing, write or shell surface at all.

    python work_interface/authority/selftest_authorized_reader.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
import authorized_reader as R  # noqa: E402
from permission_policy import PermissionPolicy, ALLOW, DENY, KIND_READ, KIND_SHELL  # noqa: E402

WI = HERE.parent
SKILL_R2_SHA = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
FIX_SHA = {
    "supplier_statement": "d0cb95ab5755bef320390f11899c53034548a60678e27430882e556ce1a45feb",
    "ledger_book": "284861d7d948dd6f0cd3a5e7826a6794d15db0ce2aafe108dafa37752c36f25e",
}

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def main() -> int:
    print("=" * 72)
    print("read_authorized_resource -- calibration (no Goose, no model)")
    print("=" * 72)

    tmp = Path(tempfile.mkdtemp(prefix="reader_cal_"))
    run = tmp / "runs" / "N1"
    run.mkdir(parents=True)
    skill_src = WI / "skill" / "r2" / "skill.md"
    (run / "SKILL.md").write_bytes(skill_src.read_bytes())

    print("\n[1] exact text and hashes for all three identifiers")
    got = R.sha256_of("skill", run)
    check(got == SKILL_R2_SHA, "skill -> frozen r2 bytes", got[:16])
    check(R.read_resource("skill", run) ==
          (run / "SKILL.md").read_text(encoding="utf-8"),
          "skill text is byte-identical to the file, untransformed")
    for rid, want in FIX_SHA.items():
        got = R.sha256_of(rid, run)
        check(got == want, f"{rid} -> frozen fixture bytes", got[:16])
        p = R.resource_path(rid, run)
        check(R.read_resource(rid, run) == p.read_text(encoding="utf-8"),
              f"{rid} text is byte-identical to the file, untransformed")
    check(set(R.RESOURCE_IDS) == {"skill", "supplier_statement", "ledger_book"},
          "the identifier set is exactly the three authorized resources",
          str(R.RESOURCE_IDS))

    print("\n[2] unknown identifiers are refused")
    for bad in ["human_answers", "validator", "", "SKILL", "skill ", None, 7,
                "../../w1a/human_answers.md", "skill;ledger_book"]:
        try:
            R.read_resource(bad, run)
            check(False, f"{bad!r} refused")
        except R.UnknownResource:
            check(True, f"{bad!r} refused by name")
        except Exception as e:
            check(False, f"{bad!r} refused", f"wrong exception {type(e).__name__}")

    print("\n[3] there is no path input, so traversal is unrepresentable")
    props = R.INPUT_SCHEMA["properties"]
    check(list(props) == ["resource_id"],
          "the schema has exactly one property", str(list(props)))
    check(props["resource_id"]["enum"] == list(R.RESOURCE_IDS),
          "and it is a closed enum, not a free string")
    check(R.INPUT_SCHEMA.get("additionalProperties") is False,
          "additional properties are rejected by schema")
    for banned in ("path", "file", "source", "dir", "glob", "pattern"):
        check(banned not in props, f"no {banned!r} argument exists")
    # a path-looking value can only ever be an unknown identifier
    try:
        R.read_resource(str(WI / "w1a" / "human_answers.md"), run)
        check(False, "an absolute path as resource_id is refused")
    except R.UnknownResource:
        check(True, "an absolute path as resource_id is just an unknown id")

    print("\n[4] no write route and no shell route -- checked by AST, not prose")
    # A substring scan would match this module's own docstring, which says
    # "no subprocess is spawned, ever". That is exactly the defect that voided
    # W1-D: prose is not code. Inspect the AST.
    import ast
    src = (HERE / "authorized_reader.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for banned in ("subprocess", "os", "shutil", "socket", "urllib", "requests"):
        check(banned not in imported,
              f"the reader imports no {banned!r}", str(sorted(imported)))
    called = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    called |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for banned in ("write_text", "write_bytes", "unlink", "rmdir", "mkdir",
                   "system", "popen", "Popen", "rename", "replace"):
        check(banned not in called,
              f"the reader never calls {banned!r}")
    check("open" not in called, "the reader never calls open()")
    check({"read_text", "read_bytes"} & called == {"read_text", "read_bytes"},
          "it reads, and only reads")
    check("tools/call" in src and "tools/list" in src,
          "it exposes exactly the MCP tool surface and nothing else")
    out = R.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, run)
    names = [t["name"] for t in out["result"]["tools"]]
    check(names == [R.TOOL_NAME], "tools/list offers exactly one tool", str(names))

    print("\n[5] the MCP server responds over stdio")
    proc = subprocess.Popen([sys.executable, str(HERE / "authorized_reader.py"),
                             str(run)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, encoding="utf-8", bufsize=1)
    try:
        def rpc(obj):
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        r = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05"}})
        check("result" in r and r["result"]["serverInfo"]["name"] ==
              "authorized-reader", "initialize handshake", json.dumps(r)[:90])
        r = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        check([t["name"] for t in r["result"]["tools"]] == [R.TOOL_NAME],
              "tools/list over stdio")
        r = rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": R.TOOL_NAME,
                            "arguments": {"resource_id": "skill"}}})
        text = r["result"]["content"][0]["text"]
        check(hashlib.sha256(text.encode("utf-8")).hexdigest() == SKILL_R2_SHA,
              "tools/call returns the exact frozen skill bytes")
        r = rpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": R.TOOL_NAME,
                            "arguments": {"resource_id": "human_answers"}}})
        check(r["result"].get("isError") is True,
              "an unknown identifier returns isError, not content",
              json.dumps(r["result"])[:90])
        r = rpc({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                 "params": {"name": "write_file",
                            "arguments": {"path": "x", "content": "y"}}})
        check(r["result"].get("isError") is True,
              "any other tool name is refused")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print("\n[6] the policy admits the reader and nothing more")
    pol = PermissionPolicy(run,
                           readable=[run / "SKILL.md",
                                     WI / "w1a" / "fixtures" / "supplier-statement.txt",
                                     WI / "w1a" / "fixtures" / "ledger-book.txt"],
                           writable=[run / "work_definition.json"],
                           resource_ids=R.RESOURCE_IDS)
    opts = [{"optionId": "allow_once", "kind": "allow_once"},
            {"optionId": "reject_once", "kind": "reject_once"}]

    def rq(raw):
        return {"params": {"toolCall": {"rawInput": raw}, "options": opts}}

    for rid in R.RESOURCE_IDS:
        d = pol.decide(rq({"resource_id": rid}))
        check(d.verdict == ALLOW and d.kind == KIND_READ,
              f"reader call for {rid!r} is ALLOWED", d.reason)
    d = pol.decide(rq({"resource_id": "human_answers"}))
    check(d.verdict == DENY, "reader call for an unknown id is DENIED", d.reason)
    d = pol.decide(rq({"resource_id": "skill", "path": "/etc/passwd"}))
    check(d.verdict == DENY,
          "a reader call smuggling an extra key is NOT treated as a reader call",
          d.reason)
    d = pol.decide(rq({"command": "type SKILL.md"}))
    check(d.verdict == DENY and d.kind == KIND_SHELL,
          "shell is still denied unconditionally", d.reason)
    d = pol.decide(rq({"path": str(WI / "w1a" / "human_answers.md")}))
    check(d.verdict == DENY, "undeclared reads are still denied", d.reason)

    print("\n[7] the reader still works after a denied shell request")
    denied = pol.decide(rq({"command": 'type "%s"' % (run / "SKILL.md")}))
    check(denied.verdict == DENY, "shell denied first", denied.reason)
    after = pol.decide(rq({"resource_id": "skill"}))
    check(after.verdict == ALLOW,
          "the reader is still ALLOWED afterwards -- a denial carries no state",
          after.reason)
    check(R.sha256_of("skill", run) == SKILL_R2_SHA,
          "and it still returns the exact frozen bytes after the denial")

    print("\n[8] a policy WITHOUT resource_ids is unchanged (W1-E behaviour)")
    old = PermissionPolicy(run, readable=[run / "SKILL.md"],
                           writable=[run / "work_definition.json"])
    d = old.decide(rq({"resource_id": "skill"}))
    check(d.verdict == DENY,
          "packs that do not enable the reader are unaffected", d.reason)

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 72)
    if FAILS:
        print(f"READER CALIBRATION FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("READER CALIBRATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
