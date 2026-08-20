#!/usr/bin/env python3
"""Surface B — lifecycle separation. Harness revision r2 (single-block lifecycle).

NEW REVISION. Historical W1 packs are untouched and keep their own harnesses;
this module is for a future adopting pack.

W1-C H1 received the canonical block FOUR times. Only the first was information
delivery: #2 followed a silent turn, #3 and #4 followed questions about
`output_order`, `on_duplicate_key` and `on_non_numeric` — fields the block
structurally cannot answer, since rows 6/7 are withheld and `output_order` has no
row at all (`work_interface/w1c/H_ANALYSIS.md`, `e1a95b5`).

r2 separates **authorized information delivery** from **worker re-entry**:

```text
initial session/prompt              -> the run prompt
first completed non-artifact turn   -> the canonical block, EXACTLY ONCE
every subsequent non-artifact turn  -> exactly "Continue."
first artifact                      -> terminate immediately
```

**The block is never delivered more than once.** Authority is asserted once and
never re-asserted, so redundant authority is impossible by construction.

**Post-block questions receive no business answer, regardless of wording.** The
full agent text is recorded verbatim; only `"Continue."` is sent. There is no
matcher, no classifier, and no attempt to decide whether a question is
worker-owned — that judgement happens offline, against the recorded text.

Silent-turn budget, carried over corrected from W1-A5:

```text
at most two consecutive silent re-entries
ONLY non-empty visible assistant content resets the streak
tool activity does NOT reset it
a visible post-block question counts as visible activity and RESETS the streak,
    but still receives only "Continue."
```

Ownership of rows 6/7 and `output_order` is unchanged by this revision.

A4 (`authority/fs_backstop.py`) is wired in as an **independent** filesystem-state
backstop, per `authority/POLICY.md`. It is not part of the lifecycle and does not
influence message selection.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "authority"))
import fs_backstop as A4  # noqa: E402

# --- lifecycle constants ---------------------------------------------------
CONTINUATION = "Continue."          # neutral activation; carries no task content
MAX_TURNS = 12
TURN_TIMEOUT_S = 1800
MAX_CONSECUTIVE_SILENT = 2

COMPLETED, CONTESTED, HARNESS_ERROR = "COMPLETED", "CONTESTED", "HARNESS_ERROR"
QUIESCENT, DIALOGUE = "QUIESCENT", "DIALOGUE"

# --- what each turn was sent ----------------------------------------------
SENT_PROMPT, SENT_BLOCK, SENT_CONTINUATION = "PROMPT", "BLOCK", "CONTINUATION"


def classify_lifecycle(visible_text: str, artifact_present: bool,
                       infrastructure_failure: bool) -> str:
    if infrastructure_failure:
        return HARNESS_ERROR
    if artifact_present:
        return COMPLETED
    if not (visible_text or "").strip():
        return QUIESCENT
    return DIALOGUE


def next_silent_action(silent_streak: int) -> tuple[str, int]:
    """Tool calls do NOT reset the streak. Activity is not dialogue advance."""
    if silent_streak >= MAX_CONSECUTIVE_SILENT:
        return "QUIESCENT_RETRY_LIMIT", silent_streak
    return "CONTINUE", silent_streak + 1


def next_message(block_sent: bool, block: str) -> tuple[str, str]:
    """THE lifecycle separation, in one place.

    The first completed non-artifact turn earns the block. Every later one earns
    a neutral activation. Nothing about the agent's text is consulted."""
    if not block_sent:
        return block, SENT_BLOCK
    return CONTINUATION, SENT_CONTINUATION


# --- integrity helpers (unchanged in kind from earlier revisions) ----------

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def forbidden_markers(run: str, all_runs: list[str], extra: list[str]) -> list[str]:
    marks = list(extra) + [os.path.join("runs", r) for r in all_runs if r != run]
    out = []
    for m in marks:
        out.append(m.replace("\\", "/").lower())
        out.append(m.replace("/", "\\").lower())
    return sorted(set(out))


@dataclass
class RunResult:
    run: str
    outcome: str = HARNESS_ERROR
    reason: str = ""
    turns: int = 0
    artifact: bool = False
    blocks_delivered: int = 0
    continuations_sent: int = 0
    silent_turns: int = 0
    turn_log: list = field(default_factory=list)
    fs_authority: dict = field(default_factory=dict)
    fs_snapshot_before: dict = field(default_factory=dict)
    hashes_before: dict = field(default_factory=dict)
    hashes_after: dict = field(default_factory=dict)


