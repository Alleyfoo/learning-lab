#!/usr/bin/env python3
"""The MODEL half of the reservation task: declare and validate, never evaluate.

This module knows what a well-formed reservation model IS. It does not decide
whether any particular date is acceptable — that is `execute_reservation.py`, and
keeping the two apart is the thing this small task exists to test.

Nothing here loads a requested date, and nothing here reads a calendar to answer
a question. If a function in this file ever needs to know today's date or a
specific request, the separation has been lost.

See `reservation/design/reservation_model_v1.md`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

MODEL_VERSIONS = (1,)

# Closed vocabularies. A model may not invent a rule or a refusal reason, for the
# same reason the recipe format has a closed problem-code list: an unknown token
# is a modelling error, not a thing to interpret generously.
RULES = ("date_well_formed", "not_holiday", "not_reserved")
REFUSALS = ("INVALID_DATE", "HOLIDAY", "ALREADY_RESERVED")
ON_ACCEPT = ("append_to_reservations",)

# `not_holiday` and `not_reserved` compare a date against a set. Neither has a
# defined answer for a string that is not a date, so well-formedness is not one
# rule among three -- it is the precondition of the other two.
MUST_BE_FIRST = "date_well_formed"

PROBLEM_CODES = (
    "unknown_model_version",
    "missing_key",
    "unknown_rule",
    "unknown_refusal",
    "unknown_on_accept",
    "duplicate_rule",
    "wellformedness_not_first",
    "no_rules",
    "missing_data_file",
    "malformed_data_file",
)


@dataclass(frozen=True)
class Rule:
    rule: str
    refusal: str


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
    holidays_path: str
    reservations_path: str
    rules: tuple[Rule, ...]
    on_accept: str

    def rule_names(self) -> tuple[str, ...]:
        return tuple(r.rule for r in self.rules)

    def refusal_for(self, rule: str) -> Optional[str]:
        for r in self.rules:
            if r.rule == rule:
                return r.refusal
        return None


@dataclass
class Report:
    problems: list[Problem]

    @property
    def valid(self) -> bool:
        return not self.problems

    def codes(self) -> set[str]:
        return {p.code for p in self.problems}


def model_from_json(raw: dict) -> Model:
    """Structural parse only. Judgement about the result belongs to validate()."""
    rules = tuple(Rule(rule=str(r.get("rule", "")), refusal=str(r.get("refusal", "")))
                  for r in raw.get("rules", []) or [])
    return Model(
        model_version=raw.get("model_version", 0),
        model_id=str(raw.get("model_id", "")),
        holidays_path=str(raw.get("holidays", "")),
        reservations_path=str(raw.get("reservations", "")),
        rules=rules,
        on_accept=str(raw.get("on_accept", "")),
    )


def load_model(path: Path) -> Model:
    return model_from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def validate(model: Model, base: Path) -> Report:
    """Is this a model the executor can be asked to run?

    `base` is the directory the model's data paths are relative to. Data files are
    checked for EXISTENCE and SHAPE here, because a model naming a file that is
    not there is a broken model -- not an execution-time surprise.
    """
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"

    if model.model_version not in MODEL_VERSIONS:
        problems.append(Problem("unknown_model_version", where,
                                str(model.model_version)))
    if not model.model_id:
        problems.append(Problem("missing_key", "<model>", "model_id"))

    # --- rules ---------------------------------------------------------------
    if not model.rules:
        problems.append(Problem("no_rules", where,
                                "a model with no rules would accept everything"))
    seen: set[str] = set()
    for i, rule in enumerate(model.rules):
        rwhere = f"{where}:rules[{i}]"
        if rule.rule not in RULES:
            problems.append(Problem("unknown_rule", rwhere, rule.rule))
        elif rule.rule in seen:
            problems.append(Problem("duplicate_rule", rwhere, rule.rule))
        else:
            seen.add(rule.rule)
        if not rule.refusal:
            problems.append(Problem("missing_key", rwhere,
                                    "a rule needs a declared refusal reason"))
        elif rule.refusal not in REFUSALS:
            problems.append(Problem("unknown_refusal", rwhere, rule.refusal))

    # Enforced rather than silently reordered: reordering a model to make it
    # runnable would mean the executed order is not the declared order, which is
    # the whole property the declared list exists to give.
    names = model.rule_names()
    if MUST_BE_FIRST in names and names[0] != MUST_BE_FIRST:
        problems.append(Problem(
            "wellformedness_not_first", where,
            f"{MUST_BE_FIRST!r} is at position {names.index(MUST_BE_FIRST)}; the "
            f"rules before it have no defined answer for a string that is not a "
            f"date"))

    if model.on_accept not in ON_ACCEPT:
        problems.append(Problem("unknown_on_accept", where, model.on_accept))

    # --- declared data -------------------------------------------------------
    for label, rel, key in (("holidays", model.holidays_path, "holidays"),
                            ("reservations", model.reservations_path, "reservations")):
        if not rel:
            problems.append(Problem("missing_key", where, label))
            continue
        path = (base / rel).resolve()
        if not path.exists():
            problems.append(Problem("missing_data_file", f"{where}:{label}", str(rel)))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(Problem("malformed_data_file", f"{where}:{label}", str(exc)))
            continue
        values = data.get(key)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            problems.append(Problem(
                "malformed_data_file", f"{where}:{label}",
                f"expected a list of date strings under {key!r}"))

    return Report(problems=problems)


def load_dates(base: Path, rel: str, key: str) -> tuple[str, ...]:
    """The declared date list, as written. No parsing, no normalisation.

    Whether a stored string is a well-formed date is a question the EXECUTOR asks
    through a declared rule. Silently dropping unparseable entries here would
    make the data quietly disagree with what the file says.
    """
    data = json.loads((base / rel).resolve().read_text(encoding="utf-8"))
    return tuple(data.get(key, []))


def _self_test() -> int:
    import copy
    import tempfile

    here = Path(__file__).resolve().parent
    base = here.parent
    failures: list[str] = []
    seen_codes: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    raw = json.loads((base / "models" / "reservation_v1.json").read_text(encoding="utf-8"))

    # --- control: the shipped model is valid ---------------------------------
    rep = validate(model_from_json(raw), base)
    seen_codes |= rep.codes()
    check(rep.valid, f"the shipped model must validate: {[str(p) for p in rep.problems]}")

    def probe(mutate) -> Report:
        bad = copy.deepcopy(raw)
        mutate(bad)
        r = validate(model_from_json(bad), base)
        seen_codes.update(r.codes())
        return r

    # --- each declared problem code, exercised -------------------------------
    r = probe(lambda d: d.update(model_version=99))
    check("unknown_model_version" in r.codes(), f"version: {sorted(r.codes())}")

    r = probe(lambda d: d.pop("model_id"))
    check("missing_key" in r.codes(), f"missing model_id: {sorted(r.codes())}")

    r = probe(lambda d: d["rules"].append({"rule": "not_a_rule", "refusal": "HOLIDAY"}))
    check("unknown_rule" in r.codes(), f"unknown rule: {sorted(r.codes())}")

    r = probe(lambda d: d["rules"].__setitem__(
        1, {"rule": "not_holiday", "refusal": "NOT_A_REASON"}))
    check("unknown_refusal" in r.codes(), f"unknown refusal: {sorted(r.codes())}")

    r = probe(lambda d: d["rules"].append({"rule": "not_holiday", "refusal": "HOLIDAY"}))
    check("duplicate_rule" in r.codes(), f"duplicate rule: {sorted(r.codes())}")

    # The load-bearing structural rule.
    def reorder(d):
        d["rules"] = [d["rules"][1], d["rules"][0], d["rules"][2]]
    r = probe(reorder)
    check("wellformedness_not_first" in r.codes(),
          f"well-formedness must be required first: {sorted(r.codes())}")

    r = probe(lambda d: d.update(rules=[]))
    check("no_rules" in r.codes(), f"empty rules: {sorted(r.codes())}")

    r = probe(lambda d: d.update(on_accept="delete_everything"))
    check("unknown_on_accept" in r.codes(), f"on_accept: {sorted(r.codes())}")

    r = probe(lambda d: d.update(holidays="fixtures/nope.json"))
    check("missing_data_file" in r.codes(), f"missing file: {sorted(r.codes())}")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"holidays": "not a list"}', encoding="utf-8")
        m = model_from_json({**raw, "holidays": bad.name})
        r2 = validate(m, Path(td))
        seen_codes |= r2.codes()
        check("malformed_data_file" in r2.codes(),
              f"malformed data must be caught by the MODEL, not at execution: "
              f"{sorted(r2.codes())}")

    # A rule without a refusal reason.
    r = probe(lambda d: d["rules"].__setitem__(1, {"rule": "not_holiday"}))
    check("missing_key" in r.codes(), f"rule without refusal: {sorted(r.codes())}")

    untested = sorted(set(PROBLEM_CODES) - seen_codes)
    check(not untested, f"declared but unexercised problem codes: {untested}")

    if failures:
        import sys
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(PROBLEM_CODES)} problem "
          f"codes exercised / well-formedness enforced first rather than reordered)")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
