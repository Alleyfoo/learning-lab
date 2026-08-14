#!/usr/bin/env python3
"""Referent grammar v1 — parser, canonical renderer, comparison key, resolver.

Spec: `design/referent_grammar_v1.md`. The spec is authority; if this file and
the spec disagree, this file is wrong.

A referent is a deterministic address into a workbook — the primitive every
definition-phase layer speaks. Surface form is A1-style and 1-BASED; the
internal form is a frozen dataclass. Text in, object compared, canonical text
out.

    workbook:                      the workbook under definition
    sheetset:Months                a declared set of sheets
    sheet:Sales                    a whole sheet
    sheet:Sales!D5                 cell          sheet:Sales!D5:P96   region
    sheet:Sales!5                  row           sheet:Sales!5:96     row range
    sheet:Sales!D                  column        sheet:Sales!D:P      column range
    sheet:Sales!@Myynti            column BY HEADER NAME
    sheet:'Myynti 2026'!A1         quoted sheet name

Binding mode is explicit and load-bearing: `!D` survives a rename and breaks on
an inserted column; `!@Myynti` survives an insert and breaks on a rename. The
grammar refuses to hide which one a recipe depends on (see spec sec.3 and
repo_reuse_map.md defect D1 -- positional mapping that silently shifts).

Resolution failures are a frozen enum and are HARD ERRORS, never warnings. Two
of them are judgement calls made deliberately:
  * `header_ambiguous` -- two columns share the header, so the reference is
    refused rather than resolved to the first match. Picking one would assert
    what the evidence does not establish.
  * `header_row_not_declared` -- `@Myynti` is meaningless until someone says
    which row the headers are on, so the recipe is forced to have declared it.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

MAX_COL = 16384  # XFD, Excel's limit
KINDS = (
    "workbook", "sheetset", "sheet",
    "cell", "cellrange", "row", "rowrange", "col", "colrange", "namedcol",
)
REASONS = (
    "malformed",
    "sheet_not_found",
    "sheetset_not_declared",
    "out_of_bounds",
    "header_row_not_declared",
    "header_not_found",
    "header_ambiguous",
)
# Sheet names containing any of these must be quoted.
_NEEDS_QUOTE = set(" !:'")


class ReferentSyntaxError(ValueError):
    """Raised by parse(). A malformed referent never becomes an object."""


# ---------------------------------------------------------------------------
# Column letters <-> 1-based index
# ---------------------------------------------------------------------------

def col_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        if not ("A" <= ch <= "Z"):
            raise ReferentSyntaxError(f"bad column letters: {letters!r}")
        n = n * 26 + (ord(ch) - 64)
    if not 1 <= n <= MAX_COL:
        raise ReferentSyntaxError(f"column out of range: {letters!r}")
    return n


def index_to_col(index: int) -> str:
    if not 1 <= index <= MAX_COL:
        raise ReferentSyntaxError(f"column index out of range: {index}")
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


# ---------------------------------------------------------------------------
# The object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Referent:
    kind: str
    sheet: Optional[str] = None
    name: Optional[str] = None          # sheetset name, or header text for namedcol
    row1: Optional[int] = None
    row2: Optional[int] = None
    col1: Optional[int] = None
    col2: Optional[int] = None

    def render(self) -> str:
        """Canonical surface form."""
        if self.kind == "workbook":
            return "workbook:"
        if self.kind == "sheetset":
            return f"sheetset:{self.name}"
        head = f"sheet:{_render_sheet_name(self.sheet or '')}"
        if self.kind == "sheet":
            return head
        return f"{head}!{self._render_span()}"

    def _render_span(self) -> str:
        k = self.kind
        if k == "namedcol":
            return f"@{self.name}"
        if k == "cell":
            return f"{index_to_col(self.col1)}{self.row1}"
        if k == "cellrange":
            return (f"{index_to_col(self.col1)}{self.row1}:"
                    f"{index_to_col(self.col2)}{self.row2}")
        if k == "row":
            return str(self.row1)
        if k == "rowrange":
            return f"{self.row1}:{self.row2}"
        if k == "col":
            return index_to_col(self.col1)
        if k == "colrange":
            return f"{index_to_col(self.col1)}:{index_to_col(self.col2)}"
        raise ValueError(f"unrenderable kind: {k}")

    def key(self) -> str:
        """Comparison key: two referents are the SAME referent iff keys match.

        Casefold + collapse internal whitespace over the canonical form. This is
        design v0's matcher, extended -- the grader compares on this.
        """
        return " ".join(self.render().casefold().split())

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.render()


def _render_sheet_name(name: str) -> str:
    if any(ch in _NEEDS_QUOTE for ch in name) or name == "":
        return "'" + name.replace("'", "''") + "'"
    return name


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_CELLRANGE = re.compile(r"([A-Za-z]{1,3})([1-9]\d*):([A-Za-z]{1,3})([1-9]\d*)")
_CELL = re.compile(r"([A-Za-z]{1,3})([1-9]\d*)")
_ROWRANGE = re.compile(r"([1-9]\d*):([1-9]\d*)")
_ROW = re.compile(r"[1-9]\d*")
_COLRANGE = re.compile(r"([A-Za-z]{1,3}):([A-Za-z]{1,3})")
_COL = re.compile(r"[A-Za-z]{1,3}")
_NAMED = re.compile(r"@(.+)", re.DOTALL)


def parse(text: str) -> Referent:
    raw = text.strip()
    if raw == "workbook:":
        return Referent(kind="workbook")
    if raw.startswith("sheetset:"):
        name = raw[len("sheetset:"):].strip()
        if not name:
            raise ReferentSyntaxError("empty sheetset name")
        return Referent(kind="sheetset", name=name)
    if not raw.startswith("sheet:"):
        raise ReferentSyntaxError(f"unknown referent prefix: {text!r}")

    sheet, span = _split_sheet_and_span(raw[len("sheet:"):])
    if span is None:
        return Referent(kind="sheet", sheet=sheet)
    return _parse_span(sheet, span)


def _split_sheet_and_span(rest: str) -> tuple[str, Optional[str]]:
    if rest.startswith("'"):
        buf: list[str] = []
        i = 1
        closed = False
        while i < len(rest):
            ch = rest[i]
            if ch == "'":
                if i + 1 < len(rest) and rest[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                closed = True
                i += 1
                break
            buf.append(ch)
            i += 1
        if not closed:
            raise ReferentSyntaxError("unterminated quoted sheet name")
        name = "".join(buf)
        remainder = rest[i:]
        if remainder == "":
            span = None
        elif remainder.startswith("!"):
            span = remainder[1:]
        else:
            raise ReferentSyntaxError(f"expected '!' after quoted sheet name: {rest!r}")
    else:
        if "!" in rest:
            name, span = rest.split("!", 1)
        else:
            name, span = rest, None
        # A bare name may not contain the characters that would make it
        # ambiguous -- those require quoting.
        if any(ch in _NEEDS_QUOTE for ch in name):
            raise ReferentSyntaxError(
                f"sheet name {name!r} must be quoted: contains one of space ! : '"
            )
    if not name:
        raise ReferentSyntaxError("empty sheet name")
    if span is not None and span == "":
        raise ReferentSyntaxError("empty span after '!'")
    return name, span


def _parse_span(sheet: str, span: str) -> Referent:
    m = _NAMED.fullmatch(span)
    if m:
        header = m.group(1).strip()
        if not header:
            raise ReferentSyntaxError("empty header name after '@'")
        return Referent(kind="namedcol", sheet=sheet, name=header)

    m = _CELLRANGE.fullmatch(span)
    if m:
        c1, r1, c2, r2 = col_to_index(m.group(1)), int(m.group(2)), col_to_index(m.group(3)), int(m.group(4))
        return Referent(kind="cellrange", sheet=sheet,
                        row1=min(r1, r2), row2=max(r1, r2),
                        col1=min(c1, c2), col2=max(c1, c2))

    m = _CELL.fullmatch(span)
    if m:
        return Referent(kind="cell", sheet=sheet,
                        row1=int(m.group(2)), col1=col_to_index(m.group(1)))

    m = _ROWRANGE.fullmatch(span)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return Referent(kind="rowrange", sheet=sheet, row1=min(a, b), row2=max(a, b))

    if _ROW.fullmatch(span):
        return Referent(kind="row", sheet=sheet, row1=int(span))

    m = _COLRANGE.fullmatch(span)
    if m:
        a, b = col_to_index(m.group(1)), col_to_index(m.group(2))
        return Referent(kind="colrange", sheet=sheet, col1=min(a, b), col2=max(a, b))

    if _COL.fullmatch(span):
        return Referent(kind="col", sheet=sheet, col1=col_to_index(span))

    raise ReferentSyntaxError(f"unparseable span: {span!r}")


def from_legacy_pointer(sheet: str, pointer: Mapping[str, object]) -> Referent:
    """Convert a Data-agents-demo `manual_recipe` source_pointer to a Referent.

    Legacy pointers are 0-BASED; this grammar is 1-based. The conversion lives
    here, once, with a test -- a silent off-by-one would mis-bind every field in
    a recipe while still producing a plausible table (spec sec.5).
    """
    if "column" in pointer:
        return Referent(kind="namedcol", sheet=sheet, name=str(pointer["column"]))
    if "row" in pointer and "col" in pointer:
        return Referent(
            kind="cell", sheet=sheet,
            row1=int(pointer["row"]) + 1, col1=int(pointer["col"]) + 1,
        )
    if "column_index" in pointer:
        return Referent(kind="col", sheet=sheet, col1=int(pointer["column_index"]) + 1)
    raise ReferentSyntaxError(f"unrecognised legacy pointer: {dict(pointer)!r}")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Resolution:
    ok: bool
    referent: Optional[Referent] = None
    sheet: Optional[str] = None          # the workbook's ACTUAL spelling
    sheets: Optional[tuple[str, ...]] = None   # for workbook:/sheetset:
    row1: Optional[int] = None
    row2: Optional[int] = None
    col1: Optional[int] = None
    col2: Optional[int] = None
    reason: Optional[str] = None
    detail: Optional[str] = None


class WorkbookView:
    """Read-only view of a workbook: sheet names, used range, header values."""

    def __init__(self, path: str | Path):
        from openpyxl import load_workbook  # imported here: parsing needs no deps

        self.path = Path(path)
        self._wb = load_workbook(self.path, data_only=True)
        self.sheet_names: tuple[str, ...] = tuple(self._wb.sheetnames)
        self._by_key = {n.casefold(): n for n in self.sheet_names}

    def actual_sheet(self, name: str) -> Optional[str]:
        return self._by_key.get(name.casefold())

    def dims(self, actual_sheet: str) -> tuple[int, int]:
        ws = self._wb[actual_sheet]
        return int(ws.max_row or 0), int(ws.max_column or 0)

    def row_values(self, actual_sheet: str, row: int) -> list[str]:
        ws = self._wb[actual_sheet]
        values = next(ws.iter_rows(min_row=row, max_row=row, values_only=True), ())
        return ["" if v is None else str(v).strip() for v in values]


def resolve(
    referent: Referent | str,
    wb: WorkbookView,
    header_rows: Optional[Mapping[str, int]] = None,
    sheetsets: Optional[Mapping[str, Sequence[str]]] = None,
) -> Resolution:
    """Resolve a referent against a workbook. Failure is a hard error."""
    if isinstance(referent, str):
        try:
            referent = parse(referent)
        except ReferentSyntaxError as exc:
            return Resolution(ok=False, reason="malformed", detail=str(exc))

    if referent.kind == "workbook":
        return Resolution(ok=True, referent=referent, sheets=wb.sheet_names)

    if referent.kind == "sheetset":
        declared = (sheetsets or {}).get(referent.name or "")
        if declared is None:
            return Resolution(ok=False, referent=referent, reason="sheetset_not_declared",
                              detail=referent.name)
        members: list[str] = []
        for member in declared:
            actual = wb.actual_sheet(member)
            if actual is None:
                return Resolution(ok=False, referent=referent, reason="sheet_not_found",
                                  detail=member)
            members.append(actual)
        return Resolution(ok=True, referent=referent, sheets=tuple(members))

    actual = wb.actual_sheet(referent.sheet or "")
    if actual is None:
        return Resolution(ok=False, referent=referent, reason="sheet_not_found",
                          detail=referent.sheet)
    max_row, max_col = wb.dims(actual)

    if referent.kind == "sheet":
        return Resolution(ok=True, referent=referent, sheet=actual,
                          row1=1, row2=max_row, col1=1, col2=max_col)

    if referent.kind == "namedcol":
        header_row = _header_row_for(actual, header_rows)
        if header_row is None:
            return Resolution(ok=False, referent=referent, sheet=actual,
                              reason="header_row_not_declared", detail=actual)
        if header_row > max_row:
            return Resolution(ok=False, referent=referent, sheet=actual,
                              reason="out_of_bounds",
                              detail=f"header row {header_row} > max_row {max_row}")
        wanted = (referent.name or "").casefold()
        hits = [i + 1 for i, v in enumerate(wb.row_values(actual, header_row))
                if v.casefold() == wanted]
        if not hits:
            return Resolution(ok=False, referent=referent, sheet=actual,
                              reason="header_not_found", detail=referent.name)
        if len(hits) > 1:
            # Refuse rather than take the first: picking one asserts what the
            # evidence does not establish.
            return Resolution(ok=False, referent=referent, sheet=actual,
                              reason="header_ambiguous",
                              detail=f"{referent.name} at columns {hits}")
        col = hits[0]
        return Resolution(ok=True, referent=referent, sheet=actual,
                          row1=1, row2=max_row, col1=col, col2=col)

    row1, row2 = referent.row1, referent.row2 or referent.row1
    col1, col2 = referent.col1, referent.col2 or referent.col1
    if referent.kind in ("row", "rowrange"):
        col1, col2 = 1, max_col
    if referent.kind in ("col", "colrange"):
        row1, row2 = 1, max_row

    if (row2 or 0) > max_row or (col2 or 0) > max_col:
        return Resolution(ok=False, referent=referent, sheet=actual, reason="out_of_bounds",
                          detail=f"used range is {max_row} rows x {max_col} cols")
    return Resolution(ok=True, referent=referent, sheet=actual,
                      row1=row1, row2=row2, col1=col1, col2=col2)


def _header_row_for(actual_sheet: str, header_rows: Optional[Mapping[str, int]]) -> Optional[int]:
    if not header_rows:
        return None
    for name, row in header_rows.items():
        if name.casefold() == actual_sheet.casefold():
            return int(row)
    return None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []
    seen_reasons: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- round-trip: parse -> render is the identity on canonical forms -------
    canonical = [
        "workbook:", "sheetset:Months", "sheet:Sales", "sheet:Sales!D5",
        "sheet:Sales!D5:P96", "sheet:Sales!5", "sheet:Sales!5:96",
        "sheet:Sales!D", "sheet:Sales!D:P", "sheet:Sales!@Myynti",
        "sheet:'Myynti 2026'!A1",
    ]
    for text in canonical:
        try:
            r = parse(text)
        except ReferentSyntaxError as exc:
            failures.append(f"canonical {text!r} failed to parse: {exc}")
            continue
        check(r.render() == text, f"round-trip {text!r} -> {r.render()!r}")
        check(r.kind in KINDS, f"unknown kind for {text!r}: {r.kind}")

    # --- comparison key ------------------------------------------------------
    check(parse("sheet:sales!d5").key() == parse("sheet:Sales!D5").key(),
          "key should be case-insensitive")
    check(parse("sheet:Sales!D5").key() != parse("sheet:Sales!D6").key(),
          "different cells must not share a key")
    check(parse("  sheet:Sales!D5  ").key() == parse("sheet:Sales!D5").key(),
          "surrounding whitespace must not matter")

    # --- quoting -------------------------------------------------------------
    check(parse("sheet:'Myynti 2026'!A1").sheet == "Myynti 2026", "quoted name lost")
    try:
        parse("sheet:Myynti 2026!A1")
        failures.append("a bare sheet name containing a space must be rejected")
    except ReferentSyntaxError:
        pass
    apostrophe = Referent(kind="sheet", sheet="O'Brien")
    check(apostrophe.render() == "sheet:'O''Brien'", f"apostrophe render: {apostrophe.render()}")
    check(parse(apostrophe.render()).sheet == "O'Brien", "apostrophe round-trip")

    # --- range ordering normalises -------------------------------------------
    check(parse("sheet:Sales!D5:B2").render() == "sheet:Sales!B2:D5", "cellrange must sort")
    check(parse("sheet:Sales!96:5").render() == "sheet:Sales!5:96", "rowrange must sort")
    check(parse("sheet:Sales!P:D").render() == "sheet:Sales!D:P", "colrange must sort")

    # --- 1-based enforcement -------------------------------------------------
    for bad in ("sheet:Sales!A0", "sheet:Sales!0", "sheet:Sales!0:5", "sheet:Sales!@", "sheet:!A1"):
        try:
            parse(bad)
            failures.append(f"{bad!r} must be rejected (1-based / non-empty)")
        except ReferentSyntaxError:
            pass

    # --- column letter maths -------------------------------------------------
    for letters, idx in (("A", 1), ("Z", 26), ("AA", 27), ("XFD", 16384)):
        check(col_to_index(letters) == idx, f"col_to_index({letters}) != {idx}")
        check(index_to_col(idx) == letters, f"index_to_col({idx}) != {letters}")

    # --- legacy 0-based conversion (spec sec.5) ------------------------------
    check(from_legacy_pointer("Sales", {"row": 0, "col": 0}).render() == "sheet:Sales!A1",
          "legacy (0,0) must be A1")
    check(from_legacy_pointer("Sales", {"row": 1, "col": 1}).render() == "sheet:Sales!B2",
          "legacy (1,1) must be B2")
    check(from_legacy_pointer("Sales", {"column": "Myynti"}).render() == "sheet:Sales!@Myynti",
          "legacy named column")

    # --- resolution against the real multi-sheet workbook --------------------
    fixture = ROOT / "fixtures" / "W1_multisheet.xlsx"
    if not fixture.exists():
        failures.append(f"fixture missing: {fixture} (run make_w1.py)")
    else:
        wb = WorkbookView(fixture)
        headers = {"Sales": 4, "Dup": 1, "Myynti 2026": 1}

        def res(text: str, **kw) -> Resolution:
            r = resolve(text, wb, header_rows=kw.pop("headers", headers), **kw)
            if r.reason:
                seen_reasons.add(r.reason)
            return r

        ok = res("sheet:Sales!A4")
        check(ok.ok and ok.sheet == "Sales" and (ok.row1, ok.col1) == (4, 1),
              f"Sales!A4 -> {ok}")

        lower = res("sheet:sales!A1")
        check(lower.ok and lower.sheet == "Sales",
              "sheet lookup must be case-insensitive and report actual spelling")

        named = res("sheet:Sales!@Tuote")
        check(named.ok and named.col1 == 1, f"@Tuote should resolve to column 1: {named}")
        named2 = res("sheet:Sales!@Yhteensä")
        check(named2.ok and named2.col1 == 5, f"@Yhteensä should be column 5: {named2}")

        nodecl = res("sheet:Sales!@Tuote", headers=None)
        check(nodecl.reason == "header_row_not_declared", f"expected header_row_not_declared: {nodecl}")

        ambig = res("sheet:Dup!@Myynti")
        check(ambig.reason == "header_ambiguous",
              f"duplicate headers must REFUSE, not pick the first: {ambig}")
        check("[2, 3]" in (ambig.detail or ""), f"ambiguity should name the columns: {ambig.detail}")

        check(res("sheet:Sales!@Nope").reason == "header_not_found", "missing header")
        check(res("sheet:Nope!A1").reason == "sheet_not_found", "missing sheet")
        check(res("sheet:Sales!G1").reason == "out_of_bounds", "col 7 > max_col 6")
        check(res("sheet:Sales!A10").reason == "out_of_bounds", "row 10 > max_row 9")
        check(res("sheet:Sales!(").reason == "malformed", "unparseable span")

        spaced = res("sheet:'Myynti 2026'!B2")
        check(spaced.ok and spaced.sheet == "Myynti 2026", f"spaced sheet: {spaced}")

        check(res("sheetset:Months").reason == "sheetset_not_declared", "undeclared sheetset")
        declared = resolve("sheetset:Months", wb,
                           sheetsets={"Months": ["2026-01", "2026-02"]})
        check(declared.ok and declared.sheets == ("2026-01", "2026-02"),
              f"declared sheetset: {declared}")

        whole = resolve("workbook:", wb)
        check(whole.ok and len(whole.sheets or ()) == 6, f"workbook: -> {whole.sheets}")

        sheet_only = res("sheet:Sales")
        check(sheet_only.ok and (sheet_only.row2, sheet_only.col2) == (9, 6),
              f"sheet: should span the used range: {sheet_only}")

        # Every declared failure reason must actually be exercised, so a reason
        # cannot be declared in the enum and never tested.
        untested = set(REASONS) - seen_reasons
        check(not untested, f"declared but untested failure reasons: {sorted(untested)}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (round-trips / keys / quoting + apostrophes / range ordering / "
        "1-based / column maths / legacy 0-based conversion / resolution on a real "
        "6-sheet workbook / all 7 failure reasons exercised incl. header_ambiguous)\n"
    )
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        raise SystemExit(_self_test())
    if argv and argv[0] == "--resolve":
        view = WorkbookView(argv[1])
        out = resolve(argv[2], view)
        print(out)
        raise SystemExit(0 if out.ok else 1)
    sys.stderr.write("usage: referents.py --self-test | --resolve <workbook.xlsx> <referent>\n")
    raise SystemExit(2)
