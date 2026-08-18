#!/usr/bin/env python3
"""v0.6 acceptance probe -- the September Acme recurring run, no modeller.

This is the gate for v0.6. It proves the recurring-source loop works end to
end on the REAL acme-august-recon model + input contract (copied into a
scratch worker so the real worker's history is not polluted), WITHOUT
invoking the modeller:

  bind supplier_sept.xlsx -> statement -> validate against input_contracts/
  v1.json -> materialize -> set partial (1/2); bind ledger_sept.xlsx ->
  transactions -> validate -> materialize -> complete (2/2) -> ONE atomic
  runs.jsonl line carrying model=v1, input_contract=v1, input_set, the
  input-set fingerprint, and per-slot document/digest/sheet/header_row/
  materialized_as; the raw arrivals are retained by digest so "show me the
  exact source used in this run" resolves worker -> run -> slot -> digest ->
  retained raw bytes; and a crash between record_run and terminalize still
  runs the set EXACTLY ONCE (the fingerprint appears in runs.jsonl once).

The negative probe: a shape-changed October statement (header moved to row 4)
is refused at validation -- exception, no run, no binding -- leaving the
operator free to re-model (a new model version + new input_contracts version +
new founding origin) as a separate explicit action.

Run:  python fleet/accept_v06.py --self-test
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))

import fleet      # noqa: E402
import inbox      # noqa: E402
import input_set  # noqa: E402


def _build_acme(scratch: Path, tag: str) -> "fleet.Worker":
    """A scratch copy of the real acme-august-recon worker: same v1 model and
    v1 input contract, sole slots statement/transactions. Established into a
    throwaway dir so the real worker's runs.jsonl is untouched."""
    if scratch.exists():
        shutil.rmtree(scratch)
    root = scratch / "workers"
    root.mkdir(parents=True)
    model = json.loads((HERE / "workers" / "acme-august-recon" / "versions" /
                        "v1.json").read_text(encoding="utf-8"))
    base = f"fleet/{scratch.name}/workers/{tag}/state"
    w = fleet.establish(root, tag, "v0.6 acceptance probe.", "reconciliation",
                        base, model)
    ident = json.loads((w.directory / "worker.json").read_text(encoding="utf-8"))
    ident.update({"input_adapter": "xlsx", "work_item_identity": "content_digest",
                  "source_roles": {
                      "statement": {"label": "supplier statement", "slot": "sole",
                                    "required": True},
                      "transactions": {"label": "ledger transactions", "slot": "sole",
                                       "required": True}}})
    (w.directory / "worker.json").write_text(json.dumps(ident, indent=2) + "\n",
                                              encoding="utf-8")
    cdir = w.directory / "input_contracts"
    cdir.mkdir()
    contract = json.loads((HERE / "workers" / "acme-august-recon" /
                           "input_contracts" / "v1.json").read_text(encoding="utf-8"))
    (cdir / "v1.json").write_text(json.dumps(contract, indent=2) + "\n",
                                  encoding="utf-8")
    w = fleet.load(w.directory)
    inbox.ensure(w)
    return w


def _drop(w, src: Path, name: str, role: str) -> None:
    shutil.copy(src, w.directory / "inbox" / name)
    (w.directory / "inbox" / f"{name}.role").write_text(role, encoding="utf-8")


