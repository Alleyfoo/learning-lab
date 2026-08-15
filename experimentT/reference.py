#!/usr/bin/env python3
"""Hand-written oracle for T's data. Trivial, as calendar_job's is.

The independent answer T's model-produced nodes are measured against. It reads
`date` from each reservation -- the reading a human would pick, and the reading
the data does NOT establish. That is deliberate: the oracle encodes the human's
INTENT, and T is asking whether the modelling stage arrives there knowingly or
by inheriting a guess.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def handle(request, holiday_dates, reservation_dates):
    try:
        date.fromisoformat(request)
    except (ValueError, TypeError):
        return False, "INVALID_DATE"
    if request in holiday_dates:
        return False, "HOLIDAY"
    if request in reservation_dates:
        return False, "ALREADY_RESERVED"
    reservation_dates.append(request)
    return True, None


def run(requests, holidays_path: Path, reservations_path: Path):
    holidays = json.loads(holidays_path.read_text(encoding="utf-8"))["holidays"]
    holiday_dates = [h["date"] for h in holidays]

    state = json.loads(reservations_path.read_text(encoding="utf-8"))
    reservation_dates = [r["date"] for r in state["reservations"]]

    out = []
    for request in requests:
        accepted, reason = handle(request, holiday_dates, reservation_dates)
        if accepted:
            state["reservations"].append({"date": request})
            reservations_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append({"request": request, "accepted": accepted, "reason": reason})
    return out
