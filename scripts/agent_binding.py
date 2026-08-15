#!/usr/bin/env python3
"""Bind an agent-network run to the agent definitions that produced it.

Why this exists
---------------
`experiment3a/harness/compose.py` hashes the fixture, so the INPUT side of every
3A-3E run is bound to the freeze. The agent side is not. `header-locator`,
`header-cell-classifier` and `warrant-reviewer` are prompt files on disk; editing
one between two runs moves the boundary those runs are being compared across, and
nothing in the record says so. The 3B.1/3C claim that a blind spot is
"run-stable across two runs" is a claim about two runs having faced the same
reviewer -- which the record currently cannot establish.

This is the failure `scripts/verify_frozen.py` exists to catch -- there, one
regenerated fixture silently rewrote six frozen ones -- applied to the leg of the
channel that has no record.

No keys, no signing. There is no adversary and no transit: the orchestrator IS
the transport and would hold any key it issued, so a keyed MAC degrades to
exactly the plain SHA-256 used here. `definition_phase/harness/approval.py` stops
at the same place for the same reason.

Four rules, each exercised by the self-test:

1. **Absence is recorded, never inferred.** A run carrying no binding must be
   distinguishable from a run whose binding verified. Silence that reads as a
   pass is the defect -- not the missing field.
2. **Verification fails per agent.** "Binding invalid" is useless; you
   immediately want to know WHICH definition moved.
3. **`model_id` is declared, not detected.** The harness cannot observe which
   model answered a subagent call. An undeclared model is reported as undeclared,
   never defaulted to whatever happens to be configured today.
4. **Recording a hash now certifies nothing about a past run.** Adoption states
   what the definitions are today. Runs completed before this module existed are
   `NOT_RECORDED`, and no amount of adopting changes that.

Usage
-----
    python scripts/agent_binding.py --show        # current definition hashes
    python scripts/agent_binding.py --self-test
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
AGENT_DIR = LAB / ".claude" / "agents"

# The 3A-3E network. Named explicitly rather than globbed: a run is bound to the
# agents it USED, and a new file appearing in the directory is not retroactively
# part of an earlier run.
NETWORK_3A = ("header-locator", "header-cell-classifier", "warrant-reviewer")

# Every verdict this module can return. The self-test requires each to be
# reachable -- a declared-but-unexercised reason is a claim with no test behind
# it (the rule `approval.py` already applies to its own REASONS tuple).
REASONS = ("OK", "DEFINITION_CHANGED", "DEFINITION_MISSING", "NOT_RECORDED",
           "MODEL_ID_UNDECLARED")

SCHEMA = "agent-binding-v1"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def definition_path(name: str) -> Path:
    return AGENT_DIR / f"{name}.md"


def current_hashes(names=NETWORK_3A) -> dict:
    """Hash each named agent definition as it stands right now.

    A missing definition maps to None rather than raising: "the reviewer's prompt
    is gone" is a fact about the record that the caller must be able to write
    down, not an error that stops the run from being recorded at all.
    """
    out: dict = {}
    for name in names:
        path = definition_path(name)
        out[name] = _sha_bytes(path.read_bytes()) if path.exists() else None
    return out


def make_binding(names=NETWORK_3A, model_id=None) -> dict:
    """The record to store alongside a run's results.

    `model_id` is whatever the run declared. Rule 3: it is not inferred here.
    """
    return {
        "schema": SCHEMA,
        "agents": dict(current_hashes(names)),
        "model_id": model_id,
        "recorded": True,
    }


def verify_binding(binding, names=NETWORK_3A) -> dict:
    """Recompute every agent hash and report per agent (rule 2).

    A run with no binding at all returns NOT_RECORDED for each agent (rule 1) --
    never OK, and never an empty `checks` dict that a caller could mistake for a
    clean result.
    """
    checks: dict = {}

    if not isinstance(binding, dict) or not binding.get("recorded"):
        for name in names:
            checks[name] = "NOT_RECORDED"
        return {
            "checks": checks,
            "failures": sorted(set(checks.values())),
            "model_id": None,
            "model_id_status": "NOT_RECORDED",
            "verified": False,
            "reason": ("no binding recorded for this run; the agent definitions "
                       "that produced it cannot be established after the fact"),
        }

    recorded = binding.get("agents") or {}
    actual = current_hashes(names)

    for name in names:
        was = recorded.get(name)
        now = actual.get(name)
        if was is None and name not in recorded:
            checks[name] = "NOT_RECORDED"
        elif now is None:
            # The definition file is gone. That is NOT the same as it having been
            # edited, and conflating them would let a deleted agent read as
            # tampering -- the distinction approval.py draws for renderers.
            checks[name] = "DEFINITION_MISSING"
        elif was == now:
            checks[name] = "OK"
        else:
            checks[name] = "DEFINITION_CHANGED"

    model_id = binding.get("model_id")
    model_status = "OK" if model_id else "MODEL_ID_UNDECLARED"

    failures = sorted({v for v in checks.values() if v != "OK"})
    verified = not failures and model_status == "OK"

    if verified:
        reason = f"all {len(names)} agent definitions unchanged; model {model_id}"
    elif failures:
        reason = f"agent definitions not verified: {failures}"
    else:
        reason = ("agent definitions unchanged, but the run declared no model_id; "
                  "which model produced these judgements is unestablished")

    return {
        "checks": checks,
        "failures": failures,
        "model_id": model_id,
        "model_id_status": model_status,
        "verified": verified,
        "reason": reason,
    }


def binding_from_judgements(judgements, names=NETWORK_3A) -> dict:
    """Binding for a run being composed now.

    Reads `model_id` from the judgements file -- the orchestrator transcribes it
    there along with the raw subagent outputs, because the harness has no way to
    observe it (rule 3).
    """
    return make_binding(names, judgements.get("model_id"))


# ---------------------------------------------------------------------------
# Self-test: control, per-agent isolation, missing vs changed, undeclared model
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import shutil
    import tempfile

    global AGENT_DIR
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    real = AGENT_DIR
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "agents"
        tmp.mkdir()
        for name in NETWORK_3A:
            src = definition_path(name)
            if not src.exists():
                sys.stderr.write(f"SELF-TEST CANNOT RUN: missing {src}\n")
                return 2
            shutil.copy2(src, tmp / f"{name}.md")

        AGENT_DIR = tmp
        try:
            binding = make_binding(model_id="glm-5.2")

            # --- control ------------------------------------------------------
            r = verify_binding(binding)
            check(r["verified"] and set(r["checks"].values()) == {"OK"},
                  f"control must verify: {r}")

            # --- 1. one definition edited, the others untouched ---------------
            target = tmp / "warrant-reviewer.md"
            original = target.read_bytes()
            target.write_bytes(original + b"\n<!-- edited after the run -->\n")
            r1 = verify_binding(binding)
            check(r1["checks"]["warrant-reviewer"] == "DEFINITION_CHANGED",
                  f"an edited reviewer must fail on its OWN entry: {r1['checks']}")
            check(r1["checks"]["header-locator"] == "OK"
                  and r1["checks"]["header-cell-classifier"] == "OK",
                  f"…and must not implicate the other two: {r1['checks']}")
            check(not r1["verified"], "a changed definition must not verify")
            target.write_bytes(original)

            # --- 2. definition deleted, distinguished from edited --------------
            target.unlink()
            r2 = verify_binding(binding)
            check(r2["checks"]["warrant-reviewer"] == "DEFINITION_MISSING",
                  f"a deleted definition must be distinguishable from an edited "
                  f"one: {r2['checks']}")
            target.write_bytes(original)

            # --- 3. no binding at all -- the load-bearing case ----------------
            # Every 3A-3E run completed before this module existed lands here.
            # It must read as unestablished, never as clean.
            r3 = verify_binding(None)
            check(set(r3["checks"].values()) == {"NOT_RECORDED"},
                  f"an unbound run must report NOT_RECORDED per agent: {r3['checks']}")
            check(not r3["verified"],
                  "an unbound run must NOT verify -- silence is not a pass")
            check(r3["checks"] and len(r3["checks"]) == len(NETWORK_3A),
                  "an unbound run must not return an empty checks dict")

            # --- 4. hashes recorded, model_id absent --------------------------
            r4 = verify_binding(make_binding(model_id=None))
            check(r4["model_id_status"] == "MODEL_ID_UNDECLARED",
                  f"an undeclared model must be reported: {r4}")
            check(not r4["verified"],
                  "definitions matching is not sufficient; the model is part of "
                  "what produced the judgements")
            check(not r4["failures"],
                  "an undeclared model is not an agent-definition failure and "
                  "must not be reported as one")

            # --- 5. the hashes must actually distinguish the three agents -----
            hashes = current_hashes()
            check(len(set(hashes.values())) == len(NETWORK_3A),
                  f"three distinct definitions must hash distinctly: {hashes}")

            seen = {v for res in (r, r1, r2, r3) for v in res["checks"].values()}
            seen.add(r4["model_id_status"])
            untested = sorted(set(REASONS) - seen)
            check(not untested, f"declared but unexercised reasons: {untested}")
        finally:
            AGENT_DIR = real

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (control verifies / an edited definition fails on its own "
        "entry only / deletion distinguished from editing / an unbound run reads as "
        "NOT_RECORDED and never as clean / undeclared model_id blocks verification "
        "without being reported as a definition failure / all 5 reasons exercised)\n")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    if argv[:1] == ["--show"]:
        for name, digest in current_hashes().items():
            print(f"{digest or 'MISSING':64}  {name}")
        return 0
    sys.stderr.write(__doc__.split("Usage\n-----\n")[-1])
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
