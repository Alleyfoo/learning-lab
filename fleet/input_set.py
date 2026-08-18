#!/usr/bin/env python3
"""The worker's one open input set -- bindings for the next run.

v0.6 introduces a durable object between "a file arrived" and "a run fired":
the INPUT SET. A run fires only when every required source ROLE is bound to a
validated, materialized document. For a shared-slot worker (fazerish: one
workbook fills two slots) the set completes on the first arrival -- the
existing per-file run recast as "one document completes a 2-slot set". For a
multi-sole-slot worker (acme: statement + transactions) the set is PARTIAL
until every sole slot is bound -- a reconciliation cannot run on one side.

One open set per worker (design note §5.1) -- an explicit v0.6 limitation.
The run record carries `input_set` so a future `input_set_id` (overlapping
periods in flight) is forward-compatible without changing this shape.

Binding is an operator act + shape validation, never filename inference. The
filename and digest are provenance, not the grounds for the binding: a file
named `untitled.xlsx` is a perfectly good `statement` instance if the operator
binds it there and the adapter validates its shape against the contract.

This module owns the set object and the binding operation. It does NOT fire
the run and does NOT touch the ledger -- `fleet/inbox.py` runs when the set
completes, so the inbox's claim/terminalize floor stays the authority. The
fingerprint and recovery contract live in Phase 4.5 (`inbox.reconcile`); the
atomic `run_input` on the run record lives in Phase 5 (`fleet.record_run`).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fleet  # noqa: E402

SET_FILE = "input_set.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path(w: "fleet.Worker") -> Path:
    return w.directory / SET_FILE


def load(w: "fleet.Worker") -> Optional[dict]:
    p = path(w)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def clear(w: "fleet.Worker") -> None:
    """Remove the open set. Called after a complete set's run is terminalized."""
    p = path(w)
    if p.is_file():
        p.unlink()


def _new(w: "fleet.Worker") -> dict:
    return {"worker": w.name, "model": w.current_version,
            "input_contract": w.current_version, "roles": {}, "complete": False}


def _save(w: "fleet.Worker", doc: dict) -> None:
    path(w).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")


# --- roles on identity (stable source roles) ------------------------------

def source_roles(w: "fleet.Worker") -> dict:
    return dict(w.identity.get("source_roles") or {})


def required_roles(w: "fleet.Worker") -> list[str]:
    return sorted(r for r, spec in source_roles(w).items()
                  if spec.get("required"))


def slot_kind(w: "fleet.Worker", role: str) -> str:
    return source_roles(w)[role]["slot"]


def shared_roles(w: "fleet.Worker") -> list[str]:
    return sorted(r for r, spec in source_roles(w).items()
                  if spec["slot"] == "shared")


def sole_roles(w: "fleet.Worker") -> list[str]:
    return sorted(r for r, spec in source_roles(w).items()
                  if spec["slot"] == "sole")


# --- completeness ---------------------------------------------------------

def is_complete(w: "fleet.Worker") -> bool:
    doc = load(w)
    if not doc:
        return False
    return all(r in doc["roles"] for r in required_roles(w))


def bound_roles(w: "fleet.Worker") -> list[str]:
    doc = load(w)
    return sorted((doc or {}).get("roles", {}))


# --- the binding operation ------------------------------------------------

def _role_specs(w: "fleet.Worker") -> dict:
    """role -> SheetSpec, from the version-bound input contract."""
    import adapters.xlsx as xlsx
    return xlsx.specs_from_contract(w.input_contract)


def _materialize(w: "fleet.Worker", role: str, items: list,
                 source_name: str) -> str:
    """Write one collection to the model-declared source path.

    The path is what `versions/v<N>.json` declares under `sources[role].path`
    -- the adapter cannot quietly relocate a source the worker depends on.
    Returns the relative path (as the model declares it) for provenance.
    """
    spec = w.model["sources"][role]
    target = w.base / spec["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"_note": f"converted from {source_name}",
                    spec["collection"]: items}, indent=2,
                   ensure_ascii=False) + "\n", encoding="utf-8")
    return spec["path"]


