#!/usr/bin/env python3
"""Run the aggregation task, graded on expectations stated before the run.

Third shape, first with STATE ACROSS ROWS. As in the two earlier tasks, what
establishes the claim is PERMUTING the declaration and requiring the output to
follow -- a run where declaration and implementation coincide proves nothing.

Two canaries, because there are two ways this shape can be unfaithful:

```text
float_sum            0.10 + 0.20 in float is 0.30000000000000004
shared_accumulator   the hazard NEW to this shape: one accumulator serving
                     every group, producing plausible totals that are the sum
                     of everything
```

Usage
-----
    python aggregation/harness/run_aggregation.py            # run + record
    python aggregation/harness/run_aggregation.py --no-record
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import aggregation_model  # noqa: E402
import task_model  # noqa: E402
from aggregation_model import validate  # noqa: E402
from execute_aggregation import (  # noqa: E402
    SUPPORTED_GROUP_ORDERS, SUPPORTED_OPS, SUPPORTED_POLICIES, UnhonourableModel,
    execute,
)
from task_model import vocabulary_parity  # noqa: E402

RESULTS = BASE / "results"
MODEL_PATH = BASE / "models" / "aggregation_v1.json"

# --- baseline, written before the run ---------------------------------------
# East is refused (quantity "x"), so it forms no group at all -- a group exists
# only if a surviving row contributed to it.
# South: 2 rows, qty 5+1=6, amount 1.00+2.50=3.50
# North: 2 rows, qty 2+3=5, amount 0.10+0.20=0.30   <- the float trap
BASELINE_COLUMNS = ["region", "n_rows", "total_quantity", "total_amount"]
BASELINE_ROWS = [
    ["South", 2, "6", "3.50"],
    ["North", 2, "5", "0.30"],
]

# --- permutation: the GROUPING KEY ------------------------------------------
# P-100 collects rows 1, 2 and 4; P-200 collects row 3.
GROUP_KEY_PERMUTATION = ["product"]
GROUP_KEY_ROWS = [
    ["P-100", 3, "8", "3.60"],
    ["P-200", 1, "3", "0.20"],
]

# --- permutation: the declared GROUP ORDER ----------------------------------
# The fixture puts South before North on purpose, so first-appearance and
# sorted orderings genuinely differ. Identical orderings would make this
# permutation a no-op -- law 4's blindness.
ORDER_EXPECTED = {
    "first_appearance": ["South", "North"],
    "sorted_by_key": ["North", "South"],
}

# --- permutation: the AGGREGATED FIELD --------------------------------------
AGG_FIELD_PERMUTATION = "quantity"          # total_amount now sums quantity
AGG_FIELD_TOTALS = ["6", "5"]

# --- permutation: the non-numeric POLICY ------------------------------------
POLICY_EXPECTED = {
    "refuse_row": {"n_rows": 2, "run_refused": False},
    "refuse_run": {"n_rows": 0, "run_refused": True},
}


def _model(mutate=None):
    raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if mutate:
        mutate(raw)
    return task_model.parse(raw)


def run_all() -> dict:
    model = _model()
    report = validate(model, BASE)
    parity = vocabulary_parity(
        declared={"ops": aggregation_model.OPS,
                  "group_orders": aggregation_model.GROUP_ORDERS,
                  "policies": aggregation_model.POLICIES},
        implemented={"ops": SUPPORTED_OPS,
                     "group_orders": SUPPORTED_GROUP_ORDERS,
                     "policies": SUPPORTED_POLICIES})
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str, why: str = "") -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL",
                       "detail": detail, "rationale": why})

    if report.valid:
        base_result = execute(model, BASE)
        record("baseline_rows",
               base_result.rows == BASELINE_ROWS
               and base_result.columns == BASELINE_COLUMNS,
               f"{base_result.columns} {base_result.rows}",
               "grouping and both aggregate kinds together, including "
               "0.10 + 0.20 = 0.30 which float arithmetic gets wrong")
        record("refused_row_forms_no_group",
               len(base_result.refused) == 1
               and all(r[0] != "East" for r in base_result.rows),
               f"refused={[r['reason'] for r in base_result.refused]}, "
               f"groups={[r[0] for r in base_result.rows]}",
               "the East row is refused BEFORE grouping, so it forms no group; a "
               "group exists only if a surviving row contributed to it")

        # --- permutation 1: the grouping key ---------------------------------
        by_product = execute(_model(lambda d: d.update(group_by=GROUP_KEY_PERMUTATION)), BASE)
        record("grouping_follows_declaration", by_product.rows == GROUP_KEY_ROWS,
               f"{by_product.rows}",
               "changing the declared grouping key must re-partition the rows; an "
               "executor grouping by a hardcoded region would not move")

        # --- permutation 2: the declared group order -------------------------
        order_detail, order_ok = {}, True
        for order, want in ORDER_EXPECTED.items():
            r = execute(_model(lambda d, o=order: d.update(group_order=o)), BASE)
            got = [row[0] for row in r.rows]
            order_detail[order] = got
            order_ok = order_ok and got == want
        record("group_order_follows_declaration", order_ok, f"{order_detail}",
               "the SAME groups in two declared orders. The fixture puts South "
               "before North so the two orderings genuinely differ -- identical "
               "orderings would make this a no-op")

        # --- permutation 3: the aggregated field -----------------------------
        def swap_field(d: dict) -> None:
            d["aggregates"][2]["field"] = AGG_FIELD_PERMUTATION
        swapped = execute(_model(swap_field), BASE)
        totals = [r[-1] for r in swapped.rows]
        record("aggregate_field_follows_declaration", totals == AGG_FIELD_TOTALS,
               f"total_amount now sums {AGG_FIELD_PERMUTATION!r}: {totals}",
               "which field is summed comes from the declaration, not the target "
               "name -- `total_amount` summing quantity is what the model said")

        # --- permutation 4: the non-numeric policy ---------------------------
        policy_detail, policy_ok = {}, True
        for policy, want in POLICY_EXPECTED.items():
            r = execute(_model(lambda d, p=policy: d.update(on_non_numeric=p)), BASE)
            got = {"n_rows": len(r.rows), "run_refused": r.run_refused is not None}
            policy_detail[policy] = got
            policy_ok = policy_ok and got == want
        record("policy_follows_declaration", policy_ok, f"{policy_detail}",
               "refuse_run must deliver NO groups rather than the groups formed "
               "before the bad row was reached")

        # --- the executor must refuse a model it cannot honour ---------------
        refused_bad = False
        try:
            execute(_model(lambda d: d["aggregates"][1].update(op="median")), BASE)
        except UnhonourableModel:
            refused_bad = True
        record("refuses_unhonourable_model", refused_bad, f"{refused_bad}",
               "an op the executor does not implement stops the run")

    # --- CANARIES ------------------------------------------------------------
    canaries: list[dict] = []
    if report.valid:
        # 1. unfaithful arithmetic. The amounts are re-summed in FLOAT to show
        #    what a naive executor would emit; the check is that it differs.
        floaty = execute(model, BASE)
        naive = {}
        for row in json.loads((BASE / "fixtures" / "sales.json").read_text(encoding="utf-8"))["sales"]:
            if row["quantity"] == "x":
                continue
            naive[row["region"]] = naive.get(row["region"], 0.0) + float(row["amount"])
        float_totals = [repr(naive[r[0]]) for r in floaty.rows]
        decimal_totals = [r[-1] for r in floaty.rows]
        canaries.append({
            "name": "float_sum",
            "fired": float_totals != decimal_totals,
            "detail": f"float would give {float_totals}, Decimal gives {decimal_totals}"})

        # 2. the hazard NEW to this shape: one accumulator for every group
        shared: dict = {}
        leaked = execute(model, BASE, accumulator_factory=lambda: shared)
        canaries.append({
            "name": "shared_accumulator",
            "fired": leaked.rows != BASELINE_ROWS,
            "detail": f"one accumulator across groups gives {leaked.rows}"})

    failed = [c for c in checks if c["status"] == "FAIL"]
    all_fired = all(c["fired"] for c in canaries) and len(canaries) == 2

    if not report.valid:
        outcome = "MODEL_INVALID"
    elif not parity["agree"]:
        outcome = "VOCABULARY_DRIFT"
    elif not all_fired:
        outcome = "VOID"
    elif failed:
        outcome = "TASK_FAILED"
    else:
        outcome = "GROUPING_AND_AGGREGATION_FAITHFUL"

    return {
        "question": ("can GROUPING and AGGREGATION ACROSS ROWS be declared by the "
                     "model and faithfully executed?"),
        "model_valid": report.valid,
        "model_problems": [str(p) for p in report.problems],
        "vocabulary_parity": parity,
        "canaries": canaries,
        "checks": checks,
        "outcome": outcome,
        "stated_limitation": (
            "five sale lines, one source, one grouping key at a time, two ops. No "
            "multi-key grouping exercised (the format allows it and the corpus "
            "does not test it), no having/filter, no ordering of ROWS within a "
            "group, no min/max/avg. Says the SHAPE works -- declared grouping and "
            "declared aggregation are both followed, and the accumulator does not "
            "leak -- not that the model is complete."),
    }


def main(argv: list[str]) -> int:
    result = run_all()
    for c in result["canaries"]:
        print(f"  CANARY {c['name']:20} fired={str(c['fired']):5}  {c['detail']}")
    print()
    for chk in result["checks"]:
        print(f"  {chk['status']:5} {chk['check']:36} {chk['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"aggregation_run{n}.json").exists():
            n += 1
        path = RESULTS / f"aggregation_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "GROUPING_AND_AGGREGATION_FAITHFUL" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
