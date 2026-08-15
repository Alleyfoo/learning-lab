#!/usr/bin/env python3
"""Run the reservation task against fixture data, graded on stated expectations.

Every expected outcome below is written in this file BEFORE the run, the way the
cross-sheet laws state their required outcome per case. The point is not that the
code passes; it is that the expectations were fixed first and are readable.

The question being answered is narrow and worth keeping narrow:

> can the system MODEL a real data task and then EXECUTE it deterministically,
> with the model owning the decisions and the executor owning none?

Usage
-----
    python reservation/harness/run_reservation.py            # run + record
    python reservation/harness/run_reservation.py --no-record
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))

import reservation_model  # noqa: E402
from execute_reservation import (  # noqa: E402
    SUPPORTED_ON_ACCEPT, SUPPORTED_RULES, UnhonourableModel, execute, execute_many,
)
from reservation_model import load_model, validate  # noqa: E402

RESULTS = BASE / "results"
MODEL_PATH = BASE / "models" / "reservation_v1.json"

# (label, request, expected accepted, expected refusal reason, why)
CASES: list[tuple[str, str, bool, Optional[str], str]] = [
    ("ordinary_free_day", "2026-05-20", True, None,
     "a real date, not in the holiday list, not in the reservation list"),
    ("impossible_date", "2026-02-30", False, "INVALID_DATE",
     "well-formed-looking and not a real day; the check is that the date EXISTS, "
     "not that the string matches a pattern"),
    ("not_a_date", "next tuesday", False, "INVALID_DATE",
     "free text must be refused by the same rule, not crash the executor"),
    ("wrong_format", "20/05/2026", False, "INVALID_DATE",
     "a real day written the wrong way is still not an ISO date; v1 declares one "
     "format and does not guess between conventions"),
    ("holiday", "2026-12-25", False, "HOLIDAY",
     "in the declared holiday list"),
    ("already_reserved", "2026-03-10", False, "ALREADY_RESERVED",
     "in the declared reservation list"),
    ("holiday_AND_reserved", "2026-12-06", False, "HOLIDAY",
     "BOTH true. The reported reason must follow the model's declared rule "
     "ORDER, not whichever check the executor happened to run first -- authority "
     "by accident is what cross-sheet law 5 is named after"),
]

# The sequence case, which a single call cannot answer: does ACCEPT take effect?
SEQUENCE = ["2026-07-14", "2026-07-14"]
SEQUENCE_EXPECTED = [(True, None), (False, "ALREADY_RESERVED")]

# PRECEDENCE. `holiday_AND_reserved` above cannot on its own establish that the
# executor follows the model's DECLARED order, because in the shipped model the
# declared order and the executor's code order coincide -- so a hardcoded
# executor would pass it. That is law 4's blindness: a corpus symmetric under the
# thing being varied proves nothing.
#
# So the order is PERMUTED and the same request re-run. If the reported reason
# does not change, the rule list is decoration and the separation this whole task
# exists to test does not hold.
PRECEDENCE_REQUEST = "2026-12-06"          # both a holiday AND already reserved
PRECEDENCE_EXPECTED = [
    (["date_well_formed", "not_holiday", "not_reserved"], "HOLIDAY"),
    (["date_well_formed", "not_reserved", "not_holiday"], "ALREADY_RESERVED"),
]


def check_vocabulary_parity() -> dict:
    """The model's vocabulary and the executor's capability must agree.

    Without this the executor's "refuse a rule I cannot honour" guard is
    UNREACHABLE: the model validator already rejects any rule outside its own
    list, so a model declaring an unimplemented rule can never reach execution.
    A guard that cannot fire is not evidence, and the real risk is drift -- a
    rule added to the model vocabulary and never implemented.

    So the guard stays (defence in depth, and it is what makes partial execution
    impossible), and THIS is the check with teeth.
    """
    declared = set(reservation_model.RULES)
    implemented = set(SUPPORTED_RULES)
    declared_accept = set(reservation_model.ON_ACCEPT)
    implemented_accept = set(SUPPORTED_ON_ACCEPT)
    return {
        "rules_declared_not_implemented": sorted(declared - implemented),
        "rules_implemented_not_declared": sorted(implemented - declared),
        "on_accept_declared_not_implemented": sorted(declared_accept - implemented_accept),
        "on_accept_implemented_not_declared": sorted(implemented_accept - declared_accept),
        "agree": declared == implemented and declared_accept == implemented_accept,
    }


def run_all() -> dict:
    model = load_model(MODEL_PATH)
    report = validate(model, BASE)

    parity = check_vocabulary_parity()

    results: list[dict] = []
    if report.valid:
        for label, request, want_ok, want_reason, why in CASES:
            d = execute(model, BASE, request)
            ok = (d.accepted == want_ok) and (d.reason == want_reason)
            results.append({
                "case": label, "request": request, "rationale": why,
                "expected": {"accepted": want_ok, "reason": want_reason},
                "observed": {"accepted": d.accepted, "reason": d.reason,
                             "evaluated": d.evaluated},
                "status": "PASS" if ok else "FAIL",
            })

    # --- the sequence: does an ACCEPT actually take effect? -------------------
    sequence: list[dict] = []
    if report.valid:
        decisions = execute_many(model, BASE, SEQUENCE)
        for i, (d, (want_ok, want_reason)) in enumerate(zip(decisions, SEQUENCE_EXPECTED)):
            ok = (d.accepted == want_ok) and (d.reason == want_reason)
            sequence.append({
                "step": i, "request": d.request,
                "expected": {"accepted": want_ok, "reason": want_reason},
                "observed": {"accepted": d.accepted, "reason": d.reason},
                "reservations_after": list(d.reservations),
                "status": "PASS" if ok else "FAIL",
            })

    # --- precedence: permute the declared order, the reason must follow ------
    precedence: list[dict] = []
    if report.valid:
        raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        by_name = {r["rule"]: r for r in raw["rules"]}
        for order, want_reason in PRECEDENCE_EXPECTED:
            variant = reservation_model.model_from_json(
                {**raw, "rules": [by_name[n] for n in order]})
            vrep = validate(variant, BASE)
            if not vrep.valid:
                precedence.append({"order": order, "status": "FAIL",
                                   "detail": f"variant invalid: {sorted(vrep.codes())}"})
                continue
            d = execute(variant, BASE, PRECEDENCE_REQUEST)
            ok = d.reason == want_reason
            precedence.append({
                "order": order, "request": PRECEDENCE_REQUEST,
                "expected_reason": want_reason, "observed_reason": d.reason,
                "evaluated": d.evaluated,
                "status": "PASS" if ok else "FAIL",
                "detail": ("the reported reason follows the DECLARED order" if ok
                           else "the reason did NOT follow the declared order -- "
                                "the rule list is decoration and the executor is "
                                "deciding precedence itself")})

    # --- CANARY: would the precedence check notice a hardcoded executor? -----
    # The precedence pair above is only evidence if it can FAIL. Here the
    # declared order is thrown away and a fixed order used instead -- exactly
    # what an executor that ignored the rule list would do. The precedence
    # expectation must then be violated. If this canary stops firing, the
    # precedence result has stopped meaning anything.
    canary_fired = False
    if report.valid:
        raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        by_name = {r["rule"]: r for r in raw["rules"]}
        fixed = ["date_well_formed", "not_holiday", "not_reserved"]
        observed = []
        for order, _ in PRECEDENCE_EXPECTED:
            del order                       # deliberately ignored, as the defect would
            hardcoded = reservation_model.model_from_json(
                {**raw, "rules": [by_name[n] for n in fixed]})
            observed.append(execute(hardcoded, BASE, PRECEDENCE_REQUEST).reason)
        expected = [want for _, want in PRECEDENCE_EXPECTED]
        canary_fired = observed != expected

    # --- the executor must refuse an invalid model, not run it ---------------
    refused_invalid_model = False
    broken = load_model(MODEL_PATH)
    broken.on_accept = "delete_everything"
    try:
        execute(broken, BASE, "2026-05-20")
    except UnhonourableModel:
        refused_invalid_model = True

    failed = [r for r in results + sequence + precedence if r["status"] == "FAIL"]
    if not report.valid:
        outcome = "MODEL_INVALID"
    elif not canary_fired:
        outcome = "VOID"
    elif not parity["agree"]:
        outcome = "VOCABULARY_DRIFT"
    elif not refused_invalid_model:
        outcome = "EXECUTOR_RAN_AN_INVALID_MODEL"
    elif failed:
        outcome = "TASK_FAILED"
    else:
        outcome = "TASK_MODELLED_AND_EXECUTED"

    return {
        "question": ("can the system model a real data task and execute it "
                     "deterministically, with the model owning the decisions?"),
        "model_valid": report.valid,
        "model_problems": [str(p) for p in report.problems],
        "vocabulary_parity": parity,
        "executor_refuses_invalid_model": refused_invalid_model,
        "precedence_canary_fired": canary_fired,
        "cases": results,
        "sequence": sequence,
        "precedence": precedence,
        "outcome": outcome,
        "stated_limitation": (
            "fixture data, one model, seven single requests and one two-step "
            "sequence. No recurrence, no ranges, no capacity, no time zones, no "
            "concurrent requests, and no persistence -- the executor returns a "
            "new list and writes nothing. This says the SPLIT works on a small "
            "real task; it says nothing about the model being complete."),
    }


def main(argv: list[str]) -> int:
    result = run_all()

    p = result["vocabulary_parity"]
    print(f"  model valid: {result['model_valid']}   "
          f"vocabulary agrees: {p['agree']}   "
          f"executor refuses invalid model: {result['executor_refuses_invalid_model']}")
    print(f"  precedence canary fired: {result['precedence_canary_fired']}"
          f"  (a hardcoded executor WOULD be caught)\n")
    for r in result["cases"]:
        print(f"  {r['status']:5} {r['case']:22} {r['request']:14} -> "
              f"accepted={r['observed']['accepted']} reason={r['observed']['reason']}")
    print()
    for s in result["sequence"]:
        print(f"  {s['status']:5} sequence[{s['step']}]        {s['request']:14} -> "
              f"accepted={s['observed']['accepted']} reason={s['observed']['reason']}")
    print()
    for pr in result["precedence"]:
        order = " then ".join(pr["order"][1:])
        print(f"  {pr['status']:5} precedence  {order:34} -> {pr.get('observed_reason')}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"reservation_run{n}.json").exists():
            n += 1
        path = RESULTS / f"reservation_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "TASK_MODELLED_AND_EXECUTED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
