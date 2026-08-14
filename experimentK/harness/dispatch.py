#!/usr/bin/env python3
"""Experiment K — front-door dispatch.

Implements the algorithm frozen in `spec/preregistration.md` sec."Dispatch
algorithm". The spec is authority; if this file and the spec disagree, this file
is wrong.

    [1] LOOKUP        by FORMAT (do the recipe's data sheets exist?), never by
                      filename.  0 -> DEFINE, >=2 -> AMBIGUOUS, 1 -> R
    [2] APPLICABILITY re-validate R against the candidate. No field binding
                      resolves -> DEFINE. Any binding/coverage problem ->
                      REDEFINE_SCOPED with the delta named. Else -> [3]
    [3] APPROVAL      content hash == approved hash, approved_by set, no
                      blocking ambiguity -> EXECUTE.  Otherwise -> BLOCKED

**No model is invoked in the EXECUTE branch** -- or anywhere else in K.

The applicability predicate is not a new artifact: it is the step-2 recipe
validator re-run against the candidate file. A recipe already declares
everything its correctness depends on, so re-validation answers "does this still
apply?" and the problem codes say what drifted.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
sys.path.insert(0, str(LAB / "definition_phase" / "harness"))

from recipe import Recipe, load_recipe  # noqa: E402
from referents import WorkbookView, parse  # noqa: E402
from validate_recipe import Problem, validate  # noqa: E402

OUTCOMES = ("EXECUTE", "REDEFINE_SCOPED", "DEFINE", "AMBIGUOUS", "BLOCKED")

BINDING_CODES = ("unresolvable_referent",)
COVERAGE_CODES = (
    "column_unclassified", "row_unclassified", "sheet_unclassified",
    "column_double_bound", "row_double_classified",
    # v1.2. `spec/v12_row_shape.md` requires the front door to treat a row-shape
    # violation as a coverage problem. Omitting it here made the first v1.2 run
    # report FAIL_FIX: the validator raised the violation and the dispatcher
    # ignored it, so C13 executed. Code-deviates-from-frozen-spec is a bug under
    # the fidelity policy; run 1 is preserved in
    # `results/superseded/K_v12_run1_spec_deviation.json`.
    "row_shape_violation",
    # v1.3. The freeze states this explicitly, because v1.2 run 1 failed by
    # adding a code in one layer and not consuming it in this one.
    "reconciliation_failure",
)


@dataclass
class Dispatch:
    outcome: str
    recipe_id: Optional[str] = None
    reason: str = ""
    delta: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"outcome": self.outcome, "recipe_id": self.recipe_id,
                "reason": self.reason, "delta": self.delta,
                "candidates": self.candidates}


def _data_sheet_names(recipe: Recipe, wb: Optional[WorkbookView] = None) -> list[str]:
    """Sheet names a recipe binds as data. Sheetsets expand to their members."""
    names: list[str] = []
    for entry in recipe.data_sheets():
        try:
            ref = parse(entry.sheet)
        except Exception:
            continue
        if ref.kind == "sheetset":
            names.extend(recipe.sheetsets.get(ref.name or "", ()))
        elif ref.kind == "sheet" and ref.sheet:
            names.append(ref.sheet)
    return names


def lookup(wb: WorkbookView, store: Sequence[Recipe]) -> list[Recipe]:
    """Recipes whose data sheets ALL exist in the candidate.

    The FORMAT is the key. The filename is never consulted -- that is DA-2.
    """
    present = {n.casefold() for n in wb.sheet_names}
    matches = []
    for r in store:
        needed = _data_sheet_names(r)
        if needed and all(n.casefold() in present for n in needed):
            matches.append(r)
    return matches


def _approval_state(recipe: Recipe, problems: Sequence[Problem]) -> tuple[bool, str]:
    prov = recipe.provenance or {}
    if any(p.code == "blocking_ambiguity" for p in problems):
        return False, "a blocking ambiguity is still open"
    if not prov.get("approved_by"):
        return False, "recipe is not approved"
    approved_hash = prov.get("approved_recipe_sha256")
    if not approved_hash:
        return False, "no approved content hash recorded"
    actual = recipe.content_sha256()
    if actual != approved_hash:
        return False, (f"recipe was edited after approval "
                       f"({actual[:12]}… != {str(approved_hash)[:12]}…)")
    return True, "approval intact"


def dispatch(wb: WorkbookView, store: Sequence[Recipe]) -> Dispatch:
    # [1] LOOKUP -- by format, never by filename
    matches = lookup(wb, store)
    if not matches:
        return Dispatch("DEFINE", reason="no recipe binds a data sheet present in this workbook")
    if len(matches) > 1:
        return Dispatch("AMBIGUOUS", reason=f"{len(matches)} recipes claim this workbook",
                        candidates=[r.recipe_id for r in matches])
    recipe = matches[0]

    # [2] APPLICABILITY -- the step-2 validator, re-run against this file
    report = validate(recipe, wb)
    binding = [p for p in report.problems if p.code in BINDING_CODES]
    coverage = [p for p in report.problems if p.code in COVERAGE_CODES]

    if binding:
        bound_sources = [f.source for e in recipe.data_sheets() for f in e.fields if f.source]
        broken = {p.detail.split(" -> ")[0] for p in binding}
        if bound_sources and all(src in broken for src in bound_sources):
            # Nothing carried over; scoping a recipe that binds nothing would be
            # a fiction.
            return Dispatch("DEFINE", recipe_id=recipe.recipe_id,
                            reason="no field binding resolves against this workbook",
                            delta=[str(p) for p in binding])

    if binding or coverage:
        return Dispatch("REDEFINE_SCOPED", recipe_id=recipe.recipe_id,
                        reason="the recipe no longer fully accounts for this workbook",
                        delta=[f"{p.code}: {p.detail}" for p in binding + coverage])

    # [3] APPROVAL -- the gate owns authority
    ok, why = _approval_state(recipe, report.problems)
    if not ok:
        return Dispatch("BLOCKED", recipe_id=recipe.recipe_id, reason=why)
    return Dispatch("EXECUTE", recipe_id=recipe.recipe_id, reason=why)


def load_store(paths: Mapping[str, str | Path]) -> dict[str, Recipe]:
    return {name: load_recipe(ROOT / p) for name, p in paths.items()}


if __name__ == "__main__":
    argv = sys.argv[1:]
    if len(argv) >= 2:
        view = WorkbookView(argv[0])
        recipes = [load_recipe(p) for p in argv[1:]]
        print(json.dumps(dispatch(view, recipes).to_dict(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    sys.stderr.write("usage: dispatch.py <workbook.xlsx> <recipe.json> [recipe.json ...]\n")
    raise SystemExit(2)
