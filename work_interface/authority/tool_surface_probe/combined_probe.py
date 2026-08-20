#!/usr/bin/env python3
"""Coached calibration of the W1-G combined capability box. CALIBRATION ONLY.

Runs in a temp directory outside every W1 pack. Not a W1 run. W1-F and W1-G
evidence are never touched.

Proves, from the ACTUAL provider request rather than from absence of a call,
that attaching the combined server offers the model exactly the two expected
capabilities -- and that both work in one session.

Coached, in order:
    1. read_authorized_resource("skill")
    2. write_work_definition("{}")
    3. write_work_definition("{}")   again -- must refuse, artifact exists

Requirements, all checked mechanically at the end:
    both tools appear SIMULTANEOUSLY in the provider `tools` array
    reader returns the frozen r2 bytes
    writer reaches the permission policy and is ALLOWED
    exactly work_definition.json appears
    a second writer call refuses because the artifact already exists
    no generic builtin write/shell is needed
    if builtins unexpectedly appear, the POLICY denies them -- the guarantee
    must not rest on Goose's suppression quirk
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

LAB = Path(r"C:\Users\pertt\learning-lab")
WI = LAB / "work_interface"
HERE = Path(__file__).resolve().parent
GOOSE = r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe"
R2 = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
W1A = WI / "w1a"
ARTIFACT = "work_definition.json"
PORT = 11599

sys.path.insert(0, str(WI / "authority"))
from permission_policy import PermissionPolicy, choose_option  # noqa: E402
import authorized_capabilities as CAPS  # noqa: E402

# ---------------------------------------------------------------- FROZEN ----
COACHED = [
    'Call read_authorized_resource with resource_id "skill".',
    'Call write_work_definition with content "{}".',
    'Call write_work_definition with content "{}" again.',
]
EXPECTED_TOOLS = {"authorized-capabilities__read_authorized_resource",
                  "authorized-capabilities__write_work_definition"}
# -----------------------------------------------------------------------------

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}"
          + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


class Session:
    def __init__(self) -> None:
        self.acp: list[dict] = []
        self.perms: list[dict] = []
        self.replies: dict[int, dict] = {}
        self.lock = threading.Lock()
        self.nid = [100]
        self.tmp = Path(tempfile.mkdtemp(prefix="w1g_combined_"))
        self.run = self.tmp / "probe"
        self.run.mkdir(parents=True)
        shutil.copyfile(WI / "skill" / "r2" / "skill.md", self.run / "SKILL.md")
        self.tee = HERE / "provider_combined.jsonl"
        if self.tee.exists():
            self.tee.unlink()

    def send(self, o: dict) -> None:
        with self.lock:
            self.acp.append({"dir": "out", "msg": o})
        self.proc.stdin.write(json.dumps(o) + "\n")
        self.proc.stdin.flush()

    def pump(self) -> None:
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            with self.lock:
                self.acp.append({"dir": "in", "msg": m})
                if "id" in m and "method" not in m:
                    self.replies[m["id"]] = m
            if "id" in m and "method" in m:
                if m.get("method") == "session/request_permission":
                    d = self.policy.decide(m)
                    tc = (m.get("params") or {}).get("toolCall") or {}
                    opts = (m.get("params") or {}).get("options") or []
                    with self.lock:
                        self.perms.append({"title": tc.get("title"),
                                           "rawInput": tc.get("rawInput"),
                                           "verdict": d.verdict,
                                           "kind": d.kind,
                                           "reason": d.reason})
                    print(f"    PERMISSION {d.verdict:5s} {d.kind:7s} "
                          f"{str(tc.get('title'))[:46]} -- {d.reason[:52]}")
                    self.send({"jsonrpc": "2.0", "id": m["id"],
                               "result": {"outcome": {
                                   "outcome": "selected",
                                   "optionId": choose_option(opts,
                                                             d.allowed)}}})
                else:
                    self.send({"jsonrpc": "2.0", "id": m["id"],
                               "error": {"code": -32601,
                                         "message": "not offered"}})

    def rq(self, method: str, params: dict, timeout: int = 900):
        self.nid[0] += 1
        i = self.nid[0]
        self.send({"jsonrpc": "2.0", "id": i, "method": method,
                   "params": params})
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if i in self.replies:
                    return self.replies.pop(i)
            if self.proc.poll() is not None:
                return {"error": {"message": "goose exited"}}
            time.sleep(0.2)
        return None

    def offered(self) -> dict:
        seen, first = {}, None
        if not self.tee.exists():
            return {"captured": False, "reason": "no provider traffic"}
        for line in self.tee.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            names = rec.get("tool_names")
            if isinstance(names, list):
                if first is None:
                    first = names
                for n in names:
                    seen[n] = True
        if first is None:
            return {"captured": False, "reason": "no tools array present"}
        return {"captured": True, "first_request": first, "union": sorted(seen)}

    def tool_results(self) -> list[str]:
        out = []
        for e in self.acp:
            up = ((e.get("msg") or {}).get("params") or {}).get("update") or {}
            if up.get("sessionUpdate") == "tool_call_update":
                for c in (up.get("content") or []):
                    blk = c.get("content") if isinstance(c, dict) else None
                    txt = (blk or {}).get("text") if isinstance(blk, dict) else None
                    if txt:
                        out.append(txt)
        return out

    def agent_text(self) -> str:
        return "".join(
            ((e.get("msg") or {}).get("params") or {}).get("update", {})
            .get("content", {}).get("text", "")
            for e in self.acp
            if ((e.get("msg") or {}).get("params") or {})
            .get("update", {}).get("sessionUpdate") == "agent_message_chunk")

    def go(self) -> int:
        print("=" * 72)
        print("W1-G COMBINED CAPABILITY CALIBRATION (coached, temp dir)")
        print("=" * 72)
        print(f"  dir: {self.run}")

        tee = subprocess.Popen(
            [sys.executable, str(HERE / "ollama_tee.py"), str(self.tee),
             str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)

        self.policy = PermissionPolicy(
            self.run,
            readable=[self.run / "SKILL.md",
                      W1A / "fixtures" / "supplier-statement.txt",
                      W1A / "fixtures" / "ledger-book.txt"],
            writable=[self.run / ARTIFACT],
            resource_ids=CAPS.RESOURCE_IDS,
            writer_capability=True)

        env = dict(os.environ)
        env["OLLAMA_HOST"] = f"http://127.0.0.1:{PORT}"
        self.proc = subprocess.Popen(
            [GOOSE, "acp"], cwd=str(self.run), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self.pump, daemon=True).start()

        self.rq("initialize",
                {"protocolVersion": 1,
                 "clientCapabilities": {"fs": {"readTextFile": False,
                                               "writeTextFile": False}}}, 60)
        mcp = [{"name": "authorized-capabilities",
                "command": sys.executable,
                "args": [str(WI / "authority" / "authorized_capabilities.py"),
                         str(self.run)],
                "env": []}]
        r = self.rq("session/new", {"cwd": str(self.run), "mcpServers": mcp},
                    180)
        sid = (r or {}).get("result", {}).get("sessionId")
        if not sid:
            raise SystemExit(f"VOID: no sessionId -> {json.dumps(r)[:300]}")
        print(f"  session: {sid}")
        self.rq("session/set_mode", {"sessionId": sid, "modeId": "approve"}, 60)

        artifact_seen = []
        for i, instruction in enumerate(COACHED, 1):
            print(f"\n  TURN {i}: {instruction}")
            t0 = time.time()
            self.rq("session/prompt",
                    {"sessionId": sid,
                     "prompt": [{"type": "text", "text": instruction}]}, 900)
            print(f"  turn {i} done in {time.time()-t0:.0f}s")
            artifact_seen.append((self.run / ARTIFACT).exists())

        time.sleep(1.0)
        art = self.run / ARTIFACT
        off = self.offered()
        results = self.tool_results()

        print("\n" + "-" * 72)
        print("REQUIREMENTS")
        print("-" * 72)

        if off.get("captured"):
            union = set(off["union"])
            print(f"  tools offered to the model: {off['union']}")
            check(EXPECTED_TOOLS <= union,
                  "both capabilities appear in the provider tools array",
                  str(sorted(EXPECTED_TOOLS & union)))
            first = set(off["first_request"])
            check(EXPECTED_TOOLS <= first,
                  "and BOTH are present SIMULTANEOUSLY in one request",
                  f"{len(first)} tool(s) in the first request")
            extra = union - EXPECTED_TOOLS
            check(not extra, "no other tool is offered",
                  f"unexpected: {sorted(extra)}" if extra else "exactly two")
            if extra:
                # The guarantee must not depend on Goose's suppression quirk.
                print("    builtins unexpectedly present -> verifying POLICY "
                      "denies them:")
                probes = {"shell": {"command": "dir"},
                          "write": {"path": str(self.run / "todo.md"),
                                    "content": "x"},
                          "read": {"path": str(WI / "w1a"
                                               / "human_answers.md")}}
                for label, raw in probes.items():
                    d = self.policy.decide(
                        {"params": {"toolCall": {"rawInput": raw},
                                    "options": []}})
                    check(d.verdict == "DENY",
                          f"policy DENIES a builtin {label} request", d.reason)
        else:
            check(False, "provider tools array captured",
                  str(off.get("reason")))

        skill_hits = [t for t in results
                      if hashlib.sha256(t.encode("utf-8")).hexdigest() == R2]
        check(bool(skill_hits),
              "reader returned the frozen r2 bytes", f"sha256 {R2[:16]}...")

        writes = [p for p in self.perms
                  if set((p.get("rawInput") or {}).keys()) == {"content"}]
        check(bool(writes), "the writer reached the permission policy",
              f"{len(writes)} request(s)")
        check(all(p["verdict"] == "ALLOW" for p in writes),
              "and every writer request was ALLOWED",
              str([p["verdict"] for p in writes]))

        check(art.is_file(), "work_definition.json appears")
        check(art.read_text(encoding="utf-8") == "{}" if art.is_file() else
              False, "with exactly the coached content")
        check(sorted(p.name for p in self.run.iterdir())
              == ["SKILL.md", ARTIFACT],
              "and exactly that file -- nothing else was created",
              str(sorted(p.name for p in self.run.iterdir())))

        refusals = [t for t in results if "already exists" in t]
        check(bool(refusals),
              "the second writer call refused: artifact already exists",
              refusals[0][:70] if refusals else "no refusal observed")

        shellish = [p for p in self.perms
                    if p["kind"] == "SHELL" or "path" in (p.get("rawInput")
                                                          or {})]
        check(not shellish,
              "no generic builtin write/shell was needed at any point",
              str([p["title"] for p in shellish]) if shellish else "none")

        record = {
            "coached": COACHED,
            "offered_tools": off,
            "permissions": self.perms,
            "tool_result_hashes": [
                {"chars": len(t),
                 "sha256": hashlib.sha256(t.encode("utf-8")).hexdigest()[:16],
                 "head": t[:60]} for t in results],
            "artifact_exists_per_turn": artifact_seen,
            "artifact_bytes": art.read_text(encoding="utf-8")
            if art.is_file() else None,
            "run_dir_contents": sorted(p.name for p in self.run.iterdir()),
            "agent_text": self.agent_text(),
            "failures": FAILS,
        }
        (HERE / "combined_record.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        (HERE / "combined_acp.json").write_text(
            json.dumps(self.acp, indent=1, ensure_ascii=False),
            encoding="utf-8")

        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        tee.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)

        print("\n" + "=" * 72)
        if FAILS:
            print(f"COMBINED CALIBRATION FAILED: {len(FAILS)} requirement(s)")
            for f in FAILS:
                print(f"  - {f}")
            return 1
        print("COMBINED CALIBRATION PASSED -- W1-G capability box confirmed")
        return 0


if __name__ == "__main__":
    raise SystemExit(Session().go())
