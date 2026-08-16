#!/usr/bin/env python3
"""The aggregation task's BODY: grouping keys and aggregates, declared not evaluated.

The third task shape, and the first with STATE ACROSS ROWS. Reservation decides
one value; enrichment decides each row independently against a reference table.
Here a row's contribution lands in an accumulator shared with other rows in its
group, which is a kind of failure neither earlier task could have.

Identity and sources are the shared envelope's job (`taskmodel/task_model.py`);
this file is the first task written ON that floor rather than migrated onto it.

Groups nothing and sums nothing — that is `execute_aggregation.py`.

See `aggregation/design/aggregation_model_v1.md`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

from task_model import (  # noqa: E402
    Problem, Report, TaskModel, TaskType, load_collection, register,
    validate as validate_envelope,
)

OPS = ("count", "sum")
# Row selection, kept as small as the job needs. `starts_with` on an ISO date
# expresses "this month" with no date arithmetic and no calendar knowledge.
SELECT_OPS = ("equals", "starts_with", "in_month")
GROUP_ORDERS = ("first_appearance", "sorted_by_key")
POLICIES = ("refuse_row", "refuse_run")
REFUSALS = ("NON_NUMERIC_OPERAND",)

# Which ops take a field, and which do not. A pairing rule rather than two
# independent enums: `sum` without a field has nothing to add, and `count` with
# one implies a filter it does not apply. PRO-2 instance 8 in the recipe line was
# exactly this -- `id` x `unpivot` were each supported and the PAIR meant nothing.
OP_TAKES_FIELD = {"count": False, "sum": True}

BODY_PROBLEM_CODES = (
    "missing_key",
    "unknown_source",
    "unknown_op",
    "unknown_policy",
    "unknown_group_order",
    "duplicate_target",
    "no_group_by",
    "no_aggregates",
    "unknown_select_op",
    "select_missing_key",
    "unknown_run_parameter",
    "select_value_and_value_from",
    "op_field_mismatch",
    "field_not_in_source",
    "malformed_data_file",
)


@dataclass(frozen=True)
class Aggregate:
    target: str
    op: str
    field: Optional[str] = None


def driving_source(model: TaskModel) -> str:
    return str(model.body.get("driving_source", ""))


def declared_inputs(model: TaskModel) -> tuple[str, ...]:
    """Parameters a RUN must supply. Configuration is the model; these are not.

    Which date field a period applies to is a task decision, settled once. WHICH
    period is run context and changes every execution. Encoding "the current
    month" in the executor would put that semantics outside the model again and
    make a run unreproducible, so a declared input has no default and no clock
    behind it: a run that does not supply one is refused.
    """
    return tuple(str(i) for i in (model.body.get("inputs") or ()))


@dataclass(frozen=True)
class Selection:
    """One declared row-selection clause.

    Selection is part of the MODEL, never something a caller does to the data
    on the way in. A run that quietly received a pre-filtered file would report
    a total over rows nobody declared, and nothing downstream could tell.
    """
    field: str
    op: str
    value: str = ""
    value_from: str = ""


def selections(model: TaskModel) -> tuple["Selection", ...]:
    return tuple(Selection(field=str(c.get("field", "")),
                           op=str(c.get("op", "")),
                           value=str(c.get("value", "")),
                           value_from=str(c.get("value_from", "")))
                 for c in (model.body.get("select") or ())
                 if isinstance(c, dict))


class MissingRunParameter(Exception):
    """A declared input the run did not supply. Never defaulted."""


def resolve(clauses: tuple, params: dict) -> tuple:
    """Bind `value_from` clauses to this run's parameters."""
    params = params or {}
    out = []
    for clause in clauses:
        if not clause.value_from:
            out.append(clause)
            continue
        if clause.value_from not in params:
            raise MissingRunParameter(
                f"select needs run parameter {clause.value_from!r}")
        out.append(Selection(clause.field, clause.op,
                             str(params[clause.value_from]), clause.value_from))
    return tuple(out)


