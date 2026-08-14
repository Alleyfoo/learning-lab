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

## Canary reachability

    A canary is valid only if the deliberately defective behaviour is
    demonstrated to have REACHED the invariant's observation point.

Learned the hard way. The second canary written here failed while the detector
was perfectly sound: its stimulus never crossed validation, so the invariant
observed nothing and correctly reported nothing. A canary that mutates something
and expects red, without proving the mutation arrived, is a reassuring ritual
that says nothing at all.

So every canary reports three things, and validity needs the first two:

    fired    the invariant reported a violation
    reached  the defective behaviour arrived at the observation point
    detail   what was seen
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
class CanaryResult:
    fired: bool
    reached: bool
    detail: str

    @property
    def valid(self) -> bool:
        return self.fired and self.reached


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
    # Reachability: this invariant observes EXECUTED output, so the defective
    # recipe must have crossed validation into the executor.
    return CanaryResult(
        fired=why is not None,
        reached=out.executed,
        detail=(why or ("stimulus never reached the observation point: the recipe "
                        f"was refused ({sorted(out.codes)})" if not out.executed
                        else "did NOT fire with the guard removed")))


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
    # Reachability: the mutated executor must actually have run AND emitted the
    # smuggled column, or the invariant was never given anything to catch.
    reached = out.executed and "smuggled" in (out.columns or [])
    return CanaryResult(
        fired=why is not None,
        reached=reached,
        detail=(why or ("stimulus never reached the observation point: "
                        f"executed={out.executed} columns={out.columns}"
                        if not reached else
                        "did NOT fire on an undeclared output column")))


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
# 3. No Undeclared Interpretation
# ---------------------------------------------------------------------------
#
# The observation boundary, stated explicitly because Excel makes it non-trivial:
#
#     compare the machine-readable TYPED VALUE ADMITTED BY INGESTION against the
#     TYPED VALUE EMITTED BY EXECUTION, under the accepted recipe.
#
# Not Excel's visual rendering. Comparing rendered text would treat FORMATTING as
# semantics -- a number 123 displayed as "00123" is not secretly the string
# "00123" -- and would drag this straight back into the review-rendering problem
# that approval provenance already solved.
#
# Value identity is (type, value).
#
# Three outcomes, and only the fourth is a defect:
#
#     declaration absent      preserve semantic identity
#     declaration supported   perform EXACTLY the declared interpretation
#     declaration ambiguous   refuse, or mark explicitly unhonoured
#     never                   guess
#
# The word doing the work is UNDECLARED. An invariant that forbade all
# interpretation would be No Interpretation, which is a different and useless
# property -- hence the inverse control in the canary.

def _typed(value) -> tuple:
    return (type(value).__name__, value)


def interpretation_violation(admitted, emitted, declared_type) -> Optional[str]:
    """Did a value acquire semantics the recipe never authorised?"""
    a_type, a_val = _typed(admitted)
    e_type, e_val = _typed(emitted)

    if declared_type in (None, "string"):
        # A declared string authorises REPRESENTATION as text and nothing else.
        # Not whitespace removal, not numeric parsing, not case folding.
        expected = "" if admitted is None else str(admitted)
        if e_val != expected:
            return (f"UNDECLARED INTERPRETATION: admitted {a_type}({a_val!r}) with "
                    f"declared type {declared_type!r}; a string declaration authorises "
                    f"representation as {expected!r}, but execution emitted "
                    f"{e_type}({e_val!r})")
        return None

    if declared_type == "number":
        # Numeric interpretation IS authorised here; only silence about failure
        # would be a defect, and that is no_partial_honour's business.
        return None

    if declared_type == "date":
        # The historical case. Without a format or locale there is no uniquely
        # correct answer, so the contract is: do not invent the missing one.
        if isinstance(admitted, str) and e_val != admitted:
            return (f"UNDECLARED INTERPRETATION: {a_val!r} declared as a date with no "
                    f"format or locale in the language, and execution emitted "
                    f"{e_type}({e_val!r}) rather than preserving it or marking it "
                    f"unhonoured")
        return None
    return None


def _canary_interpretation(tmp: Path):
    """A mutated executor coerces "00123" -> 123 under a string declaration.

    Plus the INVERSE CONTROL: with a numeric declaration the same coercion is
    authorised and must NOT fire. Without that control this would be building
    No Interpretation rather than No UNdeclared Interpretation.
    """
    admitted = "00123"

    fired_when_undeclared = interpretation_violation(admitted, 123, "string") is not None
    fired_when_declared = interpretation_violation(admitted, 123, "number") is not None

    if not fired_when_undeclared:
        return CanaryResult(False, True,
                            "did NOT fire on an undeclared string->int coercion")
    if fired_when_declared:
        return CanaryResult(False, True,
                            "fired even when the recipe DECLARED numeric coercion -- "
                            "this is No Interpretation, not No Undeclared Interpretation")
    return CanaryResult(
        fired=True, reached=True,
        detail="undeclared '00123'->123 caught; declared numeric coercion correctly allowed")


PRIMITIVES["no_undeclared_interpretation"] = Primitive(
    "no_undeclared_interpretation",
    "values may acquire only semantics explicitly authorised by the accepted "
    "recipe. Typed value in, typed value out; never a guess.",
    lambda case, out: None,          # driven by value_domains.py, which has the
                                     # admitted values; not a per-case check here
    _canary_interpretation)


# ---------------------------------------------------------------------------
# BOUNDARY A: no silent loss on admission
#
# The three primitives above all observe at or after ingestion, so none of them
# can see a source property destroyed on the way IN. Without this one, every
# invariant here could report green over an already corrupted representation.
# ---------------------------------------------------------------------------

def _canary_admission_loss(tmp: Path) -> CanaryResult:
    from admission import _canary_admission

    reached, fired, detail = _canary_admission(tmp)
    return CanaryResult(fired=fired, reached=reached, detail=detail)


PRIMITIVES["no_silent_loss_on_admission"] = Primitive(
    "no_silent_loss_on_admission",
    "source properties within the language's semantic budget must be preserved, "
    "explicitly normalised, or explicitly declared unavailable/unsupported — "
    "never collapsed into a different source fact.",
    lambda case, out: None,          # driven by admission.py, which reads the
                                     # source; not a per-case check here
    _canary_admission_loss)


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
                res = p.canary(tmp)
            except Exception as exc:
                res = CanaryResult(False, False, f"{type(exc).__name__}: {exc}")
            if not res.reached:
                problems.append(f"{name}: canary UNREACHABLE — the defective behaviour "
                                f"never arrived at the observation point: {res.detail}")
            elif not res.fired:
                problems.append(f"{name}: canary did not fire — {res.detail}")
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
            res = p.canary(tmp)
            mark = "ok  " if res.valid else "FAIL"
            sys.stdout.write(f"  {mark} canary {name:22} reached={str(res.reached):5} "
                             f"fired={str(res.fired):5} {res.detail[:42]}\n")

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