def bind(w: "fleet.Worker", roles: list[str], file_path: Path) -> dict:
    """Bind one arriving file to one or more roles of the open input set.

    Validates the file against each role's contract spec (the existing
    `convert` refusal path), materializes each role's collection into the
    model-declared source path, records the binding (document/digest/sheet/
    header_row/materialized_as), and reports whether the set is now complete.

    On a shape mismatch: NO binding is recorded for ANY role and `problems`
    is returned -- no partial state mutation for the slot (design §7: "no
    partial state mutation for that slot"). The caller moves the file to
    `exceptions/`; the open set is untouched.

    A version bump since the set was opened invalidates the partial set:
    v0.6 advances model and contract together, so a stale partial set under a
    new version is not a valid set and is replaced. (One open set per worker.)
    """
    import adapters.xlsx as xlsx
    role_specs = _role_specs(w)
    specs = [role_specs[r] for r in roles]
    conversion = xlsx.convert(file_path, specs)
    if not conversion.ok:
        return {"roles": [], "complete": False, "bindings": {},
                "problems": conversion.problems}

    raw = file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()

    doc = load(w)
    if doc is None or doc.get("model") != w.current_version:
        doc = _new(w)

    bindings: dict[str, dict] = {}
    for role in roles:
        spec = role_specs[role]
        items = conversion.collections[spec.collection]
        materialized = _materialize(w, role, items, file_path.name)
        binding = {"document": file_path.name, "digest": digest,
                   "sheet": spec.sheet, "header_row": spec.header_row,
                   "materialized_as": materialized, "bound_at": _now()}
        doc["roles"][role] = binding
        bindings[role] = binding

    complete = all(r in doc["roles"] for r in required_roles(w))
    doc["complete"] = complete
    _save(w, doc)
    return {"roles": list(roles), "complete": complete, "bindings": bindings,
            "problems": []}


def member_files(w: "fleet.Worker") -> list[str]:
    """The raw filenames bound into the open set (for terminalize to drain)."""
    doc = load(w)
    return [b["document"] for b in (doc or {}).get("roles", {}).values()]


# --- self-test ------------------------------------------------------------

