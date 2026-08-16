#!/usr/bin/env python3
"""Wire the investigator to the fleet's real exception queue.

The two halves existed independently. This is the join:

```text
work -> deterministic worker -> EXCEPTION -> packet          (fleet, no LLM)
                                              |
                                    operator opens it
                                              v
        packet -> LLM interpretation -> sufficiency gate     (experimentZ)
                                              |
                    +-------------------------+------------------+
                    v                                            v
            evidence sufficient                         evidence ambiguous
            -> PROPOSAL, shown                          -> QUESTION, one
                    |                                      human answer
                    v                                            |
            operator applies -> v2 established <----------------+
                    v
            queued work retried under v2
```

## Two axes, kept apart

Experiment Y settled the *epistemic* question: whether the evidence establishes
a replacement. It does not settle the *operational* one — whether a production
worker should change now. Those are different axes, the same way an input
contract is not a source interpretation.

So a mechanically sufficient repair is **proposed, not applied**. The operator
clicks once. That is not the system asking permission to think; it is a person
deciding when a live worker changes.

## The LLM is not in the unattended path

Nothing here runs during `poll()` or `recover()`. An exception sits in the queue
until an operator opens it. That keeps the architecture's central claim true:
the fleet runs without a model, and one is woken only for a specific failure.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "worker"))

import fleet  # noqa: E402
import inbox as inbox_mod  # noqa: E402
import worker as W  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Experiment Z's investigator, unchanged.
Z = _load("_z_investigate", LAB / "experimentZ" / "harness" / "investigate.py")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def packet_of(w: fleet.Worker) -> Optional[dict]:
    path = w.directory / "last_packet.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def needs_investigation(w: fleet.Worker) -> bool:
    """An unresolved contract failure with a packet and no investigation yet."""
    if w.investigation and w.investigation.get("state") in ("open", "proposed"):
        return False
    return bool(w.runs and not w.runs[-1]["ok"] and packet_of(w))


def _write(w: fleet.Worker, record: dict) -> fleet.Worker:
    (w.directory / "investigation.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return fleet.load(w.directory)


def investigate(w: fleet.Worker, ask: Callable[[str], str]) -> fleet.Worker:
    """Wake the investigator on this worker's packet. Operator-triggered."""
    packet = packet_of(w)
    if packet is None:
        raise ValueError(f"{w.name} has no exception packet to investigate")

    est = W.Established(w.name, w.current_version, w.model, w.base, _now())
    replacements, block, refusal = Z.investigate(est, packet, ask)

    base = {"opened": _now(), "from_version": w.current_version,
            "failure": packet.get("failure", []),
            "difference": packet.get("difference", {}),
            "measured": packet.get("measured_relationships", [])}

    if replacements:
        return _write(w, {**base, "state": "proposed", "proposal": replacements,
                          "why": "the replacement is the sole candidate with "
                                 "complete coverage and unique right-side keys"})
    if refusal:
        # The investigator proposed something the program's own gate refused.
        # That is not a question for the operator -- it is a rejected repair,
        # recorded verbatim so the attempt is visible.
        return _write(w, {**base, "state": "open", "question": refusal,
                          "options": _options(packet),
                          "gate_refused": True})
    entry = (block or [{}])[0]
    return _write(w, {**base, "state": "open",
                      "question": entry.get("question")
                                  or "The evidence does not settle this.",
                      "field": entry.get("field"),
                      "options": _options(packet)})


def _options(packet: dict) -> list[str]:
    """Mechanically sufficient candidates, for the operator to choose between."""
    lookup = None
    for rel in packet.get("measured_relationships", []):
        lookup = lookup or rel
    out = []
    for rel in packet.get("measured_relationships", []):
        left, right = rel["left"], rel["right"]
        covered, total = rel["left_coverage"].split("/")
        if covered == total and rel["right_unique"] and left.startswith(
                next(iter(packet.get("expected_fields", {"": []}))) or ""):
            out.append(right)
    if out:
        return sorted(set(out))
    return sorted({rel["right"] for rel in packet.get("measured_relationships", [])
                   if rel["left_coverage"].split("/")[0]
                   == rel["left_coverage"].split("/")[1] and rel["right_unique"]})


def answer(w: fleet.Worker, choice: str) -> fleet.Worker:
    """A human settles the ambiguity. Becomes a proposal, still applied by hand."""
    inv = w.investigation or {}
    packet = packet_of(w) or {}
    absent = []
    for source, diff in (packet.get("difference") or {}).items():
        for field in diff.get("declared_but_absent", []):
            absent.append((source, field))
    if not absent:
        raise ValueError("nothing was declared-but-absent; nothing to replace")
    source, field = absent[0]
    to_source, _, to_field = choice.partition(".")
    replacements = [{"source": source, "from": field, "to": to_field or choice}]
    return _write(w, {**inv, "state": "proposed", "proposal": replacements,
                      "answered_by": "human", "answer": choice,
                      "why": f"a human settled the ambiguity as {choice}"})


def apply_proposal(w: fleet.Worker) -> fleet.Worker:
    """Establish v2 from the proposal. The operator's act, not the model's."""
    inv = w.investigation or {}
    if inv.get("state") != "proposed":
        raise ValueError(f"{w.name} has no proposal to apply")
    replacements = inv["proposal"]
    v2 = W.apply_replacements(w.model, replacements)
    return fleet.promote(w, v2, inv.get("why", "investigation proposal"),
                         replacements)


