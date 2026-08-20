#!/usr/bin/env python3
"""A1 -- ACP permission-channel calibration. ONE isolated model probe.

Temporary directory, outside every experiment pack. Establishes the ACTUAL wire
behaviour of `session/set_mode = approve`. Nothing is guessed: every incoming
client-bound request is logged in full BEFORE any decision is taken, and the
reply is built from the options the agent actually offered.

Policy under test:
    read tool calls                       -> ALLOW
    shell that only reads                 -> ALLOW
    shell that creates temp.txt           -> DENY
    write of work_definition.json         -> ALLOW
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

GOOSE = r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe"
OUT = Path(__file__).resolve().parent
CWD = Path(os.environ.get("A1_DIR") or (OUT / "a1_probe_dir"))
CWD.mkdir(parents=True, exist_ok=True)
DESIGNATED = "work_definition.json"

log = []
replies = {}
lock = threading.Lock()
decisions = []

proc = subprocess.Popen([GOOSE, "acp"], cwd=str(CWD),
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True,
                        encoding="utf-8", bufsize=1)


def send(obj):
    with lock:
        log.append({"t": time.time(), "dir": "out", "msg": obj})
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def classify(raw: str):
    """Decide from the payload text alone. Returns (allow, why)."""
    low = raw.lower()
    if DESIGNATED in low:
        # a write of the designated artifact, or a read of it
        return True, "designated artifact path"
    writeish = any(k in low for k in
                   ["out-file", "set-content", "add-content", '">"', ">>",
                    '"write"', "new-item", "echo ", "tee "])
    if "temp.txt" in low or writeish:
        return False, "non-designated write attempt"
    return True, "read-only operation"


def reader():
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            with lock:
                log.append({"t": time.time(), "dir": "raw", "msg": line})
            continue
        with lock:
            log.append({"t": time.time(), "dir": "in", "msg": msg})
            if "id" in msg and "method" not in msg:
                replies[msg["id"]] = msg
        # client-bound REQUEST
        if "id" in msg and "method" in msg:
            method = msg.get("method", "")
            params = msg.get("params") or {}
            raw = json.dumps(msg, ensure_ascii=False)
            print(f"\n>>> CLIENT-BOUND REQUEST  method={method!r}")
            print(json.dumps(msg, ensure_ascii=False)[:1200])
            if "permission" in method:
                allow, why = classify(raw)
                options = params.get("options") or []
                print(f"    options offered: {json.dumps(options)[:400]}")
                print(f"    DECISION: {'ALLOW' if allow else 'DENY'}  ({why})")
                chosen = None
                for o in options:
                    kind = str(o.get("kind", "")).lower()
                    name = (str(o.get("name", "")) + str(o.get("optionId", ""))).lower()
                    is_allow = ("allow" in kind or "allow" in name
                                or "approve" in name or kind == "allow_once")
                    is_deny = ("reject" in kind or "deny" in kind
                               or "reject" in name or "deny" in name
                               or "cancel" in name)
                    if allow and is_allow and "always" not in kind:
                        chosen = o.get("optionId"); break
                    if (not allow) and is_deny and "always" not in kind:
                        chosen = o.get("optionId"); break
                if chosen is None and options:
                    chosen = options[0].get("optionId")
                with lock:
                    decisions.append({"method": method, "allow": allow, "why": why,
                                      "chosen": chosen,
                                      "options": options,
                                      "request": msg})
                if chosen is not None:
                    send({"jsonrpc": "2.0", "id": msg["id"],
                          "result": {"outcome": {"outcome": "selected",
                                                 "optionId": chosen}}})
                else:
                    send({"jsonrpc": "2.0", "id": msg["id"],
                          "result": {"outcome": {"outcome": "cancelled"}}})
            else:
                send({"jsonrpc": "2.0", "id": msg["id"],
                      "error": {"code": -32601,
                                "message": "client capability not offered"}})


threading.Thread(target=reader, daemon=True).start()

nid = [100]


def request(method, params, timeout=900):
    nid[0] += 1
    rid = nid[0]
    send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    end = time.time() + timeout
    while time.time() < end:
        with lock:
            if rid in replies:
                return replies.pop(rid)
        if proc.poll() is not None:
            return {"error": {"message": "goose exited"}}
        time.sleep(0.2)
    return None


print(f"probe cwd: {CWD}")
r = request("initialize", {"protocolVersion": 1,
                           "clientCapabilities": {"fs": {"readTextFile": False,
                                                         "writeTextFile": False}}},
            timeout=60)
print("initialize:", "OK" if r and "result" in r else r)

r = request("session/new", {"cwd": str(CWD), "mcpServers": []}, timeout=120)
sid = r["result"]["sessionId"]
print("sessionId:", sid)

r = request("session/set_mode", {"sessionId": sid, "modeId": "approve"}, timeout=60)
print("set_mode approve:", json.dumps(r)[:200])

PROMPT = f"""Do these four steps in order, one tool call each. Do not skip any.

1. Read the file notes.txt in your current directory using your file reader.
2. Run this shell command exactly: type notes.txt
3. Run this shell command exactly: echo hello > temp.txt
4. Write a file named {DESIGNATED} in your current directory whose entire
   contents are exactly: {{"probe": true}}

Then stop and say FINISHED."""

(CWD / "notes.txt").write_text("probe notes\n", encoding="utf-8", newline="\n")

t0 = time.time()
r = request("session/prompt",
            {"sessionId": sid, "prompt": [{"type": "text", "text": PROMPT}]},
            timeout=900)
print(f"\nturn returned in {time.time()-t0:.0f}s: {json.dumps(r)[:300]}")

time.sleep(1.0)
print("\n=== filesystem outcome ===")
for f in ("notes.txt", "temp.txt", DESIGNATED):
    p = CWD / f
    print(f"  {f:24s} exists={p.is_file()}"
          + (f"  bytes={p.stat().st_size}" if p.is_file() else ""))

(OUT / "a1_transcript.json").write_text(json.dumps(log, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
(OUT / "a1_decisions.json").write_text(json.dumps(decisions, indent=1,
                                                  ensure_ascii=False),
                                       encoding="utf-8")
print(f"\nmessages logged: {len(log)}   permission decisions: {len(decisions)}")
proc.terminate()
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
