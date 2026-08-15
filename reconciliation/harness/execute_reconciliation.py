#!/usr/bin/env python3
"""The EXECUTOR half: classify the UNION of two peer sources by relationship.

Deterministic. No arithmetic, no dates, no coercion -- this shape has no numeric
semantics at all, which is why it can answer the question the three earlier tasks
cannot: whether an `on_non_numeric`-shaped policy is common infrastructure or a
family resemblance among tasks written by one hand in one week.

## Neither side is subordinate

Enrichment consults a reference table and never iterates it. Here the union is
built from BOTH key sets, so a key present only on the right survives. An
implementation that walked the left side and looked up the right -- an ordinary
left join -- would silently drop every right-only row and produce a table with
nothing visibly wrong with it. `run_reconciliation.py` requires the right-only
case for exactly that reason.

See `reconciliation/design/reconciliation_model_v1.md`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import reconciliation_model  # noqa: E402  (registers the task type)
from reconciliation_model import (  # noqa: E402
    classify, compare_of, compares_attributes, left, match_on, on_duplicate_key,
    on_non_numeric, output_order, right, validate,
)
from task_model import TaskModel as Model, assert_refusal, load_collection, load_model  # noqa: E402

SUPPORTED_OUTPUT_ORDERS = ("left_then_right", "sorted_by_key")
SUPPORTED_DUPLICATE_POLICIES = ("refuse_run", "refuse_key")
SUPPORTED_COMPARISONS = ("exact", "trim", "casefold", "trim_casefold", "within")
SUPPORTED_NON_NUMERIC_POLICIES = ("refuse_run", "refuse_key")


def _to_number(value):
    """Decimal, or None if this is not a number.

    Deliberately strict, as in the two numeric executors: no currency symbols,
    no thousands separators, no locale guessing. An operand the model asks to
    compare numerically and that is not a number is handled by the DECLARED
    policy, never coerced into one.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None

# Absent is not a value. A compared attribute present on one side and missing on
# the other is a DIFFERENCE, reported with None for the side that lacks it --
# never silently treated as equal to "" and never quietly skipped.
ABSENT = None


def _normalised(value, how: str):
    """The form used for COMPARING. Never the form reported.

    PRO-2 instance 9: a predicate may normalise, an emitted value may not. The
    difference report below carries the ORIGINAL text, so a reviewer sees what
    the sources actually say rather than what the comparison made of them.
    """
    if value is ABSENT:
        return ABSENT
    text = str(value)
    if how == "exact":
        return text
    if how == "trim":
        return text.strip()
    if how == "casefold":
        return text.casefold()
    if how == "trim_casefold":
        return text.strip().casefold()
    raise UnhonourableModel(f"comparison {how!r} is declared but not implemented")


class NonNumericOperand(Exception):
    """A numerically-compared operand is not a number. Handled by the policy."""

    def __init__(self, field: str, left, right):
        super().__init__(field)
        self.field, self.left, self.right = field, left, right


def _differences(left_row: dict, right_row: dict,
                 compares: tuple[dict, ...]) -> list[dict]:
    """Which declared attributes differ, with the values as WRITTEN.

    Every reported value is the ORIGINAL text on both branches: the string
    comparisons normalise only to decide, and the numeric one reports the
    operands as written alongside the computed delta. PRO-2 instance 9 does not
    stop applying because the comparison became arithmetic.
    """
    out: list[dict] = []
    for spec in compares:
        field = str(spec.get("field", ""))
        how = str(spec.get("comparison", ""))
        lv = left_row.get(field, ABSENT)
        rv = right_row.get(field, ABSENT)

        if how == "within":
            ln, rn = _to_number(lv), _to_number(rv)
            if ln is None or rn is None:
                raise NonNumericOperand(field, lv, rv)
            tolerance = Decimal(str(spec.get("tolerance")))
            delta = abs(ln - rn)
            if delta > tolerance:
                out.append({"field": field, "comparison": how,
                            "left": lv, "right": rv,
                            "tolerance": str(tolerance), "delta": str(delta)})
            continue

        if _normalised(lv, how) != _normalised(rv, how):
            out.append({"field": field, "comparison": how, "left": lv, "right": rv})
    return out


class UnhonourableModel(Exception):
    """The model declares something this executor cannot evaluate."""


@dataclass
class Reconciliation:
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list[Any]] = dc_field(default_factory=list)
    refused: list[dict] = dc_field(default_factory=list)
    run_refused: Optional[str] = None

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows,
                "refused": self.refused, "run_refused": self.run_refused}


def _refuse_run(out: Reconciliation, reason: str) -> Reconciliation:
    """A refused run delivers NO rows -- as in the two earlier executors."""
    out.rows = []
    out.run_refused = reason
    return out


