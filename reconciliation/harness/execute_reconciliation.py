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
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import reconciliation_model  # noqa: E402  (registers the task type)
from reconciliation_model import (  # noqa: E402
    classify, left, match_on, on_duplicate_key, output_order, right, validate,
)
from task_model import TaskModel as Model, assert_refusal, load_collection, load_model  # noqa: E402

SUPPORTED_OUTPUT_ORDERS = ("left_then_right", "sorted_by_key")
SUPPORTED_DUPLICATE_POLICIES = ("refuse_run", "refuse_key")


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

    lname, rname = left(model), right(model)
    lfield, rfield = match_on(model)
    labels = classify(model)

    left_rows = load_collection(model, base, lname)
    right_rows = load_collection(model, base, rname)

    left_index, left_order, left_keyless = _index(left_rows, lfield)
    right_index, right_order, right_keyless = _index(right_rows, rfield)

    out = Reconciliation(columns=[lfield, "relation"])

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
        relation = "both" if (in_left and in_right) else ("only_left" if in_left
                                                          else "only_right")
        out.rows.append([key, labels[relation]])

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
