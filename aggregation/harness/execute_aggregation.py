#!/usr/bin/env python3
"""The EXECUTOR half: group and aggregate exactly what the model declares.

Deterministic. Decimal arithmetic, for the same reason the enrichment executor
uses it: `0.10 + 0.20` in float is `0.30000000000000004`, a number that is wrong,
looks fine, and is recorded nowhere.

## The hazard that is NEW to this shape

Reservation decides one value. Enrichment decides each row independently. Here a
row's contribution lands in an accumulator shared with the other rows of its
group, so a whole class of failure becomes available that neither earlier task
could have: **the accumulator leaking between groups**. A single shared
accumulator produces totals that look plausible and are the sum of everything.

`accumulator_factory` exists so the harness can induce exactly that and prove the
check notices. It defaults to the real, per-group path and nothing but the canary
passes it.

See `aggregation/design/aggregation_model_v1.md`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import aggregation_model  # noqa: E402  (registers the task type)
from aggregation_model import (  # noqa: E402
    declared_inputs, resolve, selections, selects,  # noqa: E402
    aggregates_of, driving_source, group_by, group_order, on_non_numeric, validate,
)
from task_model import TaskModel as Model, assert_refusal, load_collection, load_model  # noqa: E402

SUPPORTED_OPS = ("count", "sum")
SUPPORTED_GROUP_ORDERS = ("first_appearance", "sorted_by_key")
SUPPORTED_POLICIES = ("refuse_row", "refuse_run")


class UnhonourableModel(Exception):
    """The model declares something this executor cannot evaluate."""


@dataclass
class Aggregation:
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list[Any]] = dc_field(default_factory=list)
    refused: list[dict] = dc_field(default_factory=list)
    run_refused: Optional[str] = None
    # Rows the DECLARED selection excluded. Reported, never silent: a total
    # over a subset must say it was a subset, or nobody downstream can tell the
    # difference between "no invoices" and "filtered them all out".
    not_selected: int = 0
    selection: list = dc_field(default_factory=list)
    # What THIS run was given. Recorded so a stored result says which period it
    # covers, rather than leaving that to whoever kept the filename.
    run_parameters: dict = dc_field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows,
                "refused": self.refused, "run_refused": self.run_refused,
                "not_selected": self.not_selected, "selection": self.selection,
                "run_parameters": self.run_parameters}


def _to_number(text: Any) -> Optional[Decimal]:
    if isinstance(text, bool) or text is None:
        return None
    try:
        return Decimal(str(text).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def _refuse_run(out: Aggregation, reason: str) -> Aggregation:
    """A refused run delivers NO rows -- as in the enrichment executor."""
    out.rows = []
    out.run_refused = reason
    return out


def execute(model: Model, base: Path,
            accumulator_factory: Optional[Callable[[], dict]] = None,
            params: Optional[dict] = None) -> Aggregation:
    report = validate(model, base)
    if not report.valid:
        raise UnhonourableModel(
            "refusing to execute an invalid model: "
            + "; ".join(str(p) for p in report.problems[:4]))

    aggregates = aggregates_of(model)
    keys = group_by(model)
    order = group_order(model)
    policy = on_non_numeric(model)

    for agg in aggregates:
        if agg.op not in SUPPORTED_OPS:
            raise UnhonourableModel(f"op {agg.op!r} declared, not implemented")
    if order not in SUPPORTED_GROUP_ORDERS:
        raise UnhonourableModel(f"group_order {order!r} declared, not implemented")
    if policy not in SUPPORTED_POLICIES:
        raise UnhonourableModel(f"policy {policy!r} declared, not implemented")

    new_accumulator = accumulator_factory or dict
    rows = load_collection(model, base, driving_source(model))
    out = Aggregation(columns=list(keys) + [a.target for a in aggregates])

    # DECLARED row selection, applied before grouping. Excluded rows are
    # counted and the clauses are reported, so a total over a subset says it
    # was a subset -- nothing is scoped outside the model.
    clauses = resolve(selections(model), params or {})
    out.run_parameters = {k: str(v) for k, v in sorted((params or {}).items())
                          if k in declared_inputs(model)}
    if clauses:
        kept = [r for r in rows if isinstance(r, dict) and selects(r, clauses)]
        out.not_selected = len(rows) - len(kept)
        out.selection = [f"{c.field} {c.op} {c.value!r}" for c in clauses]
        rows = kept

    groups: dict[tuple, dict] = {}
    first_seen: list[tuple] = []

    for row in rows:
        # Every numeric operand this row will contribute is checked BEFORE any
        # accumulator is touched. A row that fails halfway would otherwise have
        # already added to some totals and not others -- partial honour inside a
        # single row, which is worse than refusing it.
        values: dict[str, Decimal] = {}
        bad = False
        for agg in aggregates:
            if agg.op != "sum":
                continue
            num = _to_number(row.get(agg.field))
            if num is None:
                bad = True
                break
            values[agg.target] = num
        if bad:
            reason = assert_refusal("aggregation", "NON_NUMERIC_OPERAND")
            if policy == "refuse_run":
                return _refuse_run(out, f"{reason} in row {row!r}")
            out.refused.append({"reason": reason, "row": row})
            continue

        key = tuple(str(row.get(k, "")) for k in keys)
        if key not in groups:
            groups[key] = new_accumulator()
            first_seen.append(key)
        acc = groups[key]
        for agg in aggregates:
            if agg.op == "count":
                acc[agg.target] = acc.get(agg.target, 0) + 1
            else:
                acc[agg.target] = acc.get(agg.target, Decimal(0)) + values[agg.target]

    # DECLARED order, not whichever order the accumulator filled.
    ordered = first_seen if order == "first_appearance" else sorted(groups)
    for key in ordered:
        acc = groups[key]
        emitted: list[Any] = list(key)
        for agg in aggregates:
            value = acc.get(agg.target, 0 if agg.op == "count" else Decimal(0))
            emitted.append(str(value) if isinstance(value, Decimal) else value)
        out.rows.append(emitted)

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.stderr.write("usage: execute_aggregation.py <model.json>\n")
        return 2
    model_path = Path(argv[0]).resolve()
    base = model_path.parent.parent
    result = execute(load_model(model_path), base)
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    return 1 if result.run_refused else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
