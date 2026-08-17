#!/usr/bin/env python3
"""Workspace v0.1 -- the human-facing current assessment.

A completed supervision run produces and persists a *current assessment*: the
supervisor's human-facing view of the fleet right now -- findings (what it
noticed), priorities (what matters most, ordered), normal/no-action context
(the "all clear" framing, so the operator can tell a healthy fleet from an
unexamined one), and suggestions (the proposals it raised, which live in the
backlog). This is what the Supervisor Dashboard shows.

The supervisor *files* the assessment itself during the run, by calling
`file_assessment(findings, priorities, normal_context)` in a ```python block
(the same pattern as `raise_proposal`). The model authors the three judgment
fields; the fourth -- suggestions -- is the set of proposals it raised in the
run (already structured in the backlog), so there is no duplication and one
path into the backlog.

Persistence:
  `supervisor/current_assessment.json`  -- the current assessment (overwritten
    each run). This is the Dashboard's source of truth on load, so the app
    shows the last assessment the moment it opens, before any review.
  `supervisor/runs/<run_id>/assessment.json` -- per-run copy for durability,
    alongside the existing run.json + session.jsonl.

If the model never calls `file_assessment`, `filed` is None and the Dashboard
shows a "supervisor did not file a structured assessment" note plus the
final-response narrative and the raised proposals as suggestions -- graceful
degradation, never a crash.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402  (save -- takes any dict, creates parent dirs)

SCHEMA = "supervisor.assessment/v1"
ASSESSMENT_FILE = HERE / "current_assessment.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- the file_assessment callable (injected into the bench namespace) --------

def file_assessment_callable(capture: dict):
    """Return a `file_assessment(findings, priorities, normal_context)` callable
    that writes its (str-cleaned) args into the closure-captured `capture` dict.
    Last call wins. Prints + returns the canary-clean string "assessment filed"
    (the harness feeds tool stdout back to the model).

    `capture` starts empty; if the model never calls this, it stays `{}` and the
    caller passes `capture or None` -> None (the "not filed" case).
    """
    def file_assessment(findings, priorities, normal_context="") -> str:
        capture["findings"] = [str(f) for f in findings] if findings else []
        capture["priorities"] = [str(p) for p in priorities] if priorities else []
        capture["normal_context"] = str(normal_context) if normal_context is not None else ""
        out = "assessment filed"
        print(out)
        return out
    return file_assessment


# --- compose + persist + load ----------------------------------------------

def compose(session: dict, run_id: str, snapshot_hash: str, fleet_shape: str,
             filed: Optional[dict], raised: list[dict],
             elapsed_seconds: float) -> dict:
    """Build the assessment artifact from a completed run.

    `filed` is what the model authored via `file_assessment` (the capture dict),
    or None if it never called it. `raised` is the run's raised proposals (folded
    backlog records with `source_run == run_id`); they become `suggestions`,
    projected to {id, text, evidence}.
    """
    suggestions = [{"id": r.get("id", ""),
                    "text": r.get("text", ""),
                    "evidence": r.get("evidence", "")}
                   for r in raised]
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "at": _now(),
        "snapshot_hash": snapshot_hash,
        "fleet_shape": fleet_shape,
        "filed": filed,
        "suggestions": suggestions,
        "final_response": session.get("final_response"),
        "model": session.get("model"),
        "stop_reason": session.get("stop_reason"),
        "turn_count": session.get("turn_count"),
        "elapsed_seconds": elapsed_seconds,
    }


def save_current(assessment: dict) -> None:
    """Overwrite the current assessment (the Dashboard's source of truth)."""
    harness.save(assessment, ASSESSMENT_FILE)


def save(assessment: dict, path: Path) -> None:
    """Persist a per-run copy of the assessment (durability/history)."""
    harness.save(assessment, path)


def load_current() -> Optional[dict]:
    """The current assessment, or None if no run has produced one yet."""
    if not ASSESSMENT_FILE.is_file():
        return None
    return json.loads(ASSESSMENT_FILE.read_text(encoding="utf-8"))


# --- self-test (no model) ----------------------------------------------------

def _self_test() -> int:
    import shutil
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    global ASSESSMENT_FILE
    real = ASSESSMENT_FILE
    tmp = Path(tempfile.mkdtemp())
    ASSESSMENT_FILE = tmp / "current_assessment.json"
    try:
        # --- file_assessment writes the capture, str-cleaning its args --------
        capture: dict = {}
        fa = file_assessment_callable(capture)
        fa(["worker a failing", "schema drift"], ["fix a first", "then schema"],
           "all clear, nothing needs action")
        check(capture["findings"] == ["worker a failing", "schema drift"],
              f"file_assessment records findings: {capture}")
        check(capture["priorities"] == ["fix a first", "then schema"],
              f"file_assessment records priorities: {capture}")
        check(capture["normal_context"] == "all clear, nothing needs action",
              f"file_assessment records normal_context: {capture}")

        # last call wins
        fa(["only this one"], ["p1"], "fine")
        check(capture["findings"] == ["only this one"],
              "a second file_assessment overwrites the first (last call wins)")

        # --- compose with filed fields + raised proposals as suggestions ------
        session = {"final_response": "narrative prose for the operator",
                   "model": "glm-5.2:cloud", "stop_reason": "final",
                   "turn_count": 3}
        raised = [{"id": "IMP-005", "text": "track per-customer refusals",
                   "evidence": "5 workers with rising refusals", "source_run": "run-1"},
                  {"id": "IMP-006", "text": "schema drift visibility",
                   "evidence": "april-invoicing diverged", "source_run": "run-1"}]
        doc = compose(session, "run-1", "abc123def456", "3w-1exc", capture,
                      raised, 12.5)
        check(doc["schema"] == SCHEMA, f"assessment schema: {doc['schema']}")
        check(doc["run_id"] == "run-1" and doc["snapshot_hash"] == "abc123def456",
              "assessment carries run_id + snapshot_hash")
        check(doc["filed"]["findings"] == ["only this one"],
              "the filed findings survive into the composed artifact")
        check(len(doc["suggestions"]) == 2
              and doc["suggestions"][0]["id"] == "IMP-005"
              and doc["suggestions"][1]["text"] == "schema drift visibility",
              f"suggestions are the raised proposals projected to {{id, text, evidence}}: {doc['suggestions']}")
        check(doc["final_response"] == "narrative prose for the operator",
              "the final-response narrative is carried")
        check(doc["stop_reason"] == "final" and doc["turn_count"] == 3,
              "run metadata is carried")

        # --- save_current / load_current roundtrip ---------------------------
        save_current(doc)
        loaded = load_current()
        check(loaded is not None and loaded["run_id"] == "run-1"
              and loaded["filed"]["findings"] == ["only this one"]
              and len(loaded["suggestions"]) == 2,
              "save_current / load_current roundtrip preserves the artifact")

        # --- save to an arbitrary per-run path -------------------------------
        run_path = tmp / "runs" / "run-1" / "assessment.json"
        save(doc, run_path)
        check(run_path.is_file(), "save(assessment, path) writes a per-run copy")

        # --- filed=None degrades gracefully (model never called it) ----------
        doc2 = compose(session, "run-2", "deadbeef", "2w-0exc", None, [], 5.0)
        check(doc2["filed"] is None,
              "filed is None when the model did not file an assessment")
        check(doc2["suggestions"] == []
              and doc2["final_response"] == "narrative prose for the operator",
              "a not-filed assessment still carries the narrative + empty suggestions")

        # --- load_current with no file -> None -------------------------------
        ASSESSMENT_FILE = tmp / "nonexistent_assessment.json"
        check(load_current() is None,
              "load_current returns None when no assessment has been written")
    finally:
        ASSESSMENT_FILE = real
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (file_assessment writes the capture / last call wins / "
          "compose builds the artifact with filed findings + raised proposals as "
          "suggestions + final-response narrative + run metadata / "
          "save_current + load_current roundtrip / save writes a per-run copy / "
          "filed=None degrades gracefully / load_current returns None when absent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)