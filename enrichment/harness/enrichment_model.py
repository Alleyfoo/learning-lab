#!/usr/bin/env python3
"""The MODEL half of the enrichment task: declare and validate, never evaluate.

Knows what a well-formed enrichment model IS. Performs no lookup and computes
nothing — that is `execute_enrichment.py`. If a function here ever needs a
particular order row to answer its question, the separation has been lost.

See `enrichment/design/enrichment_model_v1.md`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Optional

MODEL_VERSIONS = (1,)

OPS = ("multiply",)
POLICIES = ("refuse_row", "refuse_run")
REFUSALS = ("MISSING_PRODUCT", "AMBIGUOUS_PRODUCT", "NON_NUMERIC_OPERAND")
TYPES = (None, "string", "number")

PROBLEM_CODES = (
    "unknown_model_version",
    "missing_key",
    "unknown_source",
    "unknown_op",
    "unknown_policy",
    "unknown_type",
    "duplicate_target",
    "no_outputs",
    "output_needs_field_or_compute",
    "output_has_both_field_and_compute",
    "missing_data_file",
    "malformed_data_file",
    "field_not_in_source",
)


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
class Output:
    target: str
    ref: Optional[Ref] = None
    compute: Optional[Compute] = None
    type: Optional[str] = None


@dataclass(frozen=True)
class Lookup:
    into: str
    match_left: str
    match_right: str
    on_missing: str
    on_ambiguous: str


@dataclass(frozen=True)
class Problem:
    code: str
    where: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.code}@{self.where}: {self.detail}" if self.detail \
            else f"{self.code}@{self.where}"


@dataclass
class Model:
    model_version: int
    model_id: str
    sources: dict            # name -> {"path": str, "collection": str}
    driving_source: str
    lookup: Lookup
    outputs: tuple[Output, ...]
    on_non_numeric: str


@dataclass
class Report:
    problems: list[Problem]

    @property
    def valid(self) -> bool:
        return not self.problems

    def codes(self) -> set[str]:
        return {p.code for p in self.problems}


def _ref(raw: dict) -> Ref:
    return Ref(source=str(raw.get("from", "")), field=str(raw.get("field", "")))


def model_from_json(raw: dict) -> Model:
    outputs = []
    for o in raw.get("outputs", []) or []:
        comp_raw = o.get("compute")
        compute = None
        if isinstance(comp_raw, dict):
            compute = Compute(op=str(comp_raw.get("op", "")),
                              left=_ref(comp_raw.get("left", {}) or {}),
                              right=_ref(comp_raw.get("right", {}) or {}))
        ref = None
        if "from" in o or "field" in o:
            ref = _ref(o)
        outputs.append(Output(target=str(o.get("target", "")), ref=ref,
                              compute=compute, type=o.get("type")))

    lk = raw.get("lookup", {}) or {}
    return Model(
        model_version=raw.get("model_version", 0),
        model_id=str(raw.get("model_id", "")),
        sources=raw.get("sources", {}) or {},
        driving_source=str(raw.get("driving_source", "")),
        lookup=Lookup(into=str(lk.get("into", "")),
                      match_left=str(lk.get("match_left", "")),
                      match_right=str(lk.get("match_right", "")),
                      on_missing=str(lk.get("on_missing", "")),
                      on_ambiguous=str(lk.get("on_ambiguous", ""))),
        outputs=tuple(outputs),
        on_non_numeric=str(raw.get("on_non_numeric", "")),
    )


def load_model(path: Path) -> Model:
    return model_from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def load_rows(model: Model, base: Path, source: str) -> list[dict]:
    spec = model.sources[source]
    data = json.loads((base / spec["path"]).resolve().read_text(encoding="utf-8"))
    return list(data.get(spec["collection"], []))


def validate(model: Model, base: Path) -> Report:
    """Is this a model the executor can be asked to run?

    Field names are checked against the ACTUAL fixture columns. A model naming a
    field no source has is broken at modelling time, not a surprise halfway
    through a run -- the same reason the recipe validator resolves referents
    before anything executes.
    """
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"

    if model.model_version not in MODEL_VERSIONS:
        problems.append(Problem("unknown_model_version", where, str(model.model_version)))
    if not model.model_id:
        problems.append(Problem("missing_key", "<model>", "model_id"))

    # --- sources and their data ---------------------------------------------
    columns: dict[str, set[str]] = {}
    for name, spec in (model.sources or {}).items():
        swhere = f"{where}:sources.{name}"
        if not isinstance(spec, dict) or "path" not in spec or "collection" not in spec:
            problems.append(Problem("missing_key", swhere, "path and collection"))
            continue
        path = (base / spec["path"]).resolve()
        if not path.exists():
            problems.append(Problem("missing_data_file", swhere, spec["path"]))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(Problem("malformed_data_file", swhere, str(exc)))
            continue
        rows = data.get(spec["collection"])
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            problems.append(Problem("malformed_data_file", swhere,
                                    f"expected a list of objects under "
                                    f"{spec['collection']!r}"))
            continue
        columns[name] = {k for row in rows for k in row}

    known = set(model.sources or {})
    if model.driving_source not in known:
        problems.append(Problem("unknown_source", where,
                                f"driving_source {model.driving_source!r}"))
    if model.lookup.into not in known:
        problems.append(Problem("unknown_source", where,
                                f"lookup.into {model.lookup.into!r}"))

    # --- lookup --------------------------------------------------------------
    for label, policy in (("on_missing", model.lookup.on_missing),
                          ("on_ambiguous", model.lookup.on_ambiguous),
                          ("on_non_numeric", model.on_non_numeric)):
        if policy not in POLICIES:
            problems.append(Problem("unknown_policy", f"{where}:{label}", policy))

    if not model.lookup.match_left or not model.lookup.match_right:
        problems.append(Problem("missing_key", f"{where}:lookup",
                                "match_left and match_right"))
    else:
        if (model.driving_source in columns
                and model.lookup.match_left not in columns[model.driving_source]):
            problems.append(Problem("field_not_in_source", f"{where}:lookup.match_left",
                                    model.lookup.match_left))
        if (model.lookup.into in columns
                and model.lookup.match_right not in columns[model.lookup.into]):
            problems.append(Problem("field_not_in_source", f"{where}:lookup.match_right",
                                    model.lookup.match_right))

    # --- outputs -------------------------------------------------------------
    if not model.outputs:
        problems.append(Problem("no_outputs", where, "a model with no outputs emits nothing"))

    seen: set[str] = set()
    for i, out in enumerate(model.outputs):
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
            problems.append(Problem("output_has_both_field_and_compute", owhere,
                                    out.target))

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

    return Report(problems=problems)


def _self_test() -> int:
    import copy
    import sys
    import tempfile

    base = Path(__file__).resolve().parent.parent
    failures: list[str] = []
    seen: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    raw = json.loads((base / "models" / "enrichment_v1.json").read_text(encoding="utf-8"))
    rep = validate(model_from_json(raw), base)
    seen |= rep.codes()
    check(rep.valid, f"the shipped model must validate: {[str(p) for p in rep.problems]}")

    def probe(mutate) -> Report:
        bad = copy.deepcopy(raw)
        mutate(bad)
        r = validate(model_from_json(bad), base)
        seen.update(r.codes())
        return r

    r = probe(lambda d: d.update(model_version=99))
    check("unknown_model_version" in r.codes(), f"version: {sorted(r.codes())}")
    r = probe(lambda d: d.pop("model_id"))
    check("missing_key" in r.codes(), f"model_id: {sorted(r.codes())}")
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
    r = probe(lambda d: d["sources"]["orders"].update(path="fixtures/nope.json"))
    check("missing_data_file" in r.codes(), f"missing file: {sorted(r.codes())}")

    # A field no source actually has -- caught at MODELLING time.
    r = probe(lambda d: d["outputs"][1].update(field="colour"))
    check("field_not_in_source" in r.codes(), f"unknown field: {sorted(r.codes())}")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"products": "not a list"}', encoding="utf-8")
        m = model_from_json({**raw, "sources": {
            **raw["sources"],
            "products": {"path": bad.name, "collection": "products"}}})
        r2 = validate(m, Path(td))
        seen |= r2.codes()
        check("malformed_data_file" in r2.codes(), f"malformed: {sorted(r2.codes())}")

    untested = sorted(set(PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised problem codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(PROBLEM_CODES)} problem "
          f"codes exercised / field names checked against ACTUAL fixture columns)")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
