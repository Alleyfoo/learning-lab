"""Step 3 sanity check: run the warrant engine over UNCHANGED baseline data.

No drift exists. Expected behaviour:

  * every held-out period resolves to AUTHORIZED
  * the single-period false-alarm rate sits near alpha
  * `semantic_status` is "not_established" on every single result, always

The last one is the N1 guard. If any result ever claims semantic continuity,
this script fails loudly -- that is a defect in the instrument, not a finding.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from compute_floor import build_floor
from warrant.contract import (
    baseline_slice,
    build_evidence,
    build_procedure,
    load_baseline,
    period_totals,
)
from warrant.engine import evaluate

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-window", type=int, default=12)
    ap.add_argument("--anchor-every", type=int, default=1,
                    help="Re-establish the aggregate anchor every N periods. "
                         "1 = always fresh, isolating L4/structural behaviour.")
    args = ap.parse_args()

    df, manifest = load_baseline(ARTIFACTS)
    totals = period_totals(df)
    periods = list(totals.index)
    base = baseline_slice(totals, args.baseline_window)
    floor = build_floor(baseline_window=args.baseline_window)

    k = floor.sustained_window
    states: Counter[str] = Counter()
    single_alarms = 0
    rows = []

    for t in range(args.baseline_window, len(periods)):
        last_anchor = t - (t % args.anchor_every)
        evidence = build_evidence(established_at_index=last_anchor)
        # structural_fit is re-established by this very run
        evidence.structural_fit.established_at_index = t

        proc = build_procedure(df, manifest, args.baseline_window, floor=floor, evidence=evidence)
        period_df = df[df["report_period"] == periods[t]]
        recent = totals.iloc[max(0, t - k + 1): t + 1].to_numpy(dtype=float)

        res = evaluate(period_df, base, proc, now_index=t, recent_totals=recent)

        if res.semantic_status != "not_established":
            raise SystemExit(
                f"N1 GUARD FAILED at {periods[t]}: semantic_status={res.semantic_status!r}"
            )

        states[res.state.value] += 1
        single_alarms += int(res.l4_report["single_period"]["alarm"])
        rows.append(
            {
                "period": periods[t],
                "state": res.state.value,
                "shift_pct": round(res.l4_report["single_period"]["shift_pct"] * 100, 3),
                "z": round(res.l4_report["single_period"]["z"], 3),
                "single_alarm": res.l4_report["single_period"]["alarm"],
                "sustained_alarm": res.l4_report.get("sustained", {}).get("alarm"),
                "failed_predicates": len(res.failed_predicates),
                "stale": res.stale_dimensions,
            }
        )

    n = len(rows)
    out = {
        "n_held_out_periods": n,
        "states": dict(states),
        "single_period_false_alarm_rate": round(single_alarms / n, 4),
        "alpha": floor.alpha,
        "declared_floor_pct": floor.min_detectable_shift_pct,
        "declared_sustained_floor_pct": floor.sustained_min_detectable_shift_pct,
        "n1_guard": "passed - semantic_status was 'not_established' on all results",
        "per_period": rows,
    }

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "baseline_check.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )

    print(f"held-out periods : {n}")
    print(f"states           : {dict(states)}")
    print(f"false alarm rate : {out['single_period_false_alarm_rate']} (alpha={floor.alpha})")
    print(f"declared floor   : {floor.min_detectable_shift_pct:.2f}% single, "
          f"{floor.sustained_min_detectable_shift_pct:.2f}% sustained(k={k})")
    print(f"max |shift|      : {max(abs(r['shift_pct']) for r in rows):.2f}%")
    print("N1 guard         : passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
