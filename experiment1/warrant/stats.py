"""L4 statistics: detection floor computation and the tests it describes.

Two tests are declared, both BEFORE any drift variant exists:

  1. single-period   -- one incoming period against a baseline window
  2. sustained       -- mean of the last k periods against a baseline window

Declaring the sustained test up front matters. If it were added after seeing
S-creep results, it would be exactly the post-hoc tuning the preregistration
protocol forbids.

A detection floor is a statement about **Type II** error. Bounding alpha alone
and then concluding "we would have caught this" bounds the wrong error, so both
alpha and target power are required arguments everywhere -- there is no default
that lets a caller omit power.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.stats import nct, t as student_t

METHOD_VERSION = "l4/1.1.0"

# 1.0.0 used a normal reference with an sd estimated from n=12 periods. Validation
# on data satisfying the model exactly showed a null alarm rate of 0.076 against a
# declared alpha of 0.05 -- the test was anti-conservative, so the contract would
# have misstated its own Type I rate. 1.1.0 uses the t reference and a noncentral-t
# power calculation. Corrected BEFORE the floor was preregistered.


def _t_crit(alpha: float, df: int, two_sided: bool) -> float:
    a = alpha / 2.0 if two_sided else alpha
    return float(student_t.ppf(1.0 - a, df))


def _power_at(nc: float, alpha: float, df: int, two_sided: bool) -> float:
    """Power of a t-test at noncentrality `nc`."""
    crit = _t_crit(alpha, df, two_sided)
    upper = float(nct.sf(crit, df, nc))
    lower = float(nct.cdf(-crit, df, nc)) if two_sided else 0.0
    return upper + lower


def min_detectable_shift_pct(
    baseline_mean: float,
    baseline_sd: float,
    baseline_window: int,
    alpha: float,
    power: float,
    k_periods: int = 1,
    two_sided: bool = True,
) -> float:
    """Smallest shift in the mean, as a fraction of the mean, detectable at `power`.

    Comparing the mean of `k_periods` new observations against a baseline of
    `baseline_window` periods, the standard error of the difference is

        sd * sqrt(1/k + 1/n)

    The required noncentrality is found by solving the noncentral-t power equation
    rather than using a normal approximation, because sd is estimated from a short
    baseline and the normal reference understates both alpha and the floor.

    Assumes independent, identically distributed periods. That assumption is
    OPTIMISTIC for real business data -- serial correlation and seasonality inflate
    the true standard error, which makes the true floor LARGER than the number
    returned here. The direction matters: an optimistic floor manufactures false
    assurance. Callers must record `dependence_assumption` alongside the result so
    the optimism stays visible.
    """
    if baseline_mean <= 0:
        raise ValueError("baseline_mean must be positive")
    df = baseline_window - 1
    nc = brentq(lambda x: _power_at(x, alpha, df, two_sided) - power, 1e-6, 50.0, xtol=1e-8)
    se_factor = math.sqrt(1.0 / k_periods + 1.0 / baseline_window)
    return float(nc) * baseline_sd * se_factor / baseline_mean


@dataclass
class L4Outcome:
    test: str
    observed: float
    expected: float
    shift_pct: float
    z: float
    p_value: float
    alarm: bool
    floor_pct: float

    def to_dict(self) -> dict:
        return {
            "test": self.test,
            "observed": self.observed,
            "expected": self.expected,
            "shift_pct": self.shift_pct,
            "z": self.z,
            "p_value": self.p_value,
            "alarm": self.alarm,
            "floor_pct": self.floor_pct,
        }


def single_period_test(
    observed_total: float,
    baseline: np.ndarray,
    alpha: float,
    floor_pct: float,
    two_sided: bool = True,
) -> L4Outcome:
    """One incoming period against the baseline window."""
    mean = float(np.mean(baseline))
    sd = float(np.std(baseline, ddof=1))
    se = sd * math.sqrt(1.0 + 1.0 / len(baseline))
    df = len(baseline) - 1
    z = (observed_total - mean) / se if se > 0 else 0.0
    p = 2.0 * student_t.sf(abs(z), df) if two_sided else float(student_t.sf(z, df))
    return L4Outcome(
        test="single_period_t_vs_baseline",
        observed=observed_total,
        expected=mean,
        shift_pct=(observed_total - mean) / mean if mean else 0.0,
        z=float(z),
        p_value=float(p),
        alarm=bool(p < alpha),
        floor_pct=floor_pct,
    )


def sustained_test(
    recent_totals: np.ndarray,
    baseline: np.ndarray,
    alpha: float,
    floor_pct: float,
    two_sided: bool = True,
) -> L4Outcome:
    """Mean of the last k periods against the baseline window."""
    k = len(recent_totals)
    mean = float(np.mean(baseline))
    sd = float(np.std(baseline, ddof=1))
    se = sd * math.sqrt(1.0 / k + 1.0 / len(baseline))
    obs = float(np.mean(recent_totals))
    df = len(baseline) - 1
    z = (obs - mean) / se if se > 0 else 0.0
    p = 2.0 * student_t.sf(abs(z), df) if two_sided else float(student_t.sf(z, df))
    return L4Outcome(
        test=f"k{k}_period_mean_vs_baseline",
        observed=obs,
        expected=mean,
        shift_pct=(obs - mean) / mean if mean else 0.0,
        z=float(z),
        p_value=float(p),
        alarm=bool(p < alpha),
        floor_pct=floor_pct,
    )
