#!/usr/bin/env python3
"""Are the hand-written job and the modelled job the SAME job?

Asserted nowhere and demonstrated here. Both implementations start from
identical copies of the same holiday and reservation sources, process the same
request sequence, and must agree on:

```text
every decision   accept/reject and, when rejected, WHICH rule rejected it
final state      the reservation file's contents
```

State equality is the half that matters most. Two implementations can agree on
every accept/reject and still leave different data behind -- one appending
twice, one not appending at all -- and only the final state catches it.

## The request sequence, and what each entry is for

```text
2026-07-14   a free day                  ACCEPT, and it must be appended
2026-07-14   the SAME day again          REJECT ALREADY_RESERVED -- the only
                                         case that proves the append took
                                         EFFECT rather than merely being reported
2026-12-25   a holiday                   REJECT HOLIDAY
2026-02-30   looks like a date, is not   REJECT INVALID_DATE
2026-03-10   already in the source       REJECT ALREADY_RESERVED
2026-08-01   another free day            ACCEPT, after a run of rejections
```

## Canaries

Agreement is only evidence if disagreement would be caught. Three deliberately
broken variants of the REFERENCE are run, and each must be detected:

```text
skip_holiday   drops the holiday rule       -> a DECISION diverges
never_append   accepts but never persists   -> decisions agree at first, and
                                               the STATE diverges
append_twice   appends twice on accept      -> only the state diverges
```

`never_append` and `append_twice` are the ones worth having: both leave a
decision sequence that looks entirely reasonable.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

JOB = Path(__file__).resolve().parent
sys.path.insert(0, str(JOB))

import reference  # noqa: E402
import unattended  # noqa: E402

REQUESTS = ["2026-07-14", "2026-07-14", "2026-12-25", "2026-02-30",
            "2026-03-10", "2026-08-01"]


def _workspace(tmp: Path, tag: str) -> Path:
    """An isolated copy of the job's data, so neither run can see the other's."""
    ws = tmp / tag
    (ws / "fixtures").mkdir(parents=True)
    (ws / "definition").mkdir(parents=True)
    for name in ("holidays.json", "reservations.json"):
        shutil.copy(JOB / "fixtures" / name, ws / "fixtures" / name)
    shutil.copy(JOB / "definition" / "calendar_job.json",
                ws / "definition" / "calendar_job.json")
    return ws


def _state(ws: Path) -> list:
    return json.loads((ws / "fixtures" / "reservations.json")
                      .read_text(encoding="utf-8"))["reservations"]


def run_reference(ws: Path, handler: Optional[Callable] = None) -> list[dict]:
    original = reference.handle
    if handler is not None:
        reference.handle = handler
    try:
        return reference.run(REQUESTS, ws / "fixtures" / "holidays.json",
                             ws / "fixtures" / "reservations.json")
    finally:
        reference.handle = original


def run_modelled(ws: Path) -> list[dict]:
    return unattended.run(REQUESTS, base=ws,
                          definition_path=ws / "definition" / "calendar_job.json")


def compare(tmp: Path, handler: Optional[Callable] = None, tag: str = "run") -> dict:
    ref_ws = _workspace(tmp, f"{tag}_reference")
    mod_ws = _workspace(tmp, f"{tag}_modelled")

    ref_decisions = run_reference(ref_ws, handler)
    mod_decisions = run_modelled(mod_ws)

    ref_state, mod_state = _state(ref_ws), _state(mod_ws)
    decisions_agree = ref_decisions == mod_decisions
    state_agrees = ref_state == mod_state

    return {"decisions_agree": decisions_agree, "state_agrees": state_agrees,
            "equivalent": decisions_agree and state_agrees,
            "reference_decisions": ref_decisions,
            "modelled_decisions": mod_decisions,
            "reference_state": ref_state, "modelled_state": mod_state}


# --- deliberately broken references -----------------------------------------

def _skip_holiday(request, holidays, reservations):
    from datetime import date
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False, "INVALID_DATE"
    if request in reservations:
        return False, "ALREADY_RESERVED"
    reservations.append(request)
    return True, None


def _never_append(request, holidays, reservations):
    from datetime import date
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False, "INVALID_DATE"
    if request in holidays:
        return False, "HOLIDAY"
    if request in reservations:
        return False, "ALREADY_RESERVED"
    return True, None                      # accepted, and nothing written


def _append_twice(request, holidays, reservations):
    from datetime import date
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False, "INVALID_DATE"
    if request in holidays:
        return False, "HOLIDAY"
    if request in reservations:
        return False, "ALREADY_RESERVED"
    reservations.append(request)
    reservations.append(request)
    return True, None


CANARIES = (("skip_holiday", _skip_holiday),
            ("never_append", _never_append),
            ("append_twice", _append_twice))


def run_all() -> dict:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        control = compare(tmp, tag="control")

        canaries = []
        for name, handler in CANARIES:
            broken = compare(tmp, handler=handler, tag=name)
            canaries.append({
                "name": name,
                "detected": not broken["equivalent"],
                "decisions_agree": broken["decisions_agree"],
                "state_agrees": broken["state_agrees"],
                "reference_state": broken["reference_state"]})

    all_detected = all(c["detected"] for c in canaries)
    outcome = ("VOID" if not all_detected
               else "EQUIVALENT" if control["equivalent"]
               else "NOT_EQUIVALENT")

    return {"question": ("does the modelled task do the same job as the "
                         "hand-written one, including the state it leaves behind?"),
            "requests": REQUESTS, "control": control, "canaries": canaries,
            "outcome": outcome,
            "stated_limitation": (
                "one request sequence of six, one holiday list, one starting "
                "state. Says the two implementations agree HERE; it is not a "
                "proof of equivalence over all inputs. No LLM is involved in "
                "either path at runtime.")}


def main(argv: list[str]) -> int:
    result = run_all()
    c = result["control"]
    print(f"  decisions agree: {c['decisions_agree']}   "
          f"final state agrees: {c['state_agrees']}\n")
    for ref, mod in zip(c["reference_decisions"], c["modelled_decisions"]):
        mark = "  " if ref == mod else "!!"
        verdict = "ACCEPT" if ref["accepted"] else f"REJECT {ref['reason']}"
        print(f"  {mark} {ref['request']:14} {verdict}")
    print(f"\n  final reservations: {c['reference_state']}\n")
    for canary in result["canaries"]:
        print(f"  CANARY {canary['name']:14} detected={str(canary['detected']):5} "
              f"(decisions_agree={canary['decisions_agree']}, "
              f"state_agrees={canary['state_agrees']})")
    print(f"\nOUTCOME: {result['outcome']}")

    if "--no-record" not in argv:
        (JOB / "results").mkdir(exist_ok=True)
        n = 1
        while (JOB / "results" / f"equivalence_run{n}.json").exists():
            n += 1
        path = JOB / "results" / f"equivalence_run{n}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  written to {path.name}")

    return 0 if result["outcome"] == "EQUIVALENT" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