def _index(rows: list[dict], field: str) -> tuple[dict[str, list[dict]], list[str], list[dict]]:
    """key -> rows, key order of first appearance, and rows carrying NO key.

    A row without the declared match field is kept separate rather than filed
    under the empty string, which would pool every keyless row into one phantom
    key and classify it as though it were a real one.
    """
    index: dict[str, list[dict]] = {}
    order: list[str] = []
    keyless: list[dict] = []
    for row in rows:
        if field not in row or row.get(field) in (None, ""):
            keyless.append(row)
            continue
        key = str(row[field])
        if key not in index:
            index[key] = []
            order.append(key)
        index[key].append(row)
    return index, order, keyless


def execute(model: Model, base: Path) -> Reconciliation:
    report = validate(model, base)
    if not report.valid:
        raise UnhonourableModel(
            "refusing to execute an invalid model: "
            + "; ".join(str(p) for p in report.problems[:4]))

    order_mode = output_order(model)
    dup_policy = on_duplicate_key(model)
    if order_mode not in SUPPORTED_OUTPUT_ORDERS:
        raise UnhonourableModel(f"output_order {order_mode!r} declared, not implemented")
    if dup_policy not in SUPPORTED_DUPLICATE_POLICIES:
        raise UnhonourableModel(f"on_duplicate_key {dup_policy!r} declared, not implemented")

    compares = compare_of(model)
    for spec in compares:
        how = str(spec.get("comparison", ""))
        if how not in SUPPORTED_COMPARISONS:
            raise UnhonourableModel(f"comparison {how!r} declared, not implemented")
    nn_policy = on_non_numeric(model)
    if nn_policy and nn_policy not in SUPPORTED_NON_NUMERIC_POLICIES:
        raise UnhonourableModel(f"on_non_numeric {nn_policy!r} declared, not implemented")

    lname, rname = left(model), right(model)
    lfield, rfield = match_on(model)
    labels = classify(model)

    left_rows = load_collection(model, base, lname)
    right_rows = load_collection(model, base, rname)

    left_index, left_order, left_keyless = _index(left_rows, lfield)
    right_index, right_order, right_keyless = _index(right_rows, rfield)

    out = Reconciliation(columns=[lfield, "relation"]
                         + (["differences"] if compares else []))

    # A row that cannot be classified by a key it does not carry stops the run.
    # There is deliberately no policy for this: classifying it would require
    # inventing a key, and skipping it silently is the partial honour the earlier
    # tasks refuse.
    if left_keyless or right_keyless:
        reason = assert_refusal("reconciliation", "MISSING_MATCH_KEY")
        return _refuse_run(out, f"{reason}: {len(left_keyless)} row(s) in {lname!r} "
                                f"and {len(right_keyless)} in {rname!r} carry no "
                                f"match key")

    duplicates = ([(lname, k) for k, v in left_index.items() if len(v) > 1]
                  + [(rname, k) for k, v in right_index.items() if len(v) > 1])
    if duplicates and dup_policy == "refuse_run":
        reason = assert_refusal("reconciliation", "DUPLICATE_KEY")
        return _refuse_run(out, f"{reason}: {duplicates}")

    refused_keys = set()
    if duplicates:                          # dup_policy == "refuse_key"
        reason = assert_refusal("reconciliation", "DUPLICATE_KEY")
        for source, key in duplicates:
            refused_keys.add(key)
            out.refused.append({"key": key, "source": source, "reason": reason})

    # The UNION, built from both key sets. Walking only the left and looking up
    # the right is a left join, and would lose every right-only key.
    if order_mode == "left_then_right":
        keys = left_order + [k for k in right_order if k not in left_index]
    else:
        keys = sorted(set(left_index) | set(right_index))

    for key in keys:
        if key in refused_keys:
            continue
        in_left, in_right = key in left_index, key in right_index

        if not (in_left and in_right):
            relation = "only_left" if in_left else "only_right"
            out.rows.append([key, labels[relation]] + ([[]] if compares else []))
            continue

        if not compares:
            out.rows.append([key, labels["both"]])
            continue

        # Matched on the key. Whether the PAIR agrees is a separate question, and
        # one the model has to have asked -- an unasked comparison is why v1
        # reported carol as BOTH while her email had changed.
        try:
            diffs = _differences(left_index[key][0], right_index[key][0], compares)
        except NonNumericOperand as bad:
            reason = assert_refusal("reconciliation", "NON_NUMERIC_OPERAND")
            if nn_policy == "refuse_run":
                return _refuse_run(out, f"{reason}: {bad.field!r} on key {key!r}")
            out.refused.append({"key": key, "reason": reason, "field": bad.field,
                                "left": bad.left, "right": bad.right})
            continue
        relation = "both_different" if diffs else "both_same"
        out.rows.append([key, labels[relation], diffs])

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.stderr.write("usage: execute_reconciliation.py <model.json>\n")
        return 2
    model_path = Path(argv[0]).resolve()
    base = model_path.parent.parent
    result = execute(load_model(model_path), base)
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    return 1 if result.run_refused else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
