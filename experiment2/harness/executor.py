"""Run a submitted procedure deterministically against source files.

The procedure is executed in a subprocess with a timeout. NOTE: this is process
isolation for robustness, not a security sandbox. Submitted code runs with the
privileges of this process's user.

No agent is involved here. This is the deterministic execution stage of the
lifecycle: once a procedure exists, matching inputs must run without one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = 60

_RUNNER = """
import json, sys, importlib.util
sys.path.insert(0, __HARNESS__)
from contract import Escalate, AskHuman, CANONICAL_COLUMNS

def emit(d):
    print(json.dumps(d)); raise SystemExit(0)

spec = importlib.util.spec_from_file_location("submitted", __PROC__)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    emit({"outcome": "load_error", "error": repr(exc)})

if not hasattr(mod, "normalize"):
    emit({"outcome": "load_error", "error": "module defines no normalize(source_path)"})

try:
    df = mod.normalize(__SOURCE__)
except Escalate as e:
    emit({"outcome": "escalate", "reason": e.reason, "details": e.details})
except AskHuman as e:
    emit({"outcome": "ask_human", "question": e.question,
          "why_not_inferable": e.why_not_inferable})
except Exception as exc:
    emit({"outcome": "error", "error": repr(exc)})

try:
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        emit({"outcome": "schema_error", "missing_columns": missing})
    out = df[CANONICAL_COLUMNS].copy()
    out["sales"] = out["sales"].astype(float).round(2)
    for c in ("country", "product_id", "period"):
        out[c] = out[c].astype(str)
    emit({"outcome": "ok", "rows": out.to_dict(orient="records")})
except Exception as exc:
    emit({"outcome": "schema_error", "error": repr(exc)})
"""


def run_procedure(procedure_path: Path, source_path: Path) -> dict:
    code = (_RUNNER
            .replace("__HARNESS__", repr(str(ROOT / "harness")))
            .replace("__PROC__", repr(str(procedure_path)))
            .replace("__SOURCE__", repr(str(source_path))))
    try:
        cp = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"outcome": "timeout"}
    line = next((l for l in reversed(cp.stdout.splitlines()) if l.strip().startswith("{")), None)
    if line is None:
        return {"outcome": "no_output", "stderr": cp.stderr[-2000:]}
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"outcome": "bad_output", "stdout": cp.stdout[-2000:]}
