#!/usr/bin/env python3
"""Confirmation-preservation census. READ-ONLY.

Reads frozen artifacts and the frozen fidelity instrument. It writes only its
own report, inside this census directory. **It never touches a pack**: no run
directory, artifact, reporter output or closure is read for mutation, and
nothing in `work_interface/w1*` is written.

Corpus: the clean, measured, capability-box runs only.

```text
W1-H  P1 P2 P3          corrected UTF-8 transport
W1-I  U1 U2 U3 V1 V2 V3 corrected UTF-8 transport
```

W1-G is EXCLUDED: its transport is known invalid (cp1252 double-encoding voided
its fidelity layer), so its on-disk artifacts cannot support a preservation
reading. W1-A..W1-F are excluded: no capability box, and no valid measured
fidelity.

For each delivered canonical row 0-5 and each run:

```text
EXACT_INDIVIDUAL  one confirmation carries this row, and only this row
BUNDLED           a confirmation carries this row together with others
NONVERBATIM       a confirmation carries this row but not verbatim
ABSENT            no confirmation carries this row
```

    python work_interface/census/confirmation_preservation/census.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WI = HERE.parent.parent
sys.path.insert(0, str(WI / "fidelity"))
sys.path.insert(0, str(WI / "w1b" / "harness"))
import fidelity_check as F  # noqa: E402
import block_harness as B  # noqa: E402

EXACT_INDIVIDUAL = "EXACT_INDIVIDUAL"
BUNDLED = "BUNDLED"
NONVERBATIM = "NONVERBATIM"
ABSENT = "ABSENT"

# Which pack used which canonical answer table.
CORPUS = [
    ("W1-H", WI / "w1h", WI / "w1a" / "human_answers.md",
     ["P1", "P2", "P3"], {"P1": "r2", "P2": "r2", "P3": "r2"}),
    ("W1-I", WI / "w1i", WI / "w1i" / "fixtures" / "human_answers.md",
     ["U1", "U2", "U3", "V1", "V2", "V3"],
     {"U1": "r2", "U2": "r2", "U3": "r2",
      "V1": "r3", "V2": "r3", "V3": "r3"}),
]

# Does the decision this row settles have a v0 basis/confirmation slot?
# Established by reading the schema, not by inference:
#   _check_basis() is called at exactly two sites in work_definition.py --
#   body.match_on (row 0) and body.compare[<field>] (row 1).
#   `sources.<role>.basis` is "observed", not a human-confirmation slot.
#   The `output` section is validated only for field-declaration consistency
#   and carries no provenance keys at all.
PROVENANCE_SLOT = {
    0: ("YES", "body.match_on.basis + .confirmation"),
    1: ("YES", "body.compare[].basis + .confirmation"),
    2: ("NO", "an exclusion: the decision's effect is a field's ABSENCE from "
              "compare[], and an absence cannot carry a basis"),
    3: ("NO", "no source-of-truth/peer key exists in the v0 shape"),
    4: ("NO", "output.reports_fields has no provenance keys"),
    5: ("NO", "output.context_fields has no provenance keys"),
}

ROW_LABEL = {0: "match key", 1: "compare", 2: "currency / tax band",
             3: "source of truth", 4: "report fields", 5: "context fields"}


def classify_run(artifact: Path, canon: dict[int, str]) -> dict[int, str]:
    obj = json.loads(artifact.read_text(encoding="utf-8"))
    res = F.check_artifact(obj, canon)
    confs = res["confirmations"]

    out: dict[int, str] = {}
    for row in sorted(canon):
        carriers = [(cid, v) for cid, v in confs.items()
                    if row in (v.get("rows") or [])]
        if not carriers:
            out[row] = ABSENT
            continue
        # a bundled carrier is one that also carries other rows
        if any(len(v.get("rows") or []) > 1 for _, v in carriers):
            out[row] = BUNDLED
            continue
        cid, v = carriers[0]
        if v.get("verdict") != "normal" or v.get("subreason"):
            out[row] = NONVERBATIM
            continue
        out[row] = EXACT_INDIVIDUAL
    return out


def main() -> int:
    rows_seen = sorted(B.MANDATED_ROWS)
    table: list[tuple[str, str, str, dict[int, str]]] = []

    for pack, root, answers, runs, revs in CORPUS:
        tbl = B.load_table_rows(answers)
        canon = {i: tbl[i][1] for i in B.MANDATED_ROWS}
        for run in runs:
            art = root / "runs" / run / "work_definition.json"
            if not art.is_file():
                continue
            table.append((pack, run, revs[run], classify_run(art, canon)))

    lines = ["# Confirmation-preservation census", "",
             "**Read-only.** Built from frozen artifacts and the frozen "
             "fidelity instrument. No pack was modified.", "",
             "## Corpus", "",
             "```text",
             "W1-H  P1 P2 P3           corrected UTF-8 transport",
             "W1-I  U1 U2 U3 V1 V2 V3  corrected UTF-8 transport",
             "",
             "EXCLUDED",
             "W1-G       transport known invalid (cp1252 double-encoding "
             "voided its fidelity layer)",
             "W1-A..W1-F no capability box and no valid measured fidelity",
             "```", "",
             "## Provenance surface per row (read from the v0 schema)", "",
             "| row | settles | provenance slot | where |",
             "|---|---|---|---|"]
    for r in rows_seen:
        slot, where = PROVENANCE_SLOT[r]
        lines.append(f"| {r} | {ROW_LABEL[r]} | **{slot}** | {where} |")

    lines += ["", "## Per-run classification", "",
              "| pack | run | rev | "
              + " | ".join(f"row {r}" for r in rows_seen) + " |",
              "|---|---|---|" + "---|" * len(rows_seen)]
    for pack, run, rev, cls in table:
        lines.append(f"| {pack} | {run} | {rev} | "
                     + " | ".join(cls[r] for r in rows_seen) + " |")

    # per-row tallies
    lines += ["", "## Per-row tallies", "",
              "| row | provenance slot | EXACT_INDIVIDUAL | BUNDLED | "
              "NONVERBATIM | ABSENT | not individually preserved |",
              "|---|---|---|---|---|---|---|"]
    tallies = {}
    for r in rows_seen:
        vals = [cls[r] for _, _, _, cls in table]
        t = {k: vals.count(k) for k in
             (EXACT_INDIVIDUAL, BUNDLED, NONVERBATIM, ABSENT)}
        lost = t[BUNDLED] + t[NONVERBATIM] + t[ABSENT]
        tallies[r] = t
        lines.append(
            f"| {r} ({ROW_LABEL[r]}) | {PROVENANCE_SLOT[r][0]} | "
            f"{t[EXACT_INDIVIDUAL]} | {t[BUNDLED]} | {t[NONVERBATIM]} | "
            f"{t[ABSENT]} | **{lost}/{len(table)}** |")

    with_slot = [r for r in rows_seen if PROVENANCE_SLOT[r][0] == "YES"]
    without = [r for r in rows_seen if PROVENANCE_SLOT[r][0] == "NO"]
    lost_with = sum(tallies[r][BUNDLED] + tallies[r][NONVERBATIM]
                    + tallies[r][ABSENT] for r in with_slot)
    lost_without = sum(tallies[r][BUNDLED] + tallies[r][NONVERBATIM]
                       + tallies[r][ABSENT] for r in without)

    lines += ["", "## Concentration", "",
              "```text",
              f"rows WITH a provenance slot     {with_slot}",
              f"  not individually preserved    {lost_with} / "
              f"{len(with_slot) * len(table)} observations",
              f"rows WITHOUT a provenance slot  {without}",
              f"  not individually preserved    {lost_without} / "
              f"{len(without) * len(table)} observations",
              "```", "",
              "**Descriptive only.** This is a census of "
              f"{len(table)} runs, not a statistical test. No causal claim is "
              "drawn from it, and the concentration above is reported as an "
              "observation about where loss occurs, not as evidence of why.",
              ""]

    # ---- the confound this census exists to catch --------------------------
    lossy = [(p, r, v, c) for p, r, v, c in table
             if any(c[x] != EXACT_INDIVIDUAL for x in rows_seen)]
    suffix_runs = []
    for p, r, v, c in lossy:
        lost_rows = [x for x in rows_seen if c[x] != EXACT_INDIVIDUAL]
        contiguous = lost_rows == list(range(min(lost_rows),
                                             max(rows_seen) + 1))
        if contiguous:
            suffix_runs.append((r, min(lost_rows)))

    lines += ["## CONFOUND — order and provenance surface are not separable "
              "here", "",
              "In this corpus the two rows that have a provenance slot are also "
              "**the first two rows delivered**. \"Has a slot\" and \"comes "
              "early\" are therefore perfectly confounded, and the "
              "concentration above supports two readings equally well:", "",
              "```text",
              "A  loss concentrates on rows whose decisions have no place to "
              "cite authority",
              "B  loss is a suffix effect: the worker records the first few "
              "confirmations and stops",
              "```", "",
              f"{len(suffix_runs)} of the {len(lossy)} lossy runs lost a "
              "**contiguous suffix** of the delivered rows:", "",
              "```text"]
    for r, first in suffix_runs:
        lines.append(f"{r:4s} preserved rows 0..{first - 1}, "
                     f"lost {first}..{max(rows_seen)}")
    lines += ["```", "",
              "That is what reading B predicts. Reading A predicts loss on the "
              "slot-less rows **regardless of their position**, which this "
              "corpus cannot show because no slot-less row is ever delivered "
              "early.", "",
              "**Design consequence.** An experiment that only adds provenance "
              "keys to `output` cannot separate A from B: if preservation "
              "improves, it may be the new slot, or it may be that the rows "
              "moved earlier in whatever the worker is truncating. Separating "
              "them needs the delivery ORDER of the canonical rows varied "
              "independently of which rows carry a slot.", ""]

    (HERE / "CENSUS.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "CENSUS.json").write_text(json.dumps(
        {"corpus": [{"pack": p, "run": r, "revision": v,
                     "rows": {str(k): x for k, x in c.items()}}
                    for p, r, v, c in table],
         "provenance_slot": {str(k): v for k, v in PROVENANCE_SLOT.items()},
         "tallies": {str(k): v for k, v in tallies.items()}},
        indent=2), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
