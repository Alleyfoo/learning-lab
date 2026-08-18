#!/usr/bin/env python3
"""v0.5 -- thin operating wrappers over the ORDINARY fleet inbox path.

The System Map's inbox node lets an operator upload a work item and process it.
This module does NOT introduce a dashboard-specific execution path: it writes
the uploaded bytes into the worker's real `inbox/` and calls the ordinary
`fleet.inbox.poll`, which is the only thing that writes the ledger, dispatches
`fleet.record_run` (committing or not), and moves files to processed/exceptions.

Keep this thin. If a behaviour is needed, it belongs in fleet/inbox.py, not here.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "fleet"))

import fleet  # noqa: E402
import inbox  # noqa: E402


def save_to_inbox(w, filename: str, data: bytes) -> Path:
    """Write `data` into the worker's real `inbox/<filename>`.

    Ensures the inbox folders exist (the ordinary `ensure`). Returns the path.
    No processing: the file just lands where the ordinary poller will find it.
    """
    inbox.ensure(w)
    if not filename:
        raise ValueError("filename is required")
    # keep the file inside the inbox dir (reject any path separators)
    safe = Path(filename).name
    if safe != filename:
        raise ValueError(f"filename must be a bare name, not a path: {filename!r}")
    path = w.directory / "inbox" / safe
    path.write_bytes(data)
    return path


def poll_inbox(w) -> list[dict]:
    """One ordinary deterministic pass over the worker's inbox.

    Delegates straight to `fleet.inbox.poll` -- the same path a CLI/seed would
    use. Writes the ledger, dispatches record_run (committing or not), moves
    files to processed/exceptions. No dashboard-specific execution here.
    """
    return inbox.poll(w)


def inbox_counts(w) -> dict:
    """waiting/processed/exceptions via the ordinary `inbox.summary`."""
    return inbox.summary(w)


# --- self-test: save_to_inbox + poll_inbox use the ordinary path end-to-end --

def _self_test() -> int:
    import os

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    scratch = LAB / "fleet" / ".selftest-operate"
    if scratch.exists():
        shutil.rmtree(scratch)
    try:
        root = scratch / "workers"
        root.mkdir(parents=True)
        model = json.loads((LAB / "reservation" / "models" /
                            "reservation_v1.json").read_text(encoding="utf-8"))
        base_rel = "fleet/.selftest-operate/workers/inbox-worker/state"
        w = fleet.establish(root, "inbox-worker", "Operate test.", "reservation",
                            base_rel, model)
        ident = json.loads((w.directory / "worker.json").read_text(encoding="utf-8"))
        ident["work_item_identity"] = "content_digest"
        (w.directory / "worker.json").write_text(
            json.dumps(ident, indent=2) + "\n", encoding="utf-8")
        shutil.copytree(LAB / "reservation" / "fixtures",
                        w.directory / "state" / "fixtures")
        w = fleet.load(w.directory)

        def reservations() -> list:
            return json.loads((w.directory / "state" / "fixtures" /
                               "reservations.json").read_text(encoding="utf-8"))["reservations"]

        start = len(reservations())

        # save_to_inbox lands the file in the real inbox, nothing more
        payload = (json.dumps({"request": "2026-04-02"}) + "\n").encode("utf-8")
        path = save_to_inbox(w, "op.json", payload)
        check(path == w.directory / "inbox" / "op.json",
              f"save_to_inbox writes into the real inbox: {path}")
        check(path.is_file(), "the file physically lands in inbox/")
        check(inbox_counts(w)["waiting"] == 1, "waiting count sees the file")

        # a bare-name guard: a path with separators is refused
        try:
            save_to_inbox(w, "../escape.json", b"x")
            check(False, "save_to_inbox must refuse a path separator")
        except ValueError:
            check(True, "save_to_inbox refuses a path separator")
        check(not (w.directory / "escape.json").is_file(),
              "no file escaped the inbox dir")

        # poll_inbox runs the ORDINARY path: ledger + processed + effect applied
        out = poll_inbox(w)
        check(len(out) == 1 and out[0]["state"] == "completed"
              and out[0]["effect_applied"] is True,
              f"poll_inbox completed the acceptance via the ordinary path: {out}")
        check((w.directory / "processed" / "op.json").is_file(),
              "the file moved to processed/ by the ordinary path")
        ledger = inbox.ledger(w)
        check(any(e["state"] == "completed" for e in ledger),
              "the ordinary path wrote a ledger line")
        check(len(reservations()) == start + 1,
              f"the committing effect really landed (state grew): {reservations()}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (save_to_inbox lands bytes in the real inbox + "
          "guards against path escape / poll_inbox delegates to the ordinary "
          "fleet.inbox.poll which writes the ledger, moves the file to "
          "processed, and lands the committing effect -- no dashboard path)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)