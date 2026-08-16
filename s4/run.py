#!/usr/bin/env python3
"""Run S4: the cold supervisor over the large frozen fleet.

The supervisor runs with NO memory and the broad S1 prompt unchanged. The only
new variable is scale. We record every turn and every Python bench call, then
assess the run against the frozen oracle (`s4/oracle.json`).

Flow:
  1. Rebuild the frozen fleet (deterministic) and assert the snapshot hash
     matches the one stamped in the oracle -- canary that the stimulus is frozen.
  2. Run `core.review` cold: no knowledge, no preferences, the S1 prompt verbatim,
     num_ctx=131072, max_turns=10.
  3. Attach the oracle as the run's expectation slot.
  4. First-pass evidence scan of the full transcript against each signal's
     criterion (names + signal-specific terms). This is a reproducible hint, NOT
     the authoritative verdict -- that is hand-judged in FINDINGS.md, because
     "lists some refusals" is not the same finding as "names the rising trend".
  5. Preserve the raw run record and the evidence scan.

Usage:
  python s4/run.py            # full run
  python s4/run.py --raw      # also print the final response to stdout
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(HERE))

import core  # noqa: E402
import snapshot as snap_mod  # noqa: E402
import build_snapshot as gen  # noqa: E402

RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8")
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))

OPTIONS = {"temperature": 0.2, "num_ctx": 131072}
MAX_TURNS = 10


# --- first-pass evidence scan ------------------------------------------------

# Each signal: the worker names planted, core terms (the topic), and
# discriminating terms (what separates a real hit from a glancing mention).
# A name mention is strong evidence on its own; otherwise we want BOTH a core
# term and a discriminating term to propose HIT.
SIGNAL_TERMS = {
    "L1": {"names": ["reserv-acme-failed-effect"],
           "core": ["reserv", "effect", "permission"],
           "disc": ["failed effect", "effect_applied", "effect failed",
                    "permissionerror", "append_to_reservations", "investigation"]},
    "L2": {"names": ["enrich-fazerish-open-inv"],
           "core": ["enrich", "field_not_in_source", "article"],
           "disc": ["field_not_in_source", "price_list.article", "article",
                    "investigation", "open inv"]},
    "C1": {"names": [f"northwind-orders-{i:02d}" for i in range(1, 9)],
           "core": ["northwind", "refus"],
           "disc": ["trend", "increasing", "rising", "climbing", "degrad",
                    "declin", "over time", "worsen", "worsening", "creeping",
                    "upward"]},
    "C2": {"names": [f"promo-regress-{i:02d}" for i in range(1, 6)],
           "core": ["promot", "refus", "regress"],
           "disc": ["regress", "after promotion", "post-promotion", "v2",
                    "current version", "new version", "since promotion"]},
    "C3": {"names": [f"confirm-stale-{i:02d}" for i in range(1, 11)],
           "core": ["confirm"],
           "disc": ["stale", "older version", "outdated", "re-confirm",
                    "not re-confirmed", "carried over", "superseded",
                    "v1", "prior version", "un-inherited", "uninherited"]},
    "C5": {"names": [],
           "core": ["enrichment", "engine"],
           "disc": ["concentrat", "most of", "majority", "60 of", "of 70",
                    "share", "single engine", "one engine", "common engine",
                    "disproportionate", "all on"]},
    "C6": {"names": [f"hidden-exception-{i:02d}" for i in range(1, 7)],
           "core": ["exception", "pending_exceptions"],
           "disc": ["not in", "not reflected", "missing", "gap", "hidden",
                    "visibility", "d-001", "exception_files", "absent",
                    "not surfaced", "not escalated", "6 workers", "six workers"]},
}


def _corpus(record: dict) -> str:
    """Lowercased text of the final response + every turn's assistant text and
    python stdout -- everything the supervisor produced or saw from the bench."""
    parts = [record.get("final_response") or ""]
    for t in record.get("turns", []):
        parts.append(t.get("assistant", "") or "")
        for c in t.get("python_calls", []):
            parts.append(c.get("stdout", "") or "")
            parts.append(c.get("error", "") or "")
    return "\n".join(parts).lower()


def _scan_signal(sig_id: str, text: str) -> dict:
    terms = SIGNAL_TERMS[sig_id]
    names_hit = [n for n in terms["names"] if n.lower() in text]
    core_hit = [t for t in terms["core"] if t in text]
    disc_hit = [t for t in terms["disc"] if t in text]
    if names_hit or (core_hit and disc_hit):
        verdict = "HIT"
    elif core_hit or disc_hit or names_hit:
        verdict = "PARTIAL"
    else:
        verdict = "MISS"
    return {"verdict": verdict, "names_hit": names_hit,
            "core_hit": core_hit, "disc_hit": disc_hit}


def assess(record: dict, oracle: dict) -> dict:
    text = _corpus(record)
    by_signal = {}
    for sig in oracle["signals"]:
        s = _scan_signal(sig["id"], text)
        s["criterion"] = sig["criterion"]
        s["kind"] = sig["kind"]
        s["location"] = sig["location"]
        by_signal[sig["id"]] = s
    # python-use summary (the primary research variable)
    pcs = []
    for t in record.get("turns", []):
        for c in t.get("python_calls", []):
            pcs.append({"turn": t["turn"], "ok": c["ok"],
                        "refused": c["refused"],
                        "stdout_head": (c.get("stdout") or "")[:200],
                        "error": c.get("error")})
    counts = {v: sum(1 for s in by_signal.values() if s["verdict"] == v)
              for v in ("HIT", "PARTIAL", "MISS")}
    return {"python_used": record["python_used"],
            "python_call_count": record["python_call_count"],
            "python_calls": pcs,
            "verdict_counts": counts,
            "by_signal": by_signal}


# --- main --------------------------------------------------------------------

def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    RESULTS.mkdir(parents=True, exist_ok=True)

    # 1. rebuild the frozen fleet and canary the hash
    print("=== S4 BUILD (deterministic; reference-assert signals) ===", flush=True)
    stats = gen.build()
    snap = snap_mod.build(gen.OUT)
    snap_hash = snap_mod.hash_snapshot(snap)
    print(f"  workers={stats['worker_count']} runs={stats['runs_total']} "
          f"hash={snap_hash}")
    if snap_hash != ORACLE["stats"]["snapshot_hash"]:
        sys.stderr.write(
            f"CANARY FAILED: snapshot hash {snap_hash} != oracle "
            f"{ORACLE['stats']['snapshot_hash']}\n"
            "The fleet is not frozen as the oracle expects. Aborting before any "
            "model call.\n")
        return 1
    print(f"  hash matches oracle ({snap_hash}) -- stimulus frozen")

    # 2. run the cold supervisor
    print("\n=== S4 RUN (cold; no memory; S1 prompt; num_ctx=131072; "
          f"max_turns={MAX_TURNS}) ===", flush=True)
    record = core.review(snap, PROMPT, max_turns=MAX_TURNS, options=OPTIONS,
                         knowledge=None, preferences=None, request_timeout=900)
    record["run_id"] = _stamp()
    record["expectation"] = {"oracle": ORACLE, "spec": "s4/spec.md"}

    # 3. assess against the oracle
    evidence = assess(record, ORACLE)
    evidence["run_id"] = record["run_id"]
    evidence["snapshot_hash"] = snap_hash
    evidence["stop_reason"] = record["stop_reason"]
    evidence["turn_count"] = record["turn_count"]
    record["assessment"] = evidence

    # 4. preserve
    core.save(record, RESULTS / "run.json")
    (RESULTS / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # 5. summary
    print("\n=== S4 RESULT ===", flush=True)
    print(f"  python_used={evidence['python_used']}  "
          f"python_calls={evidence['python_call_count']}  "
          f"turns={evidence['turn_count']}  stop={evidence['stop_reason']}")
    print(f"  verdicts: {evidence['verdict_counts']}")
    for sid in ("L1", "L2", "C1", "C2", "C3", "C5", "C6"):
        s = evidence["by_signal"][sid]
        print(f"    {sid}: {s['verdict']:7s}  "
              f"names={s['names_hit'] or '-'}  disc={s['disc_hit'] or '-'}")
    if evidence["python_calls"]:
        print("  python calls (first lines of stdout):")
        for pc in evidence["python_calls"]:
            tag = "ok" if pc["ok"] else ("refused" if pc["refused"] else "err")
            print(f"    turn {pc['turn']} [{tag}] {pc['stdout_head']!r}"
                  + (f"  err={pc['error']}" if pc["error"] else ""))
    print(f"\n  preserved: {RESULTS / 'run.json'}")
    print(f"  preserved: {RESULTS / 'evidence.json'}")
    if raw:
        print("\n=== FINAL RESPONSE ===\n" + (record.get("final_response") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))