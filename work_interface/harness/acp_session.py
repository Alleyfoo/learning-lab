#!/usr/bin/env python3
"""Shared ACP transport for Work-interface harnesses.

Transport only: JSON-RPC over stdio to `goose acp`, an append-only transcript,
and the client-bound-request refusal. It contains NO lifecycle, NO matcher and
no policy — those live in the harness revision that drives it.

Behaviour is unchanged from the transport proven in W1-B and W1-C:

  * `initialize` is the caller's business, but the caller is expected to declare
    NO client filesystem capability, so Goose's own `developer` extension does
    all file I/O -- the same worker capability environment as W1-B/W1-C.
  * any client-bound request for a capability we never offered is refused by
    name and recorded, rather than being silently answered or deadlocking.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

GOOSE_EXE = Path(
    r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe")


class ACPSession:
    def __init__(self, cwd: Path, transcript_path: Path,
                 goose_exe: Path = GOOSE_EXE):
        self._tf = open(transcript_path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._replies: dict = {}
        self._updates: list = []
        self._next_id = 100
        self.unoffered_requests: list = []
        self.tool_payloads: list[str] = []
        self.tool_updates: list[dict] = []
        self.proc = subprocess.Popen(
            [str(goose_exe), "acp"], cwd=str(cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _record(self, direction: str, obj) -> None:
        with self._lock:
            self._tf.write(json.dumps({"t": time.time(), "dir": direction,
                                       "msg": obj}, ensure_ascii=False) + "\n")
            self._tf.flush()

    def record_lifecycle(self, obj) -> None:
        self._record("lifecycle", obj)

    def _read(self) -> None:
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                self._record("raw", line)
                continue
            self._record("in", msg)
            with self._lock:
                if "id" in msg and "method" not in msg:
                    self._replies[msg["id"]] = msg
                elif "method" in msg:
                    self._updates.append(msg)
                    u = (msg.get("params") or {}).get("update") or {}
                    if u.get("sessionUpdate") in ("tool_call", "tool_call_update"):
                        self.tool_payloads.append(json.dumps(u, ensure_ascii=False))
                        self.tool_updates.append(u)
            if "id" in msg and "method" in msg:
                with self._lock:
                    self.unoffered_requests.append(msg.get("method"))
                self._send({"jsonrpc": "2.0", "id": msg["id"],
                            "error": {"code": -32601,
                                      "message": "client capability not offered"}})

    def _send(self, obj) -> None:
        self._record("out", obj)
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, timeout: int = 120):
        with self._lock:
            self._next_id += 1
            rid = self._next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method,
                    "params": params})
        end = time.time() + timeout
        while time.time() < end:
            with self._lock:
                if rid in self._replies:
                    return self._replies.pop(rid)
            if self.proc.poll() is not None:
                return {"error": {"message": "goose process exited"}}
            time.sleep(0.2)
        return None

    def drain_agent_text(self) -> str:
        with self._lock:
            msgs, self._updates = self._updates, []
        out = []
        for m in msgs:
            u = (m.get("params") or {}).get("update") or {}
            if u.get("sessionUpdate") == "agent_message_chunk":
                out.append((u.get("content") or {}).get("text", ""))
        return "".join(out)

    def close(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            self._tf.close()
        except Exception:
            pass
