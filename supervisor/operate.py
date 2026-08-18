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


def save_to_inbox(w, filename: str, data: bytes, role: Optional[str] = None) -> Path:
    """Write `data` into the worker's real `inbox/<filename>`.

    Ensures the inbox folders exist (the ordinary `ensure`). Returns the path.
    No processing: the file just lands where the ordinary poller will find it.

    `role` (v0.6 Phase 7): if given, also writes the `<filename>.role` sidecar
    naming the slot the operator assigned this file to -- the Phase 4 binding
    mechanism for SOLE slots (filename is not authority; the operator's slot
    choice is). `role=None` writes no sidecar, which is correct for shared-slot
    workers (one upload binds all shared slots, no choice) and for non-contract
    workers.
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
    if role:
        (w.directory / "inbox" / f"{safe}.role").write_text(role, encoding="utf-8")
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


def slot_choice(w) -> Optional[dict]:
    """The operator-facing slot picture for a contract worker (v0.6 Phase 7).

    Returns ``{"sole": [...], "shared": [...], "mixed": bool}`` -- the role
    keys grouped by slot kind -- or None for a non-contract worker (no slots,
    so the v0.5 upload-and-process surface is unchanged). A sole-slot file
    needs an explicit role sidecar (the operator picks the slot); a shared-slot
    file binds all shared roles with one upload (no choice). A mixed worker
    (both sole and shared) is refused by the bind path; ``mixed`` flags it so
    the panel can say so rather than offer a broken choice.
    """
    if w.input_contract is None:
        return None
    roles = w.identity.get("source_roles") or {}
    sole = sorted(r for r, info in roles.items() if info.get("slot") == "sole")
    shared = sorted(r for r, info in roles.items() if info.get("slot") == "shared")
    return {"sole": sole, "shared": shared, "mixed": bool(sole and shared)}


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

        # --- v0.6 Phase 7: the operator binding surface (sole + shared) ----
        # save_to_inbox with a role writes the .role sidecar the Phase 4 bind
        # path reads for sole slots; slot_choice reports the operator-facing
        # picture. This drives the ORDINARY poll path -- no dashboard execution.
        scratch7 = LAB / "fleet" / ".selftest-operate-v06"
        if scratch7.exists():
            shutil.rmtree(scratch7)
        sroot = scratch7 / "workers"
        sroot.mkdir(parents=True)

        def _contract_worker(wname, model_file, task, source_roles, contract, base_tail):
            model = json.loads((LAB / "fleet" / "workers" / model_file
                                ).read_text(encoding="utf-8"))
            base = f"fleet/.selftest-operate-v06/workers/{wname}/{base_tail}"
            cw = fleet.establish(sroot, wname, "Operate bind test.", task, base, model)
            ident = json.loads((cw.directory / "worker.json").read_text(encoding="utf-8"))
            ident.update({"input_adapter": "xlsx", "work_item_identity": "content_digest",
                          "source_roles": source_roles})
            (cw.directory / "worker.json").write_text(
                json.dumps(ident, indent=2) + "\n", encoding="utf-8")
            cdir = cw.directory / "input_contracts"
            cdir.mkdir()
            (cdir / "v1.json").write_text(
                json.dumps(contract, indent=2) + "\n", encoding="utf-8")
            return fleet.load(cw.directory)

        # a non-contract worker (the reservation worker above) -> no slots
        check(slot_choice(w) is None,
              "slot_choice is None for a non-contract worker (v0.5 surface)")

        # ACME: two sole slots. The operator picks the slot for each upload.
        acme_roles = {
            "statement": {"label": "supplier statement", "slot": "sole", "required": True},
            "transactions": {"label": "ledger transactions", "slot": "sole", "required": True}}
        acme_contract = {"roles": {
            "statement": {"sheet": "Statement", "collection": "statement", "header_row": 3},
            "transactions": {"sheet": "Transactions", "collection": "transactions", "header_row": 2}}}
        aw = _contract_worker("acme", "acme-august-recon/versions/v1.json", "reconciliation",
                              acme_roles, acme_contract, "state")
        check(slot_choice(aw) == {"sole": ["statement", "transactions"],
                                  "shared": [], "mixed": False},
              f"slot_choice for a 2-sole contract worker: {slot_choice(aw)}")
        sup = (LAB / "data" / "acme-august" / "supplier.xlsx").read_bytes()
        save_to_inbox(aw, "supplier.xlsx", sup, role="statement")
        check((aw.directory / "inbox" / "supplier.xlsx.role").read_text(encoding="utf-8")
              == "statement", "save_to_inbox wrote the .role sidecar for the sole slot")
        out = poll_inbox(aw)
        check(len(out) == 1 and out[0]["state"] == "staged"
              and out[0]["roles"] == ["statement"],
              f"the statement binds via the ordinary poll (partial 1/2): {out}")
        check(len(fleet.load(aw.directory).runs) == 0, "a partial set fires no run")
        led = (LAB / "data" / "acme-august" / "ledger.xlsx").read_bytes()
        save_to_inbox(aw, "ledger.xlsx", led, role="transactions")
        out = poll_inbox(aw)
        runs = fleet.load(aw.directory).runs
        check(len(runs) == 1 and runs[-1]["ok"]
              and all(o["state"] == "completed" for o in out),
              f"the transactions completes the set and fires ONE ok run via "
              f"the ordinary poll (terminalize emits one record per bound "
              f"document): {out} runs={len(runs)}")

        # FAZERISH: two shared slots. ONE upload binds both; no slot choice,
        # no sidecar.
        faz_roles = {
            "order_lines": {"label": "order lines", "slot": "shared", "required": True},
            "price_list": {"label": "price list", "slot": "shared", "required": True}}
        faz_contract = {"roles": {
            "order_lines": {"sheet": "Order lines", "collection": "order_lines", "header_row": 1},
            "price_list": {"sheet": "Price list", "collection": "price_list", "header_row": 1}}}
        fw = _contract_worker("faz", "fazerish-invoicing/versions/v1.json", "enrichment",
                              faz_roles, faz_contract, "state")
        check(slot_choice(fw) == {"sole": [], "shared": ["order_lines", "price_list"],
                                  "mixed": False},
              f"slot_choice for a shared contract worker: {slot_choice(fw)}")
        may = (LAB / "data" / "xlsx-fazerish" / "may-order-lines.xlsx").read_bytes()
        save_to_inbox(fw, "may.xlsx", may)  # NO role: shared binds all
        check(not (fw.directory / "inbox" / "may.xlsx.role").is_file(),
              "no sidecar for a shared upload (no slot choice)")
        out = poll_inbox(fw)
        check(len(out) == 1 and out[0]["state"] == "completed"
              and sorted(out[0]["roles"]) == ["order_lines", "price_list"],
              f"a shared upload binds both slots and completes via the ordinary "
              f"poll: {out}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(LAB / "fleet" / ".selftest-operate-v06", ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (save_to_inbox lands bytes in the real inbox + "
          "guards against path escape / poll_inbox delegates to the ordinary "
          "fleet.inbox.poll which writes the ledger, moves the file to "
          "processed, and lands the committing effect -- no dashboard path / "
          "Phase 7: save_to_inbox with a role writes the sole-slot sidecar and "
          "binds via the ordinary poll (statement stages, transactions "
          "completes and runs), a shared upload binds all shared slots with no "
          "sidecar, slot_choice reports sole/shared/mixed or None)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)