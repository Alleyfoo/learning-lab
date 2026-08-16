#!/usr/bin/env python3
"""Build the fleet's state by RUNNING the existing workers, not by writing logs.

Every number the dashboard shows is the result of an actual execution through
the existing validators and executors. A fixture fleet made of invented run
records would test the dashboard's layout and nothing else.

Three workers, deliberately not three copies of one:

```text
acme-timesheets    enrichment    the full lifecycle -- healthy, exception,
                                 investigation, promotion to v2, healthy again
orders-enrichment  enrichment    SAME engine, different model. Runs green with
                                 rows refused, which is not the same as failing
room-reservation   reservation   a different engine entirely
```
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "worker"))

import fleet  # noqa: E402
import worker as W  # noqa: E402

ROOT = fleet.ROOT


def main(argv: list[str]) -> int:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    # --- 1. the full lifecycle -------------------------------------------
    timesheet = json.loads((LAB / "worker" / "established" /
                            "timesheet-cost-v1.json").read_text(encoding="utf-8"))
    w = fleet.establish(
        ROOT, "acme-timesheets",
        "Cost each timesheet entry: hours multiplied by that person's hourly "
        "rate, with their name.", "enrichment", "data", timesheet,
        trigger="data/timesheets/")
    for _ in range(6):
        fleet.record_run(w)

    w = fleet.rebase(w, "experimentZ/fixtures/A")          # the world changes
    fleet.record_run(w)
    packet = json.loads((w.directory / "last_packet.json").read_text(encoding="utf-8"))
    fleet.open_investigation(w, packet, None)
    replacements = [{"source": "staff", "from": "staff_id", "to": "employee_id"}]
    w = fleet.promote(w, W.apply_replacements(timesheet, replacements),
                      "join target renamed in the source; the replacement was "
                      "the sole candidate with complete coverage and unique keys",
                      replacements)
    for _ in range(3):
        fleet.record_run(w)

    # --- 2. same engine, different model, rows refused --------------------
    orders = json.loads((LAB / "enrichment" / "models" /
                         "enrichment_v1.json").read_text(encoding="utf-8"))
    w2 = fleet.establish(
        ROOT, "orders-enrichment",
        "Enrich each order line with its product name and price, and compute "
        "the line total.", "enrichment", "enrichment", orders,
        trigger="enrichment/fixtures/")
    for _ in range(4):
        fleet.record_run(w2)

    # --- 3. a different engine -------------------------------------------
    reservation = json.loads((LAB / "reservation" / "models" /
                              "reservation_v1.json").read_text(encoding="utf-8"))
    w3 = fleet.establish(
        ROOT, "room-reservation",
        "Accept a requested date unless it is malformed, a holiday, or already "
        "reserved.", "reservation", "reservation", reservation,
        trigger="reservation/fixtures/")
    for request in ("2026-03-10", "2026-12-25", "2026-03-10", "not-a-date",
                    "2026-04-02"):
        fleet.record_run(w3, request=request)

    for w in fleet.load_all():
        s = w.summary()
        print(f"{s['worker']:19} v{s['version']}  runs {s['runs_this_version']:>2}"
              f"/{s['runs_total']:<2} ok {s['successes']:>2}  exc "
              f"{s['exceptions']}  refused rows {s['rows_refused']}  "
              f"inv {s['investigation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
