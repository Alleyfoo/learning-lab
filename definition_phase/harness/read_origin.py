#!/usr/bin/env python3
"""Law 6 — Read Origin Matches Declared Origin.

## The law

> Every cell the executor reads must come from the sheet the referent RESOLVED
> to — or, for a sheetset, from a declared member of the entry whose prototype it
> resolved against. A read from any other origin must be refused, not performed.

## Where this came from, and a correction

Laws 3, 4 and 5 each ended at the same sentence: a referent defect is only
observable where the candidate sheets differ in LAYOUT, because only the column
INDEX crosses into the read. That was recorded as a claim about the resolver
dropping sheet identity.

**That claim was wrong.** `referents.Resolution` carries `sheet` — "the
workbook's ACTUAL spelling" — so the resolver returns origin. The executor
discards it: `resolve()` is called twice in `execute_recipe.py` and `r.sheet` is
never referenced. Reads go to `wb.row_values(member, row0)` indexed by `r.col0`,
so a resolution that landed on the wrong sheet contributes its COLUMN NUMBER to a
read of a different sheet, and nothing objects.

This needs no change to the frozen grammar. It is an executor property.

## Why this law's stimulus must be an induced defect

Unusually for this programme, the cases here cannot be built from input shapes.
With a correct resolver the violation never occurs, so the property under test is
not "what does the system do with this workbook" but:

> does the OUTPUT depend on the resolver being correct, or does the executor
> check?

That is a robustness property about a component boundary, and the only way to
exercise it is to induce the component failure. Stated plainly because it changes
what a pass means: LAW_6_HELD says a resolution defect becomes a REFUSAL rather
than silently wrong data. It says nothing about how likely such a defect is.

Executor rule 1 is what makes this the executor's job rather than the resolver's:

> The executor reads only what the recipe names. If it ever needs a cell no
> referent points at, that is FAIL_INSUFFICIENT — the honest negative answer —
> and it is raised, not worked around.

Reading a cell from a sheet the referent did not name is that rule violated, and
until now nothing enforced it.

## The controls carry the weight

Two, in the direction opposite to the induced defects:

```text
correct_resolution     an ordinary entry must execute unchanged. A check that
                       refused correct recipes would be worse than no check.
sheetset_prototype     a sheetset resolves against the PROTOTYPE and reads from
                       each MEMBER -- the origins legitimately differ, by
                       declaration. A naive "resolved sheet == read sheet"
                       rule would ban sheetsets, which is exactly the wrong fix.
```

Usage
-----
    python definition_phase/harness/read_origin.py            # run + record
    python definition_phase/harness/read_origin.py --no-record
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

import execute_recipe  # noqa: E402
from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

RESULTS = LAB / "definition_phase" / "results"

# DECOY sits first in workbook order and carries REVERSED columns, so a resolver
# that lands on it yields a different col0. Identical layouts would make the
# defect unobservable -- the blindness that made law 3 and law 4 run 1 VOID.
DECOY = "AAA_decoy"
SHEETS: dict[str, list[list]] = {
    DECOY:     [["Myynti", "Tuote"], [99, "DECOY"]],
    "Jan":     [["Tuote", "Myynti"], ["J-1", 1]],
    "Feb":     [["Tuote", "Myynti"], ["F-1", 2]],
}


def _wb(tmp: Path, tag: str, names: list[str]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    book = Workbook()
    first = True
    for name in names:
        ws = book.active if first else book.create_sheet()
        ws.title = name
        first = False
        for row in SHEETS[name]:
            ws.append(row)
    book.save(path)
    return path


def _fields(binding: str) -> list[dict]:
    return [{"target": "tuote", "source": f"sheet:{binding}!@Tuote",
             "role": "id", "type": "string"},
            {"target": "myynti", "source": f"sheet:{binding}!@Myynti",
             "role": "measure", "type": "number"}]


def _recipe_plain():
    """One ordinary data sheet, with the decoy declared as ignored."""
    raw = {
        "recipe_version": 1, "recipe_id": "law6", "workbook": {},
        "sheets": [
            {"sheet": "sheet:Jan", "role": "data", "header_row": "sheet:Jan!1",
             "data_region": "remainder", "fields": _fields("Jan"),
             "exclude": [], "ambiguities": []},
            {"sheet": f"sheet:{DECOY}", "role": "ignore", "fields": [],
             "exclude": [], "ambiguities": []},
            {"sheet": "sheet:Feb", "role": "ignore", "fields": [],
             "exclude": [], "ambiguities": []},
        ],
        "applicability": None,
        "provenance": {"proposed_by": "law6", "approved_by": "law6",
                       "approved_recipe_sha256": None},
    }
    return _finish(raw)


def _recipe_sheetset():
    """A sheetset: bindings resolve against the PROTOTYPE, reads come from each
    MEMBER. The origins differ legitimately, by declaration."""
    raw = {
        "recipe_version": 1, "recipe_id": "law6ss", "workbook": {},
        "sheetsets": {"M": ["Jan", "Feb"]},
        "sheets": [
            {"sheet": "sheetset:M", "role": "data", "layout_from": "sheet:Jan",
             "header_row": "sheet:Jan!1", "data_region": "remainder",
             "fields": _fields("Jan"), "exclude": [], "ambiguities": []},
            {"sheet": f"sheet:{DECOY}", "role": "ignore", "fields": [],
             "exclude": [], "ambiguities": []},
        ],
        "applicability": None,
        "provenance": {"proposed_by": "law6", "approved_by": "law6",
                       "approved_recipe_sha256": None},
    }
    return _finish(raw)


def _finish(raw: dict):
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _outcome(path: Path, recipe) -> dict:
    wb = WorkbookView(path)
    report = validate(recipe, wb)
    if not report.valid:
        return {"refused": True, "at": "validation",
                "codes": sorted(report.codes())}
    try:
        ex = execute(recipe, wb)
    except InsufficientRecipe as exc:
        return {"refused": True, "at": "execution", "codes": [str(exc)]}
    return {"refused": False, "columns": list(ex.columns),
            "rows": [list(r) for r in ex.rows]}


# ---------------------------------------------------------------------------
# induced resolver defects
# ---------------------------------------------------------------------------

def _first_sheet_wins(wb_first: str) -> Callable:
    """Resolve every `@Name` against the workbook's FIRST sheet. DA-1."""
    original = execute_recipe.resolve

    def leaky(text, wb, header_rows0=None, **kw):
        result = original(text, wb, header_rows0=header_rows0 or {}, **kw)
        if "!@" not in str(text):
            return result
        first = wb.sheet_names[0]
        alt = original(f"sheet:{first}!@{str(text).split('!@', 1)[1]}", wb,
                       header_rows0={**(header_rows0 or {}), first: 0})
        return alt if alt.ok else result
    return leaky


