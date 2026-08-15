#!/usr/bin/env python3
"""The reservation task's BODY: declare and validate its own rules, never evaluate.

Identity and sources are the shared envelope's job (`taskmodel/task_model.py`).
What is left here is what only this task has: an ordered rule list whose order is
precedence, and an on-accept effect.

Nothing here loads a requested date. If a function in this file ever needs one,
the separation has been lost.

See `reservation/design/reservation_model_v1.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

from task_model import (  # noqa: E402
    Problem, Report, TaskModel, TaskType, load_collection, load_model, register,
    validate as validate_envelope,
)

# Closed vocabularies. A model may not invent a rule or a refusal reason.
RULES = ("date_well_formed", "not_holiday", "not_reserved")
REFUSALS = ("INVALID_DATE", "HOLIDAY", "ALREADY_RESERVED")
ON_ACCEPT = ("append_to_reservations",)

# `not_holiday` and `not_reserved` compare a date against a set. Neither has a
# defined answer for a string that is not a date, so well-formedness is not one
# rule among three -- it is the precondition of the other two.
MUST_BE_FIRST = "date_well_formed"

# This task's OWN codes. The four envelope codes (unknown_model_version,
# missing_key, missing_data_file, malformed_data_file) live on the floor now and
# are not repeated here.
BODY_PROBLEM_CODES = (
    "field_not_in_items",
    "field_required_for_object_items",
    "unknown_rule",
    "unknown_refusal",
    "unknown_on_accept",
    "duplicate_rule",
    "wellformedness_not_first",
    "no_rules",
    "malformed_data_file",     # element shape: the envelope proves only a LIST
    "missing_key",             # a rule without a declared refusal
)


def rules_of(model: TaskModel) -> list[dict]:
    return list(model.body.get("rules") or [])


def rule_names(model: TaskModel) -> tuple[str, ...]:
    return tuple(str(r.get("rule", "")) for r in rules_of(model))


def refusal_for(model: TaskModel, rule: str) -> Optional[str]:
    for r in rules_of(model):
        if r.get("rule") == rule:
            return r.get("refusal")
    return None


def on_accept(model: TaskModel) -> str:
    return str(model.body.get("on_accept", ""))


def source_field(model: TaskModel, source: str) -> Optional[str]:
    """Which item field carries the date, when items are OBJECTS.

    Absent means the collection holds plain strings, which is what every model
    written before 2026-08-15 assumes and what `calendar_job` still uses.

    Added because Experiment S described real sources whose items are objects
    with TWO date fields. A node over such data cannot avoid saying which field
    it means -- and that binding is exactly where an unsupported upstream
    inference would land, which is what Experiment T measures.
    """
    spec = (model.body.get("source_fields") or {}).get(source)
    return str(spec) if spec else None


def validate_body(model: TaskModel, base: Path) -> list[Problem]:
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"
    rules = rules_of(model)

    if not rules:
        problems.append(Problem("no_rules", where,
                                "a model with no rules would accept everything"))

    seen: set[str] = set()
    for i, rule in enumerate(rules):
        rwhere = f"{where}:rules[{i}]"
        name = str(rule.get("rule", ""))
        refusal = str(rule.get("refusal", ""))
        if name not in RULES:
            problems.append(Problem("unknown_rule", rwhere, name))
        elif name in seen:
            problems.append(Problem("duplicate_rule", rwhere, name))
        else:
            seen.add(name)
        if not refusal:
            problems.append(Problem("missing_key", rwhere,
                                    "a rule needs a declared refusal reason"))
        elif refusal not in REFUSALS:
            problems.append(Problem("unknown_refusal", rwhere, refusal))

    # Enforced rather than silently reordered: reordering a model to make it
    # runnable would mean the executed order is not the declared order, which is
    # the whole property the declared list exists to give.
    names = rule_names(model)
    if MUST_BE_FIRST in names and names[0] != MUST_BE_FIRST:
        problems.append(Problem(
            "wellformedness_not_first", where,
            f"{MUST_BE_FIRST!r} is at position {names.index(MUST_BE_FIRST)}; the "
            f"rules before it have no defined answer for a string that is not a "
            f"date"))

    if on_accept(model) not in ON_ACCEPT:
        problems.append(Problem("unknown_on_accept", where, on_accept(model)))

    # Element shape. The envelope proved a LIST arrived; what the elements ARE
    # is this task's knowledge and nobody else's. Two shapes are accepted:
    # plain date strings, or objects plus a declared field naming which value
    # to read.
    for name in ("holidays", "reservations"):
        if name not in model.sources:
            problems.append(Problem("missing_key", where, f"sources.{name}"))
            continue
        try:
            values = load_collection(model, base, name)
        except (OSError, ValueError):
            continue                      # already reported by the envelope
        field = source_field(model, name)
        if all(isinstance(v, str) for v in values):
            if field:
                problems.append(Problem(
                    "field_not_in_items", f"{where}:{name}",
                    f"source_fields declares {field!r} but the items are plain "
                    f"strings, so there is no field to read"))
            continue
        if all(isinstance(v, dict) for v in values):
            if not field:
                problems.append(Problem(
                    "field_required_for_object_items", f"{where}:{name}",
                    "items are objects, so the model must declare WHICH field "
                    "carries the date; guessing one would make an unstated "
                    "choice on the job's behalf"))
            elif not all(field in v for v in values):
                problems.append(Problem("field_not_in_items", f"{where}:{name}",
                                        f"{field!r} is missing from some items"))
            continue
        problems.append(Problem("malformed_data_file", f"{where}:{name}",
                                "expected a list of date strings, or a list of "
                                "objects with a declared source field"))

    return problems


TASK = register(TaskType(name="reservation", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def validate(model: TaskModel, base: Path) -> Report:
    """Envelope + this task's body, in one call for the harness's convenience."""
    return validate_envelope(model, base)


def load_dates(model: TaskModel, base: Path, source: str) -> tuple[str, ...]:
    """The dates in a source, whether its items are strings or objects.

    Projection happens HERE, once, so the executor never has to know which shape
    it was handed -- and so the declared field is read rather than assumed.
    """
    values = load_collection(model, base, source)
    field = source_field(model, source)
    if field is None:
        return tuple(str(v) for v in values)
    return tuple(str(v[field]) for v in values if isinstance(v, dict) and field in v)


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

    raw = json.loads((base / "models" / "reservation_v1.json").read_text(encoding="utf-8"))
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
    r = probe(lambda d: d.pop("model_id"))
    check("missing_key" in r.codes(), f"model_id: {sorted(r.codes())}")
    r = probe(lambda d: d["sources"]["holidays"].update(path="fixtures/nope.json"))
    check("missing_data_file" in r.codes(), f"missing file: {sorted(r.codes())}")
    r = probe(lambda d: d.update(task="not_a_task"))
    check("unknown_task" in r.codes(), f"unknown task: {sorted(r.codes())}")

    # --- this task's own codes ----------------------------------------------
    r = probe(lambda d: d["rules"].append({"rule": "not_a_rule", "refusal": "HOLIDAY"}))
    check("unknown_rule" in r.codes(), f"unknown rule: {sorted(r.codes())}")
    r = probe(lambda d: d["rules"].__setitem__(
        1, {"rule": "not_holiday", "refusal": "NOT_A_REASON"}))
    check("unknown_refusal" in r.codes(), f"unknown refusal: {sorted(r.codes())}")
    r = probe(lambda d: d["rules"].append({"rule": "not_holiday", "refusal": "HOLIDAY"}))
    check("duplicate_rule" in r.codes(), f"duplicate: {sorted(r.codes())}")
    r = probe(lambda d: d.update(rules=[d["rules"][1], d["rules"][0], d["rules"][2]]))
    check("wellformedness_not_first" in r.codes(),
          f"well-formedness must be required first: {sorted(r.codes())}")
    r = probe(lambda d: d.update(rules=[]))
    check("no_rules" in r.codes(), f"empty rules: {sorted(r.codes())}")
    r = probe(lambda d: d.update(on_accept="delete_everything"))
    check("unknown_on_accept" in r.codes(), f"on_accept: {sorted(r.codes())}")
    r = probe(lambda d: d["rules"].__setitem__(1, {"rule": "not_holiday"}))
    check("missing_key" in r.codes(), f"rule without refusal: {sorted(r.codes())}")

    # --- object items and the declared source field --------------------------
    with tempfile.TemporaryDirectory() as td:
        objects = Path(td) / "objects.json"
        objects.write_text(json.dumps({"reservations": [
            {"date": "2026-03-10", "created": "2026-01-15"},
            {"date": "2026-03-11", "created": "2026-01-15"}]}), encoding="utf-8")
        holidays = Path(td) / "hol.json"
        holidays.write_text(json.dumps({"holidays": ["2026-01-01"]}), encoding="utf-8")

        def with_objects(extra=None) -> dict:
            d = copy.deepcopy(raw)
            d["sources"] = {
                "holidays": {"path": holidays.name, "collection": "holidays"},
                "reservations": {"path": objects.name, "collection": "reservations"}}
            if extra:
                d.update(extra)
            return d

        # Object items with NO declared field: the model must not be allowed to
        # let the executor guess which date matters.
        r = validate(task_model.parse(with_objects()), Path(td))
        seen |= r.codes()
        check("field_required_for_object_items" in r.codes(),
              f"object items with no declared field must be refused: {sorted(r.codes())}")

        # A declared field that is not in the items.
        r = validate(task_model.parse(
            with_objects({"source_fields": {"reservations": "booking_date"}})), Path(td))
        seen |= r.codes()
        check("field_not_in_items" in r.codes(),
              f"a field absent from the items must be refused: {sorted(r.codes())}")

        # A field declared over items that are plain STRINGS.
        r = validate(task_model.parse(
            {**copy.deepcopy(raw), "source_fields": {"holidays": "date"}}), base)
        seen |= r.codes()
        check("field_not_in_items" in r.codes(),
              f"a field declared over string items must be refused: {sorted(r.codes())}")

        # The working case, and the projection it produces.
        good = task_model.parse(
            with_objects({"source_fields": {"reservations": "date"}}))
        r = validate(good, Path(td))
        check(r.valid, f"objects + a declared field must validate: "
                       f"{[str(x) for x in r.problems]}")
        check(load_dates(good, Path(td), "reservations") == ("2026-03-10", "2026-03-11"),
              "…and the DECLARED field is what gets read")
        other = task_model.parse(
            with_objects({"source_fields": {"reservations": "created"}}))
        check(load_dates(other, Path(td), "reservations") == ("2026-01-15", "2026-01-15"),
              "…and declaring the OTHER field reads the other field -- the binding "
              "is the model's, not the executor's")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"holidays": [1, 2, 3]}', encoding="utf-8")
        m = task_model.parse({**raw, "sources": {
            **raw["sources"],
            "holidays": {"path": bad.name, "collection": "holidays"}}})
        r2 = validate(m, Path(td))
        seen |= r2.codes()
        check("malformed_data_file" in r2.codes(),
              f"non-string elements must be caught by the BODY: {sorted(r2.codes())}")

    untested = sorted(set(BODY_PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised body problem codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(BODY_PROBLEM_CODES)} body "
          f"codes exercised / envelope codes delegated to taskmodel / "
          f"well-formedness enforced first rather than reordered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
