#!/usr/bin/env python3
"""Executor breadth — what `type: number` can and cannot say.

Breadth, not a law: the question is not "does an invariant hold" but **how many
points are there where the format cannot express what the job needs, and how bad
is each one**. That is the shape Experiment L's gap G1 established, and the
useful measurement it named.

## Three outcomes, and only one of them is a finding

```text
HONOURED            the declared type was applied and the value is right
RECORDED            it could NOT be applied, the value passed through, and the
                    executor SAID SO in unhonoured_types
SILENTLY_WRONG      a value was emitted, it is wrong, and nothing recorded it
```

`RECORDED` is a success. Experiment M's S3 is the precedent for why: it lost half
the data and said nothing, and the finding was the silence rather than the loss.
An honest "I cannot honour this" is the system working.

## The ambiguity rule, stated before the run

A single separator followed by **exactly three digits**, with no other separator
present, is genuinely ambiguous:

```text
"1,234"    ->  1234 (US thousands)   or  1.234 (Finnish decimal)
"1.234"    ->  1.234 (US decimal)    or  1234  (Finnish thousands)
```

Nothing in the recipe format carries a locale, so **neither reading is
recoverable from the declaration**. One digit after the separator is not
ambiguous — no thousands group has one digit — so `"1,5"` and `"1.5"` are
decimals and must be honoured.

This is exactly gap G1 (a `date` with no format string) one type over. G1's
standing trap governs here:

> Do not fix it by implementing parsing. It is a result. A declared format string
> is the obvious fix and belongs in its own freeze.

So an ambiguous value must be **RECORDED, never guessed**. Emitting a number is
the violation whichever reading it picks, and the required outcome below says so
regardless of which one the executor happens to choose.

## Scope

`type: number` only, plus a census of the other constructs the handoff listed as
unexercised (`coerce`, multi-measure). Sheetsets became executable on 2026-08-15
and are covered by `semantic_parity` and cross-sheet laws 2-6.

Usage
-----
    python definition_phase/harness/numeric_breadth.py            # run + record
    python definition_phase/harness/numeric_breadth.py --no-record
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

from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

RESULTS = LAB / "definition_phase" / "results"

NBSP = " "
EURO = "€"

# (label, cell value, required outcome, expected value when HONOURED)
#
# "recorded" means: not honoured, passed through as text, AND named in
# unhonoured_types. "honoured" means: the declared type applied and correct.
CASES: list[tuple[str, Any, str, Optional[Any]]] = [
    # --- unambiguous, must be honoured -----------------------------------
    ("native_int",        1234,            "honoured", 1234),
    ("native_float",      12.5,            "honoured", 12.5),
    ("decimal_dot",       "1.5",           "honoured", 1.5),
    ("decimal_comma",     "1,5",           "honoured", 1.5),
    ("negative",          "-42",           "honoured", -42),

    # --- genuinely ambiguous, must be RECORDED and never guessed ---------
    ("sep_comma_3digits", "1,234",         "recorded", None),
    ("sep_dot_3digits",   "1.234",         "recorded", None),

    # --- unsupported notation, must be recorded --------------------------
    ("space_thousands",   "1 234",         "recorded", None),
    ("nbsp_thousands",    f"1{NBSP}234",   "recorded", None),
    ("us_full",           "1,234.56",      "recorded", None),
    ("fi_full",           "1 234,56",      "recorded", None),
    ("currency_prefix",   f"{EURO}1234",   "recorded", None),
    ("currency_suffix",   f"1234 {EURO}",  "recorded", None),
    ("percent",           "15%",           "recorded", None),
    ("accounting_neg",    "(1234)",        "recorded", None),
    ("blank",             "",              "recorded", None),
]


def _wb(tmp: Path, tag: str, rows: list[list]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    book = Workbook()
    ws = book.active
    ws.title = "S"
    for row in rows:
        ws.append(row)
    book.save(path)
    return path


def _recipe(extra_field: Optional[dict] = None, fields: Optional[list] = None):
    raw = {
        "recipe_version": 1, "recipe_id": "breadth", "workbook": {},
        "sheets": [{
            "sheet": "sheet:S", "role": "data", "header_row": "sheet:S!1",
            "data_region": "remainder",
            "fields": fields or [
                {"target": "id", "source": "sheet:S!@Tuote", "role": "id",
                 "type": "string"},
                dict({"target": "v", "source": "sheet:S!@Myynti",
                      "role": "measure", "type": "number"}, **(extra_field or {}))],
            "exclude": [], "ambiguities": []}],
        "applicability": None,
        "provenance": {"proposed_by": "breadth", "approved_by": "breadth",
                       "approved_recipe_sha256": None},
    }
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _classify(emitted: Any, recorded: bool, required: str,
              expected: Optional[Any]) -> tuple[str, str]:
    """HONOURED / RECORDED / SILENTLY_WRONG, against the stated requirement."""
    is_num = isinstance(emitted, (int, float)) and not isinstance(emitted, bool)

    if required == "honoured":
        if is_num and emitted == expected:
            return "HONOURED", f"{emitted!r}"
        if recorded:
            return "RECORDED", (f"could not honour a value that IS expressible "
                                f"({expected!r}); emitted {emitted!r}")
        return "SILENTLY_WRONG", f"expected {expected!r}, emitted {emitted!r}"

    # required == "recorded"
    if is_num:
        # A number came out of something the format cannot pin down. Whether the
        # digits happen to match one reading is irrelevant -- the other reading
        # was equally available and nothing recorded the choice.
        return "SILENTLY_WRONG", (f"emitted the number {emitted!r} from an "
                                  f"unresolvable notation, with nothing recorded")
    if recorded:
        return "RECORDED", f"passed through as {emitted!r}, recorded"
    return "SILENTLY_WRONG", (f"passed through as {emitted!r} and NOT recorded -- "
                              f"a consumer cannot tell this from a string field")


def run_numeric() -> list[dict]:
    out = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for label, value, required, expected in CASES:
            path = _wb(tmp, label, [["Tuote", "Myynti"], [label, value]])
            recipe = _recipe()
            wb = WorkbookView(path)
            report = validate(recipe, wb)
            if not report.valid:
                out.append({"case": label, "required": required,
                            "status": "REFUSED_AT_VALIDATION",
                            "detail": str(sorted(report.codes()))})
                continue
            ex = execute(recipe, wb)
            emitted = ex.rows[0][ex.columns.index("v")]
            recorded = any(g["target"] == "v" for g in ex.unhonoured_types)
            status, detail = _classify(emitted, recorded, required, expected)
            out.append({"case": label, "required": required,
                        "input": repr(value), "emitted": repr(emitted),
                        "recorded_unhonoured": recorded,
                        "status": status, "detail": detail})
    return out


def run_census() -> list[dict]:
    """The other constructs the handoff listed as unexercised."""
    out = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # coerce -- declared by the format, implemented nowhere
        path = _wb(tmp, "coerce", [["Tuote", "Myynti"], ["A", 1]])
        recipe = _recipe(extra_field={"transform": {"op": "coerce", "to": "number"}})
        report = validate(recipe, WorkbookView(path))
        out.append({"construct": "transform:coerce",
                    "status": "REFUSED" if not report.valid else "EXECUTED",
                    "detail": str(sorted(report.codes())) if not report.valid
                              else "executed despite being declared unsupported",
                    "expected": "REFUSED (executor_cannot_honour)"})

        # two measure fields on one sheet
        path = _wb(tmp, "multi", [["Tuote", "Jan", "Feb"], ["A", 1, 2]])
        recipe = _recipe(fields=[
            {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
            {"target": "m1", "source": "sheet:S!@Jan", "role": "measure", "type": "number"},
            {"target": "m2", "source": "sheet:S!@Feb", "role": "measure", "type": "number"}])
        wb = WorkbookView(path)
        report = validate(recipe, wb)
        if report.valid:
            ex = execute(recipe, wb)
            ok = ex.rows == [["A", 1, 2]]
            out.append({"construct": "multi-measure", "status": "HONOURED" if ok else "WRONG",
                        "detail": f"{ex.columns} {ex.rows}",
                        "expected": "HONOURED (two measures are independent columns)"})
        else:
            out.append({"construct": "multi-measure", "status": "REFUSED",
                        "detail": str(sorted(report.codes())),
                        "expected": "HONOURED"})

        # a formula cell whose value was never computed by Excel
        from openpyxl import Workbook

        p = tmp / "formula.xlsx"
        book = Workbook(); ws = book.active; ws.title = "S"
        ws.append(["Tuote", "Myynti"]); ws.append(["A", 5]); ws.append(["B", "=A2*1000"])
        book.save(p)
        wb = WorkbookView(p)
        recipe = _recipe()
        report = validate(recipe, wb)
        if report.valid:
            ex = execute(recipe, wb)
            emitted = ex.rows[1][ex.columns.index("v")]
            recorded = any(g["target"] == "v" for g in ex.unhonoured_types)
            reason = next((g.get("reason", "") for g in ex.unhonoured_types
                           if g["target"] == "v"), "")
            out.append({
                "construct": "formula_without_cached_value",
                "status": "RECORDED" if recorded else "SILENTLY_WRONG",
                "detail": (f"emitted {emitted!r}; reason {reason!r}"),
                "expected": "RECORDED",
                "residual": ("the reason says the value does not parse as a "
                             "number, which is true but not WHY: the cell held a "
                             "formula Excel never evaluated. A consumer cannot "
                             "tell it from a genuinely empty cell.")})
    return out


def run_all() -> dict:
    numeric = run_numeric()
    census = run_census()

    wrong = [r for r in numeric if r["status"] == "SILENTLY_WRONG"]
    census_wrong = [c for c in census if c["status"] not in
                    ("REFUSED", "HONOURED", "RECORDED")]

    if wrong or census_wrong:
        outcome = "BREADTH_SILENT_WRONG"
    else:
        outcome = "BREADTH_HONEST"

    return {
        "measurement": "executor breadth for type:number, plus a construct census",
        "numeric": numeric,
        "census": census,
        "outcome": outcome,
        "counts": {
            "honoured": sum(1 for r in numeric if r["status"] == "HONOURED"),
            "recorded": sum(1 for r in numeric if r["status"] == "RECORDED"),
            "silently_wrong": len(wrong),
        },
        "stated_limitation": (
            "sixteen numeric notations, author-chosen, one cell each. Says "
            "nothing about how often each occurs in real provider files -- that "
            "is the UQ-1 question and is kept separate. `type:number` only; "
            "string, boolean and date are not re-measured here (date is G1)."),
    }


def main(argv: list[str]) -> int:
    result = run_all()
    print("  type:number\n")
    for r in result["numeric"]:
        print(f"  {r['status']:16} {r['case']:20} {r.get('input',''):>16} -> {r['detail']}")
    print("\n  construct census\n")
    for c in result["census"]:
        print(f"  {c['status']:16} {c['construct']:32} {c['detail']}")
    print(f"\n  {result['counts']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"numeric_breadth_run{n}.json").exists():
            n += 1
        path = RESULTS / f"numeric_breadth_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "BREADTH_HONEST" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
