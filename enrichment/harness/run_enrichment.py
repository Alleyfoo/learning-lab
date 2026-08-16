#!/usr/bin/env python3
"""Run the enrichment task, graded on expectations stated before the run.

Two claims are under test, and each is only established by PERMUTING the
declaration and requiring the output to follow. A run where the declaration and
the implementation happen to coincide proves nothing -- the blindness cross-sheet
law 4 was VOID for, and the same reason the reservation task permutes rule order.

```text
RELATIONSHIP   join key and missing/ambiguous policy come from the MODEL
COMPUTATION    operands and operation come from the MODEL, and the arithmetic
               is faithful
```

Usage
-----
    python enrichment/harness/run_enrichment.py            # run + record
    python enrichment/harness/run_enrichment.py --no-record
"""
from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import enrichment_model  # noqa: E402
import task_model  # noqa: E402
from enrichment_model import ROUNDING, validate  # noqa: E402
from execute_enrichment import (  # noqa: E402
    SUPPORTED_OPS, SUPPORTED_POLICIES, UnhonourableModel, execute,
)
from task_model import vocabulary_parity  # noqa: E402

RESULTS = BASE / "results"
MODEL_PATH = BASE / "models" / "enrichment_v1.json"

# --- baseline expectations, written before the run --------------------------
# O-1  3 x 19.99 -> 59.97
# O-2  7 x 0.10  -> 0.70    the float trap: 7 * 0.1 is 0.7000000000000001
# O-3  P-999 is not a product          -> MISSING_PRODUCT, row refused
# O-4  quantity "two" is not a number  -> NON_NUMERIC_OPERAND, row refused
BASELINE_ROWS = [
    ["O-1", "Widget", "3", "19.99", "59.97"],
    ["O-2", "Grommet", "7", "0.10", "0.70"],
]
BASELINE_REFUSED = [("P-999", "MISSING_PRODUCT"), ("P-300", "NON_NUMERIC_OPERAND")]

# --- permutation: the COMPUTATION's operand ---------------------------------
# Same op, same left operand, different declared right FIELD. If the executor
# were multiplying by a hardcoded unit_price the totals would not move.
COMPUTE_PERMUTATION_FIELD = "weight"
COMPUTE_PERMUTATION_TOTALS = ["0.75", "10.50"]      # 3 x 0.25, 7 x 1.50

# --- permutation: the RELATIONSHIP's missing policy --------------------------
# Same data, same key, different declared policy. refuse_row keeps the good rows
# and lists the bad one; refuse_run delivers NOTHING.
MISSING_POLICY_EXPECTED = {
    "refuse_row": {"n_rows": 2, "run_refused": False},
    "refuse_run": {"n_rows": 0, "run_refused": True},
}


def _raw() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def _model(mutate=None):
    raw = _raw()
    if mutate:
        mutate(raw)
    return task_model.parse(raw)


def check_vocabulary_parity() -> dict:
    """Model vocabulary vs executor capability.

    As in the reservation task: the executor's "refuse what I cannot honour"
    guard is unreachable while the validator rejects unknown tokens first, so
    the guard is defence in depth and THIS is the check with teeth.
    """
    return vocabulary_parity(
        declared={"ops": enrichment_model.OPS, "policies": enrichment_model.POLICIES},
        implemented={"ops": SUPPORTED_OPS, "policies": SUPPORTED_POLICIES})


