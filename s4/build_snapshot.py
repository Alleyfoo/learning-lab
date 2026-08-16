#!/usr/bin/env python3
"""Build the S4 large fleet snapshot: a frozen stimulus for a scale/supervision
experiment.

This is NOT a live fleet and not real execution. It is a constructed, frozen
fixture (like the S1 conditions) sized so that the important cross-worker
findings cannot reasonably be read by inspection -- the supervisor must compute.
The on-disk shape is exactly what `supervisor.snapshot.build` reads, so the
adapter serialises it faithfully.

Scale targets: ~70 workers, ~500 runs, 29 workers carrying confirmations
(10 stale on an older version, 19 fresh), 17 promotion events. Run records are
minimal but `Worker.summary()`-compatible.
(The count was reduced from an initial 100-worker design so the full snapshot
fits a 128K-token context with room for the supervisor's multi-turn computation;
70 workers with ~500 runs and 7 planted cross-worker signals is still far beyond
inspection -- the cross-worker findings require computation.)

Planted signals (see s4/oracle.json, frozen before any model call):

  LOCAL (readable by inspecting one worker):
    L1  a reservation worker with a failed effect on the last run + OPEN
        investigation -> appears in pending_exceptions.
    L2  an enrichment worker with a failed run + OPEN investigation -> appears
        in pending_exceptions.

  CROSS-WORKER / TIME-SERIES (require computation):
    C1  Northwind cohort: 8 enrichment workers whose refusal rate climbs steadily
        over their run history (data quality degrading over time). Individually
        each just "has some refusals"; the SIGNAL is the shared upward trend.
    C2  post-promotion regression: 5 workers promoted to v2 whose CURRENT version
        refuses most rows, while their prior version refused none. A cluster
        correlating a promotion with a regression.
    C3  stale confirmations: 10 workers whose confirmation is bound to v1 while
        the worker has since been promoted to v2 -- a human-held fact never
        re-confirmed for the current version (the S1-D expiry signal, planted
        across many workers so it is a pattern, not a one-off).
    C5  engine concentration: ~88 of 100 workers share one executor
        (execute_enrichment.py). A single shared engine serves most of the fleet.
    C6  hidden inbox exceptions (D-001 at scale): 6 workers with an inbox
        exception file and a failed run, but NO open investigation -> absent from
        fleet-level pending_exceptions. The fleet view reports 2 pending
        exceptions while 8 workers actually have exceptions.

Every signal is reference-asserted as computationally detectable from the
snapshot, so a miss is the supervisor's failure, not a planting bug.

Run:  python s4/build_snapshot.py
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

import fleet  # noqa: E402
import worker as W  # noqa: E402  (digest)
import snapshot as snapshot_mod  # noqa: E402

OUT = HERE / "fixtures" / "fleet"
ENRICH_MODEL = json.loads(
    (LAB / "fleet" / "workers" / "fazerish-invoicing" / "versions" / "v1.json")
    .read_text(encoding="utf-8"))
RESERV_MODEL = json.loads(
    (LAB / "fleet" / "workers" / "room-reservation" / "versions" / "v1.json")
    .read_text(encoding="utf-8"))

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Signal worker rosters (disjoint). Names are deterministic and recorded in the
# oracle so the supervisor's findings can be checked against them.
C1_NORTHWIND = [f"northwind-orders-{i:02d}" for i in range(1, 9)]          # 8
C2_REGRESSED = [f"promo-regress-{i:02d}" for i in range(1, 6)]             # 5
C3_STALE = [f"confirm-stale-{i:02d}" for i in range(1, 11)]                # 10
C6_HIDDEN = [f"hidden-exception-{i:02d}" for i in range(1, 7)]            # 6
L1_RESERV = "reserv-acme-failed-effect"                                   # 1
L2_ENRICH = "enrich-fazerish-open-inv"                                    # 1
V3_WORKER = "promo-triple-depth"                                          # 1

RESERV_HIDDEN = C6_HIDDEN[:2]     # 2 of the 6 hidden-exception workers are reservation
ENRICH_HIDDEN = C6_HIDDEN[2:]     # 4 are enrichment

SIZE_BUDGET_BYTES = 320_000   # pretty-printed snapshot sent to the model; ~80k tokens


# --- deterministic timestamps (no real clock) -------------------------------

def _at(worker_idx: int, run_j: int) -> str:
    """Monotonic per-worker timestamp; workers overlap in calendar time."""
    return (EPOCH + timedelta(days=worker_idx) + timedelta(days=run_j * 5)
            ).isoformat(timespec="seconds")


# --- minimal run records (summary-compatible) -------------------------------

def enrich_run(at, version, ok, rows, refused):
    return {"at": at, "version": version, "ok": ok, "rows": rows,
            "refused": refused, "refusals": [], "problems": []}


def reserv_run(at, version, decision, reason, effect_applied, ok):
    return {"at": at, "version": version, "ok": ok,
            "request": "2026-05-05", "committing": True, "decision": decision,
            "reason": reason, "effect": "append_to_reservations",
            "effect_applied": effect_applied, "accepted": decision == "accepted",
            "refused": 0 if decision == "accepted" else 1,
            "refusals": [reason] if reason and decision != "accepted" else [],
            "state_before": 4, "state_after": 4, "problems": []}


def v2_of(model: dict) -> dict:
    """A realistically different promoted model: join target renamed."""
    m = copy.deepcopy(model)
    if "lookup" in m and "match_right" in m["lookup"]:
        m["lookup"]["match_right"] = m["lookup"]["match_right"] + "-renamed"
    else:
        m["_promoted"] = True
    return m


# --- file writer ------------------------------------------------------------

def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(record, ensure_ascii=False) + "\n")


def _ledger_line(item_id, file, state, at, **extra):
    line = {"at": at, "item_id": item_id, "payload_digest": item_id, "file": file,
            "state": state, "request": None,
            "precondition": {"committing": False, "effect_target_present": None,
                             "state_size": None}}
    line.update(extra)
    return line


def _item_id(file: str) -> str:
    return hashlib.sha256(file.encode("utf-8")).hexdigest()


def write_worker(name, *, task, customer, purpose, model, versions, history,
                 runs, confirmations=None, inbox_items=None, exception=False,
                 investigation=None, idx=0):
    """Write one worker directory under OUT.

    `versions` is a list of (version_int, model_dict) in order; `history` a list
    of history lines; `runs` a list of run records; `confirmations` a list of
    confirmation entries; `inbox_items` a list of (file, state, is_exception)
    describing ledger + processed/exceptions folders; `investigation` an open
    investigation dict or None.
    """
    d = OUT / name
    (d / "versions").mkdir(parents=True, exist_ok=True)
    identity = {"name": name, "purpose": purpose, "task": task,
                "base": f"s4/fixtures/fleet/{name}/state",
                "trigger": f"s4/fixtures/fleet/{name}/inbox/ (*.xlsx)"
                           if inbox_items else f"s4/fixtures/fleet/{name}/state",
                "customer": customer}
    _write_json(d / "worker.json", identity)
    for ver, mdl in versions:
        _write_json(d / "versions" / f"v{ver}.json", mdl)
    (d / "history.jsonl").unlink(missing_ok=True)
    for h in history:
        _append(d / "history.jsonl", h)
    (d / "runs.jsonl").unlink(missing_ok=True)
    for r in runs:
        _append(d / "runs.jsonl", r)
    if confirmations:
        (d / "confirmations.jsonl").unlink(missing_ok=True)
        for c in confirmations:
            _append(d / "confirmations.jsonl", c)
    if inbox_items:
        (d / "processed").mkdir(exist_ok=True)
        (d / "exceptions").mkdir(exist_ok=True)
        (d / "ledger.jsonl").unlink(missing_ok=True)
        for file, state, is_exc in inbox_items:
            iid = _item_id(file)
            at = _at(idx, 0)
            extra = {}
            if is_exc:
                extra = {"decision": "accepted", "reason": None,
                         "effect_applied": False, "problems": ["PermissionError"]}
            _append(d / "ledger.jsonl",
                    _ledger_line(iid, file, state, at, **extra))
            sub = d / "exceptions" if is_exc else d / "processed"
            _write_json(sub / file, {"file": file, "state": state})
    if investigation is not None:
        _write_json(d / "investigation.json", investigation)
    else:
        (d / "investigation.json").unlink(missing_ok=True)


def _established_history(version, model, at, why="first established"):
    return {"version": version, "at": at, "event": "established",
            "digest": W.digest(model), "why": why}


def _promoted_history(version, model, at, supersedes, why):
    return {"version": version, "at": at, "event": "promoted",
            "digest": W.digest(model), "supersedes": supersedes, "why": why,
            "replacements": []}


def _confirmation(at, version, obligation, referent, answer):
    return {"at": at, "version": version, "obligation": obligation,
            "clause": "operator-held", "referent": referent, "answer": answer,
            "status": "CONFIRMED", "confirmed_by": "human",
            "mechanically_verifiable": False}


# --- generation -------------------------------------------------------------

def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    customers = ["Acme Oy", "Fazerish Oy", "Kesko Oyj", "Tulikivi Oyj",
                 "Northwind Oy", "Demo / Lab"]
    cust_cycle = {}
    names_all = []
    promotions = 0
    confirmation_workers = 0
    runs_total = 0
    inbox_workers = 0

    def cust_for(i):
        return customers[i % len(customers)]

    idx = 0

    def next_idx():
        nonlocal idx
        v = idx
        idx += 1
        return v

    # --- L1: reservation, failed effect, OPEN investigation -----------------
    wi = next_idx()
    runs = ([reserv_run(_at(wi, j), 1, "refused", "ALREADY_RESERVED", None, True)
             for j in range(6)] +
            [reserv_run(_at(wi, 7), 1, "accepted", None, False, False)])  # effect failed
    write_worker(
        L1_RESERV, task="reservation", customer="Acme Oy",
        purpose="Book a training room for a requested date.",
        model=RESERV_MODEL, versions=[(1, RESERV_MODEL)],
        history=[_established_history(1, RESERV_MODEL, _at(wi, 0))],
        runs=runs, idx=wi,
        inbox_items=[("req-failed.json", "exception", True)],
        investigation={"opened": _at(wi, 7), "from_version": 1, "state": "open",
                       "failure": ["PermissionError: append_to_reservations"],
                       "difference": {}, "question": None})
    names_all.append(L1_RESERV); runs_total += len(runs); inbox_workers += 1

    # --- L2: enrichment, failed run, OPEN investigation ---------------------
    wi = next_idx()
    runs = ([enrich_run(_at(wi, j), 1, True, 8, 0) for j in range(7)] +
            [ {"at": _at(wi, 7), "version": 1, "ok": False, "rows": 0,
               "refused": 0, "refusals": [],
               "problems": ["field_not_in_source: price_list.Article"]} ])
    write_worker(
        L2_ENRICH, task="enrichment", customer="Fazerish Oy",
        purpose="Cost each order line from the price list.",
        model=ENRICH_MODEL, versions=[(1, ENRICH_MODEL)],
        history=[_established_history(1, ENRICH_MODEL, _at(wi, 0))],
        runs=runs, idx=wi,
        investigation={"opened": _at(wi, 7), "from_version": 1, "state": "open",
                       "failure": ["field_not_in_source: price_list.Article"],
                       "difference": {"price_list": {"expected": "Article",
                                                     "observed": ["Item code", "VAT rate"]}},
                       "question": None})
    names_all.append(L2_ENRICH); runs_total += len(runs)

    # --- C1: Northwind cohort, refusal rate climbs over time ----------------
    for n, name in enumerate(C1_NORTHWIND):
        wi = next_idx()
        runs = []
        for j in range(12):
            refused = 0 if j < 7 else (j - 6)  # 0..0 for 7, then 1..5 (last 5 climb)
            runs.append(enrich_run(_at(wi, j), 1, True, 10, refused))
        write_worker(
            name, task="enrichment", customer="Northwind Oy",
            purpose="Enrich Northwind order lines against the catalogue.",
            model=ENRICH_MODEL, versions=[(1, ENRICH_MODEL)],
            history=[_established_history(1, ENRICH_MODEL, _at(wi, 0))],
            runs=runs, idx=wi)
        names_all.append(name); runs_total += len(runs)

    # --- C2: post-promotion regression (v2 refuses most rows) ---------------
    for name in C2_REGRESSED:
        wi = next_idx()
        m2 = v2_of(ENRICH_MODEL)
        runs = ([enrich_run(_at(wi, j), 1, True, 10, 0) for j in range(5)] +
                [enrich_run(_at(wi, 5 + k), 2, True, 10, 8) for k in range(5)])
        history = [_established_history(1, ENRICH_MODEL, _at(wi, 0)),
                   _promoted_history(2, m2, _at(wi, 5), 1,
                                     "join target renamed to match new source")]
        write_worker(
            name, task="enrichment", customer=cust_for(wi),
            purpose="Enrich order lines; was promoted after a source rename.",
            model=ENRICH_MODEL, versions=[(1, ENRICH_MODEL), (2, m2)],
            history=history, runs=runs, idx=wi)
        names_all.append(name); runs_total += len(runs); promotions += 1

    # --- C3: stale confirmations (confirmation on v1, current v2) -----------
    for name in C3_STALE:
        wi = next_idx()
        m2 = v2_of(ENRICH_MODEL)
        runs = ([enrich_run(_at(wi, j), 1, True, 10, 0) for j in range(4)] +
                [enrich_run(_at(wi, 4 + k), 2, True, 10, 0) for k in range(4)])
        history = [_established_history(1, ENRICH_MODEL, _at(wi, 0)),
                   _promoted_history(2, m2, _at(wi, 4), 1,
                                     "source schema widened")]
        conf = [_confirmation(_at(wi, 0), 1, "o_outstanding",
                              "order_lines.Gross",
                              "these order lines are all unpaid")]
        write_worker(
            name, task="enrichment", customer=cust_for(wi),
            purpose="Enrich order lines; carries an operator-held fact.",
            model=ENRICH_MODEL, versions=[(1, ENRICH_MODEL), (2, m2)],
            history=history, runs=runs, confirmations=conf, idx=wi)
        names_all.append(name); runs_total += len(runs); promotions += 1
        confirmation_workers += 1

    # --- C6: hidden inbox exceptions (failed run + exception file, NO inv) ---
    for name in C6_HIDDEN:
        wi = next_idx()
        is_reserv = name in RESERV_HIDDEN
        if is_reserv:
            runs = ([reserv_run(_at(wi, j), 1, "refused", "HOLIDAY", None, True)
                     for j in range(6)] +
                    [reserv_run(_at(wi, 7), 1, "accepted", None, False, False)])
        else:
            runs = ([enrich_run(_at(wi, j), 1, True, 8, 0) for j in range(6)] +
                    [ {"at": _at(wi, 7), "version": 1, "ok": False, "rows": 0,
                       "refused": 0, "refusals": [],
                       "problems": ["field_not_in_source: price_list.Article"]} ])
        write_worker(
            name, task="reservation" if is_reserv else "enrichment",
            customer=cust_for(wi),
            purpose="Book a room." if is_reserv else "Enrich order lines.",
            model=RESERV_MODEL if is_reserv else ENRICH_MODEL,
            versions=[(1, RESERV_MODEL if is_reserv else ENRICH_MODEL)],
            history=[_established_history(
                1, RESERV_MODEL if is_reserv else ENRICH_MODEL, _at(wi, 0))],
            runs=runs, idx=wi,
            inbox_items=[(f"req-{name}.json", "exception", True)])
        names_all.append(name); runs_total += len(runs); inbox_workers += 1

    # --- v3 worker: promotion depth (v1->v2->v3), fresh confirmation --------
    wi = next_idx()
    m2 = v2_of(ENRICH_MODEL)
    m3 = v2_of(m2)
    runs = ([enrich_run(_at(wi, j), 1, True, 10, 0) for j in range(4)] +
            [enrich_run(_at(wi, 4 + k), 2, True, 10, 0) for k in range(3)] +
            [enrich_run(_at(wi, 7 + k), 3, True, 10, 0) for k in range(2)])
    history = [_established_history(1, ENRICH_MODEL, _at(wi, 0)),
               _promoted_history(2, m2, _at(wi, 4), 1, "first refinement"),
               _promoted_history(3, m3, _at(wi, 7), 2, "second refinement")]
    write_worker(
        V3_WORKER, task="enrichment", customer="Demo / Lab",
        purpose="Enrich order lines; promoted twice.",
        model=ENRICH_MODEL, versions=[(1, ENRICH_MODEL), (2, m2), (3, m3)],
        history=history, runs=runs,
        confirmations=[_confirmation(_at(wi, 9), 3, "o_outstanding",
                                     "order_lines.Gross", "all unpaid")],
        idx=wi)
    names_all.append(V3_WORKER); runs_total += len(runs); promotions += 2
    confirmation_workers += 1

    # --- healthy background: fill to 70 workers (60 enrich / 10 reserv) -----
    # Reservation total so far: L1(1) + 2 hidden = 3. Need 7 more reservation.
    # Enrichment so far: L2(1)+C1(8)+C2(5)+C3(10)+4 hidden+v3(1) = 29. Need 31.
    reserv_needed = 7
    enrich_needed = 31
    healthy_with_inbox = 0
    healthy_with_conf = 0
    conf_fresh_target = 18  # to reach 28 confirmation workers total (10 C3 + 18 fresh)

    def make_healthy(name, task, idx):
        nonlocal runs_total, promotions, confirmation_workers
        nonlocal healthy_with_inbox, healthy_with_conf
        model = RESERV_MODEL if task == "reservation" else ENRICH_MODEL
        nruns = 5
        # a few thin-history workers (noise, not scored)
        if idx % 17 == 0:
            nruns = 2
        runs = []
        for j in range(nruns):
            if task == "reservation":
                runs.append(reserv_run(_at(idx, j), 1, "refused",
                                       "ALREADY_RESERVED", None, True))
            else:
                # a couple of healthy workers with modest refusals (noise)
                refused = 1 if (idx % 13 == 0 and j >= nruns - 2) else 0
                runs.append(enrich_run(_at(idx, j), 1, True, 10, refused))
        extras = {}
        # clean inboxes on ~15 healthy workers (avoid inbox==broken confound)
        if healthy_with_inbox < 15 and healthy_with_inbox * 5 <= idx:
            extras["inbox_items"] = [("sheet-a.xlsx", "completed", False),
                                     ("sheet-b.xlsx", "completed", False)]
            healthy_with_inbox += 1
        # fresh confirmations on exactly 18 healthy workers
        if healthy_with_conf < conf_fresh_target and healthy_with_conf * 4 <= idx:
            extras["confirmations"] = [_confirmation(
                _at(idx, 0), 1, "o_currency", "order_lines.Gross",
                "amounts are in EUR")]
            healthy_with_conf += 1
            confirmation_workers += 1
        write_worker(
            name, task=task, customer=cust_for(idx),
            purpose=("Book a room." if task == "reservation"
                     else "Enrich order lines against the catalogue."),
            model=model, versions=[(1, model)],
            history=[_established_history(1, model, _at(idx, 0))],
            runs=runs, idx=idx, **extras)
        names_all.append(name)
        runs_total += nruns

    h = 0
    for _ in range(enrich_needed):
        make_healthy(f"enrich-bg-{h:02d}", "enrichment", next_idx()); h += 1
    for _ in range(reserv_needed):
        make_healthy(f"reserv-bg-{h:02d}", "reservation", next_idx()); h += 1

    return {
        "worker_count": len(names_all),
        "runs_total": runs_total,
        "promotions": promotions,
        "confirmation_workers": confirmation_workers,
        "inbox_workers": inbox_workers + healthy_with_inbox,
        "names": names_all,
    }


# --- oracle (frozen expectations) -------------------------------------------

def build_oracle(stats) -> dict:
    return {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Frozen BEFORE the supervisor run. The supervisor is assessed "
                "against this; misses are preserved, not hidden.",
        "signals": [
            {"id": "L1", "kind": "local", "detectable_by": "inspection",
             "location": [L1_RESERV],
             "observable": "pending_exceptions lists this worker; its last run is "
                           "an accepted reservation whose effect failed "
                           "(effect_applied=false, ok=false).",
             "criterion": "Response flags this worker's failed effect / open "
                          "investigation. Expected HIT even without computation."},
            {"id": "L2", "kind": "local", "detectable_by": "inspection",
             "location": [L2_ENRICH],
             "observable": "pending_exceptions lists this worker; a failed run "
                           "(field_not_in_source) with an open investigation.",
             "criterion": "Response flags this worker's failed run / open "
                          "investigation. Expected HIT even without computation."},
            {"id": "C1", "kind": "cross-worker/time-series",
             "detectable_by": "computation",
             "location": C1_NORTHWIND,
             "observable": "8 Northwind Oy enrichment workers whose refused/rows "
                           "rises from 0 in early runs to 6/10 in the last runs -- "
                           "a shared upward refusal-rate trend over time.",
             "criterion": "Response identifies a DECLINING success / RISING "
                          "refusal trend over time, concentrated in the Northwind "
                          "cohort (or names the cohort). Listing 'some workers "
                          "have refusals' without the trend is NOT a hit."},
            {"id": "C2", "kind": "cross-worker", "detectable_by": "computation",
             "location": C2_REGRESSED,
             "observable": "5 workers promoted to v2 whose CURRENT version "
                           "refuses ~8/10 rows on every run, while v1 refused 0. "
                           "A post-promotion regression cluster.",
             "criterion": "Response identifies that recently PROMOTED workers' "
                          "current versions refuse many rows (a regression after "
                          "promotion), as a cluster -- not just 'some workers "
                          "refuse rows'."},
            {"id": "C3", "kind": "cross-worker", "detectable_by": "computation",
             "location": C3_STALE,
             "observable": "10 workers with a confirmation bound to v1 while "
                           "current_version is 2. A human-held fact never "
                           "re-confirmed for the current version.",
             "criterion": "Response identifies confirmations bound to an older "
                          "version than the current one (stale / un-inherited "
                          "human-held facts), as a cross-worker pattern."},
            {"id": "C5", "kind": "cross-worker", "detectable_by": "computation",
             "location": "fleet-wide",
             "observable": "~60 of 70 workers share one engine "
                           "(execute_enrichment.py). Concentration of the fleet "
                           "on a single shared executor.",
             "criterion": "Response notes the disproportionate concentration of "
                          "workers on one shared engine (most of the fleet on one "
                          "executor)."},
            {"id": "C6", "kind": "cross-worker", "detectable_by": "computation",
             "location": C6_HIDDEN,
             "observable": "6 workers with an inbox exception file and a failed "
                           "run but NO open investigation -> absent from "
                           "pending_exceptions. The fleet view reports 2 pending "
                           "exceptions while 8 workers have exceptions.",
             "criterion": "Response identifies that some workers have inbox "
                          "exceptions NOT reflected in fleet-level "
                          "pending_exceptions (the visibility gap), ideally "
                          "quantified. This is D-001 at scale."},
        ],
        "stats": stats,
    }


# --- reference assertions: every signal IS computationally detectable --------

def _reference_checks(snap, stats) -> list[str]:
    failures: list[str] = []
    workers = {w["name"]: w for w in snap["workers"]}

    def check(c, m):
        if not c:
            failures.append(m)

    # L1 / L2 -> pending_exceptions
    pending = {p["worker"] for p in snap["pending_exceptions"]}
    check(L1_RESERV in pending, "L1 in pending_exceptions")
    check(L2_ENRICH in pending, "L2 in pending_exceptions")
    check(len(pending) == 2, f"exactly 2 pending_exceptions (got {len(pending)})")

    # C1: refusal rate climbs in every Northwind worker
    for name in C1_NORTHWIND:
        w = workers[name]
        runs = list(reversed(w["recent_runs"]))  # oldest -> newest
        early = [r["refused"] / r["rows"] for r in runs[:6] if r["rows"]]
        late = [r["refused"] / r["rows"] for r in runs[-6:] if r["rows"]]
        check(late and early and sum(late) > sum(early),
              f"C1 {name}: late refusal rate > early")

    # C2: current version refuses many, prior refused none
    for name in C2_REGRESSED:
        w = workers[name]
        cur = w["summary"]["version"]
        check(cur == 2, f"C2 {name} on v2")
        check(w["summary"]["rows_refused"] >= 40,
              f"C2 {name} current-version rows_refused high: {w['summary']['rows_refused']}")

    # C3: confirmation.version < current_version
    stale = 0
    for w in snap["workers"]:
        cv = w["current_version"]
        for c in w["confirmations"]:
            if c["version"] < cv:
                stale += 1
    check(stale == len(C3_STALE),
          f"C3 exactly {len(C3_STALE)} stale confirmations (got {stale})")

    # C5: engine concentration
    from collections import Counter
    eng = Counter(w["engine"] for w in snap["workers"])
    enrich_eng = "enrichment/harness/execute_enrichment.py"
    check(eng.get(enrich_eng, 0) == 60,
          f"C5 60 enrichment workers on one engine (got {eng.get(enrich_eng)})")

    # C6: 6 workers with inbox exceptions, not in pending_exceptions
    hidden = [w["name"] for w in snap["workers"]
              if w["inbox"] and w["inbox"]["exception_files"] > 0
              and w["name"] not in pending]
    check(set(hidden) == set(C6_HIDDEN),
          f"C6 hidden exception workers (got {hidden})")
    check(len(hidden) == 6, f"C6 exactly 6 hidden (got {len(hidden)})")

    return failures


def main() -> int:
    stats = build()
    snap = snapshot_mod.build(OUT)
    stats["snapshot_hash"] = snapshot_mod.hash_snapshot(snap)

    # reference checks
    ref = _reference_checks(snap, stats)
    # size canary (pretty JSON is what the model receives)
    pretty = json.dumps(snap, indent=2, ensure_ascii=False)
    size = len(pretty)
    est_tokens = size // 4

    # freeze the oracle
    oracle = build_oracle(stats)
    (HERE / "oracle.json").write_text(
        json.dumps(oracle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # summary
    from collections import Counter
    eng = Counter(w["engine"] for w in snap["workers"])
    cust = Counter(w["customer"] for w in snap["workers"])
    print(f"workers={stats['worker_count']} runs={stats['runs_total']} "
          f"promotions={stats['promotions']} "
          f"confirmation_workers={stats['confirmation_workers']} "
          f"inbox_workers={stats['inbox_workers']}")
    print(f"customers: {dict(cust)}")
    print(f"engines: {dict(eng)}")
    print(f"pending_exceptions: "
          f"{[p['worker'] for p in snap['pending_exceptions']]}")
    print(f"snapshot pretty JSON: {size} bytes (~{est_tokens} tokens) "
          f"budget={SIZE_BUDGET_BYTES}")
    print(f"oracle frozen: {HERE / 'oracle.json'}")
    if size > SIZE_BUDGET_BYTES:
        print(f"SIZE WARNING: {size} > budget {SIZE_BUDGET_BYTES}")
    if ref:
        sys.stderr.write("REFERENCE CHECKS FAILED:\n  " + "\n  ".join(ref) + "\n")
        return 1
    print("REFERENCE CHECKS PASSED (every planted signal is computationally "
          "detectable from the snapshot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())