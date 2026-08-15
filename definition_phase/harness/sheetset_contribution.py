#!/usr/bin/env python3
"""Cross-sheet law 2 — No Partial Honour at COLLECTION scope.

## The law

The structural analogue of the two-unpivot defect, one level up. `no_partial_
honour` governs declarations within a sheet; this governs members within a
collection:

> Either every declared member of a sheetset contributes its data rows to
> authoritative output AND that contribution is observable, or the recipe is
> refused before authoritative execution. Never a subset silently taking effect.

    A + C must not quietly contribute while B disappears.

**Observability is part of the law, not a nicety.** A member contributing zero
rows is legitimate — a month with no sales yet is a real file. What is not
legitimate is that outcome being *indistinguishable from the member never having
been declared*. Experiment M's S3 is the precedent: it lost half the data and
said nothing, and the finding was the silence rather than the loss.

## The metamorphic shape

```text
baseline:   sheetset over members {A, B, C}      -> rows(A) + rows(B) + rows(C)
mutation:   something that could cause B to drop
required:   refused before execution
        or  B's rows still present, and B's contribution readable from the result
never:      A + C alone, with nothing recording that B contributed nothing
```

No rich oracle: the required output is the union of per-member row sets, which is
set arithmetic rather than a judgement about whether a table "looks right".

## Two evidence types, kept apart

```text
canary      the detector is CAPABLE of firing on a known violation
reachability   the stimulus actually reached the observation point
```

The canary here restores the pre-2026-08-15 executor behaviour — coverage shaped
by the PROTOTYPE rather than per member — and requires the law to fire on the
longer-member case. If it ever passes silently, this suite has stopped testing
anything and the run is void.

## Stated limitation

The corpus was written after an exploratory probe of the same five shapes, so it
explores the shapes its author had already seen behave. That is the same
limitation law 1 carries and is recorded for the same reason: a bucket named
after a known hazard is no guarantee against the next one.

Usage
-----
    python definition_phase/harness/sheetset_contribution.py            # run + record
    python definition_phase/harness/sheetset_contribution.py --no-record
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

import validate_recipe  # noqa: E402
from execute_recipe import execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

RESULTS = LAB / "definition_phase" / "results"
HEADER = ["Tuote"]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _wb(tmp: Path, tag: str, sheets: dict[str, list[list]]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    book = Workbook()
    first = True
    for name, rows in sheets.items():
        ws = book.active if first else book.create_sheet()
        ws.title = name
        first = False
        for row in rows:
            ws.append(row)
    book.save(path)
    return path


def _recipe(members: list[str], proto: str = "A"):
    raw = {
        "recipe_version": 1, "recipe_id": "law2", "workbook": {},
        "sheetsets": {"M": members},
        "sheets": [{
            "sheet": "sheetset:M", "role": "data",
            "layout_from": f"sheet:{proto}",
            "header_row": f"sheet:{proto}!1", "data_region": "remainder",
            "fields": [
                {"target": "tuote", "source": f"sheet:{proto}!@Tuote",
                 "role": "id", "type": "string"},
                {"target": "kausi", "role": "derived", "type": "string",
                 "transform": {"op": "derive", "from": "sheet_name"}},
            ],
            "exclude": [], "ambiguities": [],
        }],
        "applicability": None,
        "provenance": {"proposed_by": "law2", "approved_by": "law2",
                       "approved_recipe_sha256": None},
    }
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _run(members: list[str], sheets: dict, tmp: Path, tag: str) -> dict:
    path = _wb(tmp, tag, sheets)
    wb = WorkbookView(path)
    recipe = _recipe(members)
    report = validate(recipe, wb)
    if not report.valid:
        return {"refused": True, "codes": sorted(report.codes())}
    ex = execute(recipe, wb)
    kausi = ex.columns.index("kausi")
    contributed: dict[str, int] = {}
    for row in ex.rows:
        contributed[row[kausi]] = contributed.get(row[kausi], 0) + 1
    return {"refused": False, "n_rows": len(ex.rows),
            "rows_by_member": contributed,
            # Whatever the executor itself says about member contribution. The
            # law asks for this to exist; it is read here rather than assumed.
            "declared_contribution": _declared_contribution(ex)}


def _declared_contribution(ex) -> Optional[dict]:
    """What the EXECUTION says about which members contributed.

    Read from the result rather than reconstructed from the rows, because
    reconstructing it is exactly what a consumer cannot do: a member with zero
    rows leaves no row to count. If this is None, a zero-contribution member is
    indistinguishable from an undeclared one.
    """
    for attr in ("member_contribution", "members", "contribution"):
        value = getattr(ex, attr, None)
        if isinstance(value, dict) and value:
            return dict(value)
    return None


# ---------------------------------------------------------------------------
# reachability
# ---------------------------------------------------------------------------

def assert_members_distinct(sheets: dict, members: list[str]) -> tuple[bool, str]:
    """Declared members must name DISTINCT sheets that exist.

    Without this a run can spend its time proving that two members pointed at one
    sheet, or that a 'missing' member was never resolvable in the first place --
    law 1 made that mistake three times.
    """
    present = [m for m in members if m in sheets]
    if len(set(present)) != len(present):
        return False, f"members repeat: {members}"
    return True, f"{len(present)}/{len(members)} declared members present in workbook"


# ---------------------------------------------------------------------------
# the corpus -- required outcome stated for each case BEFORE it is run
# ---------------------------------------------------------------------------
# "refused"      validation must refuse before execution
# "full_union"   every present member contributes all of its own rows
# "observable"   a member contributing ZERO rows must still be readable as
#                having been declared and contributed nothing

CASES: list[dict[str, Any]] = [
    {
        "case": "baseline",
        "why": "control: three members, one row each, all present",
        "sheets": {"A": [HEADER, ["a1"]], "B": [HEADER, ["b1"]], "C": [HEADER, ["c1"]]},
        "members": ["A", "B", "C"],
        "required": "full_union",
        "expect_rows": {"A": 1, "B": 1, "C": 1},
    },
    {
        "case": "member_missing_from_workbook",
        "why": "B is declared and absent. The literal 'A + C contribute, B "
               "disappears'. Must refuse rather than union what is present.",
        "sheets": {"A": [HEADER, ["a1"]], "C": [HEADER, ["c1"]]},
        "members": ["A", "B", "C"],
        "required": "refused",
    },
    {
        "case": "member_longer_than_prototype",
        "why": "the hazard per-member coverage exists to prevent: C has three "
               "rows where the prototype has one. A prototype-shaped map drops "
               "C's tail with nothing reporting it.",
        "sheets": {"A": [HEADER, ["a1"]], "B": [HEADER, ["b1"]],
                   "C": [HEADER, ["c1"], ["c2"], ["c3"]]},
        "members": ["A", "B", "C"],
        "required": "full_union",
        "expect_rows": {"A": 1, "B": 1, "C": 3},
    },
    {
        "case": "member_shorter_than_prototype",
        "why": "the other direction: B must contribute its OWN row count, not "
               "the prototype's. Phantom rows are the same defect mirrored.",
        "sheets": {"A": [HEADER, ["a1"], ["a2"], ["a3"]], "B": [HEADER, ["b1"]],
                   "C": [HEADER, ["c1"]]},
        "members": ["A", "B", "C"],
        "required": "full_union",
        "expect_rows": {"A": 3, "B": 1, "C": 1},
    },
    {
        "case": "member_empty",
        "why": "B has a header and no data rows. Contributing zero is "
               "LEGITIMATE -- a month with no sales is a real file -- so the law "
               "does not demand refusal. It demands that the zero be readable, "
               "because otherwise 'B contributed nothing' is indistinguishable "
               "from 'B was never declared'.",
        "sheets": {"A": [HEADER, ["a1"]], "B": [HEADER], "C": [HEADER, ["c1"]]},
        "members": ["A", "B", "C"],
        "required": "observable",
        "expect_rows": {"A": 1, "C": 1},
    },
]


def _verdict(case: dict, result: dict) -> tuple[str, str]:
    required = case["required"]

    if required == "refused":
        if result["refused"]:
            return "HELD", f"refused before execution: {result['codes']}"
        return "VIOLATED", (f"executed with {result['n_rows']} rows "
                            f"{result['rows_by_member']}; a declared member was "
                            f"absent and the rest were unioned anyway")

    if result["refused"]:
        return "NON_EVIDENTIAL", (f"refused for {result['codes']} -- the case "
                                  f"never reached the observation point, so it "
                                  f"says nothing about collection honour")

    got = result["rows_by_member"]
    expected = case["expect_rows"]

    if required == "full_union":
        if got == expected:
            return "HELD", f"every member contributed in full: {got}"
        return "VIOLATED", f"expected {expected}, got {got}"

    if required == "observable":
        if got != expected:
            return "VIOLATED", f"present members wrong: expected {expected}, got {got}"
        declared = result["declared_contribution"]
        if declared is None:
            return "VIOLATED", (
                "the empty member contributed zero rows and the execution "
                "records no per-member contribution, so a declared member that "
                "contributed nothing cannot be told apart from one that was "
                "never declared")
        missing = [m for m in case["members"] if m not in declared]
        if missing:
            return "VIOLATED", (f"execution reports contribution for "
                                f"{sorted(declared)} but not {missing}")
        return "HELD", f"zero contribution recorded: {declared}"

    return "VIOLATED", f"unknown requirement {required!r}"


# ---------------------------------------------------------------------------
# canary -- the pre-fix executor, which must make the law fire
# ---------------------------------------------------------------------------

def canary() -> tuple[bool, bool, str]:
    """Restore prototype-shaped coverage and require the law to fire.

    Returns (fired, reached, detail). `reached` matters as much as `fired`: a
    canary whose stimulus never crosses validation proves nothing about the
    detector, which is the failure that produced the reachability rule.
    """
    original = validate_recipe._coverage_for_data_sheet

    def prototype_shaped(recipe, entry, wb, header_rows0, problems,
                         sheet=None, where=None):
        # The pre-2026-08-15 behaviour: every member gets the PROTOTYPE's map.
        return original(recipe, entry, wb, header_rows0, problems,
                        sheet=None, where=where)

    case = next(c for c in CASES if c["case"] == "member_longer_than_prototype")
    validate_recipe._coverage_for_data_sheet = prototype_shaped
    try:
        with tempfile.TemporaryDirectory() as td:
            result = _run(case["members"], case["sheets"], Path(td), "canary")
    finally:
        validate_recipe._coverage_for_data_sheet = original

    reached = not result["refused"]
    if not reached:
        return False, False, f"stimulus never executed: {result['codes']}"
    status, detail = _verdict(case, result)
    return status == "VIOLATED", True, detail


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run_all() -> dict:
    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for case in CASES:
            ok, detail = assert_members_distinct(case["sheets"], case["members"])
            result = _run(case["members"], case["sheets"], tmp, case["case"])
            status, why = _verdict(case, result)
            results.append({
                "case": case["case"], "required": case["required"],
                "rationale": case["why"], "reachability": detail,
                "reachability_ok": ok, "result": result,
                "status": status, "detail": why,
            })

    fired, reached, canary_detail = canary()
    violations = [r for r in results if r["status"] == "VIOLATED"]
    non_evidential = [r for r in results if r["status"] == "NON_EVIDENTIAL"]

    if not (fired and reached):
        outcome = "VOID"
    elif violations:
        outcome = "LAW_2_VIOLATED"
    elif non_evidential:
        outcome = "INCONCLUSIVE"
    else:
        outcome = "LAW_2_HELD"

    return {
        "law": "No Partial Honour at COLLECTION scope",
        "statement": ("either every declared member contributes its rows AND the "
                      "contribution is observable, or the recipe is refused "
                      "before authoritative execution"),
        "canary": {"fired": fired, "reached": reached, "detail": canary_detail},
        "cases": results,
        "outcome": outcome,
        "stated_limitation": (
            "the corpus was written after an exploratory probe of the same five "
            "shapes; it explores shapes its author had already seen behave"),
    }


def main(argv: list[str]) -> int:
    result = run_all()

    print(f"CANARY  fired={result['canary']['fired']} "
          f"reached={result['canary']['reached']}  {result['canary']['detail']}\n")
    for r in result["cases"]:
        print(f"  {r['status']:15} {r['case']:32} {r['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"sheetset_law2_run{n}.json").exists():
            n += 1
        path = RESULTS / f"sheetset_law2_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] in ("LAW_2_HELD",) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
