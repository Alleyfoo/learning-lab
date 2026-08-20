#!/usr/bin/env python3
"""ONE coached MCP wiring probe. Temp dir, outside every W1 pack.

Tests AVAILABILITY and INVOCABILITY only -- the instruction names the tool
explicitly, so this says NOTHING about discoverability, which is what W1-F
measures.

Same Goose ACP/provider configuration as W1-F: approve mode, the fail-closed
policy with resource_ids, no client fs capability. The MCP server delegates every
message to the FROZEN authorized_reader.handle(); the wrapper adds logging only,
so the wire behaviour is the frozen module's.

W1-F is not touched, before or after.
"""
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
S = Path(__file__).resolve().parent
GOOSE = r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe"
R2 = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
READER = WI / "authority" / "authorized_reader.py"

sys.path.insert(0, str(WI / "authority"))
sys.path.insert(0, str(WI / "harness"))
from permission_policy import PermissionPolicy, choose_option  # noqa: E402
import authorized_reader as R  # noqa: E402

MCP_LOG = S / "w1f_probe_mcp.log"
if MCP_LOG.exists():
    MCP_LOG.unlink()

tmp = Path(tempfile.mkdtemp(prefix="w1f_wiring_"))
run = tmp / "probe"
run.mkdir(parents=True)
shutil.copyfile(WI / "skill" / "r2" / "skill.md", run / "SKILL.md")

policy = PermissionPolicy(
    run,
    readable=[run / "SKILL.md",
              WI / "w1a" / "fixtures" / "supplier-statement.txt",
              WI / "w1a" / "fixtures" / "ledger-book.txt"],
    writable=[run / "work_definition.json"],
    resource_ids=R.RESOURCE_IDS)

acp_log, perms, lock = [], [], threading.Lock()
replies, updates = {}, []

proc = subprocess.Popen([GOOSE, "acp"], cwd=str(run),
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True,
                        encoding="utf-8", bufsize=1)


def send(o):
    with lock:
        acp_log.append({"dir": "out", "msg": o})
    proc.stdin.write(json.dumps(o) + "\n")
    proc.stdin.flush()


def reader_thread():
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        with lock:
            acp_log.append({"dir": "in", "msg": m})
            if "id" in m and "method" not in m:
                replies[m["id"]] = m
            elif "method" in m:
                updates.append(m)
        if "id" in m and "method" in m:
            if m.get("method") == "session/request_permission":
                d = policy.decide(m)
                opts = (m.get("params") or {}).get("options") or []
                oid = choose_option(opts, d.allowed)
                tc = (m.get("params") or {}).get("toolCall") or {}
                with lock:
                    perms.append({"title": tc.get("title"),
                                  "rawInput": tc.get("rawInput"),
                                  "verdict": d.verdict, "kind": d.kind,
                                  "reason": d.reason})
                print(f"  PERMISSION {d.verdict:5s} {d.kind:7s} "
                      f"{str(tc.get('title'))[:56]}  -- {d.reason}")
                send({"jsonrpc": "2.0", "id": m["id"],
                      "result": {"outcome": {"outcome": "selected",
                                             "optionId": oid}}})
            else:
                send({"jsonrpc": "2.0", "id": m["id"],
                      "error": {"code": -32601, "message": "not offered"}})


threading.Thread(target=reader_thread, daemon=True).start()
nid = [100]


def rq(method, params, timeout=600):
    nid[0] += 1
    i = nid[0]
    send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
    end = time.time() + timeout
    while time.time() < end:
        with lock:
            if i in replies:
                return replies.pop(i)
        if proc.poll() is not None:
            return {"error": {"message": "goose exited"}}
        time.sleep(0.2)
    return None


print(f"probe dir: {run}")
print(f"frozen reader sha256: {hashlib.sha256(READER.read_bytes()).hexdigest()[:16]}")
rq("initialize", {"protocolVersion": 1,
                  "clientCapabilities": {"fs": {"readTextFile": False,
                                                "writeTextFile": False}}}, 60)
mcp = [{"name": "authorized-reader", "command": sys.executable,
        "args": [str(S / "mcp_tee.py"), str(MCP_LOG), str(run)], "env": []}]
r = rq("session/new", {"cwd": str(run), "mcpServers": mcp}, 180)
sid = (r or {}).get("result", {}).get("sessionId")
print("session/new:", sid or json.dumps(r)[:200])
rq("session/set_mode", {"sessionId": sid, "modeId": "approve"}, 60)

PROMPT = ('Call read_authorized_resource with resource_id "skill" and report '
          'whether the call succeeded. Do not use any other tool.')
print("\ncoached prompt sent; awaiting turn...\n")
t0 = time.time()
res = rq("session/prompt", {"sessionId": sid,
                            "prompt": [{"type": "text", "text": PROMPT}]}, 900)
print(f"\nturn returned in {time.time()-t0:.0f}s: {json.dumps(res)[:220]}")

time.sleep(1.0)
(S / "w1f_probe_acp.json").write_text(json.dumps(acp_log, indent=1,
                                                 ensure_ascii=False),
                                      encoding="utf-8")
(S / "w1f_probe_permissions.json").write_text(json.dumps(perms, indent=1,
                                                         ensure_ascii=False),
                                              encoding="utf-8")
print(f"\nacp messages: {len(acp_log)}   permission decisions: {len(perms)}")
print(f"run dir contents: {sorted(p.name for p in run.iterdir())}")
proc.terminate()
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
shutil.rmtree(tmp, ignore_errors=True)
