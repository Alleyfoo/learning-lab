"""RUN B -- corrected MDE method, calibrated and certified on disjoint seeds.

Implements exactly what spec/run_b_preregistration.md declares. Nothing here
may be tuned after results are observed; pass criteria P1-P4 are read from the
preregistration and applied as written.

Method l4/2.0.0: the closed form is abandoned, not patched. MDE is solved by
Monte Carlo under a declared MULTIPLICATIVE shift model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from run_experiment import load_committed_floor
from sweep import MODELS, simulate
from warrant.stats import single_period_test, sustained_test

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
METHOD_VERSION = "l4/2.0.0"
SHIFT_MODEL = "multiplicative"

CAL_SEED_FAMILY = 700000      # preregistered
CERT_SEED_FAMILY = 810000     # preregistered, disjoint

# Pass criteria, copied verbatim from the preregistration. Do not edit.
P1_BAND = (0.78, 0.82)        # power, resampled baseline
P2_BAND = (0.04, 0.06)        # null alarm rate, resampled baseline
P3_BAND = (0.75, 0.85)        # power, fixed committed baseline
FLOOR_V1_PCT = 22.4367        # P4: corrected floor must exceed this


def alarm_rate_multiplicative(
    delta: float, mu: float, sd: float, n: int, alpha: float, k: int,
    trials: int, seed: int, model: str = "iid",
    fixed_baseline: np.ndarray | None = None,
) -> tuple[float, float]:
    """Alarm rate under a MULTIPLICATIVE shift: mean AND sd scale by (1+delta)."""
    rng = np.random.default_rng(seed)
    single_hits = sustained_hits = 0
    for _ in range(trials):
        if fixed_baseline is not None:
            base = fixed_baseline
            nxt = simulate(model, mu, sd, k, rng)
        else:
            series = simulate(model, mu, sd, n + k, rng)
            base, nxt = series[:n], series[n:]
        shifted = nxt * (1.0 + delta)
        single_hits += int(single_period_test(float(shifted[-1]), base, alpha, 0.0).alarm)
        sustained_hits += int(sustained_test(shifted, base, alpha, 0.0).alarm)
    return single_hits / trials, sustained_hits / trials


def calibrate(mu, sd, n, alpha, power, k, trials, seed_family, model="iid", k_periods=1):
    """Solve for delta* such that simulated power == target. Calibration seeds only."""
    counter = {"i": 0}

    def power_at(delta: float) -> float:
        counter["i"] += 1
        s, ks = alarm_rate_multiplicative(
            delta, mu, sd, n, alpha, k, trials, seed_family + counter["i"], model
        )
        return (s if k_periods == 1 else ks) - power

    return float(brentq(power_at, 0.01, 2.0, xtol=1e-5, rtol=1e-4))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal-trials", type=int, default=8000)
    ap.add_argument("--cert-trials", type=int, default=40000)
    args = ap.parse_args()

    v1 = load_committed_floor()
    mu, sd, n, alpha, power, k = (
        v1.baseline_mean, v1.baseline_sd, v1.baseline_window,
        v1.alpha, v1.power, v1.sustained_window,
    )

    print(f"v1 floor: {v1.min_detectable_shift_pct:.4f}% single, "
          f"{v1.sustained_min_detectable_shift_pct:.4f}% sustained")
    print(f"calibrating {METHOD_VERSION} ({SHIFT_MODEL} shift), "
          f"cal seeds {CAL_SEED_FAMILY}, {args.cal_trials} trials/eval ...")

    d_single = calibrate(mu, sd, n, alpha, power, k, args.cal_trials, CAL_SEED_FAMILY,
                         k_periods=1)
    d_sust = calibrate(mu, sd, n, alpha, power, k, args.cal_trials, CAL_SEED_FAMILY + 500,
                       k_periods=k)
    single_pct, sust_pct = d_single * 100, d_sust * 100
    print(f"calibrated: {single_pct:.4f}% single, {sust_pct:.4f}% sustained\n")

    # ---------------- certification, disjoint seeds ------------------------
    print(f"certifying on held-out seeds {CERT_SEED_FAMILY}, {args.cert_trials} trials ...")
    p1, _ = alarm_rate_multiplicative(d_single, mu, sd, n, alpha, k, args.cert_trials,
                                      CERT_SEED_FAMILY + 1)
    p2, _ = alarm_rate_multiplicative(0.0, mu, sd, n, alpha, k, args.cert_trials,
                                      CERT_SEED_FAMILY + 2)
    fixed = np.asarray(
        __import__("pandas").read_csv(ARTIFACTS / "baseline_history.csv")
        .groupby("report_period")["amount"].sum().sort_index().iloc[:n],
        dtype=float,
    )
    p3, _ = alarm_rate_multiplicative(d_single, mu, sd, n, alpha, k, args.cert_trials,
                                      CERT_SEED_FAMILY + 3, fixed_baseline=fixed)

    checks = {
        "P1_power_resampled": {"value": round(p1, 4), "band": list(P1_BAND),
                               "pass": P1_BAND[0] <= p1 <= P1_BAND[1]},
        "P2_null_alpha_resampled": {"value": round(p2, 4), "band": list(P2_BAND),
                                    "pass": P2_BAND[0] <= p2 <= P2_BAND[1]},
        "P3_power_fixed_baseline": {"value": round(p3, 4), "band": list(P3_BAND),
                                    "pass": P3_BAND[0] <= p3 <= P3_BAND[1]},
        "P4_floor_larger_than_v1": {"value": round(single_pct, 4), "band": [FLOOR_V1_PCT, None],
                                    "pass": single_pct > FLOOR_V1_PCT},
    }
    overall = all(c["pass"] for c in checks.values())

    # ---------------- descriptive stress, cannot cause pass/fail -----------
    stress = {}
    for model in MODELS:
        s_null, _ = alarm_rate_multiplicative(0.0, mu, sd, n, alpha, k, args.cert_trials // 4,
                                              CERT_SEED_FAMILY + 100 + hash(model) % 97, model)
        s_pow, _ = alarm_rate_multiplicative(d_single, mu, sd, n, alpha, k,
                                             args.cert_trials // 4,
                                             CERT_SEED_FAMILY + 200 + hash(model) % 97, model)
        stress[model] = {"null_alarm_rate": round(s_null, 4),
                         "power_at_corrected_floor": round(s_pow, 4)}

    floor_v2 = {
        "metric": "period_total",
        "alpha": alpha, "power": power, "assumption": "iid",
        "shift_model": SHIFT_MODEL,
        "mde_method": "monte_carlo",
        "min_detectable_shift_pct": round(single_pct, 4),
        "sustained_min_detectable_shift_pct": round(sust_pct, 4),
        "sustained_window": k, "baseline_window": n,
        "baseline_mean": mu, "baseline_sd": sd, "baseline_cv": v1.baseline_cv,
        "baseline_sha256": v1.baseline_sha256,
        "method_version": METHOD_VERSION,
        "supersedes": {"method_version": v1.method_version,
                       "min_detectable_shift_pct": v1.min_detectable_shift_pct},
        "calibration_trials": args.cal_trials,
        "calibration_seed_family": CAL_SEED_FAMILY,
        "certification_trials": args.cert_trials,
        "certification_seed_family": CERT_SEED_FAMILY,
        "certification": checks,
        "certified": overall,
        "descriptive_stress_not_a_pass_criterion": stress,
        "interpretation": (
            f"Under a multiplicative measure redefinition, single-period changes smaller than "
            f"{single_pct:.2f}% of the period total are not reliably distinguishable from normal "
            f"variation at alpha={alpha}, power={power}. Absence of an alarm is NOT evidence of "
            f"semantic continuity."
        ),
        "assumption_bias_direction": (
            "The iid assumption remains OPTIMISTIC and is deliberately uncorrected in RUN B. "
            "See descriptive_stress_not_a_pass_criterion."
        ),
        "external_validity": (
            "Certification seeds are held out from calibration but draw from the same declared "
            "world model. This establishes internal calibration stability, not external "
            "validity."
        ),
    }

    (ROOT / "results").mkdir(exist_ok=True)
    if overall:
        (ARTIFACTS / "detection_floor_v2.json").write_text(
            json.dumps(floor_v2, indent=2) + "\n", encoding="utf-8")
    (ROOT / "results" / "run_b_summary.json").write_text(
        json.dumps(floor_v2, indent=2) + "\n", encoding="utf-8")

    print()
    for name, c in checks.items():
        band = f"[{c['band'][0]}, {c['band'][1]}]" if c["band"][1] is not None else f"> {c['band'][0]}"
        print(f"  {name:28s} {c['value']:<10} {band:<16} {'PASS' if c['pass'] else 'FAIL'}")
    print(f"\nRUN B: {'PASSED' if overall else 'FAILED'}")
    print(f"floor v1 -> v2: {v1.min_detectable_shift_pct:.4f}% -> {single_pct:.4f}% "
          f"({single_pct / v1.min_detectable_shift_pct:.3f}x)")
    print("\ndescriptive stress against the corrected floor (not a pass criterion):")
    for model, s in stress.items():
        print(f"  {model:10s} null={s['null_alarm_rate']:.4f}  "
              f"power={s['power_at_corrected_floor']:.4f}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
