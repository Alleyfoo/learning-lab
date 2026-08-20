#!/usr/bin/env python3
"""Paired coached ACP tool-surface calibration. CALIBRATION ONLY -- NOT a W1 run.

Runs entirely in a temporary directory outside every W1 pack. W1-F is never
read for mutation, never written, never re-run.

Probe A (control)    no MCP attached
Probe B (treatment)  the exact frozen authorized-reader MCP that W1-F attaches

Everything else is identical between the two: same Goose binary, same
qwen3.5:9b, same ACP client capabilities, same `approve` session mode, same
fail-closed PermissionPolicy (including resource_ids, so the policy object is
byte-for-byte the same in both arms), same coached write instruction.

The ONLY differing input is the `mcpServers` parameter of `session/new`.

Question: does attaching an MCP server change or suppress the builtin tool
surface offered to the model? Absence of a tool call is NOT treated as evidence
of absence of the tool -- that is why the provider traffic is teed.
"""
from __future__ import annotations

import hashlib
import json
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
R2_SHA = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
W1A = WI / "w1a"
ARTIFACT = "work_definition.json"

# ---------------------------------------------------------------- FROZEN ----
# These two strings are the coached instructions. They are frozen before
# execution and are byte-identical between the arms for the write turn.
WRITE_INSTRUCTION = (
    "Use the write tool to create work_definition.json containing {}. "
    "Do not use shell."
)
READER_INSTRUCTION = 'Call read_authorized_resource with resource_id "skill".'
# -----------------------------------------------------------------------------

sys.path.insert(0, str(WI / "authority"))
sys.path.insert(0, str(WI / "harness"))
from permission_policy import PermissionPolicy, choose_option  # noqa: E402
import authorized_reader as READER  # noqa: E402

TOOL_LOG_PORT = 11599


