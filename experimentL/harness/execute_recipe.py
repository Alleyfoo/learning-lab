#!/usr/bin/env python3
"""Execute a validated, approved recipe. Deterministic — no model, ever.

This is the step the architecture has been protecting for four experiments and
had never run. It answers the designer's question directly: **is a recipe
sufficient to do the job?**

Two hard rules, both from the freeze:

1. **The executor reads only what the recipe names.** If it ever needs a cell no
   referent points at, that is `FAIL_INSUFFICIENT` — the honest negative answer
   — and it is raised, not worked around.
2. **Nothing is guessed.** A declaration the format cannot support (a `date` with
   no format string) leaves the value as-is and is *recorded* as an unhonoured
   type. Guessing `dd.mm.yyyy` would hide the finding.

The output column order is the recipe's field order, with the unpivot's
`var_target` / `value_target` taking the place of the `period_measure` field.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
sys.path.insert(0, str(LAB / "definition_phase" / "harness"))
sys.path.insert(0, str(LAB / "experimentJ" / "harness"))

from executor_contract import normalize_for  # noqa: E402
from macro_v2 import is_number  # noqa: E402
from recipe import Recipe, SheetEntry, load_recipe  # noqa: E402
from referents import WorkbookView, parse, resolve  # noqa: E402
from validate_recipe import validate  # noqa: E402


class InsufficientRecipe(Exception):
    """The executor needs information the recipe does not carry."""


@dataclass
class Execution:
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list[Any]] = dc_field(default_factory=list)
    unhonoured_types: list[dict] = dc_field(default_factory=list)
    notes: list[str] = dc_field(default_factory=list)

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows,
                "unhonoured_types": self.unhonoured_types, "notes": self.notes}


def _coerce(value: Any, declared: Optional[str], target: str,
            unhonoured: list[dict]) -> Any:
    """Apply a declared type, or record that it could not be applied.

    Normalisation is DECLARED per construct (PRO-2 instance 9). A declared
    `string` authorises representation as text and nothing else, so `text` is
    preserved; `number` and `boolean` trim because their own declaration
    authorises it.
    """
    if value is None:
        return ""
    text = normalize_for("field_value", str(value))
    if declared in (None, "string"):
        return text
    if declared == "number":
        numeric = normalize_for("numeric_parse", text)
        if is_number(numeric):
            number = float(numeric.replace(",", "."))
            return int(number) if number.is_integer() else number
        unhonoured.append({"target": target, "declared": declared,
                           "reason": f"value {text!r} does not parse as a number"})
        return text
    if declared == "boolean":
        flag = normalize_for("boolean_parse", text)
        if flag in ("true", "false"):
            return flag == "true"
        unhonoured.append({"target": target, "declared": declared,
                           "reason": f"value {text!r} is not a boolean literal"})
        return text
    if declared == "date":
        # GAP G1. The format carries no date format string and no locale, so the
        # only way to honour this is to guess dd.mm.yyyy vs mm.dd.yyyy. Guessing
        # is what this programme does not do -- the value is passed through and
        # the unhonoured declaration is recorded.
        unhonoured.append({
            "target": target, "declared": "date", "gap": "G1",
            "reason": "the recipe format has no date format string or locale, so "
                      "the declared type cannot be honoured without guessing"})
        return text
    unhonoured.append({"target": target, "declared": declared,
                       "reason": "unknown declared type"})
    return text


def _member_coverage(entry: SheetEntry, report) -> dict[str, dict]:
    """Per-member coverage maps for a data entry, keyed by ACTUAL sheet name.

    An ordinary `sheet:` entry has exactly one member, so there is one code path
    rather than a sheetset special case.
    """
    cov = report.coverage.get(entry.sheet)
    if not cov:
        raise InsufficientRecipe(f"no coverage map for {entry.sheet}")
    members = cov.get("members")
    if not members:
        raise InsufficientRecipe(f"no member coverage for {entry.sheet}")
    return members


def _data_row0s(cov: dict, where: str) -> list[int]:
    """Rows the VALIDATOR classified as data. Reusing its coverage map keeps the
    executor and the checker from ever disagreeing about what a data row is.

    For a sheetset this is the member's OWN map, not the prototype's. Members
    differ in length; taking the prototype's row set would drop a longer member's
    tail with nothing reporting it -- partial honour at collection scope.
    """
    if not cov:
        raise InsufficientRecipe(f"no coverage map for {where}")
    return sorted(r for r, labels in cov["rows"].items()
                  if labels == ["data_region"])


def execute(recipe: Recipe, wb: WorkbookView) -> Execution:
    report = validate(recipe, wb)
    if not report.valid:
        raise InsufficientRecipe(
            "refusing to execute an invalid recipe: "
            + "; ".join(f"{p.code}@{p.where}" for p in report.problems[:4]))
    if not report.approvable:
        raise InsufficientRecipe("refusing to execute: recipe is not approvable")

    out = Execution()
    for entry in recipe.data_sheets():
        members = _member_coverage(entry, report)
        header_ref = parse(entry.header_row)

        # Field referents are addressed against the PROTOTYPE sheet: the frozen
        # grammar has no member-relative referent and deliberately does not grow
        # one, so `layout_from` is what declares that the prototype governs every
        # member's layout. Column POSITIONS are resolved against it and applied
        # to each member. That is sound ONLY because the validator refuses a
        # member whose header row does not match the prototype
        # (`sheetset_member_layout_mismatch`); without that check this would be
        # the executor reading cells no referent named, which rule 1 forbids.
        header_rows0 = {m: header_ref.row0 for m in members}
        if entry.layout_from:
            proto_ref = parse(entry.layout_from)
            proto = wb.actual_sheet(proto_ref.sheet or "")
            if proto is None:
                raise InsufficientRecipe(
                    f"cannot resolve layout_from {entry.layout_from} for {entry.sheet}")
            header_rows0[proto] = header_ref.row0

        entry_columns: Optional[list[str]] = None

        for member, cov in members.items():
            header_values = wb.row_values(member, header_ref.row0)
            data_rows = _data_row0s(cov, f"{entry.sheet}@{member}")

            scalars: dict[str, Any] = {}
            id_fields: list[tuple[str, int, Optional[str]]] = []
            measures: list[tuple[str, int, Optional[str]]] = []
            unpivot: Optional[tuple[str, str, list[int], Optional[str]]] = None

            for fld in entry.fields:
                if fld.role == "metadata":
                    r = resolve(fld.source, wb, header_rows0=header_rows0)
                    values = wb.row_values(member, r.row0)
                    cell0 = values[r.col0] if r.col0 < len(values) else ""
                    scalars[fld.target] = _coerce(cell0, fld.type, fld.target,
                                                  out.unhonoured_types)
                    continue
                if fld.role == "derived":
                    op = fld.transform.op if fld.transform else None
                    params = fld.transform.params if fld.transform else {}
                    if op == "derive" and params.get("from") == "sheet_name":
                        # THIS member's name, not the prototype's. Period taken
                        # from the sheet name is the case sheetsets exist for, so
                        # using the prototype here would label every member's
                        # rows with the first member's period.
                        scalars[fld.target] = member
                        continue
                    raise InsufficientRecipe(
                        f"derived field {fld.target!r} needs transform {op!r}, "
                        "which the executor does not implement")
                r = resolve(fld.source, wb, header_rows0=header_rows0)
                cols = list(range(r.col0, r.col0_last + 1))
                if fld.role == "id":
                    id_fields.append((fld.target, cols[0], fld.type))
                elif fld.role == "measure":
                    measures.append((fld.target, cols[0], fld.type))
                elif fld.role == "period_measure":
                    if not fld.transform or fld.transform.op != "unpivot":
                        raise InsufficientRecipe(
                            f"period_measure {fld.target!r} without an unpivot transform")
                    params = fld.transform.params
                    var_target = params.get("var_target")
                    value_target = params.get("value_target")
                    if not var_target or not value_target:
                        raise InsufficientRecipe(
                            "unpivot needs var_target and value_target")
                    unpivot = (var_target, value_target, cols, fld.type)

            columns = list(scalars) + [t for t, _, _ in id_fields]
            if unpivot:
                columns += [unpivot[0], unpivot[1]]
            columns += [t for t, _, _ in measures]

            # Members of one entry must agree on shape. If they do not, the union
            # would silently write one member's values under another's headers --
            # the same defect recorded separately in PRO-2 instance 10.
            if entry_columns is None:
                entry_columns = columns
            elif columns != entry_columns:
                raise InsufficientRecipe(
                    f"{entry.sheet} member {member!r} yields columns {columns}, "
                    f"but earlier members yield {entry_columns}")
            if not out.columns:
                out.columns = columns

            for row0 in data_rows:
                values = wb.row_values(member, row0)

                def cell(col0: int, _values=values) -> str:
                    return _values[col0] if col0 < len(_values) else ""

                base = [scalars[k] for k in scalars]
                base += [_coerce(cell(c), t, name, out.unhonoured_types)
                         for name, c, t in id_fields]
                tail = [_coerce(cell(c), t, name, out.unhonoured_types)
                        for name, c, t in measures]

                if unpivot:
                    var_target, value_target, cols, dtype = unpivot
                    for col0 in cols:
                        label = normalize_for(
                            "unpivot_var_label",
                            header_values[col0] if col0 < len(header_values) else "")
                        out.rows.append(base + [label,
                                                _coerce(cell(col0), dtype, value_target,
                                                        out.unhonoured_types)] + tail)
                else:
                    out.rows.append(base + tail)

    # One entry per (target, gap) rather than one per cell.
    seen: set[tuple] = set()
    unique = []
    for item in out.unhonoured_types:
        key = (item["target"], item.get("gap"), item["declared"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    out.unhonoured_types = unique
    return out


if __name__ == "__main__":
    argv = sys.argv[1:]
    if len(argv) == 2:
        result = execute(load_recipe(argv[1]), WorkbookView(argv[0]))
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    sys.stderr.write("usage: execute_recipe.py <workbook.xlsx> <recipe.json>\n")
    raise SystemExit(2)