def _foreign_sheet(target: str) -> Callable:
    """Resolve every `@Name` against one named sheet, whatever was asked for."""
    original = execute_recipe.resolve

    def leaky(text, wb, header_rows0=None, **kw):
        result = original(text, wb, header_rows0=header_rows0 or {}, **kw)
        if "!@" not in str(text):
            return result
        alt = original(f"sheet:{target}!@{str(text).split('!@', 1)[1]}", wb,
                       header_rows0={**(header_rows0 or {}), target: 0})
        return alt if alt.ok else result
    return leaky


# ---------------------------------------------------------------------------
# the corpus -- required outcome stated before the run
# ---------------------------------------------------------------------------

CASES: list[dict[str, Any]] = [
    {
        "case": "CONTROL_correct_resolution",
        "why": "an ordinary entry under a correct resolver must execute "
               "unchanged. A check that refused correct recipes would be worse "
               "than no check at all.",
        "recipe": "plain", "patch": None,
        "required": "executes", "expect_rows": [["J-1", 1]],
    },
    {
        "case": "CONTROL_sheetset_prototype",
        "why": "a sheetset resolves against the PROTOTYPE and reads from each "
               "MEMBER, so resolved origin and read origin legitimately differ. A "
               "naive 'resolved sheet == read sheet' rule would ban sheetsets, "
               "which is the wrong fix rather than a stricter one.",
        "recipe": "sheetset", "patch": None,
        "required": "executes", "expect_rows": [["J-1", 1], ["F-1", 2]],
    },
    {
        "case": "first_sheet_wins_resolver",
        "why": "DA-1 from this repo's reuse audit, induced. Resolution lands on "
               "the decoy sheet and contributes ITS column numbers to a read of "
               "Jan. The executor must refuse rather than emit the wrong columns.",
        "recipe": "plain", "patch": "first_sheet",
        "required": "refused",
    },
    {
        "case": "foreign_sheet_resolver",
        "why": "resolution lands on a sheet that is neither the declared one nor "
               "any member. The broadest form of the same defect.",
        "recipe": "plain", "patch": "foreign",
        "required": "refused",
    },
    {
        "case": "foreign_sheet_resolver_on_sheetset",
        "why": "the same induced defect against a sheetset, so the fix cannot be "
               "'trust anything whose entry is a sheetset'. The prototype is "
               "declared; the decoy is not.",
        "recipe": "sheetset", "patch": "foreign",
        "required": "refused",
    },
]


