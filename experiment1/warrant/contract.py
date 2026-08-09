"""Construct the applicability contract from the frozen baseline.

The L1/L2/L3 predicates are *observed* from the baseline -- they are deterministic
facts about structure. The L5 assertions are *declared* -- they come from the
baseline manifest and are marked uncheckable. Nothing here infers meaning.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .model import (
    ApplicabilityContract,
    EvidenceClaim,
    EvidenceVector,
    L1Structural,
    L2Column,
    L3Grain,
    L4Spec,
    L5SemanticAssertion,
    WarrantedProcedure,
)

MEASURE = "amount"
GRAIN_KEY = ["article_sku", "report_period"]


def load_baseline(artifacts: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(artifacts / "baseline_history.csv")
    manifest = json.loads((artifacts / "baseline_manifest.json").read_text(encoding="utf-8"))
    return df, manifest


def period_totals(df: pd.DataFrame, measure: str = MEASURE) -> pd.Series:
    return df.groupby("report_period")[measure].sum().sort_index()


def build_contract(df: pd.DataFrame, manifest: dict, baseline_window: int) -> ApplicabilityContract:
    per_period = df.groupby("report_period").size()
    lo, hi = int(per_period.min()), int(per_period.max())
    slack = max(3, int(round(0.10 * per_period.mean())))

    l5 = [
        L5SemanticAssertion(
            claim=a["claim"],
            source=a["source"],
            established_at_period=str(df["report_period"].min()),
            checkable_from_data=bool(a["checkable_from_data"]),
        )
        for a in manifest["semantic_assertions"]
    ]

    return ApplicabilityContract(
        l1=L1Structural(
            sheet=None,
            header_row=0,
            column_names=list(df.columns),
            column_count=len(df.columns),
            required_columns=["article_sku", "report_period", MEASURE],
        ),
        l2={
            "article_sku": L2Column(dtype="string", null_rate_max=0.0, cardinality_min=100),
            "quantity": L2Column(dtype="int", null_rate_max=0.0),
            "unit_price": L2Column(dtype="float", null_rate_max=0.0),
            MEASURE: L2Column(dtype="float", null_rate_max=0.0),
        },
        l3=L3Grain(
            key=list(GRAIN_KEY),
            key_must_be_unique=True,
            row_count_band=(lo - slack, hi + slack),
        ),
        l4=L4Spec(baseline_window=baseline_window),
        l5=l5,
    )


def build_evidence(
    established_at_index: int = 0,
    semantic_tolerance: int = 24,
    aggregate_tolerance: int = 6,
    structural_tolerance: int = 1,
) -> EvidenceVector:
    """Evidence dimensions are orthogonal and decay at different rates (B3.1)."""
    return EvidenceVector(
        semantic_meaning=EvidenceClaim(
            dimension="semantic_meaning",
            source="human_confirmation",
            established_at_index=established_at_index,
            staleness_tolerance_periods=semantic_tolerance,
        ),
        aggregate_correctness=EvidenceClaim(
            dimension="aggregate_correctness",
            source="independent_reconciliation",
            established_at_index=established_at_index,
            staleness_tolerance_periods=aggregate_tolerance,
        ),
        structural_fit=EvidenceClaim(
            dimension="structural_fit",
            source="deterministic_validation",
            established_at_index=established_at_index,
            staleness_tolerance_periods=structural_tolerance,
        ),
    )


def build_procedure(
    df: pd.DataFrame,
    manifest: dict,
    baseline_window: int,
    floor=None,
    evidence: EvidenceVector | None = None,
) -> WarrantedProcedure:
    return WarrantedProcedure(
        procedure_id="synthetic-provider-001",
        version=1,
        applicability=build_contract(df, manifest, baseline_window),
        detection_capability=floor,
        evidence=evidence if evidence is not None else build_evidence(),
    )


def baseline_slice(totals: pd.Series, window: int) -> np.ndarray:
    return totals.iloc[:window].to_numpy(dtype=float)
