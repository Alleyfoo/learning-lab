#!/usr/bin/env python3
"""Normalisation parity — a construct performs exactly what it declares.

The fix for PRO-2 instance 9 turned normalisation from a helper sitting
underneath every construct into something a construct **declares**. That fix is
worth nothing unless the declaration and the behaviour are checked against each
other, so:

> If a construct declares normalisation `N`, execution performs exactly `N`.
> If no normalisation is declared, the admitted value is preserved.

**Every probe drives the authoritative path** — build a workbook, validate,
execute, observe. None of them call `normalize_for`. Asking the implementation
whether it obeys its own table would be letting the implementation generate its
own oracle, which is the mistake this programme keeps refusing to make.

## How a normalisation is identified by behaviour alone

Two independent dimensions, each observed as "do these two inputs behave the
same?":

```text
                  whitespace   case
none                  no        no
trim_whitespace      yes        no
trim_casefold        yes       yes
```

That table is what makes the test discriminating: it separates all three
declared normalisations without reading which one was declared.

**A dimension that does not exist for a construct is reported `n/a`, never
passed.** Blankness and numeric parsing have no case dimension, and claiming a
pass there would be a vacuous green.
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

from executor_contract import CONSTRUCT_NORMALIZATION  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402
from execute_recipe import InsufficientRecipe, execute  # noqa: E402

# Behaviour expected of each declared normalisation, by observation only.
EXPECTED = {
    "none":            {"whitespace": False, "case": False},
    "trim_whitespace": {"whitespace": True,  "case": False},
    "trim_casefold":   {"whitespace": True,  "case": True},
}


def _recipe(fields: list[dict], *, exclude: Optional[list] = None,
            shape: Optional[dict] = None) -> dict:
    entry: dict[str, Any] = {"sheet": "sheet:S", "role": "data",
                             "header_row": "sheet:S!1", "data_region": "remainder",
                             "fields": fields, "exclude": exclude or [],
                             "ambiguities": []}
    if shape:
        entry["data_row_shape"] = shape
    return {"recipe_version": 1, "recipe_id": "norm", "workbook": {},
            "sheets": [entry], "applicability": None,
            "provenance": {"proposed_by": "norm", "approved_by": "norm",
                           "approved_recipe_sha256": None}}


def _run(tmp: Path, tag: str, rows: list[list], raw: dict) -> dict:
    """Build, validate, execute. Returns an OBSERVATION, never raises."""
    from openpyxl import Workbook

    path = tmp / f"{tag}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    for row in rows:
        ws.append(row)
    wb.save(path)

    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    r = recipe_from_json(raw)

    view = WorkbookView(path)
    report = validate(r, view)
    if not report.valid:
        return {"valid": False, "codes": sorted(report.codes())}
    try:
        ex = execute(r, view)
    except InsufficientRecipe as exc:
        return {"valid": True, "executed": False, "detail": str(exc)}
    return {"valid": True, "executed": True,
            "columns": list(ex.columns), "rows": [list(x) for x in ex.rows]}


# --- probes: each returns (whitespace_tolerant, case_tolerant, detail) -------
# True  = the two inputs behaved IDENTICALLY (the difference was normalised away)
# False = they behaved differently (the difference was preserved)
# "n/a" = the dimension does not exist for this construct

def _p_field_value(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
         {"target": "v", "source": "sheet:S!@V", "role": "measure", "type": "string"}]

    def emitted(value: str) -> Any:
        out = _run(tmp, f"fv{abs(hash(value))}", [["Tuote", "V"], ["E1", value]], _recipe(f))
        return out.get("rows", [[None, None]])[0][-1]

    ws = emitted(" x ") == emitted("x")
    case = emitted("X") == emitted("x")
    return ws, case, f"' x '->{emitted(' x ')!r}  'x'->{emitted('x')!r}"


def _p_header_label(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"}]

    def resolves(header: str) -> bool:
        return _run(tmp, f"hl{abs(hash(header))}", [[header], ["E1"]], _recipe(f)).get("valid", False)

    base = resolves("Tuote")
    ws = resolves(" Tuote ") == base
    case = resolves("TUOTE") == base
    return ws, case, f"'Tuote'={base} ' Tuote '={resolves(' Tuote ')} 'TUOTE'={resolves('TUOTE')}"


def _p_label_in(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"}]
    exc = [{"rule": {"op": "label_in", "column": "sheet:S!@Tuote", "values": ["total"]},
            "reason": "grand total row, matched by label"}]

    def excluded(cell: str) -> bool:
        out = _run(tmp, f"li{abs(hash(cell))}", [["Tuote"], ["E1"], [cell]],
                   _recipe(f, exclude=exc))
        return len(out.get("rows", [])) == 1     # only E1 survives

    ws = excluded(" total ")
    case = excluded("Total")
    return ws, case, f"' total ' excluded={ws}  'Total' excluded={case}"


def _p_blank_detection(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
         {"target": "v", "source": "sheet:S!@V", "role": "measure", "type": "string"}]
    shape = {"require_non_blank": ["sheet:S!@V"]}

    def refused(value: str) -> bool:
        out = _run(tmp, f"bd{abs(hash(value))}", [["Tuote", "V"], ["E1", value]],
                   _recipe(f, shape=shape))
        return not out.get("valid", False)

    # " " behaving like "" means whitespace was normalised away for the predicate.
    ws = refused(" ") == refused("")
    return ws, "n/a", f"' ' refused={refused(' ')}  '' refused={refused('')}  'x' refused={refused('x')}"


def _p_numeric_parse(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
         {"target": "v", "source": "sheet:S!@V", "role": "measure", "type": "string"}]
    shape = {"require_numeric": ["sheet:S!@V"]}

    def accepted(value: str) -> bool:
        return _run(tmp, f"np{abs(hash(value))}", [["Tuote", "V"], ["E1", value]],
                    _recipe(f, shape=shape)).get("valid", False)

    ws = accepted(" 1,5 ") == accepted("1,5")
    return ws, "n/a", f"' 1,5 ' ok={accepted(' 1,5 ')}  '1,5' ok={accepted('1,5')}"


def _p_boolean_parse(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
         {"target": "v", "source": "sheet:S!@V", "role": "measure", "type": "boolean"}]

    def emitted(value: str) -> Any:
        out = _run(tmp, f"bp{abs(hash(value))}", [["Tuote", "V"], ["E1", value]], _recipe(f))
        return out.get("rows", [[None, None]])[0][-1]

    ws = emitted(" true ") == emitted("true")
    case = emitted("TRUE") == emitted("true")
    return ws, case, f"' true '->{emitted(' true ')!r} 'TRUE'->{emitted('TRUE')!r}"


def _p_unpivot_var_label(tmp: Path) -> tuple:
    f = [{"target": "id", "source": "sheet:S!@Tuote", "role": "id", "type": "string"},
         {"target": "m", "source": "sheet:S!B:B", "role": "period_measure",
          "type": "number", "transform": {"op": "unpivot", "var_target": "kk",
                                          "value_target": "m"}}]

    def label(header: str) -> Any:
        out = _run(tmp, f"uv{abs(hash(header))}", [["Tuote", header], ["E1", 1]], _recipe(f))
        rows = out.get("rows") or [[None, None, None]]
        cols = out.get("columns") or []
        return rows[0][cols.index("kk")] if "kk" in cols else None

    ws = label(" kk1 ") == label("kk1")
    case = label("KK1") == label("kk1")
    return ws, case, f"' kk1 '->{label(' kk1 ')!r}  'KK1'->{label('KK1')!r}"


def _p_sheetset_header_parity(tmp: Path) -> tuple:
    # Sheetsets are UNSUPPORTED by the executor contract, so this construct
    # cannot be driven through the authoritative path. Reported as unreachable
    # rather than passed -- the same rule the canaries live under.
    return "unreachable", "unreachable", "sheetsets are outside the executable language"


PROBES: dict[str, Callable[[Path], tuple]] = {
    "field_value": _p_field_value,
    "header_label": _p_header_label,
    "label_in": _p_label_in,
    "blank_detection": _p_blank_detection,
    "numeric_parse": _p_numeric_parse,
    "boolean_parse": _p_boolean_parse,
    "unpivot_var_label": _p_unpivot_var_label,
    "sheetset_header_parity": _p_sheetset_header_parity,
}


def assert_probes_total() -> None:
    """Every declared construct must be probed, and only declared ones."""
    declared, probed = set(CONSTRUCT_NORMALIZATION), set(PROBES)
    if declared - probed:
        raise RuntimeError(f"constructs declaring a normalisation but never probed: "
                           f"{sorted(declared - probed)}")
    if probed - declared:
        raise RuntimeError(f"probes for constructs that declare no normalisation: "
                           f"{sorted(probed - declared)}")


def run_all() -> dict:
    assert_probes_total()
    results: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for construct, probe in sorted(PROBES.items()):
            declared = CONSTRUCT_NORMALIZATION[construct]
            want = EXPECTED[declared]
            ws, case, detail = probe(tmp)
            observed = {"whitespace": ws, "case": case}
            if ws == "unreachable":
                verdict = "unreachable"
            else:
                mismatch = [d for d in ("whitespace", "case")
                            if observed[d] != "n/a" and observed[d] != want[d]]
                verdict = "ok" if not mismatch else "MISMATCH:" + ",".join(mismatch)
            results.append({"construct": construct, "declares": declared,
                            "expected": want, "observed": observed,
                            "verdict": verdict, "detail": detail})
    return {"results": results,
            "ok": sum(1 for r in results if r["verdict"] == "ok"),
            "unreachable": sum(1 for r in results if r["verdict"] == "unreachable"),
            "mismatches": [r for r in results if r["verdict"].startswith("MISMATCH")]}


def _self_test() -> int:
    out = run_all()
    for r in out["results"]:
        o = r["observed"]
        sys.stdout.write(f"  {r['verdict'][:9]:10} {r['construct']:24} "
                         f"declares {r['declares']:16} "
                         f"ws={str(o['whitespace']):11} case={o['case']}\n")
    sys.stdout.write(f"\n  {out['ok']} construct(s) behave exactly as declared, "
                     f"{out['unreachable']} unreachable, "
                     f"{len(out['mismatches'])} mismatch(es)\n")
    (HERE.parent / "results").mkdir(parents=True, exist_ok=True)
    (HERE.parent / "results" / "normalization_parity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if out["mismatches"]:
        sys.stdout.write("\nNORMALIZATION PARITY FAILED\n")
        for m in out["mismatches"]:
            sys.stdout.write(f"  {m['construct']}: {m['detail']}\n")
        return 1
    sys.stdout.write("\nNORMALIZATION PARITY PASSED — every reachable construct "
                     "performs exactly the normalisation it declares\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
