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

# --- sheet reference kinds --------------------------------------------------
# No format enum names these: a sheet entry may reference `sheet:X` or
# `sheetset:Y`, and that is a structural property of the referent, not an enum
# value. Level-two completeness therefore could not see it, and a sheetset data
# entry validated cleanly while the executor could not run it at all. Found by
# the level-three parity check (semantic_parity.py), which tests behaviour rather
# than vocabulary -- the seventh instance of the PRO-2 family.
SUPPORTED_SHEET_REFS = frozenset({"sheet"})
UNSUPPORTED_SHEET_REFS = {
    "sheetset": ("the executor resolves a single sheet per data entry and cannot "
                 "union a sheetset, so the recipe would refuse at execution after "
                 "validating cleanly"),
}

# --- legal COMPOSITION, not merely supported atoms ---------------------------
# PRO-2 instance 8: `unpivot` is supported and `id` is supported, and the pair
# `id x unpivot` has no defined meaning. The language admitted a sentence the
# executor only understood half of -- it read the transform and dropped it, and
# the declared var_target column never appeared.
#
# So support is declared per PAIRING. The rule enforced from it:
#
#     every declared transform must either be valid for the role it is attached
#     to and be fully honoured, or validation must refuse the recipe
#
# There is deliberately no "ignore a meaningless transform because it probably
# was not intended" branch. That is exactly how partial honour sneaks back in.
#
# None means "no transform", which is itself a pairing decision rather than an
# absence: period_measure and derived REQUIRE theirs.
ROLE_TRANSFORM_PAIRS: dict[str, frozenset] = {
    "id":             frozenset({None}),
    "measure":        frozenset({None}),
    "metadata":       frozenset({None}),
    "period_measure": frozenset({"unpivot"}),
    "derived":        frozenset({"derive"}),
}


def pairing_reason(role: str, transform_op) -> str | None:
    """Why this role/transform pairing cannot be honoured, or None if it can."""
    allowed = ROLE_TRANSFORM_PAIRS.get(role)
    if allowed is None:
        return None                       # unknown role: reported elsewhere
    if transform_op in allowed:
        return None
    shown = sorted(x for x in allowed if x) or ["no transform"]
    got = transform_op or "no transform"
    return (f"role {role!r} with {got!r}: the executor honours a transform only "
            f"for the roles it is defined on, so this one would be read and "
            f"silently dropped. {role!r} allows {shown}")


# --- shape limits -----------------------------------------------------------
# One unpivot per sheet. The executor keeps a single unpivot binding, so a
# second one overwrites the first (Experiment M, S3).
MAX_UNPIVOTS_PER_SHEET = 1
SUPPORTED_DERIVE_SOURCES = frozenset({"sheet_name"})


# --- normalisation: a declared semantic operation ---------------------------
# PRO-2 instance 9. Whitespace trimming used to live inside `row_values()`, a
# helper sitting underneath every construct that reads a cell. Constructs that
# genuinely want trimming (header matching, label comparison) inherited it, and
# so did the one construct that must never have it: the literal value of a field.
#
# The fix is NOT to delete the trim. That would repair literal values and quietly
# break header matching — the classic whack-a-mole. Instead normalisation becomes
# something a construct DECLARES, and the default is to preserve.
NORMALIZATIONS: dict[str, str] = {
    "none":           "the admitted value is preserved exactly",
    "trim_whitespace": "leading and trailing whitespace removed",
    "trim_casefold":  "trimmed, then case-folded for comparison",
}

