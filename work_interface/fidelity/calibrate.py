#!/usr/bin/env python3
"""Calibration of the fidelity checker against the frozen expectations.

THIS IS A CALIBRATION, NOT A BLIND WORKER EXPERIMENT. The corpus (W1-B F1/F2/F3)
was already inspected in detail, and the expectations below were hand-derived
from the frozen bytes and written into PREREGISTRATION.md §5 BEFORE
fidelity_check.py existed. This run falsifies the INSTRUMENT, not the workers.
No fidelity claim about `define-lab-process` may be drawn from it.

Pass criterion: the checker reproduces the table exactly. Missed and surplus
findings cost the same.

    python work_interface/fidelity/calibrate.py

No Goose. No model. Read-only with respect to every artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fidelity_check as F  # noqa: E402

W1B_RUNS = HERE.parent / "w1b" / "runs"

# --- frozen expectations, transcribed from PREREGISTRATION.md §5 -----------
EXPECTED_CONFIRMATIONS = {
    ("F1", "Q_compare_amount"):  ((1,),            F.NORMAL, None),
    ("F2", "Q_match_key"):       ((0,),            F.NORMAL, None),
    ("F2", "Q_compare_rule"):    ((1, 2, 3, 4, 5), F.FID_2,  None),
    ("F2", "Q_source_of_truth"): ((3,),            F.FID_6,  "TRUNCATED_PREFIX"),
    ("F3", "Q_match_key"):       ((0,),            F.NORMAL, None),
    ("F3", "Q_compare_policy"):  ((1,),            F.FID_6,  "TRAILING_CONTENT"),
    ("F3", "Q_source_of_truth"): ((3,),            F.NORMAL, None),
    ("F3", "Q_report_fields"):   ((4, 5),          F.FID_2,  None),
}

# (run, finding, where) -- confirmation-level findings are implied by the table
# above and are checked through it, so only slot-level findings are listed here.
EXPECTED_SLOT_FINDINGS = {
    ("F1", F.FID_1, "body.match_on"),
    ("F1", F.FID_5, "human_confirmations", 4),
    ("F1", F.FID_5, "human_confirmations", 5),
    ("F2", F.FID_1, "body.compare[Amount]"),
    ("F3", F.FID_1, "body.compare[Amount]"),
}

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def main() -> int:
    print("=" * 74)
    print("FIDELITY SLICE 1 -- CALIBRATION OF THE INSTRUMENT")
    print("Corpus: W1-B F1/F2/F3, already inspected. Expectations hand-derived")
    print("from the frozen bytes before this checker existed. This falsifies the")
    print("checker, NOT the workers. No worker-quality claim follows from it.")
    print("=" * 74)

    canon = F.canonical_rows()
    got_conf: dict[tuple[str, str], tuple] = {}
    got_slots: set = set()

    for run in ("F1", "F2", "F3"):
        art = json.loads((W1B_RUNS / run / "work_definition.json")
                         .read_text(encoding="utf-8"))
        res = F.check_artifact(art, canon)
        for cid, v in res["confirmations"].items():
            got_conf[(run, cid)] = (tuple(v["rows"]), v["verdict"], v["subreason"])
        for f in res["findings"]:
            if f["finding"] == F.FID_1:
                got_slots.add((run, F.FID_1, f["where"]))
            elif f["finding"] == F.FID_5:
                got_slots.add((run, F.FID_5, f["where"], f["row"]))
            elif f["finding"] == F.FID_4:
                got_slots.add((run, F.FID_4, f["where"], f["row"]))

    print("\n[1] confirmation attribution + classification")
    for key in sorted(set(EXPECTED_CONFIRMATIONS) | set(got_conf)):
        exp = EXPECTED_CONFIRMATIONS.get(key)
        got = got_conf.get(key)
        check(exp == got, f"{key[0]} {key[1]}",
              f"expected={exp} got={got}" if exp != got else str(got))

    print("\n[2] slot-level findings (exact set)")
    missed = EXPECTED_SLOT_FINDINGS - got_slots
    surplus = got_slots - EXPECTED_SLOT_FINDINGS
    for m in sorted(map(str, missed)):
        print(f"  MISSED   {m}")
    for s in sorted(map(str, surplus)):
        print(f"  SURPLUS  {s}")
    check(not missed, "no missed slot-level findings", str(sorted(map(str, missed))))
    check(not surplus, "no surplus slot-level findings", str(sorted(map(str, surplus))))

    print("\n[3] declared invariants of the instrument")
    check(F.attribute("The match key (InvoiceNumber) and the compared field (Amount) "
                      "in report rows.", canon).rows == [4],
          "nesting canary: row 0 does not steal row 4's span")
    check(F.attribute("InvoiceNumber", canon).rows == [0],
          "row 0 still attributes when it stands alone")
    check(F.attribute("Neither — both are peer sources.", canon).rows == [3],
          "strict-prefix partial attribution reaches row 3")
    check(F.attribute("completely unrelated text", canon).rows == [],
          "unrelated text attributes to nothing")
    check(F.classify(canon[1], canon)["verdict"] == F.NORMAL,
          "a byte-exact canonical answer is normal")

    print("\n" + "=" * 74)
    if FAILS:
        print(f"CALIBRATION FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("CALIBRATION PASSED -- the instrument reproduces the frozen table exactly.")
    print("This says nothing about worker fidelity; the corpus was pre-inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
