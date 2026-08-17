#!/usr/bin/env python3
"""Workspace v0 -- the persistent append-only Improvements backlog.

The supervisor's job during a run is to RAISE improvement proposals (with
evidence + provenance). Routing and activation happen later, on human demand,
from the Streamlit Improvements page. This module is the durable record of
every proposal's life: raised -> routed -> (for NEW_RULE+proposed) activatable
-> active.

It is a genuinely append-only audit log: one JSON object per line in
`supervisor/backlog.jsonl`, folded by `id` on load (mirrors how S14's
`proposed_rules.jsonl` had a separate `approval_of` line). Nothing is ever
rewritten or deleted; later amendment lines extend a proposal's record.

Amendment kinds:
  raise    -- {kind:"raise", id, at, source_run, text, evidence,
              provenance:{snapshot_hash, fleet_shape}}
             written by raise_proposal() during a supervision run.
  route    -- {kind:"route", id, at, suggested_route, route_metadata:{...}}
             written by routing.route() (the S14/S15 routing desk).
  activate -- {kind:"activate", id, at, rule_id, area, statement,
              activated_by:"human"}
             written by routing.activate() (the human-gated step that also
             appends the rule to rulebook.jsonl).

The historical `supervisor/improvements.jsonl` (the S3 artifact, IMP-001..004)
is a separate file and is left untouched. `next_id()` continues past it so the
first v0 proposal is IMP-005, never colliding with the S3 register.

This module also builds the `raise_proposal` harness tool: a `harness.Tool`
named `python_analysis` (the name the harness dispatches every fenced ```python
block to) whose bench namespace injects `raise_proposal(text, evidence)`
alongside the usual `snapshot`. That is how the supervisor files structured
proposals with provenance inside the proven SupervisorHarness path.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench    # noqa: E402  (restricted namespace + timed exec)
import harness  # noqa: E402  (the Tool contract / authority)
import rulebook  # noqa: E402  (the historical improvements.jsonl, for next_id)

BACKLOG_FILE = HERE / "backlog.jsonl"
IMPROVEMENTS_FILE = HERE / "improvements.jsonl"  # the S3 artifact, read-only here

_IMP_RE = re.compile(r"IMP-(\d+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def append(entry: dict) -> dict:
    """Append one amendment line to the backlog (never rewrite)."""
    BACKLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with BACKLOG_FILE.open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _existing_imp_numbers() -> list[int]:
    """IMP-NNN numbers already used in the backlog AND the S3 improvements file,
    so v0 ids continue past the historical register without colliding."""
    nums: list[int] = []
    for path in (BACKLOG_FILE, IMPROVEMENTS_FILE):
        for e in _read(path):
            m = _IMP_RE.search(str(e.get("id", "")))
            if m:
                nums.append(int(m.group(1)))
    return nums


def next_id() -> str:
    """The next IMP id, continuing past the historical S3 register (IMP-001..004).
    With an empty backlog and the S3 file present, the first v0 id is IMP-005."""
    nums = _existing_imp_numbers()
    n = (max(nums) + 1) if nums else 1
    return f"IMP-{n:03d}"


# --- the folded record (one per proposal id) -------------------------------

def _state_of(rec: dict) -> str:
    """raised -> routed -> activatable -> active."""
    if rec.get("activated_at"):
        return "active"
    rmeta = rec.get("route_metadata") or {}
    route = rec.get("suggested_route")
    if route is None:
        return "raised"
    # a NEW_RULE that reached state=proposed is pending human activation
    if route == "NEW_RULE" and rmeta.get("lifecycle_state") == "proposed":
        return "activatable"
    return "routed"


def load() -> list[dict]:
    """Fold the append-only backlog into one record per proposal id, in raise
    order. Each record: {id, raised_at, source_run, text, evidence, provenance,
    suggested_route, route_metadata, rule_id, activated_at, state}.
    """
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for e in _read(BACKLOG_FILE):
        iid = e.get("id")
        if iid is None:
            continue
        if iid not in by_id:
            by_id[iid] = {"id": iid}
            order.append(iid)
        rec = by_id[iid]
        kind = e.get("kind")
        if kind == "raise":
            rec["raised_at"] = e.get("at")
            rec["source_run"] = e.get("source_run")
            rec["text"] = e.get("text")
            rec["evidence"] = e.get("evidence")
            rec["provenance"] = e.get("provenance")
        elif kind == "route":
            rec["routed_at"] = e.get("at")
            rec["suggested_route"] = e.get("suggested_route")
            rec["route_metadata"] = e.get("route_metadata")
        elif kind == "activate":
            rec["activated_at"] = e.get("at")
            rec["rule_id"] = e.get("rule_id")
            rec["area"] = e.get("area")
            rec["statement"] = e.get("statement")
    out = []
    for iid in order:
        rec = by_id[iid]
        rec["state"] = _state_of(rec)
        out.append(rec)
    return out


def get(imp_id: str) -> Optional[dict]:
    """The folded record for one proposal id, or None."""
    for rec in load():
        if rec["id"] == imp_id:
            return rec
    return None


# --- the raise_proposal harness tool ---------------------------------------

def raise_proposal_tool(run_id: str, snapshot_hash: str, fleet_shape: str, *,
                         bench_timeout: float = 10.0) -> "harness.Tool":
    """A `harness.Tool` named `python_analysis` (the name the harness dispatches
    every fenced ```python block to) that runs the model's analysis code against
    a COPY of the snapshot AND exposes `raise_proposal(text, evidence)` to file
    an improvement proposal with provenance.

    Modelled on `harness.python_analysis_tool` and S13's `_desk_analysis_tool`:
    execute() builds the namespace via `bench._build_namespace`, injects the
    `raise_proposal` closure, then runs the code via `bench._exec_timed`. The
    authority class is `write_improvement_proposals` -- the new power granted
    (analysis-over-a-copy remains bench-enforced as read-only).
    """
    def raise_proposal(text: str, evidence: str = "") -> str:
        imp_id = next_id()
        append({"kind": "raise", "id": imp_id, "at": _now(),
                "source_run": run_id, "text": str(text),
                "evidence": str(evidence) if evidence is not None else "",
                "provenance": {"snapshot_hash": snapshot_hash,
                               "fleet_shape": fleet_shape}})
        out = f"raised: {imp_id}"
        print(out)
        return out

    def execute(inp: dict, state: dict) -> dict:
        code = inp.get("code", "")
        snap = state.get("snapshot", {})
        ns = bench._build_namespace(copy.deepcopy(snap))
        ns["raise_proposal"] = raise_proposal
        stdout, _v, error = bench._exec_timed(code, ns, bench_timeout)
        return {
            "ok": error is None,
            "stdout": stdout[:20000],
            "stdout_truncated": len(stdout) > 20000,
            "error": error,
            "refused": isinstance(error, str) and error.startswith("BenchError"),
        }

    return harness.Tool(
        name="python_analysis",
        description=(
            "Run a Python analysis snippet against a COPY of the fleet snapshot, "
            "and/or file an improvement proposal. You do not have to use it.\n\n"
            "IMPORTANT -- fresh namespace per call: each call runs in a fresh, "
            "INDEPENDENT namespace. Variables, imports and bindings you create "
            "in one call DO NOT persist to the next call. Re-bind anything you "
            "need at the top of EVERY call (for example "
            "`workers = snapshot[\"workers\"]`).\n\n"
            "The snapshot is available as `snapshot` (a plain Python dict). "
            "`json`, `math`, `re`, `collections` and `pandas` (as `pd`) are "
            "available; any other import is refused. There is no file, shell or "
            "network access. Output you `print()` is returned to you.\n\n"
            "To file an improvement proposal for the operator, call "
            "`raise_proposal(text, evidence)` where `text` is the proposal and "
            "`evidence` is what you observed that supports it. Each call appends "
            "one proposal to the durable backlog with its provenance; it returns "
            "`raised: IMP-NNN`. Use it once per distinct improvement you want to "
            "raise. Proposals are routed and activated later by the operator.\n\n"
            "To use it, emit a fenced ```python block containing your code. "
            "When you are ready to tell the operator your findings, write plain "
            "prose with NO ```python block -- that ends the session."
        ),
        input_schema={"type": "object",
                      "properties": {"code": {"type": "string"}},
                      "required": ["code"]},
        output_schema={"type": "object",
                       "properties": {
                           "ok": {"type": "boolean"},
                           "stdout": {"type": "string"},
                           "error": {"type": ["string", "null"]},
                           "refused": {"type": "boolean"},
                           "stdout_truncated": {"type": "boolean"}}},
        authority_class="write_improvement_proposals",
        execute=execute,
    )


