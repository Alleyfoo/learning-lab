"""Floor calibration sweep and dependence-misspecification stress.

Two questions, both asked against the COMMITTED floor. The floor is never refitted.

  1. Calibration: does the declared floor correspond to ~80% power in the world
     the floor assumed (iid)? Sweep shift magnitude 0.1x -- 4x the floor and
     locate the empirical 80%-power point.

  2. Misspecification: how far do the declared alpha and power degrade when the
     dependence assumption is wrong -- AR(1) rho = 0.3, rho = 0.6, seasonal?

Simulation model. Each replicate draws a fresh 12-period baseline plus one test
period from the stated process, then runs the DECLARED test exactly as deployed:
mean and sd re-estimated from that replicate's own baseline window. This is the
deployed procedure's behaviour, not a textbook idealisation.

Marginal sd is held equal to the committed baseline sd across all models, so a
given shift percentage means the same thing in every world.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_experiment import load_committed_floor
from warrant.stats import single_period_test, sustained_test

ROOT = Path(__file__).resolve().parent
MODELS = ["iid", "ar1_0.3", "ar1_0.6", "seasonal"]
SWEEP_MULTIPLES = [0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]


def simulate(model: str, mu: float, sd: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw `n` consecutive periods with marginal sd == `sd`."""
    if model == "iid":
        return rng.normal(mu, sd, n)

    if model.startswith("ar1_"):
        phi = float(model.split("_")[1])
        eps_sd = sd * np.sqrt(1.0 - phi**2)
        x = np.empty(n)
        x[0] = rng.normal(0.0, sd)          # start from the stationary distribution
        for i in range(1, n):
            x[i] = phi * x[i - 1] + rng.normal(0.0, eps_sd)
        return mu + x

    if model == "seasonal":
        # 12-period sinusoid carrying 70% of the marginal sd, iid noise the rest.
        amp_sd, noise_sd = 0.7 * sd, sd * np.sqrt(1.0 - 0.7**2)
        phase = rng.uniform(0, 2 * np.pi)
        t = np.arange(n)
        seasonal = np.sqrt(2.0) * amp_sd * np.sin(2 * np.pi * t / 12.0 + phase)
        return mu + seasonal + rng.normal(0.0, noise_sd, n)

    raise ValueError(f"unknown model: {model}")


def alarm_rate(
    model: str, shift: float, mu: float, sd: float, window: int, alpha: float,
    k: int, trials: int, seed: int,
) -> tuple[float, float]:
    """Return (single-period alarm rate, sustained alarm rate) at `shift`."""
    rng = np.random.default_rng(seed)
    single_hits = sustained_hits = 0
    for _ in range(trials):
        series = simulate(model, mu, sd, window + k, rng)
        base = series[:window]
        recent = series[window:] * (1.0 + shift)
        single_hits += int(single_period_test(float(recent[-1]), base, alpha, 0.0).alarm)
        sustained_hits += int(sustained_test(recent, base, alpha, 0.0).alarm)
    return single_hits / trials, sustained_hits / trials


def crossing(multiples: list[float], powers: list[float], target: float = 0.80) -> float | None:
    """Linear interpolation of the multiple at which power first reaches `target`."""
    for i in range(1, len(multiples)):
        if powers[i - 1] < target <= powers[i]:
            span = powers[i] - powers[i - 1]
            if span <= 0:
                return multiples[i]
            frac = (target - powers[i - 1]) / span
            return multiples[i - 1] + frac * (multiples[i] - multiples[i - 1])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=90909)
    args = ap.parse_args()

    floor = load_committed_floor()
    mu, sd, window, alpha, k = (
        floor.baseline_mean, floor.baseline_sd, floor.baseline_window,
        floor.alpha, floor.sustained_window,
    )
    f_single = floor.min_detectable_shift_pct / 100.0

    rows = []
    for mi, model in enumerate(MODELS):
        # null behaviour
        s0, k0 = alarm_rate(model, 0.0, mu, sd, window, alpha, k, args.trials,
                            args.seed + 1000 * mi)
        rows.append({"model": model, "multiple": 0.0, "shift_pct": 0.0,
                     "single_alarm": s0, "sustained_alarm": k0})
        for j, m in enumerate(SWEEP_MULTIPLES):
            s, ks = alarm_rate(model, m * f_single, mu, sd, window, alpha, k, args.trials,
                               args.seed + 1000 * mi + j + 1)
            rows.append({"model": model, "multiple": m, "shift_pct": round(m * f_single * 100, 4),
                         "single_alarm": s, "sustained_alarm": ks})

    df = pd.DataFrame(rows)

    summary = {"floor_used": floor.to_dict(), "trials_per_point": args.trials, "models": {}}
    for model in MODELS:
        sub = df[(df.model == model) & (df.multiple > 0)].sort_values("multiple")
        null = float(df[(df.model == model) & (df.multiple == 0)].single_alarm.iloc[0])
        null_k = float(df[(df.model == model) & (df.multiple == 0)].sustained_alarm.iloc[0])
        at_floor = float(sub[sub.multiple == 1.0].single_alarm.iloc[0])
        cross = crossing(sub.multiple.tolist(), sub.single_alarm.tolist())
        summary["models"][model] = {
            "null_alarm_rate_single": round(null, 4),
            "declared_alpha": alpha,
            "alpha_inflation_factor": round(null / alpha, 2),
            "power_at_declared_floor": round(at_floor, 4),
            "declared_power": floor.power,
            "empirical_80pct_power_multiple": None if cross is None else round(cross, 3),
            "empirical_80pct_power_shift_pct": (
                None if cross is None else round(cross * floor.min_detectable_shift_pct, 3)
            ),
            "null_alarm_rate_sustained": round(null_k, 4),
        }

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "sweep_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    df.to_csv(ROOT / "results" / "sweep_detail.csv", index=False, lineterminator="\n")

    print(f"committed floor: {floor.min_detectable_shift_pct:.2f}% single "
          f"(alpha={alpha}, power={floor.power}, assumption={floor.assumption})")
    print(f"trials/point: {args.trials}\n")
    hdr = f"{'model':10s} {'null a':>7s} {'infl':>5s} {'pwr@floor':>10s} {'80% at':>8s} {'= shift':>8s}"
    print(hdr)
    print("-" * len(hdr))
    for model, s in summary["models"].items():
        cross = s["empirical_80pct_power_multiple"]
        shift = s["empirical_80pct_power_shift_pct"]
        print(f"{model:10s} {s['null_alarm_rate_single']:7.4f} "
              f"{s['alpha_inflation_factor']:5.2f} {s['power_at_declared_floor']:10.4f} "
              f"{('n/a' if cross is None else f'{cross:.2f}x'):>8s} "
              f"{('n/a' if shift is None else f'{shift:.1f}%'):>8s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