def selects(row: dict, clauses: tuple) -> bool:
    """Every clause must hold. A missing field never matches."""
    for clause in clauses:
        value = row.get(clause.field)
        if value is None:
            return False
        text = str(value)
        if clause.op == "equals" and text != clause.value:
            return False
        if clause.op == "starts_with" and not text.startswith(clause.value):
            return False
        if clause.op == "in_month":
            # Deliberately NOT calendar arithmetic. The month is supplied as an
            # ISO `YYYY-MM` and matched as a prefix of an ISO date, so the
            # executor knows nothing about calendars and a run is reproducible
            # from its parameters alone.
            if not text.startswith(f"{clause.value}-"):
                return False
    return True


def group_by(model: TaskModel) -> tuple[str, ...]:
    return tuple(model.body.get("group_by") or ())


def group_order(model: TaskModel) -> str:
    return str(model.body.get("group_order", ""))


def aggregates_of(model: TaskModel) -> tuple[Aggregate, ...]:
    return tuple(Aggregate(target=str(a.get("target", "")),
                           op=str(a.get("op", "")),
                           field=a.get("field"))
                 for a in (model.body.get("aggregates") or ()))


def on_non_numeric(model: TaskModel) -> str:
    return str(model.body.get("on_non_numeric", ""))


def validate_body(model: TaskModel, base: Path) -> list[Problem]:
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"
    driving = driving_source(model)

    columns: dict[str, set[str]] = {}
    for name in model.sources:
        try:
            rows = load_collection(model, base, name)
        except (OSError, ValueError):
            continue                       # already reported by the envelope
        if not all(isinstance(r, dict) for r in rows):
            problems.append(Problem("malformed_data_file", f"{where}:sources.{name}",
                                    "expected a list of objects"))
            continue
        columns[name] = {k for row in rows for k in row}

    if driving not in set(model.sources):
        problems.append(Problem("unknown_source", where, f"driving_source {driving!r}"))

    if on_non_numeric(model) not in POLICIES:
        problems.append(Problem("unknown_policy", f"{where}:on_non_numeric",
                                on_non_numeric(model)))

    # Group ordering is DECLARED. Emitting groups in whatever order the
    # accumulator happened to fill is order-by-accident, and cross-sheet law 4
    # is the reason that is not acceptable even when it looks stable.
    if group_order(model) not in GROUP_ORDERS:
        problems.append(Problem("unknown_group_order", where, group_order(model)))

    keys = group_by(model)
    if not keys:
        problems.append(Problem("no_group_by", where,
                                "a model with no grouping keys would aggregate "
                                "everything into one unnamed bucket"))
    for key in keys:
        if driving in columns and key not in columns[driving]:
            problems.append(Problem("field_not_in_source", f"{where}:group_by",
                                    f"{driving}.{key}"))

    inputs = declared_inputs(model)
    for index, clause in enumerate(selections(model)):
        cwhere = f"{where}:select[{index}]"
        if clause.value and clause.value_from:
            problems.append(Problem("select_value_and_value_from", cwhere,
                                    "a clause is either fixed or bound to a run "
                                    "parameter, never both"))
        if not clause.field or not clause.op or (
                not clause.value and not clause.value_from):
            problems.append(Problem("select_missing_key", cwhere,
                                    "field, op, and one of value or value_from"))
        if clause.value_from and clause.value_from not in inputs:
            problems.append(Problem("unknown_run_parameter", cwhere,
                                    f"{clause.value_from!r} is not in inputs "
                                    f"{list(inputs)}"))
        if clause.op and clause.op not in SELECT_OPS:
            problems.append(Problem("unknown_select_op", cwhere, clause.op))
        if clause.field and driving in columns and clause.field not in columns[driving]:
            problems.append(Problem("field_not_in_source", cwhere,
                                    f"{driving}.{clause.field}"))

    aggregates = aggregates_of(model)
    if not aggregates:
        problems.append(Problem("no_aggregates", where, "a model with no aggregates emits nothing"))

    seen: set[str] = set()
    for i, agg in enumerate(aggregates):
        awhere = f"{where}:aggregates[{i}]"
        if not agg.target:
            problems.append(Problem("missing_key", awhere, "target"))
        elif agg.target in seen or agg.target in keys:
            problems.append(Problem("duplicate_target", awhere, agg.target))
        else:
            seen.add(agg.target)

        if agg.op not in OPS:
            problems.append(Problem("unknown_op", awhere, agg.op))
            continue

        # The PAIRING, not the two enums separately.
        takes_field = OP_TAKES_FIELD[agg.op]
        if takes_field and not agg.field:
            problems.append(Problem("op_field_mismatch", awhere,
                                    f"{agg.op!r} needs a field to aggregate"))
        if not takes_field and agg.field:
            problems.append(Problem("op_field_mismatch", awhere,
                                    f"{agg.op!r} takes no field, but {agg.field!r} "
                                    f"was given -- it implies a filter that is not "
                                    f"applied"))
        if agg.field and driving in columns and agg.field not in columns[driving]:
            problems.append(Problem("field_not_in_source", awhere,
                                    f"{driving}.{agg.field}"))

    return problems


