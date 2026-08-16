#!/usr/bin/env python3
"""Version-bound human confirmations that no construct carries.

`f575c09` measured the hole precisely:

> An answer that CHANGED THE MODEL survives as the model; an answer that changed
> nothing survives nowhere.

The bookkeeper's *"these are all unpaid invoices"* is load-bearing — the total is
"what we owe" only if it is true — and it altered no construct, so on reload it
was gone. `confirmed_by` and `CONFIRMED` appeared nowhere on disk.

This closes only that hole.

```text
confirmations.jsonl   append-only, one line per confirmation, TAGGED WITH ITS
                      VERSION
```

## Version-bound, like runs

A confirmation was given about a particular established model. A later version
inherits authority but not history — the rule `scripts/agent_binding.py` fixed
and Experiment Z carried to workers — so v2 does not silently acquire v1's
answers. If the same assumption still holds for v2, someone says so again.

## Reconstructed as CONFIRMED, never OBSERVED

Replaying a stored human act produces a `CONFIRMED` claim carrying who settled
it and when. It never produces `OBSERVED`: nothing here was measured, and a
program that could turn a remembered answer into an observation would be
laundering provenance exactly as Experiment T did. `mechanically_verifiable` is
recorded and is `false` for this fixture — the export exposes no payment status,
so nothing can re-prove it.

## What this is NOT

Not a source-contract language. There is no vocabulary of assumption kinds, no
inheritance, no re-verification policy. One fixture, one shape: an obligation, a
referent, an answer, a person, a version.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FILENAME = "confirmations.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(directory: Path, version: int, obligation: str, clause: str,
           referent: str, answer: str, by: str = "human",
           mechanically_verifiable: bool = False) -> dict:
    """Append one confirmation. Never rewrites an earlier line."""
    entry = {"at": _now(), "version": int(version), "obligation": obligation,
             "clause": clause, "referent": referent, "answer": answer,
             "status": "CONFIRMED", "confirmed_by": by,
             "mechanically_verifiable": bool(mechanically_verifiable)}
    with (directory / FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load(directory: Path, version: Optional[int] = None) -> list[dict]:
    path = directory / FILENAME
    if not path.is_file():
        return []
    entries = [json.loads(line)
               for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    if version is None:
        return entries
    return [e for e in entries if e["version"] == version]


def as_claims(directory: Path, version: int) -> list[dict]:
    """Rebuild them in the claim shape the rest of the chain speaks.

    `status` is CONFIRMED and cannot be anything else -- see the module
    docstring. `basis` names the person, not a measurement.
    """
    out = []
    for entry in load(directory, version):
        out.append({
            "claim": {"referent": entry["referent"],
                      "obligation": entry["obligation"],
                      "meaning": entry["answer"]},
            "status": "CONFIRMED",
            "confirmed_by": entry["confirmed_by"],
            "basis": "human_confirmation",
            "mechanically_verifiable": entry["mechanically_verifiable"],
            "at": entry["at"], "version": entry["version"]})
    return out


def discharged(directory: Path, version: int) -> set:
    """Obligation ids a stored confirmation answers, for this version only."""
    return {e["obligation"] for e in load(directory, version)}


def _self_test() -> int:
    import shutil
    failures: list[str] = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    sys.path.insert(0, str(HERE.parent / "modeller"))
    import manifest as M

    scratch = HERE / ".selftest-conf"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    try:
        # The bookkeeping fixture: an obligation nothing in the model carries.
        obs = [{"id": "o1", "clause": "total what we owe each supplier"},
               {"id": "o2", "clause": "the rows are outstanding invoices"}]
        inventory = ("group_by:Supplier", "sum:Gross")
        man = {"o1": {"via": "construct", "construct": "sum:Gross"},
               "o2": {"via": "question"}}

        # --- unanswered, it BLOCKS -----------------------------------------
        ok(M.check(obs, man, inventory, asked=[]),
           "CANARY: an unanswered question must still block establishment")

        record(scratch, 1, "o2",
               "the rows are outstanding invoices",
               "purchase_invoices.Gross",
               "all six invoices are unpaid; none has been settled")

        # --- RELOAD, as a restart would --------------------------------------
        claims = as_claims(scratch, 1)
        ok(len(claims) == 1, f"one confirmation reloads: {claims}")
        claim = claims[0]
        ok(claim["status"] == "CONFIRMED",
           f"it must reload as CONFIRMED: {claim['status']}")
        ok(claim["status"] != "OBSERVED" and claim["basis"] == "human_confirmation",
           "CANARY: a remembered answer must NEVER become an observation -- "
           "nothing here was measured")
        ok(claim["confirmed_by"] == "human" and claim["at"],
           f"provenance survives: {claim}")
        ok(claim["claim"]["referent"] == "purchase_invoices.Gross"
           and claim["claim"]["obligation"] == "o2",
           f"the exact obligation and referent survive: {claim['claim']}")
        ok(claim["mechanically_verifiable"] is False,
           "…and that it cannot be re-proven is recorded, not implied")

        ok(discharged(scratch, 1) == {"o2"},
           f"the stored answer discharges its obligation: {discharged(scratch, 1)}")

        # --- VERSION-BOUND ---------------------------------------------------
        ok(as_claims(scratch, 2) == [] and discharged(scratch, 2) == set(),
           "CANARY: v2 must NOT inherit v1's confirmation -- authority is "
           "inherited, history is not")
        record(scratch, 2, "o2", "the rows are outstanding invoices",
               "purchase_invoices.Gross", "still unpaid as of the July export")
        ok(len(load(scratch, 1)) == 1 and len(load(scratch, 2)) == 1,
           "each version keeps its own answer")
        ok(load(scratch, 1)[0]["answer"].startswith("all six"),
           "CANARY: v1's line is untouched by v2's -- append only")

        # --- an answer for the WRONG version does not discharge -------------
        ok(M.check(obs, man, inventory,
                   asked=list(discharged(scratch, 3))) != [],
           "CANARY: a version with no stored answer still blocks")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (an unanswered question still blocks / a stored "
          "answer reloads as CONFIRMED and never OBSERVED, with its person, "
          "time, exact obligation and referent, and mechanically_verifiable "
          "recorded / it discharges its obligation / v2 does NOT inherit v1's "
          "confirmation and v1's line is untouched / a version with no stored "
          "answer still blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
