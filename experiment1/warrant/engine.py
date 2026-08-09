"""The decision path.

    evidence sufficient?  ->  applicability checks pass?  ->  warrant current?
                          ->  authorized / re-anchor / mismatch

All conditions are evaluated; nothing short-circuits, so the full condition set
is always reported. A single terminal state is then resolved by a declared
precedence (see `PRECEDENCE` below) rather than by evaluation order, so the
outcome does not depend on how the code happens to be arranged.

Hard constraint, enforced by construction: this layer never emits
"semantically unchanged". `AuthorizationResult.semantic_status` has one value
and no code path assigns another.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .model import (
    AuthorizationResult,
    AuthorizationState,
    EscalationReason,
    WarrantedProcedure,
)
from .stats import single_period_test, sustained_test

# A hard structural mismatch is unambiguous regardless of evidence age, so it
# outranks staleness. Staleness outranks "authorized" because a stale anchor
# means the applicability judgement itself rests on unverified history.
PRECEDENCE = [
    AuthorizationState.MISMATCH_ESCALATION,
    AuthorizationState.UNDECIDABLE_EXTERNAL,
    AuthorizationState.RE_ANCHOR_REQUIRED,
    AuthorizationState.AUTHORIZED,
]


def _check_l1(df: pd.DataFrame, proc: WarrantedProcedure) -> list[dict[str, Any]]:
    l1 = proc.applicability.l1
    failed: list[dict[str, Any]] = []
    observed = list(df.columns)
    if l1.column_names and sorted(observed) != sorted(l1.column_names):
        failed.append(
            {
                "level": "L1",
                "predicate": "column_names",
                "expected": sorted(l1.column_names),
                "observed": sorted(observed),
            }
        )
    if l1.column_count is not None and len(observed) != l1.column_count:
        failed.append(
            {"level": "L1", "predicate": "column_count",
             "expected": l1.column_count, "observed": len(observed)}
        )
    for col in l1.required_columns:
        if col not in observed:
            failed.append(
                {"level": "L1", "predicate": "required_column", "expected": col, "observed": None}
            )
    return failed


def _check_l2(df: pd.DataFrame, proc: WarrantedProcedure) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for col, spec in proc.applicability.l2.items():
        if col not in df.columns:
            continue
        series = df[col]
        null_rate = float(series.isna().mean())
        if null_rate > spec.null_rate_max:
            failed.append(
                {"level": "L2", "predicate": f"{col}.null_rate",
                 "expected": f"<={spec.null_rate_max}", "observed": null_rate}
            )
        if spec.dtype in {"int", "float", "number"}:
            numeric_ok = pd.to_numeric(series, errors="coerce").notna().mean()
            if numeric_ok < 0.99:
                failed.append(
                    {"level": "L2", "predicate": f"{col}.dtype",
                     "expected": spec.dtype, "observed": f"numeric_ratio={numeric_ok:.3f}"}
                )
        if spec.cardinality_min is not None and series.nunique() < spec.cardinality_min:
            failed.append(
                {"level": "L2", "predicate": f"{col}.cardinality",
                 "expected": f">={spec.cardinality_min}", "observed": int(series.nunique())}
            )
    return failed


def _check_l3(df: pd.DataFrame, proc: WarrantedProcedure) -> list[dict[str, Any]]:
    l3 = proc.applicability.l3
    failed: list[dict[str, Any]] = []
    if l3.key and l3.key_must_be_unique:
        if all(k in df.columns for k in l3.key):
            dupes = int(df.duplicated(subset=l3.key).sum())
            if dupes:
                failed.append(
                    {"level": "L3", "predicate": "key_uniqueness",
                     "expected": f"unique on {l3.key}", "observed": f"{dupes} duplicate rows"}
                )
        else:
            failed.append(
                {"level": "L3", "predicate": "key_present",
                 "expected": l3.key, "observed": list(df.columns)}
            )
    if l3.row_count_band is not None:
        lo, hi = l3.row_count_band
        if not (lo <= len(df) <= hi):
            failed.append(
                {"level": "L3", "predicate": "row_count_band",
                 "expected": [lo, hi], "observed": len(df)}
            )
    return failed


def evaluate(
    period_df: pd.DataFrame,
    baseline_totals: np.ndarray,
    proc: WarrantedProcedure,
    now_index: int,
    measure_column: str = "amount",
    recent_totals: np.ndarray | None = None,
) -> AuthorizationResult:
    """Evaluate one incoming period against a warranted procedure.

    `recent_totals` enables the declared sustained test. It is the trailing
    window of accepted period totals INCLUDING the incoming one.
    """
    floor = proc.detection_capability
    if floor is None:
        raise ValueError(
            "Refusing to authorize without a committed detection floor. "
            "A procedure with no declared detection capability cannot state "
            "what it is blind to."
        )

    failed = _check_l1(period_df, proc) + _check_l2(period_df, proc) + _check_l3(period_df, proc)

    if measure_column not in period_df.columns:
        # The measure itself is missing. L4 cannot be evaluated at all; this is an
        # L1 failure, not a statistical result, and must not be reported as "no
        # evidence of change".
        return AuthorizationResult(
            state=AuthorizationState.MISMATCH_ESCALATION,
            reasons=[EscalationReason.OBSERVED_MISMATCH],
            failed_predicates=failed
            + [{"level": "L1", "predicate": "measure_column_present",
                "expected": measure_column, "observed": None}],
            l4_report={"single_period": None, "note": "measure column absent; L4 not evaluable"},
            stale_dimensions=proc.evidence.stale_dimensions(now_index),
            periods_since_independent_anchor=proc.evidence.periods_since_independent_anchor(
                now_index
            ),
            undecidable_region=proc.undecidable_region(),
        )

    observed_total = float(pd.to_numeric(period_df[measure_column], errors="coerce").sum())
    single = single_period_test(
        observed_total, baseline_totals, proc.applicability.l4.alpha, floor.min_detectable_shift_pct
    )
    l4_report: dict[str, Any] = {"single_period": single.to_dict()}

    if recent_totals is not None and len(recent_totals) >= 2:
        sust = sustained_test(
            recent_totals,
            baseline_totals,
            proc.applicability.l4.alpha,
            floor.sustained_min_detectable_shift_pct,
        )
        l4_report["sustained"] = sust.to_dict()
    else:
        sust = None

    l4_alarm = single.alarm or (sust.alarm if sust is not None else False)

    stale = proc.evidence.stale_dimensions(now_index)
    anchor_age = proc.evidence.periods_since_independent_anchor(now_index)

    # ---- resolve candidate states, then apply declared precedence -------
    candidates: list[AuthorizationState] = []
    reasons: list[EscalationReason] = []

    if failed or l4_alarm:
        candidates.append(AuthorizationState.MISMATCH_ESCALATION)
        reasons.append(EscalationReason.OBSERVED_MISMATCH)
    if stale:
        candidates.append(AuthorizationState.RE_ANCHOR_REQUIRED)
        reasons.append(EscalationReason.EVIDENCE_EXPIRY)
    if not candidates:
        candidates.append(AuthorizationState.AUTHORIZED)

    state = next(s for s in PRECEDENCE if s in candidates)

    return AuthorizationResult(
        state=state,
        reasons=reasons,
        failed_predicates=failed,
        l4_report=l4_report,
        stale_dimensions=stale,
        periods_since_independent_anchor=anchor_age,
        undecidable_region=proc.undecidable_region(),
        # semantic_status intentionally left at its only permitted value.
    )
