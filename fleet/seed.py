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
import os
import shutil
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "worker"))

import fleet  # noqa: E402
import inbox  # noqa: E402
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

    # --- 3. a different engine, and the COMMITTING path -------------------
    # This worker owns its state. Its effect writes into its own folder, not
    # into a shared repo fixture, which is what makes "accepted reservations
    # change worker state" a fact about the worker rather than a side effect on
    # everyone else.
    reservation = json.loads((LAB / "reservation" / "models" /
                              "reservation_v1.json").read_text(encoding="utf-8"))
    w3 = fleet.establish(
        ROOT, "room-reservation",
        "Accept a requested date unless it is malformed, a holiday, or already "
        "reserved. Accepted dates are appended to this worker's own state.",
        "reservation", "fleet/workers/room-reservation/state", reservation,
        trigger="fleet/workers/room-reservation/state/fixtures/")
    ident = json.loads((w3.directory / "worker.json").read_text(encoding="utf-8"))
    ident["work_item_identity"] = "content_digest"
    (w3.directory / "worker.json").write_text(
        json.dumps(ident, indent=2) + chr(10), encoding="utf-8")
    w3 = fleet.load(w3.directory)
    state = w3.directory / "state"
    shutil.copytree(LAB / "reservation" / "fixtures", state / "fixtures")
    w3 = fleet.load(w3.directory)

    def reservations() -> list:
        return json.loads((state / "fixtures" / "reservations.json")
                          .read_text(encoding="utf-8"))["reservations"]

    started_with = len(reservations())
    target = state / "fixtures" / "reservations.json"

    # Everything below arrives as a FILE in the inbox. Nothing calls the worker
    # directly, and no LLM is reachable from any of it.
    inbox.ensure(w3)

    def drop(name: str, request: str) -> None:
        (w3.directory / "inbox" / name).write_text(
            json.dumps({"request": request}, indent=2) + chr(10), encoding="utf-8")


    for name, request in (("req-001.json", "2026-12-25"),
                          ("req-002.json", "2026-03-10"),
                          ("req-003.json", "not-a-date"),
                          ("req-004.json", "2026-04-02")):
        drop(name, request)
    inbox.poll(w3)
    w3 = fleet.load(w3.directory)

    # The same request again, under a different filename. Identical bytes, so
    # the ledger recognises the same work item and the booking is not repeated.
    drop("req-004-resend.json", "2026-04-02")
    inbox.poll(w3)
    w3 = fleet.load(w3.directory)
    after_duplicate = len(reservations())

    # A REAL failed effect: the state file is read-only for exactly one pass,
    # so an accepted decision cannot land. Into the exception queue.
    drop("req-005.json", "2026-05-05")
    os.chmod(target, stat.S_IREAD)
    try:
        inbox.poll(w3)
    finally:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
    w3 = fleet.load(w3.directory)

    # A person retries it. Now it applies -- exactly once.
    inbox.retry(w3, "req-005.json")
    inbox.poll(w3)
    w3 = fleet.load(w3.directory)

    # --- two interruptions, and recovery ------------------------------
    # A crash BEFORE the effect: nothing applied, so the work must not be lost.
    drop("req-006.json", "2026-07-14")
    try:
        inbox.poll(w3, crash_at="after_claim")
    except inbox.CrashInjected:
        pass
    w3 = fleet.load(w3.directory)
    before_recovery = len(reservations())
    inbox.recover(w3)
    w3 = fleet.load(w3.directory)
    after_before_crash = len(reservations())

    # A crash AFTER the effect: it landed but was never recorded. Recovery must
    # complete it without re-executing, or the date is booked twice.
    drop("req-007.json", "2026-08-20")
    try:
        inbox.poll(w3, crash_at="after_effect")
    except inbox.CrashInjected:
        pass
    w3 = fleet.load(w3.directory)
    landed_uncorded = len(reservations())
    inbox.recover(w3)
    w3 = fleet.load(w3.directory)

    ended_with = len(reservations())
    print(f"crash BEFORE effect: state {before_recovery} -> "
          f"{after_before_crash} (work recovered, applied once)")
    print(f"crash AFTER effect:  effect had landed at {landed_uncorded}, "
          f"state after recovery {ended_with} (no duplicate)")
    print(f"inbox: duplicate resend left state at {after_duplicate}, "
          f"retry applied once")
    print("inbox summary:", json.dumps(inbox.summary(w3)))
    print(f"room-reservation state: {started_with} -> {ended_with} "
          f"reservation(s) -- {reservations()}")

    for w in fleet.load_all():
        s = w.summary()
        print(f"{s['worker']:19} v{s['version']}  runs {s['runs_this_version']:>2}"
              f"/{s['runs_total']:<2} ok {s['successes']:>2}  exc "
              f"{s['exceptions']}  refused rows {s['rows_refused']}  "
              f"inv {s['investigation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
