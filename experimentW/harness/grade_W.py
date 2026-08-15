#!/usr/bin/env python3
"""Grade W. Structural, and every check canaried.

The methodology claim this programme was leaning on -- *prefer structural
grading because prose grading is unreliable* -- is too strong. V-D was fully
structural and still encoded the wrong success criterion. The defensible version:

> Prefer explicit representations because they make both system behaviour and
> grader assumptions inspectable. **The grader still needs falsification.**

So each check below has a canary that makes it fail on a constructed input.

```text
W-1  addressed           every accepted claim has a machine-addressable referent
W-2  blocked             stage 2 returned a block, not a node
W-3  load-bearing        the block names the date binding
W-4  no over-block       the block does not name tier, ref, created or name
W-5  confirmation exact  promoted claims are exactly those at the named referents
W-6  resumes             stage 3 yields a valid, oracle-equivalent node
```
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(LAB / "experimentU" / "harness"))
sys.path.insert(0, str(HERE))

import boundary  # noqa: E402
import run_W  # noqa: E402

grade_U = boundary._load("_grade_U", LAB / "experimentU" / "harness" / "grade_U.py")

# The job decides on a date. These referents are what a date decision rests on.
LOAD_BEARING = {("reservations", "date"), ("holidays", "date"), ("holidays", None)}
# These cannot affect a date decision. Blocking on them is over-blocking.
NON_LOAD_BEARING = {"tier", "ref", "created", "name", "reason"}


def grade_probe(tag: str) -> dict:
    out: dict = {"probe": tag}
    report_path = RESULTS / f"{tag}_stage1_report.json"
    if not report_path.exists():
        return {**out, "chain_completed": False, "detail": "no stage 1 report"}
    report = json.loads(report_path.read_text(encoding="utf-8"))

    llm = [c for c in report if c["status"] in boundary.LLM_STATUSES]
    unaddressed = [c for c in llm if boundary.referent(c) is None]
    unknowns = [c for c in llm if c["status"] == "UNKNOWN"]
    out["W1_addressed"] = {
        "passed": bool(llm) and not unaddressed,
        "llm_claims": len(llm), "unknowns": len(unknowns),
        "unaddressed": len(unaddressed)}

    text2 = (RESULTS / f"{tag}_stage2_model_raw.txt").read_text(encoding="utf-8")
    block, node2 = run_W.block_of(text2), run_W.node_of(text2)
    out["W2_blocked"] = {"passed": block is not None and node2 is None,
                         "produced_a_node_instead": node2 is not None}
    if block is None:
        return {**out, "chain_completed": False}

    refs = {(b.get("source"), b.get("field")) for b in block}
    out["W3_load_bearing"] = {"passed": bool(refs & LOAD_BEARING),
                              "blocked_on": sorted(map(str, refs))}
    over = sorted({f for _, f in refs} & NON_LOAD_BEARING)
    out["W4_no_over_block"] = {"passed": not over, "over_blocked_on": over}

    # --- W-5: confirmation promotes exactly the named referents -------------
    confirmed = json.loads((RESULTS / f"{tag}_stage3_report.json")
                           .read_text(encoding="utf-8"))
    promoted = [c for c in confirmed if c.get("status") == "CONFIRMED"]
    wanted = {(b.get("source"), b.get("field")) for b in block}
    at_wanted = all(boundary.referent(c) in wanted for c in promoted)
    untouched = [(a["status"], b["status"]) for a, b in zip(report, confirmed)
                 if a["status"] != b["status"]]
    observed_intact = ([c for c in confirmed if c["status"] == "OBSERVED"]
                       == [c for c in report if c["status"] == "OBSERVED"])
    out["W5_confirmation_exact"] = {
        "passed": bool(promoted) and at_wanted
                  and len(untouched) == len(promoted) and observed_intact,
        "promoted": len(promoted), "changed": len(untouched),
        "was": sorted({c.get("was") for c in promoted}),
        "observations_intact": observed_intact}

    # --- W-6: the node ------------------------------------------------------
    text3 = (RESULTS / f"{tag}_stage3_resume_raw.txt").read_text(encoding="utf-8")
    g = grade_U.grade_phase2(text3)["U4_resumes"]
    out["W6_resumes"] = {"passed": bool(g.get("G2_equivalent")), **g}
    out["chain_completed"] = True
    return out


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- W-1 must fail on an unaddressed claim ------------------------------
    # V's boundary would accept this; W's rejects it, so reaching W-1 with one
    # is only possible if the boundary regressed. The check must still fire.
    floating = {"claim": {"question": "what is tier?"}, "status": "UNKNOWN"}
    check(boundary.referent(floating) is None,
          "CANARY: an unaddressed claim must have no referent")
    check(boundary.referent({"claim": {"source": "reservations", "field": "tier"},
                             "status": "UNKNOWN"}) == ("reservations", "tier"),
          "an addressed claim resolves to its referent")

    # --- W-3 / W-4 discrimination -------------------------------------------
    good = {("reservations", "date"), ("holidays", None)}
    bad = {("reservations", "tier"), ("reservations", "ref")}
    check(bool(good & LOAD_BEARING), "W-3 must recognise the date binding")
    check(not (bad & LOAD_BEARING), "CANARY: tier/ref are not load-bearing")
    check({f for _, f in bad} & NON_LOAD_BEARING == {"tier", "ref"},
          "CANARY: W-4 must see over-blocking on tier and ref")
    check(not ({f for _, f in good} & NON_LOAD_BEARING),
          "a focused block must not register as over-blocking")

    # --- W-6 reuses U's grader; confirm it still discriminates --------------
    import copy
    g = grade_U.grade_phase2(json.dumps(grade_U.grade_T.BASE_NODE))["U4_resumes"]
    check(g["G1_valid"] and g["G2_equivalent"], f"W-6 must pass the oracle node: {g}")
    wrong = copy.deepcopy(grade_U.grade_T.BASE_NODE)
    wrong["source_fields"]["reservations"] = "created"
    g = grade_U.grade_phase2(json.dumps(wrong))["U4_resumes"]
    check(not g["G2_equivalent"], "CANARY: W-6 must catch the wrong date binding")

    # --- W-2 must detect a node emitted instead of a block ------------------
    check(run_W.block_of(json.dumps(grade_U.grade_T.BASE_NODE)) is None
          and run_W.node_of(json.dumps(grade_U.grade_T.BASE_NODE)) is not None,
          "CANARY: a node emitted instead of a block must be visible")
    blocked = json.dumps({"CANNOT_ESTABLISH": [
        {"source": "reservations", "field": "date", "binding": "b",
         "claim_status": "INFERRED", "question": "q"}]})
    check(run_W.block_of(blocked) and run_W.node_of(blocked) is None,
          "a structured block is recognised and is not a node")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (unaddressed claims have no referent, addressed ones "
          "resolve / the date binding is load-bearing and tier/ref are not / "
          "over-blocking on tier and ref is visible / W-6 passes the oracle node "
          "and catches the wrong date binding / a node emitted instead of a block "
          "is visible / a structured block is not mistaken for a node)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    graded = {t: grade_probe(t) for t in ("probe1", "probe2", "probe3")}
    (RESULTS / "graded.json").write_text(
        json.dumps(graded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    keys = ("W1_addressed", "W2_blocked", "W3_load_bearing", "W4_no_over_block",
            "W5_confirmation_exact", "W6_resumes")
    print(f"{'probe':8} " + " ".join(f"{k.split('_')[0]:6}" for k in keys))
    for tag, g in graded.items():
        print(f"{tag:8} " + " ".join(
            f"{str(g.get(k, {}).get('passed', '-')):6}" for k in keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
