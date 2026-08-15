#!/usr/bin/env python3
"""The EXECUTOR half: join and compute exactly what the model declares.

Deterministic. No clock, no network, no hidden state, and no judgement of its
own. Two rules carried from the reservation executor because they are what makes
the split worth having:

1. **Join on the key the model declares, and handle missing/ambiguous the way
   the model declares.** Not the way the code finds convenient.
2. **Refuse a model this executor cannot honour** rather than approximating it.

## Arithmetic is Decimal, and that is load-bearing

Operands arrive as strings and are parsed with `Decimal`. Using float would make
`7 x 0.10` emit `0.7000000000000001` -- a number that is wrong, looks fine, and
that nothing records. For a task whose whole purpose is a *deterministic computed
output*, that is a faithfulness failure, not a display detail. `run_enrichment.py`
carries a canary that runs the same case in float and requires the check to
notice.

See `enrichment/design/enrichment_model_v1.md`.
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

import enrichment_model  # noqa: E402  (registers the task type)
from enrichment_model import (  # noqa: E402
    driving_source, load_rows, lookup_of, on_non_numeric, outputs_of, validate,
)
from task_model import TaskModel as Model, assert_refusal, load_model  # noqa: E402


class UnhonourableModel(Exception):
    """The model declares something this executor cannot evaluate."""


SUPPORTED_OPS = ("multiply",)
SUPPORTED_POLICIES = ("refuse_row", "refuse_run")


@dataclass
class Enrichment:
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list[Any]] = dc_field(default_factory=list)
    refused: list[dict] = dc_field(default_factory=list)
    run_refused: Optional[str] = None      # set when a policy said refuse_run

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows,
                "refused": self.refused, "run_refused": self.run_refused}


def _to_number(text: Any) -> Optional[Decimal]:
    """Decimal, or None if this is not a number.

    Deliberately strict: no stripping of currency symbols, no thousands
    separators, no locale guessing. An operand the model calls a number and that
    is not one is refused under the declared policy, never coerced.
    """
    if isinstance(text, bool) or text is None:
        return None
    try:
        return Decimal(str(text).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def _apply(op: str, left: Decimal, right: Decimal) -> Decimal:
    if op == "multiply":
        return left * right
    raise UnhonourableModel(f"op {op!r} is declared but not implemented")


def _format(value: Decimal) -> str:
    """Emit the exact computed value as text.

    Returned as a string so the faithful Decimal result is not handed to a float
    on the way out -- which would reintroduce the very error Decimal avoids.

    NOT normalized. `Decimal.normalize()` turns 0.70 into 0.7, and Decimal
    multiplication gives a scale that is the SUM of the operand scales, so 0.70
    is what the declared computation actually produced. Stripping it would be a
    representation change nobody declared -- PRO-2 instance 9, where a helper
    trimmed values on behalf of every construct that used it.
    """
    return format(value, "f")


def _refuse_run(out: "Enrichment", reason: str) -> "Enrichment":
    """A refused run delivers NO rows.

    Returning the rows accumulated before the refusal would hand a consumer a
    partial table alongside a refusal, and partial output that looks like a
    result is exactly what the cross-sheet work spent five laws on. The reason
    survives; the rows do not.
    """
    out.rows = []
    out.run_refused = reason
    return out


def execute(model: Model, base: Path,
            multiply: Optional[Callable[[Decimal, Decimal], Any]] = None) -> Enrichment:
    """Enrich the driving source against the lookup source.

    `multiply` exists ONLY for the float canary in run_enrichment.py: it lets the
    harness substitute unfaithful arithmetic and prove the check notices. It
    defaults to the real, Decimal path and nothing in production passes it.
    """
    report = validate(model, base)
    if not report.valid:
        raise UnhonourableModel(
            "refusing to execute an invalid model: "
            + "; ".join(str(p) for p in report.problems[:4]))

    lookup = lookup_of(model)
    outputs = outputs_of(model)
    driving = driving_source(model)

    for out in outputs:
        if out.compute is not None and out.compute.op not in SUPPORTED_OPS:
            raise UnhonourableModel(f"op {out.compute.op!r} declared, not implemented")
    for policy in (lookup.on_missing, lookup.on_ambiguous, on_non_numeric(model)):
        if policy not in SUPPORTED_POLICIES:
            raise UnhonourableModel(f"policy {policy!r} declared, not implemented")

    driving_rows = load_rows(model, base, driving)
    reference = load_rows(model, base, lookup.into)

    # Index by the DECLARED right-hand key. Every matching row is kept, so
    # ambiguity is a fact the executor can report rather than one it resolves by
    # taking the first.
    index: dict[str, list[dict]] = {}
    for row in reference:
        index.setdefault(str(row.get(lookup.match_right, "")), []).append(row)

    out = Enrichment(columns=[o.target for o in outputs])

    for row in driving_rows:
        key = str(row.get(lookup.match_left, ""))
        matches = index.get(key, [])

        if len(matches) == 0:
            if lookup.on_missing == "refuse_run":
                return _refuse_run(out, f"MISSING_PRODUCT for {key!r}")
            out.refused.append({"key": key,
                                "reason": assert_refusal("enrichment", "MISSING_PRODUCT"),
                                "row": row})
            continue
        if len(matches) > 1:
            if lookup.on_ambiguous == "refuse_run":
                return _refuse_run(out, f"AMBIGUOUS_PRODUCT: {key!r} matches "
                                        f"{len(matches)} reference rows")
            out.refused.append({"key": key,
                                "reason": assert_refusal("enrichment", "AMBIGUOUS_PRODUCT"),
                                "row": row})
            continue

        env = {driving: row, lookup.into: matches[0]}

        values: list[Any] = []
        refusal: Optional[str] = None
        for spec in outputs:
            if spec.compute is not None:
                left = _to_number(env[spec.compute.left.source].get(spec.compute.left.field))
                right = _to_number(env[spec.compute.right.source].get(spec.compute.right.field))
                if left is None or right is None:
                    refusal = assert_refusal("enrichment", "NON_NUMERIC_OPERAND")
                    break
                product = (multiply(left, right) if multiply
                           else _apply(spec.compute.op, left, right))
                values.append(_format(product) if isinstance(product, Decimal)
                              else product)
                continue
            raw = env[spec.ref.source].get(spec.ref.field)
            if spec.type == "number":
                # `type: number` authorises CHECKING that the value is a number,
                # not rewriting how it was written. The source says "0.10"; a
                # pass-through that emitted "0.1" would be an undeclared
                # normalisation of someone else's data. A COMPUTED value is
                # different -- it has no source text, so its representation is
                # whatever the arithmetic produced.
                if _to_number(raw) is None:
                    refusal = assert_refusal("enrichment", "NON_NUMERIC_OPERAND")
                    break
                values.append(raw)
            else:
                values.append(raw)

        if refusal:
            if on_non_numeric(model) == "refuse_run":
                return _refuse_run(out, f"{refusal} on {key!r}")
            out.refused.append({"key": key, "reason": refusal, "row": row})
            continue

        out.rows.append(values)

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.stderr.write("usage: execute_enrichment.py <model.json>\n")
        return 2
    model_path = Path(argv[0]).resolve()
    base = model_path.parent.parent
    result = execute(load_model(model_path), base)
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    return 1 if result.run_refused else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
