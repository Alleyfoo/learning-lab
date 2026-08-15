#!/usr/bin/env python3
"""Hand-written reference implementation. Deliberately trivial.

This is what a person writes in ten minutes when asked to automate the job:
accept a requested date unless it is malformed, a holiday, or already taken;
append it if accepted. No model, no framework, no declaration -- the rules are
in the control flow, which is exactly the point of having it.

Its purpose is to be the INDEPENDENT answer that the modelled path is compared
against. If the two disagree, at least one of them is wrong, and the comparison
says so without anyone having to decide which reading of the spec was intended.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def handle(request: str, holidays: list[str], reservations: list[str]) -> tuple[bool, str | None]:
    """Return (accepted, reason). Appends to `reservations` in place on accept."""
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False, "INVALID_DATE"
    if request in holidays:
        return False, "HOLIDAY"
    if request in reservations:
        return False, "ALREADY_RESERVED"
    reservations.append(request)
    return True, None


def run(requests: list[str], holidays_path: Path, reservations_path: Path) -> list[dict]:
    """Process a sequence, persisting after each acceptance."""
    holidays = json.loads(holidays_path.read_text(encoding="utf-8"))["holidays"]
    state = json.loads(reservations_path.read_text(encoding="utf-8"))
    reservations = state["reservations"]

    out = []
    for request in requests:
        accepted, reason = handle(request, holidays, reservations)
        if accepted:
            state["reservations"] = reservations
            reservations_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append({"request": request, "accepted": accepted, "reason": reason})
    return out
