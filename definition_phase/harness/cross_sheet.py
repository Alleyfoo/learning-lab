#!/usr/bin/env python3
"""Cross-sheet law 1 — No Undeclared Duplicate Contribution.

## Source identity is ORIGIN, never content

The trap this module is built to avoid is the exact structural twin of the
observation-boundary mistake the value work caught:

```text
Sheet A contents == Sheet B contents   =>   Sheet A == Sheet B      WRONG
```

Two genuinely different sheets can hold byte-identical data and remain two
distinct sources; the same cells can be reached through two different referent
paths. So identity is *where a value came from*, not what it says:

```text
SourceAtom          workbook, sheet identity, row, column
SourceContribution  declaration_id, referent_path, atom, output_effect
```

which separates three cases that look alike from the output side:

```text
same values, different source atoms   -> potentially legitimate, two contributions
same source atom, two declared paths  -> duplication / aliasing question
same source atom, one path            -> ordinary
```

## The law

Deliberately narrow — **No Undeclared Duplicate Contribution**, not "no duplicate
contribution", because the language may one day intentionally allow a source to
be used twice:

> A source atom may affect authoritative output through each explicitly
> authorised semantic relationship, but reaching the same atom through an
> additional undeclared/aliasing path must not silently duplicate its effect.

## The metamorphic test

```text
baseline:  data sheet S through path P            -> O
mutation:  same S reachable through P and Q
required:  validation refuses the ambiguous relationship
       or  output remains semantically O (P and Q recognised as aliases)
never:     O + O
```

No rich oracle needed, which is the point.

**Reachability is enforced before the result is believed:** P and Q must be shown
to resolve to the *same* `SourceAtom` set. Otherwise Q quietly pointed at a
copied sheet and the run measured nothing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView, parse, resolve  # noqa: E402
from validate_recipe import validate  # noqa: E402
from execute_recipe import InsufficientRecipe, execute  # noqa: E402


@dataclass(frozen=True)
class SourceAtom:
    """Where a value came from. Never what it says.

    `sheet` is the ACTUAL sheet name resolved by the workbook, not the referent
    spelling — `sheet:Sales` and `sheet:SALES` name one origin, and that is the
    whole reason this type exists rather than comparing referent strings.
    """
    workbook: str
    sheet: str
    row0: int
    col0: int


@dataclass(frozen=True)
class SourceContribution:
    declaration_id: str        # which declaration reached it
    referent_path: str         # the referent text as written
    atom: SourceAtom
    output_effect: str         # the output column it feeds


def contributions(recipe, wb: WorkbookView) -> list[SourceContribution]:
    """Every (declaration, path, atom, effect) the recipe would realise.

    Resolution goes through the authoritative `resolve()`, so an alias the
    resolver treats as one origin is seen here as one atom.
    """
    out: list[SourceContribution] = []
    book = str(wb.path.resolve())
    for i, entry in enumerate(recipe.sheets):
        ref = parse(entry.sheet)
        if ref.kind != "sheet":
            continue                       # sheetsets: law 2, not this one
        actual = wb.actual_sheet(ref.sheet or "")
        if actual is None:
            continue
        header_ref = parse(entry.header_row) if entry.header_row else None
        header_rows0 = {actual: header_ref.row0} if header_ref else {}
        n_rows, _ = wb.dims(actual)
        for fld in entry.fields:
            if not fld.source:
                continue                   # derived fields have no source atom
            r = resolve(fld.source, wb, header_rows0=header_rows0)
            if not r.ok:
                continue
            rows = range(r.row0, min(r.row0_last, n_rows - 1) + 1)
            for col0 in range(r.col0, r.col0_last + 1):
                for row0 in rows:
                    out.append(SourceContribution(
                        declaration_id=f"sheet[{i}]:{entry.sheet}:field:{fld.target}",
                        referent_path=fld.source,
                        atom=SourceAtom(book, actual, row0, col0),
                        output_effect=fld.target))
    return out


def aliased_atoms(contribs: list[SourceContribution]) -> dict[SourceAtom, set[str]]:
    """Atoms reached by more than one DISTINCT referent path."""
    paths: dict[SourceAtom, set[str]] = {}
    for c in contribs:
        paths.setdefault(c.atom, set()).add(c.referent_path)
    return {a: p for a, p in paths.items() if len(p) > 1}


def assert_same_origin(wb: WorkbookView, path_p: str, path_q: str,
                       header_rows0: Optional[dict] = None) -> tuple[bool, str]:
    """REACHABILITY: do P and Q genuinely name the same origin?

    Without this a run can spend hours proving that a second path pointed at a
    copied sheet. That mistake has been made enough times here to be worth a
    dedicated check.
    """
    rp = resolve(path_p, wb, header_rows0=header_rows0 or {})
    rq = resolve(path_q, wb, header_rows0=header_rows0 or {})
    if not (rp.ok and rq.ok):
        return False, f"unresolvable: {path_p}={rp.ok} {path_q}={rq.ok}"
    same = (rp.sheet == rq.sheet and rp.row0 == rq.row0 and rp.row0_last == rq.row0_last
            and rp.col0 == rq.col0 and rp.col0_last == rq.col0_last)
    detail = (f"{path_p} -> {rp.sheet}[{rp.row0}:{rp.row0_last},{rp.col0}:{rp.col0_last}] | "
              f"{path_q} -> {rq.sheet}[{rq.row0}:{rq.row0_last},{rq.col0}:{rq.col0_last}]")
    return same, detail


# ---------------------------------------------------------------------------
# the metamorphic corpus
# ---------------------------------------------------------------------------

def _fields(sheet_ref: str) -> list[dict]:
    return [{"target": "tuote", "source": f"{sheet_ref}!@Tuote", "role": "id",
             "type": "string"},
            {"target": "myynti", "source": f"{sheet_ref}!@Myynti", "role": "measure",
             "type": "number"}]


def _entry(sheet_ref: str, fields: list[dict]) -> dict:
    return {"sheet": sheet_ref, "role": "data", "header_row": f"{sheet_ref}!1",
            "data_region": "remainder", "fields": fields, "exclude": [],
            "ambiguities": []}


def _recipe(entries: list[dict]) -> dict:
    return {"recipe_version": 1, "recipe_id": "xsheet", "workbook": {},
            "sheets": entries, "applicability": None,
            "provenance": {"proposed_by": "xsheet", "approved_by": "xsheet",
                           "approved_recipe_sha256": None}}


def _make_wb(tmp: Path, tag: str, sheets: dict[str, list[list]]) -> Path:
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    wb = Workbook()
    first = True
    for name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = name
        first = False
        for row in rows:
            ws.append(row)
    wb.save(path)
    return path


def _outcome(path: Path, raw: dict) -> dict:
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    r = recipe_from_json(raw)
    view = WorkbookView(path)
    report = validate(r, view)
    if not report.valid:
        return {"refused": True, "codes": sorted(report.codes())}
    try:
        ex = execute(r, view)
    except InsufficientRecipe as exc:
        return {"refused": True, "codes": [f"executor: {exc}"]}
    return {"refused": False, "columns": list(ex.columns),
            "rows": [list(x) for x in ex.rows]}


SALES = [["Tuote", "Myynti"], ["A", 1], ["B", 2]]


def case_sheet_name_case(tmp: Path) -> dict:
    """P = `sheet:Sales`, Q = `sheet:SALES`. Sheet lookup is case-insensitive."""
    path = _make_wb(tmp, "alias_case", {"Sales": SALES})
    view = WorkbookView(path)
    same, detail = assert_same_origin(view, "sheet:Sales!A1", "sheet:SALES!A1")

    baseline = _outcome(path, _recipe([_entry("sheet:Sales", _fields("sheet:Sales"))]))
    mutated = _outcome(path, _recipe([_entry("sheet:Sales", _fields("sheet:Sales")),
                                      _entry("sheet:SALES", _fields("sheet:SALES"))]))
    return {"case": "sheet_name_case", "same_origin": same, "origin_detail": detail,
            "baseline": baseline, "mutated": mutated,
            "paths": ["sheet:Sales", "sheet:SALES"]}


def case_named_vs_positional(tmp: Path) -> dict:
    """P = `@Tuote`, Q = `A:A`. Two spellings of one column."""
    path = _make_wb(tmp, "alias_col", {"Sales": SALES})
    view = WorkbookView(path)
    same, detail = assert_same_origin(view, "sheet:Sales!@Tuote", "sheet:Sales!A:A",
                                      header_rows0={"Sales": 0})

    baseline = _outcome(path, _recipe([_entry("sheet:Sales", _fields("sheet:Sales"))]))
    doubled = _fields("sheet:Sales") + [
        {"target": "tuote_again", "source": "sheet:Sales!A:A", "role": "id",
         "type": "string"}]
    mutated = _outcome(path, _recipe([_entry("sheet:Sales", doubled)]))
    return {"case": "named_vs_positional", "same_origin": same, "origin_detail": detail,
            "baseline": baseline, "mutated": mutated,
            "paths": ["sheet:Sales!@Tuote", "sheet:Sales!A:A"]}


def case_distinct_sheets_same_content(tmp: Path) -> dict:
    """CONTROL, in the other direction. Identical CONTENT, distinct ORIGINS.

    Two sheets holding byte-identical data are two sources. If the law fired
    here it would be identifying sources by content, which is the whole mistake
    this module exists to avoid.
    """
    path = _make_wb(tmp, "twins", {"Jan": SALES, "Feb": [r[:] for r in SALES]})
    view = WorkbookView(path)
    same, detail = assert_same_origin(view, "sheet:Jan!A1", "sheet:Feb!A1")

    baseline = _outcome(path, _recipe([_entry("sheet:Jan", _fields("sheet:Jan"))]))
    both = _outcome(path, _recipe([_entry("sheet:Jan", _fields("sheet:Jan")),
                                   _entry("sheet:Feb", _fields("sheet:Feb"))]))
    return {"case": "distinct_sheets_same_content", "same_origin": same,
            "origin_detail": detail, "baseline": baseline, "mutated": both,
            "paths": ["sheet:Jan", "sheet:Feb"], "control": True}


CASES = [case_sheet_name_case, case_named_vs_positional, case_distinct_sheets_same_content]


def _verdict(result: dict) -> tuple[str, str]:
    """refuse | aliases_recognised | DUPLICATED | (control) legitimate."""
    base, mut = result["baseline"], result["mutated"]
    if result.get("control"):
        if not result["same_origin"] and not mut["refused"]:
            return "legitimate", ("distinct origins both contributed, as they should; "
                                  "the law did not fire on identical content")
        if result["same_origin"]:
            return "CONTROL FAILED", "distinct sheets were treated as one origin"
        return "legitimate", f"refused: {mut.get('codes')}"

    if not result["same_origin"]:
        return "UNREACHABLE", ("the two paths do not resolve to the same origin, so "
                               "this case tests nothing: " + result["origin_detail"])
    if mut["refused"]:
        return "refuse", f"validation refused the aliased relationship: {mut['codes']}"
    n_base = len(base.get("rows", []))
    n_mut = len(mut.get("rows", []))
    if n_mut > n_base and base.get("rows") and \
            mut["rows"][:n_base] == base["rows"] and n_mut == 2 * n_base:
        return "DUPLICATED", (f"the same origin contributed twice: {n_base} rows became "
                              f"{n_mut}, the baseline output repeated verbatim")
    if mut.get("rows") == base.get("rows"):
        return "aliases_recognised", "output unchanged; the two paths were treated as one"
    return "DUPLICATED", (f"output changed without refusal: {n_base} -> {n_mut} rows")


def run_all() -> dict:
    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for case in CASES:
            r = case(tmp)
            verdict, why = _verdict(r)
            results.append({**r, "verdict": verdict, "why": why})
    bad = [r for r in results
           if r["verdict"] in ("DUPLICATED", "UNREACHABLE", "CONTROL FAILED")]
    return {"cases": len(results), "results": results, "violations": bad}


# ---------------------------------------------------------------------------
# canary — before the corpus, as always
# ---------------------------------------------------------------------------

def duplicate_contribution_violation(contribs: list[SourceContribution],
                                     emitted_rows: int, baseline_rows: int
                                     ) -> Optional[str]:
    """The detector: an aliased atom whose effect was realised more than once."""
    aliased = aliased_atoms(contribs)
    if aliased and emitted_rows > baseline_rows:
        atom, paths = next(iter(aliased.items()))
        return (f"UNDECLARED DUPLICATE CONTRIBUTION: {atom.sheet}"
                f"[{atom.row0},{atom.col0}] reached by {sorted(paths)}; output grew "
                f"{baseline_rows} -> {emitted_rows} rows")
    return None


def _canary_duplicate(tmp: Path) -> tuple[bool, bool, str]:
    """A mutated executor appends one contribution per referent path.

    Reachability is checked FIRST and reported separately: both paths must
    genuinely resolve to the same SourceAtom, or the canary is testing an
    unrelated sheet and its green means nothing.
    """
    path = _make_wb(tmp, "canary_dup", {"Sales": SALES})
    view = WorkbookView(path)

    same, detail = assert_same_origin(view, "sheet:Sales!A1", "sheet:SALES!A1")
    if not same:
        return False, False, f"CANARY UNREACHABLE: paths differ in origin — {detail}"

    raw = _recipe([_entry("sheet:Sales", _fields("sheet:Sales")),
                   _entry("sheet:SALES", _fields("sheet:SALES"))])
    r = recipe_from_json(raw)
    contribs = contributions(r, view)
    if not aliased_atoms(contribs):
        return False, False, ("CANARY UNREACHABLE: no atom is reached by two paths, "
                              "so the detector is never offered a violation")

    # The mutation: contribution counted once per path, no origin de-duplication.
    baseline_rows = 2
    emitted_rows = 4
    why = duplicate_contribution_violation(contribs, emitted_rows, baseline_rows)
    fired = why is not None

    # INVERSE CONTROL: with no aliasing, growth alone must NOT be reported.
    solo = recipe_from_json(_recipe([_entry("sheet:Sales", _fields("sheet:Sales"))]))
    control = duplicate_contribution_violation(contributions(solo, view), 4, 2)
    if control is not None:
        return True, False, f"INVERSE CONTROL FAILED: fired without aliasing: {control}"
    return True, fired, (why or "detector did not fire")[:110]


def _self_test() -> int:
    with tempfile.TemporaryDirectory() as td:
        reached, fired, detail = _canary_duplicate(Path(td))
    sys.stdout.write(f"  canary duplicate_contribution  reached={reached}  fired={fired}\n"
                     f"    {detail}\n\n")
    if not (reached and fired):
        sys.stdout.write("CANARY FAILED — the corpus below would be meaningless\n")
        return 1

    out = run_all()
    for r in out["results"]:
        sys.stdout.write(f"  {r['verdict']:20} {r['case']:30} same_origin={r['same_origin']}\n"
                         f"      {r['why'][:100]}\n")
    results = HERE.parent / "results"
    results.mkdir(parents=True, exist_ok=True)
    n = 1
    while (results / f"cross_sheet_law1_run{n}.json").exists():
        n += 1
    (results / f"cross_sheet_law1_run{n}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(f"\n  written to cross_sheet_law1_run{n}.json\n")

    if out["violations"]:
        sys.stdout.write("\nNO UNDECLARED DUPLICATE CONTRIBUTION — VIOLATED\n")
        return 1
    sys.stdout.write("\nLAW 1 HELD on every case in this corpus\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
