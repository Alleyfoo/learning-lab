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

    # Element shape. The envelope proved a LIST arrived; that these are date
    # STRINGS is this task's knowledge and nobody else's.
    for name in ("holidays", "reservations"):
        if name not in model.sources:
            problems.append(Problem("missing_key", where, f"sources.{name}"))
            continue
        try:
            values = load_collection(model, base, name)
        except (OSError, ValueError):
            continue                      # already reported by the envelope
        if not all(isinstance(v, str) for v in values):
            problems.append(Problem("malformed_data_file", f"{where}:{name}",
                                    "expected a list of date strings"))

    return problems


TASK = register(TaskType(name="reservation", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def validate(model: TaskModel, base: Path) -> Report:
    """Envelope + this task's body, in one call for the harness's convenience."""
    return validate_envelope(model, base)


def load_dates(model: TaskModel, base: Path, source: str) -> tuple[str, ...]:
    return tuple(load_collection(model, base, source))


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