# --- self-test -------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    tmp = Path(tempfile.mkdtemp())
    global BACKLOG_FILE, IMPROVEMENTS_FILE
    bfile, ifile = BACKLOG_FILE, IMPROVEMENTS_FILE
    BACKLOG_FILE = tmp / "backlog.jsonl"
    IMPROVEMENTS_FILE = tmp / "improvements.jsonl"
    try:
        # --- next_id starts at IMP-001 with no S3 file, IMP-005 with it ------
        check(next_id() == "IMP-001", "next_id starts at IMP-001 with empty stores")
        # simulate the S3 historical register
        IMPROVEMENTS_FILE.write_text(
            json.dumps({"id": "IMP-001", "proposal": "x"}) + "\n"
            + json.dumps({"id": "IMP-004", "proposal": "y"}) + "\n",
            encoding="utf-8")
        check(next_id() == "IMP-005",
              "next_id continues past the historical S3 register -> IMP-005")

        # --- the raise_proposal tool files a raise line with provenance -------
        tool = raise_proposal_tool("run-test-001", "deadbeef", "3w-1exc",
                                   bench_timeout=5)
        check(tool.name == "python_analysis",
              "raise_proposal_tool is named python_analysis (harness dispatch name)")
        check(tool.authority_class == "write_improvement_proposals",
              "raise_proposal_tool authority is write_improvement_proposals")
        outcome = tool.execute(
            {"code": "raise_proposal('Track per-customer refusal rate over time.', "
                     "'observed 5 workers with rising refusals')"},
            {"snapshot": {"worker_count": 3}})
        check(outcome["ok"] and "raised: IMP-005" in outcome["stdout"],
              f"raise_proposal filed IMP-005 and returned canary-clean stdout: {outcome}")
        # the raise line landed in the backlog
        lines = _read(BACKLOG_FILE)
        check(len(lines) == 1 and lines[0]["kind"] == "raise"
              and lines[0]["id"] == "IMP-005"
              and lines[0]["source_run"] == "run-test-001"
              and lines[0]["provenance"]["snapshot_hash"] == "deadbeef",
              f"raise line persisted with provenance: {lines[0]}")

        # the tool still runs plain analysis against the snapshot copy
        out2 = tool.execute({"code": "print(snapshot['worker_count'])"},
                            {"snapshot": {"worker_count": 3}})
        check(out2["ok"] and out2["stdout"].strip() == "3",
              f"the tool still runs plain analysis against the snapshot copy: {out2}")

        # --- fold: raise -> routed -> activatable -> active state machine ----
        # raise a second proposal, then route it as a MEASUREMENT
        check(next_id() == "IMP-006", "second proposal is IMP-006")
        append({"kind": "raise", "id": "IMP-006", "at": "t2", "source_run": "r2",
                "text": "second proposal", "evidence": "ev2", "provenance": {}})
        recs = load()
        check(len(recs) == 2 and recs[0]["id"] == "IMP-005"
              and recs[1]["id"] == "IMP-006",
              "load folds in raise order")
        check(all(r["state"] == "raised" for r in recs),
              "both proposals start in state=raised")

        # route IMP-006 as a measurement -> state routed
        append({"kind": "route", "id": "IMP-006", "at": "t3",
                "suggested_route": "MEASUREMENT",
                "route_metadata": {"restated_rule": None, "conflicts_with": [],
                                   "compatible": True,
                                   "mandatory_gate": {"ran": False, "caught": False,
                                                      "demoted": False,
                                                      "restates": None},
                                   "rule_draft": None, "lifecycle_state": None}})
        rec6 = get("IMP-006")
        check(rec6["state"] == "routed" and rec6["suggested_route"] == "MEASUREMENT",
              f"after a MEASUREMENT route, state=routed: {rec6['state']}")

        # route IMP-005 as a NEW_RULE that reached proposed -> state activatable
        append({"kind": "route", "id": "IMP-005", "at": "t4",
                "suggested_route": "NEW_RULE",
                "route_metadata": {"restated_rule": None, "conflicts_with": [],
                                   "compatible": True,
                                   "mandatory_gate": {"ran": True, "caught": False,
                                                      "demoted": False,
                                                      "restates": None},
                                   "rule_draft": "A shared engine change requires staged verification.",
                                   "lifecycle_state": "proposed"}})
        rec5 = get("IMP-005")
        check(rec5["state"] == "activatable",
              f"a NEW_RULE+proposed route -> state=activatable: {rec5['state']}")
        check(rec5["route_metadata"]["rule_draft"].startswith("A shared engine"),
              "the rule draft is carried in route_metadata")

        # activate IMP-005 -> state active
        append({"kind": "activate", "id": "IMP-005", "at": "t5",
                "rule_id": "R-IMP-005", "area": "versions",
                "statement": "A shared engine change requires staged verification.",
                "activated_by": "human"})
        rec5 = get("IMP-005")
        check(rec5["state"] == "active" and rec5["rule_id"] == "R-IMP-005",
              f"after activation, state=active with a rule_id: {rec5['state']}")

        # --- a demoted restatement routes to DUPLICATE_RULE, never activatable -
        append({"kind": "raise", "id": "IMP-007", "at": "t6", "source_run": "r3",
                "text": "re-confirm after promotion", "evidence": "ev3",
                "provenance": {}})
        append({"kind": "route", "id": "IMP-007", "at": "t7",
                "suggested_route": "DUPLICATE_RULE",
                "route_metadata": {"restated_rule": "R-CONFIRM-VERSION",
                                   "conflicts_with": [], "compatible": True,
                                   "mandatory_gate": {"ran": True, "caught": True,
                                                      "demoted": True,
                                                      "restates": "R-CONFIRM-VERSION"},
                                   "rule_draft": None, "lifecycle_state": None}})
        rec7 = get("IMP-007")
        check(rec7["state"] == "routed" and rec7["suggested_route"] == "DUPLICATE_RULE",
              "a demoted restatement routes to DUPLICATE_RULE, state=routed (not activatable)")

        # --- the append-only log is never rewritten; all amendments survive ---
        raw = _read(BACKLOG_FILE)
        kinds = [e["kind"] for e in raw]
        check(kinds.count("raise") == 3 and kinds.count("route") == 3
              and kinds.count("activate") == 1,
              f"the append-only log preserves every amendment line: {kinds}")
    finally:
        BACKLOG_FILE, IMPROVEMENTS_FILE = bfile, ifile
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (next_id continues past the S3 register / "
          "raise_proposal_tool is named python_analysis with the right authority / "
          "it files a raise line with provenance and still runs plain analysis / "
          "load folds amendments in raise order / "
          "the state machine raised->routed->activatable->active holds / "
          "a demoted DUPLICATE_RULE is routed not activatable / "
          "the append-only log preserves every amendment line)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)