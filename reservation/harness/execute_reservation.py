#!/usr/bin/env python3
"""The EXECUTOR half: evaluate a validated model against a request. No judgement.

Deterministic. No model in the LLM sense, no clock, no network, no hidden state.
Given the same model, the same data and the same request it returns the same
decision, and it returns a NEW reservation list rather than mutating one.

Two rules carried over from the recipe executor, because they are what makes the
split worth having:

1. **Evaluate only what the model declares, in the order it declares it.** The
   rule list is the precedence. "Whichever check ran first" is authority by
   accident.
2. **Refuse a model this executor cannot honour.** A rule name the executor does
   not implement stops the run. Doing something reasonable instead is how a
   declared rule silently stops being enforced.

See `reservation/design/reservation_model_v1.md`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from datetime import date
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from reservation_model import (  # noqa: E402
    Model, load_dates, load_model, validate,
)


class UnhonourableModel(Exception):
    """The model declares something this executor cannot evaluate."""


@dataclass
class Decision:
    accepted: bool
    request: str
    reason: Optional[str] = None          # the DECISIVE refusal, if refused
    evaluated: list[str] = dc_field(default_factory=list)
    reservations: tuple[str, ...] = ()    # the list AFTER the decision

    def as_dict(self) -> dict:
        return {"accepted": self.accepted, "request": self.request,
                "reason": self.reason, "evaluated": self.evaluated,
                "reservations": list(self.reservations)}


def _is_well_formed(request: str) -> bool:
    """ISO 8601 calendar date, and a real one.

    `date.fromisoformat` rejects 2026-02-30 and 2026-13-01, which is the point:
    "well-formed" here means a date that exists, not a string that looks like one.
    """
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False
    return True


# Every rule the executor can evaluate, keyed by the name the model declares.
# A model naming anything outside this mapping is refused rather than
# approximated -- the same contract the recipe executor enforces.
def _eval_rule(name: str, request: str, holidays: frozenset,
               reservations: tuple[str, ...]) -> bool:
    """True if the rule PASSES (the request survives it)."""
    if name == "date_well_formed":
        return _is_well_formed(request)
    if name == "not_holiday":
        return request not in holidays
    if name == "not_reserved":
        return request not in reservations
    raise UnhonourableModel(
        f"the model declares rule {name!r}, which this executor does not "
        f"implement; refusing rather than skipping it")


SUPPORTED_RULES = ("date_well_formed", "not_holiday", "not_reserved")
SUPPORTED_ON_ACCEPT = ("append_to_reservations",)


def execute(model: Model, base: Path, request: str) -> Decision:
    """Evaluate `request` against `model`. Returns a Decision; mutates nothing."""
    report = validate(model, base)
    if not report.valid:
        raise UnhonourableModel(
            "refusing to execute an invalid model: "
            + "; ".join(str(p) for p in report.problems[:4]))

    # Contract check BEFORE any evaluation, so an unhonourable model cannot be
    # partially executed and then abandoned halfway through its rule list.
    for rule in model.rules:
        if rule.rule not in SUPPORTED_RULES:
            raise UnhonourableModel(
                f"rule {rule.rule!r} is declared but not implemented")
    if model.on_accept not in SUPPORTED_ON_ACCEPT:
        raise UnhonourableModel(
            f"on_accept {model.on_accept!r} is declared but not implemented")

    holidays = frozenset(load_dates(base, model.holidays_path, "holidays"))
    reservations = load_dates(base, model.reservations_path, "reservations")

    evaluated: list[str] = []
    for rule in model.rules:                      # DECLARED order, not ours
        evaluated.append(rule.rule)
        if not _eval_rule(rule.rule, request, holidays, reservations):
            # First failure decides. Later rules are deliberately NOT evaluated:
            # `not_holiday` has no defined answer for a malformed date, and
            # reporting a second reason would imply it was checked when it was
            # not.
            return Decision(accepted=False, request=request, reason=rule.refusal,
                            evaluated=evaluated, reservations=reservations)

    # on_accept: append, returning a NEW list.
    return Decision(accepted=True, request=request, reason=None,
                    evaluated=evaluated, reservations=tuple(reservations) + (request,))


def execute_many(model: Model, base: Path, requests: list[str]) -> list[Decision]:
    """Process requests in sequence, carrying the reservation list forward.

    Needed to answer the question a single call cannot: does an ACCEPT actually
    take effect? The same date requested twice must be accepted then refused.
    Written by threading the returned list rather than by re-reading the file, so
    the test does not depend on the executor writing anything to disk.
    """
    out: list[Decision] = []
    current = load_dates(base, model.reservations_path, "reservations")
    for request in requests:
        decision = _execute_against(model, base, request, current)
        out.append(decision)
        current = decision.reservations
    return out


def _execute_against(model: Model, base: Path, request: str,
                     reservations: tuple[str, ...]) -> Decision:
    """`execute`, but against an in-memory reservation list."""
    holidays = frozenset(load_dates(base, model.holidays_path, "holidays"))
    evaluated: list[str] = []
    for rule in model.rules:
        evaluated.append(rule.rule)
        if not _eval_rule(rule.rule, request, holidays, reservations):
            return Decision(accepted=False, request=request, reason=rule.refusal,
                            evaluated=evaluated, reservations=reservations)
    return Decision(accepted=True, request=request, reason=None,
                    evaluated=evaluated, reservations=tuple(reservations) + (request,))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: execute_reservation.py <model.json> <YYYY-MM-DD>\n")
        return 2
    model_path = Path(argv[0]).resolve()
    base = model_path.parent.parent
    decision = execute(load_model(model_path), base, argv[1])
    print(json.dumps(decision.as_dict(), indent=2, ensure_ascii=False))
    return 0 if decision.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
