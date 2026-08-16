#!/usr/bin/env python3
"""Freeze the four S1 conditions as committed fleet fixtures.

Derives `s1/fixtures/{A,B,C,D}/` from the inherited fleet (`fleet/workers/`) by
copying selected workers and, for B, truncating `room-reservation` to the moment
an accepted effect failed to land, before the retry. Every fixture is then
asserted to actually exhibit its intended condition, so the stimuli are
falsifiable and the build is reproducible.

Run:  python s1/build_conditions.py
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
import snapshot as snap  # noqa: E402

SRC = fleet.ROOT            # the inherited fleet -- the authority, read-only here
OUT = HERE / "fixtures"


def _copy_worker(name: str, dest_root: Path) -> None:
    src = SRC / name
    if not src.is_dir():
        raise SystemExit(f"inherited fleet has no worker {name!r}; run fleet/seed.py")
    shutil.copytree(src, dest_root / name)


def _read_lines(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_A() -> None:
    """Boring: one clean, healthy worker, nothing requiring attention."""
    root = OUT / "A"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _copy_worker("fazerish-invoicing", root)


def build_B() -> None:
    """Effect failure: room-reservation frozen at the failed effect, pre-retry."""
    root = OUT / "B"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _copy_worker("room-reservation", root)
    wdir = root / "room-reservation"

    # runs.jsonl: keep the first five -- three refusals, req-004 accepted, req-005
    # failed (ok=false, effect_applied=false). Drop the retry and the later runs.
    runs = _read_lines(wdir / "runs.jsonl")
    _write_lines(wdir / "runs.jsonl", runs[:5])

    # ledger.jsonl: keep through the req-005 "exception" line; drop its retry and
    # everything after.
    ledger = _read_lines(wdir / "ledger.jsonl")
    kept = []
    for line in ledger:
        kept.append(line)
        obj = json.loads(line)
        if obj.get("file") == "req-005.json" and obj.get("state") == "exception":
            break
    _write_lines(wdir / "ledger.jsonl", kept)

    # Move req-005 back into exceptions/ (it was processed after the retry) and
    # remove the later items that have not happened yet at this freeze point.
    processed = wdir / "processed"
    exceptions = wdir / "exceptions"
    exceptions.mkdir(exist_ok=True)
    for late in ("req-005.json", "req-006.json", "req-007.json"):
        p = processed / late
        if p.exists():
            if late == "req-005.json":
                shutil.copy2(p, exceptions / late)
            p.unlink()
    # req-004-resend was skipped_duplicate before req-005; it stays in processed.

    # State at the failure: the effect did not land, so reservations stay at 4
    # (original 3 + req-004). Truncate the appended retry/later dates back off.
    rpath = wdir / "state" / "fixtures" / "reservations.json"
    doc = json.loads(rpath.read_text(encoding="utf-8"))
    doc["reservations"] = doc["reservations"][:4]
    rpath.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def build_C() -> None:
    """Noisy but healthy: declared policy refusals, no exception, no failed effect."""
    root = OUT / "C"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _copy_worker("orders-enrichment", root)


def build_D() -> None:
    """Nothing broken, something interesting: two workers each carrying a
    version-bound human confirmation the machinery cannot re-prove."""
    root = OUT / "D"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _copy_worker("supplier-outstanding", root)
    _copy_worker("training-room", root)


# --- assertions over exactly what the model sees (the snapshot) -------------

def _assert(cond: bool, msg: str, failures: list[str]) -> None:
    if not cond:
        failures.append(msg)


def assert_conditions(failures: list[str]) -> None:
    def s(name: str) -> dict:
        return snap.build(OUT / name)

    # A: nothing requiring attention
    a = s("A")
    _assert(len(a["workers"]) == 1, f"A has one worker: {[w['name'] for w in a['workers']]}", failures)
    wa = a["workers"][0]
    _assert(all(r["ok"] for r in wa["recent_runs"]), "A: every run is healthy", failures)
    _assert(not any(r.get("refused") or r.get("refusals") for r in wa["recent_runs"]),
            "A: no refused rows", failures)
    _assert(not wa["confirmations"], "A: no confirmations", failures)
    _assert(wa["investigation"] is None and not a["pending_exceptions"],
            "A: no investigation, no pending exception", failures)

    # B: an accepted effect that failed to land, as the latest run, queued
    b = s("B")
    wb = b["workers"][0]
    last = wb["recent_runs"][0]  # recent_runs is newest-first
    _assert(last["ok"] is False and last.get("effect_applied") is False,
            f"B: latest run is a failed effect (ok={last['ok']}, "
            f"effect_applied={last.get('effect_applied')})", failures)
    _assert(last.get("decision") == "accepted",
            "B: the failed run was an ACCEPTED decision (the point: something "
            "downstream is entitled to believe it)", failures)
    _assert(wb["inbox"] and wb["inbox"]["exception_files"] == 1,
            f"B: one item queued in the exception inbox: {wb['inbox']}", failures)
    # recent_runs is newest-first, so `last` being the failed run is itself the
    # proof the fleet is frozen pre-retry: a successful retry would be newer.

    # C: healthy refusals, no exception, no failed effect
    c = s("C")
    wc = c["workers"][0]
    _assert(all(r["ok"] for r in wc["recent_runs"]), "C: every run is healthy", failures)
    _assert(sum(r.get("refused", 0) for r in wc["recent_runs"]) > 0,
            "C: there are refused rows (the noisy-but-healthy signal)", failures)
    _assert(not any(r.get("effect_applied") is False for r in wc["recent_runs"]),
            "C: no failed effect", failures)

    # D: two workers with confirmations, nothing operationally broken
    d = s("D")
    _assert(len(d["workers"]) == 2, f"D has two workers: {[w['name'] for w in d['workers']]}", failures)
    _assert(all(w["confirmations"] for w in d["workers"]),
            "D: each worker carries a human confirmation", failures)
    _assert(not d["pending_exceptions"]
            and not any(w["investigation"] for w in d["workers"]),
            "D: no open investigation / pending exception", failures)
    _assert(not any(r.get("ok") is False for w in d["workers"] for r in w["recent_runs"]),
            "D: no failed runs", failures)


def main(argv: list[str]) -> int:
    build_A(); build_B(); build_C(); build_D()
    failures: list[str] = []
    assert_conditions(failures)
    for name in ("A", "B", "C", "D"):
        s = snap.build(OUT / name)
        print(f"{name}: workers={[w['name'] for w in s['workers']]} "
              f"hash={snap.hash_snapshot(s)}")
    if failures:
        sys.stderr.write("CONDITION ASSERTIONS FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("ALL FOUR CONDITIONS FROZEN AND ASSERTED (A boring / B failed effect as "
          "latest run + 1 queued exception / C healthy refusals no failure / "
          "D two confirmations nothing broken)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))