def retry_queued(w: fleet.Worker) -> list[dict]:
    """Move queued exceptions back to the inbox and run them under the CURRENT
    version. Items that already completed are still caught by the ledger."""
    queue = w.directory / "exceptions"
    if not queue.is_dir():
        return []
    names = sorted(p.name for p in queue.glob("*.json"))
    for name in names:
        inbox_mod.retry(w, name)
    return inbox_mod.poll(w) if names else []


def _self_test() -> int:
    import shutil
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    model = json.loads((LAB / "worker" / "established" /
                        "timesheet-cost-v1.json").read_text(encoding="utf-8"))
    scratch = LAB / "fleet" / ".selftest-inv"
    if scratch.exists():
        shutil.rmtree(scratch)
    try:
        root = scratch / "workers"
        root.mkdir(parents=True)

        def broken_worker(condition: str) -> fleet.Worker:
            name = f"tw-{condition}"
            w = fleet.establish(root, name, "Cost timesheets.", "enrichment",
                                "data", model)
            fleet.record_run(w)                       # healthy
            w = fleet.rebase(w, f"experimentZ/fixtures/{condition}")
            fleet.record_run(w)                       # exception
            return fleet.load(w.directory)

        # --- SUFFICIENT: a proposal, NOT an application -------------------
        w = broken_worker("A")
        check(needs_investigation(w), "a worker with a packet needs investigating")
        proposal = json.dumps({"REPLACEMENTS": [
            {"source": "staff", "from": "staff_id", "to": "employee_id"}]})
        w = investigate(w, lambda prompt: proposal)
        check(w.investigation["state"] == "proposed",
              f"a supported repair becomes a PROPOSAL: {w.investigation}")
        check(w.current_version == 1,
              "CANARY: and is NOT applied -- a live worker changes when a "
              "person says so")
        w = apply_proposal(w)
        check(w.current_version == 2
              and w.model["lookup"]["match_right"] == "employee_id",
              f"applying establishes v2: {w.model['lookup']}")
        out = fleet.record_run(w)
        check(out["ok"], f"and the worker runs again: {out}")
        check(len(w.runs_for(1)) == 2 and len(w.runs_for(2)) == 1,
              f"v1 keeps its runs; v2 starts fresh: {w.summary()}")

        # --- AMBIGUOUS: a question, then one human answer -----------------
        w = broken_worker("B")
        blocked = json.dumps({"CANNOT_ESTABLISH": [
            {"source": "staff", "field": "staff_id", "binding": "join key",
             "question": "employee_id or staff_code?"}]})
        w = investigate(w, lambda prompt: blocked)
        check(w.investigation["state"] == "open",
              f"an ambiguous world becomes a QUESTION: {w.investigation}")
        check(set(w.investigation["options"])
              == {"staff.employee_id", "staff.staff_code"},
              f"…offering both sufficient candidates: "
              f"{w.investigation.get('options')}")
        w = answer(w, "staff.employee_id")
        check(w.investigation["state"] == "proposed"
              and w.investigation["proposal"][0]["to"] == "employee_id",
              f"the answer becomes a proposal: {w.investigation}")
        w = apply_proposal(w)
        check(w.current_version == 2
              and w.model["lookup"]["match_right"] == "employee_id",
              "and applying it establishes v2")

        # --- CANARY: the gate still refuses an unsupported proposal -------
        w = broken_worker("C")
        bad = json.dumps({"REPLACEMENTS": [
            {"source": "staff", "from": "staff_id", "to": "record"}]})
        w = investigate(w, lambda prompt: bad)
        check(w.investigation["state"] == "open"
              and w.investigation.get("gate_refused"),
              f"CANARY: a proposal the measurements do not support must NOT "
              f"become a proposal: {w.investigation}")
        check(w.current_version == 1, "…and the worker is unchanged")

        # --- retry_queued moves queued work under the new version ---------
        res = json.loads((LAB / "reservation" / "models" / "reservation_v1.json")
                         .read_text(encoding="utf-8"))
        rw = fleet.establish(root, "rw", "Reserve.", "reservation",
                             "fleet/.selftest-inv/workers/rw/state", res)
        ident = json.loads((rw.directory / "worker.json").read_text(encoding="utf-8"))
        ident["work_item_identity"] = "content_digest"
        (rw.directory / "worker.json").write_text(
            json.dumps(ident, indent=2) + chr(10), encoding="utf-8")
        rw = fleet.load(rw.directory)
        shutil.copytree(LAB / "reservation" / "fixtures", rw.directory / "state" / "fixtures")
        inbox_mod.ensure(rw)
        (rw.directory / "exceptions" / "queued.json").write_text(
            json.dumps({"request": "2026-04-02"}) + chr(10), encoding="utf-8")
        out = retry_queued(fleet.load(rw.directory))
        check(out and out[0]["state"] == "completed"
              and out[0]["effect_applied"] is True,
              f"queued work is retried and applied: {out}")
        check(not list((rw.directory / "exceptions").glob("*.json")),
              "…and the queue drains")

    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (a worker with a packet needs investigating / a "
          "supported repair becomes a PROPOSAL and is not applied until a "
          "person applies it / applying establishes v2, the worker runs again, "
          "v1 keeps its runs / an ambiguous world becomes a QUESTION offering "
          "both sufficient candidates, and one human answer becomes a proposal "
          "/ a proposal the measurements do not support is refused by the gate "
          "and leaves the worker unchanged / queued work is retried under the "
          "current version and the queue drains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