def _fp_count(w, fp: str) -> int:
    return sum(1 for r in fleet.load(w.directory).runs
               if (r.get("run_input") or {}).get("fingerprint") == fp)


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    sept = LAB / "data" / "acme-sept"
    oct_dir = LAB / "data" / "acme-october"
    sup_sept = sept / "supplier.xlsx"
    led_sept = sept / "ledger.xlsx"
    sup_oct = oct_dir / "supplier.xlsx"
    for p in (sup_sept, led_sept, sup_oct):
        check(p.is_file(), f"fixture present: {p}")

    # =====================================================================
    # POSITIVE PROBE: the September Acme recurring run, no modeller
    # =====================================================================
    scratch = LAB / "fleet" / ".selftest-accept"
    try:
        w = _build_acme(scratch, "acme-sept")

        # bind the statement -> validate against the contract -> materialize
        _drop(w, sup_sept, "supplier.xlsx", role="statement")
        out1 = inbox.poll(w)
        check(len(out1) == 1 and out1[0]["state"] == "staged"
              and out1[0]["roles"] == ["statement"],
              f"September statement binds + stages (partial 1/2): {out1}")
        check(len(fleet.load(w.directory).runs) == 0,
              "a partial September set fires NO run (wait for complete input)")
        check(input_set.is_complete(w) is False, "the set is partial (1/2)")

        # bind the transactions -> validate -> materialize -> complete -> run
        _drop(w, led_sept, "ledger.xlsx", role="transactions")
        out2 = inbox.poll(w)
        runs = fleet.load(w.directory).runs
        check(len(runs) == 1 and runs[-1]["ok"]
              and all(o["state"] == "completed" for o in out2),
              f"September ledger completes the set and fires ONE ok run: "
              f"runs={len(runs)} out={out2}")
        check(input_set.load(w) is None,
              "the completed September set is cleared after the run")

        # the run record is ONE atomic line carrying the full provenance block
        run = runs[-1]
        ri = run.get("run_input")
        check(ri is not None, "the September run carries a run_input block")
        check(ri["model"] == 1 and ri["input_contract"] == 1,
              f"run_input tags model=v1, input_contract=v1: {ri}")
        check(ri["input_set"] == {"worker": "acme-sept", "id": None},
              f"run_input.input_set is the open set (id None in v0.6): {ri['input_set']}")
        fp = ri["fingerprint"]
        check(fp is not None and len(fp) == 64,
              f"run_input carries the 64-char input-set fingerprint: {fp}")
        check(set(ri["slots"]) == {"statement", "transactions"},
              f"run_input.slots covers both bound roles: {set(ri['slots'])}")
        sup_digest = hashlib.sha256(sup_sept.read_bytes()).hexdigest()
        led_digest = hashlib.sha256(led_sept.read_bytes()).hexdigest()
        check(ri["slots"]["statement"] == {
            "document": "supplier.xlsx", "digest": sup_digest,
            "sheet": "Statement", "header_row": 3,
            "materialized_as": ri["slots"]["statement"]["materialized_as"]},
            f"statement slot provenance is digest-truthful: {ri['slots']['statement']}")
        check(ri["slots"]["transactions"]["document"] == "ledger.xlsx"
              and ri["slots"]["transactions"]["digest"] == led_digest
              and ri["slots"]["transactions"]["sheet"] == "Transactions"
              and ri["slots"]["transactions"]["header_row"] == 2,
              f"transactions slot provenance is digest-truthful: "
              f"{ri['slots']['transactions']}")
        # the materialized sources landed at the declared paths
        for role, slot in ri["slots"].items():
            check((w.base / slot["materialized_as"]).is_file(),
                  f"the {role} slot was materialized to {slot['materialized_as']}")

        # --- raw retention: resolve run -> slot -> digest -> retained bytes --
        for role, slot in ri["slots"].items():
            retained = (w.directory / "processed"
                        / inbox.retained_name(slot["document"], slot["digest"]))
            check(retained.is_file(),
                  f"the {role} raw arrival is retained by digest at {retained.name}")
            check(hashlib.sha256(retained.read_bytes()).hexdigest() == slot["digest"],
                  f"the retained {role} bytes match the recorded digest (truthful)")

        # =================================================================
        # CRASH/RECOVERY (canary 3 on September data): run EXACTLY ONCE
        # =================================================================
        wc = _build_acme(scratch, "acme-sept-crash")
        _drop(wc, sup_sept, "supplier.xlsx", role="statement")
        inbox.poll(wc)  # stage the statement
        _drop(wc, led_sept, "ledger.xlsx", role="transactions")
        try:
            inbox.poll(wc, crash_at="after_effect")
            failures.append("crash canary: the injected crash must interrupt")
        except inbox.CrashInjected:
            pass
        fp_c = input_set.fingerprint(wc)
        check(_fp_count(wc, fp_c) == 1,
              "after the crash the September fingerprint is in runs.jsonl once "
              "(record_run fired before terminalize)")
        check(input_set.load(wc) is not None,
              "after the crash the set is still complete (not terminalized)")
        inbox.recover(wc)
        check(_fp_count(wc, fp_c) == 1,
              "LOAD-BEARING: recovery did NOT append a second September run -- "
              "fingerprint in runs.jsonl EXACTLY ONCE across crash + recovery")
        check(input_set.load(wc) is None,
              "recovery terminalized and cleared the September set")
        check(len(fleet.load(wc.directory).runs) == 1,
              "exactly one run line exists for the September set")

        # =================================================================
        # NEGATIVE PROBE: October shape-changed statement is refused
        # =================================================================
        wo = _build_acme(scratch, "acme-oct")
        _drop(wo, sup_oct, "supplier.xlsx", role="statement")
        out = inbox.poll(wo)
        check(len(out) == 1 and out[0]["state"] == "exception"
              and out[0]["problems"],
              f"the October shape-changed statement is refused at validation: {out}")
        check(len(fleet.load(wo.directory).runs) == 0,
              "CANARY: a refused October binding fires NO run")
        check(input_set.load(wo) is None,
              "a refused October binding records NO binding (no partial mutation)")
        # the operator's recourse is to re-model -- a separate explicit action,
        # not something this probe performs or the inbox guesses.
        check(input_set.bound_roles(wo) == [],
              "no slot is bound for the refused October statement")
    finally:
        shutil.rmtree(LAB / "fleet" / ".selftest-accept", ignore_errors=True)

    if failures:
        sys.stderr.write("v0.6 ACCEPTANCE FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("v0.6 ACCEPTANCE PASSED (September Acme, no modeller: statement stages "
          "1/2 / transactions completes 2/2 and fires ONE ok run whose single "
          "runs.jsonl line carries model=v1, input_contract=v1, input_set, the "
          "fingerprint, and per-slot digest-truthful provenance / raw arrivals "
          "retained by digest so run -> slot -> digest -> retained bytes "
          "resolves / crash after record_run still runs the set EXACTLY ONCE / "
          "October shape-changed statement is refused at validation with no run "
          "and no binding, leaving re-model as a separate explicit action)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)