def _self_test() -> int:
    import shutil

    import inbox  # imported here to avoid a circular import at module load

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    def build_worker(scratch_name: str, wname: str, model_file: str,
                     source_roles: dict, contract: dict,
                     task: str) -> "fleet.Worker":
        scratch = fleet.LAB / "fleet" / scratch_name
        if scratch.exists():
            shutil.rmtree(scratch)
        root = scratch / "workers"
        root.mkdir(parents=True)
        model = json.loads((fleet.LAB / "fleet" / "workers" / model_file
                            ).read_text(encoding="utf-8"))
        base = f"fleet/{scratch_name}/workers/{wname}/state"
        w = fleet.establish(root, wname, "Input-set test.", task, base, model)
        ident = json.loads((w.directory / "worker.json").read_text(encoding="utf-8"))
        ident.update({"input_adapter": "xlsx",
                       "work_item_identity": "content_digest",
                       "source_roles": source_roles})
        (w.directory / "worker.json").write_text(
            json.dumps(ident, indent=2) + "\n", encoding="utf-8")
        cdir = w.directory / "input_contracts"
        cdir.mkdir()
        (cdir / "v1.json").write_text(
            json.dumps(contract, indent=2) + "\n", encoding="utf-8")
        w = fleet.load(w.directory)
        inbox.ensure(w)
        return w

    def drop(w, src, name, role=None):
        shutil.copy(src, w.directory / "inbox" / name)
        if role is not None:
            (w.directory / "inbox" / f"{name}.role").write_text(
                role, encoding="utf-8")

    try:
        # --- ACME: two sole slots, N-of-M completeness ---------------------
        acme_model = "acme-august-recon/versions/v1.json"
        acme_roles = {
            "statement": {"label": "supplier statement", "slot": "sole",
                          "required": True},
            "transactions": {"label": "ledger transactions", "slot": "sole",
                             "required": True},
        }
        acme_contract = {"roles": {
            "statement": {"sheet": "Statement", "collection": "statement",
                          "header_row": 3},
            "transactions": {"sheet": "Transactions", "collection": "transactions",
                             "header_row": 2}}}
        w = build_worker(".selftest-acme", "acme", acme_model, acme_roles,
                         acme_contract, "reconciliation")

        drop(w, fleet.LAB / "data" / "acme-august" / "supplier.xlsx",
             "supplier.xlsx", role="statement")
        out1 = inbox.poll(w)
        check(len(out1) == 1 and out1[0]["state"] == "staged"
              and out1[0]["roles"] == ["statement"],
              f"binding the statement stages it (1/2): {out1}")
        check(len(fleet.load(w.directory).runs) == 0,
              "CANARY: a partial set fires NO run")
        check(is_complete(w) is False and bound_roles(w) == ["statement"],
              f"the open set is partial with only statement bound: "
              f"{load(w)}")
        # the staged file stays in inbox/ (the set, not the location, is authority)
        check((w.directory / "inbox" / "supplier.xlsx").is_file(),
              "a staged file stays in inbox/ until the set completes")

        drop(w, fleet.LAB / "data" / "acme-august" / "ledger.xlsx",
             "ledger.xlsx", role="transactions")
        out2 = inbox.poll(w)
        runs = fleet.load(w.directory).runs
        check(len(runs) == 1 and runs[-1]["ok"],
              f"binding the transactions completes the set and fires ONE run: "
              f"runs={len(runs)} ok={runs[-1]['ok'] if runs else None}")
        check(load(w) is None,
              "CANARY: the open set is cleared after the run terminalizes")
        check((w.directory / "processed" / "supplier.xlsx").is_file()
              and (w.directory / "processed" / "ledger.xlsx").is_file(),
              "both bound files drained to processed/")
        check(not (w.directory / "inbox" / "supplier.xlsx").is_file()
              and not (w.directory / "inbox" / "ledger.xlsx").is_file(),
              "the inbox drains for both set members")

        # --- ACME: a shape mismatch refuses, no partial mutation ------------
        w = build_worker(".selftest-acme2", "acme", acme_model, acme_roles,
                         acme_contract, "reconciliation")
        # the fazerish workbook (Order lines/Price list) is the wrong shape for
        # the acme `statement` slot (expects Statement, header 3) -> refused.
        drop(w, fleet.LAB / "data" / "xlsx-fazerish" / "may-order-lines.xlsx",
             "wrong.xlsx", role="statement")
        out = inbox.poll(w)
        check(len(out) == 1 and out[0]["state"] == "exception"
              and out[0]["problems"],
              f"a shape mismatch excepts with named problems: {out}")
        check(load(w) is None and len(fleet.load(w.directory).runs) == 0,
              "CANARY: a refused binding records NO binding and fires NO run")
        check((w.directory / "exceptions" / "wrong.xlsx").is_file(),
              "the refused file is queued in exceptions/")

        # --- ACME: a sole file with no slot sidecar is refused, not guessed -
        w = build_worker(".selftest-acme3", "acme", acme_model, acme_roles,
                         acme_contract, "reconciliation")
        drop(w, fleet.LAB / "data" / "acme-august" / "supplier.xlsx",
             "supplier.xlsx")  # NO .role sidecar
        out = inbox.poll(w)
        check(len(out) == 1 and out[0]["state"] == "exception"
              and "bind it to a role" in out[0]["reason"],
              f"a sole-slot file with no explicit slot is refused, not "
              f"inferred from the filename: {out}")

        # --- FAZERISH: one shared workbook completes on first arrival -------
        faz_model = "fazerish-invoicing/versions/v1.json"
        faz_roles = {
            "order_lines": {"label": "order lines", "slot": "shared",
                            "required": True},
            "price_list": {"label": "price list", "slot": "shared",
                           "required": True},
        }
        faz_contract = {"roles": {
            "order_lines": {"sheet": "Order lines", "collection": "order_lines",
                            "header_row": 1},
            "price_list": {"sheet": "Price list", "collection": "price_list",
                           "header_row": 1}}}
        w = build_worker(".selftest-faz", "faz", faz_model, faz_roles,
                         faz_contract, "enrichment")
        drop(w, fleet.LAB / "data" / "xlsx-fazerish" / "may-order-lines.xlsx",
             "may.xlsx")  # shared: no sidecar needed
        out = inbox.poll(w)
        runs = fleet.load(w.directory).runs
        check(len(out) == 1 and out[0]["state"] == "completed"
              and sorted(out[0]["roles"]) == ["order_lines", "price_list"],
              f"one shared workbook completes the 2-slot set in one record: {out}")
        check(len(runs) == 1 and runs[-1]["ok"],
              f"CANARY: a shared worker runs immediately on one workbook: "
              f"runs={len(runs)}")
        check(load(w) is None,
              "the shared set is cleared after the run")
        check((w.directory / "processed" / "may.xlsx").is_file(),
              "the shared workbook drains to processed/")

    finally:
        for s in (".selftest-acme", ".selftest-acme2", ".selftest-acme3",
                  ".selftest-faz"):
            shutil.rmtree(fleet.LAB / "fleet" / s, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (acme: statement stages 1/2 with NO run / "
          "transactions completes 2/2 and fires ONE ok run, both files drain, "
          "set clears / a shape mismatch refuses with NO binding and NO run / "
          "a sole file with no explicit slot is refused not guessed / fazerish: "
          "one shared workbook completes the 2-slot set immediately and runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)