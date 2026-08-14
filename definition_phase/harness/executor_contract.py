#!/usr/bin/env python3
"""What the executor can actually honour — declared once, checked from both sides.

This module exists because of PRO-2, the recurring defect shape in this codebase:
**a capability declared in one layer and silently not consumed by another.** Four
confirmed instances before this file existed:

  1. Two `period_measure` fields both validate; the executor honours only the
     last. Half the data disappears with no signal (Experiment M, shape S3).
  2. `coerce` is a declared transform op the executor implements nowhere. A
     recipe using it validates, dispatches EXECUTE, and the transform is dropped.
  3. A sheet with role `metadata` validates and contributes nothing to the
     output. Nothing says so.
  4. Fifteen of twenty-three validator problem codes were unclassified by the
     dispatcher, so a recipe the validator declared INVALID dispatched to
     EXECUTE.

The pattern in every case is the same: one side declares a capability, the other
side does not implement it, and nothing compares the two. So the fix is not four
patches — it is a single place where support is declared, plus assertions that
run in both directions and fail loudly when they disagree.

Rules for changing this file:

  * Adding a value to a format enum (`TRANSFORM_OPS`, `FIELD_ROLES`,
    `SHEET_ROLES`) without classifying it here fails `assert_contract_total()`.
  * Marking something SUPPORTED that the executor does not implement is caught
    by the executor's own conformance test.
  * A capability the executor cannot honour belongs in the UNSUPPORTED map WITH
    A REASON, not left out.

Silence is the failure mode; both maps are mandatory.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recipe import FIELD_ROLES, SHEET_ROLES, TRANSFORM_OPS  # noqa: E402

# --- transforms -------------------------------------------------------------
SUPPORTED_TRANSFORM_OPS = frozenset({"unpivot", "derive"})
UNSUPPORTED_TRANSFORM_OPS = {
    "coerce": ("declared by the format but implemented nowhere in the executor; "
               "a recipe using it would have its transform silently dropped"),
}

# --- roles ------------------------------------------------------------------
SUPPORTED_FIELD_ROLES = frozenset({"id", "measure", "period_measure", "metadata", "derived"})
UNSUPPORTED_FIELD_ROLES: dict[str, str] = {}

SUPPORTED_SHEET_ROLES = frozenset({"data", "ignore"})
UNSUPPORTED_SHEET_ROLES = {
    "metadata": ("the executor reads only data sheets, so a metadata sheet "
                 "contributes nothing to the output and nothing reports it"),
}

# --- shape limits -----------------------------------------------------------
# One unpivot per sheet. The executor keeps a single unpivot binding, so a
# second one overwrites the first (Experiment M, S3).
MAX_UNPIVOTS_PER_SHEET = 1
SUPPORTED_DERIVE_SOURCES = frozenset({"sheet_name"})


def assert_contract_total() -> None:
    """Every value of every format enum must be classified as supported or not.

    Raised at import time by the validator, so an enum value added without a
    decision cannot reach a run.
    """
    problems: list[str] = []
    for name, declared, supported, unsupported in (
        ("TRANSFORM_OPS", TRANSFORM_OPS, SUPPORTED_TRANSFORM_OPS, UNSUPPORTED_TRANSFORM_OPS),
        ("FIELD_ROLES", FIELD_ROLES, SUPPORTED_FIELD_ROLES, UNSUPPORTED_FIELD_ROLES),
        ("SHEET_ROLES", SHEET_ROLES, SUPPORTED_SHEET_ROLES, UNSUPPORTED_SHEET_ROLES),
    ):
        unclassified = [v for v in declared if v not in supported and v not in unsupported]
        if unclassified:
            problems.append(
                f"{name}: {unclassified} declared by the format but neither supported "
                f"nor listed as unsupported — classify them in executor_contract.py")
        both = [v for v in declared if v in supported and v in unsupported]
        if both:
            problems.append(f"{name}: {both} listed as BOTH supported and unsupported")
        for value, reason in unsupported.items():
            if not str(reason).strip():
                problems.append(f"{name}: unsupported value {value!r} has no reason")
    if problems:
        raise RuntimeError("executor contract is not total:\n  " + "\n  ".join(problems))


def unsupported_reason(kind: str, value: str) -> str | None:
    """The recorded reason a capability is unsupported, or None if supported."""
    table = {"transform_op": UNSUPPORTED_TRANSFORM_OPS,
             "field_role": UNSUPPORTED_FIELD_ROLES,
             "sheet_role": UNSUPPORTED_SHEET_ROLES}.get(kind, {})
    return table.get(value)


assert_contract_total()


if __name__ == "__main__":
    assert_contract_total()
    print("contract is total:")
    for name, sup, unsup in (
        ("transform ops", SUPPORTED_TRANSFORM_OPS, UNSUPPORTED_TRANSFORM_OPS),
        ("field roles", SUPPORTED_FIELD_ROLES, UNSUPPORTED_FIELD_ROLES),
        ("sheet roles", SUPPORTED_SHEET_ROLES, UNSUPPORTED_SHEET_ROLES),
    ):
        print(f"  {name:14} supported={sorted(sup)}")
        for value, reason in unsup.items():
            print(f"  {'':14} UNSUPPORTED {value}: {reason}")
    print(f"  max unpivots per sheet: {MAX_UNPIVOTS_PER_SHEET}")
