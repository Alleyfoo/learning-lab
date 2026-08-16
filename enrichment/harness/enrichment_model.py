#!/usr/bin/env python3
"""The enrichment task's BODY: declare and validate its own lookup and outputs.

Identity and sources are the shared envelope's job (`taskmodel/task_model.py`).
What is left here is what only this task has: a join, an output list, and the
policies governing missing/ambiguous/non-numeric.

Performs no lookup and computes nothing — that is `execute_enrichment.py`. If a
function here ever needs a particular order row, the separation has been lost.

See `enrichment/design/enrichment_model_v1.md`.
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

OPS = ("multiply",)
# Rounding is NAMED, never inherited from whatever the language defaults to.
# `half_up` and `half_even` disagree on exact halves, which is the point of
# making the model say which one it means.
ROUNDING = {"half_up": "ROUND_HALF_UP", "half_even": "ROUND_HALF_EVEN",
            "down": "ROUND_DOWN", "up": "ROUND_UP", "floor": "ROUND_FLOOR",
            "ceiling": "ROUND_CEILING"}
MAX_DECIMAL_PLACES = 12
POLICIES = ("refuse_row", "refuse_run")
REFUSALS = ("MISSING_PRODUCT", "AMBIGUOUS_PRODUCT", "NON_NUMERIC_OPERAND")
TYPES = (None, "string", "number")

# This task's OWN codes. The four envelope codes live on the floor now.
# `missing_key` and `malformed_data_file` reappear because the BODY also uses
# them -- same code name, different `where`: the envelope owns identity and "a
# list arrived", the body owns its required keys and element shape.
BODY_PROBLEM_CODES = (
    "missing_key",
    "unknown_source",
    "unknown_op",
    "unknown_policy",
    "unknown_type",
    "duplicate_target",
    "no_outputs",
    "output_needs_field_or_compute",
    "output_has_both_field_and_compute",
    "malformed_data_file",
    "field_not_in_source",
    "representation_on_passthrough",
    "unknown_rounding",
    "invalid_decimal_places",
    "representation_missing_key",
)


# --- typed views over the body ----------------------------------------------
# The body is a plain dict on the floor. These give the executor the same shape
# it had before the extraction, without the floor knowing any of it.

@dataclass(frozen=True)
class Ref:
    source: str
    field: str


@dataclass(frozen=True)
class Compute:
    op: str
    left: Ref
    right: Ref


@dataclass(frozen=True)
class Representation:
    """How a COMPUTED value is written out. Declared, or it does not happen.

    A computed value has no source text -- it is whatever the arithmetic
    produced -- so the model may say how to present it. A passthrough copies
    somebody else's data and may NOT, which is why `representation` on a
    passthrough is a validation error rather than a silent no-op. That is
    PRO-2 instance 9 kept closed: nothing reformats a value on the way past
    because it looked nicer.
    """
    decimal_places: int
    rounding: str


@dataclass(frozen=True)
class Output:
    target: str
    ref: Optional[Ref] = None
    compute: Optional[Compute] = None
    type: Optional[str] = None
    representation: Optional[Representation] = None


@dataclass(frozen=True)
class Lookup:
    into: str
    match_left: str
    match_right: str
    on_missing: str
    on_ambiguous: str


def _ref(raw: dict) -> Ref:
    return Ref(source=str(raw.get("from", "")), field=str(raw.get("field", "")))


def outputs_of(model: TaskModel) -> tuple[Output, ...]:
    out = []
    for o in model.body.get("outputs") or []:
        comp_raw = o.get("compute")
        compute = None
        if isinstance(comp_raw, dict):
            compute = Compute(op=str(comp_raw.get("op", "")),
                              left=_ref(comp_raw.get("left") or {}),
                              right=_ref(comp_raw.get("right") or {}))
        ref = _ref(o) if ("from" in o or "field" in o) else None
        rep_raw = o.get("representation")
        representation = None
        if isinstance(rep_raw, dict):
            representation = Representation(
                decimal_places=rep_raw.get("decimal_places"),
                rounding=str(rep_raw.get("rounding", "")))
        out.append(Output(target=str(o.get("target", "")), ref=ref,
                          compute=compute, type=o.get("type"),
                          representation=representation))
    return tuple(out)


def lookup_of(model: TaskModel) -> Lookup:
    lk = model.body.get("lookup") or {}
    return Lookup(into=str(lk.get("into", "")),
                  match_left=str(lk.get("match_left", "")),
                  match_right=str(lk.get("match_right", "")),
                  on_missing=str(lk.get("on_missing", "")),
                  on_ambiguous=str(lk.get("on_ambiguous", "")))


def driving_source(model: TaskModel) -> str:
    return str(model.body.get("driving_source", ""))


def on_non_numeric(model: TaskModel) -> str:
    return str(model.body.get("on_non_numeric", ""))


def load_rows(model: TaskModel, base: Path, source: str) -> list[dict]:
    return load_collection(model, base, source)


def validate_body(model: TaskModel, base: Path) -> list[Problem]:
    """Field names are checked against the ACTUAL fixture columns.

    A model naming a field no source has is broken at modelling time, not a
    surprise halfway through a run -- the same reason the recipe validator
    resolves referents before anything executes.
    """
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"
    lookup = lookup_of(model)
    outputs = outputs_of(model)

    # Element shape. The envelope proved a LIST arrived; that these are OBJECTS
    # is this task's knowledge and nobody else's.
    columns: dict[str, set[str]] = {}
    for name in model.sources:
        try:
            rows = load_collection(model, base, name)
        except (OSError, ValueError):
            continue                      # already reported by the envelope
        if not all(isinstance(r, dict) for r in rows):
            problems.append(Problem("malformed_data_file", f"{where}:sources.{name}",
                                    "expected a list of objects"))
            continue
        columns[name] = {k for row in rows for k in row}

    known = set(model.sources)
    if driving_source(model) not in known:
        problems.append(Problem("unknown_source", where,
                                f"driving_source {driving_source(model)!r}"))
    if lookup.into not in known:
        problems.append(Problem("unknown_source", where,
                                f"lookup.into {lookup.into!r}"))

    for label, policy in (("on_missing", lookup.on_missing),
                          ("on_ambiguous", lookup.on_ambiguous),
                          ("on_non_numeric", on_non_numeric(model))):
        if policy not in POLICIES:
            problems.append(Problem("unknown_policy", f"{where}:{label}", policy))

    if not lookup.match_left or not lookup.match_right:
        problems.append(Problem("missing_key", f"{where}:lookup",
                                "match_left and match_right"))
    else:
        if (driving_source(model) in columns
                and lookup.match_left not in columns[driving_source(model)]):
            problems.append(Problem("field_not_in_source", f"{where}:lookup.match_left",
                                    lookup.match_left))
        if lookup.into in columns and lookup.match_right not in columns[lookup.into]:
            problems.append(Problem("field_not_in_source", f"{where}:lookup.match_right",
                                    lookup.match_right))

    if not outputs:
        problems.append(Problem("no_outputs", where, "a model with no outputs emits nothing"))

    seen: set[str] = set()
    for i, out in enumerate(outputs):
        owhere = f"{where}:outputs[{i}]"
        if not out.target:
            problems.append(Problem("missing_key", owhere, "target"))
        elif out.target in seen:
            problems.append(Problem("duplicate_target", owhere, out.target))
        else:
            seen.add(out.target)

        if out.type not in TYPES:
            problems.append(Problem("unknown_type", owhere, str(out.type)))

        if out.ref is None and out.compute is None:
            problems.append(Problem("output_needs_field_or_compute", owhere, out.target))
        if out.ref is not None and out.compute is not None:
            problems.append(Problem("output_has_both_field_and_compute", owhere, out.target))

        for ref in filter(None, (out.ref,
                                 out.compute.left if out.compute else None,
                                 out.compute.right if out.compute else None)):
            if ref.source not in known:
                problems.append(Problem("unknown_source", owhere, ref.source))
            elif ref.source in columns and ref.field not in columns[ref.source]:
                problems.append(Problem("field_not_in_source", owhere,
                                        f"{ref.source}.{ref.field}"))

        if out.compute is not None and out.compute.op not in OPS:
            problems.append(Problem("unknown_op", owhere, out.compute.op))

        rep = out.representation
        if rep is not None:
            if out.compute is None:
                # A passthrough emits somebody else's text. Declaring how to
                # round it would be an undeclared rewrite of their data.
                problems.append(Problem("representation_on_passthrough",
                                        owhere, out.target))
            if rep.decimal_places is None or rep.rounding == "":
                problems.append(Problem("representation_missing_key", owhere,
                                        "decimal_places and rounding are both "
                                        "required"))
            if rep.rounding and rep.rounding not in ROUNDING:
                problems.append(Problem("unknown_rounding", owhere, rep.rounding))
            places = rep.decimal_places
            if places is not None and (not isinstance(places, int)
                                       or isinstance(places, bool)
                                       or places < 0
                                       or places > MAX_DECIMAL_PLACES):
                problems.append(Problem("invalid_decimal_places", owhere,
                                        repr(places)))

    return problems


TASK = register(TaskType(name="enrichment", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def validate(model: TaskModel, base: Path) -> Report:
    """Envelope + this task's body, in one call for the harness's convenience."""
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

    raw = json.loads((base / "models" / "enrichment_v1.json").read_text(encoding="utf-8"))
    rep = validate(task_model.parse(raw), base)
    seen |= rep.codes()
    check(rep.valid, f"the shipped model must validate: {[str(p) for p in rep.problems]}")

    def probe(mutate) -> Report:
        bad = copy.deepcopy(raw)
        mutate(bad)
        r = validate(task_model.parse(bad), base)
        seen.update(r.codes())
        return r

    # --- envelope codes, now owned by the floor ------------------------------
    r = probe(lambda d: d.update(model_version=99))
    check("unknown_model_version" in r.codes(), f"version: {sorted(r.codes())}")
    r = probe(lambda d: d["sources"]["orders"].update(path="fixtures/nope.json"))
    check("missing_data_file" in r.codes(), f"missing file: {sorted(r.codes())}")
    r = probe(lambda d: d.update(task="not_a_task"))
    check("unknown_task" in r.codes(), f"unknown task: {sorted(r.codes())}")

    # --- this task's own codes ----------------------------------------------
    r = probe(lambda d: d.update(driving_source="nope"))
    check("unknown_source" in r.codes(), f"driving_source: {sorted(r.codes())}")
    r = probe(lambda d: d["lookup"].update(on_missing="emit_null"))
    check("unknown_policy" in r.codes(), f"policy: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"][4]["compute"].update(op="exponentiate"))
    check("unknown_op" in r.codes(), f"op: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"][0].update(type="colour"))
    check("unknown_type" in r.codes(), f"type: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"].append(dict(d["outputs"][0])))
    check("duplicate_target" in r.codes(), f"duplicate: {sorted(r.codes())}")
    r = probe(lambda d: d.update(outputs=[]))
    check("no_outputs" in r.codes(), f"no outputs: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"].append({"target": "orphan"}))
    check("output_needs_field_or_compute" in r.codes(), f"orphan: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"][4].update(**{"from": "orders", "field": "quantity"}))
    check("output_has_both_field_and_compute" in r.codes(), f"both: {sorted(r.codes())}")
    r = probe(lambda d: d["outputs"][1].update(field="colour"))
    check("field_not_in_source" in r.codes(), f"unknown field: {sorted(r.codes())}")
    r = probe(lambda d: d["lookup"].update(match_left=""))
    check("missing_key" in r.codes(), f"lookup keys: {sorted(r.codes())}")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"products": ["not an object"]}', encoding="utf-8")
        m = task_model.parse({**raw, "sources": {
            **raw["sources"],
            "products": {"path": bad.name, "collection": "products"}}})
        r2 = validate(m, Path(td))
        seen |= r2.codes()
        check("malformed_data_file" in r2.codes(),
              f"non-object elements must be caught by the BODY: {sorted(r2.codes())}")

    # --- declared representation: only on a computed value, fully named ----
    def _with_outputs(outputs):
        m = task_model.parse({**raw, "outputs": outputs})
        r = validate(m, base)
        return r.codes()

    computed = {"target": "line_total", "compute": {
        "op": "multiply",
        "left": {"from": "orders", "field": "quantity"},
        "right": {"from": "products", "field": "unit_price"}}}

    good = _with_outputs([{**computed,
                           "representation": {"decimal_places": 2,
                                              "rounding": "half_up"}}])
    seen |= good
    check(not (good & {"representation_on_passthrough", "unknown_rounding",
                       "invalid_decimal_places", "representation_missing_key"}),
          f"a fully declared representation on a COMPUTED output is valid: {good}")

    # A passthrough copies somebody else's text and may not be reformatted.
    codes = _with_outputs([{"target": "unit_price", "from": "products",
                            "field": "unit_price",
                            "representation": {"decimal_places": 2,
                                               "rounding": "half_up"}}])
    seen |= codes
    check("representation_on_passthrough" in codes,
          f"CANARY: representation on a passthrough must be refused -- that is "
          f"rewriting someone else's data: {sorted(codes)}")

    codes = _with_outputs([{**computed, "representation": {
        "decimal_places": 2, "rounding": "bankers"}}])
    seen |= codes
    check("unknown_rounding" in codes,
          f"CANARY: an unnamed rounding mode must be refused, never defaulted: "
          f"{sorted(codes)}")

    for places in (-1, 99, 2.5, True, "2"):
        codes = _with_outputs([{**computed, "representation": {
            "decimal_places": places, "rounding": "half_up"}}])
        seen |= codes
        check("invalid_decimal_places" in codes,
              f"CANARY: decimal_places={places!r} must be refused: "
              f"{sorted(codes)}")

    codes = _with_outputs([{**computed,
                            "representation": {"decimal_places": 2}}])
    seen |= codes
    check("representation_missing_key" in codes,
          f"CANARY: a half-declared representation must be refused: "
          f"{sorted(codes)}")

    untested = sorted(set(BODY_PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised body problem codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(BODY_PROBLEM_CODES)} body "
          f"codes exercised / envelope codes delegated to taskmodel / field names "
          f"checked against ACTUAL fixture columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
