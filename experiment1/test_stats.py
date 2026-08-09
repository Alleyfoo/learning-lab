"""Validate the floor FORMULA on data that satisfies its assumptions exactly.

This is not the calibration experiment. It is a much narrower check: if
`min_detectable_shift_pct` is miscoded, every downstream result is void, and we
would not be able to tell a broken estimator from a broken claim.

Here the data is drawn from the exact model the formula assumes -- iid normal,
known sigma structure. Empirical power at the computed floor should land near
the requested power. Any gap is estimator error, not misspecification.

Misspecification (AR(1), seasonality) is measured separately in step 7, against
the committed floor, and is NOT tested here.
"""

from __future__ import annotations

import numpy as np

from warrant.stats import min_detectable_shift_pct, single_period_test, sustained_test

RNG = np.random.default_rng(4242)
MEAN, SD, N_BASE, ALPHA, POWER = 1000.0, 70.0, 12, 0.05, 0.80
TRIALS = 20000


def _empirical_power(shift_pct: float, k: int) -> float:
    hits = 0
    for _ in range(TRIALS):
        base = RNG.normal(MEAN, SD, N_BASE)
        new = RNG.normal(MEAN * (1 + shift_pct), SD, k)
        if k == 1:
            out = single_period_test(float(new[0]), base, ALPHA, 0.0)
        else:
            out = sustained_test(new, base, ALPHA, 0.0)
        hits += int(out.alarm)
    return hits / TRIALS


def main() -> int:
    ok = True
    for k in (1, 6):
        floor = min_detectable_shift_pct(MEAN, SD, N_BASE, ALPHA, POWER, k_periods=k)
        emp = _empirical_power(floor, k)
        # Tolerance is wide on purpose: the test uses a normal reference with an
        # estimated sd from n=12, so empirical power sits slightly BELOW nominal.
        passed = 0.70 <= emp <= 0.88
        ok &= passed
        print(
            f"k={k:>2}  declared_floor={floor*100:6.2f}%  "
            f"empirical_power={emp:.3f}  target={POWER}  {'OK' if passed else 'FAIL'}"
        )

    # Null behaviour: at zero shift the alarm rate must sit near alpha.
    null = _empirical_power(0.0, 1)
    passed_null = 0.03 <= null <= 0.09
    ok &= passed_null
    print(f"k= 1  shift=0.00%          empirical_alarm={null:.3f}  alpha={ALPHA}  "
          f"{'OK' if passed_null else 'FAIL'}")

    print("\nformula validation:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
