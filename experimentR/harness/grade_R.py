#!/usr/bin/env python3
"""Grade a proposed node definition. Deterministic, and NOT string comparison.

A definition may differ textually from the hand-written one and still be right.
It is graded on what it DOES:

```text
G1  VALID        the task's own validator accepts it
G2  EQUIVALENT   run against the hand-written oracle over the frozen request
                 sequence: same decisions AND same final state
G3  STRUCTURAL   reported, NOT a pass criterion -- rule set, rule ORDER,
                 refusal mapping, on_accept
```

**G2 is the pass criterion.** G3 is recorded because a definition that reaches
the right behaviour by a different route is interesting and must not be silently
scored as identical.

The self-test proves the grader can FAIL before any model output is trusted.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
JOB = LAB / "calendar_job"
sys.path.insert(0, str(LAB / "taskmodel"))
sys.path.insert(0, str(LAB / "reservation" / "harness"))
sys.path.insert(0, str(JOB))

import reservation_model  # noqa: E402,F401  (registers the task type)
import task_model  # noqa: E402
import equivalence  # noqa: E402

ESTABLISHED = json.loads((JOB / "definition" / "calendar_job.json")
                         .read_text(encoding="utf-8"))


def _workspace(tmp: Path, tag: str, definition: dict) -> Path:
    ws = tmp / tag
    (ws / "fixtures").mkdir(parents=True)
    (ws / "definition").mkdir(parents=True)
    for name in ("holidays.json", "reservations.json"):
        shutil.copy(JOB / "fixtures" / name, ws / "fixtures" / name)
    (ws / "definition" / "calendar_job.json").write_text(
        json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ws


def g1_valid(definition: dict) -> dict:
    """The task's own validator. Nothing is added here."""
    with tempfile.TemporaryDirectory() as td:
        ws = _workspace(Path(td), "g1", definition)
        report = task_model.validate(task_model.parse(definition), ws)
    return {"valid": report.valid,
            "codes": sorted(report.codes()),
            "problems": [str(p) for p in report.problems]}


def g2_equivalent(definition: dict) -> dict:
    """Does it do the same job as the ten-minute Python oracle?

    Both sides run the frozen six-request sequence from identical copies of the
    same data, and must agree on every decision AND on the reservation list left
    behind.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ref_ws = equivalence._workspace(tmp, "oracle")
        cand_ws = _workspace(tmp, "candidate", definition)
        # The candidate workspace needs the same starting state as the oracle's.
        shutil.copy(JOB / "fixtures" / "reservations.json",
                    cand_ws / "fixtures" / "reservations.json")

        oracle = equivalence.run_reference(ref_ws)
        try:
            candidate = equivalence.unattended.run(
                equivalence.REQUESTS, base=cand_ws,
                definition_path=cand_ws / "definition" / "calendar_job.json")
        except Exception as exc:                 # noqa: BLE001 - reported
            return {"equivalent": False, "error": f"{type(exc).__name__}: {exc}"}

        oracle_state = equivalence._state(ref_ws)
        cand_state = equivalence._state(cand_ws)

    decisions_agree = oracle == candidate
    state_agrees = oracle_state == cand_state
    return {"equivalent": decisions_agree and state_agrees,
            "decisions_agree": decisions_agree, "state_agrees": state_agrees,
            "oracle_decisions": oracle, "candidate_decisions": candidate,
            "oracle_state": oracle_state, "candidate_state": cand_state}


def g3_structural(definition: dict) -> dict:
    """Reported, never a pass criterion. Order is compared, because order is
    semantics: the first failing rule decides the refusal."""
    def shape(d: dict) -> dict:
        return {"rules": [(r.get("rule"), r.get("refusal"))
                          for r in d.get("rules", [])],
                "on_accept": d.get("on_accept"),
                "sources": {k: v.get("collection")
                            for k, v in (d.get("sources") or {}).items()}}

    want, got = shape(ESTABLISHED), shape(definition)
    return {"matches": want == got, "established": want, "proposed": got,
            "rule_order_matches": [r[0] for r in want["rules"]] == [r[0] for r in got["rules"]],
            "differs_only_in_prose": (want == got
                                      and definition.get("purpose") != ESTABLISHED.get("purpose"))}


def grade(definition: dict) -> dict:
    g1 = g1_valid(definition)
    g2 = g2_equivalent(definition) if g1["valid"] else {
        "equivalent": False, "skipped": "not run: an invalid definition is never executed"}
    g3 = g3_structural(definition)
    return {"G1_valid": g1, "G2_equivalent": g2, "G3_structural": g3,
            "passed": bool(g1["valid"] and g2.get("equivalent"))}


def _self_test() -> int:
    """The grader must be shown able to FAIL before any model output is trusted."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- control: the established definition must pass its own grader --------
    control = grade(copy.deepcopy(ESTABLISHED))
    check(control["passed"], f"the established definition must grade PASS: {control}")
    check(control["G3_structural"]["matches"], "…and match itself structurally")

    # --- canary 1: the holiday rule removed ---------------------------------
    no_holiday = copy.deepcopy(ESTABLISHED)
    no_holiday["rules"] = [r for r in no_holiday["rules"] if r["rule"] != "not_holiday"]
    c1 = grade(no_holiday)
    check(c1["G1_valid"]["valid"],
          "a definition missing a rule is still VALID -- the format cannot know "
          "which rules the job needs, which is exactly why the oracle exists")
    check(not c1["G2_equivalent"]["equivalent"],
          f"CANARY DID NOT FIRE: a definition that books holidays graded "
          f"equivalent: {c1['G2_equivalent']}")

    # --- canary 2: rules reordered ------------------------------------------
    reordered = copy.deepcopy(ESTABLISHED)
    reordered["rules"] = [reordered["rules"][1], reordered["rules"][0],
                          reordered["rules"][2]]
    c2 = grade(reordered)
    check(not c2["G1_valid"]["valid"]
          and "wellformedness_not_first" in c2["G1_valid"]["codes"],
          f"CANARY DID NOT FIRE: a reordered definition must be refused by the "
          f"validator: {c2['G1_valid']}")
    check(c2["G2_equivalent"].get("skipped"),
          "an invalid definition must never be executed")

    # --- canary 3: an invented refusal name ---------------------------------
    invented = copy.deepcopy(ESTABLISHED)
    invented["rules"][1]["refusal"] = "BAD_DATE"
    c3 = grade(invented)
    check(not c3["G1_valid"]["valid"] and "unknown_refusal" in c3["G1_valid"]["codes"],
          f"CANARY DID NOT FIRE: an invented refusal must be refused: {c3['G1_valid']}")

    # --- G3 must not be a pass criterion ------------------------------------
    reworded = copy.deepcopy(ESTABLISHED)
    reworded["purpose"] = "Books a room unless the day is impossible, closed or taken."
    reworded["model_id"] = "someone_elses_name"
    c4 = grade(reworded)
    check(c4["passed"],
          "a definition differing only in PROSE must still pass -- grading is "
          "on what it does, not on matching our JSON")
    check(c4["G3_structural"]["matches"],
          "…and its structure still matches")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (established definition grades PASS / a missing rule is "
          "VALID but NOT equivalent -- the oracle catches what the format cannot / "
          "reordered rules refused by the validator and never executed / an invented "
          "refusal refused / a differently-worded definition still passes, because "
          "grading is on behaviour not text)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    if len(argv) != 1:
        sys.stderr.write("usage: grade_R.py --self-test | <proposed.json>\n")
        return 2
    proposed = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    print(json.dumps(grade(proposed), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
