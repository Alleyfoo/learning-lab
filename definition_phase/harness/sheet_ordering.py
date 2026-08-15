#!/usr/bin/env python3
"""Cross-sheet law 4 — Order Is Not Semantics.

## The law

> Permuting the physical order of sheets in a workbook must not change
> authoritative output. What a recipe means is fixed by what it DECLARES, never
> by where a sheet happens to sit in the file.

```text
baseline:   workbook with sheets in order [P, Q, R]   -> O
mutation:   same sheets, same content, order [R, Q, P] -> O'
required:   O == O'
never:      O != O'
```

## The hazard this law is most likely to fail at

**A permutation law passes for free if its fixtures are symmetric under the
permutation.** Three identical sheets can be reordered all day and prove nothing,
because reordering them is a no-op. Law 3 shipped exactly this defect in a
different form — six cases passing while blind to a whole leak path — so here it
is guarded twice:

```text
reachability   the two workbooks must differ in sheet ORDER, and every sheet
               must be pairwise distinguishable by content. Either failing
               makes the permutation a no-op and the case vacuous.
control        permuting the DECLARED member order MUST change the output.
               Without it, a harness whose output is order-blind in both
               directions would pass every invariance case.
```

The control is the sharp one. Output row order follows the recipe's declared
member order, so it is *supposed* to move when the declaration moves. If it does
not, the observation channel cannot see order at all and every invariance result
here is measuring nothing.

## Two canaries, two order-dependence paths

```text
first_sheet_wins     resolution takes wb.sheet_names[0] instead of the named
                     sheet. This is DA-1, a real defect from this repo's own
                     reuse audit: `_read_preview_rows` took
                     `excel.sheet_names[0]` unconditionally.
members_in_file_order  sheetset members expand in WORKBOOK order rather than
                     declared order -- the collection-scope version of the
                     same mistake.
```

Both must fire AND be reached, or the run is VOID.

## Run 1 was VOID, and for the SAME reason law 3 run 1 was

Four of four permutations passed, the control held, `members_in_file_order`
fired — and `first_sheet_wins` did not. Every sheet put `Tuote` at col0, so
resolving against the wrong sheet produced the same column INDEX, and the sheet
identity never crossed into the read.

That is precisely law 3's blindness, recurring one law later in a corpus written
by someone who had just diagnosed it. **The generalisation worth carrying: a
referent defect is only observable where the candidate sheets differ in LAYOUT,
because layout is the only part of a sheet's identity that reaches the read.**
Fixed by giving `Ignored` reversed columns; the canary then fires visibly, and
the swap is the observable:

```text
[['Jan', '1', 'J-1'], …]   ->   [['Jan', 'J-1', 1], …]
```

Usage
-----
    python definition_phase/harness/sheet_ordering.py            # run + record
    python definition_phase/harness/sheet_ordering.py --no-record
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

import execute_recipe  # noqa: E402
import validate_recipe  # noqa: E402
from execute_recipe import execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

RESULTS = LAB / "definition_phase" / "results"

# Every sheet holds DIFFERENT content. Identical sheets would be symmetric under
# permutation, so reordering them would be a no-op and the law would pass without
# testing anything -- the specific way a permutation law fails silently.
#
# `Ignored` additionally carries its columns in the OPPOSITE ORDER. That is not
# decoration: with every sheet putting `Tuote` at col0, a positional resolution
# defect resolves to the same INDEX whichever sheet it lands on, and is
# unobservable. Run 1 of this law was VOID for exactly that reason, and it is the
# same blindness law 3 run 1 had -- only the column index crosses into the read,
# never the sheet identity. A layout difference is what makes the sheet identity
# observable at all.
SHEETS: dict[str, list[list]] = {
    "Jan":     [["Tuote", "Myynti"], ["J-1", 1]],
    "Feb":     [["Tuote", "Myynti"], ["F-1", 2]],
    "Ignored": [["Myynti", "Tuote"], [99, "X-1"]],
}
MEMBERS = ["Jan", "Feb"]


def _wb(tmp: Path, tag: str, order: list[str]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    book = Workbook()
    first = True
    for name in order:
        ws = book.active if first else book.create_sheet()
        ws.title = name
        first = False
        for row in SHEETS[name]:
            ws.append(row)
    book.save(path)
    return path


def _recipe(members: Optional[list[str]] = None):
    """A sheetset over `members` (declared order), plus the ignored sheet.

    The sheetset is what makes this law worth running: a single data entry whose
    member expansion is the place workbook order could leak in.
    """
    members = members or MEMBERS
    raw = {
        "recipe_version": 1, "recipe_id": "law4", "workbook": {},
        "sheetsets": {"M": list(members)},
        "sheets": [
            {"sheet": "sheetset:M", "role": "data",
             "layout_from": f"sheet:{members[0]}",
             "header_row": f"sheet:{members[0]}!1", "data_region": "remainder",
             "fields": [
                 {"target": "tuote", "source": f"sheet:{members[0]}!@Tuote",
                  "role": "id", "type": "string"},
                 {"target": "myynti", "source": f"sheet:{members[0]}!@Myynti",
                  "role": "measure", "type": "number"},
                 {"target": "kausi", "role": "derived", "type": "string",
                  "transform": {"op": "derive", "from": "sheet_name"}}],
             "exclude": [], "ambiguities": []},
            {"sheet": "sheet:Ignored", "role": "ignore", "fields": [],
             "exclude": [], "ambiguities": []},
        ],
        "applicability": None,
        "provenance": {"proposed_by": "law4", "approved_by": "law4",
                       "approved_recipe_sha256": None},
    }
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _outcome(path: Path, members: Optional[list[str]] = None) -> dict:
    wb = WorkbookView(path)
    recipe = _recipe(members)
    report = validate(recipe, wb)
    if not report.valid:
        return {"refused": True, "codes": sorted(report.codes())}
    ex = execute(recipe, wb)
    return {"refused": False, "columns": list(ex.columns),
            "rows": [list(r) for r in ex.rows],
            "member_contribution": dict(ex.member_contribution)}


# ---------------------------------------------------------------------------
# reachability
# ---------------------------------------------------------------------------

def assert_permutation_reached(order_a: list[str],
                               order_b: list[str]) -> tuple[bool, str]:
    """The permutation must be real AND non-vacuous.

    Two conditions, kept apart because they fail differently:

        order differs        otherwise nothing was permuted
        sheets distinct      otherwise permuting them is a no-op even though
                             the order string changed
    """
    if order_a == order_b:
        return False, f"sheet order is IDENTICAL in both workbooks: {order_a}"
    seen: dict[str, str] = {}
    for name in set(order_a) | set(order_b):
        key = json.dumps(SHEETS[name], ensure_ascii=False)
        if key in seen:
            return False, (f"sheets {seen[key]!r} and {name!r} hold identical "
                           f"content, so permuting them is a no-op and this case "
                           f"cannot detect an order dependence")
        seen[key] = name
    return True, f"{order_a} -> {order_b}, all {len(seen)} sheets distinguishable"


# ---------------------------------------------------------------------------
# the corpus
# ---------------------------------------------------------------------------

CASES: list[dict[str, Any]] = [
    {
        "case": "full_reversal",
        "why": "every sheet moves, including the one openpyxl makes active. The "
               "broadest permutation available on this fixture.",
        "order_a": ["Ignored", "Jan", "Feb"],
        "order_b": ["Feb", "Jan", "Ignored"],
        "required": "invariant",
    },
    {
        "case": "members_reversed_in_file",
        "why": "declared member order stays [Jan, Feb] while the FILE holds them "
               "as [Feb, Jan]. The expansion must follow the declaration, not the "
               "file -- output rows in declared order either way.",
        "order_a": ["Jan", "Feb", "Ignored"],
        "order_b": ["Feb", "Jan", "Ignored"],
        "required": "invariant",
    },
    {
        "case": "ignored_first_vs_last",
        "why": "law 3 held the ignored sheet FIRST throughout, so its position "
               "was never varied. A resolver defaulting to the first sheet reads "
               "ignored material in one arrangement and data in the other.",
        "order_a": ["Ignored", "Jan", "Feb"],
        "order_b": ["Jan", "Feb", "Ignored"],
        "required": "invariant",
    },
    {
        "case": "prototype_not_first",
        "why": "the sheetset's layout_from prototype is Jan. Here Jan sits last, "
               "so a prototype taken by position rather than by name resolves to "
               "the wrong sheet.",
        "order_a": ["Jan", "Feb", "Ignored"],
        "order_b": ["Ignored", "Feb", "Jan"],
        "required": "invariant",
    },
    {
        "case": "CONTROL_permute_the_declaration",
        "why": "the other direction. Output row order follows the DECLARED member "
               "order, so permuting the declaration MUST move it. If it does not, "
               "this harness is order-blind and every invariance case above is "
               "measuring nothing.",
        "order_a": ["Jan", "Feb", "Ignored"],
        "order_b": ["Jan", "Feb", "Ignored"],
        "members_a": ["Jan", "Feb"],
        "members_b": ["Feb", "Jan"],
        "required": "must_differ",
    },
]


def _verdict(case: dict, base: dict, mut: dict,
             reached: bool, reach_detail: str) -> tuple[str, str]:
    if case["required"] != "must_differ" and not reached:
        return "NON_EVIDENTIAL", reach_detail
    if base["refused"] or mut["refused"]:
        return "NON_EVIDENTIAL", (
            f"refused before execution (a={base.get('codes')}, "
            f"b={mut.get('codes')}) -- never reached the observation point")

    same = base["rows"] == mut["rows"] and base["columns"] == mut["columns"]

    if case["required"] == "must_differ":
        if same:
            return "CONTROL_FAILED", (
                "permuting the DECLARED member order did not move the output; "
                "this harness cannot see order at all, so every invariance "
                "result in this run is void")
        return "HELD", f"declaration order moved the output: {base['rows']} -> {mut['rows']}"

    if same:
        return "HELD", f"output unchanged under permutation: {base['rows']}"
    return "VIOLATED", f"sheet order changed the output: {base['rows']} -> {mut['rows']}"


# ---------------------------------------------------------------------------
# canaries
# ---------------------------------------------------------------------------

def _canary_first_sheet_wins() -> dict:
    """Resolution takes the workbook's FIRST sheet instead of the named one.

    DA-1 from this repo's own reuse audit: `_read_preview_rows` took
    `excel.sheet_names[0]` unconditionally. Under permutation, the first sheet
    differs, so a leaky resolver reads different material.
    """
    original = execute_recipe.resolve

    def leaky(text, wb, header_rows0=None, **kw):
        result = original(text, wb, header_rows0=header_rows0 or {}, **kw)
        if "!@" not in str(text):
            return result
        first = wb.sheet_names[0]
        name_part = str(text).split("!@", 1)[1]
        alt = original(f"sheet:{first}!@{name_part}", wb,
                       header_rows0={**(header_rows0 or {}), first: 0})
        return alt if alt.ok else result

    case = next(c for c in CASES if c["case"] == "ignored_first_vs_last")
    execute_recipe.resolve = leaky
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            a = _outcome(_wb(tmp, "c1a", case["order_a"]))
            b = _outcome(_wb(tmp, "c1b", case["order_b"]))
    finally:
        execute_recipe.resolve = original

    if a["refused"] or b["refused"]:
        return {"name": "first_sheet_wins", "fired": False, "reached": False,
                "detail": f"never executed: {a.get('codes')} / {b.get('codes')}"}
    fired = a["rows"] != b["rows"]
    return {"name": "first_sheet_wins", "fired": fired, "reached": True,
            "detail": (f"first-sheet resolution made order matter: "
                       f"{a['rows']} -> {b['rows']}" if fired else
                       "first-sheet resolution changed nothing -- this law "
                       "cannot detect a positional resolution defect")}


def _canary_members_in_file_order() -> dict:
    """Sheetset members expand in WORKBOOK order rather than declared order.

    The collection-scope version of the same mistake, and a distinct code path
    from resolution: it reaches the output through member expansion.
    """
    original = validate_recipe._member_sheets

    def by_file_order(recipe, entry, wb, problems):
        members = original(recipe, entry, wb, problems)
        position = {name: i for i, name in enumerate(wb.sheet_names)}
        return sorted(members, key=lambda m: position.get(m, 0))

    case = next(c for c in CASES if c["case"] == "members_reversed_in_file")
    validate_recipe._member_sheets = by_file_order
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            a = _outcome(_wb(tmp, "c2a", case["order_a"]))
            b = _outcome(_wb(tmp, "c2b", case["order_b"]))
    finally:
        validate_recipe._member_sheets = original

    if a["refused"] or b["refused"]:
        return {"name": "members_in_file_order", "fired": False, "reached": False,
                "detail": f"never executed: {a.get('codes')} / {b.get('codes')}"}
    fired = a["rows"] != b["rows"]
    return {"name": "members_in_file_order", "fired": fired, "reached": True,
            "detail": (f"file-order member expansion made order matter: "
                       f"{a['rows']} -> {b['rows']}" if fired else
                       "file-order member expansion changed nothing -- this law "
                       "cannot detect an expansion-order defect")}


def canaries() -> list[dict]:
    return [_canary_first_sheet_wins(), _canary_members_in_file_order()]


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run_all() -> dict:
    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for case in CASES:
            if case["required"] == "must_differ":
                reached, reach_detail = True, "declaration permuted, file fixed"
            else:
                reached, reach_detail = assert_permutation_reached(
                    case["order_a"], case["order_b"])

            a = _outcome(_wb(tmp, f"{case['case']}_a", case["order_a"]),
                         case.get("members_a"))
            b = _outcome(_wb(tmp, f"{case['case']}_b", case["order_b"]),
                         case.get("members_b"))
            status, why = _verdict(case, a, b, reached, reach_detail)
            results.append({
                "case": case["case"], "required": case["required"],
                "rationale": case["why"],
                "order_a": case["order_a"], "order_b": case["order_b"],
                "members_a": case.get("members_a", MEMBERS),
                "members_b": case.get("members_b", MEMBERS),
                "reachability": reach_detail, "reachability_ok": reached,
                "a": a, "b": b, "status": status, "detail": why,
            })

    canary_results = canaries()
    violations = [r for r in results if r["status"] == "VIOLATED"]
    control_failed = [r for r in results if r["status"] == "CONTROL_FAILED"]
    non_evidential = [r for r in results if r["status"] == "NON_EVIDENTIAL"]

    if not all(c["fired"] and c["reached"] for c in canary_results):
        outcome = "VOID"
    elif control_failed:
        outcome = "VOID"
    elif violations:
        outcome = "LAW_4_VIOLATED"
    elif non_evidential:
        outcome = "INCONCLUSIVE"
    else:
        outcome = "LAW_4_HELD"

    return {
        "law": "Order Is Not Semantics",
        "statement": ("permuting the physical order of sheets in a workbook must "
                      "not change authoritative output"),
        "canaries": canary_results,
        "cases": results,
        "outcome": outcome,
        "stated_limitation": (
            "four permutations of a three-sheet workbook, and two registered "
            "order-dependence paths (positional resolution, member expansion). "
            "Three sheets admit six orderings; four are exercised. Sheet order is "
            "permuted, never sheet NAMES -- naming ambiguity is axis 5."),
    }


def main(argv: list[str]) -> int:
    result = run_all()

    for c in result["canaries"]:
        print(f"CANARY {c['name']:24} fired={str(c['fired']):5} "
              f"reached={str(c['reached']):5}  {c['detail']}")
    print()
    for r in result["cases"]:
        print(f"  {r['status']:15} {r['case']:32} {r['detail']}")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        RESULTS.mkdir(exist_ok=True)
        n = 1
        while (RESULTS / f"sheet_ordering_run{n}.json").exists():
            n += 1
        path = RESULTS / f"sheet_ordering_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "LAW_4_HELD" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
