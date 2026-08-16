#!/usr/bin/env python3
"""Run S6: frozen S4 through the SupervisorHarness, and compare to old S4.

This is the regression proof for the harness floor. The stimulus, model,
settings, prompt and oracle are all the S4 ones, unchanged. The only new
variable is the execution boundary: the supervisor runs through
`SupervisorHarness.run` instead of `core.review`.

Flow:
  0. Run the harness self-test (no model call) -- the boundary, contract and
     reconstructability invariant must hold before any model call.
  1. Rebuild the frozen S4 fleet (deterministic) and assert the snapshot hash
     matches the oracle stamp a38f6a5a1382ab03 -- canary that the stimulus is
     frozen and identical to the old S4 run.
  2. Run the supervisor through the harness: contexts=[FleetContext] only (cold
     -- no memory, no rulebook), the S1 prompt verbatim as the operator prompt,
     glm-5.2:cloud, temperature=0.2, num_ctx=131072, max_turns=10. The harness
     assembles the system message from contracts (tool contract + authority
     statement), NOT from core.py's prose -- so the model sees a differently
     worded but equivalent prompt. Exact prose/tool calls need not match the
     old run; behaviour and usefulness must.
  3. Assess the harnessed run against the SAME S4 oracle, reusing s4/run.py's
     assess() and SIGNAL_TERMS by import.
  4. Compare harnessed S4 vs old S4 (s4/results/run.json, run_id
     20260816T182432Z) on tool use, turns, errors/recovery, L1..C6 scan
     verdicts, reconstructability, authority. Preserve new misses/surprises.
  5. Preserve session.jsonl (the append-only event log), run.json (the full
     session record + assessment + comparison), evidence.json (the scan).

Usage:
  python s6/run.py            # full run
  python s6/run.py --raw      # also print the harnessed final response
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
# LAB first so `s4` and `s6` resolve as namespace packages (no __init__.py);
# then supervisor, s4 and s6 dirs so their modules import as top-level names.
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(LAB / "s4"))
sys.path.insert(0, str(HERE))

import core          # noqa: E402  (legacy path; stays available)
import harness       # noqa: E402  (the S6 boundary)
import snapshot as snap_mod  # noqa: E402
import build_snapshot as gen  # noqa: E402
import s4.run as s4run   # noqa: E402  (reuse assess + SIGNAL_TERMS)

RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8")
ORACLE = json.loads((HERE.parent / "s4" / "oracle.json").read_text(encoding="utf-8"))
OLD_S4 = json.loads((HERE.parent / "s4" / "results" / "run.json").read_text(encoding="utf-8"))

OPTIONS = {"temperature": 0.2, "num_ctx": 131072}
MAX_TURNS = 10
REQUEST_TIMEOUT = 900.0
BENCH_TIMEOUT = 10.0


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _shape_for_assess(session: dict) -> dict:
    """Adapt a harness session record to the shape s4.run.assess() expects.

    assess() reads record['final_response'], record['turns'][i]['assistant']
    and record['turns'][i]['python_calls'][j] (ok/refused/stdout/error), plus
    record['python_used'] / record['python_call_count'] / record['stop_reason']
    / record['turn_count']. The harness session already has all of these in the
    same shape (by design), so this is mostly a passthrough with the fields
    assess() needs surfaced.
    """
    return {
        "final_response": session["final_response"],
        "turns": session["turns"],
        "python_used": session["python_used"],
        "python_call_count": session["python_call_count"],
        "stop_reason": session["stop_reason"],
        "turn_count": session["turn_count"],
    }


def _compare(old: dict, new_assess: dict, new_session: dict) -> dict:
    """Old S4 vs harnessed S4, on the dimensions the spec names."""
    old_a = old["assessment"]
    old_scan = {sid: s["verdict"] for sid, s in old_a["by_signal"].items()}
    new_scan = {sid: s["verdict"] for sid, s in new_assess["by_signal"].items()}
    scan_delta = {sid: {"old": old_scan.get(sid), "new": new_scan.get(sid)}
                  for sid in sorted(set(old_scan) | set(new_scan))}
    # error/recovery: count python calls that errored (ok=False, refused=False)
    def _errors(assess):
        return [c for c in assess["python_calls"]
                if not c["ok"] and not c["refused"]]
    return {
        "old_run_id": old.get("run_id"),
        "new_run_id": new_session.get("run_id"),
        "tool_use": {
            "old": {"python_used": old_a["python_used"],
                    "python_calls": old_a["python_call_count"]},
            "new": {"python_used": new_assess["python_used"],
                    "python_calls": new_assess["python_call_count"]},
        },
        "turns": {
            "old": old_a["turn_count"], "new": new_assess["turn_count"],
        },
        "stop_reason": {"old": old_a["stop_reason"], "new": new_assess["stop_reason"]},
        "errors": {
            "old_count": len(_errors(old_a)),
            "new_count": len(_errors(new_assess)),
            "new_errors": [{"turn": e["turn"], "error": e["error"]}
                           for e in _errors(new_assess)],
        },
        "scan_verdicts": {"old": old_scan, "new": new_scan},
        "scan_delta": scan_delta,
        "reconstructability": new_session["reconstructability"],
        "authority": {
            "allow": new_session["authority"]["allow"],
            "never": new_session["authority"]["never"],
            "tool_authority_classes": {
                t: "analyse_copied_data" for t in new_session["tool_names"]},
        },
        "note": ("Exact prose and tool calls need not match. The harness "
                 "assembles the system message from contracts, not core.py's "
                 "prose, so the model sees a differently-worded but equivalent "
                 "prompt. We compare behaviour and usefulness, not transcripts."),
    }


def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    RESULTS.mkdir(parents=True, exist_ok=True)

    # 0. harness self-test (no model call)
    print("=== S6 HARNESS SELF-TEST (no model call) ===", flush=True)
    if harness._self_test() != 0:
        sys.stderr.write("SELF-TEST FAILED -- aborting before any model call.\n")
        return 1

    # 1. rebuild the frozen S4 fleet and canary the hash (same as s4/run.py)
    print("\n=== S6 BUILD (frozen S4 fleet; reference-assert signals) ===",
          flush=True)
    stats = gen.build()
    snap = snap_mod.build(gen.OUT)
    snap_hash = snap_mod.hash_snapshot(snap)
    print(f"  workers={stats['worker_count']} runs={stats['runs_total']} "
          f"hash={snap_hash}")
    if snap_hash != ORACLE["stats"]["snapshot_hash"]:
        sys.stderr.write(
            f"CANARY FAILED: snapshot hash {snap_hash} != oracle "
            f"{ORACLE['stats']['snapshot_hash']}\n"
            "The fleet is not the frozen S4 stimulus. Aborting before any "
            "model call.\n")
        return 1
    print(f"  hash matches oracle ({snap_hash}) -- stimulus frozen, identical "
          f"to old S4")

    # 2. run the supervisor through the harness (cold; S1 prompt; no memory)
    print("\n=== S6 RUN (harnessed; cold; S1 prompt; num_ctx=131072; "
          f"max_turns={MAX_TURNS}) ===", flush=True)
    print("  boundary: SupervisorHarness.run (NOT core.review)", flush=True)
    print("  contexts: [FleetContext] only (no memory, no rulebook)", flush=True)
    print("  tools: [python_analysis] (fresh namespace declared in contract)",
          flush=True)
    h = harness.SupervisorHarness(
        tools=[harness.python_analysis_tool(BENCH_TIMEOUT)],
        contexts=[harness.FleetContext(snap)],
        options=OPTIONS, request_timeout=REQUEST_TIMEOUT,
        bench_timeout=BENCH_TIMEOUT)
    session = h.run(PROMPT, max_turns=MAX_TURNS)
    session["run_id"] = _stamp()
    session["expectation"] = {"oracle": ORACLE, "spec": "s6/spec.md"}

    # 3. assess against the SAME S4 oracle (reuse s4/run.py assess + SIGNAL_TERMS)
    print("\n=== S6 ASSESS (against frozen S4 oracle; same scan as old S4) ===",
          flush=True)
    assessable = _shape_for_assess(session)
    evidence = s4run.assess(assessable, ORACLE)
    evidence["run_id"] = session["run_id"]
    evidence["snapshot_hash"] = snap_hash
    evidence["stop_reason"] = session["stop_reason"]
    evidence["turn_count"] = session["turn_count"]
    session["assessment"] = evidence

    # 4. compare old vs harnessed S4
    comparison = _compare(OLD_S4, evidence, session)
    session["comparison"] = comparison

    # 5. preserve
    harness.save(session, RESULTS / "run.json")
    harness.save_events_jsonl(session, RESULTS / "session.jsonl")
    (RESULTS / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (RESULTS / "comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # 6. summary
    print("\n=== S6 RESULT ===", flush=True)
    print(f"  python_used={evidence['python_used']}  "
          f"python_calls={evidence['python_call_count']}  "
          f"turns={evidence['turn_count']}  stop={evidence['stop_reason']}")
    print(f"  verdicts: {evidence['verdict_counts']}")
    for sid in ("L1", "L2", "C1", "C2", "C3", "C5", "C6"):
        s = evidence["by_signal"][sid]
        d = comparison["scan_delta"][sid]
        print(f"    {sid}: new={s['verdict']:7s}  (old={d['old']})  "
              f"disc={s['disc_hit'] or '-'}")
    print(f"  errors: old={comparison['errors']['old_count']} "
          f"new={comparison['errors']['new_count']}")
    print(f"  reconstructability: {session['reconstructability']}")
    if evidence["python_calls"]:
        print("  python calls (first lines of stdout):")
        for pc in evidence["python_calls"]:
            tag = "ok" if pc["ok"] else ("refused" if pc["refused"] else "err")
            print(f"    turn {pc['turn']} [{tag}] {pc['stdout_head']!r}"
                  + (f"  err={pc['error']}" if pc["error"] else ""))
    print(f"\n  preserved: {RESULTS / 'run.json'}")
    print(f"  preserved: {RESULTS / 'session.jsonl'}")
    print(f"  preserved: {RESULTS / 'evidence.json'}")
    print(f"  preserved: {RESULTS / 'comparison.json'}")
    if raw:
        print("\n=== HARNESSED FINAL RESPONSE ===\n"
              + (session.get("final_response") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))