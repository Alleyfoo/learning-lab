#!/usr/bin/env python3
"""W1-A5 ACP harness -- W1-A4's harness plus exactly two lifecycle changes.

W1-A4 ended 1/3 PASS. D3 produced the first structurally valid Work Definition
through the automated path. The other two runs were lost for reasons that say
nothing about `define-lab-process`:

  D1  HARNESS-CONTESTED  two clear questions went undetected because their
                         terminal "?" was wrapped in Markdown emphasis:
                         "**Q5: ...excluded?**" ends with "**", not "?".
  D2  AGENT-QUIESCENT    the completed turn carried zero agent_message_chunk --
                         393 thought chunks, 4 tool calls, no user-visible text.
                         The harness had no lifecycle state for "the turn ended
                         and the agent simply did not speak".

W1-A5 changes ONLY those two things.

  1. QUESTION PRESENTATION NORMALIZATION. Presentation-only wrappers -- Markdown
     emphasis, backticks, surrounding whitespace -- are stripped before deciding
     whether a fragment is interrogative. "?**" is recognized equivalently to
     "?". No synonyms, no semantic interpretation, no LLM. The intent table, the
     term matching and the answer rendering are untouched.

  2. SILENT-TURN RE-ENTRY. A completed turn with no artifact, no user-visible
     assistant content and no infrastructure failure is classified QUIESCENT
     rather than CONTESTED, and exactly `Continue.` is sent into the same
     session. That string carries no business or task information; it is a
     lifecycle trigger only. At most two CONSECUTIVE silent continuations are
     allowed; the counter resets ONLY when the agent emits non-empty user-visible
     assistant content. Tool calls do NOT reset it -- activity is not a
     mechanically established dialogue advance -- so silent turns full of tool
     calls stay consecutive and reach CONTESTED: QUIESCENT_RETRY_LIMIT. Artifact
     existence still terminates immediately as COMPLETED.

Unchanged and still enforced: SKILL.md, the fixtures, human_answers.md, the
validator, the intent table and the answer rendering; the first-artifact hard
stop; controlled-input hashing; forbidden-access checks; the deterministic answer
boundary; complete transcript capture; and infrastructure-vs-experimental exit
semantics.

Usage:
    python work_interface/w1a5/harness/acp_harness.py --run all
    python work_interface/w1a5/harness/acp_harness.py --run E1 --dry-run
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
# Frozen constants
# --------------------------------------------------------------------------

GOOSE_EXE = Path(
    r"F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe")

HERE = Path(__file__).resolve().parent
W1A5 = HERE.parent
W1A = W1A5.parent / "w1a"
RUNS_DIR = W1A5 / "runs"

FROZEN_SKILL_SHA256 = "4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55"
HUMAN_ANSWERS = W1A / "human_answers.md"
HUMAN_ANSWERS_SHA256 = "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd"

ARTIFACT_NAME = "work_definition.json"
ALL_RUNS = ["E1", "E2", "E3"]

MAX_CLARIFICATION_TURNS = 12
TURN_TIMEOUT_S = 1800
DISPLAY_TRUNCATE = 400          # display only; machine evidence is never truncated

# Lifecycle change 2
MAX_CONSECUTIVE_SILENT = 2
CONTINUATION = "Continue."      # lifecycle trigger only; carries no task content

# Outcomes
COMPLETED, CONTESTED, HARNESS_ERROR = "COMPLETED", "CONTESTED", "HARNESS_ERROR"
# Matcher statuses
RECOGNIZED, NO_MATCH = "RECOGNIZED", "NO_MATCH"
# Lifecycle states
QUIESCENT, DIALOGUE = "QUIESCENT", "DIALOGUE"


# --------------------------------------------------------------------------
# The frozen answer table (unchanged from W1-A4)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    index: int
    terms: tuple[tuple[str, ...], ...]
    canonical: str
    raw_intent: str


def _norm(s: str) -> str:
    s = s.lower().replace("`", " ").replace("*", " ")
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_answer_table(path: Path = HUMAN_ANSWERS) -> list[Intent]:
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
            continue
        bold = re.findall(r"\*\*(.+?)\*\*", intent_cell)
        if not bold:
            continue
        groups = []
        for b in bold:
            alts = tuple(a for a in (_norm(x) for x in b.split("/")) if a)
            if alts:
                groups.append(alts)
        canonical = answer_cell.strip()
        if canonical.startswith("`") and canonical.endswith("`"):
            canonical = canonical[1:-1].strip()
        intents.append(Intent(len(intents), tuple(groups), canonical, intent_cell))
    return intents


# --------------------------------------------------------------------------
# CHANGE 1: question presentation normalization
# --------------------------------------------------------------------------

# Presentation-only wrapper characters. Stripping these decides ONLY whether a
# fragment is interrogative. It adds no synonym, no semantics, no interpretation.
PRESENTATION_CHARS = "*_`~ \t\r\n"


def strip_presentation(s: str) -> str:
    """Remove presentation-only wrappers from both ends of a fragment."""
    return s.strip().strip(PRESENTATION_CHARS).strip()


def is_interrogative(fragment: str) -> bool:
    """A fragment ending `?**`, `?`, "`?`" or `? ` are all interrogative."""
    return strip_presentation(fragment).endswith("?")


def segment_fragments(message: str) -> list[str]:
    """Split a completed assistant turn into interrogative fragments.

    Fragments are REPORTING units, not verdict units. Only interrogative text is
    considered, so narration cannot pull an answer out of the harness for a
    question that was never asked."""
    out: list[str] = []
    for raw in message.splitlines():
        line = raw.strip()
        if not line or "?" not in line:
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line)
        # a "?" may be followed by closing emphasis before the next sentence
        for p in re.split(r"(?<=\?)[*_`~]*\s+", line):
            p = strip_presentation(p)
            if p.endswith("?") and len(p) > 3:
                out.append(p)
    return out


# --------------------------------------------------------------------------
# Turn-level classifier (unchanged semantics from W1-A4)
# --------------------------------------------------------------------------

def intents_in(fragment: str, intents: list[Intent]) -> list[Intent]:
    n = _norm(fragment)
    return [i for i in intents
            if all(any(alt in n for alt in group) for group in i.terms)]


def classify_turn(message: str, intents: list[Intent]) -> dict:
    fragments = segment_fragments(message)
    detail, recognised, unmatched = [], {}, []
    for f in fragments:
        hits = intents_in(f, intents)
        detail.append({"fragment": f, "intents": [h.index for h in hits]})
        if hits:
            for h in hits:
                recognised[h.index] = h
        else:
            unmatched.append(f)
    if not recognised:
        return {"status": NO_MATCH, "intents": [], "answers": [],
                "unmatched": unmatched, "fragments": detail}
    ordered = [recognised[k] for k in sorted(recognised)]
    return {"status": RECOGNIZED, "intents": [i.index for i in ordered],
            "answers": [i.canonical for i in ordered],
            "unmatched": unmatched, "fragments": detail}


def render_answers(answers: list[str]) -> str:
    """Frozen response format, unchanged."""
    if len(answers) == 1:
        return answers[0]
    return "\n".join(f"{i}. {a}" for i, a in enumerate(answers, 1))


# --------------------------------------------------------------------------
# CHANGE 2: lifecycle state machine
# --------------------------------------------------------------------------

def classify_lifecycle(visible_text: str, artifact_present: bool,
                       infrastructure_failure: bool) -> str:
    """Classify the state of a turn that reached stopReason.

        artifact present                      -> COMPLETED
        infrastructure failure                -> HARNESS_ERROR
        no user-visible assistant content     -> QUIESCENT
        otherwise                             -> DIALOGUE
    """
    if infrastructure_failure:
        return HARNESS_ERROR
    if artifact_present:
        return COMPLETED
    if not (visible_text or "").strip():
        return QUIESCENT
    return DIALOGUE


def next_silent_action(silent_streak: int) -> tuple[str, int]:
    """Decide what to do about a QUIESCENT turn.

    **Tool calls do NOT reset the streak.** Activity is not a mechanically
    established completion or dialogue advance: an agent can call tools
    indefinitely without ever producing an actionable question, which is exactly
    what W1-A4's D2 did. The streak resets only when the agent emits non-empty
    user-visible assistant content (handled by the caller, in the DIALOGUE
    branch); artifact existence terminates the run as COMPLETED before this
    function is ever reached.

    So a sequence of silent turns -- tool calls or not -- stays consecutive and
    reaches QUIESCENT_RETRY_LIMIT after MAX_CONSECUTIVE_SILENT continuations."""
    if silent_streak >= MAX_CONSECUTIVE_SILENT:
        return "QUIESCENT_RETRY_LIMIT", silent_streak
    return "CONTINUE", silent_streak + 1


# --------------------------------------------------------------------------
# Controlled-input integrity (unchanged)
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
    marks = ["human_answers", "work_definition.py",
             os.path.join("w1a", "runs"), os.path.join("w1a2", "runs"),
             os.path.join("w1a3", "runs"), os.path.join("w1a4", "runs"),
             os.path.join("w1a5", "harness"),
             "RESULTS.json", "RESULTS.md", "POSTMORTEM", "CLOSURE",
             os.path.join("work_interface", "cases")]
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
    outcome: str = HARNESS_ERROR
    reason: str = ""                      # complete; never truncated
    turns: int = 0
    artifact: bool = False
    silent_continuations: int = 0
    turn_log: list = field(default_factory=list)
    hashes_before: dict = field(default_factory=dict)
    hashes_after: dict = field(default_factory=dict)
    transcript: str = ""


class ACPSession:
    def __init__(self, cwd: Path, transcript_path: Path, goose_exe: Path = GOOSE_EXE):
        self.transcript_path = transcript_path
        self._tf = open(transcript_path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._replies: dict = {}
        self._updates: list = []
        self._next_id = 100
        self.unoffered_requests: list = []
        self.tool_payloads: list[str] = []
        self.tool_call_count = 0
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
        """Lifecycle decisions are recorded in the transcript alongside the wire
        traffic, so a reader can see why a `Continue.` was sent."""
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
                    k = u.get("sessionUpdate")
                    if k in ("tool_call", "tool_call_update"):
                        self.tool_payloads.append(json.dumps(u, ensure_ascii=False))
                    if k == "tool_call":
                        self.tool_call_count += 1
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
            intents: list[Intent] | None = None, artifact_name: str = ARTIFACT_NAME,
            check_skill: bool = True) -> RunResult:
    run_dir = (runs_dir / run).resolve()
    artifact = run_dir / artifact_name
    res = RunResult(run=run)

    if artifact.exists():
        res.outcome = HARNESS_ERROR
        res.reason = f"{artifact_name} already exists; run directory is not fresh"
        return res
    if intents is None:
        intents = load_answer_table()

    if check_skill:
        if sha256_file(run_dir / "SKILL.md") != FROZEN_SKILL_SHA256:
            res.outcome, res.reason = CONTESTED, "SKILL.md does not match the frozen hash"
            return res
        if sha256_file(HUMAN_ANSWERS) != HUMAN_ANSWERS_SHA256:
            res.outcome, res.reason = CONTESTED, "human_answers.md does not match the frozen hash"
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
        silent_streak = 0
        tools_seen = 0
        for turn in range(MAX_CLARIFICATION_TURNS + 1):
            res.turns = turn + 1
            r = s.request("session/prompt",
                          {"sessionId": sid,
                           "prompt": [{"type": "text", "text": message}]},
                          timeout=TURN_TIMEOUT_S)

            # --- first-artifact hard stop, before anything else can happen ---
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
            if turn == MAX_CLARIFICATION_TURNS:
                res.outcome = CONTESTED
                res.reason = (f"clarification turn limit ({MAX_CLARIFICATION_TURNS}) "
                              "reached without an artifact")
                break

            text = s.drain_agent_text()
            tools_now = s.tool_call_count
            progress = tools_now > tools_seen
            state = classify_lifecycle(text, artifact.exists(), False)

            if state == QUIESCENT:
                # `progress` is recorded as observation only; it does NOT reset
                # the streak. Tool calls are activity, not dialogue advance.
                action, silent_streak = next_silent_action(silent_streak)
                entry = {"turn": turn + 1, "status": QUIESCENT,
                         "visible_chars": 0,
                         "tool_calls_observed": progress,
                         "tool_calls_total": tools_now,
                         "streak_reset_by_tool_calls": False,
                         "silent_streak": silent_streak,
                         "action": action}
                if action == "QUIESCENT_RETRY_LIMIT":
                    res.turn_log.append(entry)
                    s.record_lifecycle(entry)
                    res.outcome = CONTESTED
                    res.reason = ("QUIESCENT_RETRY_LIMIT: the completed turn carried no "
                                  "user-visible assistant content after "
                                  f"{MAX_CONSECUTIVE_SILENT} consecutive `Continue.` "
                                  "re-entries. Tool calls during those turns are "
                                  "activity, not dialogue advance, and do not reset "
                                  "the streak")
                    break
                entry["continuation_sent"] = CONTINUATION
                res.turn_log.append(entry)
                s.record_lifecycle(entry)
                res.silent_continuations += 1
                tools_seen = tools_now
                message = CONTINUATION
                continue

            # DIALOGUE: user-visible content present -> the streak resets
            silent_streak = 0
            tools_seen = tools_now
            c = classify_turn(text, intents)
            res.turn_log.append({"turn": turn + 1, "status": c["status"],
                                 "lifecycle": DIALOGUE,
                                 "recognized_intents": c["intents"],
                                 "answers_sent": c["answers"],
                                 "unmatched_fragments": c["unmatched"],
                                 "fragments": c["fragments"],
                                 "agent_turn_text": text})
            if c["status"] == NO_MATCH:
                res.outcome = CONTESTED
                res.reason = ("NO_MATCH: zero frozen intents recognized in the "
                              "completed turn. fragments=" + json.dumps(c["fragments"]))
                break
            message = render_answers(c["answers"])
    finally:
        s.close()
        res.hashes_after = hash_controlled(run_dir)

    if res.outcome == COMPLETED:
        changed = [k for k in res.hashes_before
                   if res.hashes_before[k] != res.hashes_after.get(k)]
        if changed:
            res.outcome = CONTESTED
            res.reason = f"controlled input mutated during the run: {changed}"
    return res


def _display(text: str) -> str:
    return text if len(text) <= DISPLAY_TRUNCATE else \
        text[:DISPLAY_TRUNCATE] + " …[truncated for display; full reason in harness_result.json]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W1-A5 ACP harness")
    ap.add_argument("--run", required=True, choices=ALL_RUNS + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not GOOSE_EXE.is_file():
        print(f"HARNESS ERROR: Goose CLI not found: {GOOSE_EXE}", file=sys.stderr)
        return 1

    intents = load_answer_table()
    print(f"frozen answer table: {len(intents)} intents from {HUMAN_ANSWERS.name} "
          f"({sha256_file(HUMAN_ANSWERS)[:12]})")
    for i in intents:
        print(f"  [{i.index}] terms={[list(g) for g in i.terms]}")

    runs = ALL_RUNS if args.run == "all" else [args.run]
    if args.dry_run:
        for run in runs:
            d = RUNS_DIR / run
            print(f"{run}: prompt={(d / 'PROMPT.md').is_file()} "
                  f"skill_ok={sha256_file(d / 'SKILL.md') == FROZEN_SKILL_SHA256} "
                  f"artifact_absent={not (d / ARTIFACT_NAME).exists()}")
        return 0

    infra_failure = False
    for run in runs:
        print(f"\n=== {run} ===")
        res = run_one(run, intents=intents)
        print(f"  outcome            : {res.outcome}")
        print(f"  reason             : {_display(res.reason)}")
        print(f"  turns              : {res.turns}")
        print(f"  silent continuations: {res.silent_continuations}")
        print(f"  artifact           : {res.artifact}")
        print(f"  transcript         : {res.transcript}")
        (RUNS_DIR / run / "harness_result.json").write_text(
            json.dumps({"run": res.run, "outcome": res.outcome, "reason": res.reason,
                        "turns": res.turns, "artifact": res.artifact,
                        "silent_continuations": res.silent_continuations,
                        "turn_log": res.turn_log,
                        "hashes_before": res.hashes_before,
                        "hashes_after": res.hashes_after}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        if res.outcome == HARNESS_ERROR:
            infra_failure = True

    return 1 if infra_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
