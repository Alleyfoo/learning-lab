#!/usr/bin/env python3
"""W1-B ACP harness -- the perfect-information ablation.

Authority: `work_interface/W1A_DISPOSITION.md`. W1-A2..W1-A5 are closed as
measurement-invalid for skill-quality inference: the dialogue channel routed only
37% of worker questions correctly and MISROUTED 17%, answering (for example)
"For output order: left_then_right or sorted_by_key?" with "InvoiceNumber". A
channel that both withholds and misdelivers cannot attribute PASS or FAIL to the
skill.

W1-B removes the channel instead of repairing it, changing the question from

    "can the worker interact correctly with our dialogue harness?"
to
    "can the worker perform the skill when all required human information is
     definitely available?"

THE ABLATION PROPERTY
---------------------
After every completed worker turn that did not produce the artifact, the harness
sends ONE canonical block containing exactly the five SKILL-mandated human-owned
answers, always in frozen table order. The outgoing message is **unconditional**:
it does not depend on what the worker said, or whether it said anything at all.

There is NO lexical matching, NO semantic matching, NO synonyms, NO routing and
NO question classification anywhere in this file. There is deliberately no
`classify_turn`, no `intents_in`, no `segment_fragments` and no import of any
W1-A harness. `verify_prep.py` asserts their absence.

Interrogative counting exists ONLY to log whether the worker keeps asking for
information it already holds. It never selects, alters or gates a message.

WHAT THE BLOCK CONTAINS, AND WHAT IT MUST NOT
---------------------------------------------
Included -- the five questions SKILL.md step 5 mandates the human answer:
    S1 match key                  frozen table row 0
    S2 compare field + tolerance  row 1
    S3 other field in the rule    row 2
    S4 source of truth            row 3
    S5 report row vs context      rows 4 AND 5   (both halves of one question)

Excluded, deliberately:
    rows 6, 7  duplicate-key and non-numeric policy -- SKILL.md:124-125 assigns
               these to the worker via closed vocabularies. Supplying them would
               paper over the ownership inconsistency this ablation must leave
               standing.
    row 8      the Notes field -- a further specialisation beyond the five.
    left/right roles, classify labels, output order, purpose -- SKILL.md assigns
               all four to the worker; the frozen table has no answer for them.

Every byte of the block is copied verbatim from `w1a/human_answers.md`: the
question labels are the table's own Intent cells and the answers are its own
canonical strings. Nothing is authored here.

Outcomes:
    COMPLETED                            artifact written; session terminated at once
    CONTESTED: BLOCKED_WITH_COMPLETE_INFORMATION
                                         the worker never produced an artifact
                                         although it held the complete mandated
                                         block -- a meaningful worker-behaviour
                                         result, not a harness fault
    CONTESTED                            timeout, forbidden path, mutated input
    HARNESS_ERROR                        infrastructure only

    exit 0  the batch executed correctly, CONTESTED runs included
    exit 1  HARNESS_ERROR only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

GOOSE_EXE = Path(
    r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe")

HERE = Path(__file__).resolve().parent
W1B = HERE.parent
W1A = W1B.parent / "w1a"
RUNS_DIR = W1B / "runs"

FROZEN_SKILL_SHA256 = "4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55"
HUMAN_ANSWERS = W1A / "human_answers.md"
HUMAN_ANSWERS_SHA256 = "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd"

ARTIFACT_NAME = "work_definition.json"
ALL_RUNS = ["F1", "F2", "F3"]

# Rows of the frozen table that answer the five SKILL-mandated human questions.
MANDATED_ROWS = (0, 1, 2, 3, 4, 5)
EXCLUDED_ROWS = (6, 7, 8)

MAX_TURNS = 12
TURN_TIMEOUT_S = 1800
DISPLAY_TRUNCATE = 400

COMPLETED, CONTESTED, HARNESS_ERROR = "COMPLETED", "CONTESTED", "HARNESS_ERROR"


# --------------------------------------------------------------------------
# The canonical block, built mechanically from the frozen table
# --------------------------------------------------------------------------

def load_table_rows(path: Path = HUMAN_ANSWERS) -> list[tuple[str, str]]:
    """Return (intent cell, canonical answer) for every row of the frozen table,
    verbatim. This is a table READER, not a matcher: it never inspects worker
    text and produces no terms."""
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        intent_cell, answer_cell = cells
        if intent_cell.lower().startswith("intent goose"):
            continue
        if "**" not in intent_cell:
            continue
        answer = answer_cell.strip()
        if answer.startswith("`") and answer.endswith("`"):
            answer = answer[1:-1].strip()
        rows.append((intent_cell, answer))
    return rows


def build_block(path: Path = HUMAN_ANSWERS) -> str:
    """The canonical block: the mandated rows, in frozen table order, verbatim.

    No preamble and no framing sentence -- any such text would be authored here
    rather than by the frozen script, and could bias the worker."""
    rows = load_table_rows(path)
    parts = []
    for idx in MANDATED_ROWS:
        cell, answer = rows[idx]
        parts.append(f"{cell}\n{answer}")
    return "\n\n".join(parts)


def count_interrogatives(text: str) -> int:
    """LOGGING ONLY. Counts question-bearing lines so continued questioning can be
    recorded. It selects nothing, gates nothing, and never touches the block."""
    return sum(1 for l in (text or "").splitlines() if "?" in l)


# --------------------------------------------------------------------------
# Controlled-input integrity
# --------------------------------------------------------------------------

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def controlled_inputs(run_dir: Path) -> dict[str, Path]:
    return {
        "PROMPT.md": run_dir / "PROMPT.md",
        "SKILL.md": run_dir / "SKILL.md",
        "supplier-statement.txt": W1A / "fixtures" / "supplier-statement.txt",
        "ledger-book.txt": W1A / "fixtures" / "ledger-book.txt",
        "human_answers.md": HUMAN_ANSWERS,
    }


def hash_controlled(run_dir: Path) -> dict[str, str]:
    return {k: sha256_file(v) for k, v in controlled_inputs(run_dir).items()}


def forbidden_markers(run: str) -> list[str]:
    marks = ["human_answers", "work_definition.py", "census",
             os.path.join("w1a", "runs"), os.path.join("w1a2", "runs"),
             os.path.join("w1a3", "runs"), os.path.join("w1a4", "runs"),
             os.path.join("w1a5", "runs"), os.path.join("w1b", "harness"),
             "RESULTS.json", "RESULTS.md", "POSTMORTEM", "CLOSURE",
             "DISPOSITION", os.path.join("work_interface", "cases")]
    marks += [os.path.join("runs", r) for r in ALL_RUNS if r != run]
    out = []
    for m in marks:
        out.append(m.replace("\\", "/").lower())
        out.append(m.replace("/", "\\").lower())
    return sorted(set(out))


# --------------------------------------------------------------------------
# ACP session
# --------------------------------------------------------------------------

@dataclass
class RunResult:
    run: str
    outcome: str = HARNESS_ERROR
    reason: str = ""
    turns: int = 0
    artifact: bool = False
    blocks_delivered: int = 0
    silent_turns: int = 0
    questions_after_block: int = 0
    turn_log: list = field(default_factory=list)
    hashes_before: dict = field(default_factory=dict)
    hashes_after: dict = field(default_factory=dict)
    transcript: str = ""


class ACPSession:
    def __init__(self, cwd: Path, transcript_path: Path, goose_exe: Path = GOOSE_EXE):
        self._tf = open(transcript_path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._replies: dict = {}
        self._updates: list = []
        self._next_id = 100
        self.unoffered_requests: list = []
        self.tool_payloads: list[str] = []
        self.proc = subprocess.Popen(
            [str(goose_exe), "acp"], cwd=str(cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1)
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
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
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


# --------------------------------------------------------------------------
# One run
# --------------------------------------------------------------------------

def run_one(run: str, runs_dir: Path = RUNS_DIR, goose_exe: Path = GOOSE_EXE,
            artifact_name: str = ARTIFACT_NAME, check_skill: bool = True,
            session_factory=None, block: str | None = None) -> RunResult:
    run_dir = (runs_dir / run).resolve()
    artifact = run_dir / artifact_name
    res = RunResult(run=run)

    if artifact.exists():
        res.outcome = HARNESS_ERROR
        res.reason = f"{artifact_name} already exists; run directory is not fresh"
        return res

    if check_skill:
        if sha256_file(run_dir / "SKILL.md") != FROZEN_SKILL_SHA256:
            res.outcome, res.reason = CONTESTED, "SKILL.md does not match the frozen hash"
            return res
        if sha256_file(HUMAN_ANSWERS) != HUMAN_ANSWERS_SHA256:
            res.outcome, res.reason = CONTESTED, "human_answers.md does not match the frozen hash"
            return res

    if block is None:
        block = build_block()
    res.hashes_before = hash_controlled(run_dir)
    transcript = run_dir / "acp_transcript.jsonl"
    res.transcript = str(transcript)
    prompt_text = (run_dir / "PROMPT.md").read_text(encoding="utf-8")
    marks = forbidden_markers(run)

    factory = session_factory or (lambda: ACPSession(run_dir, transcript, goose_exe))
    s = factory()
    try:
        r = s.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False,
                                          "writeTextFile": False}}}, timeout=60)
        if not r or "result" not in r:
            res.outcome, res.reason = HARNESS_ERROR, f"initialize failed: {r}"
            return res
        r = s.request("session/new", {"cwd": str(run_dir), "mcpServers": []}, timeout=120)
        if not r or "result" not in r:
            res.outcome, res.reason = HARNESS_ERROR, f"session/new failed: {r}"
            return res
        sid = r["result"]["sessionId"]
        r = s.request("session/set_mode", {"sessionId": sid, "modeId": "auto"}, timeout=60)
        if r is None or "error" in r:
            res.outcome, res.reason = HARNESS_ERROR, f"session/set_mode auto failed: {r}"
            return res

        message = prompt_text
        for turn in range(MAX_TURNS + 1):
            res.turns = turn + 1
            r = s.request("session/prompt",
                          {"sessionId": sid,
                           "prompt": [{"type": "text", "text": message}]},
                          timeout=TURN_TIMEOUT_S)

            # --- first-artifact hard stop, before anything else --------------
            if artifact.exists():
                res.artifact, res.outcome = True, COMPLETED
                res.reason = "artifact written; session terminated immediately"
                break

            blob = "\n".join(s.tool_payloads).replace("\\\\", "\\").lower()
            hit = sorted({m for m in marks if m in blob})
            if hit:
                res.outcome = CONTESTED
                res.reason = f"tool call touched forbidden path(s): {hit}"
                break
            if s.unoffered_requests:
                res.outcome = HARNESS_ERROR
                res.reason = ("agent issued client-bound request(s) for a capability "
                              f"we never offered: {s.unoffered_requests}")
                break
            if r is None:
                res.outcome = CONTESTED
                res.reason = f"turn {turn + 1} exceeded {TURN_TIMEOUT_S}s with no stopReason"
                break
            if "error" in r:
                res.outcome = HARNESS_ERROR
                res.reason = f"session/prompt error: {json.dumps(r['error'])}"
                break

            text = s.drain_agent_text()
            silent = not (text or "").strip()
            q = count_interrogatives(text)
            already_had_block = res.blocks_delivered > 0
            if silent:
                res.silent_turns += 1
            if already_had_block:
                res.questions_after_block += q

            if turn == MAX_TURNS:
                res.outcome = CONTESTED
                res.reason = (
                    "BLOCKED_WITH_COMPLETE_INFORMATION: the worker did not produce an "
                    f"artifact within {MAX_TURNS} turns although the complete mandated "
                    f"block was delivered {res.blocks_delivered} time(s)"
                    if already_had_block else
                    f"turn limit ({MAX_TURNS}) reached before any block was delivered")
                res.turn_log.append({"turn": turn + 1, "silent": silent,
                                     "interrogative_lines": q,
                                     "block_delivered": False,
                                     "agent_turn_text": text})
                break

            # --- UNCONDITIONAL delivery. No inspection of `text` occurs here. --
            entry = {"turn": turn + 1, "silent": silent, "interrogative_lines": q,
                     "questions_after_block_so_far": res.questions_after_block,
                     "block_delivered": True,
                     "block_sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
                     "agent_turn_text": text}
            res.turn_log.append(entry)
            s.record_lifecycle({k: v for k, v in entry.items()
                                if k != "agent_turn_text"})
            res.blocks_delivered += 1
            message = block
    finally:
        try:
            s.close()
        except Exception:
            pass
        res.hashes_after = hash_controlled(run_dir)

    if res.outcome == COMPLETED:
        changed = [k for k in res.hashes_before
                   if res.hashes_before[k] != res.hashes_after.get(k)]
        if changed:
            res.outcome = CONTESTED
            res.reason = f"controlled input mutated during the run: {changed}"
    return res


def _display(t: str) -> str:
    return t if len(t) <= DISPLAY_TRUNCATE else t[:DISPLAY_TRUNCATE] + " …[full reason in harness_result.json]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W1-B perfect-information ablation")
    ap.add_argument("--run", required=True, choices=ALL_RUNS + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-block", action="store_true",
                    help="print the canonical block and exit")
    args = ap.parse_args(argv)

    block = build_block()
    if args.show_block:
        print(block)
        return 0

    print(f"canonical block: {len(block)} bytes, sha256 "
          f"{hashlib.sha256(block.encode('utf-8')).hexdigest()[:16]}, "
          f"rows {list(MANDATED_ROWS)} of {HUMAN_ANSWERS.name} "
          f"({sha256_file(HUMAN_ANSWERS)[:12]})")

    if not GOOSE_EXE.is_file():
        print(f"HARNESS ERROR: Goose CLI not found: {GOOSE_EXE}", file=sys.stderr)
        return 1

    runs = ALL_RUNS if args.run == "all" else [args.run]
    if args.dry_run:
        for run in runs:
            d = RUNS_DIR / run
            print(f"{run}: prompt={(d / 'PROMPT.md').is_file()} "
                  f"skill_ok={sha256_file(d / 'SKILL.md') == FROZEN_SKILL_SHA256} "
                  f"artifact_absent={not (d / ARTIFACT_NAME).exists()}")
        return 0

    infra = False
    for run in runs:
        print(f"\n=== {run} ===")
        res = run_one(run, block=block)
        print(f"  outcome                : {res.outcome}")
        print(f"  reason                 : {_display(res.reason)}")
        print(f"  turns                  : {res.turns}")
        print(f"  blocks delivered       : {res.blocks_delivered}")
        print(f"  silent turns           : {res.silent_turns}")
        print(f"  questions after block  : {res.questions_after_block}")
        print(f"  artifact               : {res.artifact}")
        (RUNS_DIR / run / "harness_result.json").write_text(
            json.dumps({"run": res.run, "outcome": res.outcome, "reason": res.reason,
                        "turns": res.turns, "artifact": res.artifact,
                        "blocks_delivered": res.blocks_delivered,
                        "silent_turns": res.silent_turns,
                        "questions_after_block": res.questions_after_block,
                        "block_sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
                        "turn_log": res.turn_log,
                        "hashes_before": res.hashes_before,
                        "hashes_after": res.hashes_after}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        if res.outcome == HARNESS_ERROR:
            infra = True
    return 1 if infra else 0


if __name__ == "__main__":
    raise SystemExit(main())
