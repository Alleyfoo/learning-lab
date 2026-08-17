#!/usr/bin/env python3
"""Workspace v0 -- the supervision run, wired through the proven SupervisorHarness.

This replaces the S1 `core.review` surface in the live app. A "Review fleet" run
builds a `SupervisorHarness` with:
  - the `raise_proposal` tool (a `python_analysis`-named tool whose bench
    namespace exposes `raise_proposal(text, evidence)` to file proposals with
    provenance),
  - FleetContext (the snapshot), RulebookContext (rules + the backlog as the
    improvement register), MemoryContext (knowledge / preferences / methods),
and runs the harness loop. The session is saved to `supervisor/runs/<run_id>/`.

The operator prompt extends the S1 broad question with the instruction to use
`raise_proposal` for each distinct improvement worth raising. Routing and
activation happen later, on human demand, from the Improvements page (see
routing.py) -- a run only RAISES.

  streamlit run supervisor/app.py   (the UI; calls review())
"""
from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import core      # noqa: E402  (MODEL, ENDPOINT)
import harness   # noqa: E402  (SupervisorHarness + contexts + save)
import memory    # noqa: E402  (load_knowledge/preferences/methods)
import rulebook  # noqa: E402  (load_rules)
import snapshot as snap_mod  # noqa: E402  (hash_snapshot)

import backlog  # noqa: E402  (the raise_proposal tool + the backlog)

RUNS_DIR = HERE / "runs"

# The v0 operator prompt: the S1 broad question, extended to tell the supervisor
# it has `raise_proposal(text, evidence)` to file each distinct improvement.
PROMPT = """\
You are supervising this fleet. Inspect the available system state using the \
analysis tool, and tell the operator anything you consider worth their attention.

You may also raise improvements you think the system itself should consider. To \
raise an improvement, call `raise_proposal(text, evidence)` in a ```python block, \
where `text` is the proposal and `evidence` is what you observed in the fleet that \
supports it. Raise one proposal per distinct improvement. Do not raise the same \
improvement twice. Do not change the fleet.

When you are ready to give the operator your final summary, write plain prose with \
NO ```python block -- that ends the session.
"""


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _new_run_id(snapshot_hash: str) -> str:
    return f"run-{snapshot_hash[:8]}-{_now_compact()}-{secrets.token_hex(2)}"


def _fleet_shape(snapshot: dict) -> str:
    wc = snapshot.get("worker_count", 0)
    exc = len(snapshot.get("pending_exceptions", []))
    return f"{wc}w-{exc}exc"


def _backlog_as_register() -> list[dict]:
    """The folded backlog rendered as the improvement register for
    RulebookContext (so the model sees already-raised proposals and does not
    re-raise them). rulebook._render_register expects {id, proposal}."""
    return [{"id": r["id"], "proposal": r.get("text", "")}
            for r in backlog.load() if r.get("text")]


def review(snapshot: dict, *,
           rules: Optional[list] = None,
           knowledge: Optional[list] = None,
           preferences: Optional[list] = None,
           methods: Optional[list] = None,
           model: str = core.MODEL, endpoint: str = core.ENDPOINT,
           options: Optional[dict] = None,
           max_turns: int = 6,
           request_timeout: float = 900.0,
           bench_timeout: float = 10.0) -> dict:
    """Run one supervision session over `snapshot` through the SupervisorHarness.

    Loads rules (fresh, so human-activated rules bind), memory (if present), and
    the backlog (as the improvement register). Builds the harness with the
    raise_proposal tool + fleet/rulebook/memory contexts, runs it, and saves the
    session to `supervisor/runs/<run_id>/`. Returns the harness session plus the
    run_id and the proposals raised in this run.
    """
    if rules is None:
        rules = rulebook.load_rules()
    if knowledge is None:
        knowledge = memory.load_knowledge()
    if preferences is None:
        preferences = memory.load_preferences()
    if methods is None:
        methods = memory.load_methods()
    opts = options or {"temperature": 0.2, "num_ctx": 131072}

    snapshot_hash = snap_mod.hash_snapshot(snapshot)
    run_id = _new_run_id(snapshot_hash)
    fleet_shape = _fleet_shape(snapshot)

    tool = backlog.raise_proposal_tool(run_id, snapshot_hash, fleet_shape,
                                       bench_timeout=bench_timeout)
    h = harness.SupervisorHarness(
        tools=[tool],
        contexts=[harness.FleetContext(snapshot),
                  harness.RulebookContext(rules, _backlog_as_register()),
                  harness.MemoryContext(knowledge, preferences, methods)],
        model=model, endpoint=endpoint, options=opts,
        request_timeout=request_timeout, bench_timeout=bench_timeout)
    session = h.run(PROMPT, max_turns=max_turns)

    # persist the session
    run_dir = RUNS_DIR / run_id
    harness.save(session, run_dir / "run.json")
    harness.save_events_jsonl(session, run_dir / "session.jsonl")

    # the proposals raised in this run (from the backlog, by source_run)
    raised = [r for r in backlog.load() if r.get("source_run") == run_id]
    session["run_id"] = run_id
    session["snapshot_hash"] = snapshot_hash
    session["fleet_shape"] = fleet_shape
    session["raised_proposals"] = raised
    return session


