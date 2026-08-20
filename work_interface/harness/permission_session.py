#!/usr/bin/env python3
"""ACP transport with enforced, fail-closed permission handling (Surface A).

Same transport as `acp_session.ACPSession`, plus the client half of
`session/request_permission`. The wire shape is the one calibrated in
`authority/a1_calibration/FINDINGS.md`; nothing is guessed.

Every request is **logged in full before any decision is taken**. A denial is
returned normally with the agent's own `reject_once` option, so the session
continues — a denial is worker evidence, not a run failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "authority"))
from permission_policy import PermissionPolicy, choose_option  # noqa: E402

GOOSE_EXE = Path(
    r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe")

PERMISSION_METHOD = "session/request_permission"


class PermissionSession:
    """Drives `goose acp` with a fail-closed permission handler."""

    def __init__(self, cwd: Path, transcript_path: Path,
                 policy: PermissionPolicy, goose_exe: Path = GOOSE_EXE):
        self.policy = policy
        self._tf = open(transcript_path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._replies: dict = {}
        self._updates: list = []
        self._next_id = 100
        self.unoffered_requests: list = []
        self.tool_payloads: list[str] = []
        self.tool_updates: list[dict] = []
        self.permission_log: list[dict] = []
        self.shell_attempts: int = 0
        self.proc = subprocess.Popen(
            [str(goose_exe), "acp"], cwd=str(cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    # -- transcript ----------------------------------------------------
    def _record(self, direction: str, obj) -> None:
        with self._lock:
            self._tf.write(json.dumps({"t": time.time(), "dir": direction,
                                       "msg": obj}, ensure_ascii=False) + "\n")
            self._tf.flush()

    def record_lifecycle(self, obj) -> None:
        self._record("lifecycle", obj)

    # -- permission ----------------------------------------------------
    def _handle_permission(self, msg: dict) -> None:
        # LOG FIRST, decide second.
        self._record("permission_request", msg)
        decision = self.policy.decide(msg)
        params = msg.get("params") or {}
        options = params.get("options") or []
        option_id = choose_option(options, decision.allowed)
        tc = (params.get("toolCall") or {})
        entry = {"toolCallId": tc.get("toolCallId"),
                 "title": tc.get("title"),
                 "verdict": decision.verdict,
                 "kind": decision.kind,
                 "reason": decision.reason,
                 "paths": list(decision.paths),
                 "optionId": option_id,
                 "options_offered": [o.get("optionId") for o in options],
                 "rawInput": tc.get("rawInput")}
        with self._lock:
            self.permission_log.append(entry)
            if decision.kind == "SHELL":
                self.shell_attempts += 1
        self._record("permission_decision", entry)
        if option_id is not None:
            self._send({"jsonrpc": "2.0", "id": msg["id"],
                        "result": {"outcome": {"outcome": "selected",
                                               "optionId": option_id}}})
        else:
            # No usable option was offered: refuse by cancelling, never by
            # guessing an identifier.
            self._send({"jsonrpc": "2.0", "id": msg["id"],
                        "result": {"outcome": {"outcome": "cancelled"}}})

    # -- reader --------------------------------------------------------
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
                if msg.get("method") == PERMISSION_METHOD:
                    self._handle_permission(msg)
                else:
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
