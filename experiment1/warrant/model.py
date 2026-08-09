"""Warrant and evidence data structures.

Deliberately dumb. These are representations, not intelligence. Nothing here
learns, infers meaning, or calls a model.

Vocabulary is frozen by amendment 003:

    WORLD STATE          does the procedure still describe the source?
    EVIDENCE STATE       how strongly can we establish that?
    AUTHORIZATION STATE  are we willing to let it run unattended?

This module represents the second and third. It has no access to the first, and
must never emit a claim about it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "warrant/1"


class AuthorizationState(str, Enum):
    """Terminal states of the authorization machine (amendment C2)."""

    AUTHORIZED = "authorized"                      # applicable + well-evidenced
    RE_ANCHOR_REQUIRED = "re_anchor_required"      # possibly applicable, evidence stale
    MISMATCH_ESCALATION = "mismatch_escalation"    # observed mismatch
    UNDECIDABLE_EXTERNAL = "undecidable_external"  # semantic status not establishable here


class EscalationReason(str, Enum):
    """Amendment B5. Reason 3 fires when nothing looks wrong."""

    OBSERVED_MISMATCH = "observed_mismatch"
    EPISTEMIC_INSUFFICIENCY = "epistemic_insufficiency"
    EVIDENCE_EXPIRY = "evidence_expiry"


# --------------------------------------------------------------------------
# Applicability contract (L0-L5)
# --------------------------------------------------------------------------


@dataclass
class L1Structural:
    sheet: str | None = None
    header_row: int = 0
    column_names: list[str] = field(default_factory=list)   # multiset, order-insensitive
    column_count: int | None = None
    required_columns: list[str] = field(default_factory=list)


@dataclass
class L2Column:
    dtype: str
    null_rate_max: float = 1.0
    cardinality_min: int | None = None


@dataclass
class L3Grain:
    key: list[str] = field(default_factory=list)
    key_must_be_unique: bool = True
    row_count_band: tuple[int, int] | None = None


@dataclass
class L4Spec:
    """Declaration of the statistical test. Every field affects the floor."""

    metric: str = "period_total"
    statistic: str = "monthly_total"
    test: str = "single_period_t_vs_baseline"
    baseline_window: int = 12
    alpha: float = 0.05
    target_power: float = 0.80
    variance_basis: str = "independently_anchored_periods"
    dependence_assumption: str = "iid"
    two_sided: bool = True

    # Sustained-shift companion test, declared up front so that a cumulative
    # detector cannot be introduced after seeing S-creep results.
    sustained_test: str = "k_period_mean_vs_baseline"
    sustained_window: int = 6


@dataclass
class L5SemanticAssertion:
    """Recorded, never checked. This is the undecidable region, written down."""

    claim: str
    source: str
    established_at_period: str
    checkable_from_data: bool = False


@dataclass
class ApplicabilityContract:
    l1: L1Structural = field(default_factory=L1Structural)
    l2: dict[str, L2Column] = field(default_factory=dict)
    l3: L3Grain = field(default_factory=L3Grain)
    l4: L4Spec = field(default_factory=L4Spec)
    l5: list[L5SemanticAssertion] = field(default_factory=list)


# --------------------------------------------------------------------------
# Detection capability
# --------------------------------------------------------------------------


@dataclass
class DetectionFloor:
    """What the contract CLAIMS it can see. Committed before any drift exists."""

    metric: str
    alpha: float
    power: float
    assumption: str
    min_detectable_shift_pct: float          # single-period test
    sustained_min_detectable_shift_pct: float
    sustained_window: int
    baseline_window: int
    baseline_mean: float
    baseline_sd: float
    baseline_cv: float
    baseline_commit: str
    baseline_sha256: str
    method_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "alpha": self.alpha,
            "power": self.power,
            "assumption": self.assumption,
            "min_detectable_shift_pct": self.min_detectable_shift_pct,
            "sustained_min_detectable_shift_pct": self.sustained_min_detectable_shift_pct,
            "sustained_window": self.sustained_window,
            "baseline_window": self.baseline_window,
            "baseline_mean": self.baseline_mean,
            "baseline_sd": self.baseline_sd,
            "baseline_cv": self.baseline_cv,
            "baseline_commit": self.baseline_commit,
            "baseline_sha256": self.baseline_sha256,
            "method_version": self.method_version,
        }


# --------------------------------------------------------------------------
# Evidence vector -- orthogonal dimensions, per-dimension decay (amendment B3)
# --------------------------------------------------------------------------


@dataclass
class EvidenceClaim:
    dimension: str          # semantic_meaning | aggregate_correctness | structural_fit
    source: str
    established_at_index: int
    staleness_tolerance_periods: int

    def periods_since(self, now_index: int) -> int:
        return now_index - self.established_at_index

    def is_stale(self, now_index: int) -> bool:
        return self.periods_since(now_index) > self.staleness_tolerance_periods


@dataclass
class EvidenceVector:
    """Not a ladder. Each dimension is strong where the others are blind."""

    semantic_meaning: EvidenceClaim
    aggregate_correctness: EvidenceClaim
    structural_fit: EvidenceClaim

    def claims(self) -> list[EvidenceClaim]:
        return [self.semantic_meaning, self.aggregate_correctness, self.structural_fit]

    def stale_dimensions(self, now_index: int) -> list[str]:
        return [c.dimension for c in self.claims() if c.is_stale(now_index)]

    def periods_since_independent_anchor(self, now_index: int) -> int:
        """Headline operator number: age of the aggregate_correctness anchor."""
        return self.aggregate_correctness.periods_since(now_index)


# --------------------------------------------------------------------------
# The warranted procedure (amendment C7)
# --------------------------------------------------------------------------


@dataclass
class WarrantedProcedure:
    procedure_id: str
    version: int
    applicability: ApplicabilityContract
    detection_capability: DetectionFloor | None
    evidence: EvidenceVector

    def undecidable_region(self) -> dict[str, Any]:
        """What this machinery cannot establish. Required component, not a footnote."""
        floor = self.detection_capability
        return {
            "unverifiable_semantic_assertions": [
                a.claim for a in self.applicability.l5 if not a.checkable_from_data
            ],
            "measure_shifts_below_pct": None if floor is None else floor.min_detectable_shift_pct,
            "sustained_shifts_below_pct": (
                None if floor is None else floor.sustained_min_detectable_shift_pct
            ),
            "note": (
                "Changes smaller than the stated floors are not reliably distinguishable "
                "from normal variation. Absence of an alarm is not evidence of semantic "
                "continuity."
            ),
        }


@dataclass
class AuthorizationResult:
    """Output of the decision path.

    `semantic_status` is hard-coded to 'not_established'. There is no code path
    that sets it to anything else. This is the N1 guard, enforced by construction
    rather than by review.
    """

    state: AuthorizationState
    reasons: list[EscalationReason]
    failed_predicates: list[dict[str, Any]]
    l4_report: dict[str, Any]
    stale_dimensions: list[str]
    periods_since_independent_anchor: int
    undecidable_region: dict[str, Any]
    semantic_status: str = "not_established"

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reasons": [r.value for r in self.reasons],
            "failed_predicates": self.failed_predicates,
            "l4_report": self.l4_report,
            "stale_dimensions": self.stale_dimensions,
            "periods_since_independent_anchor": self.periods_since_independent_anchor,
            "undecidable_region": self.undecidable_region,
            "semantic_status": self.semantic_status,
        }