# Every construct that reads a source cell must appear here. `none` is not a
# fallback for constructs nobody classified — an unlisted construct raises.
CONSTRUCT_NORMALIZATION: dict[str, str] = {
    # The value a field emits. The one construct that must preserve.
    "field_value":            "none",
    # Matching `@Name` against a header cell.
    "header_label":           "trim_casefold",
    # `label_in` exclusion rules comparing a cell against declared labels.
    "label_in":               "trim_casefold",
    # Sheetset member header parity.
    "sheetset_header_parity": "trim_casefold",
    # PREDICATES over the source, not emitted values. Deciding that a cell of
    # spaces counts as blank is a legitimate declared choice; silently EMITTING
    # "" for it is not. Instance 9 is the second thing, not the first.
    "blank_detection":        "trim_whitespace",
    # Numeric parsing for `reconcile` and `require_numeric`.
    "numeric_parse":          "trim_whitespace",
    # Parsing a declared `boolean`. Trimming and folding here is AUTHORISED by
    # the declaration; the same trim applied to a declared `string` is not.
    "boolean_parse":          "trim_casefold",
    # An unpivot emits the HEADER LABEL as a value. Neither neighbour's rule is
    # automatically right, so it gets its own: a header cell's surrounding
    # whitespace is layout, and it is trimmed on the way in for matching, so
    # emitting the untrimmed form would make the emitted label differ from the
    # label the recipe matched against. Case is NOT folded — that would destroy
    # information in something being emitted rather than compared.
    "unpivot_var_label":      "trim_whitespace",
}


def normalize(value: str, normalization: str) -> str:
    """Apply exactly the named normalisation. Unknown names raise."""
    if normalization == "none":
        return value
    if normalization == "trim_whitespace":
        return value.strip()
    if normalization == "trim_casefold":
        return value.strip().casefold()
    raise KeyError(f"unknown normalization {normalization!r}; "
                   f"declared: {sorted(NORMALIZATIONS)}")


def normalize_for(construct: str, value: str) -> str:
    """Normalise a cell for a named construct, per the declared contract."""
    try:
        rule = CONSTRUCT_NORMALIZATION[construct]
    except KeyError:
        raise KeyError(
            f"construct {construct!r} reads source cells but declares no "
            f"normalisation. Classify it in CONSTRUCT_NORMALIZATION — defaulting "
            f"to 'none' would silently re-create PRO-2 instance 9 in reverse."
        ) from None
    return normalize(value, rule)


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
        ("SHEET_REFS", ("sheet", "sheetset"), SUPPORTED_SHEET_REFS, UNSUPPORTED_SHEET_REFS),
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
    undeclared = {c: n for c, n in CONSTRUCT_NORMALIZATION.items() if n not in NORMALIZATIONS}
    if undeclared:
        problems.append(f"CONSTRUCT_NORMALIZATION: {undeclared} name normalisations "
                        f"that do not exist; declared: {sorted(NORMALIZATIONS)}")
    if problems:
        raise RuntimeError("executor contract is not total:\n  " + "\n  ".join(problems))


def unsupported_reason(kind: str, value: str) -> str | None:
    """The recorded reason a capability is unsupported, or None if supported."""
    table = {"transform_op": UNSUPPORTED_TRANSFORM_OPS,
             "field_role": UNSUPPORTED_FIELD_ROLES,
             "sheet_role": UNSUPPORTED_SHEET_ROLES,
             "sheet_ref": UNSUPPORTED_SHEET_REFS}.get(kind, {})
    return table.get(value)


assert_contract_total()


if __name__ == "__main__":
    assert_contract_total()
    print("contract is total:")
    for name, sup, unsup in (
        ("transform ops", SUPPORTED_TRANSFORM_OPS, UNSUPPORTED_TRANSFORM_OPS),
        ("field roles", SUPPORTED_FIELD_ROLES, UNSUPPORTED_FIELD_ROLES),
        ("sheet roles", SUPPORTED_SHEET_ROLES, UNSUPPORTED_SHEET_ROLES),
        ("sheet refs", SUPPORTED_SHEET_REFS, UNSUPPORTED_SHEET_REFS),
    ):
        print(f"  {name:14} supported={sorted(sup)}")
        for value, reason in unsup.items():
            print(f"  {'':14} UNSUPPORTED {value}: {reason}")
    print(f"  max unpivots per sheet: {MAX_UNPIVOTS_PER_SHEET}")
