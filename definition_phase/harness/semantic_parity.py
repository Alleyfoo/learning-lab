#!/usr/bin/env python3
"""Level three: every accepted declaration has a tested observable meaning.

PRO-2 turned out to be a defect *family*, not a bug:

    producer declares capability -> consumer interprets capability
                                 -> nobody proves they mean the same thing

`executor_contract.py` closed the middle question. It cannot close the last one,
because **agreement on vocabulary is not agreement on semantics.** Both layers can
happily say `period_measure = supported` while one means *every declaration is
transformed* and the other means *one declaration is transformed*. The
completeness assertion goes green and the data still goes sideways — which is
exactly what Experiment M's S3 was.

So the three levels are:

    Level 1  declaration completeness   the format enum lists it
    Level 2  consumption completeness   the contract classifies it and the
                                        dispatcher acts on it
    Level 3  semantic parity            it has an OBSERVABLE INVARIANT,
                                        demonstrated end to end

Running MORE cases against these invariants is not a level four. It is
**evidence depth** -- generated variation around each invariant. Numbering it
would suggest a fourth architectural boundary, and there isn't one: level three
already asks the last structural question. What is missing after it is
confidence, not another kind of check.

    proven here          there is at least one passing demonstration per construct
    NOT proven here      the invariant holds across the construct's input domain

This module is the third. Each supported construct registers an invariant
expressed in terms of the pipeline's observable output, and
`assert_parity_coverage()` fails if a construct is claimed supported without one.

**A construct with no passing parity test may not be listed as supported.** That
is the strengthening: the contract stops being a promise and becomes a
demonstration.

Fixtures are built in a temp directory per run. Nothing here is frozen — these are
tests, and generating them fresh sidesteps the .xlsx non-reproducibility hazard
entirely.
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentK" / "harness"))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from executor_contract import (  # noqa: E402
    SUPPORTED_DERIVE_SOURCES, SUPPORTED_FIELD_ROLES, SUPPORTED_SHEET_REFS,
    SUPPORTED_SHEET_ROLES, SUPPORTED_TRANSFORM_OPS,
)
from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402

# Constructs beyond the enums that also carry observable meaning.
EXTRA_CONSTRUCTS = (
    "exclude:referent", "exclude:rule:label_in", "data_region:remainder",
    "data_row_shape", "reconcile", "type:number", "type:date",
    "composition:role_x_transform",
)


@dataclass
class ParityResult:
    construct: str
    invariant: str
    passed: bool
    detail: str


PARITY: dict[str, tuple[str, Callable]] = {}


def parity(construct: str, invariant: str):
    def deco(fn):
        PARITY[construct] = (invariant, fn)
        return fn
    return deco


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------

def _wb(tmp: Path, name: str, sheets: dict[str, list[list]]) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    first = True
    for title, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title)
        ws.title = title
        first = False
        for row in rows:
            ws.append(row)
    path = tmp / f"{name}.xlsx"
    wb.save(path)
    return path


def _recipe(sheets: list[dict], **kw):
    raw = {"recipe_version": 1, "recipe_id": "parity", "workbook": {},
           "sheets": sheets, "applicability": None,
           "provenance": {"proposed_by": "parity", "approved_by": "parity",
                          "approved_recipe_sha256": None}}
    raw.update(kw)
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _data(sheet, header, region, fields, exclude=(), **kw):
    e = {"sheet": sheet, "role": "data", "header_row": header,
         "data_region": region, "fields": fields, "exclude": list(exclude),
         "ambiguities": []}
    e.update(kw)
    return e


def _run(recipe, path: Path):
    wb = WorkbookView(path)
    report = validate(recipe, wb)
    if not report.valid:
        return report, None
    return report, execute(recipe, wb)


SIMPLE = [["Tuote", "Tammi", "Helmi"], ["A-1", 1, 2], ["A-2", 3, 4]]


# ---------------------------------------------------------------------------
# invariants
# ---------------------------------------------------------------------------

@parity("composition:role_x_transform",
        "a declared transform is EITHER valid for the role it is attached to and "
        "fully honoured, OR the recipe is refused. Every role x transform pair is "
        "checked, not only the pairs observed to fail.")
def _p_composition(tmp):
    """PRO-2 instance 8 as an invariant, over the whole pairing space.

    Patching the seven observed bad combinations would have been patching the
    specimen again; this enumerates all of them.
    """
    from executor_contract import ROLE_TRANSFORM_PAIRS
    from recipe import FIELD_ROLES, TRANSFORM_OPS

    path = _wb(tmp, "composition", {"S": SIMPLE})
    bad: list[str] = []
    for role in FIELD_ROLES:
        for op in (None,) + tuple(TRANSFORM_OPS):
            field = {"target": "probe", "role": role, "type": "string"}
            if role != "derived":
                field["source"] = "sheet:S!@Tuote"
            if op == "unpivot":
                field["transform"] = {"op": "unpivot", "var_target": "kk",
                                      "value_target": "probe"}
            elif op == "derive":
                field["transform"] = {"op": "derive", "from": "sheet_name"}
            elif op is not None:
                field["transform"] = {"op": op}

            r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [field],
                               exclude=[{"referent": "sheet:S!@Tammi", "reason": "c"},
                                        {"referent": "sheet:S!@Helmi", "reason": "c"}])])
            report, ex = _run(r, path)
            legal = op in ROLE_TRANSFORM_PAIRS.get(role, frozenset())

            if not legal:
                if ex is not None:
                    bad.append(f"{role} x {op}: illegal pairing EXECUTED")
                continue
            if ex is None:
                # A legal pairing may still be refused for an unrelated reason
                # (a role needing a source shape this probe does not give it).
                if "executor_cannot_honour" in report.codes():
                    bad.append(f"{role} x {op}: legal pairing refused as unhonourable")
                continue
            declared = {"probe"}
            if op == "unpivot":
                declared = {"kk", "probe"}
            missing = declared - set(ex.columns)
            if missing:
                bad.append(f"{role} x {op}: accepted but {sorted(missing)} missing")
    if bad:
        return False, "; ".join(bad[:4])
    n = len(FIELD_ROLES) * (len(TRANSFORM_OPS) + 1)
    return True, f"all {n} role x transform pairs: honoured in full, or refused"


@parity("transform_op:unpivot",
        "N period columns x M data rows produce exactly N*M output rows, and each "
        "row's var value is the header cell of the column its value came from")
def _p_unpivot(tmp):
    path = _wb(tmp, "unpivot", {"S": SIMPLE})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B:C", "role": "period_measure", "type": "number",
         "transform": {"op": "unpivot", "var_target": "kk", "value_target": "v"}}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    if len(ex.rows) != 4:
        return False, f"2 columns x 2 rows must give 4 output rows, got {len(ex.rows)}"
    kk = ex.columns.index("kk")
    got = {(row[ex.columns.index("id")], row[kk], row[ex.columns.index("v")]) for row in ex.rows}
    want = {("A-1", "Tammi", 1), ("A-1", "Helmi", 2), ("A-2", "Tammi", 3), ("A-2", "Helmi", 4)}
    if got != want:
        return False, f"var/value pairing wrong: {sorted(got)}"
    return True, "4 rows, each var equal to its source column header"


@parity("field_role:period_measure",
        "EVERY accepted period_measure declaration contributes its rows, or "
        "validation refuses the recipe. Never a subset, never silently.")
def _p_period_measure(tmp):
    # This is Experiment M's S3 as an invariant: two declarations must either
    # both be honoured or the recipe must be refused.
    path = _wb(tmp, "two_pm", {"S": [["Tuote", "a1", "a2", "b1", "b2"],
                                     ["A-1", 1, 2, 10, 20]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "a", "source": "sheet:S!B:C", "role": "period_measure", "type": "number",
         "transform": {"op": "unpivot", "var_target": "ka", "value_target": "a"}},
        {"target": "b", "source": "sheet:S!D:E", "role": "period_measure", "type": "number",
         "transform": {"op": "unpivot", "var_target": "kb", "value_target": "b"}}])])
    report, ex = _run(r, path)
    if ex is None:
        return True, ("two declarations refused at validation "
                      f"({sorted(report.codes())}) -- the invariant holds by refusal")
    if len(ex.rows) == 4:
        return True, "both declarations honoured (2 x 2 rows)"
    return False, (f"executed with {len(ex.rows)} rows: a declaration was accepted "
                   "and silently not honoured")


@parity("transform_op:derive",
        "every output row carries the derived value; for from=sheet_name that is "
        "the sheet the row came from")
def _p_derive(tmp):
    path = _wb(tmp, "derive", {"Jan": SIMPLE})
    r = _recipe([_data("sheet:Jan", "sheet:Jan!1", "remainder", [
        {"target": "id", "source": "sheet:Jan!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:Jan!B", "role": "measure", "type": "number"},
        {"target": "kausi", "role": "derived", "type": "string",
         "transform": {"op": "derive", "from": "sheet_name"}}],
        exclude=[{"referent": "sheet:Jan!C", "reason": "not needed"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    col = ex.columns.index("kausi")
    vals = {row[col] for row in ex.rows}
    return (vals == {"Jan"}), f"derived column values {vals}"


@parity("field_role:id",
        "each output row carries the id cell of the source row it came from")
def _p_id(tmp):
    path = _wb(tmp, "id", {"S": SIMPLE})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!C", "reason": "unused"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    ids = [row[ex.columns.index("id")] for row in ex.rows]
    return (ids == ["A-1", "A-2"]), f"ids {ids}"


@parity("field_role:measure",
        "a measure value equals its source cell, coerced by the declared type")
def _p_measure(tmp):
    path = _wb(tmp, "measure", {"S": SIMPLE})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!C", "reason": "unused"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    vals = [row[ex.columns.index("v")] for row in ex.rows]
    return (vals == [1, 3]), f"measure values {vals}"


@parity("field_role:metadata",
        "a metadata scalar is broadcast identically to EVERY output row")
def _p_metadata(tmp):
    path = _wb(tmp, "meta", {"S": [["Raportti", "2026-02"], [], ["Tuote", "Tammi"],
                                   ["A-1", 1], ["A-2", 3]]})
    r = _recipe([_data("sheet:S", "sheet:S!3", "remainder", [
        {"target": "kausi", "source": "sheet:S!B1", "role": "metadata", "type": "string"},
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!1:2", "reason": "preamble"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    col = ex.columns.index("kausi")
    vals = {row[col] for row in ex.rows}
    return (vals == {"2026-02"} and len(ex.rows) == 2), f"broadcast values {vals}, {len(ex.rows)} rows"


@parity("field_role:derived", "a derived field has no source and takes its value "
                              "from its transform")
def _p_derived(tmp):
    return _p_derive(tmp)


@parity("sheet_role:data", "a data sheet contributes output rows")
def _p_sheet_data(tmp):
    path = _wb(tmp, "sdata", {"S": SIMPLE})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!C", "reason": "unused"}])])
    _, ex = _run(r, path)
    return (ex is not None and len(ex.rows) == 2), f"{0 if ex is None else len(ex.rows)} rows"


@parity("sheet_role:ignore",
        "an ignored sheet contributes NOTHING: adding one cannot change the output")
def _p_sheet_ignore(tmp):
    base = _wb(tmp, "ign_a", {"S": SIMPLE})
    both = _wb(tmp, "ign_b", {"S": SIMPLE, "Muu": [["x"], ["y"]]})
    fields = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
              {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}]
    exc = [{"referent": "sheet:S!C", "reason": "unused"}]
    r1 = _recipe([_data("sheet:S", "sheet:S!1", "remainder", fields, exc)])
    r2 = _recipe([_data("sheet:S", "sheet:S!1", "remainder", fields, exc),
                  {"sheet": "sheet:Muu", "role": "ignore", "reason": "not data"}])
    _, a = _run(r1, base)
    _, b = _run(r2, both)
    if a is None or b is None:
        return False, "one of the recipes did not validate"
    return (a.rows == b.rows), f"{len(a.rows)} vs {len(b.rows)} rows"


@parity("exclude:referent",
        "an excluded row's values appear nowhere in the output")
def _p_exclude_ref(tmp):
    path = _wb(tmp, "exc", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["SUMMA", 99]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!3", "reason": "total row"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    flat = {str(v) for row in ex.rows for v in row}
    return ("SUMMA" not in flat and "99" not in flat and len(ex.rows) == 1), \
        f"rows {ex.rows}"


@parity("exclude:rule:label_in",
        "a label rule removes exactly and only the rows whose label it denotes")
def _p_exclude_rule(tmp):
    path = _wb(tmp, "excr", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["SUMMA", 99], ["A-2", 3]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"rule": {"op": "label_in", "column": "sheet:S!@Tuote",
                           "values": ["SUMMA"]}, "reason": "aggregate"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    ids = [row[ex.columns.index("id")] for row in ex.rows]
    return (ids == ["A-1", "A-2"]), f"surviving ids {ids} (exactly and only SUMMA removed)"


@parity("data_region:remainder",
        "the region is whatever the header and exclusions leave, so adding a data "
        "row adds exactly one output row")
def _p_remainder(tmp):
    small = _wb(tmp, "rem_a", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["SUMMA", 9]]})
    big = _wb(tmp, "rem_b", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["A-2", 2], ["SUMMA", 9]]})
    sheets = [_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"rule": {"op": "label_in", "column": "sheet:S!@Tuote",
                           "values": ["SUMMA"]}, "reason": "aggregate"}])]
    _, a = _run(_recipe(sheets), small)
    _, b = _run(_recipe(sheets), big)
    if a is None or b is None:
        return False, "one of the recipes did not validate"
    return (len(b.rows) == len(a.rows) + 1), f"{len(a.rows)} -> {len(b.rows)} rows"


@parity("data_row_shape",
        "a row violating the declared shape causes REFUSAL, never silent inclusion")
def _p_row_shape(tmp):
    path = _wb(tmp, "shape", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["Huom: teksti", None]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        data_row_shape={"require_non_blank": ["sheet:S!@Tuote"],
                        "require_numeric": ["sheet:S!B"]})])
    report, ex = _run(r, path)
    if ex is not None:
        return False, f"executed with {len(ex.rows)} rows instead of refusing"
    return ("row_shape_violation" in report.codes()), f"codes {sorted(report.codes())}"


@parity("reconcile",
        "a sheet whose declared total disagrees with its data rows is REFUSED")
def _p_reconcile(tmp):
    path = _wb(tmp, "rec", {"S": [["Tuote", "Tammi"], ["A-1", 1], ["A-2", 2], ["SUMMA", 99]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"rule": {"op": "label_in", "column": "sheet:S!@Tuote",
                           "values": ["SUMMA"]}, "reason": "aggregate"}],
        reconcile=[{"total_row": {"op": "label_in", "column": "sheet:S!@Tuote",
                                  "values": ["SUMMA"]},
                    "columns": "sheet:S!B", "reason": "total must equal the rows"}])])
    report, ex = _run(r, path)
    if ex is not None:
        return False, f"executed despite 1+2 != 99 ({len(ex.rows)} rows)"
    return ("reconciliation_failure" in report.codes()), f"codes {sorted(report.codes())}"


@parity("type:number",
        "a declared number is either parsed deterministically or recorded as "
        "explicitly unhonoured -- never silently left as text")
def _p_type_number(tmp):
    path = _wb(tmp, "tnum", {"S": [["Tuote", "Tammi"], ["A-1", "1 234"]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder", [
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    value = ex.rows[0][ex.columns.index("v")]
    unhonoured = [t["target"] for t in ex.unhonoured_types]
    if isinstance(value, (int, float)):
        return True, f"parsed to {value}"
    return ("v" in unhonoured), f"left as {value!r}; unhonoured={unhonoured}"


@parity("type:date",
        "a declared date the format cannot describe is recorded as unhonoured "
        "(gap G1), never guessed")
def _p_type_date(tmp):
    path = _wb(tmp, "tdate", {"S": [["Raportti", "3.2.2026"], [], ["Tuote", "Tammi"],
                                    ["A-1", 1]]})
    r = _recipe([_data("sheet:S", "sheet:S!3", "remainder", [
        {"target": "pvm", "source": "sheet:S!B1", "role": "metadata", "type": "date"},
        {"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
        {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}],
        exclude=[{"referent": "sheet:S!1:2", "reason": "preamble"}])])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    gaps = [t for t in ex.unhonoured_types if t["target"] == "pvm"]
    value = ex.rows[0][ex.columns.index("pvm")]
    return (bool(gaps) and value == "3.2.2026"), \
        f"value {value!r}, unhonoured={[g.get('gap') for g in gaps]}"


@parity("sheet_ref:sheet",
        "an ordinary `sheet:` data entry contributes exactly its own data rows, "
        "and nothing from any other sheet in the workbook")
def _p_sheet_ref_sheet(tmp):
    path = _wb(tmp, "one_sheet", {"S": SIMPLE, "Other": [["Tuote"], ["X-9"]]})
    r = _recipe([_data("sheet:S", "sheet:S!1", "remainder",
                       [{"target": "tuote", "source": "sheet:S!@Tuote",
                         "role": "id", "type": "string"}],
                       exclude=[{"referent": "sheet:S!@Tammi", "reason": "c"},
                                {"referent": "sheet:S!@Helmi", "reason": "c"}]),
                 {"sheet": "sheet:Other", "role": "ignore", "fields": [],
                  "exclude": [], "ambiguities": []}])
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"
    got = [row[0] for row in ex.rows]
    return got == ["A-1", "A-2"], f"rows {got}"


@parity("sheet_ref:sheetset",
        "a sheetset UNIONS its members: every member contributes ALL of its own "
        "data rows, and a field derived from sheet_name carries THAT member's "
        "name. Members of differing length are the case that matters -- taking "
        "the prototype's row set would drop a longer member's tail unseen.")
def _p_sheet_ref_sheetset(tmp):
    """The observable meaning of a sheetset, and the axis-2 hazard in one case.

    Member lengths are deliberately 2 / 1 / 3. Equal-length members would pass
    just as well against a prototype-shaped coverage map, so they would
    demonstrate nothing about partial honour at collection scope.
    """
    path = _wb(tmp, "months", {
        "2026-01": [["Tuote", "Myynti"], ["A-1", 1], ["A-2", 2]],
        "2026-02": [["Tuote", "Myynti"], ["B-1", 3]],
        "2026-03": [["Tuote", "Myynti"], ["C-1", 4], ["C-2", 5], ["C-3", 6]],
    })
    entry = _data("sheetset:Months", "sheet:2026-01!1", "remainder",
                  [{"target": "tuote", "source": "sheet:2026-01!@Tuote",
                    "role": "id", "type": "string"},
                   {"target": "myynti", "source": "sheet:2026-01!@Myynti",
                    "role": "measure", "type": "number"},
                   {"target": "kausi", "role": "derived", "type": "string",
                    "transform": {"op": "derive", "from": "sheet_name"}}],
                  layout_from="sheet:2026-01")
    r = _recipe([entry], sheetsets={"Months": ["2026-01", "2026-02", "2026-03"]})
    _, ex = _run(r, path)
    if ex is None:
        return False, "recipe did not validate"

    kausi, tuote = ex.columns.index("kausi"), ex.columns.index("tuote")
    pairs = sorted((row[kausi], row[tuote]) for row in ex.rows)
    expected = sorted([("2026-01", "A-1"), ("2026-01", "A-2"),
                       ("2026-02", "B-1"),
                       ("2026-03", "C-1"), ("2026-03", "C-2"), ("2026-03", "C-3")])
    return pairs == expected, f"{len(ex.rows)} rows, (kausi, tuote) = {pairs}"


# ---------------------------------------------------------------------------
# coverage + run
# ---------------------------------------------------------------------------

def required_constructs() -> set[str]:
    # `sheet_ref` was MISSING from this enumeration until 2026-08-15, which is
    # why PRO-2 instance 7 (a sheetset validating cleanly and failing at
    # execution) had to be found by behaviour rather than by the completeness
    # check that exists to find exactly that. A sheet reference kind is a
    # construct with observable meaning like any other; leaving the dimension out
    # meant nothing demanded a demonstration of what a sheetset MEANS.
    return ({f"transform_op:{op}" for op in SUPPORTED_TRANSFORM_OPS}
            | {f"field_role:{r}" for r in SUPPORTED_FIELD_ROLES}
            | {f"sheet_role:{r}" for r in SUPPORTED_SHEET_ROLES}
            | {f"sheet_ref:{k}" for k in SUPPORTED_SHEET_REFS}
            | set(EXTRA_CONSTRUCTS))


def assert_parity_coverage() -> None:
    """A construct claimed SUPPORTED must have a registered invariant.

    This is the level-three completeness check. Level two asked whether both
    layers know the token; this asks whether anyone has demonstrated they mean
    the same thing by it.
    """
    missing = sorted(required_constructs() - set(PARITY))
    if missing:
        raise RuntimeError(
            "constructs claimed supported with no semantic parity test — their "
            f"meaning is undemonstrated: {missing}")
    stray = sorted(set(PARITY) - required_constructs())
    if stray:
        raise RuntimeError(f"parity tests for constructs nothing claims to support: {stray}")


def run_all() -> list[ParityResult]:
    assert_parity_coverage()
    out: list[ParityResult] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for construct in sorted(PARITY):
            invariant, fn = PARITY[construct]
            try:
                ok, detail = fn(tmp)
            except Exception as exc:  # a construct whose test cannot run is a failure
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            out.append(ParityResult(construct, invariant, ok, detail))
    return out


def _self_test() -> int:
    results = run_all()
    failed = [r for r in results if not r.passed]
    for r in results:
        mark = "ok  " if r.passed else "FAIL"
        sys.stdout.write(f"  {mark} {r.construct:32} {r.detail}\n")
    if failed:
        sys.stderr.write(f"\nSEMANTIC PARITY FAILED for {len(failed)} construct(s)\n")
        return 1
    sys.stdout.write(
        f"\nSEMANTIC PARITY PASSED — {len(results)} supported constructs, each with a "
        "demonstrated observable meaning\n")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--json"]:
        print(json.dumps([r.__dict__ for r in run_all()], ensure_ascii=False, indent=2))
        raise SystemExit(0)
    raise SystemExit(_self_test())
