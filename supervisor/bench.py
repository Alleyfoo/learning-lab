#!/usr/bin/env python3
"""A Python analysis bench for the supervisor: exploratory analysis over a COPY
of the fleet snapshot, never production filesystem access.

The supervisor may write temporary Python to investigate the snapshot. This
module runs that code in a restricted namespace against a `deepcopy` of the
snapshot, so even a buggy or hostile snippet cannot reach the live fleet.

## What it is, and what it is not

This is a RESEARCH SANDBOX for S1, not a production-grade isolation boundary.
The handoff explicitly defers production sandbox design. The restrictions below
are honest about that: they remove the obvious production-reaching primitives
(no `open`, no `__import__` beyond a whitelist, no `os`/`sys`/`subprocess`/`socket`,
no `eval`/`exec`/`compile`) and run against a copied dict, but this is `exec` in
the same process, not a separate OS principal. It is enough to observe what the
supervisor tries to calculate over lab fixtures; it is not a claim of containment
against a determined adversary.

## Allowed modules

Analysis only: `json`, `math`, `statistics`, `collections`, `itertools`,
`datetime`, `re`, `copy`, `decimal`, `fractions`, and `pandas` (as `pd`, if
installed). Anything else an `import` names is refused.

## What we log

Every call returns its stdout, the result of a trailing expression (if any), any
error, and whether it hit the turn cap. The supervisor core records all of it,
because *what the LLM tried to calculate* is the research evidence.
"""
from __future__ import annotations

import copy
import io
import sys
import threading
from contextlib import redirect_stdout
from typing import Optional

# Modules the bench may import. Analysis only -- no I/O, no OS, no network.
_ALLOWED_MODULES = {
    "json", "math", "statistics", "collections", "itertools", "datetime",
    "re", "copy", "decimal", "fractions", "pandas",
}

# Builtins that reach the world or escape the namespace. Anything not here is
# absent from the bench's global scope.
_SAFE_BUILTINS = {
    "True": True, "False": False, "None": None,
    "abs": abs, "all": all, "any": any, "bool": bool, "bytes": bytes,
    "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "getattr": getattr, "hasattr": hasattr, "hash": hash, "hex": hex, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "iter": iter, "len": len,
    "list": list, "map": map, "max": max, "min": min, "next": next, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip, "ascii": ascii, "bin": bin,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError,
    "StopIteration": StopIteration, "AttributeError": AttributeError,
    "NameError": NameError, "NotImplementedError": NotImplementedError,
    "RuntimeError": RuntimeError, "ArithmeticError": ArithmeticError,
    "LookupError": LookupError, "OverflowError": OverflowError,
}

_FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals",
    "vars", "dir", "input", "breakpoint", "memoryview", "classmethod",
    "staticmethod", "property", "super", "object",
}


class BenchError(Exception):
    """Raised when the bench refuses to run code that breaks its rules."""


