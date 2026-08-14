#!/usr/bin/env python3
"""Evidence depth — generated variation around the parity invariants.

Not a level four. Level three (`semantic_parity.py`) already asks the last
structural question; this deepens the evidence behind it:

    proven by level 3      there is at least one passing demonstration per construct
    proven here            the invariant survives generated variation of its inputs
    still not proven       the invariant holds across the WHOLE input domain

Three things are kept conceptually apart, because collapsing them makes the
exercise quietly circular:

    generator   produces declarations and input shapes across four buckets
    oracle      states what must happen, computed from the contract with plain
                set/filter logic -- it NEVER asks the system under test
    system      validator -> dispatcher -> executor

**The system under test never generates its own oracle.** Where an exact expected
output is cheap (which labels survive an exclusion, how many rows an unpivot
yields), the oracle computes it directly. Where it is not, the property is
metamorphic: mutate a case in a controlled way and assert the delta, which needs
no knowledge of the whole correct table.

Refusal is part of the contract, not a test failure. Three states, and only the
third is a defect:

    accepted     -> the exact observable invariant holds
    unsupported  -> refused at the declared boundary
    NEVER        -> accepted and partially honoured

That third state is the beast. `no_partial_honour` is its universal check and is
the generalisation of LIM-4.

Counterexamples are kept verbatim in BOTH forms: the generated original, which
shows what realistic complexity exposed the defect, and the shrunk minimum, which
shows why it failed. Shrinking that discarded the original would be the same
mistake as overwriting a superseded run.
"""
from __future__ import annotations

import copy
import json
import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from execute_recipe import InsufficientRecipe, execute  # noqa: E402
from recipe import recipe_from_json  # noqa: E402
from referents import WorkbookView, index0_to_col  # noqa: E402
from validate_recipe import validate  # noqa: E402

BUCKETS = ("ordinary_valid", "boundary_valid", "invalid", "structurally_surprising")
CASES_PER_PROPERTY = 12
SEED = 20260814


# ---------------------------------------------------------------------------
# a generated case: workbook and recipe as DATA, so they can be shrunk and kept
# ---------------------------------------------------------------------------

@dataclass
class Case:
    bucket: str
    sheets: dict            # sheet name -> list of rows
    recipe: dict            # raw recipe json
    note: str = ""

    def as_dict(self) -> dict:
        return {"bucket": self.bucket, "note": self.note,
                "sheets": self.sheets, "recipe": self.recipe}


@dataclass
class Outcome:
    valid: bool
    codes: set
    columns: Optional[list]
    rows: Optional[list]
    unhonoured: list = field(default_factory=list)
    refused_reason: str = ""

    @property
    def executed(self) -> bool:
        return self.rows is not None


def _write(tmp: Path, sheets: dict, name: str = "gen") -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    first = True
    for title, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title)
        ws.title = title
        first = False
        for row in rows:
            ws.append(list(row))
    path = tmp / f"{name}.xlsx"
    wb.save(path)
    return path


def run_case(case: Case, tmp: Path) -> Outcome:
    """The system under test, end to end."""
    path = _write(tmp, case.sheets, f"c{abs(hash(json.dumps(case.sheets, sort_keys=True))) % 10**8}")
    raw = copy.deepcopy(case.recipe)
    r = recipe_from_json(raw)
    raw.setdefault("provenance", {})["approved_recipe_sha256"] = r.content_sha256()
    r = recipe_from_json(raw)
    wb = WorkbookView(path)
    report = validate(r, wb)
    if not report.valid:
        return Outcome(False, report.codes(), None, None,
                       refused_reason="validation refused")
    try:
        ex = execute(r, wb)
    except InsufficientRecipe as exc:
        return Outcome(True, report.codes(), None, None, refused_reason=str(exc))
    return Outcome(True, report.codes(), ex.columns, ex.rows, ex.unhonoured_types)


# ---------------------------------------------------------------------------
# recipe/workbook builders used by the generators
# ---------------------------------------------------------------------------

def _recipe(sheets: list[dict], **kw) -> dict:
    raw = {"recipe_version": 1, "recipe_id": "gen", "workbook": {}, "sheets": sheets,
           "applicability": None,
           "provenance": {"proposed_by": "generator", "approved_by": "generator",
                          "approved_recipe_sha256": None}}
    raw.update(kw)
    return raw


def _data_entry(sheet, fields, exclude=(), header=1, **kw):
    e = {"sheet": f"sheet:{sheet}", "role": "data",
         "header_row": f"sheet:{sheet}!{header}", "data_region": "remainder",
         "fields": fields, "exclude": list(exclude), "ambiguities": []}
    e.update(kw)
    return e


