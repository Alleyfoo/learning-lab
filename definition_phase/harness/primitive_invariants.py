#!/usr/bin/env python3
"""Primitive invariants — the layer with the weakest semantic assumptions.

Three test layers, kept apart because they fail differently:

```text
rich oracle          understands intended language semantics
                     powerful, and vulnerable to author misunderstanding
metamorphic oracle   understands only expected change / invariance
                     narrower assumptions
primitive invariant  compares a DECLARATION against its observable consequence
                     weakest assumptions: "you declared this effect; did it exist?"
```

The bottom layer earns its place empirically, not aesthetically. PRO-2 instance 8
was found by a primitive invariant **while the rich oracle was wrong in 177
places**. A property that does not route through the author's model of the
language keeps working when that model is mistaken.

## Every primitive invariant must have a canary

    The canary validates the DETECTOR, not the domain coverage.

That sentence is methodology here, not commentary on one test. A primitive
invariant that has never been observed to fire might be discriminating, or might
be wired wrong and reporting green regardless of behaviour — and those look
identical from the outside. So each one registers a **known violation it must
detect**, and `assert_canaries_fire()` fails if any invariant cannot catch its
own mutation.

What a canary establishes is narrow and worth stating exactly:

    established      the invariant is sensitive to at least one known violation
    NOT established  the generator can reach every violating shape
"""
from __future__ import annotations

import copy
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))


@dataclass
class Primitive:
    name: str
    statement: str
    check: Callable                     # (case, outcome) -> violation str | None
    canary: Callable                    # (tmp) -> (fired: bool, detail: str)


PRIMITIVES: dict[str, Primitive] = {}


def primitive(name: str, statement: str, canary: Callable):
    def deco(fn):
        PRIMITIVES[name] = Primitive(name, statement, fn, canary)
        return fn
    return deco


def _declared_targets(case) -> set:
    """Output effects the recipe declares, by declaration rather than by count."""
    expected: set = set()
    for entry in case.recipe.get("sheets", []):
        if entry.get("role") != "data":
            continue
        for f in entry.get("fields", []):
            tr = f.get("transform") or {}
            if tr.get("op") == "unpivot":
                expected.add(tr.get("var_target"))
                expected.add(tr.get("value_target"))
            else:
                expected.add(f.get("target"))
    return {t for t in expected if t}


# ---------------------------------------------------------------------------
# 1. No Partial Honour
# ---------------------------------------------------------------------------

def _canary_partial(tmp: Path):
    """Remove the guards that close LIM-4 and instance 8, then require a catch."""
    import validate_recipe as vr
    from parity_properties import Case, _data_entry, _id_field, _recipe, run_case

    rows = [["Tuote", "a1", "a2"], ["E1", 1, 2]]
    case = Case("canary", {"S": rows}, _recipe([_data_entry(
        "S", [_id_field("S"),
              {"target": "v", "source": "sheet:S!B:C", "role": "id", "type": "string",
               "transform": {"op": "unpivot", "var_target": "kk", "value_target": "v"}}])]),
        note="id x unpivot with the pairing guard removed")

    original_pairing, original_max = vr.pairing_reason, vr.MAX_UNPIVOTS_PER_SHEET
    try:
        vr.pairing_reason = lambda *a, **k: None      # remove the guard
        vr.MAX_UNPIVOTS_PER_SHEET = 99
        out = run_case(case, tmp)
    finally:
        vr.pairing_reason, vr.MAX_UNPIVOTS_PER_SHEET = original_pairing, original_max

    why = no_partial_honour(case, out)
    return (why is not None), (why or "did NOT fire with the guard removed")


@primitive("no_partial_honour",
           "either every accepted declaration is honoured, or the recipe is refused "
           "before authoritative execution. Never a subset silently taking effect.",
           _canary_partial)
def no_partial_honour(case, out) -> Optional[str]:
    if not out.executed:
        return None
    expected = _declared_targets(case)
    missing = sorted(t for t in expected if t not in set(out.columns or []))
    if missing:
        return (f"accepted and PARTIALLY HONOURED: declared {sorted(expected)}, "
                f"output columns {out.columns}, missing {missing}")
    return None


# ---------------------------------------------------------------------------
# 2. No Undeclared Output
# ---------------------------------------------------------------------------

def _canary_undeclared(tmp: Path):
    """Make the executor emit a column nobody declared, and require a catch."""
    import parity_properties as pp
    from parity_properties import Case, _data_entry, _id_field, _recipe, run_case

    rows = [["Tuote", "A"], ["E1", 1]]
    case = Case("canary", {"S": rows}, _recipe([_data_entry(
        "S", [_id_field("S"),
              {"target": "v", "source": "sheet:S!B", "role": "measure", "type": "number"}])]),
        note="executor mutated to emit an undeclared column")

    # Patch the binding run_case actually uses. `from x import y` creates a new
    # name in the importing module, so patching the source module would leave the
    # caller untouched -- the first version of this canary did exactly that, and
    # the canary framework caught it. Which is the point of canaries.
    original = pp.execute

    def mutated(recipe, wb):
        ex = original(recipe, wb)
        ex.columns = list(ex.columns) + ["smuggled"]
        ex.rows = [list(r) + ["x"] for r in ex.rows]
        return ex

    try:
        pp.execute = mutated
        out = run_case(case, tmp)
    finally:
        pp.execute = original

    why = no_undeclared_output(case, out)
    return (why is not None), (why or "did NOT fire on an undeclared output column")


@primitive("no_undeclared_output",
           "every output column traces to a declaration. Execution may not invent "
           "an effect the accepted recipe never asked for.",
           _canary_undeclared)
def no_undeclared_output(case, out) -> Optional[str]:
    if not out.executed:
        return None
    declared = _declared_targets(case)
    extra = sorted(c for c in (out.columns or []) if c not in declared)
    if extra:
        return (f"UNDECLARED OUTPUT: columns {extra} appear in the result but are "
                f"declared nowhere in the recipe (declared {sorted(declared)})")
    return None


# ---------------------------------------------------------------------------
# canary enforcement
# ---------------------------------------------------------------------------

def assert_canaries_fire() -> list[str]:
    """Every registered primitive must detect its own known violation."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, p in sorted(PRIMITIVES.items()):
            try:
                fired, detail = p.canary(tmp)
            except Exception as exc:
                fired, detail = False, f"{type(exc).__name__}: {exc}"
            if not fired:
                problems.append(f"{name}: canary did not fire — {detail}")
    return problems


def check_all(case, out) -> list[str]:
    """Every primitive, against one case. Used by the generators."""
    return [why for p in PRIMITIVES.values()
            if (why := p.check(case, out)) is not None]


def _self_test() -> int:
    problems = assert_canaries_fire()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, p in sorted(PRIMITIVES.items()):
            fired, detail = p.canary(tmp)
            mark = "ok  " if fired else "FAIL"
            sys.stdout.write(f"  {mark} canary {name:24} {detail[:64]}\n")

    if problems:
        sys.stderr.write("\nCANARIES FAILED — a primitive invariant that cannot detect "
                         "its own known violation proves nothing when it reports "
                         "green:\n  " + "\n  ".join(problems) + "\n")
        return 1
    sys.stdout.write(
        f"\nPRIMITIVE INVARIANTS: {len(PRIMITIVES)} registered, every canary fires.\n"
        "  established:     each invariant is sensitive to at least one known violation\n"
        "  NOT established: that the generators reach every violating shape\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
