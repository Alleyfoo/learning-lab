"""O5 -- evidence expiry. The state where nothing looks wrong.

Feeds UNCHANGED data while allowing the independent (aggregate_correctness)
anchor to age. Every structural, typing, grain and statistical check continues
to pass. The question is whether authorization stops anyway.

This is also where O1a is actually measurable: RUN A held evidence fresh by
design, so it could not observe an unwarranted execution.

Two scenarios:
  no_reanchor -- the anchor is established once and never refreshed
  reanchor    -- the anchor is refreshed when the system demands it, showing
                 that authorization resumes rather than latching
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_experiment import load_committed_floor
from warrant.contract import (
    baseline_slice,
    build_evidence,
    build_procedure,
    load_baseline,
    period_totals,
)
from warrant.engine import evaluate
from warrant.model import AuthorizationState

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
EVAL_START = 12
AGG_TOLERANCE = 6


def run(scenario: str) -> pd.DataFrame:
    floor = load_committed_floor()
    df, manifest = load_baseline(ARTIFACTS)
    totals = period_totals(df)
    periods = list(totals.index)
    base = baseline_slice(totals, floor.baseline_window)
    k = floor.sustained_window

    anchor_at = EVAL_START
    rows = []
    for t in range(EVAL_START, len(periods)):
        evidence = build_evidence(
            established_at_index=anchor_at, aggregate_tolerance=AGG_TOLERANCE
        )
        # structural_fit is re-established by this very run; semantic is long-lived
        evidence.structural_fit.established_at_index = t
        evidence.semantic_meaning.established_at_index = 0

        proc = build_procedure(df, manifest, floor.baseline_window, floor=floor,
                               evidence=evidence)
        period_df = df[df["report_period"] == periods[t]]
        recent = totals.iloc[max(0, t - k + 1): t + 1].to_numpy(dtype=float)

        res = evaluate(period_df, base, proc, now_index=t, recent_totals=recent)
        assert res.semantic_status == "not_established", "N1 guard failed"

        sp = res.l4_report["single_period"]
        automatic_checks_pass = (not res.failed_predicates) and (not sp["alarm"]) and (
            not res.l4_report.get("sustained", {}).get("alarm", False)
        )

        rows.append({
            "period": periods[t],
            "period_index": t,
            "anchor_age": res.periods_since_independent_anchor,
            "state": res.state.value,
            "automatic_checks_pass": automatic_checks_pass,
            "stale_dimensions": ",".join(res.stale_dimensions) or None,
            "shift_pct": round(sp["shift_pct"] * 100, 3),
        })

        if scenario == "reanchor" and res.state == AuthorizationState.RE_ANCHOR_REQUIRED:
            anchor_at = t          # operator supplies fresh independent evidence

    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args()

    out = {}
    frames = {}
    for scenario in ("no_reanchor", "reanchor"):
        d = run(scenario)
        frames[scenario] = d

        clean = d[d["automatic_checks_pass"]]
        stale_and_clean = clean[clean["stale_dimensions"].notna()]
        o1a = int(((d["state"] == AuthorizationState.AUTHORIZED.value)
                   & d["stale_dimensions"].notna()).sum())

        out[scenario] = {
            "n_periods": int(len(d)),
            "O1a_unwarranted_execution": o1a,
            "O5_expiry_fired_while_all_checks_pass": int(len(stale_and_clean)),
            "first_expiry_period": (
                stale_and_clean["period"].iloc[0] if len(stale_and_clean) else None
            ),
            "states": d["state"].value_counts().to_dict(),
            "per_period": d.to_dict(orient="records"),
        }

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "expiry_summary.json").write_text(
        json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")

    for scenario, d in frames.items():
        print(f"=== {scenario} ===")
        print(d.to_string(index=False))
        s = out[scenario]
        print(f"O1a unwarranted execution: {s['O1a_unwarranted_execution']}")
        print(f"O5 expiry while every automatic check passes: "
              f"{s['O5_expiry_fired_while_all_checks_pass']} "
              f"(first at {s['first_expiry_period']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
