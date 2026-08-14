#!/usr/bin/env python3
"""Mutation testing the primitive invariants — who watches the watchmen.

A canary proves an invariant catches **one** known violation. It does not prove
the invariant is load-bearing: a detector could be firing for an incidental
reason, or three of its four conditions could be dead code. The question a
canary cannot answer is:

> If I damage this detector, does anything notice?

So each primitive's detector is deliberately broken, one mutation at a time, and
the canary is re-run. A mutation that leaves every canary green is a **surviving
mutant** — the detector contains logic nothing depends on, and the green is worth
less than it appeared.

```text
canary            the detector catches a known violation
mutation          the detector STOPS catching it when damaged
                  -> the detector's logic is actually load-bearing
```

Mutations are applied by monkey-patching the module under test and always undone
in a `finally`, so a failure here cannot leave a damaged detector installed for
the rest of the suite.

## What this does not establish

That the detectors catch every violating shape — that was never claimed and is
not claimed now. Mutation testing measures whether the *existing* logic is
necessary, not whether it is sufficient.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

import admission  # noqa: E402
import primitive_invariants as PI  # noqa: E402


# --- mutations: (primitive, name, install) ----------------------------------
# `install` damages the detector and returns a callable that restores it.

def _mut_partial_always_none():
    """no_partial_honour never reports anything."""
    original = PI.no_partial_honour
    PI.PRIMITIVES["no_partial_honour"].__dict__  # noqa: B018  (dataclass is frozen)
    PI.no_partial_honour = lambda case, out: None
    _swap_check("no_partial_honour", lambda case, out: None)
    return lambda: (_swap_check("no_partial_honour", original),
                    setattr(PI, "no_partial_honour", original))


def _mut_undeclared_output_always_none():
    """no_undeclared_output never reports anything."""
    original = PI.no_undeclared_output
    PI.no_undeclared_output = lambda case, out: None
    _swap_check("no_undeclared_output", lambda case, out: None)
    return lambda: (_swap_check("no_undeclared_output", original),
                    setattr(PI, "no_undeclared_output", original))


def _mut_interpretation_always_none():
    """interpretation_violation never reports anything."""
    original = PI.interpretation_violation
    PI.interpretation_violation = lambda admitted, emitted, declared: None
    return lambda: setattr(PI, "interpretation_violation", original)


def _mut_interpretation_ignores_type():
    """Compare by str() instead of by (type, value) — drops value identity.

    The subtle one: '123' and 123 stop being different values, so a coercion
    under a declared string becomes invisible while the detector still LOOKS
    like it is checking something.
    """
    original = PI.interpretation_violation

    def weakened(admitted, emitted, declared_type):
        if str(admitted if admitted is not None else "") == str(emitted):
            return None
        return original(admitted, emitted, declared_type)

    PI.interpretation_violation = weakened
    return lambda: setattr(PI, "interpretation_violation", original)


def _mut_admission_always_none():
    """admission_loss never reports anything."""
    original = admission.admission_loss
    admission.admission_loss = lambda source, admitted: None
    return lambda: setattr(admission, "admission_loss", original)


def _mut_admission_ignores_cache():
    """Treat a formula as fine whenever it is a formula, cached or not.

    This is the exact mistake the boundary exists to prevent: it makes
    'formula with no cached result' indistinguishable from 'formula that
    computed something', which is how the collapse happened in the first place.
    """
    original = admission.admission_loss

    def weakened(source, admitted):
        if source.kind == "formula":
            return None
        return original(source, admitted)

    admission.admission_loss = weakened
    return lambda: setattr(admission, "admission_loss", original)


def _swap_check(name: str, fn) -> None:
    """Replace a registered primitive's check (the dataclass is frozen)."""
    p = PI.PRIMITIVES[name]
    PI.PRIMITIVES[name] = PI.Primitive(p.name, p.statement, fn, p.canary)


MUTATIONS: list[tuple[str, str, Callable]] = [
    ("no_partial_honour", "detector always returns None", _mut_partial_always_none),
    ("no_undeclared_output", "detector always returns None", _mut_undeclared_output_always_none),
    ("no_undeclared_interpretation", "detector always returns None",
     _mut_interpretation_always_none),
    ("no_undeclared_interpretation", "compares by str(), dropping (type, value) identity",
     _mut_interpretation_ignores_type),
    ("no_silent_loss_on_admission", "detector always returns None", _mut_admission_always_none),
    ("no_silent_loss_on_admission", "treats any formula as fine, cached or not",
     _mut_admission_ignores_cache),
]


def _canary_state(name: str) -> tuple[bool, bool, str]:
    with tempfile.TemporaryDirectory() as td:
        try:
            res = PI.PRIMITIVES[name].canary(Path(td))
        except Exception as exc:                      # a crash is a detection
            return False, True, f"{type(exc).__name__}: {exc}"
    return res.reached, res.fired, res.detail


def run_all() -> dict:
    results: list[dict] = []
    for target, description, install in MUTATIONS:
        before_reached, before_fired, _ = _canary_state(target)
        restore = install()
        try:
            after_reached, after_fired, detail = _canary_state(target)
        finally:
            restore()
        healthy_reached, healthy_fired, _ = _canary_state(target)

        # KILLED: the canary noticed the damage. SURVIVED: it did not.
        killed = before_fired and not after_fired
        results.append({
            "primitive": target, "mutation": description,
            "canary_before": {"reached": before_reached, "fired": before_fired},
            "canary_after": {"reached": after_reached, "fired": after_fired},
            "verdict": "killed" if killed else "SURVIVED",
            "restored_ok": healthy_reached and healthy_fired,
            "detail": detail[:100],
        })
    survivors = [r for r in results if r["verdict"] == "SURVIVED"]
    not_restored = [r for r in results if not r["restored_ok"]]
    return {"mutations": len(results), "killed": len(results) - len(survivors),
            "survivors": survivors, "not_restored": not_restored, "results": results}


def _self_test() -> int:
    out = run_all()
    for r in out["results"]:
        sys.stdout.write(f"  {r['verdict']:9} {r['primitive']:30} {r['mutation'][:46]}\n")
    sys.stdout.write(f"\n  {out['killed']}/{out['mutations']} mutants killed\n")

    results = HERE.parent / "results"
    results.mkdir(parents=True, exist_ok=True)
    n = 1
    while (results / f"mutation_run{n}.json").exists():
        n += 1
    (results / f"mutation_run{n}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(f"  written to mutation_run{n}.json\n")

    if out["not_restored"]:
        sys.stdout.write("\nFAILED: a mutation was not cleanly restored — later results "
                         "in this process cannot be trusted:\n")
        for r in out["not_restored"]:
            sys.stdout.write(f"  {r['primitive']}: {r['mutation']}\n")
        return 1
    if out["survivors"]:
        sys.stdout.write("\nSURVIVING MUTANTS — the damaged detector still passed its "
                         "canary, so that logic is not load-bearing:\n")
        for r in out["survivors"]:
            sys.stdout.write(f"  {r['primitive']}: {r['mutation']}\n")
        return 1
    sys.stdout.write(
        "\nMUTATION PASSED — every deliberate damage to a detector was caught by that\n"
        "detector's own canary, so the logic is load-bearing rather than decorative.\n"
        "  NOT established: that the detectors catch every violating shape.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
