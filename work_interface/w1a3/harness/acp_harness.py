#!/usr/bin/env python3
"""W1-A3 ACP harness -- drives one Goose session per run with no human operator.

Removes the desktop operator from the W1 experiment. Every W1-A2 protocol defect
this closes is closed *structurally*, not by asking the agent nicely:

  B2's prompt destruction   the prompt is never a file Goose can reach. The harness
                            reads PROMPT.md itself and sends its TEXT.
  B2's cross-run inspection tool calls naming another run dir -> CONTESTED.
  B3's post-write repair    the session is killed the instant the artifact exists.
  the answer-key handover   human_answers.md is parsed in-process. Goose only ever
                            receives individual canonical answer strings.

The harness never interprets. It matches a question to a frozen intent or it stops
the run. There is no second model anywhere in this file.

Usage:
    python work_interface/w1a3/harness/acp_harness.py --run C1
    python work_interface/w1a3/harness/acp_harness.py --run C1 --dry-run

Outcomes per run:
    COMPLETED   the artifact was written and the session was terminated at once
    CONTESTED   a controlled input changed, a forbidden path was touched, a question
                did not match exactly one frozen intent, or the interface behaved
                outside the declared contract
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

# --------------------------------------------------------------------------
# Frozen constants. None of these may drift without invalidating the run.
# --------------------------------------------------------------------------

GOOSE_EXE = Path(
    r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe")

HERE = Path(__file__).resolve().parent
W1A3 = HERE.parent
W1A = W1A3.parent / "w1a"
RUNS_DIR = W1A3 / "runs"

FROZEN_SKILL_SHA256 = "4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55"
HUMAN_ANSWERS = W1A / "human_answers.md"
HUMAN_ANSWERS_SHA256 = "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd"
FIXTURES = {
    "supplier-statement.txt":
        "d0cb95ab5755bef320390f11899c53034548a60678e27430882e556ce1a45feb",
    "ledger-book.txt":
        "284861d7d948dd6f0cd3a5e7826a6794d15db0ce2aafe108dafa37752c36f25e",
}

ARTIFACT_NAME = "work_definition.json"
ALL_RUNS = ["C1", "C2", "C3"]

# Safety rails. Exceeding either stops the run rather than letting it wander.
MAX_CLARIFICATION_TURNS = 12
TURN_TIMEOUT_S = 1800

# The frozen response format. One canonical answer per line, in the order the
# questions appeared. Numbered only when more than one question was asked, so a
# single answer is sent as the bare frozen string with nothing added to it.
def render_answers(answers: list[str]) -> str:
    if len(answers) == 1:
        return answers[0]
    return "\n".join(f"{i}. {a}" for i, a in enumerate(answers, 1))


# --------------------------------------------------------------------------
# The frozen answer table, derived mechanically from human_answers.md
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    index: int
    # One group per **bold** span. EVERY group must be satisfied, and a group is
    # satisfied by ANY of its alternatives -- a "/" inside a bold span is the
    # author's own alternation ("same record / invoice"). Mechanical, not judged.
    terms: tuple[tuple[str, ...], ...]
    canonical: str
    raw_intent: str


def _norm(s: str) -> str:
    """Lowercase, strip markdown/punctuation noise, collapse whitespace."""
    s = s.lower()
    s = s.replace("`", " ").replace("*", " ")
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_answer_table(path: Path = HUMAN_ANSWERS) -> list[Intent]:
    """Parse the frozen table. The discriminating terms of each intent are exactly
    the **bold** spans of its Intent cell -- an author-marked, mechanical hook. No
    judgement is applied here and none may be added later."""
    text = path.read_text(encoding="utf-8")
    intents: list[Intent] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        intent_cell, answer_cell = cells
        if intent_cell.lower().startswith("intent goose"):
            continue  # header row
        bold = re.findall(r"\*\*(.+?)\*\*", intent_cell)
        if not bold:
            continue
        groups = []
        for b in bold:
            alts = tuple(a for a in (_norm(x) for x in b.split("/")) if a)
            if alts:
                groups.append(alts)
        terms = tuple(groups)
        canonical = answer_cell.strip()
        if canonical.startswith("`") and canonical.endswith("`"):
            canonical = canonical[1:-1].strip()
        intents.append(Intent(len(intents), terms, canonical, intent_cell))
    return intents


# --------------------------------------------------------------------------
# Deterministic closed matcher
# --------------------------------------------------------------------------

UNIQUE_MATCH, NO_MATCH, MULTIPLE_MATCHES = "UNIQUE_MATCH", "NO_MATCH", "MULTIPLE_MATCHES"


def segment_questions(message: str) -> list[str]:
    """Split an assistant message into question units.

    Goose often asks several load-bearing questions in one message, as numbered or
    bulleted lines. Each unit is matched independently, so several distinct frozen
    intents in one message are answerable -- but any single unit that is ambiguous
    stops the run."""
    units: list[str] = []
    for raw in message.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line)
        if "?" not in line:
            continue
        # one line may carry several sentences; keep only the interrogative ones
        parts = re.split(r"(?<=\?)\s+", line)
        for p in parts:
            p = p.strip()
            if p.endswith("?") and len(p) > 3:
                units.append(p)
    return units


def match_unit(unit: str, intents: list[Intent]) -> tuple[str, list[Intent]]:
    norm = _norm(unit)
    hits = [i for i in intents
            if all(any(alt in norm for alt in group) for group in i.terms)]
    if len(hits) == 1:
        return UNIQUE_MATCH, hits
    if not hits:
        return NO_MATCH, []
    return MULTIPLE_MATCHES, hits


def match_message(message: str, intents: list[Intent]) -> dict:
    """Return {'status', 'answers', 'detail'}. Any non-unique unit fails the run."""
    units = segment_questions(message)
    if not units:
        return {"status": NO_MATCH, "answers": [],
                "detail": "turn ended with no artifact and no recognisable question"}
    resolved, detail = [], []
    for u in units:
        status, hits = match_unit(u, intents)
        detail.append({"unit": u, "status": status,
                       "intents": [h.index for h in hits]})
        if status != UNIQUE_MATCH:
            return {"status": status, "answers": [], "detail": detail}
        resolved.append(hits[0])
    # Two units resolving to the same intent is itself ambiguity: we cannot know
    # which of the two questions the single frozen answer belongs to.
    seen = [r.index for r in resolved]
    if len(set(seen)) != len(seen):
        return {"status": MULTIPLE_MATCHES, "answers": [],
                "detail": detail + [{"note": "two questions mapped to one intent"}]}
    return {"status": UNIQUE_MATCH,
            "answers": [r.canonical for r in resolved], "detail": detail}


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
    """Substrings whose appearance in a TOOL CALL means the run crossed a boundary.
    Only tool payloads are scanned -- the prompt text itself names these paths in its
    prohibitions, and matching on that would be a false positive."""
    marks = ["human_answers", "work_definition.py", os.path.join("w1a", "runs"),
             os.path.join("w1a2", "runs"), os.path.join("w1a3", "harness"),
             "RESULTS.json", "RESULTS.md", "POSTMORTEM", os.path.join("work_interface", "cases")]
    marks += [os.path.join("runs", r) for r in ALL_RUNS if r != run]
    out = []
    for m in marks:
        out.append(m.replace("\\", "/").lower())
        out.append(m.replace("/", "\\").lower())
    return sorted(set(out))


# --------------------------------------------------------------------------
# ACP client
# --------------------------------------------------------------------------

@dataclass
class RunResult:
    run: str
    outcome: str = "INCOMPLETE"
    reason: str = ""
    turns: int = 0
    artifact: bool = False
    hashes_before: dict = field(default_factory=dict)
    hashes_after: dict = field(default_factory=dict)
    transcript: str = ""


class ACPSession:
    def __init__(self, cwd: Path, transcript_path: Path, goose_exe: Path = GOOSE_EXE):
        self.cwd = cwd
        self.transcript_path = transcript_path
        self._tf = open(transcript_path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._replies: dict = {}
        self._updates: list = []
        self._next_id = 100
        self.tool_payloads: list[str] = []
        self.proc = subprocess.Popen(
            [str(goose_exe), "acp"], cwd=str(cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    # -- transport ---------------------------------------------------------
    def _record(self, direction: str, obj) -> None:
        with self._lock:
            self._tf.write(json.dumps({"t": time.time(), "dir": direction,
                                       "msg": obj}, ensure_ascii=False) + "\n")
            self._tf.flush()

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
                # A client-bound request. We declared no fs capability, so anything
                # arriving here is outside the declared contract; refuse rather than
                # deadlock, and let the caller mark the run CONTESTED.
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
                return {"error": {"message": "goose exited"}}
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
            intents: list[Intent] | None = None, artifact_name: str = ARTIFACT_NAME,
            check_skill: bool = True) -> RunResult:
    run_dir = (runs_dir / run).resolve()
    artifact = run_dir / artifact_name
    res = RunResult(run=run)

    if artifact.exists():
        res.outcome, res.reason = "REFUSED", f"{artifact_name} already exists; run is not fresh"
        return res
    if intents is None:
        intents = load_answer_table()

    if check_skill:
        if sha256_file(run_dir / "SKILL.md") != FROZEN_SKILL_SHA256:
            res.outcome, res.reason = "CONTESTED", "SKILL.md does not match the frozen hash"
            return res
        if sha256_file(HUMAN_ANSWERS) != HUMAN_ANSWERS_SHA256:
            res.outcome, res.reason = "CONTESTED", "human_answers.md does not match the frozen hash"
            return res

    res.hashes_before = hash_controlled(run_dir)
    transcript = run_dir / "acp_transcript.jsonl"
    res.transcript = str(transcript)
    prompt_text = (run_dir / "PROMPT.md").read_text(encoding="utf-8")
    marks = forbidden_markers(run)

    s = ACPSession(run_dir, transcript, goose_exe)
    try:
        r = s.request("initialize", {
            "protocolVersion": 1,
            # Deliberately no filesystem capability: Goose must use its own
            # `developer` extension, exactly as in the desktop runs.
            "clientCapabilities": {"fs": {"readTextFile": False,
                                          "writeTextFile": False}}}, timeout=60)
        if not r or "result" not in r:
            res.outcome, res.reason = "CONTESTED", f"initialize failed: {r}"
            return res

        r = s.request("session/new", {"cwd": str(run_dir), "mcpServers": []}, timeout=120)
        if not r or "result" not in r:
            res.outcome, res.reason = "CONTESTED", f"session/new failed: {r}"
            return res
        sid = r["result"]["sessionId"]

        r = s.request("session/set_mode", {"sessionId": sid, "modeId": "auto"}, timeout=60)
        if r is None or "error" in r:
            res.outcome, res.reason = "CONTESTED", f"set_mode auto failed: {r}"
            return res

        message = prompt_text
        for turn in range(MAX_CLARIFICATION_TURNS + 1):
            res.turns = turn + 1
            r = s.request("session/prompt",
                          {"sessionId": sid,
                           "prompt": [{"type": "text", "text": message}]},
                          timeout=TURN_TIMEOUT_S)

            # --- the stop rule, checked before anything else can happen -----
            if artifact.exists():
                res.artifact, res.outcome = True, "COMPLETED"
                res.reason = "artifact written; session terminated immediately"
                break

            blob = "\n".join(s.tool_payloads).replace("\\\\", "\\").lower()
            hit = [m for m in marks if m in blob]
            if hit:
                res.outcome, res.reason = "CONTESTED", f"tool call touched forbidden path(s): {sorted(set(hit))[:4]}"
                break
            if r is None:
                res.outcome, res.reason = "CONTESTED", "turn exceeded the timeout with no stopReason"
                break
            if "error" in r:
                res.outcome, res.reason = "CONTESTED", f"session/prompt error: {r['error']}"
                break
            if turn == MAX_CLARIFICATION_TURNS:
                res.outcome, res.reason = "CONTESTED", "clarification turn limit reached without an artifact"
                break

            text = s.drain_agent_text()
            m = match_message(text, intents)
            if m["status"] != UNIQUE_MATCH:
                res.outcome = "CONTESTED"
                res.reason = f"matcher {m['status']}: {json.dumps(m['detail'])[:400]}"
                break
            message = render_answers(m["answers"])
    finally:
        s.close()
        res.hashes_after = hash_controlled(run_dir)

    if res.outcome in ("COMPLETED", "INCOMPLETE"):
        changed = [k for k in res.hashes_before
                   if res.hashes_before[k] != res.hashes_after.get(k)]
        if changed:
            res.outcome = "CONTESTED"
            res.reason = f"controlled input mutated during the run: {changed}"
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W1-A3 ACP harness")
    ap.add_argument("--run", required=True, choices=ALL_RUNS + ["all"])
    ap.add_argument("--dry-run", action="store_true",
                    help="parse the answer table and report readiness; start no session")
    args = ap.parse_args(argv)

    if not GOOSE_EXE.is_file():
        print(f"Goose CLI not found: {GOOSE_EXE}", file=sys.stderr)
        return 2

    intents = load_answer_table()
    print(f"frozen answer table: {len(intents)} intents from {HUMAN_ANSWERS.name} "
          f"({sha256_file(HUMAN_ANSWERS)[:12]})")
    for i in intents:
        print(f"  [{i.index}] terms={[list(g) for g in i.terms]}")

    if args.dry_run:
        for run in (ALL_RUNS if args.run == "all" else [args.run]):
            d = RUNS_DIR / run
            print(f"{run}: prompt={ (d/'PROMPT.md').is_file() } "
                  f"skill_ok={sha256_file(d/'SKILL.md') == FROZEN_SKILL_SHA256} "
                  f"artifact_absent={not (d/ARTIFACT_NAME).exists()}")
        return 0

    runs = ALL_RUNS if args.run == "all" else [args.run]
    rc = 0
    for run in runs:
        print(f"\n=== {run} ===")
        res = run_one(run, intents=intents)
        print(f"  outcome  : {res.outcome}")
        print(f"  reason   : {res.reason}")
        print(f"  turns    : {res.turns}")
        print(f"  artifact : {res.artifact}")
        print(f"  transcript: {res.transcript}")
        (RUNS_DIR / run / "harness_result.json").write_text(
            json.dumps({"run": res.run, "outcome": res.outcome, "reason": res.reason,
                        "turns": res.turns, "artifact": res.artifact,
                        "hashes_before": res.hashes_before,
                        "hashes_after": res.hashes_after}, indent=2),
            encoding="utf-8")
        if res.outcome != "COMPLETED":
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
