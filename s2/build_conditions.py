#!/usr/bin/env python3
"""Build the S2 transfer fixture: a genuinely DIFFERENT healthy enrichment worker.

`acme-order-cost` is established and run for real through the inherited machinery
(XLSX adapter + inbox), not a rename of fazerish. Different name, customer and
purpose; same clean shape that exposed the S1-A misreads: non-committing, an inbox
ledger, thin history (one run), and a model that declares `refuse_row` conditions
the single clean run never exercised.

S2's before/safety reviews reuse the frozen S1 fixtures directly:
  before  -> s1/fixtures/A   (fazerish-invoicing)
  safety  -> s1/fixtures/B   (room-reservation effect failure)
This script only builds the transfer fixture, so S1 stays frozen.

Run:  python s2/build_conditions.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "fleet"))
sys.path.insert(0, str(LAB / "supervisor"))

import fleet  # noqa: E402
import inbox  # noqa: E402
import snapshot as snap  # noqa: E402

OUT = HERE / "fixtures" / "transfer"
FAZERISH_MODEL = LAB / "fleet" / "workers" / "fazerish-invoicing" / "versions" / "v1.json"
CLEAN_WORKBOOK = LAB / "data" / "xlsx-fazerish" / "may-order-lines.xlsx"

# base is stored relative to the lab root and resolved by fleet.Worker.base.
BASE = "s2/fixtures/transfer/acme-order-cost/state"


def build_transfer() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    model = json.loads(FAZERISH_MODEL.read_text(encoding="utf-8"))

    w = fleet.establish(
        OUT, "acme-order-cost",
        "Cost each order line from the order workbook: quantity times the "
        "article's unit price from the price list.", "enrichment", BASE, model,
        trigger="s2/fixtures/transfer/acme-order-cost/inbox/ (*.xlsx)")

    # Augment identity with the XLSX adapter fields, the way the live workers
    # carry them. establish() writes only the core identity.
    ident = json.loads((w.directory / "worker.json").read_text(encoding="utf-8"))
    ident.update({
        "customer": "Acme Oy",
        "input_adapter": "xlsx",
        "work_item_identity": "content_digest",
        "adapter_sheets": [
            {"sheet": "Order lines", "collection": "order_lines", "header_row": 1},
            {"sheet": "Price list", "collection": "price_list", "header_row": 1},
        ],
    })
    (w.directory / "worker.json").write_text(
        json.dumps(ident, indent=2) + "\n", encoding="utf-8")
    w = fleet.load(w.directory)

    # Drive one clean workbook through the inbox. This is a REAL execution: the
    # adapter converts it, the executor runs the model, a healthy run + ledger
    # line are produced -- nothing invented.
    inbox.ensure(w)
    shutil.copy2(CLEAN_WORKBOOK, w.directory / "inbox" / "may-order-lines.xlsx")
    inbox.poll(w)
    w = fleet.load(w.directory)


def assert_transfer(failures: list[str]) -> None:
    s = snap.build(OUT)
    _assert(len(s["workers"]) == 1, f"transfer has one worker: {[w['name'] for w in s['workers']]}", failures)
    w = s["workers"][0]
    _assert(w["name"] == "acme-order-cost"
            and w["customer"] == "Acme Oy"
            and w["name"] != "fazerish-invoicing",
            "transfer worker is a DIFFERENT identity from fazerish", failures)
    _assert(w["task"] == "enrichment" and w["committing"] is False,
            "transfer is a non-committing enrichment worker (the dry-run misread bait)", failures)
    _assert(all(r["ok"] for r in w["recent_runs"]),
            "transfer is healthy", failures)
    _assert(sum(r.get("refused", 0) for r in w["recent_runs"]) == 0,
            "transfer had zero refused rows (the unexercised-refusal bait)", failures)
    _assert(len(w["recent_runs"]) == 1,
            "transfer has thin history (one run) -- the thin-history misread bait", failures)
    _assert(w["inbox"] is not None and w["inbox"]["ledger_lines"] >= 2,
            f"transfer has an inbox ledger (the ledger-vs-rows misread bait): {w['inbox']}", failures)
    # different snapshot from A (transfer, not recall)
    a = snap.build(LAB / "s1" / "fixtures" / "A")
    _assert(snap.hash_snapshot(s) != snap.hash_snapshot(a),
            "CANARY: transfer snapshot differs from S1-A (different identity)", failures)


def _assert(cond: bool, msg: str, failures: list[str]) -> None:
    if not cond:
        failures.append(msg)


def main(argv: list[str]) -> int:
    build_transfer()
    failures: list[str] = []
    assert_transfer(failures)
    s = snap.build(OUT)
    w = s["workers"][0]
    print(f"transfer: {w['name']} ({w['customer']}) task={w['task']} "
          f"runs={w['runs_total']} refused={sum(r.get('refused',0) for r in w['recent_runs'])} "
          f"ledger_lines={w['inbox']['ledger_lines']} hash={snap.hash_snapshot(s)}")
    if failures:
        sys.stderr.write("TRANSFER ASSERTIONS FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("TRANSFER FIXTURE BUILT AND ASSERTED (different identity from fazerish / "
          "non-committing enrichment / one healthy run / zero refusals / inbox "
          "ledger present / snapshot hash differs from S1-A)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))