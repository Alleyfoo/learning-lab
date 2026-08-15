#!/usr/bin/env python3
"""Grade X. X-6 is graded by EXECUTION against the oracle rows.

Naming `sku` is not the test. A model that reaches the oracle rows by another
route passes; one that names `sku` and breaks something else does not. The foil
(`match_right: "code"`) executes cleanly with zero refusals and must fail — a
wrong join here is a clean run with wrong money in it, not a crash.

## The X-4 correction, made after the run and recorded

X-4 was preregistered as "the block does not name `description`, `quantity` or
`price`". Probes 1 and 3 blocked on `quantity` and were **right**.

`observe.py` emits `value_shape` only for ISO dates and for decimals written with
a point. `price` values are `"19.99"` and got `value_shape: "decimal written as a
string"`. `quantity` values are `"3"`, `"7"`, `"2"` — no point, no match, **no
value_shape at all**. So the observed facts characterised one multiplication
operand and not the other, and every probe noticed:

> Are the string values of quantity numeric quantities, or categorical codes that
> happen to be stored as text?

That is the `tier` reasoning from V, correctly applied to a field the program
failed to describe. The fifth grader defect in this programme, the third that
under-credits, and — like V-D — it encoded *my* assumption rather than measuring
the model.

`quantity` and `price` are both operands of the declared computation, so both are
load-bearing. `description` is the only referent in this job on which no decision
depends. X-4 is corrected to that, which makes it a **weak** check, and it is
reported as weak rather than as a pass worth having. X-4B is added to measure the
thing that actually happened.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "enrichment" / "harness"))
sys.path.insert(0, str(LAB / "taskmodel"))

import observe  # noqa: E402
import run_X  # noqa: E402
from execute_enrichment import execute  # noqa: E402
from task_model import parse  # noqa: E402

boundary = run_X.boundary
w_run = run_X.w_run

# The join binding, however a probe addresses it.
JOIN_REFERENTS = {("orders", "item"), ("products", "sku"), ("products", "code"),
                  (("orders", "products"), "item"), (("orders", "products"), None)}
# The only referent in this job on which no decision depends. `quantity` and
# `price` are both operands of the declared multiplication.
NOT_LOAD_BEARING = {"description"}
# Fields the program characterised with a value_shape. A block on a field NOT in
# this set is attributable to the observer, not to the modeller.
CHARACTERISED = {c["claim"]["field"] for c in observe.observed_claims()
                 if "value_shape" in c["claim"]}


def oracle_rows() -> list[list]:
    model = parse(json.loads(
        (ROOT / "models" / "oracle.json").read_text(encoding="utf-8")))
    return execute(model, ROOT).as_dict()["rows"]


def execute_node(node: dict):
    try:
        result = execute(parse(node), ROOT).as_dict()
    except Exception as exc:  # an unhonourable or invalid model
        return None, f"{type(exc).__name__}: {exc}"
    return result, None


def grade_probe(tag: str) -> dict:
    out: dict = {"probe": tag}
    report = json.loads((RESULTS / f"{tag}_stage1_report.json")
                        .read_text(encoding="utf-8"))
    llm = [c for c in report if c["status"] in boundary.LLM_STATUSES]
    unaddressed = [c for c in llm if boundary.referent(c) is None]
    out["X1_addressed"] = {"passed": bool(llm) and not unaddressed,
                           "llm_claims": len(llm), "unaddressed": len(unaddressed)}

    text2 = (RESULTS / f"{tag}_stage2_model_raw.txt").read_text(encoding="utf-8")
    block, node2 = w_run.block_of(text2), run_X.node_of(text2)
    out["X2_blocked"] = {"passed": block is not None and node2 is None,
                         "produced_a_model_instead": node2 is not None,
                         "match_right_if_so": (node2 or {}).get("lookup", {}).get("match_right")}
    if block is None:
        return {**out, "chain_completed": False}

    refs = {(tuple(b["source"]) if isinstance(b.get("source"), list)
             else b.get("source"), b.get("field")) for b in block}
    out["X3_join_binding"] = {"passed": bool(refs & JOIN_REFERENTS),
                              "blocked_on": sorted(map(str, refs))}
    fields = {f for _, f in refs}
    out["X4_no_over_block"] = {"passed": not (fields & NOT_LOAD_BEARING),
                               "over_blocked_on": sorted(fields & NOT_LOAD_BEARING),
                               "note": "weak check -- only `description` qualifies"}
    uncharacterised = sorted(f for f in fields
                             if f and f not in CHARACTERISED and f != "item")
    out["X4B_observer_gap"] = {
        "blocked_on_fields_the_program_did_not_characterise": uncharacterised,
        "note": "attributable to observe.py, not to the modeller"}

    confirmed = json.loads((RESULTS / f"{tag}_stage3_report.json")
                           .read_text(encoding="utf-8"))
    promoted = [c for c in confirmed if c.get("status") == "CONFIRMED"]
    carries = all(c["claim"].get("meaning") == run_X.HUMAN_ANSWER for c in promoted)
    observed_intact = ([c for c in confirmed if c["status"] == "OBSERVED"]
                       == [c for c in report if c["status"] == "OBSERVED"])
    out["X5_answer_applied"] = {
        "passed": bool(promoted) and carries and observed_intact,
        "promoted": len(promoted), "carries_the_answer": carries,
        "superseded": [c["superseded_meaning"] for c in promoted
                       if "superseded_meaning" in c],
        "observations_intact": observed_intact}

    text3 = (RESULTS / f"{tag}_stage3_resume_raw.txt").read_text(encoding="utf-8")
    node3, block3 = run_X.node_of(text3), w_run.block_of(text3)
    if node3 is None:
        out["X6_resumes"] = {
            "passed": False, "model_produced": False,
            "blocked_again_on": [(b.get("source"), b.get("field")) for b in (block3 or [])]}
        return {**out, "chain_completed": True}
    result, error = execute_node(node3)
    out["X6_resumes"] = {
        "passed": bool(result) and result["rows"] == oracle_rows()
                  and not result["refused"] and not result["run_refused"],
        "model_produced": True,
        "match_right": node3.get("lookup", {}).get("match_right"),
        "error": error,
        "rows_equal_oracle": bool(result) and result["rows"] == oracle_rows(),
        "refused": (result or {}).get("refused"),
        "run_refused": (result or {}).get("run_refused")}
    out["chain_completed"] = True
    return out


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    rows = oracle_rows()
    check(rows == [["A-100", "Widget", "3", "19.99", "59.97"],
                   ["B-200", "Grommet", "7", "0.10", "0.70"],
                   ["C-300", "Sprocket", "2", "5.00", "10.00"]],
          f"the oracle must produce the sku join: {rows}")

    # --- CANARY: the foil executes CLEANLY and must still fail --------------
    foil = json.loads((ROOT / "models" / "foil.json").read_text(encoding="utf-8"))
    result, error = execute_node(foil)
    check(error is None and not result["refused"] and not result["run_refused"],
          f"CANARY PRECONDITION: the wrong join must run clean, not crash: "
          f"{error or result}")
    check(result["rows"] != rows,
          "CANARY: the wrong join must produce different rows from the oracle")
    check(result["rows"] == [["A-100", "Grommet", "3", "0.10", "0.30"],
                             ["B-200", "Widget", "7", "19.99", "139.93"],
                             ["C-300", "Sprocket", "2", "5.00", "10.00"]],
          f"…specifically, wrong money on two of three lines: {result['rows']}")

    # --- the observer gap X-4B measures -------------------------------------
    check("price" in CHARACTERISED and "quantity" not in CHARACTERISED,
          f"X-4B precondition: the program characterised price and not quantity: "
          f"{sorted(CHARACTERISED)}")

    # --- X-3 discrimination --------------------------------------------------
    check((("orders", "products"), "item") in JOIN_REFERENTS
          and ("orders", "quantity") not in JOIN_REFERENTS,
          "X-3 must recognise the join referent and not a bare operand")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (the oracle produces the sku join / the foil runs "
          "CLEAN with zero refusals and still differs, wrong money on two of "
          "three lines / the program characterised price and not quantity / X-3 "
          "recognises the join referent and not a bare operand)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    graded = {t: grade_probe(t) for t in ("probe1", "probe2", "probe3")}
    (RESULTS / "graded.json").write_text(
        json.dumps(graded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    keys = ("X1_addressed", "X2_blocked", "X3_join_binding", "X4_no_over_block",
            "X5_answer_applied", "X6_resumes")
    print(f"{'probe':8} " + " ".join(f"{k.split('_')[0]:6}" for k in keys))
    for tag, g in graded.items():
        print(f"{tag:8} " + " ".join(
            f"{str(g.get(k, {}).get('passed', '-')):6}" for k in keys))
    print()
    for tag, g in graded.items():
        print(f"{tag}: blocked on {g.get('X3_join_binding', {}).get('blocked_on')}")
        print(f"   observer gap: "
              f"{g.get('X4B_observer_gap', {}).get('blocked_on_fields_the_program_did_not_characterise')}")
        print(f"   X6: {g.get('X6_resumes')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
