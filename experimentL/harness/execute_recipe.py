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
import re
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


# A number whose ONLY separator is followed by exactly three digits. Thousands
# and decimal readings of it differ by a factor of 1000 and the format carries no
# locale to choose between them (gap G2). Anchored, and deliberately narrow: more
# or fewer than three trailing digits is not ambiguous.
_AMBIGUOUS_GROUPING = re.compile(r"^[+-]?\d{1,3}[.,]\d{3}$")


class InsufficientRecipe(Exception):
    """The executor needs information the recipe does not carry."""


@dataclass
class Execution:
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list[Any]] = dc_field(default_factory=list)
    unhonoured_types: list[dict] = dc_field(default_factory=list)
    notes: list[str] = dc_field(default_factory=list)
    # How many data rows each declared source sheet contributed. Cross-sheet law
    # 2: a member with a header and no data rows contributes zero, which is
    # legitimate -- and without this record it is indistinguishable from a member
    # that was never declared. A zero cannot be recovered by counting output
    # rows, because it leaves no row to count.
    member_contribution: dict[str, int] = dc_field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows,
                "unhonoured_types": self.unhonoured_types, "notes": self.notes,
                "member_contribution": self.member_contribution}


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
        if _AMBIGUOUS_GROUPING.match(numeric):
            # GAP G2, the sibling of G1. A single separator followed by exactly
            # three digits cannot be resolved without a locale, and the recipe
            # format carries none:
            #
            #     "1,234"  ->  1234 (US thousands)  or  1.234 (FI decimal)
            #     "1.234"  ->  1.234 (US decimal)   or  1234  (FI thousands)
            #
            # The old code did `float(numeric.replace(",", "."))`, which committed
            # to the decimal reading every time and emitted 1.234 for a US
            # thousands separator -- a factor-1000 error, marked honoured, with
            # nothing recorded.
            #
            # Not fixed by implementing locale parsing. G1's standing trap: that
            # is a result, and a declared format string is the obvious answer
            # belonging in its own freeze. One digit after the separator is NOT
            # ambiguous -- no thousands group has one digit -- so "1,5" and "1.5"
            # are still honoured as decimals.
            unhonoured.append({
                "target": target, "declared": "number", "gap": "G2",
                "reason": f"value {text!r} has a separator followed by exactly "
                          f"three digits and the recipe format carries no locale, "
                          f"so thousands and decimal readings differ by 1000 and "
                          f"neither is recoverable from the declaration"})
            return text
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
            binding_sheet = proto
        else:
            binding_sheet = next(iter(members))

        def _resolve_here(source: str, _binding=binding_sheet):
            """Resolve, and refuse anything that landed somewhere else (law 6).

            The resolver returns the ACTUAL sheet it resolved to; until this
            check existed the executor used only `col0` from it, so a resolution
            that landed on the wrong sheet contributed that sheet's COLUMN NUMBER
            to a read of this one. The output was wrong rather than refused,
            which is executor rule 1 -- read only what the recipe names --
            unenforced at the one place it can be checked.

            The comparison is against the entry's BINDING sheet, not the sheet
            being read: a sheetset binds to its prototype and reads from each
            member, so those legitimately differ. Requiring them to match would
            ban sheetsets rather than tighten anything.
            """
            r = resolve(source, wb, header_rows0=header_rows0)
            if r.ok and r.sheet != _binding:
                raise InsufficientRecipe(
                    f"{source!r} resolved to sheet {r.sheet!r}, but {entry.sheet} "
                    f"binds against {_binding!r}. Reading it would take one "
                    f"sheet's column positions into another sheet's rows.")
            return r

        entry_columns: Optional[list[str]] = None

        for member, cov in members.items():
            header_values = wb.row_values(member, header_ref.row0)
            data_rows = _data_row0s(cov, f"{entry.sheet}@{member}")
            # Recorded BEFORE the rows are emitted, so a member contributing zero
            # still appears. Deriving this afterwards from the output is exactly
            # what a consumer cannot do.
            out.member_contribution[member] = len(data_rows)

            scalars: dict[str, Any] = {}
            id_fields: list[tuple[str, int, Optional[str]]] = []
            measures: list[tuple[str, int, Optional[str]]] = []
            unpivot: Optional[tuple[str, str, list[int], Optional[str]]] = None

            for fld in entry.fields:
                if fld.role == "metadata":
                    r = _resolve_here(fld.source)
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
                r = _resolve_here(fld.source)
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
