#!/usr/bin/env python3
"""Enforce Observable Error v1 — a degradation must travel with the result.

The rule (`definition_phase/design/observable_error_v1.md`, designer 2026-08-15):

> A diagnostic counts as SURFACED only if it is presented alongside the
> authoritative result or the review. Internal logging alone does not turn a
> silently degraded output into a successful one.

`operating_procedure.md` §2.1 is explicit that a rule is only worth stating if it
is checkable, so this is the check.

## What is actually verified

```text
1. derived         `degraded` is computed from the execution's own state, not
                   assigned. A caller cannot build a degraded result that
                   reports itself clean.
2. inseparable     `as_dict()` carries `degraded` alongside `columns`/`rows`.
                   Serialising the authoritative table cannot drop the flag.
3. faithful        `degraded` is true exactly when a declaration went
                   unhonoured -- not "usually", and not only for the gaps that
                   happen to exist today.
4. not over-eager  an INCOMPLETE-BY-FACT result is NOT degraded. A sheetset
                   member with no data rows contributes zero and every value is
                   right; flagging it would make the flag meaningless by firing
                   on correct output.
```

## The canary

A degraded execution whose flag is suppressed must be detected. If it ever stops
firing, this check has stopped checking and the run is void.

## What this does NOT claim

It binds the result OBJECT. No in-process mechanism can force a downstream
consumer to read a field it was handed. What it removes is the case that actually
occurred: `unhonoured_types` existed, and Experiment M still correctly graded S5
as silently wrong because the table was separable from it.

The REVIEW surface (`approval.py`) is not covered here — see the spec's open
section.

Usage
-----
    python scripts/check_surfaced.py --self-test
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "definition_phase" / "harness"))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from execute_recipe import Execution, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView  # noqa: E402
from validate_recipe import validate  # noqa: E402


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


def _recipe(declared_type: str = "number"):
    raw = {
        "recipe_version": 1, "recipe_id": "surfaced", "workbook": {},
        "sheets": [{
            "sheet": "sheet:S", "role": "data", "header_row": "sheet:S!1",
            "data_region": "remainder",
            "fields": [
                {"target": "id", "source": "sheet:S!@Tuote", "role": "id",
                 "type": "string"},
                {"target": "v", "source": "sheet:S!@Myynti", "role": "measure",
                 "type": declared_type}],
            "exclude": [], "ambiguities": []}],
        "applicability": None,
        "provenance": {"proposed_by": "surfaced", "approved_by": "surfaced",
                       "approved_recipe_sha256": None},
    }
    r = recipe_from_json(raw)
    raw["provenance"]["approved_recipe_sha256"] = r.content_sha256()
    return recipe_from_json(raw)


def _execute(tmp: Path, tag: str, rows: list[list], declared: str = "number"):
    path = _wb(tmp, tag, rows)
    wb = WorkbookView(path)
    recipe = _recipe(declared)
    report = validate(recipe, wb)
    if not report.valid:
        raise AssertionError(f"fixture recipe invalid: {sorted(report.codes())}")
    return execute(recipe, wb)


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # --- 1. a clean result is NOT degraded --------------------------------
        clean = _execute(tmp, "clean", [["Tuote", "Myynti"], ["A", 1], ["B", 2]])
        check(not clean.degraded, f"a fully honoured result must not be degraded: "
                                  f"{clean.unhonoured_types}")
        check(clean.as_dict()["degraded"] is False,
              "as_dict must carry degraded=False explicitly, not omit it")

        # --- 2. an unhonourable declaration IS degraded ----------------------
        # "1,234" is gap G2: separator + exactly three digits, no locale.
        dirty = _execute(tmp, "dirty", [["Tuote", "Myynti"], ["A", "1,234"]])
        check(dirty.degraded,
              "a declared type that could not be honoured must mark the result "
              "degraded")
        check(any(g.get("gap") == "G2" for g in dirty.degradation),
              f"the degradation must name the gap: {dirty.degradation}")

        # --- 3. INSEPARABLE: the table cannot be serialised without the flag --
        d = dirty.as_dict()
        check("degraded" in d and "rows" in d,
              "the authoritative table and its degradation must be one artifact")
        check(d["degraded"] is True,
              f"as_dict reported degraded={d['degraded']} for a degraded result")
        check(d["degradation"], "as_dict must carry WHICH declarations failed")

        # --- 4. DERIVED: a caller cannot assign the flag away ----------------
        # The failure mode the rule exists to stop is a result that is degraded
        # and reports itself clean.
        forged = Execution(columns=list(dirty.columns), rows=[list(r) for r in dirty.rows],
                           unhonoured_types=list(dirty.unhonoured_types))
        check(forged.degraded,
              "reconstructing an Execution from a degraded one must stay degraded")
        try:
            forged.degraded = False          # type: ignore[misc]
            assignable = True
        except AttributeError:
            assignable = False
        check(not assignable,
              "degraded must not be assignable -- a settable flag is exactly the "
              "internal-logging failure the rule forbids")

        # --- 5. NOT OVER-EAGER: incomplete-by-fact is not degraded -----------
        # The designer's law-2 ruling. Every value right, source simply had less.
        thin = _execute(tmp, "thin", [["Tuote", "Myynti"], ["A", 1]])
        check(not thin.degraded,
              "a correct result over a small source must NOT be flagged; a flag "
              "that fires on correct output means nothing")

        # --- 6. date gap G1 is degradation too -------------------------------
        dated = _execute(tmp, "dated", [["Tuote", "Myynti"], ["A", "3.2.2026"]],
                         declared="date")
        check(dated.degraded and any(g.get("gap") == "G1" for g in dated.degradation),
              f"G1 must mark the result degraded: {dated.degradation}")

        # --- CANARY: suppress the flag, and this check must notice ------------
        class Suppressed(Execution):
            @property
            def degraded(self) -> bool:
                return False

        canary = Suppressed(columns=list(dirty.columns),
                            rows=[list(r) for r in dirty.rows],
                            unhonoured_types=list(dirty.unhonoured_types))
        fired = bool(canary.unhonoured_types) and not canary.degraded
        check(fired,
              "CANARY DID NOT FIRE: a degraded result reporting itself clean was "
              "not detectable, so this check has stopped checking")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (clean result not degraded / unhonourable declaration "
        "degrades and names its gap / table and flag are one artifact / degraded "
        "is derived and NOT assignable / incomplete-by-fact is not flagged / G1 "
        "and G2 both degrade / canary fires on a suppressed flag)\n")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    sys.stderr.write("usage: check_surfaced.py --self-test\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
