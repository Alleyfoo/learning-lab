#!/usr/bin/env python3
"""Cross-sheet axis 2 — REACHABILITY PROBE, run before the law is written.

Axis 2 is *partial sheetset contribution*: No Partial Honour at COLLECTION scope,
the structural analogue of the two-unpivot defect.

    A + C must not quietly contribute while B disappears.

Before that can be measured, one question has to be answered:

    can the axis-2 stimulus REACH an observation point at all?

## Status

**Reports REACHABLE since 2026-08-15** (`173ab5d`), and law 2 has since been
written and run (`sheetset_contribution.py`). Kept as a standing precondition
check, not as history: if the executor ever loses the ability to union members,
law 2 would start passing vacuously — every case refused, nothing observed — and
this probe is what distinguishes that from the law genuinely holding.

## Why this probe exists rather than the law

`executor_contract.py` used to declare `sheetset` unsupported — "the executor
resolves a single sheet per data entry and cannot union a sheetset, so the recipe
would refuse at execution after validating cleanly" (PRO-2 instance 7). While
that held, a sheetset recipe never produced authoritative output, so "A + C
contributed while B disappeared" had nothing to be observed *in*, and a run would
have reported a refusal that says nothing about partial honour.

That failure has now happened three times in this repo — cross-sheet law 1 run 1
(`duplicate_target`), run 3 (`sheet_unclassified`), and the multiplicity axes
before their generator was repaired. Each was a correct refusal for the wrong
reason: NON-EVIDENTIAL on the axis under test. The harness rule that came out of
it is binding here:

> A stimulus is valid only if the behaviour under test is demonstrated to have
> REACHED the invariant's observation point.

So this module establishes where a sheetset stops, and nothing else. It states no
law and grades no outcome.

## The two observation points, which fail differently

```text
AUTHORITATIVE OUTPUT   execute() -- where partial honour is normally observed
CONTRIBUTION PATHS     cross_sheet.contributions() -- the pre-execution view
```

Both are checked, because they give different answers to "can axis 2 be run":
output is where the law *should* be observed, and contributions is the fallback
if it cannot be. `contributions()` currently skips sheetsets outright
(`cross_sheet.py:109`, "sheetsets: law 2, not this one"), so a blocked executor
plus a skipping collector means axis 2 has no observation point at all — which is
a finding about what must be built first, not a result about partial honour.

## The control carries the weight

A sheetset refusal only means something if the SAME three sheets, declared as
three ordinary `sheet:` entries over the same fixture and fields, do reach
execution. Without that, a refusal could equally be about the fixture, the field
declarations, or the header rows. The control is the repair shape law 1 needed
twice: build a valid representation of the question being asked.

Usage
-----
    python definition_phase/harness/sheetset_reachability.py
    python definition_phase/harness/sheetset_reachability.py --json
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from cross_sheet import _make_wb, contributions  # noqa: E402
from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

MEMBERS = ("2026-01", "2026-02", "2026-03")

# One row per member, so a member silently dropping is visible as a row count.
# Values differ per sheet: identical content across members would make a dropped
# member indistinguishable from a deduplicated one, which is law 1's mistake
# (identity by content) reappearing inside law 2's fixture.
SHEETS = {
    "2026-01": [["Tuote", "Myynti"], ["A", 1]],
    "2026-02": [["Tuote", "Myynti"], ["B", 2]],
    "2026-03": [["Tuote", "Myynti"], ["C", 3]],
}


def _fields(ref: str) -> list[dict]:
    return [{"target": "tuote", "source": f"{ref}!@Tuote", "role": "id",
             "type": "string"},
            {"target": "myynti", "source": f"{ref}!@Myynti", "role": "measure",
             "type": "number"}]


def _recipe(entries: list[dict], sheetsets: dict | None = None) -> dict:
    return {"recipe_version": 1, "recipe_id": "axis2_reach", "workbook": {},
            "sheetsets": sheetsets or {}, "sheets": entries, "applicability": None,
            "provenance": {"proposed_by": "axis2", "approved_by": "axis2",
                           "approved_recipe_sha256": None}}


def _outcome(path: Path, raw: dict) -> dict:
    """Where does this recipe stop, and with what?

    The three stopping points are kept distinct. Collapsing "refused by the
    validator" into "refused by the executor" would hide exactly the thing this
    probe is for: a recipe that validates cleanly and then cannot run is PRO-2's
    signature, not an ordinary refusal.
    """
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    r = recipe_from_json(raw)
    view = WorkbookView(path)

    report = validate(r, view)
    if not report.valid:
        return {"stopped_at": "validation", "codes": sorted(report.codes())}
    try:
        ex = execute(r, view)
    except InsufficientRecipe as exc:
        return {"stopped_at": "execution", "codes": [str(exc)]}
    return {"stopped_at": "none", "columns": list(ex.columns),
            "rows": [list(x) for x in ex.rows], "n_rows": len(ex.rows)}


def probe() -> dict:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_wb(tmp, "months", SHEETS)
        view = WorkbookView(path)

        # --- CONTROL: three ordinary sheet entries over the same fixture ------
        # Distinct targets per entry, because identical targets are refused for
        # duplicate_target -- law 1 run 1's non-evidential outcome.
        control_entries = []
        for i, m in enumerate(MEMBERS):
            ref = f"sheet:{m}"
            flds = [{**f, "target": f"{f['target']}_{i}"} for f in _fields(ref)]
            control_entries.append({"sheet": ref, "role": "data",
                                    "header_row": f"{ref}!1",
                                    "data_region": "remainder", "fields": flds,
                                    "exclude": [], "ambiguities": []})
        control = _outcome(path, _recipe(control_entries))

        # --- STIMULUS: the same three sheets as one sheetset ------------------
        # Fields are addressed against the PROTOTYPE sheet (`layout_from`), not
        # against `sheetset:Months`. The frozen grammar has no member-relative
        # referent and deliberately should not grow one (recipe_format_v1 §3).
        # Writing `sheetset:Months!@Tuote` here produced unresolvable_referent +
        # field_source_kind_mismatch on the first run of this probe — a malformed
        # stimulus that would have been misread as sheetsets being blocked.
        proto = f"sheet:{MEMBERS[0]}"
        stimulus_entry = {"sheet": "sheetset:Months", "role": "data",
                          "layout_from": proto,
                          "header_row": f"{proto}!1",
                          "data_region": "remainder", "fields": _fields(proto),
                          "exclude": [], "ambiguities": []}
        stimulus = _outcome(path, _recipe([stimulus_entry],
                                          sheetsets={"Months": list(MEMBERS)}))

        # --- the second observation point -------------------------------------
        raw = _recipe([stimulus_entry], sheetsets={"Months": list(MEMBERS)})
        r = recipe_from_json(raw)
        contribs = contributions(r, view)
        members_seen = sorted({c.atom.sheet for c in contribs})

    return {
        "members": list(MEMBERS),
        "control": control,
        "stimulus": stimulus,
        "contributions": {"n": len(contribs), "member_sheets_seen": members_seen},
    }


def verdict(result: dict) -> tuple[str, list[str]]:
    """REACHABLE / BLOCKED_* / CONTROL_FAILED, with the reasoning shown."""
    notes: list[str] = []
    control, stim = result["control"], result["stimulus"]

    if control["stopped_at"] != "none":
        return "CONTROL_FAILED", [
            f"three ordinary sheet entries stopped at {control['stopped_at']}: "
            f"{control.get('codes')}",
            "the fixture or the field declarations are wrong, so NOTHING can be "
            "concluded about sheetsets from this run"]
    notes.append(f"control reached output: {control['n_rows']} rows from "
                 f"{len(result['members'])} sheets -- fixture and fields are sound")

    seen = result["contributions"]["member_sheets_seen"]
    notes.append(f"contribution paths see {result['contributions']['n']} atoms "
                 f"across member sheets {seen or '[]'}")

    if stim["stopped_at"] == "none":
        notes.append(f"sheetset reached output: {stim['n_rows']} rows")
        return "REACHABLE", notes

    where = stim["stopped_at"]
    notes.append(f"sheetset stopped at {where}: {stim['codes']}")

    # A refusal only tells us sheetsets are blocked if it is ABOUT sheetsets.
    # Referent or binding errors mean the probe wrote a bad recipe and measured
    # itself -- the exact non-evidential outcome this module exists to prevent,
    # and what the first run of this probe actually did.
    off_axis = [c for c in stim["codes"] if c != "executor_cannot_honour"]
    if off_axis:
        notes.append(f"but the refusal carries off-axis codes {off_axis}: the "
                     f"stimulus is not a valid representation of the question, "
                     f"so this run says NOTHING about sheetset reachability")
        return "STIMULUS_MALFORMED", notes
    if not seen:
        notes.append("and the contribution collector skips sheetsets, so the "
                     "axis-2 question has NO observation point in the current "
                     "system")
        return f"BLOCKED_AT_{where.upper()}_NO_FALLBACK", notes
    notes.append("but contribution paths DO see the members, so axis 2 could be "
                 "observed there instead of at output")
    return f"BLOCKED_AT_{where.upper()}_FALLBACK_AVAILABLE", notes


def main(argv: list[str]) -> int:
    result = probe()
    v, notes = verdict(result)
    result["verdict"] = v
    result["notes"] = notes

    if argv[:1] == ["--json"]:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"AXIS-2 REACHABILITY: {v}\n")
    for n in notes:
        print(f"  - {n}")
    print("\nThis probe states no law and grades no outcome. It answers only "
          "whether\nthe axis-2 stimulus reaches an observation point.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