TASK = register(TaskType(name="aggregation", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def validate(model: TaskModel, base: Path) -> Report:
    return validate_envelope(model, base)


def _self_test() -> int:
    import copy
    import json
    import tempfile

    import task_model

    base = Path(__file__).resolve().parent.parent
    failures: list[str] = []
    seen: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    raw = json.loads((base / "models" / "aggregation_v1.json").read_text(encoding="utf-8"))
    rep = validate(task_model.parse(raw), base)
    seen |= rep.codes()
    check(rep.valid, f"the shipped model must validate: {[str(p) for p in rep.problems]}")

    def probe(mutate) -> Report:
        bad = copy.deepcopy(raw)
        mutate(bad)
        r = validate(task_model.parse(bad), base)
        seen.update(r.codes())
        return r

    r = probe(lambda d: d.update(driving_source="nope"))
    check("unknown_source" in r.codes(), f"driving: {sorted(r.codes())}")
    r = probe(lambda d: d.update(on_non_numeric="shrug"))
    check("unknown_policy" in r.codes(), f"policy: {sorted(r.codes())}")
    r = probe(lambda d: d.update(group_order="whatever_order_it_filled"))
    check("unknown_group_order" in r.codes(), f"group_order: {sorted(r.codes())}")
    r = probe(lambda d: d.update(group_by=[]))
    check("no_group_by" in r.codes(), f"no group_by: {sorted(r.codes())}")
    r = probe(lambda d: d.update(group_by=["colour"]))
    check("field_not_in_source" in r.codes(), f"bad group key: {sorted(r.codes())}")
    r = probe(lambda d: d.update(aggregates=[]))
    check("no_aggregates" in r.codes(), f"no aggregates: {sorted(r.codes())}")
    r = probe(lambda d: d["aggregates"][0].update(op="median"))
    check("unknown_op" in r.codes(), f"op: {sorted(r.codes())}")
    r = probe(lambda d: d["aggregates"].append(dict(d["aggregates"][0])))
    check("duplicate_target" in r.codes(), f"duplicate: {sorted(r.codes())}")
    r = probe(lambda d: d["aggregates"][0].pop("target"))
    check("missing_key" in r.codes(), f"no target: {sorted(r.codes())}")

    # --- the PAIRING, both directions ---------------------------------------
    r = probe(lambda d: d["aggregates"][1].pop("field"))
    check("op_field_mismatch" in r.codes(), f"sum without field: {sorted(r.codes())}")
    r = probe(lambda d: d["aggregates"][0].update(field="quantity"))
    check("op_field_mismatch" in r.codes(), f"count WITH field: {sorted(r.codes())}")

    r = probe(lambda d: d["aggregates"][1].update(field="colour"))
    check("field_not_in_source" in r.codes(), f"bad sum field: {sorted(r.codes())}")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"sales": ["not an object"]}', encoding="utf-8")
        m = task_model.parse({**raw, "sources": {
            "sales": {"path": bad.name, "collection": "sales"}}})
        r2 = validate(m, Path(td))
        seen |= r2.codes()
        check("malformed_data_file" in r2.codes(), f"element shape: {sorted(r2.codes())}")

    # --- declared row selection --------------------------------------------
    def _with_select(clauses):
        m = task_model.parse({**raw, "select": clauses})
        return validate(m, base).codes()

    ok = _with_select([{"field": "region", "op": "equals", "value": "north"}])
    seen |= ok
    check(not (ok & {"unknown_select_op", "select_missing_key"}),
          f"a fully declared clause is valid: {sorted(ok)}")

    codes = _with_select([{"field": "region", "op": "matches", "value": "n.*"}])
    seen |= codes
    check("unknown_select_op" in codes,
          f"CANARY: an unimplemented select op must be refused, not ignored -- "
          f"silently dropping a clause would widen the data behind the "
          f"declaration: {sorted(codes)}")

    for partial in ({"field": "region", "op": "equals"},
                    {"op": "equals", "value": "north"},
                    {"field": "region", "value": "north"}):
        codes = _with_select([partial])
        seen |= codes
        check("select_missing_key" in codes,
              f"CANARY: a half-declared clause must be refused: {partial}")

    codes = _with_select([{"field": "nope", "op": "equals", "value": "x"}])
    seen |= codes
    check("field_not_in_source" in codes,
          f"a clause on a field that is not there must be caught: {sorted(codes)}")

    # selects() itself: every clause must hold, a missing field never matches
    from aggregation_model import Selection as _S
    clauses = (_S("date", "starts_with", "2026-06"), _S("region", "equals", "n"))
    check(selects({"date": "2026-06-04", "region": "n"}, clauses), "both hold")
    check(not selects({"date": "2026-07-04", "region": "n"}, clauses),
          "CANARY: one failing clause excludes the row")
    check(not selects({"region": "n"}, clauses),
          "CANARY: a missing field must never match")

    # --- run parameters: configuration vs run context -----------------------
    def _params(inputs, clauses):
        m = task_model.parse({**raw, "inputs": inputs, "select": clauses})
        return validate(m, base).codes()

    bound = [{"field": "region", "op": "equals", "value_from": "which_region"}]
    ok = _params(["which_region"], bound)
    seen |= ok
    check(not (ok & {"unknown_run_parameter", "select_missing_key",
                     "select_value_and_value_from"}),
          f"a clause bound to a DECLARED input is valid: {sorted(ok)}")

    codes = _params([], bound)
    seen |= codes
    check("unknown_run_parameter" in codes,
          f"CANARY: a clause may only bind to an input the model DECLARES: "
          f"{sorted(codes)}")

    codes = _params(["which_region"],
                    [{"field": "region", "op": "equals", "value": "north",
                      "value_from": "which_region"}])
    seen |= codes
    check("select_value_and_value_from" in codes,
          f"CANARY: a clause is fixed or bound, never both -- otherwise which "
          f"one applied would depend on the reader: {sorted(codes)}")

    # resolve(): no defaults, no clock
    from aggregation_model import (MissingRunParameter, Selection as _S,
                                   resolve as _resolve)
    clause = (_S("date", "in_month", "", "reporting_month"),)
    got = _resolve(clause, {"reporting_month": "2026-06"})
    check(got[0].value == "2026-06", f"a supplied parameter binds: {got}")
    try:
        _resolve(clause, {})
        check(False, "CANARY: a missing run parameter must REFUSE, never default")
    except MissingRunParameter:
        pass

    # in_month is prefix matching, NOT calendar arithmetic
    june = (_S("date", "in_month", "2026-06"),)
    check(selects({"date": "2026-06-30"}, june), "a June date is in June")
    check(not selects({"date": "2026-07-01"}, june), "a July date is not")
    check(not selects({"date": "2026-061"}, june),
          "CANARY: in_month must not match a longer month number by prefix")

    untested = sorted(set(BODY_PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised body problem codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(BODY_PROBLEM_CODES)} body "
          f"codes exercised / op-field PAIRING checked in both directions / group "
          f"ordering must be declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