class Probe:
    def __init__(self, arm: str, attach_mcp: bool) -> None:
        self.arm = arm
        self.attach_mcp = attach_mcp
        self.acp: list[dict] = []
        self.perms: list[dict] = []
        self.replies: dict[int, dict] = {}
        self.lock = threading.Lock()
        self.nid = [100]
        self.tmp = Path(tempfile.mkdtemp(prefix=f"toolsurface_{arm}_"))
        self.run = self.tmp / "probe"
        self.run.mkdir(parents=True)
        shutil.copyfile(WI / "skill" / "r2" / "skill.md", self.run / "SKILL.md")
        self.tee_log = HERE / f"provider_{arm}.jsonl"
        if self.tee_log.exists():
            self.tee_log.unlink()

    # -- plumbing ------------------------------------------------------------
    def send(self, obj: dict) -> None:
        with self.lock:
            self.acp.append({"dir": "out", "msg": obj})
        self.proc.stdin.write(json.dumps(obj) + "\n")
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
                    opts = (m.get("params") or {}).get("options") or []
                    tc = (m.get("params") or {}).get("toolCall") or {}
                    with self.lock:
                        self.perms.append({
                            "title": tc.get("title"),
                            "rawInput": tc.get("rawInput"),
                            "verdict": d.verdict, "kind": d.kind,
                            "reason": d.reason})
                    print(f"    PERMISSION {d.verdict:5s} {d.kind:7s} "
                          f"{str(tc.get('title'))[:52]}  -- {d.reason[:60]}")
                    self.send({"jsonrpc": "2.0", "id": m["id"],
                               "result": {"outcome": {
                                   "outcome": "selected",
                                   "optionId": choose_option(opts, d.allowed)}}})
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

    # -- evidence ------------------------------------------------------------
    def agent_text(self) -> str:
        out = []
        for e in self.acp:
            up = ((e.get("msg") or {}).get("params") or {}).get("update") or {}
            if up.get("sessionUpdate") == "agent_message_chunk":
                out.append((up.get("content") or {}).get("text") or "")
        return "".join(out)

    def tool_calls(self) -> list[dict]:
        out = []
        for e in self.acp:
            up = ((e.get("msg") or {}).get("params") or {}).get("update") or {}
            if up.get("sessionUpdate") == "tool_call":
                out.append({"title": up.get("title"),
                            "kind": up.get("kind"),
                            "rawInput": up.get("rawInput")})
        return out

    def offered_tools(self) -> dict:
        """The tool set the provider was actually given. Direct evidence."""
        seen, first = {}, None
        if not self.tee_log.exists():
            return {"captured": False, "reason": "no provider traffic captured"}
        for line in self.tee_log.read_text(encoding="utf-8").splitlines():
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
            return {"captured": False,
                    "reason": "traffic captured but no tools array present"}
        return {"captured": True, "first_request": first,
                "union": sorted(seen), "count_first": len(first)}

    # -- run -----------------------------------------------------------------
    def go(self) -> dict:
        print(f"\n{'='*72}\nPROBE {self.arm}  "
              f"(MCP attached: {self.attach_mcp})\n{'='*72}")
        print(f"  dir: {self.run}")

        tee = subprocess.Popen(
            [sys.executable, str(HERE / "ollama_tee.py"),
             str(self.tee_log), str(TOOL_LOG_PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)

        self.policy = PermissionPolicy(
            self.run,
            readable=[self.run / "SKILL.md",
                      W1A / "fixtures" / "supplier-statement.txt",
                      W1A / "fixtures" / "ledger-book.txt"],
            writable=[self.run / ARTIFACT],
            resource_ids=READER.RESOURCE_IDS)

        import os
        env = dict(os.environ)
        env["OLLAMA_HOST"] = f"http://127.0.0.1:{TOOL_LOG_PORT}"

        self.proc = subprocess.Popen(
            [GOOSE, "acp"], cwd=str(self.run), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self.pump, daemon=True).start()

        self.rq("initialize",
                {"protocolVersion": 1,
                 "clientCapabilities": {"fs": {"readTextFile": False,
                                               "writeTextFile": False}}}, 60)
        params: dict = {"cwd": str(self.run)}
        if self.attach_mcp:
            params["mcpServers"] = [{
                "name": "authorized-reader",
                "command": sys.executable,
                "args": [str(WI / "authority" / "authorized_reader.py"),
                         str(self.run)],
                "env": []}]
        r = self.rq("session/new", params, 180)
        sid = (r or {}).get("result", {}).get("sessionId")
        print(f"  session: {sid}")
        self.rq("session/set_mode", {"sessionId": sid, "modeId": "approve"}, 60)

        turns = []
        print(f"\n  TURN 1 (write): {WRITE_INSTRUCTION}")
        t0 = time.time()
        res = self.rq("session/prompt",
                      {"sessionId": sid,
                       "prompt": [{"type": "text", "text": WRITE_INSTRUCTION}]},
                      900)
        turns.append({"instruction": WRITE_INSTRUCTION,
                      "seconds": round(time.time() - t0),
                      "result": res})
        print(f"  turn 1 done in {time.time()-t0:.0f}s -> "
              f"{json.dumps(res)[:120]}")
        artifact_after_write = (self.run / ARTIFACT).exists()

        if self.attach_mcp:
            print(f"\n  TURN 2 (reader): {READER_INSTRUCTION}")
            t0 = time.time()
            res2 = self.rq("session/prompt",
                           {"sessionId": sid,
                            "prompt": [{"type": "text",
                                        "text": READER_INSTRUCTION}]}, 900)
            turns.append({"instruction": READER_INSTRUCTION,
                          "seconds": round(time.time() - t0),
                          "result": res2})
            print(f"  turn 2 done in {time.time()-t0:.0f}s")

        time.sleep(1.0)
        art = self.run / ARTIFACT
        record = {
            "arm": self.arm,
            "mcp_attached": self.attach_mcp,
            "write_instruction": WRITE_INSTRUCTION,
            "reader_instruction": READER_INSTRUCTION if self.attach_mcp else None,
            "turns": turns,
            "tool_calls": self.tool_calls(),
            "permissions": self.perms,
            "artifact_exists_after_write_turn": artifact_after_write,
            "artifact_exists": art.exists(),
            "artifact_bytes": (art.read_bytes().decode("utf-8", "replace")
                               if art.exists() else None),
            "run_dir_contents": sorted(p.name for p in self.run.iterdir()),
            "offered_tools": self.offered_tools(),
            "agent_text": self.agent_text(),
        }

        (HERE / f"probe_{self.arm}_acp.json").write_text(
            json.dumps(self.acp, indent=1, ensure_ascii=False),
            encoding="utf-8")
        (HERE / f"probe_{self.arm}_record.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")

        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        tee.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)
        return record


def summarize(rec: dict) -> None:
    ot = rec["offered_tools"]
    print(f"\n  -- PROBE {rec['arm']} SUMMARY --")
    print(f"  tool calls made      : "
          f"{[t['title'] for t in rec['tool_calls']]}")
    print(f"  permission decisions : "
          f"{[(p['verdict'], str(p['title'])[:40]) for p in rec['permissions']]}")
    print(f"  {ARTIFACT} created   : {rec['artifact_exists']}")
    if ot.get("captured"):
        print(f"  tools OFFERED to model ({ot['count_first']}): "
              f"{ot['first_request']}")
        print(f"  builtin 'write' offered: "
              f"{any('write' in (n or '') for n in ot['union'])}")
    else:
        print(f"  tools offered        : NOT CAPTURED ({ot.get('reason')})")


def main(argv: list[str]) -> int:
    arms = argv or ["A", "B"]
    out = {}
    for arm in arms:
        rec = Probe(arm, attach_mcp=(arm == "B")).go()
        summarize(rec)
        out[arm] = rec
    print("\n" + "=" * 72)
    print("CALIBRATION EVIDENCE WRITTEN. No W1 run was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
