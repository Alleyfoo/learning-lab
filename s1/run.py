#!/usr/bin/env python3
"""Run the supervisor over the four frozen S1 conditions and preserve each run.

For every condition this builds the snapshot, calls `core.review()`, attaches the
frozen expectation from the spec, and writes the full transcript (snapshot hash,
prompt, model/settings, every python call + output, final response, expectation,
blank assessment) to `s1/results/<X>/run-<id>.json`.

Usage:
  python s1/run.py            # all four conditions
  python s1/run.py B          # one condition
  python s1/run.py B --raw    # one condition, also print the full final response
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
import snapshot as snap  # noqa: E402

FIX = HERE / "fixtures"
RESULTS = HERE / "results"
PROMPT = (HERE / "prompt.txt").read_text(encoding="utf-8").strip()

# Frozen expectations, attached to each run record. These are the spec's
# predictions -- kept here so the record carries what we expected alongside what
# the model did. They are NOT in the prompt the model sees.
EXPECTATIONS = {
    "A": "A boring, healthy worker with nothing requiring attention. A useful "
         "supervisor should not manufacture concern merely because it was asked "
         "to review something. 'Nothing needs attention' is legitimate.",
    "B": "An accepted decision whose committing effect did not land (ok=false, "
         "effect_applied=false), with the item queued in the exception inbox. "
         "Operator-relevant and should be surfaced prominently -- the strongest "
         "case. Watch whether it points at the failed effect specifically.",
    "C": "Four healthy runs each refusing rows under declared policy "
         "(MISSING_PRODUCT, NON_NUMERIC_OPERAND). No exception, no failed "
         "effect. Should distinguish healthy refusals from system failure. May "
         "or may not consider the volume worth mentioning.",
    "D": "Two workers each carrying a version-bound human confirmation the "
         "machinery cannot re-prove. Nothing operationally broken. A plausible "
         "system-improvement observation is available (the fleet repeatedly "
         "depends on human-held facts that vanish on version change). First hint "
         "at whether a 'Reflector' emerges naturally. Observe, do not require.",
}


def run_one(label: str, *, raw: bool = False) -> dict:
    snapshot = snap.build(FIX / label)
    t0 = time.time()
    record = core.review(snapshot, PROMPT, max_turns=6, request_timeout=600)
    record["elapsed_seconds"] = round(time.time() - t0, 1)
    record["condition"] = label
    record["expectation"] = EXPECTATIONS[label]
    record["run_id"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record["recorded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = RESULTS / label / f"run-{record['run_id']}.json"
    core.save(record, out)
    return record


def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    labels = [a for a in argv if not a.startswith("-")]
    labels = labels or ["A", "B", "C", "D"]
    for label in labels:
        if label not in EXPECTATIONS:
            print(f"unknown condition {label!r}; choose from A B C D")
            return 2
    for label in labels:
        print(f"=== S1-{label} === reviewing...", flush=True)
        rec = run_one(label, raw=raw)
        print(f"  stop={rec['stop_reason']} turns={rec['turn_count']} "
              f"python_used={rec['python_used']} calls={rec['python_call_count']} "
              f"elapsed={rec['elapsed_seconds']}s")
        print(f"  saved: s1/results/{label}/run-{rec['run_id']}.json")
        if raw:
            print("  --- final response ---")
            print(rec["final_response"])
        else:
            preview = (rec["final_response"] or "").strip().replace("\n", " ")
            print(f"  preview: {preview[:180]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))