def run_one(run: str, run_dir: Path, block: str, session_factory,
            artifact_name: str = "work_definition.json",
            controlled: dict[str, Path] | None = None,
            all_runs: list[str] | None = None,
            forbidden_extra: list[str] | None = None,
            fs_enforcing: bool = True) -> RunResult:
    """Drive one worker session under the r2 lifecycle.

    `session_factory` returns an object exposing request/drain_agent_text/
    record_lifecycle/close plus `tool_payloads` and `unoffered_requests`, so the
    lifecycle is testable offline with a scripted transport.

    `fs_enforcing=False` puts A4 in SHADOW mode: the pre-run snapshot is
    recorded as data, no verdict is computed in-run, and the filesystem state
    can never terminate, alter, rescue or otherwise influence the run. An
    experiment that wants A4 descriptive rather than binding uses this and
    audits after the complete batch.
    """
    run_dir = Path(run_dir).resolve()
    artifact = run_dir / artifact_name
    res = RunResult(run=run)
    controlled = controlled or {}
    marks = forbidden_markers(run, all_runs or [], forbidden_extra or [])

    if artifact.exists():
        res.outcome = HARNESS_ERROR
        res.reason = f"{artifact_name} already exists; run directory is not fresh"
        return res

    res.hashes_before = {k: sha256_file(v) for k, v in controlled.items()}
    fs_before = A4.snapshot(run_dir)
    res.fs_snapshot_before = fs_before
    prompt_text = (run_dir / "PROMPT.md").read_text(encoding="utf-8")

    s = session_factory()
    try:
        r = s.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False,
                                          "writeTextFile": False}}}, timeout=60)
        if not r or "result" not in r:
            res.outcome, res.reason = HARNESS_ERROR, f"initialize failed: {r}"
            return res
        r = s.request("session/new", {"cwd": str(run_dir), "mcpServers": []},
                      timeout=120)
        if not r or "result" not in r:
            res.outcome, res.reason = HARNESS_ERROR, f"session/new failed: {r}"
            return res
        sid = r["result"]["sessionId"]
        r = s.request("session/set_mode", {"sessionId": sid, "modeId": "auto"},
                      timeout=60)
        if r is None or "error" in r:
            res.outcome, res.reason = HARNESS_ERROR, f"set_mode failed: {r}"
            return res

        message, sent_kind = prompt_text, SENT_PROMPT
        block_sent = False
        silent_streak = 0

        for turn in range(MAX_TURNS + 1):
            res.turns = turn + 1
            r = s.request("session/prompt",
                          {"sessionId": sid,
                           "prompt": [{"type": "text", "text": message}]},
                          timeout=TURN_TIMEOUT_S)

            # --- first artifact wins, always checked first -----------------
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
                res.reason = ("agent issued client-bound request(s) for a "
                              f"capability we never offered: {s.unoffered_requests}")
                break
            if r is None:
                res.outcome = CONTESTED
                res.reason = f"turn {turn + 1} exceeded {TURN_TIMEOUT_S}s"
                break
            if "error" in r:
                res.outcome = HARNESS_ERROR
                res.reason = f"session/prompt error: {json.dumps(r['error'])}"
                break
            if turn == MAX_TURNS:
                res.outcome = CONTESTED
                res.reason = (
                    "BLOCKED_WITH_COMPLETE_INFORMATION: no artifact within "
                    f"{MAX_TURNS} turns although the block was delivered"
                    if block_sent else
                    f"turn limit ({MAX_TURNS}) reached before the block was delivered")
                break

            text = s.drain_agent_text()
            state = classify_lifecycle(text, False, False)

            # --- silent budget: only visible content resets ----------------
            if state == QUIESCENT:
                res.silent_turns += 1
                action, silent_streak = next_silent_action(silent_streak)
                if action == "QUIESCENT_RETRY_LIMIT":
                    entry = {"turn": turn + 1, "lifecycle": QUIESCENT,
                             "silent_streak": silent_streak,
                             "action": action, "sent": None,
                             "agent_turn_text": text}
                    res.turn_log.append(entry)
                    s.record_lifecycle({k: v for k, v in entry.items()
                                        if k != "agent_turn_text"})
                    res.outcome = CONTESTED
                    res.reason = ("QUIESCENT_RETRY_LIMIT: no user-visible content "
                                  f"after {MAX_CONSECUTIVE_SILENT} consecutive "
                                  "re-entries; tool activity does not reset the "
                                  "streak")
                    break
            else:
                silent_streak = 0     # visible content resets -- questions included

            # --- lifecycle separation: what we send never depends on the text
            message, sent_kind = next_message(block_sent, block)
            if sent_kind == SENT_BLOCK:
                block_sent = True
                res.blocks_delivered += 1
            else:
                res.continuations_sent += 1

            entry = {"turn": turn + 1,
                     "lifecycle": state,
                     "silent_streak": silent_streak,
                     "sent": sent_kind,
                     "sent_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
                     "agent_turn_text": text}
            res.turn_log.append(entry)
            s.record_lifecycle({k: v for k, v in entry.items()
                                if k != "agent_turn_text"})
    finally:
        try:
            s.close()
        except Exception:
            pass
        res.hashes_after = {k: sha256_file(v) for k, v in controlled.items()
                            if v.exists()}
        # --- A4: independent, non-lifecycle -----------------------------
        if fs_enforcing:
            res.fs_authority = A4.record(A4.verdict(fs_before,
                                                    A4.snapshot(run_dir),
                                                    designated=artifact_name))
        else:
            # SHADOW: recorded, never decided here.
            res.fs_authority = {"filesystem_authority": "SHADOW_DEFERRED"}

    if res.outcome == COMPLETED:
        changed = [k for k in res.hashes_before
                   if res.hashes_before[k] != res.hashes_after.get(k)]
        if changed:
            res.outcome = CONTESTED
            res.reason = f"controlled input mutated during the run: {changed}"
        elif fs_enforcing and \
                res.fs_authority.get("filesystem_authority") != "CLEAN":
            res.outcome = CONTESTED
            res.reason = f"CONTESTED: {res.fs_authority['reason']}"
    return res
