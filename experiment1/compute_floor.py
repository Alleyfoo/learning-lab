"""Compute the detection floor from the frozen baseline.

The floor is derived from the FIRST `--baseline-window` periods only. The
remaining periods are held out so that no part of the evaluation history
influences the declared capability.

Run with `--write` to emit `artifacts/detection_floor.json`. That artifact is
the hard preregistration gate: it must be committed and pushed BEFORE any drift
variant exists. If a drift variant is present in the working tree when `--write`
runs, this script refuses.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from warrant.contract import baseline_slice, load_baseline, period_totals
from warrant.model import DetectionFloor
from warrant.stats import METHOD_VERSION, min_detectable_shift_pct

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
DRIFT_MARKERS = ["drift", "variant", "s_obvious", "s_invisible", "s_creep", "sweep"]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT.parent, text=True).strip()


def _assert_no_drift_corpus() -> None:
    """Refuse to write the floor if drift artifacts already exist (B6.2)."""
    offenders = [
        p.as_posix()
        for p in ROOT.rglob("*")
        if p.is_file() and any(m in p.name.lower() for m in DRIFT_MARKERS)
    ]
    if offenders:
        raise SystemExit(
            "REFUSING to write the detection floor: drift artifacts already exist.\n"
            + "\n".join(f"  {o}" for o in offenders)
            + "\nThe preregistration ordering is violated. Discard this run and restart."
        )


def build_floor(
    baseline_window: int = 12,
    alpha: float = 0.05,
    power: float = 0.80,
    sustained_window: int = 6,
) -> DetectionFloor:
    """Compute the floor from the first `baseline_window` periods only."""
    df, manifest = load_baseline(ARTIFACTS)
    totals = period_totals(df)
    base = baseline_slice(totals, baseline_window)

    mean = float(np.mean(base))
    sd = float(np.std(base, ddof=1))

    single = min_detectable_shift_pct(mean, sd, baseline_window, alpha, power, k_periods=1)
    sustained = min_detectable_shift_pct(
        mean, sd, baseline_window, alpha, power, k_periods=sustained_window
    )

    return DetectionFloor(
        metric="period_total",
        alpha=alpha,
        power=power,
        assumption="iid",
        min_detectable_shift_pct=round(single * 100, 4),
        sustained_min_detectable_shift_pct=round(sustained * 100, 4),
        sustained_window=sustained_window,
        baseline_window=baseline_window,
        baseline_mean=round(mean, 4),
        baseline_sd=round(sd, 4),
        baseline_cv=round(sd / mean, 6),
        baseline_commit=_git("rev-parse", "HEAD"),
        baseline_sha256=manifest["artifact_sha256"]["baseline_history.csv"],
        method_version=METHOD_VERSION,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-window", type=int, default=12)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.80)
    ap.add_argument("--sustained-window", type=int, default=6)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    floor = build_floor(
        args.baseline_window, args.alpha, args.power, args.sustained_window
    )
    payload = floor.to_dict()
    payload["declared_before_drift_corpus"] = True
    payload["interpretation"] = (
        f"Given a {args.baseline_window}-period baseline, the declared test and a "
        f"{args.power:.0%} power requirement, single-period changes smaller than "
        f"{payload['min_detectable_shift_pct']:.2f}% of the period total are not reliably "
        f"distinguishable from normal variation. Sustained changes over "
        f"{args.sustained_window} periods below "
        f"{payload['sustained_min_detectable_shift_pct']:.2f}% are likewise not reliably "
        f"distinguishable. Absence of an alarm is NOT evidence of semantic continuity."
    )
    payload["assumption_bias_direction"] = (
        "The iid assumption is OPTIMISTIC. Serial correlation and seasonality inflate the true "
        "standard error, making the true floor LARGER than stated here. Step 7 measures how "
        "much."
    )

    print(json.dumps(payload, indent=2))

    if args.write:
        _assert_no_drift_corpus()
        out = ARTIFACTS / "detection_floor.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
