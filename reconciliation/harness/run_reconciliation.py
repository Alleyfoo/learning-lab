#!/usr/bin/env python3
"""Run the reconciliation task, graded on expectations stated before the run.

Fourth shape: two PEER sources, classifying the union by relationship. The
claims are established the same way as in the earlier tasks -- by permuting the
declaration and requiring the output to follow -- plus two FOILS specific to
this shape.

```text
left_join_foil     what an implementation that walked the left side and looked
                   up the right would emit. dave vanishes. Nothing about the
                   remaining table looks wrong.
intersection_foil  what an implementation that kept only matching keys would
                   emit. bob AND dave vanish.
```

Both foils are computed from the fixtures, not by patching the executor: they
are the plausible wrong answers, and the real output must differ from each.

Usage
-----
    python reconciliation/harness/run_reconciliation.py            # run + record
    python reconciliation/harness/run_reconciliation.py --no-record
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

import reconciliation_model  # noqa: E402
import task_model  # noqa: E402
from execute_reconciliation import (  # noqa: E402
    SUPPORTED_DUPLICATE_POLICIES, SUPPORTED_OUTPUT_ORDERS, UnhonourableModel, execute,
)
from reconciliation_model import validate  # noqa: E402
from task_model import vocabulary_parity  # noqa: E402

RESULTS = BASE / "results"
MODEL_PATH = BASE / "models" / "reconciliation_v1.json"
V2_PATH = BASE / "models" / "reconciliation_v2.json"
V3_PATH = BASE / "models" / "reconciliation_v3.json"

# --- v3: TOLERANCE-BASED NUMERIC COMPARISON ----------------------------------
# Added because the JOB needed it: reconciling balances cannot be done by string
# equality. alice differs by 0.004 (inside a 0.01 tolerance), carol by 0.50.
V3_ROWS = [
    ["alice", "SAME", []],
    ["bob", "ONLY_EXPECTED", []],
    ["carol", "DIFFERENT",
     [{"field": "email", "comparison": "exact",
       "left": "carol@x", "right": "changed@x"},
      {"field": "balance", "comparison": "within",
       "left": "50.00", "right": "50.50",
       "tolerance": "0.01", "delta": "0.50"}]],
    ["dave", "ONLY_ACTUAL", []],
]

# Same data, same field, different declared comparison. alice's balances are
# 100.00 and 100.004: equal under a 0.01 tolerance, unequal as strings.
TOLERANCE_MODE_EXPECTED = {
    "exact": {"alice": "DIFFERENT", "carol": "DIFFERENT"},
    "within": {"alice": "SAME", "carol": "DIFFERENT"},
}

# carol's balance is the string "unknown" in this fixture.
NON_NUMERIC_EXPECTED = {
    "refuse_key": {"n_rows": 3, "run_refused": False, "refused": ["carol"]},
    "refuse_run": {"n_rows": 0, "run_refused": True, "refused": []},
}

# --- v2: DECLARED ATTRIBUTE COMPARISON ---------------------------------------
# v1 reported carol as BOTH while her email had changed. That was correct under
# a model that classifies by key presence -- and useless for the job. The fix is
# a DECLARATION, not a cleverer executor: which attributes are compared, and how.
V2_ROWS = [
    ["alice", "SAME", []],
    ["bob", "ONLY_EXPECTED", []],
    ["carol", "DIFFERENT",
     [{"field": "email", "comparison": "exact",
       "left": "carol@x", "right": "changed@x"}]],
    ["dave", "ONLY_ACTUAL", []],
]

# Same data, same key, different declared COMPARISON. alice's names are `Alice`
# and `ALICE`: identical under casefold, different under exact. This is the
# discriminator for "the executor must not invent normalisation".
COMPARISON_MODE_EXPECTED = {
    "exact": {"alice": "DIFFERENT", "carol": "SAME"},
    "casefold": {"alice": "SAME", "carol": "SAME"},
}

# A compared attribute present on one side and absent on the other.
MISSING_ATTR_DIFF = {"field": "status", "comparison": "exact",
                     "left": "active", "right": None}

# --- baseline, written before the run ---------------------------------------
BASELINE_COLUMNS = ["user_id", "relation"]
BASELINE_ROWS = [
    ["alice", "BOTH"],
    ["bob", "ONLY_EXPECTED"],
    ["carol", "BOTH"],
    ["dave", "ONLY_ACTUAL"],
]

# The plausible wrong answers. NOT expectations -- foils.
LEFT_JOIN_FOIL = [["alice", "BOTH"], ["bob", "ONLY_EXPECTED"], ["carol", "BOTH"]]
INTERSECTION_FOIL = [["alice", "BOTH"], ["carol", "BOTH"]]

# --- permutation: the MATCH KEY ---------------------------------------------
# The fixtures are built so user_id and email partition the union DIFFERENTLY:
# carol matches by id but not email; dave matches bob by email but not id.
# Identical partitions would make this permutation a no-op.
EMAIL_ROWS = [
    ["alice@x", "BOTH"],
    ["bob@x", "BOTH"],
    ["carol@x", "ONLY_EXPECTED"],
    ["changed@x", "ONLY_ACTUAL"],
]

# --- permutation: the declared OUTPUT ORDER ---------------------------------
ORDER_FIXTURES = ("fixtures/expected_order.json", "fixtures/actual_order.json")
ORDER_EXPECTED = {
    "left_then_right": ["zoe", "alice", "bob"],
    "sorted_by_key": ["alice", "bob", "zoe"],
}

# --- permutation: the declared LABELS ----------------------------------------
RELABELLED = "MISSING_FROM_EXPECTED"

# --- duplicate keys, under each declared policy ------------------------------
DUP_EXPECTED = {
    "refuse_run": {"n_rows": 0, "run_refused": True, "refused_keys": []},
    "refuse_key": {"n_rows": 3, "run_refused": False, "refused_keys": ["alice"]},
}


def _model2(mutate=None):
    raw = json.loads(V2_PATH.read_text(encoding="utf-8"))
    if mutate:
        mutate(raw)
    return task_model.parse(raw)


def _model3(mutate=None):
    raw = json.loads(V3_PATH.read_text(encoding="utf-8"))
    if mutate:
        mutate(raw)
    return task_model.parse(raw)


def _model(mutate=None):
    raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if mutate:
        mutate(raw)
    return task_model.parse(raw)


def run_all() -> dict:
    model = _model()
    report = validate(model, BASE)
    parity = vocabulary_parity(
        declared={"output_orders": reconciliation_model.OUTPUT_ORDERS,
                  "duplicate_policies": reconciliation_model.DUPLICATE_POLICIES},
        implemented={"output_orders": SUPPORTED_OUTPUT_ORDERS,
                     "duplicate_policies": SUPPORTED_DUPLICATE_POLICIES})
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str, why: str = "") -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL",
                       "detail": detail, "rationale": why})

    if report.valid:
        base_result = execute(model, BASE)
        record("baseline_union",
               base_result.rows == BASELINE_ROWS
               and base_result.columns == BASELINE_COLUMNS,
               f"{base_result.rows}",
               "the union of two peer sources, each key classified by which "
               "side(s) it appears on")

        # --- FOIL 1: a hidden left join --------------------------------------
        record("right_only_survives",
               ["dave", "ONLY_ACTUAL"] in base_result.rows
               and base_result.rows != LEFT_JOIN_FOIL,
               f"left-join foil would give {LEFT_JOIN_FOIL}",
               "an implementation that walked the LEFT side and looked up the "
               "right would drop dave entirely, and the remaining three rows "
               "would look perfectly reasonable. Neither source is subordinate "
               "here, so a right-only key must survive")

        # --- FOIL 2: intersection only ---------------------------------------
        record("non_matching_keys_survive",
               base_result.rows != INTERSECTION_FOIL
               and len(base_result.rows) == 4,
               f"intersection foil would give {INTERSECTION_FOIL}",
               "keeping only matching keys loses bob AND dave -- the two rows a "
               "reconciliation exists to surface")

        # --- permutation 1: the match key ------------------------------------
        def by_email(d: dict) -> None:
            d["match_on"] = {"left_field": "email", "right_field": "email"}
        emailed = execute(_model(by_email), BASE)
        record("match_follows_declaration", emailed.rows == EMAIL_ROWS,
               f"{emailed.rows}",
               "matching by email partitions the union differently: carol "
               "matches by id but not email, dave matches bob by email but not "
               "id. If the output did not move, the relationship is hardcoded")

        # --- permutation 2: the declared output order ------------------------
        order_detail, order_ok = {}, True
        for order, want in ORDER_EXPECTED.items():
            def set_order(d: dict, o=order) -> None:
                d["sources"]["expected"]["path"] = ORDER_FIXTURES[0]
                d["sources"]["actual"]["path"] = ORDER_FIXTURES[1]
                d["output_order"] = o
            r = execute(_model(set_order), BASE)
            got = [row[0] for row in r.rows]
            order_detail[order] = got
            order_ok = order_ok and got == want
        record("output_order_follows_declaration", order_ok, f"{order_detail}",
               "the union of two sources has no natural order, so it must be "
               "DECLARED. The fixture puts zoe before alice on purpose so the "
               "two orderings genuinely differ")

        # --- permutation 3: the declared labels ------------------------------
        def relabel(d: dict) -> None:
            d["classify"]["only_right"] = RELABELLED
        relabelled = execute(_model(relabel), BASE)
        record("labels_follow_declaration",
               ["dave", RELABELLED] in relabelled.rows,
               f"only_right relabelled -> {relabelled.rows[-1]}",
               "the output labels are the model's words, not the executor's")

        # --- duplicate keys, under each declared policy ----------------------
        dup_detail, dup_ok = {}, True
        for policy, want in DUP_EXPECTED.items():
            def set_dup(d: dict, p=policy) -> None:
                d["sources"]["expected"]["path"] = "fixtures/expected_dup.json"
                d["on_duplicate_key"] = p
            r = execute(_model(set_dup), BASE)
            got = {"n_rows": len(r.rows), "run_refused": r.run_refused is not None,
                   "refused_keys": sorted({x["key"] for x in r.refused})}
            dup_detail[policy] = got
            dup_ok = dup_ok and got == want
        record("duplicate_policy_follows_declaration", dup_ok, f"{dup_detail}",
               "a key appearing twice on one side has no single right answer, so "
               "the model declares it. `deduplicate` and `separate_records` are "
               "deliberately ABSENT -- both silently change what the data says")

        # --- a row with no match key -----------------------------------------
        def no_key(d: dict) -> None:
            d["sources"]["actual"]["path"] = "fixtures/actual_missing_key.json"
        missing = execute(_model(no_key), BASE)
        record("missing_match_key_refuses_run",
               missing.run_refused is not None
               and "MISSING_MATCH_KEY" in missing.run_refused
               and not missing.rows,
               f"run_refused={missing.run_refused!r}",
               "a row cannot be classified by a key it does not carry. Filing it "
               "under the empty string would pool every keyless row into one "
               "phantom key and classify it as though it were real")

        # --- the executor must refuse a model it cannot honour ---------------
        refused_bad = False
        try:
            execute(_model(lambda d: d.update(output_order="whatever_it_built")), BASE)
        except UnhonourableModel:
            refused_bad = True
        record("refuses_unhonourable_model", refused_bad, f"{refused_bad}",
               "an output order the executor does not implement stops the run")

        # --- v2: declared attribute comparison ---------------------------
        v2 = execute(_model2(), BASE)
        record("v2_attribute_comparison", v2.rows == V2_ROWS,
               f"{v2.rows}",
               "v1 reported carol as BOTH while her email had changed -- correct "
               "for a model that classifies by key presence, and useless for the "
               "job. The difference is now named, with the values as WRITTEN")

        # Which fields are compared, and HOW, both come from the model.
        mode_detail, mode_ok = {}, True
        for how, want in COMPARISON_MODE_EXPECTED.items():
            def set_mode(d: dict, h=how) -> None:
                d["compare"] = [{"field": "name", "comparison": h}]
            r = execute(_model2(set_mode), BASE)
            got = {row[0]: row[1] for row in r.rows if row[1] in ("SAME", "DIFFERENT")}
            mode_detail[how] = got
            mode_ok = mode_ok and got == want
        record("comparison_mode_follows_declaration", mode_ok, f"{mode_detail}",
               "alice's names are `Alice` and `ALICE`: identical under casefold, "
               "different under exact. Whether those are the same person's name "
               "is a property of the JOB, and the executor must not decide it")

        # The report must carry the values as written, not as compared.
        exact_name = execute(_model2(
            lambda d: d.update(compare=[{"field": "name", "comparison": "exact"}])), BASE)
        alice_diff = next(r[2] for r in exact_name.rows if r[0] == "alice")
        record("report_carries_original_values",
               alice_diff == [{"field": "name", "comparison": "exact",
                               "left": "Alice", "right": "ALICE"}],
               f"{alice_diff}",
               "a casefold comparison must not make the REPORT say `alice` twice. "
               "PRO-2 instance 9: a predicate may normalise, an emitted value "
               "may not")

        # A compared attribute absent on one side is a difference, not equality.
        status_run = execute(_model2(
            lambda d: d.update(compare=[{"field": "status", "comparison": "exact"}])), BASE)
        alice_status = next(r[2] for r in status_run.rows if r[0] == "alice")
        record("absent_attribute_is_a_difference",
               alice_status == [MISSING_ATTR_DIFF],
               f"{alice_status}",
               "actual's alice carries no status at all. Absent is not equal to "
               "the empty string and must not be silently skipped")

        # --- the classify/compare PAIRING, both directions -------------------
        split_ok = True
        flat_on_v2 = validate(_model2(lambda d: d.update(
            classify={"both": "BOTH", "only_left": "L", "only_right": "R"})), BASE)
        split_on_v1 = validate(_model(lambda d: d.update(
            classify={"both_same": "S", "both_different": "D",
                      "only_left": "L", "only_right": "R"})), BASE)
        split_ok = ("classify_split_mismatch" in flat_on_v2.codes()
                    and "classify_split_mismatch" in split_on_v1.codes())
        record("classify_matches_whether_attributes_are_compared", split_ok,
               f"flat-on-v2={sorted(flat_on_v2.codes())}, "
               f"split-on-v1={sorted(split_on_v1.codes())}",
               "a model that compares attributes and still reports a flat `both` "
               "would hide every difference it went looking for; a model that "
               "compares nothing cannot report SAME vs DIFFERENT. Refused BOTH "
               "ways rather than patched up")

        # --- v3: tolerance-based numeric comparison ------------------------
        v3 = execute(_model3(), BASE)
        record("v3_tolerance_comparison", v3.rows == V3_ROWS,
               f"{v3.rows}",
               "reconciling balances cannot be done by string equality. carol's "
               "difference reports the ORIGINAL values plus the declared "
               "tolerance and the computed delta")

        tol_detail, tol_ok = {}, True
        for how, want in TOLERANCE_MODE_EXPECTED.items():
            def set_cmp(d: dict, h=how) -> None:
                spec = {"field": "balance", "comparison": h}
                if h == "within":
                    spec["tolerance"] = "0.01"
                d["compare"] = [spec]
                if h != "within":
                    d.pop("on_non_numeric", None)
            r = execute(_model3(set_cmp), BASE)
            got = {row[0]: row[1] for row in r.rows if row[1] in ("SAME", "DIFFERENT")}
            tol_detail[how] = got
            tol_ok = tol_ok and got == want
        record("tolerance_follows_declaration", tol_ok, f"{tol_detail}",
               "alice's balances are 100.00 and 100.004: equal within 0.01, "
               "unequal as strings. Whether that gap matters is the JOB's "
               "question, and the tolerance is where it is answered")

        # --- the non-numeric policy, which this task now has a REASON to have -
        nn_detail, nn_ok = {}, True
        for policy, want in NON_NUMERIC_EXPECTED.items():
            def set_nn(d: dict, p=policy) -> None:
                d["sources"]["actual"]["path"] = "fixtures/actual_nonnumeric.json"
                d["on_non_numeric"] = p
            r = execute(_model3(set_nn), BASE)
            got = {"n_rows": len(r.rows), "run_refused": r.run_refused is not None,
                   "refused": sorted({x["key"] for x in r.refused})}
            nn_detail[policy] = got
            nn_ok = nn_ok and got == want
        record("non_numeric_policy_follows_declaration", nn_ok, f"{nn_detail}",
               "carol's balance is the string `unknown`, which no tolerance can "
               "compare. The unit refused is a KEY, not a row -- this task emits "
               "one row per key in the union, so `refuse_row` would name "
               "something that does not exist here")

        # The numeric operands are reported AS WRITTEN, like the string ones.
        nn_run = execute(_model3(lambda d: (
            d["sources"]["actual"].update(path="fixtures/actual_nonnumeric.json"),
            d.update(on_non_numeric="refuse_key"))), BASE)
        carol_refusal = next(x for x in nn_run.refused if x["key"] == "carol")
        record("non_numeric_refusal_names_the_operands",
               carol_refusal["field"] == "balance"
               and carol_refusal["left"] == "50.00"
               and carol_refusal["right"] == "unknown",
               f"{carol_refusal}",
               "a refusal that did not name WHICH field and WHAT values would "
               "leave the reader to guess which of two compared attributes "
               "failed")

    # --- the point of this task, asserted --------------------------------------
    v1raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    v2raw = json.loads(V2_PATH.read_text(encoding="utf-8"))
    v3raw = json.loads(V3_PATH.read_text(encoding="utf-8"))
    policy_presence = {
        "v1 (key presence only)": "on_non_numeric" in v1raw,
        "v2 (string comparison)": "on_non_numeric" in v2raw,
        "v3 (tolerance)": "on_non_numeric" in v3raw,
    }
    record("policy_appears_only_with_numeric_comparison",
           policy_presence == {"v1 (key presence only)": False,
                               "v2 (string comparison)": False,
                               "v3 (tolerance)": True},
           f"{policy_presence}",
           "WITHIN ONE TASK: the non-numeric policy is absent until a numeric "
           "comparison is declared, and required once it is. That is the "
           "cleanest available evidence that the policy tracks numeric "
           "semantics rather than task-hood -- and it is enforced by the model "
           "validator, not merely observed")

    failed = [c for c in checks if c["status"] == "FAIL"]
    if not report.valid:
        outcome = "MODEL_INVALID"
    elif not parity["agree"]:
        outcome = "VOCABULARY_DRIFT"
    elif failed:
        outcome = "TASK_FAILED"
    else:
        outcome = "RECONCILIATION_FAITHFUL"

    return {
        "question": ("can a relationship between two PEER sources be declared by "
                     "the model and faithfully executed, with neither side "
                     "subordinate?"),
        "model_valid": report.valid,
        "model_problems": [str(p) for p in report.problems],
        "vocabulary_parity": parity,
        "foils": {"left_join": LEFT_JOIN_FOIL, "intersection": INTERSECTION_FOIL},
        "checks": checks,
        "outcome": outcome,
        "floor_evidence": (
            "CORRECTED TALLY. Only enrichment and aggregation declare an "
            "on_non_numeric policy -- 2 of 4, not 3. Reservation has none "
            "either: it handles a malformed value as a RULE in its ordered list "
            "(date_well_formed -> INVALID_DATE), not as a policy field. So the "
            "policy appears exactly where NUMERIC COERCION happens and nowhere "
            "else, which is stronger evidence than a 3-of-4 split would have "
            "been: it tracks a property of the task's data, not of task-hood. It "
            "does not belong in the shared envelope."),
        "stated_limitation": (
            "three users a side, one match field at a time, string keys only. No "
            "composite match keys, no fuzzy or normalised matching, no "
            "three-way reconciliation, and no comparison of non-key ATTRIBUTES "
            "(carol's email differs between the sources and this model has no "
            "way to say so -- it classifies by key presence only). Says the "
            "SHAPE works, not that the model is complete."),
    }


def main(argv: list[str]) -> int:
    result = run_all()
    print(f"  model valid: {result['model_valid']}   "
          f"vocabulary agrees: {result['vocabulary_parity']['agree']}\n")
    for chk in result["checks"]:
        print(f"  {chk['status']:5} {chk['check']:36} {chk['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"reconciliation_run{n}.json").exists():
            n += 1
        path = RESULTS / f"reconciliation_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "RECONCILIATION_FAITHFUL" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
