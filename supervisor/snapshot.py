#!/usr/bin/env python3
"""A read-only snapshot of the fleet, for a supervising LLM to reason about.

The deterministic fleet underneath is the authority; this module never invents a
second status model. It reads what `fleet`, `confirmations` and the inbox ledger
already produce and serialises it into one plain dict the supervisor (and its
Python bench) can inspect.

## Pure and read-only

`build()` touches no fleet file. It does not call `inbox.summary()` -- that
calls `inbox.ensure()`, which *creates* the inbox folders, a write. The snapshot
reads `ledger.jsonl` directly and computes the same counts itself. A self-test
canaries that building a snapshot over a fleet root leaves every file
byte-identical, and that two builds produce the same JSON (the snapshot is a
deterministic function of the fleet on disk -- no clock, no mtimes, no trivia).

## What it includes

Enough to reason about supervision without prescribing what matters:

  scopes/customers, workers, current model + version history, recent runs with
  outcomes and refusal/problem codes, effect attempted vs effect_applied, open
  investigations (pending exceptions), version-bound human confirmations, and
  inbox state where a worker has one.

It deliberately does NOT include filesystem mtimes or incidental trivia.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "fleet"))

import fleet  # noqa: E402
import confirmations  # noqa: E402

SCHEMA = "supervisor.snapshot/v1"
RECENT_RUNS = 25  # cap per worker; the seeded fleet has fewer, so this is a ceiling


def _inbox_state(w: fleet.Worker) -> Optional[dict]:
    """Read the inbox ledger directly. Never call inbox.ensure/summary (they write)."""
    path = w.directory / "ledger.jsonl"
    if not path.is_file():
        return None
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8")
               .splitlines() if line.strip()]
    final: dict[str, str] = {}
    ever_completed: set[str] = set()
    for e in entries:
        final[e["item_id"]] = e["state"]
        if e["state"] in ("completed", "recovered_completed"):
            ever_completed.add(e["item_id"])

        def _count(folder: str) -> int:
            d = w.directory / folder
            return len([p for p in d.iterdir() if p.is_file()]) if d.is_dir() else 0
    return {
        "has_inbox": True,
        "ledger_lines": len(entries),
        "items_seen": len(final),
        "completed": len(ever_completed),
        "waiting": sum(1 for s in final.values() if s == "waiting"),
        "in_flight": sum(1 for s in final.values() if s == "claimed"),
        "processed_files": _count("processed"),
        "exception_files": _count("exceptions"),
        "duplicates_skipped": sum(1 for e in entries if e["state"] == "skipped_duplicate"),
        "recovered": sum(1 for e in entries if str(e["state"]).startswith("recovered_")),
        "recent": list(reversed(entries))[:15],
    }


def _worker_record(w: fleet.Worker) -> dict:
    runs = list(w.runs)
    return {
        "name": w.name,
        "purpose": w.purpose,
        "task": w.task,
        "engine": w.engine,
        "customer": w.identity.get("customer"),
        "trigger": w.trigger,
        "committing": w.committing,
        "effect": w.effect,
        "current_version": w.current_version,
        "version_count": len(w.versions),
        "readable_model": fleet.readable(w),
        "summary": w.summary(),
        "version_history": w.history,
        "recent_runs": list(reversed(runs))[:RECENT_RUNS],
        "runs_total": len(runs),
        "investigation": w.investigation,
        "confirmations": confirmations.load(w.directory),
        "inbox": _inbox_state(w),
    }


def build(root: Path) -> dict:
    """Serialise the fleet under `root` into one plain, JSON-serialisable dict.

    Pure and deterministic: a function of the files on disk, nothing else.
    """
    workers = fleet.load_all(root)
    scopes = sorted({w.identity.get("customer") for w in workers
                     if w.identity.get("customer")})
    records = [_worker_record(w) for w in workers]
    pending = [{
        "worker": w.name,
        "state": w.open_investigation["state"],
        "opened": w.open_investigation.get("opened"),
        "from_version": w.open_investigation.get("from_version"),
        "failure": w.open_investigation.get("failure", []),
        "difference": w.open_investigation.get("difference", {}),
        "question": w.open_investigation.get("question"),
    } for w in workers if w.open_investigation]
    return {
        "schema": SCHEMA,
        "scopes": scopes,
        "worker_count": len(records),
        "workers": records,
        "pending_exceptions": pending,
    }


def hash_snapshot(snapshot: dict) -> str:
    """A stable identity for the snapshot the model actually saw."""
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


def _hash_tree(root: Path) -> str:
    """Hash every file's contents under root, in sorted path order."""
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        h.update(str(p.relative_to(root)).replace("\\", "/").encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _self_test() -> int:
    import shutil
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    root = fleet.ROOT
    if not root.is_dir() or not fleet.load_all(root):
        # Seed a tiny scratch fleet so the canary runs without depending on seed.py.
        root = Path(tempfile.mkdtemp()) / "workers"
        root.mkdir(parents=True)
        model = json.loads((LAB / "worker" / "established" /
                            "timesheet-cost-v1.json").read_text(encoding="utf-8"))
        fleet.establish(root, "tw", "Cost each timesheet entry.", "enrichment",
                        "data", model)
        try:
            return _run_self_test(root, failures, check)
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
    return _run_self_test(root, failures, check)


def _run_self_test(root: Path, failures: list[str], check) -> int:
    # --- CANARY: building a snapshot changes no fleet file ----------------
    before = _hash_tree(root)
    snap = build(root)
    after = _hash_tree(root)
    check(before == after,
          f"CANARY: building a snapshot must not change any fleet file "
          f"(before {before} != after {after})")

    # --- deterministic: two builds produce identical JSON -----------------
    snap2 = build(root)
    check(json.dumps(snap, sort_keys=True) == json.dumps(snap2, sort_keys=True),
          "CANARY: build() must be deterministic across calls")

    # --- serialisable and well-formed -------------------------------------
    check(snap["schema"] == SCHEMA, f"schema tag present: {snap['schema']}")
    for w in snap["workers"]:
        check(set(w) >= {"name", "purpose", "task", "summary", "recent_runs",
                         "version_history", "confirmations", "inbox"},
              f"worker record has the expected keys: {set(w)}")
    json.dumps(snap)  # raises if not serialisable

    # --- a real seeded fleet exposes the things supervision cares about ---
    workers = fleet.load_all(root)
    if len(workers) >= 3:
        names = {w.name for w in workers}
        check("pending_exceptions" in snap and isinstance(snap["pending_exceptions"], list),
              "pending exceptions collected")
        # At least one worker carries refusals or an effect record or a confirmation
        # somewhere in the fleet -- the material supervision reasons about.
        has_refusals = any(r.get("refused", 0) or r.get("refusals")
                           for w in snap["workers"] for r in w["recent_runs"])
        has_effect = any(r.get("effect_applied") is not None
                         for w in snap["workers"] for r in w["recent_runs"])
        has_confirmations = any(w["confirmations"] for w in snap["workers"])
        check(has_refusals or has_effect or has_confirmations,
              f"fleet exposes refusals/effects/confirmations to reason about "
              f"(refusals={has_refusals}, effect={has_effect}, "
              f"confirmations={has_confirmations})")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (build is read-only: {_hash_tree(root)} unchanged / "
          f"deterministic across calls / serialisable with the expected keys / "
          f"fleet exposes refusals, effects or confirmations to reason about)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)