def run_all() -> dict:
    model = _model()
    report = validate(model, BASE)
    parity = check_vocabulary_parity()
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str, why: str = "") -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL",
                       "detail": detail, "rationale": why})

    if report.valid:
        # --- baseline --------------------------------------------------------
        base_result = execute(model, BASE)
        record("baseline_rows", base_result.rows == BASELINE_ROWS,
               f"{base_result.rows}",
               "the join and the computation together, including 7 x 0.10 = 0.70 "
               "which float arithmetic gets wrong")
        record("baseline_refusals",
               [(r["key"], r["reason"]) for r in base_result.refused] == BASELINE_REFUSED,
               f"{[(r['key'], r['reason']) for r in base_result.refused]}",
               "a missing key and a non-numeric operand are refused by NAME, not "
               "dropped and not filled in")

        # --- permutation 1: the computation's declared operand ---------------
        def swap_operand(raw: dict) -> None:
            raw["outputs"][4]["compute"]["right"]["field"] = COMPUTE_PERMUTATION_FIELD
        permuted = execute(_model(swap_operand), BASE)
        totals = [r[-1] for r in permuted.rows]
        record("computation_follows_declaration",
               totals == COMPUTE_PERMUTATION_TOTALS,
               f"declared right operand -> {COMPUTE_PERMUTATION_FIELD}; totals {totals}",
               "changing WHICH declared field is multiplied must change the "
               "output; an executor multiplying a hardcoded unit_price would not "
               "move")

        # --- declared numeric representation: A, B, C ------------------------
        # A real timesheet job produced 318.750 and 633.9375 for money. The task
        # language could not say what a person means by "cost", so nothing could
        # be asked and nothing could be fixed. Now a COMPUTED output may declare
        # how it is written, and only a computed one -- a passthrough copies
        # somebody else's text and is refused at validation.
        def represent(places, mode):
            def mutate(raw: dict) -> None:
                raw["outputs"][4]["representation"] = {
                    "decimal_places": places, "rounding": mode}
            return mutate

        # C: nothing declared -> today's exact behaviour, byte for byte.
        record("C_undeclared_is_unchanged", base_result.rows == BASELINE_ROWS,
               f"{[r[-1] for r in base_result.rows]}",
               "a model that declares no representation must behave exactly as "
               "before; the executor never tidies a number on its own")

        # A: the exact result already fits -> representation changes nothing.
        a = execute(_model(represent(2, "half_up")), BASE)
        a_totals = [r[-1] for r in a.rows]
        record("A_exact_already_fits", a_totals == ["59.97", "0.70"],
               f"{a_totals}",
               "19.99 x 3 and 0.10 x 7 already have two places, so declaring two "
               "places must not alter the value -- 0.70 in particular must not "
               "become 0.7")

        # B: the result has more places -> the DECLARED rule decides.
        b = execute(_model(represent(1, "half_up")), BASE)
        b_totals = [r[-1] for r in b.rows]
        record("B_declared_rule_decides", b_totals == ["60.0", "0.7"],
               f"{b_totals}",
               "declaring one place must round 59.97 to 60.0; the same model "
               "with no declaration produced 59.97, so the declaration is what "
               "moved it")

        # The rounding MODE must be the model's, not the language's default.
        # 0.125 is the case where half_up and half_even genuinely disagree, and
        # Python's own default for quantize is half_even.
        modes = {}
        for mode, want in (("half_up", "0.13"), ("half_even", "0.12"),
                           ("down", "0.12"), ("up", "0.13")):
            got = str(Decimal("0.125").quantize(
                Decimal("0.01"), rounding=ROUNDING[mode]))
            modes[mode] = got
        record("rounding_mode_is_the_models",
               modes == {"half_up": "0.13", "half_even": "0.12",
                         "down": "0.12", "up": "0.13"},
               f"0.125 to 2 places -> {modes}",
               "half_up and half_even disagree on an exact half, so a silent "
               "default would be a silent choice about somebody's money")

        # And the disagreement must reach the actual OUTPUT, not just a helper.
        # The baseline totals (59.97, 0.70) sit on no exact half, so every mode
        # agrees on them and a check against those numbers proves nothing --
        # this canary failed first time round for exactly that reason. Swapping
        # the operand to `weight` gives 7 x 1.50 = 10.50, which at zero places
        # is a genuine half: half_up says 11, half_even says 10.
        def half_case(mode):
            def mutate(raw: dict) -> None:
                raw["outputs"][4]["compute"]["right"]["field"] = "weight"
                raw["outputs"][4]["representation"] = {"decimal_places": 0,
                                                       "rounding": mode}
            return mutate

        halves = {}
        for mode in ("half_up", "half_even"):
            halves[mode] = [r[-1] for r in execute(_model(half_case(mode)),
                                                   BASE).rows]
        record("mode_reaches_the_output",
               halves == {"half_up": ["1", "11"], "half_even": ["1", "10"]},
               f"7 x 1.50 = 10.50 at 0 places -> {halves}",
               "CANARY: if both modes produced the same table the executor would "
               "not be reading the declared mode at all")

        # --- permutation 2: the relationship's declared policy ---------------
        policy_detail = {}
        policy_ok = True
        for policy, want in MISSING_POLICY_EXPECTED.items():
            def set_policy(raw: dict, p=policy) -> None:
                raw["lookup"]["on_missing"] = p
            r = execute(_model(set_policy), BASE)
            got = {"n_rows": len(r.rows), "run_refused": r.run_refused is not None}
            policy_detail[policy] = got
            policy_ok = policy_ok and got == want
        record("missing_policy_follows_declaration", policy_ok, f"{policy_detail}",
               "the SAME data under two declared policies must behave "
               "differently, and refuse_run must deliver no rows at all rather "
               "than a partial table beside a refusal")

        # --- ambiguity: a key denoting two rows must not resolve silently ----
        def ambiguous(raw: dict) -> None:
            raw["sources"]["products"]["path"] = "fixtures/products_ambiguous.json"
        amb = execute(_model(ambiguous), BASE)
        record("ambiguous_key_refused",
               amb.run_refused is not None and "AMBIGUOUS" in amb.run_refused
               and not amb.rows,
               f"run_refused={amb.run_refused!r}, rows={len(amb.rows)}",
               "P-100 appears twice at DIFFERENT prices; picking the first is "
               "authority by accident and here it is worth money")

        # --- the executor must refuse a model it cannot honour ---------------
        refused_bad_model = False
        try:
            execute(_model(lambda raw: raw["outputs"][4]["compute"].update(op="divide")),
                    BASE)
        except UnhonourableModel:
            refused_bad_model = True
        record("refuses_unhonourable_model", refused_bad_model,
               f"{refused_bad_model}",
               "an op the executor does not implement stops the run instead of "
               "being approximated")

    # --- CANARY: would the baseline notice unfaithful arithmetic? ------------
    # Substitutes float multiplication -- what a naive executor would do -- and
    # requires the baseline row check to break. If this stops firing, the
    # 0.70 result has stopped being evidence of anything.
    canary_fired = False
    canary_detail = ""
    if report.valid:
        def float_multiply(left: Decimal, right: Decimal) -> str:
            return repr(float(left) * float(right))
        floaty = execute(model, BASE, multiply=float_multiply)
        canary_fired = floaty.rows != BASELINE_ROWS
        canary_detail = f"float arithmetic produced {[r[-1] for r in floaty.rows]}"

    failed = [c for c in checks if c["status"] == "FAIL"]
    if not report.valid:
        outcome = "MODEL_INVALID"
    elif not parity["agree"]:
        outcome = "VOCABULARY_DRIFT"
    elif not canary_fired:
        outcome = "VOID"
    elif failed:
        outcome = "TASK_FAILED"
    else:
        outcome = "RELATION_AND_COMPUTATION_FAITHFUL"

    return {
        "question": ("can a RELATIONSHIP and a COMPUTATION be declared by the "
                     "model and faithfully executed?"),
        "model_valid": report.valid,
        "model_problems": [str(p) for p in report.problems],
        "vocabulary_parity": parity,
        "arithmetic_canary": {"fired": canary_fired, "detail": canary_detail},
        "checks": checks,
        "outcome": outcome,
        "stated_limitation": (
            "three products, four order lines, one model, one operation. No "
            "multi-key joins, many-to-many, nested lookups, currency or units. "
            "Representation covers a COMPUTED output only: decimal places and a "
            "named rounding mode, nothing about money types or localisation. "
            "Says the SHAPE works -- a declared relationship, a declared "
            "computation and a declared representation are all followed -- not "
            "that the model is complete."),
    }


def main(argv: list[str]) -> int:
    result = run_all()
    c = result["arithmetic_canary"]
    print(f"  model valid: {result['model_valid']}   "
          f"vocabulary agrees: {result['vocabulary_parity']['agree']}")
    print(f"  arithmetic canary fired: {c['fired']}   {c['detail']}\n")
    for chk in result["checks"]:
        print(f"  {chk['status']:5} {chk['check']:34} {chk['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"enrichment_run{n}.json").exists():
            n += 1
        path = RESULTS / f"enrichment_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "RELATION_AND_COMPUTATION_FAITHFUL" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
