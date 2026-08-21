#!/usr/bin/env python3
"""W1-K PRIMARY MEASURE — the Surface C causal ladder, per row, per run.

**Overall FIDELITY PASS is deliberately not the result.** The question is not
whether more runs are clean; it is whether a *provenance affordance* changes
whether the answers it governs keep their independent evidence identity.

The ladder, per row:

```text
slot offered
   -> slot populated
   -> confirmation exists
   -> confirmation is individually attributable
   -> confirmation is byte-exact
   -> slot points to that confirmation
```

Within-artifact controls, fixed by design:

```text
row 0  match key        existing slot   POSITIVE CONTROL
row 1  compare          existing slot   POSITIVE CONTROL
row 2  currency         no slot         NEGATIVE CONTROL
row 3  source of truth  no slot         NEGATIVE CONTROL
row 4  report fields    NEW slot (arm B only)   TARGET
row 5  context fields   NEW slot (arm B only)   TARGET
```

Row 1 is a **live** positive control, not a formality: it lost its identity in
3 of 3 W1-J runs (`../w1j/CLOSURE.md` 2). If it collapses again here under the
canonical order, the Surface C interpretation is weakened regardless of what
rows 4/5 do.

Read-only. It never edits, repairs or moves an artifact.

    python work_interface/w1k/surface_c_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WI = HERE.parent
sys.path.insert(0, str(WI / "fidelity"))
sys.path.insert(0, str(WI / "w1b" / "harness"))
sys.path.insert(0, str(HERE / "harness"))
import fidelity_check as F  # noqa: E402
import block_harness as B  # noqa: E402
import run_batch as RB  # noqa: E402

EXACT_INDIVIDUAL = "EXACT_INDIVIDUAL"
BUNDLED = "BUNDLED"
NONVERBATIM = "NONVERBATIM"
ABSENT = "ABSENT"

RUNS = RB.ALL_RUNS
ROW_LABEL = {0: "match key", 1: "compare", 2: "currency",
             3: "source of truth", 4: "report fields", 5: "context fields"}
SLOT_CLASS = {0: "existing", 1: "existing", 2: "none", 3: "none",
              4: "new", 5: "new"}
CONTROL_ROLE = {0: "POSITIVE CONTROL", 1: "POSITIVE CONTROL",
                2: "NEGATIVE CONTROL", 3: "NEGATIVE CONTROL",
                4: "TARGET", 5: "TARGET"}


def _confirmations(art: dict) -> dict:
    """id -> confirmation object, for both list and dict shapes."""
    out = {}
    c = art.get("human_confirmations")
    if isinstance(c, list):
        for x in c:
            if isinstance(x, dict) and isinstance(x.get("id"), str):
                out[x["id"]] = x
    elif isinstance(c, dict):
        for k, v in c.items():
            if isinstance(k, str):
                out[k] = v if isinstance(v, dict) else {"answer": v}
    return out


def cited_id(art: dict, row: int) -> tuple[bool, str | None]:
    """(slot populated, cited confirmation id) for the row's provenance slot."""
    body = art.get("body") if isinstance(art.get("body"), dict) else {}
    if row == 0:
        m = body.get("match_on")
        if isinstance(m, dict) and m.get("basis") is not None:
            cid = m.get("confirmation")
            return True, cid if isinstance(cid, str) else None
        return False, None
    if row == 1:
        comp = body.get("compare")
        if isinstance(comp, list):
            for entry in comp:
                if isinstance(entry, dict) and entry.get("basis") is not None:
                    cid = entry.get("confirmation")
                    return True, cid if isinstance(cid, str) else None
        return False, None
    if row in (4, 5):
        out = art.get("output")
        if not isinstance(out, dict):
            return False, None
        prov = out.get("provenance")
        if not isinstance(prov, dict):
            return False, None
        key = "reports_fields" if row == 4 else "context_fields"
        entry = prov.get(key)
        if isinstance(entry, dict) and entry.get("basis") is not None:
            cid = entry.get("confirmation")
            return True, cid if isinstance(cid, str) else None
        return False, None
    return False, None       # rows 2 and 3 have no slot in either arm