def _id_field(sheet, name="Tuote", target="id"):
    return {"target": target, "source": f"sheet:{sheet}!@{name}",
            "role": "id", "type": "string"}


# ---------------------------------------------------------------------------
# properties
# ---------------------------------------------------------------------------

@dataclass
class PropertyResult:
    name: str
    kind: str
    statement: str
    checked: int
    failures: list


PROPERTIES: list = []


def prop(name: str, kind: str, statement: str):
    def deco(fn):
        PROPERTIES.append((name, kind, statement, fn))
        return fn
    return deco


# ---- exact-oracle properties ----------------------------------------------

@prop("exclude:label_in", "exact oracle",
      "the surviving ids are exactly the source labels minus the excluded set, "
      "computed by plain set logic and never by asking the executor")
def _p_label_in(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        labels = [rng.choice(["A", "B", "C", "D", "E"]) for _ in range(rng.randint(2, 7))]
        if bucket == "boundary_valid":
            excluded = sorted(set(labels))          # exclude everything
        elif bucket == "structurally_surprising":
            excluded = ["ZZ"]                       # excludes nothing present
        else:
            excluded = rng.sample(sorted(set(labels)), k=min(2, len(set(labels))))
        rows = [["Tuote", "Arvo"]] + [[lab, n] for n, lab in enumerate(labels, start=1)]
        case = Case(bucket, {"S": rows}, _recipe([_data_entry(
            "S", [_id_field("S"), {"target": "v", "source": "sheet:S!B",
                                   "role": "measure", "type": "number"}],
            exclude=[{"rule": {"op": "label_in", "column": "sheet:S!@Tuote",
                               "values": excluded}, "reason": "generated"}])]),
            note=f"labels={labels} excluded={excluded}")

        # ORACLE: independent set logic. Never consults the system.
        expected = [lab for lab in labels if lab not in set(excluded)]

        out = run_case(case, tmp)
        if not out.executed:
            if expected:
                failures.append((case, f"refused with rows expected: {out.refused_reason} "
                                       f"{sorted(out.codes)}"))
            continue
        got = [row[out.columns.index("id")] for row in out.rows]
        if got != expected:
            failures.append((case, f"oracle {expected} != system {got}"))
    return failures


@prop("period_measure:cardinality+identity", "exact oracle",
      "n entities x m accepted measures produce exactly n*m rows AND each "
      "(entity, measure) pair appears exactly once -- a duplicate plus an "
      "omission cannot cancel out")
def _p_pm_identity(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        n = 1 if bucket == "boundary_valid" else rng.randint(2, 4)
        m = 1 if bucket == "boundary_valid" else rng.randint(2, 4)
        months = [f"M{j}" for j in range(1, m + 1)]
        rows = [["Tuote"] + months]
        for e in range(1, n + 1):
            rows.append([f"E{e}"] + [e * 10 + j for j in range(1, m + 1)])
        last = index0_to_col(m)
        case = Case(bucket, {"S": rows}, _recipe([_data_entry(
            "S", [_id_field("S"),
                  {"target": "v", "source": f"sheet:S!B:{last}",
                   "role": "period_measure", "type": "number",
                   "transform": {"op": "unpivot", "var_target": "kk",
                                 "value_target": "v"}}])]),
            note=f"{n} entities x {m} measures")

        # ORACLE: the cartesian product, computed here.
        expected = {(f"E{e}", months[j]) for e in range(1, n + 1) for j in range(m)}

        out = run_case(case, tmp)
        if not out.executed:
            failures.append((case, f"refused: {out.refused_reason} {sorted(out.codes)}"))
            continue
        pairs = [(row[out.columns.index("id")], row[out.columns.index("kk")])
                 for row in out.rows]
        if len(pairs) != n * m:
            failures.append((case, f"cardinality {len(pairs)} != {n * m}"))
        elif sorted(pairs) != sorted(expected):
            failures.append((case, f"identity mismatch: {sorted(set(pairs) ^ expected)}"))
    return failures


# ---- metamorphic properties -----------------------------------------------

def _base_case(rng, bucket, sheet="S", n=3):
    rows = [["Tuote", "A", "B"]] + [[f"E{e}", e, e * 2] for e in range(1, n + 1)]
    return Case(bucket, {sheet: rows}, _recipe([_data_entry(
        sheet, [_id_field(sheet),
                {"target": "v", "source": f"sheet:{sheet}!B:C",
                 "role": "period_measure", "type": "number",
                 "transform": {"op": "unpivot", "var_target": "kk", "value_target": "v"}}])]))


@prop("metamorphic:ignore_sheet", "metamorphic",
      "adding an arbitrary IGNORED sheet cannot change the output")
def _p_ignore(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        base = _base_case(rng, bucket, n=rng.randint(1, 4))
        before = run_case(base, tmp)
        after_case = copy.deepcopy(base)
        junk = [[rng.choice(["x", "y", 1, None])] for _ in range(rng.randint(1, 3))]
        pos = rng.choice(["before", "after"])
        name = f"Extra{i}"
        sheets = {name: junk, **after_case.sheets} if pos == "before" else {**after_case.sheets, name: junk}
        after_case.sheets = sheets
        after_case.recipe["sheets"].append(
            {"sheet": f"sheet:{name}", "role": "ignore", "reason": "generated"})
        after_case.note = f"ignored sheet added {pos} the data sheet"
        after = run_case(after_case, tmp)
        if before.rows != after.rows or before.columns != after.columns:
            failures.append((after_case, f"output changed: {before.rows} -> {after.rows}"))
    return failures


@prop("metamorphic:absent_exclusion", "metamorphic",
      "excluding a label that does not occur in the source cannot change the output")
def _p_absent_exclusion(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        base = _base_case(rng, bucket, n=rng.randint(1, 4))
        before = run_case(base, tmp)
        after_case = copy.deepcopy(base)
        after_case.recipe["sheets"][0]["exclude"].append(
            {"rule": {"op": "label_in", "column": "sheet:S!@Tuote",
                      "values": [f"NOT-PRESENT-{i}"]}, "reason": "generated"})
        after_case.note = "exclusion naming a label absent from the source"
        after = run_case(after_case, tmp)
        if before.rows != after.rows:
            failures.append((after_case, f"output changed: {before.rows} -> {after.rows}"))
    return failures


@prop("metamorphic:one_more_measure", "metamorphic",
      "adding one accepted measure column adds exactly one output row per entity")
def _p_one_more(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        n = rng.randint(1, 4)
        m = rng.randint(1, 3)
        def build(cols):
            rows = [["Tuote"] + [f"M{j}" for j in range(1, cols + 1)]]
            for e in range(1, n + 1):
                rows.append([f"E{e}"] + [e * 10 + j for j in range(1, cols + 1)])
            last = index0_to_col(cols)
            return Case(bucket, {"S": rows}, _recipe([_data_entry(
                "S", [_id_field("S"),
                      {"target": "v", "source": f"sheet:S!B:{last}",
                       "role": "period_measure", "type": "number",
                       "transform": {"op": "unpivot", "var_target": "kk",
                                     "value_target": "v"}}])]),
                note=f"{n} entities, {cols} measures")
        a = run_case(build(m), tmp)
        b = run_case(build(m + 1), tmp)
        if not (a.executed and b.executed):
            failures.append((build(m + 1), "one of the pair refused"))
            continue
        if len(b.rows) - len(a.rows) != n:
            failures.append((build(m + 1),
                             f"adding one measure changed the row count by "
                             f"{len(b.rows) - len(a.rows)}, expected {n}"))
    return failures


@prop("metamorphic:column_permutation", "metamorphic",
      "permuting UNRELATED columns leaves the output semantics unchanged as a set")
def _p_permute(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        n = rng.randint(1, 4)
        # Tuote | A | B | noise1 | noise2 -- the noise columns are excluded and
        # get permuted between runs.
        def build(order):
            head = ["Tuote", "A", "B"] + [f"N{k}" for k in order]
            rows = [head]
            for e in range(1, n + 1):
                rows.append([f"E{e}", e, e * 2] + [f"n{k}{e}" for k in order])
            return Case(bucket, {"S": rows}, _recipe([_data_entry(
                "S", [_id_field("S"),
                      {"target": "v", "source": "sheet:S!B:C",
                       "role": "period_measure", "type": "number",
                       "transform": {"op": "unpivot", "var_target": "kk",
                                     "value_target": "v"}}],
                exclude=[{"referent": f"sheet:S!@N{k}", "reason": "noise"} for k in order])]),
                note=f"noise column order {order}")
        a = run_case(build([1, 2]), tmp)
        b = run_case(build([2, 1]), tmp)
        if not (a.executed and b.executed):
            failures.append((build([2, 1]), "one of the pair refused"))
            continue
        if sorted(map(str, a.rows)) != sorted(map(str, b.rows)):
            failures.append((build([2, 1]), f"semantics changed: {a.rows} vs {b.rows}"))
    return failures


# ---- refusal-is-contract properties ---------------------------------------

@prop("refusal:unsupported_sheet_role", "refusal",
      "an unsupported sheet role is refused BEFORE execution, every time")
def _p_refuse_role(rng, tmp):
    failures = []
    for i in range(CASES_PER_PROPERTY):
        bucket = "invalid"
        case = _base_case(rng, bucket, n=rng.randint(1, 3))
        name = f"Meta{i}"
        case.sheets[name] = [["k", "v"], ["a", 1]]
        case.recipe["sheets"].append({"sheet": f"sheet:{name}", "role": "metadata"})
        case.note = "sheet declared with the unsupported 'metadata' role"
        out = run_case(case, tmp)
        if out.executed:
            failures.append((case, "executed instead of refusing an unsupported role"))
        elif "executor_cannot_honour" not in out.codes:
            failures.append((case, f"refused for the wrong reason: {sorted(out.codes)}"))
    return failures


@prop("refusal:ambiguous_date", "refusal",
      "a locale-ambiguous date is never silently converted: it is recorded as "
      "unhonoured or refused")
def _p_date(rng, tmp):
    failures = []
    ambiguous = ["3.2.2026", "01/02/2026", "2.3.26", "04-05-2026"]
    for i in range(CASES_PER_PROPERTY):
        bucket = BUCKETS[i % len(BUCKETS)]
        text = ambiguous[i % len(ambiguous)]
        rows = [["Raportti", text], [], ["Tuote", "A"], ["E1", 1]]
        case = Case(bucket, {"S": rows}, _recipe([_data_entry(
            "S", [{"target": "pvm", "source": "sheet:S!B1", "role": "metadata",
                   "type": "date"},
                  _id_field("S"),
                  {"target": "v", "source": "sheet:S!B", "role": "measure",
                   "type": "number"}],
            exclude=[{"referent": "sheet:S!1:2", "reason": "preamble"}], header=3)]),
            note=f"ambiguous date {text!r}")
        out = run_case(case, tmp)
        if not out.executed:
            continue                       # refusal is a valid implementation
        value = out.rows[0][out.columns.index("pvm")]
        recorded = any(t["target"] == "pvm" for t in out.unhonoured)
        if value != text or not recorded:
            failures.append((case, f"date {text!r} became {value!r}, "
                                   f"unhonoured recorded={recorded}"))
    return failures


# ---- the universal property ------------------------------------------------

def no_partial_honour(case: Case, out: Outcome) -> Optional[str]:
    """The generalisation of LIM-4.

        accepted    -> every accepted declaration is honoured
        refused     -> nothing took effect
        NEVER       -> a subset of accepted semantics silently took effect

    Checked by declaration, not by row count: every declared target must appear
    in the output, so an omission cannot be masked by a duplicate elsewhere.
    """
    if not out.executed:
        return None
    expected: set[str] = set()
    for entry in case.recipe["sheets"]:
        if entry.get("role") != "data":
            continue
        for f in entry.get("fields", []):
            tr = f.get("transform") or {}
            if tr.get("op") == "unpivot":
                expected.add(tr.get("var_target"))
                expected.add(tr.get("value_target"))
            else:
                expected.add(f.get("target"))
    missing = sorted(t for t in expected if t and t not in set(out.columns or []))
    if missing:
        return (f"accepted and PARTIALLY HONOURED: declared {sorted(expected)}, "
                f"output columns {out.columns}, missing {missing}")
    return None


# ---------------------------------------------------------------------------
# shrinking — keep BOTH the original and the minimum
# ---------------------------------------------------------------------------

def shrink(case: Case, fails: Callable[[Case], bool], tmp: Path) -> Case:
    current = copy.deepcopy(case)
    changed = True
    while changed:
        changed = False
        for sheet in list(current.sheets):
            rows = current.sheets[sheet]
            if len(rows) > 2:                       # keep header + one data row
                trial = copy.deepcopy(current)
                trial.sheets[sheet] = rows[:-1]
                if fails(trial):
                    current, changed = trial, True
                    continue
        for idx, entry in enumerate(current.recipe.get("sheets", [])):
            for key in ("exclude",):
                items = entry.get(key) or []
                if items:
                    trial = copy.deepcopy(current)
                    trial.recipe["sheets"][idx][key] = items[:-1]
                    if fails(trial):
                        current, changed = trial, True
    return current


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run_all(seed: int = SEED) -> dict:
    results: list[PropertyResult] = []
    partial_failures: list = []
    counterexamples: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rng = random.Random(seed)

        # every generated case is also checked against the universal property
        generated: list[Case] = []
        original_run = run_case

        def traced(case: Case, t: Path) -> Outcome:
            out = original_run(case, t)
            generated.append(case)
            why = no_partial_honour(case, out)
            if why:
                partial_failures.append((case, why))
            return out

        globals()["run_case"] = traced
        try:
            for name, kind, statement, fn in PROPERTIES:
                fails = fn(rng, tmp)
                results.append(PropertyResult(name, kind, statement,
                                              CASES_PER_PROPERTY, fails))
                for case, detail in fails:
                    def still_fails(c: Case, _fn=fn) -> bool:
                        out = original_run(c, tmp)
                        return no_partial_honour(c, out) is not None or True
                    counterexamples.append({
                        "property": name, "detail": detail,
                        "generated_original": case.as_dict(),
                        "shrunk_minimal": shrink(case, still_fails, tmp).as_dict(),
                    })
        finally:
            globals()["run_case"] = original_run

    for case, why in partial_failures:
        counterexamples.append({"property": "no_partial_honour", "detail": why,
                                "generated_original": case.as_dict(),
                                "shrunk_minimal": case.as_dict()})

    total_fail = sum(len(r.failures) for r in results) + len(partial_failures)
    return {"seed": seed, "cases_generated": len(generated),
            "properties": [{"name": r.name, "kind": r.kind, "statement": r.statement,
                            "checked": r.checked, "failed": len(r.failures)}
                           for r in results],
            "no_partial_honour": {"checked": len(generated),
                                  "failed": len(partial_failures)},
            "counterexamples": counterexamples,
            "total_failures": total_fail}


def canary() -> tuple[bool, str]:
    """Prove the universal property can detect the defect it generalises.

    An all-green property suite is evidence of nothing until it is shown to fail
    when it should. So: remove the LIM-4 guard, feed the suite the two-unpivot
    shape that caused it, and require `no_partial_honour` to fire. If this canary
    ever passes silently, the suite has stopped testing anything.
    """
    import validate_recipe as vr

    rows = [["Tuote", "a1", "a2", "b1", "b2"], ["E1", 1, 2, 10, 20]]
    case = Case("regression", {"S": rows}, _recipe([_data_entry(
        "S", [_id_field("S"),
              {"target": "a", "source": "sheet:S!B:C", "role": "period_measure",
               "type": "number",
               "transform": {"op": "unpivot", "var_target": "ka", "value_target": "a"}},
              {"target": "b", "source": "sheet:S!D:E", "role": "period_measure",
               "type": "number",
               "transform": {"op": "unpivot", "var_target": "kb", "value_target": "b"}}])]),
        note="LIM-4 shape with the guard removed")

    original = vr.MAX_UNPIVOTS_PER_SHEET
    with tempfile.TemporaryDirectory() as td:
        try:
            vr.MAX_UNPIVOTS_PER_SHEET = 99          # remove the guard
            out = run_case(case, Path(td))
        finally:
            vr.MAX_UNPIVOTS_PER_SHEET = original
    why = no_partial_honour(case, out)
    if why is None:
        return False, ("the canary did NOT fire: with the guard removed the suite "
                       f"failed to notice partial honour (executed={out.executed}, "
                       f"columns={out.columns})")
    return True, why


def _self_test() -> int:
    ok, detail = canary()
    sys.stdout.write(f"  {'ok  ' if ok else 'FAIL'} {'canary: guard removed':36} "
                     f"{'teeth':12} {detail[:66]}\n")
    out = run_all()
    for p in out["properties"]:
        mark = "ok  " if p["failed"] == 0 else "FAIL"
        sys.stdout.write(f"  {mark} {p['name']:36} {p['kind']:12} "
                         f"{p['checked'] - p['failed']}/{p['checked']}\n")
    npc = out["no_partial_honour"]
    mark = "ok  " if npc["failed"] == 0 else "FAIL"
    sys.stdout.write(f"  {mark} {'no_partial_honour':36} {'universal':12} "
                     f"{npc['checked'] - npc['failed']}/{npc['checked']}\n")

    if not ok:
        sys.stderr.write("\nCANARY FAILED — the suite cannot detect the defect "
                         "class it was built for, so its green results mean "
                         "nothing\n")
        return 1
    if out["total_failures"]:
        path = HERE.parent / "results" / "parity_counterexamples.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.stderr.write(f"\n{out['total_failures']} failure(s); counterexamples "
                         f"(original AND shrunk) written to {path}\n")
        return 1
    sys.stdout.write(f"\nPROPERTY PARITY PASSED — {out['cases_generated']} generated cases "
                     f"across {len(out['properties'])} properties, plus "
                     f"no_partial_honour on every one\n")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--json"]:
        print(json.dumps(run_all(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    raise SystemExit(_self_test())
