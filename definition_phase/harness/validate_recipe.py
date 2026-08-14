#!/usr/bin/env python3
"""Recipe validator — structural / resolvable / coverage.

Spec: `design/recipe_format_v1.md`. Built on the frozen referent grammar
(`referent-grammar-v1`). No LLM anywhere; fully deterministic.

    STRUCTURAL   schema-valid; enums known; targets unique; referent kinds match
                 the field roles that bind them
    RESOLVABLE   every referent resolves against THIS workbook
    COVERAGE     every sheet has a role, and within each data sheet every row and
                 every column is claimed EXACTLY ONCE

Coverage is the load-bearing check. It is design v0's totality, doing the same
work: an unclassified row or column is a hole where data enters or leaves the
output without anyone deciding it should. Forgetting to exclude a grand-total row
makes it *unclassified* rather than *silently included* -- the SILENCE failure,
caught before a single row is read.

Validity is not approvability, and they are kept separate on purpose:

    valid       structural + resolvable + coverage all clean
    approvable  valid AND no blocking ambiguity

A recipe can be perfectly well-formed and still not runnable because a human
question is open. Collapsing the two would make "I have described this correctly
and one thing still needs you" indistinguishable from an error.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from recipe import (  # noqa: E402
    COLUMN_BOUND_ROLES, COLUMN_KINDS, EXCLUDE_RULE_OPS, FIELD_ROLES, RECIPE_VERSIONS,
    REMAINDER, ROW_SHAPE_CONSTRAINTS, SHEET_ROLES, TRANSFORM_OPS, TYPES, Exclusion,
    Recipe, SheetEntry, load_recipe,
)
sys.path.insert(0, str(HERE.parent.parent / "experimentJ" / "harness"))
from macro_v2 import is_number  # noqa: E402  (frozen numeric parse, Experiment J)
from referents import (  # noqa: E402
    ReferentSyntaxError, Referent, WorkbookView, parse, resolve,
)

PROBLEM_CODES = (
    # structural
    "unknown_recipe_version", "missing_key", "unknown_sheet_role",
    "unknown_field_role", "unknown_transform_op", "unknown_type",
    "duplicate_target", "malformed_referent", "wrong_referent_kind",
    "missing_exclude_reason", "field_source_kind_mismatch",
    "metadata_cell_in_data_region", "malformed_exclude", "unknown_exclude_rule_op",
    # resolution
    "unresolvable_referent",
    # coverage
    "sheet_unclassified", "column_unclassified", "column_double_bound",
    "row_unclassified", "row_double_classified", "row_shape_violation",
    # sheetset
    "sheetset_member_layout_mismatch",
    # approval (does NOT make the recipe invalid)
    "blocking_ambiguity",
)
APPROVAL_ONLY = ("blocking_ambiguity",)


@dataclass(frozen=True)
class Problem:
    code: str
    where: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.code:32} {self.where:28} {self.detail}"


@dataclass
class Report:
    recipe_id: str
    valid: bool = False
    approvable: bool = False
    problems: list[Problem] = dc_field(default_factory=list)
    coverage: dict = dc_field(default_factory=dict)
    content_sha256: str = ""

    def codes(self) -> set[str]:
        return {p.code for p in self.problems}


def _parse_ref(text: str, where: str, problems: list[Problem]) -> Optional[Referent]:
    try:
        return parse(text)
    except ReferentSyntaxError as exc:
        problems.append(Problem("malformed_referent", where, f"{text!r}: {exc}"))
        return None


def _expand_rows(ref: Referent, n_rows: int) -> set[int]:
    if ref.kind == "row":
        return {ref.row0}
    if ref.kind == "rowrange":
        return set(range(ref.row0, ref.row0_last + 1))
    if ref.kind == "sheet":
        return set(range(n_rows))
    return set()


def _expand_cols(ref: Referent, resolved_col0: Optional[int] = None) -> set[int]:
    if ref.kind == "col":
        return {ref.col0}
    if ref.kind == "colrange":
        return set(range(ref.col0, ref.col0_last + 1))
    if ref.kind == "namedcol" and resolved_col0 is not None:
        return {resolved_col0}
    return set()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(recipe: Recipe, wb: WorkbookView) -> Report:
    problems: list[Problem] = []
    coverage: dict = {}

    if recipe.recipe_version not in RECIPE_VERSIONS:
        problems.append(Problem("unknown_recipe_version", recipe.recipe_id,
                                str(recipe.recipe_version)))

    # ---- 1. structural: enums, uniqueness, referent kinds -------------------
    seen_targets: set[str] = set()
    for entry in recipe.sheets:
        where = entry.sheet or "<no sheet>"
        if entry.role not in SHEET_ROLES:
            problems.append(Problem("unknown_sheet_role", where, entry.role))
        if entry.role == "data":
            for key in ("header_row", "data_region"):
                if not getattr(entry, key):
                    problems.append(Problem("missing_key", where, key))
        for exc in entry.exclude:
            if not (exc.reason or "").strip():
                problems.append(Problem("missing_exclude_reason", where,
                                        exc.referent or str(exc.rule)))
            if bool(exc.referent) == bool(exc.rule):
                problems.append(Problem("malformed_exclude", where,
                                        "an exclusion needs exactly one of referent / rule"))
            if exc.rule and exc.rule.op not in EXCLUDE_RULE_OPS:
                problems.append(Problem("unknown_exclude_rule_op", where, exc.rule.op))
        if entry.data_row_shape:
            for constraint, ref_text in entry.data_row_shape.columns():
                ref = _parse_ref(ref_text, f"{where}:{constraint}", problems)
                if ref is not None and ref.kind not in COLUMN_KINDS:
                    problems.append(Problem("wrong_referent_kind", where,
                                            f"data_row_shape.{constraint} needs a column "
                                            f"referent, got {ref.kind}"))
        for fld in entry.fields:
            fwhere = f"{where}:{fld.target or '<no target>'}"
            if not fld.target:
                problems.append(Problem("missing_key", where, "field.target"))
            elif fld.target in seen_targets:
                problems.append(Problem("duplicate_target", fwhere, fld.target))
            else:
                seen_targets.add(fld.target)
            if fld.role not in FIELD_ROLES:
                problems.append(Problem("unknown_field_role", fwhere, fld.role))
            if fld.type is not None and fld.type not in TYPES:
                problems.append(Problem("unknown_type", fwhere, str(fld.type)))
            if fld.transform and fld.transform.op not in TRANSFORM_OPS:
                problems.append(Problem("unknown_transform_op", fwhere, fld.transform.op))
            # role <-> referent-kind pairing
            if fld.role == "derived":
                if fld.source:
                    problems.append(Problem("field_source_kind_mismatch", fwhere,
                                            "derived fields take no source"))
                if not fld.transform:
                    problems.append(Problem("missing_key", fwhere, "derived field needs a transform"))
            elif not fld.source:
                problems.append(Problem("missing_key", fwhere, "field.source"))
            else:
                ref = _parse_ref(fld.source, fwhere, problems)
                if ref is not None:
                    if fld.role in COLUMN_BOUND_ROLES and ref.kind not in COLUMN_KINDS:
                        problems.append(Problem("field_source_kind_mismatch", fwhere,
                                                f"role {fld.role} needs a column referent, got {ref.kind}"))
                    if fld.role == "metadata" and ref.kind != "cell":
                        problems.append(Problem("field_source_kind_mismatch", fwhere,
                                                f"metadata needs a cell referent, got {ref.kind}"))

    # ---- 2. resolution ------------------------------------------------------
    # `@name` cannot resolve until the header row is known, so header rows are
    # derived FROM THE RECIPE before fields are attempted.
    header_rows0: dict[str, int] = {}
    for entry in recipe.sheets:
        if entry.role != "data" or not entry.header_row:
            continue
        ref = _parse_ref(entry.header_row, entry.sheet, problems)
        if ref is None:
            continue
        if ref.kind != "row":
            problems.append(Problem("wrong_referent_kind", entry.sheet,
                                    f"header_row must be a row, got {ref.kind}"))
            continue
        for sheet_name in _member_sheets(recipe, entry, wb, problems):
            header_rows0[sheet_name] = ref.row0

    def _resolve(text: str, where: str):
        r = resolve(text, wb, header_rows0=header_rows0, sheetsets=recipe.sheetsets)
        if not r.ok:
            problems.append(Problem("unresolvable_referent", where,
                                    f"{text} -> {r.reason}" + (f" ({r.detail})" if r.detail else "")))
        return r

    for entry in recipe.sheets:
        _resolve(entry.sheet, entry.sheet)
        for exc in entry.exclude:
            if exc.referent:
                _resolve(exc.referent, entry.sheet)
            elif exc.rule and exc.rule.column:
                _resolve(exc.rule.column, entry.sheet)
        for amb in entry.ambiguities:
            _resolve(amb.referent, entry.sheet)
        for fld in entry.fields:
            if fld.source:
                _resolve(fld.source, f"{entry.sheet}:{fld.target}")
        if entry.data_row_shape:
            for constraint, ref_text in entry.data_row_shape.columns():
                _resolve(ref_text, f"{entry.sheet}:{constraint}")

    # ---- 3. coverage --------------------------------------------------------
    declared: set[str] = set()
    for entry in recipe.sheets:
        for name in _member_sheets(recipe, entry, wb, problems):
            declared.add(name.casefold())
    for name in wb.sheet_names:
        if name.casefold() not in declared:
            problems.append(Problem("sheet_unclassified", name,
                                    "every sheet must be given a role"))

    for entry in recipe.data_sheets():
        coverage[entry.sheet] = _coverage_for_data_sheet(
            recipe, entry, wb, header_rows0, problems)

    # ---- 4. sheetset member layouts ----------------------------------------
    for entry in recipe.sheets:
        if entry.is_sheetset and entry.role == "data":
            _check_sheetset_layout(recipe, entry, wb, header_rows0, problems)

    # ---- verdict ------------------------------------------------------------
    for entry in recipe.sheets:
        for amb in entry.ambiguities:
            if amb.blocking:
                problems.append(Problem("blocking_ambiguity", entry.sheet, amb.referent))

    hard = [p for p in problems if p.code not in APPROVAL_ONLY]
    report = Report(recipe_id=recipe.recipe_id, problems=problems, coverage=coverage,
                    content_sha256=recipe.content_sha256())
    report.valid = not hard
    report.approvable = report.valid and not any(p.code == "blocking_ambiguity" for p in problems)
    return report


def _member_sheets(recipe: Recipe, entry: SheetEntry, wb: WorkbookView,
                   problems: list[Problem]) -> list[str]:
    """Actual workbook sheet names an entry covers (a sheetset covers many)."""
    ref = _parse_ref(entry.sheet, entry.sheet, problems)
    if ref is None:
        return []
    if ref.kind == "sheetset":
        members = recipe.sheetsets.get(ref.name or "", ())
        out = []
        for member in members:
            actual = wb.actual_sheet(member)
            if actual:
                out.append(actual)
        return out
    if ref.kind == "sheet":
        actual = wb.actual_sheet(ref.sheet or "")
        return [actual] if actual else []
    return []


def _prototype_sheet(recipe: Recipe, entry: SheetEntry, wb: WorkbookView,
                     problems: list[Problem]) -> Optional[str]:
    if entry.is_sheetset:
        if not entry.layout_from:
            problems.append(Problem("missing_key", entry.sheet,
                                    "a sheetset data entry needs layout_from"))
            return None
        ref = _parse_ref(entry.layout_from, entry.sheet, problems)
        return wb.actual_sheet(ref.sheet or "") if ref else None
    members = _member_sheets(recipe, entry, wb, problems)
    return members[0] if members else None


def _coverage_for_data_sheet(recipe: Recipe, entry: SheetEntry, wb: WorkbookView,
                             header_rows0: dict, problems: list[Problem]) -> dict:
    sheet = _prototype_sheet(recipe, entry, wb, problems)
    if sheet is None:
        return {}
    n_rows, n_cols = wb.dims(sheet)

    row_claims: dict[int, list[str]] = {}
    col_claims: dict[int, list[str]] = {}

    def claim_rows(rows: set[int], label: str) -> None:
        for r in rows:
            row_claims.setdefault(r, []).append(label)

    def claim_cols(cols: set[int], label: str) -> None:
        for c in cols:
            col_claims.setdefault(c, []).append(label)

    if entry.header_row:
        ref = parse(entry.header_row)
        if ref.kind == "row":
            claim_rows({ref.row0}, "header_row")

    # Exclusions are resolved BEFORE the data region, because a `remainder`
    # region is defined as whatever they leave behind (v1.1).
    for exc in entry.exclude:
        if exc.rule is not None:
            claim_rows(_rule_rows(exc, wb, sheet, n_rows, header_rows0, problems),
                       "exclude")
            continue
        ref = _parse_ref(exc.referent or "", entry.sheet, problems)
        if ref is None:
            continue
        if ref.kind in ("row", "rowrange"):
            claim_rows(_expand_rows(ref, n_rows), "exclude")
        elif ref.kind in COLUMN_KINDS:
            r = resolve(ref, wb, header_rows0=header_rows0)
            claim_cols(_expand_cols(ref, r.col0 if r.ok else None), "exclude")
        else:
            problems.append(Problem("wrong_referent_kind", entry.sheet,
                                    f"exclude must be rows or columns, got {ref.kind}"))

    if entry.data_region == REMAINDER:
        # The region grows with the file instead of being pinned to the row
        # count of the day the recipe was written (Experiment K, C3).
        claim_rows({r for r in range(n_rows) if r not in row_claims}, "data_region")
    elif entry.data_region:
        ref = _parse_ref(entry.data_region, entry.sheet, problems)
        if ref is not None:
            if ref.kind not in ("row", "rowrange"):
                problems.append(Problem("wrong_referent_kind", entry.sheet,
                                        f"data_region must be rows, got {ref.kind}"))
            else:
                claim_rows(_expand_rows(ref, n_rows), "data_region")

    data_rows = {r for r, labels in row_claims.items() if "data_region" in labels}

    for fld in entry.fields:
        if not fld.source:
            continue
        ref = _parse_ref(fld.source, entry.sheet, problems)
        if ref is None:
            continue
        if ref.kind in COLUMN_KINDS:
            r = resolve(ref, wb, header_rows0=header_rows0)
            claim_cols(_expand_cols(ref, r.col0 if r.ok else None), f"field:{fld.target}")
        elif ref.kind == "cell" and fld.role == "metadata":
            # A metadata cell is a separate channel: it does not participate in
            # column coverage, but it must not sit inside the data region.
            if ref.row0 in data_rows:
                problems.append(Problem("metadata_cell_in_data_region",
                                        f"{entry.sheet}:{fld.target}", fld.source))

    if entry.data_row_shape:
        _check_row_shape(entry, wb, sheet, sorted(data_rows), header_rows0, problems)

    for r in range(n_rows):
        labels = row_claims.get(r, [])
        if not labels:
            problems.append(Problem("row_unclassified", entry.sheet,
                                    f"row0 {r} (A1 row {r + 1}) is claimed by nothing"))
        elif len(labels) > 1:
            problems.append(Problem("row_double_classified", entry.sheet,
                                    f"row0 {r} claimed by {labels}"))
    for c in range(n_cols):
        labels = col_claims.get(c, [])
        if not labels:
            problems.append(Problem("column_unclassified", entry.sheet,
                                    f"col0 {c} is claimed by nothing"))
        elif len(labels) > 1:
            problems.append(Problem("column_double_bound", entry.sheet,
                                    f"col0 {c} claimed by {labels}"))

    return {
        "sheet": sheet, "n_rows": n_rows, "n_cols": n_cols,
        "rows": {r: row_claims.get(r, []) for r in range(n_rows)},
        "cols": {c: col_claims.get(c, []) for c in range(n_cols)},
    }


def _check_row_shape(entry: SheetEntry, wb: WorkbookView, sheet: str,
                     data_rows: list[int], header_rows0: dict,
                     problems: list[Problem]) -> None:
    """Every data row must satisfy the declared shape (v1.2).

    TYPE-LEVEL only: blank / numeric / neither. The validator never branches on
    what a cell SAYS, so a hostile workbook can force an escalation and nothing
    else -- the widened input surface buys detection without buying authority.
    """
    from referents import parse as _parse

    shape = entry.data_row_shape
    if shape is None:
        return
    resolved: list[tuple[str, str, int]] = []
    for constraint, ref_text in shape.columns():
        r = resolve(ref_text, wb, header_rows0=header_rows0)
        if not r.ok:
            continue                      # already reported as unresolvable
        for col0 in range(r.col0, r.col0_last + 1):
            resolved.append((constraint, ref_text, col0))

    for row0 in data_rows:
        values = wb.row_values(sheet, row0)
        for constraint, ref_text, col0 in resolved:
            cell = values[col0] if col0 < len(values) else ""
            if constraint == "require_non_blank" and cell.strip() == "":
                problems.append(Problem(
                    "row_shape_violation", entry.sheet,
                    f"row0 {row0} (A1 row {row0 + 1}): {ref_text} col0 {col0} is blank"))
            elif constraint == "require_numeric" and not is_number(cell):
                problems.append(Problem(
                    "row_shape_violation", entry.sheet,
                    f"row0 {row0} (A1 row {row0 + 1}): {ref_text} col0 {col0} "
                    f"is not numeric ({cell.strip()[:24]!r})"))


def _rule_rows(exc: Exclusion, wb: WorkbookView, sheet: str, n_rows: int,
               header_rows0: dict, problems: list[Problem]) -> set[int]:
    """Rows matched by a content rule (v1.1).

    Rules exist for things anchored to the BOTTOM of a sheet -- a grand-total
    row moves every month, a preamble does not. The principle: anchor
    positionally from the stable end, by rule from the unstable one.

    `label_in` matches LITERAL values only. No patterns, no regex: a rule is a
    predicate over untrusted cell content, and a pattern language would be an
    expression language arriving through the back door.
    """
    rule = exc.rule
    if rule is None or rule.op not in EXCLUDE_RULE_OPS:
        return set()

    if rule.op == "row_blank":
        return {r for r in range(n_rows)
                if all(v.strip() == "" for v in wb.row_values(sheet, r))}

    # label_in
    if not rule.column:
        problems.append(Problem("malformed_exclude", sheet, "label_in needs a column"))
        return set()
    resolved = resolve(rule.column, wb, header_rows0=header_rows0)
    if not resolved.ok:
        return set()   # already reported as unresolvable_referent
    wanted = {v.strip().casefold() for v in rule.values}
    hits: set[int] = set()
    for r in range(n_rows):
        values = wb.row_values(sheet, r)
        if resolved.col0 < len(values) and values[resolved.col0].strip().casefold() in wanted:
            hits.add(r)
    return hits


def _check_sheetset_layout(recipe: Recipe, entry: SheetEntry, wb: WorkbookView,
                           header_rows0: dict, problems: list[Problem]) -> None:
    """Every member must share the prototype's header row.

    A small applicability predicate -- the same machinery the front door needs
    (plan sec.8.5). The concept appears twice because it is one concept.
    """
    prototype = _prototype_sheet(recipe, entry, wb, problems)
    if prototype is None or not entry.header_row:
        return
    ref = parse(entry.header_row)
    if ref.kind != "row":
        return
    expected = [v.casefold() for v in wb.row_values(prototype, ref.row0)]
    for member in _member_sheets(recipe, entry, wb, problems):
        if member.casefold() == prototype.casefold():
            continue
        actual = [v.casefold() for v in wb.row_values(member, ref.row0)]
        if actual != expected:
            problems.append(Problem("sheetset_member_layout_mismatch", member,
                                    f"header {actual} != prototype {expected}"))


# ---------------------------------------------------------------------------
# Dry run — prove the bindings point at real data, without executing
# ---------------------------------------------------------------------------

def dry_run(recipe: Recipe, wb: WorkbookView) -> list[dict]:
    header_rows0: dict[str, int] = {}
    for entry in recipe.sheets:
        if entry.role == "data" and entry.header_row:
            try:
                ref = parse(entry.header_row)
            except ReferentSyntaxError:
                continue
            if ref.kind == "row":
                for name in _member_sheets(recipe, entry, wb, []):
                    header_rows0[name] = ref.row0

    out: list[dict] = []
    for entry in recipe.data_sheets():
        for fld in entry.fields:
            if not fld.source:
                out.append({"target": fld.target, "role": fld.role,
                            "source": None, "note": "derived", "sample": []})
                continue
            r = resolve(fld.source, wb, header_rows0=header_rows0,
                        sheetsets=recipe.sheetsets)
            if not r.ok:
                out.append({"target": fld.target, "role": fld.role,
                            "source": fld.source, "note": f"UNRESOLVED {r.reason}",
                            "sample": []})
                continue
            data_rows: set[int] = set()
            if entry.data_region:
                data_rows = _expand_rows(parse(entry.data_region), r.row0_last + 1)
            sample: list[str] = []
            rows = sorted(data_rows) if (data_rows and fld.role != "metadata") else [r.row0]
            for row0 in rows[:3]:
                values = wb.row_values(r.sheet, row0)
                cells = [values[c] if c < len(values) else ""
                         for c in range(r.col0, r.col0_last + 1)]
                sample.append(", ".join(cells))
            out.append({
                "target": fld.target, "role": fld.role, "source": fld.source,
                "note": (f"{r.sheet} rows {r.row0}..{r.row0_last} "
                         f"cols {r.col0}..{r.col0_last}"),
                "sample": sample,
            })
    return out


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []
    seen_codes: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    wb = WorkbookView(ROOT / "fixtures" / "W1_multisheet.xlsx")

    # --- the good recipe: valid, but NOT approvable (blocking ambiguity) -----
    good = load_recipe(ROOT / "recipes" / "W1_sales.json")
    rep = validate(good, wb)
    seen_codes |= rep.codes()
    check(rep.valid, f"W1_sales should be valid; problems: {[str(p) for p in rep.problems]}")
    check(not rep.approvable,
          "W1_sales must NOT be approvable: it has a blocking ambiguity")
    check(rep.codes() == {"blocking_ambiguity"},
          f"W1_sales should report only the blocking ambiguity, got {rep.codes()}")
    cov = rep.coverage["sheet:Sales"]
    check(cov["n_rows"] == 9 and cov["n_cols"] == 6, f"Sales dims: {cov['n_rows']}x{cov['n_cols']}")
    check(all(len(v) == 1 for v in cov["rows"].values()),
          f"every row claimed exactly once: {cov['rows']}")
    check(all(len(v) == 1 for v in cov["cols"].values()),
          f"every column claimed exactly once: {cov['cols']}")
    check(cov["rows"][3] == ["header_row"], f"row0 3 is the header: {cov['rows'][3]}")
    check(cov["rows"][8] == ["exclude"], f"row0 8 is the total row, excluded: {cov['rows'][8]}")
    check(len(rep.content_sha256) == 64, "content hash for approval binding")

    # --- v1.1: remainder region + rule-based exclusion (Experiment K, C3) ----
    v11 = load_recipe(ROOT / "recipes" / "W1_sales_v11.json")
    rep11 = validate(v11, wb)
    seen_codes |= rep11.codes()
    check(rep11.valid, f"W1_sales_v11 should be valid; {[str(p) for p in rep11.problems]}")
    cov11 = rep11.coverage["sheet:Sales"]
    check(all(len(v) == 1 for v in cov11["rows"].values()),
          f"remainder must leave every row claimed exactly once: {cov11['rows']}")
    check(cov11["rows"][8] == ["exclude"],
          f"the YHTEENSÄ row must be excluded BY RULE, not by position: {cov11['rows'][8]}")
    check(cov11["rows"][4] == ["data_region"] and cov11["rows"][7] == ["data_region"],
          "the four product rows must fall to the remainder")
    # The whole point: the same recipe must still be total when rows are ADDED.
    wb_more = WorkbookView(ROOT.parent / "experimentK" / "fixtures" / "C3_more_rows.xlsx")
    rep11_more = validate(v11, wb_more)
    cov_more = rep11_more.coverage["sheet:Sales"]
    check(cov_more["n_rows"] == 11, f"C3 has 11 rows, got {cov_more['n_rows']}")
    check(all(len(v) == 1 for v in cov_more["rows"].values()),
          f"remainder must absorb two extra products: {cov_more['rows']}")
    check(cov_more["rows"][10] == ["exclude"],
          f"the total row MOVED to row0 10 and must still be excluded: {cov_more['rows'][10]}")
    check(not [p for p in rep11_more.problems if p.code != "blocking_ambiguity"],
          f"v1.1 must have no coverage problems on C3: "
          f"{[str(p) for p in rep11_more.problems]}")

    # --- v1.2: row-shape expectation (Experiment K, C13) ---------------------
    v12 = load_recipe(ROOT / "recipes" / "W1_sales_v12.json")
    rep12 = validate(v12, wb)
    seen_codes |= rep12.codes()
    check(rep12.valid, f"W1_sales_v12 should be valid on W1: "
                       f"{[str(p) for p in rep12.problems]}")
    # The footnote fixture is what the shape rule exists to catch.
    wb_foot = WorkbookView(ROOT.parent / "experimentK" / "fixtures" / "C13_footnote_row.xlsx")
    rep12_foot = validate(v12, wb_foot)
    seen_codes |= rep12_foot.codes()
    check("row_shape_violation" in rep12_foot.codes(),
          f"a footnote row with blank measures must violate the shape: "
          f"{sorted(rep12_foot.codes())}")
    # ...and the subtotal fixture is what it provably CANNOT catch: VÄLISUMMA is
    # non-blank and its measures are numeric, so it has exactly a data row's
    # shape. This asserts the boundary, not a capability.
    wb_sub = WorkbookView(ROOT.parent / "experimentK" / "fixtures" / "C8_silent_subtotal.xlsx")
    rep12_sub = validate(v12, wb_sub)
    check("row_shape_violation" not in rep12_sub.codes(),
          "a subtotal row has a data row's SHAPE; a type-level rule must not "
          "claim to catch it")
    # v1.1 (no shape declared) must be unaffected by any of this.
    check("row_shape_violation" not in validate(
        load_recipe(ROOT / "recipes" / "W1_sales_v11.json"), wb_foot).codes(),
        "a recipe without data_row_shape must not gain the check")

    # --- v1.1 structural failures -------------------------------------------
    from recipe import recipe_from_json as _rfj

    def _probe_raw(raw: dict) -> Report:
        r = validate(_rfj(raw), wb)
        seen_codes.update(r.codes())
        return r

    ignore_rest = [{"sheet": f"sheet:{n}" if " " not in n else f"sheet:'{n}'",
                    "role": "ignore", "reason": "x"}
                   for n in wb.sheet_names if n != "Dup"]
    bad_rules = {
        "recipe_version": 1, "recipe_id": "p",
        "sheets": [{"sheet": "sheet:Dup", "role": "data", "header_row": "sheet:Dup!1",
                    "data_region": "remainder",
                    "fields": [{"target": "a", "source": "sheet:Dup!A:C",
                                "role": "id", "type": "string"}],
                    "exclude": [
                        {"referent": "sheet:Dup!2", "rule": {"op": "label_in"},
                         "reason": "both referent and rule"},
                        {"rule": {"op": "levitate", "column": "sheet:Dup!A"},
                         "reason": "unknown op"},
                    ]}] + ignore_rest}
    rep_rules = _probe_raw(bad_rules)
    check("malformed_exclude" in rep_rules.codes(),
          f"referent AND rule must be rejected: {sorted(rep_rules.codes())}")
    check("unknown_exclude_rule_op" in rep_rules.codes(),
          f"unknown rule op must be rejected: {sorted(rep_rules.codes())}")

    # --- sheetset recipe -----------------------------------------------------
    months = load_recipe(ROOT / "recipes" / "W1_months.json")
    rep_m = validate(months, wb)
    seen_codes |= rep_m.codes()
    check(rep_m.valid and rep_m.approvable,
          f"W1_months should be valid and approvable; problems: {[str(p) for p in rep_m.problems]}")

    # --- broken 1: the SILENCE case, caught statically -----------------------
    b1 = load_recipe(ROOT / "recipes" / "broken" / "W1_sales_missing_total_row.json")
    rep1 = validate(b1, wb)
    seen_codes |= rep1.codes()
    check(not rep1.valid, "missing total-row exclusion must be invalid")
    check("row_unclassified" in rep1.codes(),
          f"omitting the total row must be row_unclassified, got {rep1.codes()}")
    check(any("row0 8" in p.detail for p in rep1.problems if p.code == "row_unclassified"),
          "the unclassified row must be named (row0 8 / A1 row 9)")

    # --- broken 2: double-bound column + undeclared sheet --------------------
    b2 = load_recipe(ROOT / "recipes" / "broken" / "W1_sales_double_bound.json")
    rep2 = validate(b2, wb)
    seen_codes |= rep2.codes()
    check(not rep2.valid, "double-bound column must be invalid")
    check("column_double_bound" in rep2.codes(), f"expected column_double_bound: {rep2.codes()}")
    check("sheet_unclassified" in rep2.codes(),
          f"the undeclared Notes sheet must be caught: {rep2.codes()}")

    # --- structural / resolution codes, exercised on constructed recipes -----
    from recipe import recipe_from_json

    def probe(raw: dict) -> Report:
        r = validate(recipe_from_json(raw), wb)
        seen_codes.update(r.codes())
        return r

    base_sheets = [{"sheet": f"sheet:{n}" if " " not in n else f"sheet:'{n}'",
                    "role": "ignore", "reason": "x"} for n in wb.sheet_names]

    def with_data(entry: dict) -> dict:
        others = [s for s in base_sheets if s["sheet"] != entry["sheet"]]
        return {"recipe_version": 1, "recipe_id": "probe", "sheets": [entry] + others}

    check("unknown_recipe_version" in probe(
        {"recipe_version": 99, "recipe_id": "p", "sheets": base_sheets}).codes(),
        "unknown_recipe_version")
    check("unknown_sheet_role" in probe(
        {"recipe_version": 1, "recipe_id": "p",
         "sheets": [dict(s, role="banana") for s in base_sheets]}).codes(),
        "unknown_sheet_role")

    dup = with_data({"sheet": "sheet:Dup", "role": "data",
                     "header_row": "sheet:Dup!1", "data_region": "sheet:Dup!2:3",
                     "fields": [
                         {"target": "a", "source": "sheet:Dup!@Tuote", "role": "id", "type": "string"},
                         {"target": "a", "source": "sheet:Dup!B", "role": "measure", "type": "banana"},
                         {"target": "c", "source": "sheet:Dup!B2", "role": "id"},
                         {"target": "d", "source": "sheet:Dup!@Myynti", "role": "measure"},
                         {"target": "e", "role": "derived",
                          "transform": {"op": "levitate"}},
                         {"target": "f", "role": "metadata", "source": "sheet:Dup!A2"},
                     ],
                     "exclude": [{"referent": "sheet:Dup!C"}]})
    rep3 = probe(dup)
    for expected in ("duplicate_target", "unknown_type", "field_source_kind_mismatch",
                     "unknown_transform_op", "missing_exclude_reason",
                     "unresolvable_referent", "metadata_cell_in_data_region"):
        check(expected in rep3.codes(), f"{expected} not reported; got {sorted(rep3.codes())}")

    bad_kinds = with_data({"sheet": "sheet:Notes", "role": "data",
                           "header_row": "sheet:Notes!A1", "data_region": "sheet:Notes!A1",
                           "fields": [{"target": "x", "source": "sheet:Notes!@Foo",
                                       "role": "id", "type": "string"}],
                           "exclude": [{"referent": "sheet:Notes!A1", "reason": "r"}]})
    rep4 = probe(bad_kinds)
    check("wrong_referent_kind" in rep4.codes(), f"wrong_referent_kind: {sorted(rep4.codes())}")

    malformed = with_data({"sheet": "sheet:Notes", "role": "data",
                           "header_row": "sheet:Notes!1", "data_region": "sheet:Notes!2",
                           "fields": [{"target": "x", "source": "sheet:Notes!((",
                                       "role": "id", "type": "string"}],
                           "exclude": []})
    check("malformed_referent" in probe(malformed).codes(), "malformed_referent")

    missing = with_data({"sheet": "sheet:Notes", "role": "data"})
    check("missing_key" in probe(missing).codes(), "missing_key")
    check("unknown_field_role" in probe(with_data(
        {"sheet": "sheet:Notes", "role": "data", "header_row": "sheet:Notes!1",
         "data_region": "sheet:Notes!2",
         "fields": [{"target": "x", "source": "sheet:Notes!A", "role": "wizard"}],
         "exclude": []})).codes(), "unknown_field_role")

    # column_unclassified: bind only one of Dup's three columns
    partial = with_data({"sheet": "sheet:Dup", "role": "data",
                         "header_row": "sheet:Dup!1", "data_region": "sheet:Dup!2:3",
                         "fields": [{"target": "a", "source": "sheet:Dup!A",
                                     "role": "id", "type": "string"}],
                         "exclude": []})
    check("column_unclassified" in probe(partial).codes(), "column_unclassified")

    # row_double_classified: data_region overlapping the header row
    overlap = with_data({"sheet": "sheet:Dup", "role": "data",
                         "header_row": "sheet:Dup!1", "data_region": "sheet:Dup!1:3",
                         "fields": [{"target": "a", "source": "sheet:Dup!A:C",
                                     "role": "id", "type": "string"}],
                         "exclude": []})
    check("row_double_classified" in probe(overlap).codes(), "row_double_classified")

    # sheetset_member_layout_mismatch: a set whose members differ
    mismatch = {"recipe_version": 1, "recipe_id": "p",
                "sheetsets": {"Bad": ["2026-01", "Dup"]},
                "sheets": [
                    {"sheet": "sheetset:Bad", "role": "data", "layout_from": "sheet:2026-01",
                     "header_row": "sheet:2026-01!1", "data_region": "sheet:2026-01!2:3",
                     "fields": [{"target": "a", "source": "sheet:2026-01!A:B",
                                 "role": "id", "type": "string"}],
                     "exclude": []},
                    {"sheet": "sheet:Sales", "role": "ignore", "reason": "x"},
                    {"sheet": "sheet:'Myynti 2026'", "role": "ignore", "reason": "x"},
                    {"sheet": "sheet:Notes", "role": "ignore", "reason": "x"},
                    {"sheet": "sheet:2026-02", "role": "ignore", "reason": "x"},
                ]}
    check("sheetset_member_layout_mismatch" in probe(mismatch).codes(),
          "sheetset_member_layout_mismatch")

    # --- legacy adapter: the expressiveness proof ---------------------------
    from recipe import from_legacy_manual_recipe
    legacy = {
        "header_row_index": 3,
        "fields": [
            {"target": "paivitetty", "source_pointer": {"row": 1, "col": 1},
             "source_type": "metadata", "data_type": "date"},
            {"target": "tuote", "source_pointer": {"column": "Tuote"},
             "source_type": "column", "data_type": "string"},
        ],
    }
    conv = from_legacy_manual_recipe(legacy, "Sales", n_rows=9)
    entry = conv.sheets[0]
    check(entry.header_row == "sheet:Sales!4",
          f"legacy header_row_index 3 (0-based) -> A1 row 4, got {entry.header_row}")
    check(entry.fields[0].source == "sheet:Sales!B2",
          f"legacy (row 1, col 1) -> B2, got {entry.fields[0].source}")
    check(entry.fields[1].source == "sheet:Sales!@Tuote",
          f"legacy column pointer -> @Tuote, got {entry.fields[1].source}")

    # --- dry run: bindings point at real data -------------------------------
    rows = dry_run(good, wb)
    by_target = {r["target"]: r for r in rows}
    check(by_target["tuote"]["sample"][:1] == ["ART-001"],
          f"dry run should pull real values: {by_target['tuote']}")
    check(by_target["myynti"]["sample"][:1] == ["10, 12, 8"],
          f"unpivot source should span three month columns: {by_target['myynti']}")
    check(by_target["paivitetty"]["sample"][:1] == ["3.2.2026"],
          f"metadata cell: {by_target['paivitetty']}")

    untested = set(PROBLEM_CODES) - seen_codes
    check(not untested, f"declared but untested problem codes: {sorted(untested)}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (W1_sales valid but NOT approvable / sheetset recipe valid / "
        "missing total row -> row_unclassified / double-bound column + undeclared sheet / "
        "legacy adapter round-trip / dry run pulls real values / v1.2 row shape catches "
        "the footnote and provably does NOT catch the subtotal / all 23 problem codes "
        "exercised)\n"
    )
    return 0


def _print_report(rep: Report) -> None:
    print(f"recipe   {rep.recipe_id}")
    print(f"valid    {rep.valid}")
    print(f"approvable {rep.approvable}")
    print(f"sha256   {rep.content_sha256[:16]}…")
    if rep.problems:
        print("problems:")
        for p in rep.problems:
            print(f"  {p}")
    else:
        print("problems: none")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        raise SystemExit(_self_test())
    if argv and argv[0] == "--validate":
        view = WorkbookView(argv[1])
        rep = validate(load_recipe(argv[2]), view)
        _print_report(rep)
        raise SystemExit(0 if rep.valid else 1)
    if argv and argv[0] == "--dry-run":
        view = WorkbookView(argv[1])
        print(json.dumps(dry_run(load_recipe(argv[2]), view), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    sys.stderr.write(
        "usage: validate_recipe.py --self-test\n"
        "       validate_recipe.py --validate <workbook.xlsx> <recipe.json>\n"
        "       validate_recipe.py --dry-run  <workbook.xlsx> <recipe.json>\n")
    raise SystemExit(2)