def _verdict(case: dict, result: dict) -> tuple[str, str]:
    if case["required"] == "executes":
        if result["refused"]:
            return "CONTROL_FAILED", (
                f"a correct recipe was refused at {result['at']}: "
                f"{result['codes']}. A check that rejects valid work is not a "
                f"stricter law, it is a broken one.")
        if result["rows"] != case["expect_rows"]:
            return "CONTROL_FAILED", (f"expected {case['expect_rows']}, "
                                      f"got {result['rows']}")
        return "HELD", f"executed correctly: {result['rows']}"

    if result["refused"]:
        return "HELD", f"refused at {result['at']}: {result['codes']}"
    return "VIOLATED", (f"a read from an undeclared origin was PERFORMED, not "
                        f"refused: {result['rows']}")


def run_all() -> dict:
    results = []
    original = execute_recipe.resolve
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        order = [DECOY, "Jan", "Feb"]
        path = _wb(tmp, "law6", order)

        for case in CASES:
            recipe = _recipe_plain() if case["recipe"] == "plain" else _recipe_sheetset()
            if case["patch"] == "first_sheet":
                execute_recipe.resolve = _first_sheet_wins(DECOY)
            elif case["patch"] == "foreign":
                execute_recipe.resolve = _foreign_sheet(DECOY)
            try:
                result = _outcome(path, recipe)
            finally:
                execute_recipe.resolve = original

            status, why = _verdict(case, result)
            results.append({
                "case": case["case"], "required": case["required"],
                "rationale": case["why"], "recipe": case["recipe"],
                "induced_defect": case["patch"], "workbook_order": order,
                "result": result, "status": status, "detail": why,
            })

    violations = [r for r in results if r["status"] == "VIOLATED"]
    control_failed = [r for r in results if r["status"] == "CONTROL_FAILED"]

    if control_failed:
        outcome = "VOID"
    elif violations:
        outcome = "LAW_6_VIOLATED"
    else:
        outcome = "LAW_6_HELD"

    return {
        "law": "Read Origin Matches Declared Origin",
        "statement": ("every cell read must come from the sheet the referent "
                      "resolved to, or from a declared member of the entry whose "
                      "prototype it resolved against"),
        "cases": results,
        "outcome": outcome,
        "note_on_method": (
            "the stimulus is necessarily an INDUCED resolver defect: with a "
            "correct resolver the violation cannot occur, so the property under "
            "test is whether the output depends on the resolver being right. "
            "LAW_6_HELD means a resolution defect becomes a refusal rather than "
            "silently wrong data; it says nothing about how likely one is."),
        "stated_limitation": (
            "two induced defect shapes (first-sheet-wins, fixed-foreign-sheet), "
            "both landing on a sheet with a REVERSED layout so the defect is "
            "observable. A defect landing on a same-layout sheet would produce "
            "identical output and is indistinguishable from correct operation by "
            "output alone -- which is the argument for checking origin rather "
            "than comparing results."),
    }


def main(argv: list[str]) -> int:
    result = run_all()
    for r in result["cases"]:
        print(f"  {r['status']:15} {r['case']:36} {r['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"read_origin_run{n}.json").exists():
            n += 1
        path = RESULTS / f"read_origin_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "LAW_6_HELD" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