def analyse(run: str, canon: dict[int, str]) -> dict:
    d = HERE / "runs" / run
    rec: dict = {"run": run, "arm": RB.arm_of(run), "skill": RB.skill_of(run)}
    art_path = d / "work_definition.json"
    if not art_path.is_file():
        rec["status"] = "NO_ARTIFACT"
        return rec
    try:
        art = json.loads(art_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rec["status"] = "UNPARSEABLE_JSON"
        rec["error"] = f"{type(e).__name__}: {e}"
        return rec

    res = F.check_artifact(art, canon)
    confs = res["confirmations"]
    known = _confirmations(art)

    rows = {}
    for row in sorted(canon):
        carriers = [(cid, v) for cid, v in confs.items()
                    if row in (v.get("rows") or [])]
        if not carriers:
            preservation = ABSENT
        elif any(len(v.get("rows") or []) > 1 for _, v in carriers):
            preservation = BUNDLED
        elif carriers[0][1].get("verdict") != "normal" \
                or carriers[0][1].get("subreason"):
            preservation = NONVERBATIM
        else:
            preservation = EXACT_INDIVIDUAL

        offered = SLOT_CLASS[row] == "existing" or (
            SLOT_CLASS[row] == "new" and rec["arm"] == "treatment")
        populated, cid = cited_id(art, row)
        # binding valid: the cited id exists AND that confirmation carries THIS row
        binding = None
        if populated and cid:
            exists = cid in known
            carries = row in ((confs.get(cid) or {}).get("rows") or [])
            binding = bool(exists and carries)
        rows[row] = {
            "slot_class": SLOT_CLASS[row],
            "role": CONTROL_ROLE[row],
            "slot_offered": offered,
            "preservation": preservation,
            "provenance_populated": populated,
            "cited": cid,
            "binding_valid": binding,
        }
    rec["status"] = "GRADED"
    rec["rows"] = rows
    return rec


def main() -> int:
    tbl = B.load_table_rows(RB.HUMAN_ANSWERS)
    canon = {i: tbl[i][1] for i in B.MANDATED_ROWS}
    records = [analyse(r, canon) for r in RUNS]

    def fmt(v):
        return {True: "yes", False: "no", None: "-"}.get(v, str(v))

    lines = ["# W1-K Surface C results", "",
             "Generated by `work_interface/w1k/surface_c_report.py`. "
             "Read-only.", "",
             "**Primary measure.** Overall FIDELITY PASS is deliberately not "
             "the result.", "",
             "```text",
             "arm A  control    r2  + v0     no output provenance",
             "arm B  treatment  r2c + v0+C   output provenance for rows 4/5",
             "canonical delivery order 0->5 in BOTH arms",
             "```", "",
             "| row | settles | slot class | role |",
             "|---|---|---|---|"]
    for r in sorted(canon):
        lines.append(f"| {r} | {ROW_LABEL[r]} | {SLOT_CLASS[r]} | "
                     f"{CONTROL_ROLE[r]} |")
    lines.append("")

    for rec in records:
        lines += [f"## {rec['run']} — arm {rec['arm']} ({rec['skill']})", ""]
        if rec["status"] != "GRADED":
            lines += [f"- **{rec['status']}**", ""]
            continue
        lines += ["| row | slot class | slot offered | confirmation "
                  "preservation | provenance populated | binding valid |",
                  "|---|---|---|---|---|---|"]
        for row in sorted(rec["rows"]):
            x = rec["rows"][row]
            lines.append(
                f"| {row} ({ROW_LABEL[row]}) | {x['slot_class']} | "
                f"{fmt(x['slot_offered'])} | **{x['preservation']}** | "
                f"{fmt(x['provenance_populated'])} | "
                f"{fmt(x['binding_valid'])} |")
        lines.append("")

    # ---- the ladder, per arm ------------------------------------------------
    lines += ["## The ladder, by arm", ""]
    for arm in ("control", "treatment"):
        rs = [r for r in records if r["arm"] == arm and r["status"] == "GRADED"]
        lines += [f"### {arm}", "", "```text"]
        for label, rowset in (("targets (4,5)", (4, 5)),
                              ("positive controls (0,1)", (0, 1)),
                              ("negative controls (2,3)", (2, 3))):
            offered = sum(1 for r in rs for x in rowset
                          if r["rows"][x]["slot_offered"])
            populated = sum(1 for r in rs for x in rowset
                            if r["rows"][x]["provenance_populated"])
            bound = sum(1 for r in rs for x in rowset
                        if r["rows"][x]["binding_valid"])
            exact = sum(1 for r in rs for x in rowset
                        if r["rows"][x]["preservation"] == EXACT_INDIVIDUAL)
            total = len(rs) * len(rowset)
            lines.append(f"{label:24s} slot offered {offered}/{total}  "
                         f"populated {populated}/{total}  "
                         f"binding valid {bound}/{total}  "
                         f"EXACT_INDIVIDUAL {exact}/{total}")
        lines += ["```", ""]

    lines += ["**Descriptive.** Three runs per arm. No percentages, no "
              "reliability estimate, no statistical inference. The "
              "interpretation branches are fixed in `PREREGISTRATION.md` and "
              "are read off these observations directly.", ""]

    (HERE / "SURFACE_C.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "SURFACE_C.json").write_text(
        json.dumps({"runs": records, "slot_class": SLOT_CLASS,
                    "role": CONTROL_ROLE}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
