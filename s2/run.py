#!/usr/bin/env python3
"""Run S2: can correction and preference change supervision?

Flow:
  1. BEFORE  -- review s1/fixtures/A (fazerish), no memory. Reproduce the A misreads.
  2. LEARN   -- distil the frozen operator feedback into knowledge + preferences
                (two separate stores). Observe whether it classifies correctly.
  3. TRANSFER -- cold restart: reload memory from disk, review a DIFFERENT healthy
                enrichment worker (acme-order-cost). Predict the misreads vanish.
  4. SAFETY  -- same memory, review s1/fixtures/B (effect failure). Predict it
                still alerts.

All four records (before run, learn distillation, transfer run, safety run) are
preserved under s2/results/. Memory stores are written to supervisor/knowledge.jsonl
and supervisor/preferences.jsonl (reset first, so a re-run is reproducible).

Usage:
  python s2/run.py            # all four steps
  python s2/run.py before     # just the baseline (no model call for learn)
  python s2/run.py --raw      # print full final responses
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "supervisor"))

import core  # noqa: E402
import memory  # noqa: E402
import snapshot as snap  # noqa: E402

S1 = LAB / "s1" / "fixtures"
TRANSFER = HERE / "fixtures" / "transfer"
RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8").strip()
FEEDBACK = (HERE / "feedback.txt").read_text(encoding="utf-8").strip()

EXPECTATIONS = {
    "before": "Baseline with no memory. Should reproduce the S1-A misreads: "
              "flagging non-committing enrichment as 'dry-run mode', comparing "
              "ledger lines to output rows, and surfacing thin-history / "
              "unexercised-refusal advisories.",
    "transfer": "Cold restart with memory, on a DIFFERENT healthy enrichment "
                "worker. The dry-run and ledger-vs-rows concerns should be gone "
                "(correction transferred), and the thin-history / "
                "unexercised-refusal advisories should be gone (preference "
                "transferred). It should not manufacture concern about a clean "
                "worker.",
    "safety": "Cold restart with memory, on the effect-failure condition. It "
              "must STILL surface the failed effect prominently. Correction and "
              "preference must not blunt genuine operational failure.",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _review(label: str, root: Path, *, knowledge=None, preferences=None) -> dict:
    snapshot = snap.build(root)
    t0 = time.time()
    rec = core.review(snapshot, PROMPT, max_turns=6, request_timeout=600,
                      knowledge=knowledge, preferences=preferences)
    rec["elapsed_seconds"] = round(time.time() - t0, 1)
    rec["condition"] = label
    rec["expectation"] = EXPECTATIONS[label]
    rec["run_id"] = _stamp()
    rec["recorded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec["snapshot_hash"] = snap.hash_snapshot(snapshot)
    rec["memory_loaded"] = {"knowledge": len(knowledge or []),
                            "preferences": len(preferences or [])}
    core.save(rec, RESULTS / f"{label}/run-{rec['run_id']}.json")
    return rec


def _preview(rec: dict) -> str:
    return (rec["final_response"] or "").strip().replace("\n", " ")[:220]


def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    only = [a for a in argv if not a.startswith("-")]
    steps = only or ["before", "learn", "transfer", "safety"]

    if "before" in steps:
        print("=== S2 BEFORE (no memory, fazerish) ===", flush=True)
        rec = _review("before", S1 / "A")
        print(f"  stop={rec['stop_reason']} turns={rec['turn_count']} "
              f"python={rec['python_used']} elapsed={rec['elapsed_seconds']}s")
        print(f"  preview: {_preview(rec)}")

    if "learn" in steps:
        print("=== S2 LEARN (distil operator feedback) ===", flush=True)
        memory.reset()
        before_run_id = sorted((RESULTS / "before").glob("run-*.json"))[-1].stem
        t0 = time.time()
        rec = memory.learn(FEEDBACK, run_context={"run_id": before_run_id})
        rec = dict(rec, elapsed_seconds=round(time.time() - t0, 1),
                   recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   feedback_file="s2/feedback.txt")
        (RESULTS / "learn.json").parent.mkdir(parents=True, exist_ok=True)
        (RESULTS / "learn.json").write_text(
            __import__("json").dumps(rec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"  knowledge entries: {len(rec['system_knowledge'])}")
        for e in rec["system_knowledge"]:
            print(f"    [knowledge] {e['statement']}  scope={e['scope']}")
        print(f"  preference entries: {len(rec['operator_preferences'])}")
        for e in rec["operator_preferences"]:
            print(f"    [preference] {e['statement']}  scope={e['scope']}")
        if rec.get("parse_error"):
            print(f"  PARSE ERROR: {rec['parse_error']}")

    if "transfer" in steps or "safety" in steps:
        knowledge = memory.load_knowledge()
        preferences = memory.load_preferences()
        print(f"  (loaded from disk: {len(knowledge)} knowledge, "
              f"{len(preferences)} preferences)")

    if "transfer" in steps:
        print("=== S2 TRANSFER (cold restart + memory, acme-order-cost) ===", flush=True)
        rec = _review("transfer", TRANSFER, knowledge=knowledge, preferences=preferences)
        print(f"  stop={rec['stop_reason']} turns={rec['turn_count']} "
              f"python={rec['python_used']} elapsed={rec['elapsed_seconds']}s")
        print(f"  preview: {_preview(rec)}")

    if "safety" in steps:
        print("=== S2 SAFETY (cold restart + memory, room-reservation effect failure) ===", flush=True)
        rec = _review("safety", S1 / "B", knowledge=knowledge, preferences=preferences)
        print(f"  stop={rec['stop_reason']} turns={rec['turn_count']} "
              f"python={rec['python_used']} elapsed={rec['elapsed_seconds']}s")
        print(f"  preview: {_preview(rec)}")

    if raw:
        for label in ("before", "transfer", "safety"):
            d = RESULTS / label
            if d.is_dir():
                f = sorted(d.glob("run-*.json"))[-1]
                r = __import__("json").loads(f.read_text(encoding="utf-8"))
                print(f"\n--- {label} final response ---")
                print(r["final_response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))