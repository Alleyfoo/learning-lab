#!/usr/bin/env python3
"""Version-bound human confirmations that no construct carries.

`f575c09` measured the hole precisely:

> An answer that CHANGED THE MODEL survives as the model; an answer that changed
> nothing survives nowhere.

The bookkeeper's *"these are all unpaid invoices"* is load-bearing — the total is
"what we owe" only if it is true — and it altered no construct, so on reload it
was gone. `confirmed_by` and `CONFIRMED` appeared nowhere on disk.

This closes only that hole.

```text
confirmations.jsonl   append-only, one line per confirmation, TAGGED WITH ITS
                      VERSION
```

## Version-bound, and authority is NOT automatically inherited

A confirmation was given about a particular established model. v2 gets neither
v1's confirmation nor any retroactive authority from it: someone must establish
that truth again for v2. That is the conservative rule these tests actually
demonstrate, and it is stricter than the promotion rule for models — a promoted
model carries forward as the thing that runs, but a human answer about the world
does not carry forward at all.

The lineage is `scripts/agent_binding.py`'s: adopting now certifies nothing
about a past run. Here the same caution points the other way too — a past answer
certifies nothing about a new version.

## Reconstructed as CONFIRMED, never OBSERVED

Replaying a stored human act produces a `CONFIRMED` claim carrying who settled
it and when. It never produces `OBSERVED`: nothing here was measured, and a
program that could turn a remembered answer into an observation would be
laundering provenance exactly as Experiment T did. `mechanically_verifiable` is
recorded and is `false` for this fixture — the export exposes no payment status,
so nothing can re-prove it.

## What this is NOT

Not a source-contract language. There is no vocabulary of assumption kinds, no
inheritance, no re-verification policy. One fixture, one shape: an obligation, a
referent, an answer, a person, a version.
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FILENAME = "confirmations.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(directory: Path, version: int, obligation: str, clause: str,
           referent: str, answer: str, by: str = "human",
           mechanically_verifiable: bool = False) -> dict:
    """Append one confirmation. Never rewrites an earlier line."""
    entry = {"at": _now(), "version": int(version), "obligation": obligation,
             "clause": clause, "referent": referent, "answer": answer,
             "status": "CONFIRMED", "confirmed_by": by,
             "mechanically_verifiable": bool(mechanically_verifiable)}
    with (directory / FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load(directory: Path, version: Optional[int] = None) -> list[dict]:
    path = directory / FILENAME
    if not path.is_file():
        return []
    entries = [json.loads(line)
               for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    if version is None:
        return entries
    return [e for e in entries if e["version"] == version]


def as_claims(directory: Path, version: int) -> list[dict]:
    """Rebuild them in the claim shape the rest of the chain speaks.

    `status` is CONFIRMED and cannot be anything else -- see the module
    docstring. `basis` names the person, not a measurement.
    """
    out = []
    for entry in load(directory, version):
        out.append({
            "claim": {"referent": entry["referent"],
                      "obligation": entry["obligation"],
                      "meaning": entry["answer"]},
            "status": "CONFIRMED",
            "confirmed_by": entry["confirmed_by"],
            "basis": "human_confirmation",
            "mechanically_verifiable": entry["mechanically_verifiable"],
            "at": entry["at"], "version": entry["version"]})
    return out


def discharged(directory: Path, version: int) -> set:
    """Obligation ids a stored confirmation answers, for this version only."""
    return {e["obligation"] for e in load(directory, version)}


class EstablishmentFailed(Exception):
    """Establishment did not happen. Nothing partial is left behind."""


@dataclass
class Pending:
    """An answer given during DEFINE, before any version exists.

    A confirmation is bound to a version, and during DEFINE there is none -- the
    model is still a proposal. So answers wait here and are written only when a
    version is created, which is also the only moment their version number is
    known.
    """
    obligation: str
    clause: str
    referent: str
    answer: str
    by: str = "human"
    mechanically_verifiable: bool = False


def required_confirmations(obligations_list: list, manifest: dict) -> set:
    """Obligations the manifest says a person answered. These must persist."""
    out = set()
    for obligation in obligations_list or []:
        entry = (manifest or {}).get(obligation["id"])
        if isinstance(entry, dict) and entry.get("via") == "question":
            out.add(obligation["id"])
    return out


def establish(root: Path, name: str, purpose: str, task: str, base: str,
              model: dict, obligations_list: list, manifest: dict,
              pending: list, trigger: Optional[str] = None,
              establish_fn=None):
    """Create the version AND persist every confirmation its manifest requires.

    Either both happen or neither is reported. If a required confirmation cannot
    be written and read back, the worker directory is removed and
    `EstablishmentFailed` is raised -- a worker that runs while the truth it
    depends on was silently lost is worse than one that was never established.
    """
    required = required_confirmations(obligations_list, manifest)
    supplied = {p.obligation for p in pending}
    missing = required - supplied
    if missing:
        raise EstablishmentFailed(
            f"manifest requires human confirmation for {sorted(missing)} and no "
            f"answer was given; establishment refused")

    if establish_fn is None:
        import fleet as _fleet
        establish_fn = _fleet.establish
    worker = establish_fn(root, name, purpose, task, base, model,
                          trigger=trigger)
    directory = worker.directory
    version = worker.current_version
    try:
        for item in pending:
            if item.obligation in required:
                record(directory, version, item.obligation, item.clause,
                       item.referent, item.answer, item.by,
                       item.mechanically_verifiable)
        # Read back from disk. A write that returned is not evidence -- the same
        # rule the committing runtime applies to its effects.
        landed = discharged(directory, version)
        if not required <= landed:
            raise EstablishmentFailed(
                f"required confirmations {sorted(required - landed)} did not "
                f"persist")
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return worker


def _self_test() -> int:
    import shutil
    failures: list[str] = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    sys.path.insert(0, str(HERE.parent / "modeller"))
    import manifest as M

    scratch = HERE / ".selftest-conf"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    try:
        # The bookkeeping fixture: an obligation nothing in the model carries.
        obs = [{"id": "o1", "clause": "total what we owe each supplier"},
               {"id": "o2", "clause": "the rows are outstanding invoices"}]
        inventory = ("group_by:Supplier", "sum:Gross")
        man = {"o1": {"via": "construct", "construct": "sum:Gross"},
               "o2": {"via": "question"}}

        # --- unanswered, it BLOCKS -----------------------------------------
        ok(M.check(obs, man, inventory, asked=[]),
           "CANARY: an unanswered question must still block establishment")

        record(scratch, 1, "o2",
               "the rows are outstanding invoices",
               "purchase_invoices.Gross",
               "all six invoices are unpaid; none has been settled")

        # --- RELOAD, as a restart would --------------------------------------
        claims = as_claims(scratch, 1)
        ok(len(claims) == 1, f"one confirmation reloads: {claims}")
        claim = claims[0]
        ok(claim["status"] == "CONFIRMED",
           f"it must reload as CONFIRMED: {claim['status']}")
        ok(claim["status"] != "OBSERVED" and claim["basis"] == "human_confirmation",
           "CANARY: a remembered answer must NEVER become an observation -- "
           "nothing here was measured")
        ok(claim["confirmed_by"] == "human" and claim["at"],
           f"provenance survives: {claim}")
        ok(claim["claim"]["referent"] == "purchase_invoices.Gross"
           and claim["claim"]["obligation"] == "o2",
           f"the exact obligation and referent survive: {claim['claim']}")
        ok(claim["mechanically_verifiable"] is False,
           "…and that it cannot be re-proven is recorded, not implied")

        ok(discharged(scratch, 1) == {"o2"},
           f"the stored answer discharges its obligation: {discharged(scratch, 1)}")

        # --- VERSION-BOUND ---------------------------------------------------
        ok(as_claims(scratch, 2) == [] and discharged(scratch, 2) == set(),
           "CANARY: v2 must NOT inherit v1's confirmation -- authority is not "
           "automatically inherited across versions")
        record(scratch, 2, "o2", "the rows are outstanding invoices",
               "purchase_invoices.Gross", "still unpaid as of the July export")
        ok(len(load(scratch, 1)) == 1 and len(load(scratch, 2)) == 1,
           "each version keeps its own answer")
        ok(load(scratch, 1)[0]["answer"].startswith("all six"),
           "CANARY: v1's line is untouched by v2's -- append only")

        # --- ESTABLISHMENT is all-or-nothing --------------------------------
        import fleet as _fleet
        model = json.loads((HERE.parent / "data" / "xlsx-purchases" /
                            "established_model.json").read_text(encoding="utf-8"))
        root = scratch / "workers"
        root.mkdir(exist_ok=True)
        pend = [Pending("o2", obs[1]["clause"], "purchase_invoices.Gross",
                        "all six invoices are unpaid")]

        # a required confirmation with no answer refuses, and leaves nothing
        try:
            establish(root, "w-missing", "p", "aggregation", "data", model,
                      obs, man, [])
            ok(False, "CANARY: establishment must refuse when a required "
                      "confirmation was never answered")
        except EstablishmentFailed:
            ok(not (root / "w-missing").exists(),
               "CANARY: and must leave no half-established worker behind")

        # a persistence failure is reported as failure, not success
        def _broken(*a, **k):
            w = _fleet.establish(*a, **k)
            (w.directory / FILENAME).mkdir()      # make the append impossible
            return w

        try:
            establish(root, "w-broken", "p", "aggregation", "data", model,
                      obs, man, pend, establish_fn=_broken)
            ok(False, "CANARY: a failed confirmation write must fail the "
                      "establishment")
        except Exception:
            ok(not (root / "w-broken").exists(),
               "CANARY: and must roll the worker back")

        worker = establish(root, "w-ok", "p", "aggregation", "data", model,
                           obs, man, pend)
        v = worker.current_version
        ok(discharged(worker.directory, v) == {"o2"},
           "a good establishment persists its required confirmations")

        # --- RELOAD reproduces the establishable state, no second question --
        reloaded = _fleet.load(worker.directory)
        ok(M.check(obs, man, inventory,
                   asked=list(discharged(reloaded.directory,
                                         reloaded.current_version))) == [],
           "CANARY: reload must be establishable again WITHOUT asking anyone")
        ok(as_claims(reloaded.directory, v)[0]["status"] == "CONFIRMED",
           "…with the answer still CONFIRMED")

        # --- THROUGH THE UI-FACING HANDLER, end to end ----------------------
        # Same function modeller/app.py calls. The UI hands the whole Question
        # back; it never reconstructs an obligation id from the question text.
        import pipeline as PL
        PL.pending_clear()
        block = [{"source": "purchase_invoices", "field": "Gross",
                  "obligation": "o2", "binding": "outstanding",
                  "question": "Are these invoices unpaid, or already paid?"}]
        q = PL.questions_from(block, [])[0]
        ok(q.obligation == "o2",
           f"CANARY: the question must CARRY its obligation id: {q}")
        PL.submit_answer([], q, "all six invoices are unpaid")
        pending2 = [Pending(**x) for x in PL.pending_answers()]
        ok([x.obligation for x in pending2] == ["o2"]
           and pending2[0].referent == "purchase_invoices.Gross",
           f"the UI handler produced an addressed pending confirmation: "
           f"{PL.pending_answers()}")

        w2 = establish(root, "w-ui", "p", "aggregation", "data", model,
                       obs, man, pending2)
        v2 = w2.current_version
        del w2
        back = _fleet.load(root / "w-ui")
        claim = as_claims(back.directory, back.current_version)[0]
        ok(claim["status"] == "CONFIRMED"
           and claim["claim"]["obligation"] == "o2"
           and claim["claim"]["referent"] == "purchase_invoices.Gross",
           f"CANARY: after restart, CONFIRMED / o2 / purchase_invoices.Gross: "
           f"{claim}")
        ok(M.check(obs, man, inventory,
                   asked=list(discharged(back.directory,
                                         back.current_version))) == [],
           "CANARY: and it runs without asking again")

        # --- NEGATIVE: an answer with no address ---------------------------
        PL.pending_clear()
        anon = PL.Question("purchase_invoices", "Gross", "b",
                           "Are these unpaid?")
        ok(anon.obligation is None, "a question with no obligation id")
        PL.submit_answer([], anon, "yes, unpaid")
        ok(PL.pending_answers() == [],
           f"CANARY: an unaddressed answer must NOT become a generic "
           f"confirmation: {PL.pending_answers()}")
        ok(PL.UNADDRESSED and PL.UNADDRESSED[0]["answer"] == "yes, unpaid",
           "…it is left visible as unresolved rather than dropped")
        try:
            establish(root, "w-anon", "p", "aggregation", "data", model,
                      obs, man, [Pending(**x) for x in PL.pending_answers()])
            ok(False, "CANARY: establishment must still refuse -- the "
                      "obligation nobody addressed is unanswered")
        except EstablishmentFailed:
            ok(not (root / "w-anon").exists(), "…and nothing is left behind")
        PL.pending_clear()

        # --- an answer for the WRONG version does not discharge -------------
        ok(M.check(obs, man, inventory,
                   asked=list(discharged(scratch, 3))) != [],
           "CANARY: a version with no stored answer still blocks")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (an unanswered question still blocks / a stored "
          "answer reloads as CONFIRMED and never OBSERVED, with its person, "
          "time, exact obligation and referent, and mechanically_verifiable "
          "recorded / it discharges its obligation / v2 does NOT inherit v1's "
          "confirmation and v1's line is untouched / a version with no stored "
          "answer still blocks / establishment REFUSES when a required "
          "confirmation was never answered and when its write fails, rolling "
          "the worker back both times / a good establishment persists them and "
          "reload is establishable again WITHOUT asking anyone / THROUGH THE "
          "UI-FACING HANDLER a question carries its obligation id, the answer "
          "persists, and after restart CONFIRMED/o2/purchase_invoices.Gross "
          "runs without asking again / an answer with NO address never becomes "
          "a generic confirmation -- it stays visibly unresolved and "
          "establishment still refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