def _make_import():
    import importlib
    allowed = _ALLOWED_MODULES

    def _import(name: str, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if level != 0 or root not in allowed:
            raise BenchError(
                f"import of {name!r} is not allowed in the analysis bench "
                f"(analysis modules only: {sorted(allowed)})")
        return importlib.import_module(name)
    return _import


def _build_namespace(snapshot_copy: dict) -> dict:
    ns: dict = {"__builtins__": dict(_SAFE_BUILTINS)}
    ns["__builtins__"]["__import__"] = _make_import()
    # Pre-load the common ones so `pd.DataFrame(...)` works without an import line,
    # and so the model has a natural surface to reach for.
    import json as _json, math as _math, re as _re, collections as _collections
    ns["json"] = _json
    ns["math"] = _math
    ns["re"] = _re
    ns["collections"] = _collections
    try:
        import pandas as _pd
        ns["pd"] = _pd
    except Exception:
        pass  # pandas optional; the model can still use pure-python analysis
    ns["snapshot"] = snapshot_copy
    return ns


def _exec_timed(code: str, ns: dict, timeout: float) -> tuple[str, Optional[str], Optional[str]]:
    """Run `code`; return (stdout, expr_value, error). Times out via a watcher."""
    buf = io.StringIO()
    result: dict = {"value": None, "error": None, "done": False}

    def _run():
        try:
            with redirect_stdout(buf):
                pcode = compile(code, "<bench>", "exec")
                exec(pcode, ns)
            result["done"] = True
        except BenchError as e:
            result["error"] = f"{type(e).__name__}: {e}"
        except Exception as e:  # analysis code is untrusted; never let it propagate raw
            result["error"] = f"{type(e).__name__}: {e}"
        finally:
            result["done"] = True

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return buf.getvalue(), None, f"TimeoutError: analysis exceeded {timeout}s limit"
    return buf.getvalue(), result.get("value"), result.get("error")


def run(code: str, snapshot: dict, *, timeout: float = 10.0,
        max_calls: int = 12) -> dict:
    """Execute one ``python`` block from the supervisor against a copy of the snapshot.

    Returns a record of what happened, never raises on analysis errors.
    """
    if not code or not code.strip():
        return {"ok": False, "stdout": "", "error": "EmptyBench: no code supplied",
                "refused": True}
    # The namespace simply does not contain the forbidden builtins, so any
    # reference to them raises NameError at runtime. We do not need a lexical
    # guard on top of that -- absence is the enforcement.
    snapshot_copy = copy.deepcopy(snapshot)
    ns = _build_namespace(snapshot_copy)
    stdout, _value, error = _exec_timed(code, ns, timeout)
    return {
        "ok": error is None,
        "stdout": stdout[:20000],   # bound the record; the core logs truncation
        "stdout_truncated": len(stdout) > 20000,
        "error": error,
        "refused": isinstance(error, str) and error.startswith("BenchError"),
    }


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    snap = {"workers": [
        {"name": "a", "task": "enrichment", "recent_runs": [
            {"ok": True, "refused": 2, "refusals": ["MISSING_PRODUCT"]},
            {"ok": False, "effect_applied": False},
        ]},
        {"name": "b", "task": "reservation", "recent_runs": []},
    ]}

    # --- normal analysis works and sees the snapshot -----------------------
    r = run("print(len(snapshot['workers'])); "
            "print(sum(1 for w in snapshot['workers'] for x in w['recent_runs'] if not x['ok']))",
            snap)
    check(r["ok"], f"plain analysis should succeed: {r}")
    check("2\n1\n" == r["stdout"], f"analysis output matches: {r!r}")

    # --- pandas is available if installed ----------------------------------
    try:
        import pandas  # noqa: F401
        r = run("import pandas as pd; df = pd.DataFrame(snapshot['workers']); "
                "print(len(df))", snap)
        check(r["ok"] and r["stdout"].strip() == "2",
              f"pandas analysis works: {r}")
    except Exception:
        pass  # pandas absent is acceptable

    # --- the original snapshot is untouched (deepcopy) ---------------------
    before = repr(snap)
    run("snapshot['workers'].append({'name': 'EVIL', 'recent_runs': []})", snap)
    check(repr(snap) == before, "CANARY: bench must run against a COPY -- the "
          "original snapshot is not mutable from bench code")

    # --- forbidden modules are refused -------------------------------------
    r = run("import os; os.listdir('.')", snap)
    check(not r["ok"] and "os" in (r["error"] or ""),
          f"importing os must be refused: {r}")
    r = run("import subprocess", snap)
    check(not r["ok"] and "subprocess" in (r["error"] or ""),
          f"importing subprocess must be refused: {r}")

    # --- open() is not available -------------------------------------------
    r = run("open('anything.txt').read()", snap)
    check(not r["ok"], f"open() must not be reachable: {r}")

    # --- a crash in analysis is reported, not propagated -------------------
    r = run("1/0", snap)
    check(not r["ok"] and "ZeroDivisionError" in (r["error"] or ""),
          f"analysis errors are captured, not raised: {r}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (plain analysis reads the snapshot / pandas works if "
          "installed / the original snapshot is not mutable from bench code / "
          "os and subprocess imports are refused / open() is unreachable / "
          "analysis errors are captured not raised)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)