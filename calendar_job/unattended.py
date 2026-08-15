#!/usr/bin/env python3
"""Unattended runtime: the established task definition is the authority.

**No LLM anywhere in this file or anything it calls.** No human either -- there
is no per-run approval, no prompt, no confirmation. A request arrives, the
established definition decides, and an accepted date is appended.

## What "established" means here

The definition was authored and agreed BEFORE any of these runs, and the runtime
is not permitted to reinterpret it:

```text
definition is INVALID   ->  the run stops. An unattended job with no one to ask
                            must not fall back on a best guess.
definition CHANGED      ->  reported. `--established <sha256>` pins which
                            definition is in force, so a run cannot silently
                            execute an edited authority. This is not approval --
                            it is checking WHICH authority is being obeyed.
```

## Where the append happens, and why not in the executor

`execute()` returns the reservation list as it would stand after the decision and
writes nothing -- that is what makes it deterministic and re-runnable. Persisting
is the RUNTIME's act, and it happens only on acceptance. Keeping those apart is
why the same executor can be previewed safely in the modeller and trusted here.

    python calendar_job/unattended.py 2026-07-14 2026-12-25
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parent
LAB = JOB.parent
sys.path.insert(0, str(LAB / "taskmodel"))
sys.path.insert(0, str(LAB / "reservation" / "harness"))

import reservation_model  # noqa: E402,F401  (registers the task type)
import task_model  # noqa: E402
from execute_reservation import execute  # noqa: E402

DEFINITION = JOB / "definition" / "calendar_job.json"


def definition_digest(raw: dict) -> str:
    """Which definition is in force. Canonical, so key order cannot change it."""
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest()


class DefinitionRefused(Exception):
    """The established definition cannot be run as written."""


def run(requests: list[str], base: Path = JOB,
        definition_path: Path = DEFINITION,
        established: str | None = None) -> list[dict]:
    raw = json.loads(definition_path.read_text(encoding="utf-8"))

    digest = definition_digest(raw)
    if established is not None and digest != established:
        raise DefinitionRefused(
            f"definition in force is {digest[:12]}, expected {established[:12]}; "
            f"refusing to run an authority that is not the established one")

    model = task_model.parse(raw)
    report = task_model.validate(model, base)
    if not report.valid:
        raise DefinitionRefused(
            "the established definition is invalid, and there is no one to ask: "
            + "; ".join(str(p) for p in report.problems[:4]))

    reservations_path = base / model.sources["reservations"].path
    state = json.loads(reservations_path.read_text(encoding="utf-8"))

    out: list[dict] = []
    for request in requests:
        decision = execute(model, base, request)
        if decision.accepted:
            # The append is the RUNTIME's act, on acceptance only.
            state["reservations"] = list(decision.reservations)
            reservations_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
        out.append({"request": request, "accepted": decision.accepted,
                    "reason": decision.reason})
    return out


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: unattended.py <YYYY-MM-DD> [...]\n")
        return 2
    raw = json.loads(DEFINITION.read_text(encoding="utf-8"))
    print(f"definition {definition_digest(raw)[:12]}  purpose: {raw.get('purpose','')[:60]}...")
    for record in run(argv):
        verdict = "ACCEPT" if record["accepted"] else f"REJECT {record['reason']}"
        print(f"  {record['request']:14} {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
