#!/usr/bin/env python3
"""Cross-sheet law 5 — No Authority By Accident.

## The law

> A sheet reference that could denote more than one sheet in the workbook must
> resolve explicitly or be refused. It must never silently pick one.

The last of the five cross-sheet axes, and the one whose defect the previous two
laws already used as a CANARY: laws 3 and 4 both simulate "first matching sheet
wins" to prove their detectors work. Here it stops being the instrument and
becomes the subject.

## What makes a reference ambiguous HERE

Not a design question — a fact about the system's own matching rule:

```python
def actual_sheet(self, name):
    return self._by_key.get(name.casefold())      # referents.py
```

`_by_key` is keyed by `casefold()`, so any two sheet names that casefold to the
same string collapse into ONE dictionary entry. The loser is unreachable and
nothing reports it.

`casefold()` is deliberately more aggressive than `lower()` — that is its purpose
— so the collision does not require a case-only duplicate, which Excel and
openpyxl both refuse to create:

```text
"Straße".casefold()  == "strasse"        both are legal, DISTINCT Excel sheet
"Strasse".casefold() == "strasse"        names, and openpyxl keeps both
```

A German provider file with a `Straße` sheet and a `Strasse` sheet is not exotic.
Under the security frame it is better than that: it is a **file-supplied**
collision, chosen by whoever produced the workbook rather than by the recipe.

## Layout, because that lesson has cost two VOID runs

Laws 3 and 4 each passed a full corpus while blind, both times because the
candidate sheets shared a column layout and only the column INDEX crosses into
the read. So every colliding pair here is given **reversed columns**, and
reachability asserts it:

> a referent defect is only observable where the candidate sheets differ in
> LAYOUT, because layout is the only part of a sheet's identity that reaches
> the read

## Reachability, checked before any verdict

Three conditions, all of which have produced a false clean result somewhere in
this programme:

```text
collision is real     the two names must actually casefold to one key, or
                      there is no ambiguity to adjudicate
both names survive    the workbook writer must have kept both sheets rather
                      than renaming one (openpyxl renames case-only collisions
                      to `NAME1`, which would silently remove the ambiguity)
layouts differ        or which sheet won is unobservable
```

## The control

Distinct, non-colliding names must be ACCEPTED and resolve to their own sheets.
Without it a law that refused every workbook would score a perfect pass.

Usage
-----
    python definition_phase/harness/naming_ambiguity.py            # run + record
    python definition_phase/harness/naming_ambiguity.py --no-record
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from execute_recipe import execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

RESULTS = LAB / "definition_phase" / "results"

# Colliding pairs. Reported through `unicode_escape` rather than printed raw:
# the probe that found this collision crashed on a cp1252 console while the
# logic was sound, and a failure nobody can read is its own hazard.
ESZETT = "Straße"          # casefold -> "strasse"
PLAIN = "Strasse"               # casefold -> "strasse"
LIGATURE = "ﬁle"           # U+FB01 LATIN SMALL LIGATURE FI -> "file"
ASCII_FI = "file"               # casefold -> "file"

# Normal layout vs REVERSED layout, so which sheet won is visible in the output.
NORMAL = [["Tuote", "Myynti"], ["WANTED", 1]]
REVERSED = [["Myynti", "Tuote"], [99, "OTHER"]]


def _wb(tmp: Path, tag: str, sheets: list[tuple[str, list[list]]]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    book = Workbook()
    first = True
    for name, rows in sheets:
        ws = book.active if first else book.create_sheet()
        ws.title = name
        first = False
        for row in rows:
            ws.append(row)
    book.save(path)
    return path


def _recipe(declared: str, ignore: tuple[str, ...] = ()):
    """The recipe under test.

    `ignore` exists only for the CONTROL. Every sheet needs a role, and with
    distinct names the second sheet needs its own entry to say so. The colliding
    cases deliberately do NOT get one: both names casefold to a single key, so
    declaring either spelling marks BOTH sheets covered. That the collision also
    defeats the coverage check is part of the defect, not an accident of setup.
    """
    raw = {
        "recipe_version": 1, "recipe_id": "law5", "workbook": {},
        "sheets": [
            {"sheet": f"sheet:{declared}", "role": "data",
             "header_row": f"sheet:{declared}!1", "data_region": "remainder",
             "fields": [
                 {"target": "tuote", "source": f"sheet:{declared}!@Tuote",
                  "role": "id", "type": "string"},
                 {"target": "myynti", "source": f"sheet:{declared}!@Myynti",
                  "role": "measure", "type": "number"}],
             "exclude": [], "ambiguities": []},
        ] + [{"sheet": f"sheet:{name}", "role": "ignore", "fields": [],
              "exclude": [], "ambiguities": []} for name in ignore],
        "applicability": None,
        "provenance": {"proposed_by": "law5", "approved_by": "law5",
                       "approved_recipe_sha256": None},
    }
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _outcome(path: Path, declared: str, ignore: tuple[str, ...] = ()) -> dict:
    wb = WorkbookView(path)
    recipe = _recipe(declared, ignore)
    report = validate(recipe, wb)
    if not report.valid:
        return {"refused": True, "codes": sorted(report.codes())}
    ex = execute(recipe, wb)
    return {"refused": False, "columns": list(ex.columns),
            "rows": [list(r) for r in ex.rows]}


# ---------------------------------------------------------------------------
# reachability
# ---------------------------------------------------------------------------

def assert_collision_reached(path: Path, a: str, b: str) -> tuple[bool, str]:
    """The ambiguity must be real, present, and observable."""
    if a.casefold() != b.casefold():
        return False, (f"{a!r} and {b!r} do not casefold to one key "
                       f"({a.casefold()!r} vs {b.casefold()!r}) -- no ambiguity "
                       f"to adjudicate")
    view = WorkbookView(path)
    names = list(view.sheet_names)
    if a not in names or b not in names:
        return False, (f"the workbook writer did not keep both names: {names!r} "
                       f"-- the collision was removed before the test saw it")
    rows_a = view.row_values(a, 0)
    rows_b = view.row_values(b, 0)
    if rows_a == rows_b:
        return False, (f"both sheets share the header layout {rows_a!r}, so which "
                       f"one wins is unobservable -- the blindness that made "
                       f"law 3 and law 4 run 1 VOID")
    return True, (f"{a!r} and {b!r} both casefold to {a.casefold()!r}; both "
                  f"present; layouts differ ({rows_a} vs {rows_b})")


# ---------------------------------------------------------------------------
# the corpus
# ---------------------------------------------------------------------------

CASES: list[dict[str, Any]] = [
    {
        "case": "eszett_collision_declare_first",
        "why": "a German provider file with both spellings. The recipe declares "
               "the eszett sheet; casefold collapses it onto the plain one.",
        "sheets": [(ESZETT, NORMAL), (PLAIN, REVERSED)],
        "declared": ESZETT,
        "pair": (ESZETT, PLAIN),
        "required": "refused",
    },
    {
        "case": "eszett_collision_declare_second",
        "why": "the same workbook, declaring the OTHER spelling. If one direction "
               "silently works and the other silently reads the wrong sheet, the "
               "outcome depends on workbook order rather than on the declaration.",
        "sheets": [(ESZETT, NORMAL), (PLAIN, REVERSED)],
        "declared": PLAIN,
        "pair": (ESZETT, PLAIN),
        "required": "refused",
    },
    {
        "case": "ligature_collision",
        "why": "a second collision family, so the finding is about the casefold "
               "RULE rather than about one exotic character. U+FB01 casefolds to "
               "'fi'.",
        "sheets": [(LIGATURE, NORMAL), (ASCII_FI, REVERSED)],
        "declared": LIGATURE,
        "pair": (LIGATURE, ASCII_FI),
        "required": "refused",
    },
    {
        "case": "CONTROL_distinct_names",
        "why": "the other direction. Names that do NOT collide must be accepted "
               "and resolve to their own sheet, or a law that refused every "
               "workbook would score a perfect pass.",
        "sheets": [("Sales", NORMAL), ("Notes", REVERSED)],
        "declared": "Sales",
        "pair": None,
        "required": "accepted",
        "ignore": ("Notes",),
        "expect_rows": [["WANTED", 1]],
    },
]


def _verdict(case: dict, result: dict, reached: bool,
             reach_detail: str) -> tuple[str, str]:
    if case["required"] == "accepted":
        if result["refused"]:
            return "CONTROL_FAILED", (
                f"non-colliding names were refused ({result['codes']}); this law "
                f"cannot tell ambiguity from ordinary resolution, so every "
                f"result in this run is void")
        if result["rows"] != case["expect_rows"]:
            return "CONTROL_FAILED", (f"expected {case['expect_rows']}, "
                                      f"got {result['rows']}")
        return "HELD", f"distinct names accepted and resolved: {result['rows']}"

    if not reached:
        return "NON_EVIDENTIAL", reach_detail

    if result["refused"]:
        return "HELD", f"ambiguous reference refused: {result['codes']}"

    # It executed. WHICH sheet answered is the interesting part.
    got = result["rows"]
    which = "the declared sheet" if got == [["WANTED", 1]] else "the OTHER sheet"
    return "VIOLATED", (f"an ambiguous reference silently resolved to {which} "
                        f"and executed: {got}")


def run_all() -> dict:
    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for case in CASES:
            path = _wb(tmp, case["case"], case["sheets"])
            if case["pair"]:
                reached, reach_detail = assert_collision_reached(
                    path, case["pair"][0], case["pair"][1])
            else:
                reached, reach_detail = True, "control: no collision intended"
            result = _outcome(path, case["declared"],
                              tuple(case.get("ignore", ())))
            status, why = _verdict(case, result, reached, reach_detail)
            results.append({
                "case": case["case"], "required": case["required"],
                "rationale": case["why"],
                "sheets": [n.encode("unicode_escape").decode() for n, _ in case["sheets"]],
                "declared": case["declared"].encode("unicode_escape").decode(),
                "reachability": reach_detail, "reachability_ok": reached,
                "result": result, "status": status, "detail": why,
            })

    violations = [r for r in results if r["status"] == "VIOLATED"]
    control_failed = [r for r in results if r["status"] == "CONTROL_FAILED"]
    non_evidential = [r for r in results if r["status"] == "NON_EVIDENTIAL"]

    if control_failed:
        outcome = "VOID"
    elif violations:
        outcome = "LAW_5_VIOLATED"
    elif non_evidential:
        outcome = "INCONCLUSIVE"
    else:
        outcome = "LAW_5_HELD"

    return {
        "law": "No Authority By Accident",
        "statement": ("a sheet reference that could denote more than one sheet "
                      "must resolve explicitly or be refused, never silently "
                      "pick one"),
        "cases": results,
        "outcome": outcome,
        "note_on_canaries": (
            "laws 3 and 4 register synthetic canaries because their subject is an "
            "invariance that could hold vacuously. Here the subject IS the defect "
            "those canaries simulate, so a VIOLATED case demonstrates the "
            "detector directly. The CONTROL carries the burden a canary carries "
            "elsewhere: it proves the law is not simply refusing everything."),
        "stated_limitation": (
            "two collision families (eszett, ligature), both arising from "
            "casefold(). Collisions from other normalisation the system does not "
            "perform -- Unicode NFC/NFD, trailing whitespace, non-breaking space "
            "-- are NOT ambiguous under the current rule and are not covered. "
            "Sheet NAMES collide here; sheet ORDER is axis 4."),
    }


def main(argv: list[str]) -> int:
    result = run_all()

    for r in result["cases"]:
        print(f"  {r['status']:15} {r['case']:34} {r['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"naming_ambiguity_run{n}.json").exists():
            n += 1
        path = RESULTS / f"naming_ambiguity_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "LAW_5_HELD" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
