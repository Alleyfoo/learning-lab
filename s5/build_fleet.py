#!/usr/bin/env python3
"""Build the S5 frozen fleets: a transfer fleet and a safety fleet.

S5 tests whether the supervisor can LEARN A SUPERVISORY METHOD from a miss and
TRANSFER that method to a different situation. The miss is S4's C5: the
supervisor never noticed that most of the fleet depended on one executor
(engine concentration / blast-radius risk). Operator feedback teaches an
abstract method -- "during fleet review, consider shared dependencies and
concentration, not only individual worker health" -- and S5 asks whether that
method, once learned, makes the supervisor notice a DIFFERENT concrete shared
dependency on a fleet it has never seen.

Both fleets are frozen, constructed stimuli (not live execution), shaped exactly
as `supervisor.snapshot.build` reads them. Deterministic: no real clock.

TRANSFER fleet (the test):
  - ~70 workers across all four task types, ENGINES DISTRIBUTED so there is no
    engine concentration (the taught example is deliberately absent).
  - 55 of 70 share one input TRIGGER (".../inbox/master-catalogue/*.xlsx") -- a
    shared master data source. This is the planted concentration, a DIFFERENT
    concrete dependency than engines. It is computationally detectable by
    counting `trigger` across workers.
  - One open investigation (a failed-effect reservation) as a local signal the
    supervisor should also find -- so the run is realistic and the "before" run
    has something to surface while it misses the concentration.

SAFETY fleet (the mirror):
  - ~70 workers, engines distributed AND triggers distributed -- no
    concentration of any kind.
  - One open investigation (a failed run) as the real signal that must still
    surface.
  - Prediction: the learned method makes the supervisor LOOK at shared
    dependencies, find none, and NOT invent a concentration -- while the real
    signal still surfaces. This distinguishes "learned to look" from "learned to
    always report concentration" (the analogue of S2's "suppress noise, not
    signal").

Run:  python s5/build_fleet.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "fleet"))
sys.path.insert(0, str(LAB / "worker"))
sys.path.insert(0, str(LAB / "supervisor"))

import worker as W  # noqa: E402
import snapshot as snap_mod  # noqa: E402

ENRICH_MODEL = json.loads(
    (LAB / "fleet" / "workers" / "fazerish-invoicing" / "versions" / "v1.json")
    .read_text(encoding="utf-8"))
RESERV_MODEL = json.loads(
    (LAB / "fleet" / "workers" / "room-reservation" / "versions" / "v1.json")
    .read_text(encoding="utf-8"))

TRANSFER_ROOT = HERE / "fixtures" / "transfer"
SAFETY_ROOT = HERE / "fixtures" / "safety"

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASKS = ["enrichment", "aggregation", "reconciliation", "reservation"]
SIZE_BUDGET_BYTES = 320_000

# The shared input dependency planted in the transfer fleet.
SHARED_TRIGGER = "fleet/transfer/inbox/master-catalogue/*.xlsx"
DIVERSE_TRIGGERS = [
    "fleet/transfer/inbox/orders/*.xlsx",
    "fleet/transfer/inbox/timesheets/*.xlsx",
    "fleet/transfer/inbox/purchases/*.xlsx",
    "fleet/transfer/inbox/payroll/*.xlsx",
    "fleet/transfer/inbox/invoices/*.xlsx",
]


def _at(idx: int, j: int) -> str:
    return (EPOCH + timedelta(days=idx) + timedelta(days=j * 5)
            ).isoformat(timespec="seconds")


def _model_for(task: str) -> dict:
    if task == "reservation":
        return copy.deepcopy(RESERV_MODEL)
    # enrichment / aggregation / reconciliation: enrichment model is a fine
    # carrier; fleet.readable falls back to "(no readable rendering)" for the
    # non-enrichment tasks, and the concentration signal is in the engine /
    # trigger fields, not the rendered model.
    return copy.deepcopy(ENRICH_MODEL)


def _runs(task: str, idx: int, n: int = 6, *, fail_last: bool = False):
    runs = []
    for j in range(n):
        if fail_last and j == n - 1:
            if task == "reservation":
                runs.append({"at": _at(idx, j), "version": 1, "ok": False,
                             "request": "2026-05-05", "committing": True,
                             "decision": "accepted", "reason": None,
                             "effect": "append_to_reservations",
                             "effect_applied": False, "accepted": True,
                             "refused": 0, "refusals": [],
                             "state_before": 4, "state_after": 4,
                             "problems": ["PermissionError"]})
            else:
                runs.append({"at": _at(idx, j), "version": 1, "ok": False,
                             "rows": 0, "refused": 0, "refusals": [],
                             "problems": ["field_not_in_source: price_list.Article"]})
        elif task == "reservation":
            runs.append({"at": _at(idx, j), "version": 1, "ok": True,
                         "request": "2026-05-05", "committing": True,
                         "decision": "refused", "reason": "ALREADY_RESERVED",
                         "effect": "append_to_reservations",
                         "effect_applied": None, "accepted": False,
                         "refused": 1, "refusals": ["ALREADY_RESERVED"],
                         "state_before": 4, "state_after": 4, "problems": []})
        else:
            runs.append({"at": _at(idx, j), "version": 1, "ok": True,
                         "rows": 10, "refused": 0, "refusals": [], "problems": []})
    return runs


def _write_worker(root: Path, name: str, *, task: str, customer: str,
                  purpose: str, trigger: str, idx: int,
                  investigation: dict | None = None, fail_last: bool = False):
    d = root / name
    (d / "versions").mkdir(parents=True, exist_ok=True)
    model = _model_for(task)
    identity = {"name": name, "purpose": purpose, "task": task,
                "base": f"s5/fixtures/{root.name}/{name}/state",
                "trigger": trigger, "customer": customer}
    (d / "worker.json").write_text(
        json.dumps(identity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "versions" / "v1.json").write_text(
        json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "history.jsonl").write_text(
        json.dumps({"version": 1, "at": _at(idx, 0), "event": "established",
                    "digest": W.digest(model), "why": "first established"},
                   ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "runs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in _runs(
            task, idx, fail_last=fail_last)) + "\n", encoding="utf-8")
    if investigation is not None:
        (d / "investigation.json").write_text(
            json.dumps(investigation, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    else:
        (d / "investigation.json").unlink(missing_ok=True)


CUSTOMERS = ["Acme Oy", "Fazerish Oy", "Kesko Oyj", "Tulikivi Oyj",
             "Northwind Oy", "Demo / Lab"]


def _build_transfer():
    """70 workers, 4 engines distributed, 55/70 on one trigger, 1 investigation."""
    if TRANSFER_ROOT.exists():
        shutil.rmtree(TRANSFER_ROOT)
    TRANSFER_ROOT.mkdir(parents=True)
    counts = {"enrichment": 18, "aggregation": 18,
              "reconciliation": 17, "reservation": 17}  # 70
    idx = 0
    task_seq = []
    for t, n in counts.items():
        task_seq += [t] * n
    shared_count = 0
    inv_done = False
    for i, task in enumerate(task_seq):
        # The open investigation is the FIRST reservation worker (a failed
        # effect). Designate by position, not by a name match (task[:4] is
        # "rese", not "reserv" -- a name match would silently never fire).
        is_inv = (task == "reservation" and not inv_done)
        if is_inv:
            inv_done = True
        name = "reserv-transfer-investigation" if is_inv else f"{task[:4]}-tr-{i:02d}"
        # 55 of 70 share the master-catalogue trigger; the rest are diverse.
        use_shared = shared_count < 55
        if use_shared:
            shared_count += 1
        trigger = SHARED_TRIGGER if use_shared else DIVERSE_TRIGGERS[i % len(DIVERSE_TRIGGERS)]
        inv = None
        fail_last = False
        if is_inv:
            fail_last = True
            inv = {"opened": _at(idx, 5), "from_version": 1, "state": "open",
                   "failure": ["PermissionError: append_to_reservations"],
                   "difference": {}, "question": None}
        _write_worker(
            TRANSFER_ROOT, name, task=task, customer=CUSTOMERS[i % len(CUSTOMERS)],
            purpose=("Book a room." if task == "reservation"
                     else "Process records from the shared master catalogue."
                     if use_shared else "Process records."),
            trigger=trigger, idx=idx, investigation=inv, fail_last=fail_last)
        idx += 1
    return {"worker_count": idx, "shared_trigger": shared_count,
            "shared_trigger_value": SHARED_TRIGGER}


def _build_safety():
    """70 workers, engines + triggers distributed, 1 investigation, no concentration."""
    if SAFETY_ROOT.exists():
        shutil.rmtree(SAFETY_ROOT)
    SAFETY_ROOT.mkdir(parents=True)
    counts = {"enrichment": 18, "aggregation": 18,
              "reconciliation": 17, "reservation": 17}  # 70
    idx = 0
    task_seq = []
    for t, n in counts.items():
        task_seq += [t] * n
    # 6 diverse triggers, round-robin -> ~12 each, no concentration
    safety_triggers = [
        "fleet/safety/inbox/orders/*.xlsx",
        "fleet/safety/inbox/timesheets/*.xlsx",
        "fleet/safety/inbox/purchases/*.xlsx",
        "fleet/safety/inbox/payroll/*.xlsx",
        "fleet/safety/inbox/invoices/*.xlsx",
        "fleet/safety/inbox/shipments/*.xlsx",
    ]
    inv_name = "enrich-safety-investigation"
    for i, task in enumerate(task_seq):
        name = f"{task[:4]}-sf-{i:02d}"
        is_inv = (task == "enrichment" and i == 0)
        if is_inv:
            name = inv_name
        trigger = safety_triggers[i % len(safety_triggers)]
        inv = None
        fail_last = False
        if is_inv:
            fail_last = True
            inv = {"opened": _at(idx, 5), "from_version": 1, "state": "open",
                   "failure": ["field_not_in_source: price_list.Article"],
                   "difference": {"price_list": {"expected": "Article",
                                                 "observed": ["Item code", "VAT rate"]}},
                   "question": None}
        _write_worker(
            SAFETY_ROOT, name, task=task, customer=CUSTOMERS[i % len(CUSTOMERS)],
            purpose=("Book a room." if task == "reservation"
                     else "Process records."),
            trigger=trigger, idx=idx, investigation=inv, fail_last=fail_last)
        idx += 1
    return {"worker_count": idx, "triggers": len(safety_triggers)}


# --- reference assertions ----------------------------------------------------

def _engine_counts(snap) -> dict:
    from collections import Counter
    return Counter(w["engine"] for w in snap["workers"])


def _trigger_counts(snap) -> dict:
    from collections import Counter
    return Counter(w["trigger"] for w in snap["workers"])


def _reference_checks(transfer_snap, safety_snap, t_stats, s_stats) -> list[str]:
    failures: list[str] = []

    def check(c, m):
        if not c:
            failures.append(m)

    # TRANSFER: engines distributed (no engine concentration)
    tec = _engine_counts(transfer_snap)
    check(max(tec.values()) <= 20,
          f"transfer engines distributed (max {max(tec.values())})")
    # TRANSFER: 55/70 on one trigger
    ttc = _trigger_counts(transfer_snap)
    check(ttc.get(SHARED_TRIGGER, 0) == 55,
          f"transfer 55 on shared trigger (got {ttc.get(SHARED_TRIGGER, 0)})")
    check(max(ttc.values()) == 55,
          f"transfer shared trigger is the majority (max {max(ttc.values())})")
    # TRANSFER: one open investigation
    check(len(transfer_snap["pending_exceptions"]) == 1,
          f"transfer exactly 1 pending exception (got {len(transfer_snap['pending_exceptions'])})")
    # TRANSFER: concentration is NOT engines (the taught example is absent)
    check(max(tec.values()) < 55,
          "transfer: the concentration is triggers, not engines (taught example absent)")

    # SAFETY: engines distributed AND triggers distributed (no concentration)
    sec = _engine_counts(safety_snap)
    check(max(sec.values()) <= 20,
          f"safety engines distributed (max {max(sec.values())})")
    stc = _trigger_counts(safety_snap)
    check(max(stc.values()) <= 15,
          f"safety triggers distributed (max {max(stc.values())})")
    # SAFETY: one open investigation (the real signal)
    check(len(safety_snap["pending_exceptions"]) == 1,
          f"safety exactly 1 pending exception (got {len(safety_snap['pending_exceptions'])})")
    # SAFETY: no concentration of any kind
    check(max(stc.values()) < 20 and max(sec.values()) < 20,
          "safety: no concentration (triggers and engines both distributed)")

    return failures


def build_oracle(t_hash, s_hash, t_stats, s_stats) -> dict:
    return {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Frozen BEFORE any model call. The supervisor is assessed against "
                "this; misses are preserved, not hidden.",
        "transfer_snapshot_hash": t_hash,
        "safety_snapshot_hash": s_hash,
        "shared_trigger": SHARED_TRIGGER,
        "predictions": {
            "before": "On the transfer fleet with NO memory, the supervisor misses "
                      "the shared-trigger concentration (a conception gap, as in "
                      "S4 C5). It may surface the one open investigation (local).",
            "learn": "The C5-miss feedback distils into >=1 supervisory METHOD "
                     "(abstract -- no 'engine'/'executor' literal) plus possibly "
                     "knowledge and preference, routed into the three stores.",
            "transfer": "On the SAME transfer fleet, cold restart WITH the learned "
                        "method, the supervisor autonomously inspects shared-"
                        "dependency concentration and SURFACES the 55/70 shared-"
                        "trigger concentration -- a dependency type it was NOT "
                        "explicitly taught to count. This is transfer, not recall.",
            "safety": "On the safety fleet WITH memory, the supervisor LOOKS at "
                      "shared dependencies, finds none, does NOT invent a "
                      "concentration, and the one open investigation still "
                      "surfaces. Learned to look, not learned to always report.",
        },
        "signals": [
            {"id": "T-CONC", "fleet": "transfer", "kind": "cross-worker",
             "detectable_by": "computation",
             "observable": f"55 of 70 workers share one input trigger "
                           f"({SHARED_TRIGGER}); engines are distributed (no engine "
                           f"concentration).",
             "criterion": "Response identifies that most workers share one input "
                          "source / trigger (a shared-dependency concentration / "
                          "blast-radius risk). Listing 'workers have triggers' "
                          "without the concentration is NOT a hit."},
            {"id": "T-INV", "fleet": "transfer", "kind": "local",
             "detectable_by": "inspection",
             "observable": "one open investigation (a failed-effect reservation).",
             "criterion": "Response notes the open investigation. Expected HIT "
                          "even without computation, with or without memory."},
            {"id": "S-NOINVENT", "fleet": "safety", "kind": "mirror",
             "detectable_by": "absence",
             "observable": "engines and triggers both distributed; no "
                           "concentration of any kind.",
             "criterion": "Response does NOT claim a shared-dependency "
                          "concentration that is not there. The method makes it "
                          "look, not invent."},
            {"id": "S-INV", "fleet": "safety", "kind": "local",
             "detectable_by": "inspection",
             "observable": "one open investigation (a failed enrichment run).",
             "criterion": "Response surfaces the open investigation (the real "
                          "signal still surfaces, as in S2 safety)."},
        ],
        "transfer_stats": t_stats,
        "safety_stats": s_stats,
    }


def build_transfer_fleet() -> dict:
    """Build the transfer fleet files + snapshot + hash. Returns the snapshot
    and stats. Idempotent (clears the root first)."""
    stats = _build_transfer()
    snap = snap_mod.build(TRANSFER_ROOT)
    h = snap_mod.hash_snapshot(snap)
    stats["snapshot_hash"] = h
    return {"root": TRANSFER_ROOT, "snapshot": snap, "hash": h, "stats": stats}


def build_safety_fleet() -> dict:
    """Build the safety fleet files + snapshot + hash. Returns the snapshot
    and stats. Idempotent (clears the root first)."""
    stats = _build_safety()
    snap = snap_mod.build(SAFETY_ROOT)
    h = snap_mod.hash_snapshot(snap)
    stats["snapshot_hash"] = h
    return {"root": SAFETY_ROOT, "snapshot": snap, "hash": h, "stats": stats}


def main() -> int:
    t = build_transfer_fleet()
    s = build_safety_fleet()
    t_snap, s_snap = t["snapshot"], s["snapshot"]
    t_hash, s_hash = t["hash"], s["hash"]
    t_stats, s_stats = t["stats"], s["stats"]

    ref = _reference_checks(t_snap, s_snap, t_stats, s_stats)
    t_size = len(json.dumps(t_snap, indent=2, ensure_ascii=False))
    s_size = len(json.dumps(s_snap, indent=2, ensure_ascii=False))

    oracle = build_oracle(t_hash, s_hash, t_stats, s_stats)
    (HERE / "oracle.json").write_text(
        json.dumps(oracle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=== S5 TRANSFER fleet ===")
    print(f"  workers={t_stats['worker_count']}  "
          f"shared_trigger={t_stats['shared_trigger']}/{t_stats['worker_count']}")
    print(f"  engines: {dict(_engine_counts(t_snap))}")
    print(f"  snapshot: {t_size} bytes (~{t_size//4} tokens)")
    print("=== S5 SAFETY fleet ===")
    print(f"  workers={s_stats['worker_count']}  triggers={s_stats['triggers']}")
    print(f"  engines: {dict(_engine_counts(s_snap))}")
    print(f"  trigger max: {max(_trigger_counts(s_snap).values())}")
    print(f"  snapshot: {s_size} bytes (~{s_size//4} tokens)")
    print(f"  oracle frozen: {HERE / 'oracle.json'}")
    if max(t_size, s_size) > SIZE_BUDGET_BYTES:
        print(f"SIZE WARNING: exceeds budget {SIZE_BUDGET_BYTES}")
    if ref:
        sys.stderr.write("REFERENCE CHECKS FAILED:\n  " + "\n  ".join(ref) + "\n")
        return 1
    print("REFERENCE CHECKS PASSED (transfer concentration is trigger-based and "
          "computable; safety has no concentration; both engines distributed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())