# --- self-test (stubbed model; no real Ollama) ------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    global RUNS_DIR
    tmp = Path(tempfile.mkdtemp())
    global_backlog = backlog.BACKLOG_FILE
    backlog.BACKLOG_FILE = tmp / "backlog.jsonl"
    global_runs = RUNS_DIR
    runs_dir = tmp / "runs"
    try:
        RUNS_DIR = runs_dir

        snap = {
            "schema": "supervisor.snapshot/v1", "scopes": ["Acme"],
            "worker_count": 2, "pending_exceptions": [],
            "workers": [
                {"name": "a", "engine": "engA", "trigger": "t0", "effect": None,
                 "current_version": 1,
                 "version_history": [{"version": 1, "digest": "d0"}],
                 "recent_runs": [{"ok": False, "effect_applied": False}]},
                {"name": "b", "engine": "engA", "trigger": "t0", "effect": None,
                 "current_version": 1,
                 "version_history": [{"version": 1, "digest": "d1"}],
                 "recent_runs": []},
            ],
        }

        # stub the model: turn 1 raises a proposal, turn 2 gives final prose
        calls = {"n": 0}

        def stub_chat(messages, *, model, endpoint, options, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return ('I see a failed run. Raising an improvement.\n\n'
                        '```python\nraise_proposal("Track per-worker failure rate over time.", '
                        '"worker a has a failed run with effect_applied=False")\n```')
            return "One failed run worth your attention; I raised one improvement."

        orig = core._chat
        core._chat = stub_chat
        try:
            session = review(snap, max_turns=4, request_timeout=10, bench_timeout=5)
        finally:
            core._chat = orig

        check(session["stop_reason"] == "final",
              f"session ended on final prose: {session['stop_reason']}")
        check(session["run_id"].startswith("run-"),
              f"run_id assigned: {session['run_id']}")
        check(len(session["raised_proposals"]) == 1,
              f"one proposal raised in this run: {len(session['raised_proposals'])}")
        rp = session["raised_proposals"][0]
        check(rp["text"] == "Track per-worker failure rate over time."
              and rp["source_run"] == session["run_id"]
              and rp["provenance"]["snapshot_hash"] == session["snapshot_hash"],
              f"the raised proposal carries text + provenance: {rp}")

        # the session was saved to disk
        run_dir = runs_dir / session["run_id"]
        check((run_dir / "run.json").is_file() and (run_dir / "session.jsonl").is_file(),
              "the session was saved to runs/<run_id>/")

        # the raise line landed in the backlog
        lines = backlog._read(backlog.BACKLOG_FILE)
        check(len(lines) == 1 and lines[0]["kind"] == "raise"
              and lines[0]["source_run"] == session["run_id"],
              "the raise line is in the backlog with the run_id")

        # the harness session shape is intact (reconstructability field present)
        check(session["schema"] == "supervisor.harness.session/v1",
              f"harness session schema intact: {session['schema']}")
        check("reconstructability" in session and "turns" in session,
              "harness session carries reconstructability + turns")
    finally:
        backlog.BACKLOG_FILE = global_backlog
        RUNS_DIR = global_runs
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (review runs through the SupervisorHarness with the "
          "raise_proposal tool / a stub model raises one proposal with provenance "
          "/ the session ends on final prose / the run is saved to runs/<run_id>/ "
          "/ the raise line lands in the backlog with the run_id / the harness "
          "session shape is intact)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)