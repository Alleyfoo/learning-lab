#!/usr/bin/env python3
"""A deterministic inbox around an established worker. No LLM anywhere.

```text
<worker>/
  inbox/        a file landing here is the trigger
  processed/    the run completed -- accepted, or refused by policy
  exceptions/   the run could not complete, or its effect did not land
  ledger.jsonl  append-only work-item state. This is the twice-protection.
```

## Why a ledger and not "did the file move"

A file's location is a consequence, not a record. If a process dies between
applying an effect and moving the file, the file is still in `inbox/` and a
naive poller reruns it — and for a worker with an effect that is a duplicate
booking, not a retry.

So an item is **claimed in the ledger before it is run**, and the ledger is what
the next poll consults. A crash leaves a visible `claimed` line rather than an
item that silently looks fresh.

## Item identity is content, not filename

`item_id` is the sha256 of the file's bytes. Renaming a file does not make it new
work, and re-dropping the same content is recognised as the same work. That is
deterministic, needs no clock and no counter, and is what makes "cannot be
processed twice accidentally" a property rather than a hope.

Two requests that genuinely differ produce different bytes and different ids.
Two requests that are byte-identical are the same work item, which for this
worker is exactly right: the second one must not book the date twice.

## What lands where

```text
completed   accepted with its effect applied, OR refused by policy
            -> processed/    a policy refusal is a healthy, finished run
exception   the run failed, or an accepted decision's effect did not land
            -> exceptions/   retryable, deliberately, by moving it back
```
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fleet  # noqa: E402

LEDGER = "ledger.jsonl"
FOLDERS = ("inbox", "processed", "exceptions")


@dataclass(frozen=True)
class Item:
    path: Path
    item_id: str
    request: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure(w: fleet.Worker) -> None:
    for folder in FOLDERS:
        (w.directory / folder).mkdir(exist_ok=True)


def ledger(w: fleet.Worker) -> list[dict]:
    path = w.directory / LEDGER
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _append(w: fleet.Worker, record: dict) -> None:
    with (w.directory / LEDGER).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def item_state(w: fleet.Worker, item_id: str) -> Optional[str]:
    """The LAST recorded state for an item, or None if never seen."""
    state = None
    for entry in ledger(w):
        if entry["item_id"] == item_id:
            state = entry["state"]
    return state


def read_item(path: Path) -> Item:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    return Item(path, hashlib.sha256(raw).hexdigest(), payload["request"])


def waiting(w: fleet.Worker) -> list[Path]:
    """Files in the inbox, in a deterministic order."""
    return sorted((w.directory / "inbox").glob("*.json"))


def poll(w: fleet.Worker) -> list[dict]:
    """One deterministic pass over the inbox. Contains no LLM and no clock logic.

    Every item is claimed before it is run, so an interrupted pass leaves
    evidence rather than a fresh-looking file.
    """
    ensure(w)
    outcomes = []
    for path in waiting(w):
        try:
            item = read_item(path)
        except (OSError, ValueError, KeyError) as exc:
            record = {"at": _now(), "item_id": f"unreadable:{path.name}",
                      "file": path.name, "state": "exception",
                      "reason": f"unreadable work item: {type(exc).__name__}"}
            _append(w, record)
            shutil.move(str(path), w.directory / "exceptions" / path.name)
            outcomes.append(record)
            continue

        seen = item_state(w, item.item_id)
        if seen == "completed":
            # ALREADY DONE. Not re-run, and above all its effect is not
            # re-applied. The file is filed away so the inbox drains.
            record = {"at": _now(), "item_id": item.item_id, "file": path.name,
                      "state": "skipped_duplicate", "request": item.request,
                      "reason": "an item with identical content already completed"}
            _append(w, record)
            shutil.move(str(path), w.directory / "processed" / path.name)
            outcomes.append(record)
            continue

        _append(w, {"at": _now(), "item_id": item.item_id, "file": path.name,
                    "state": "claimed", "request": item.request})

        run = fleet.record_run(w, request=item.request)
        healthy = run["ok"]
        state = "completed" if healthy else "exception"
        destination = "processed" if healthy else "exceptions"
        record = {"at": _now(), "item_id": item.item_id, "file": path.name,
                  "state": state, "request": item.request,
                  "decision": run.get("decision"), "reason": run.get("reason"),
                  "effect_applied": run.get("effect_applied"),
                  "problems": run.get("problems", [])}
        _append(w, record)
        shutil.move(str(path), w.directory / destination / path.name)
        outcomes.append(record)
    return outcomes


def retry(w: fleet.Worker, filename: str) -> None:
    """Move one exception back to the inbox, deliberately.

    Retrying is a decision a person makes, so it is an explicit act rather than
    something the poller does on a timer. An item whose effect never landed will
    apply it on the retry; one that completed is caught by the ledger.
    """
    source = w.directory / "exceptions" / filename
    shutil.move(str(source), w.directory / "inbox" / filename)


def summary(w: fleet.Worker) -> dict:
    ensure(w)
    entries = ledger(w)
    final: dict[str, str] = {}
    for entry in entries:
        final[entry["item_id"]] = entry["state"]
    return {
        "waiting": len(waiting(w)),
        "processed": len(list((w.directory / "processed").glob("*.json"))),
        "exceptions": len(list((w.directory / "exceptions").glob("*.json"))),
        "items_seen": len(final),
        "completed": sum(1 for s in final.values() if s == "completed"),
        "in_flight": sum(1 for s in final.values() if s == "claimed"),
        "duplicates_skipped": sum(1 for e in entries
                                  if e["state"] == "skipped_duplicate"),
        "ledger_lines": len(entries),
    }


def _self_test() -> int:
    """Runs inside the lab, not the system temp dir.

    A worker's base is stored relative to the lab root, so a scratch worker has
    to live where that path can be expressed. Cleaned up either way.
    """
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    model = json.loads((fleet.LAB / "reservation" / "models" /
                        "reservation_v1.json").read_text(encoding="utf-8"))
    return _run_in_lab(check, failures, model)


def _run_in_lab(check, failures, model) -> int:
    import os
    import stat

    scratch = fleet.LAB / "fleet" / ".selftest"
    if scratch.exists():
        shutil.rmtree(scratch)
    try:
        root = scratch / "workers"
        root.mkdir(parents=True)
        base_rel = "fleet/.selftest/workers/inbox-worker/state"
        w = fleet.establish(root, "inbox-worker", "Inbox test.", "reservation",
                            base_rel, model)
        shutil.copytree(fleet.LAB / "reservation" / "fixtures",
                        w.directory / "state" / "fixtures")
        w = fleet.load(w.directory)
        ensure(w)

        def drop(name: str, request: str) -> Path:
            path = w.directory / "inbox" / name
            path.write_text(json.dumps({"request": request}) + "\n",
                            encoding="utf-8")
            return path

        def reservations() -> list:
            return json.loads((w.directory / "state" / "fixtures" /
                               "reservations.json").read_text(encoding="utf-8"))["reservations"]

        start = len(reservations())

        # --- a policy refusal COMPLETES normally --------------------------
        drop("a.json", "2026-12-25")
        out = poll(w)
        check(out[0]["state"] == "completed" and out[0]["reason"] == "HOLIDAY",
              f"a policy refusal must complete, not except: {out}")
        check((w.directory / "processed" / "a.json").is_file(),
              "…and be filed as processed")
        check(len(reservations()) == start, "…and change no state")

        # --- an acceptance applies its effect ------------------------------
        drop("b.json", "2026-04-02")
        out = poll(w)
        check(out[0]["state"] == "completed" and out[0]["effect_applied"] is True,
              f"an acceptance must complete with its effect applied: {out}")
        check(len(reservations()) == start + 1,
              f"…and worker state must grow: {reservations()}")

        # --- THE RETRY: identical content must not double-apply ------------
        after_first = list(reservations())
        drop("b-again.json", "2026-04-02")          # same bytes, new filename
        out = poll(w)
        check(out[0]["state"] == "skipped_duplicate",
              f"CANARY: identical content is the same work item: {out}")
        check(reservations() == after_first,
              f"CANARY: the effect must NOT be applied twice: {reservations()}")
        check(len(fleet.load(w.directory).runs) == 2,
              "CANARY: a duplicate must not even produce a run")

        # --- an effect that cannot land becomes an EXCEPTION ---------------
        target = w.directory / "state" / "fixtures" / "reservations.json"
        drop("c.json", "2026-05-05")
        os.chmod(target, stat.S_IREAD)
        try:
            out = poll(w)
        finally:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        check(out[0]["state"] == "exception"
              and out[0]["effect_applied"] is False,
              f"an accepted decision whose effect failed must except: {out}")
        check((w.directory / "exceptions" / "c.json").is_file(),
              "…and land in the exception queue")
        check(len(reservations()) == start + 1,
              f"…and have changed nothing: {reservations()}")

        # --- retrying an exception DOES apply it ---------------------------
        retry(w, "c.json")
        out = poll(w)
        check(out[0]["state"] == "completed"
              and out[0]["effect_applied"] is True,
              f"a retried exception must apply once the cause is gone: {out}")
        check(len(reservations()) == start + 2,
              f"…and state must grow exactly once: {reservations()}")

        # --- and now IT is a duplicate too ---------------------------------
        after_retry = list(reservations())
        drop("c-again.json", "2026-05-05")
        poll(w)
        check(reservations() == after_retry,
              f"CANARY: a completed retry cannot be re-applied: {reservations()}")

        # --- an unreadable item excepts rather than stopping the pass ------
        (w.directory / "inbox" / "bad.json").write_text("{not json",
                                                        encoding="utf-8")
        drop("d.json", "2026-06-01")
        out = poll(w)
        states = {o["file"]: o["state"] for o in out}
        check(states.get("bad.json") == "exception",
              f"an unreadable item must except: {states}")
        check(states.get("d.json") == "completed",
              f"CANARY: and must not stop the rest of the pass: {states}")

        # --- the ledger is append-only and the summary agrees --------------
        s = summary(w)
        check(s["waiting"] == 0 and s["in_flight"] == 0,
              f"the inbox must drain: {s}")
        check(s["duplicates_skipped"] == 2, f"two duplicates skipped: {s}")
        check(s["exceptions"] == 1, f"one item left in the queue (bad.json): {s}")
        entries = ledger(w)
        # The invariant that matters: one claim per run, no more and no fewer.
        # A duplicate produces neither; an unreadable item produces neither.
        claims = [e["state"] for e in entries].count("claimed")
        check(claims == len(fleet.load(w.directory).runs),
              f"exactly one claim per run: {claims} claim(s), "
              f"{len(fleet.load(w.directory).runs)} run(s)")
        check(s["ledger_lines"] == len(entries), "the summary reads the ledger")

    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (a policy refusal completes and changes no state / an "
          "acceptance applies its effect and grows state / identical content is "
          "the same work item, produces no run and does NOT apply twice / a "
          "failed effect excepts, queues and changes nothing / retrying applies "
          "it exactly once / the retried item is then itself a duplicate / an "
          "unreadable item excepts without stopping the pass / every run was "
          "claimed before it ran and the inbox drains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
