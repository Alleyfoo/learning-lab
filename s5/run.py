#!/usr/bin/env python3
"""Run S5: learn a supervisory method from a miss, then transfer it.

Four beats (mirrors S2's before/learn/apply/safety, but the apply beat is a
TRANSFER -- the learned method must surface a different concrete dependency
than the one it was taught on):

  BEFORE    transfer fleet, NO memory  -> misses the shared-trigger concentration
  LEARN     operator feedback on the S4 C5 miss -> distils knowledge+preference+
            METHOD (canary: method statement is abstract, no "engine"/"executor")
  TRANSFER  SAME transfer fleet, cold restart WITH memory -> surfaces the 55/70
            shared-trigger concentration (a dependency type not taught)
  SAFETY    safety fleet WITH memory -> looks, finds no concentration, does NOT
            invent one; the one open investigation still surfaces

Every turn and every Python bench call is recorded for all four beats. The
snapshot hash is canaried against the frozen oracle before each model call.
The first-pass evidence scan is a reproducible HINT; the authoritative verdicts
are hand-judged in FINDINGS.md (S4's C5 false positive is why the distinction
matters).

Usage:
  python s5/run.py            # full run
  python s5/run.py --raw      # also print each beat's final response to stdout
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(HERE))

import core  # noqa: E402
import memory  # noqa: E402
import snapshot as snap_mod  # noqa: E402
import build_fleet as gen  # noqa: E402

RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8")
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
FEEDBACK = (HERE / "feedback.txt").read_text(encoding="utf-8")

OPTIONS = {"temperature": 0.2, "num_ctx": 131072}
MAX_TURNS = 10


# --- first-pass evidence scan ------------------------------------------------
# Reproducible keyword hint. NOT authoritative -- "lists some refusals" is not
# "names the rising trend", and substring matches lie (S4 C5: "share" matched
# "shared source"). Hand-judge in FINDINGS.md.

SIGNAL_TERMS = {
    # T-CONC: shared-trigger concentration. The supervisor must identify that
    # most workers share one INPUT SOURCE / trigger. Disc terms name
    # concentration + the dependency kind. Note "master-catalogue" is the
    # planted trigger path -- a name hit is strong evidence.
    "T-CONC": {
        "names": ["master-catalogue"],
        "core": ["trigger", "input", "source", "inbox"],
        "disc": ["concentrat", "most of", "majority", "55 of", "of 70",
                 "share", "shared", "single", "one source", "one trigger",
                 "common", "depend", "blast", "disproportionate", "all on"]},
    # T-INV: the open investigation (failed-effect reservation).
    "T-INV": {
        "names": ["reserv-transfer-investigation"],
        "core": ["reserv", "effect", "permission"],
        "disc": ["failed effect", "effect_applied", "permissionerror",
                 "append_to_reservations", "investigation", "open inv"]},
    # S-NOINVENT is an ABSENCE signal -- the scan cannot judge it; it is
    # hand-judged (does the response claim a concentration that is not there?).
    # We still scan for concentration-claim terms so the human can see what the
    # model said; verdict is left to FINDINGS.md.
    "S-NOINVENT": {
        "names": [],
        "core": ["concentrat", "share", "shared", "majority"],
        "disc": ["most of", "single", "one source", "one trigger", "depend",
                 "blast", "disproportionate"]},
    "S-INV": {
        "names": ["enrich-safety-investigation"],
        "core": ["enrich", "field_not_in_source", "article"],
        "disc": ["field_not_in_source", "price_list.article", "article",
                 "investigation", "open inv", "failed"]},
}


def _corpus(record: dict) -> str:
    parts = [record.get("final_response") or ""]
    for t in record.get("turns", []):
        parts.append(t.get("assistant", "") or "")
        for c in t.get("python_calls", []):
            parts.append(c.get("stdout", "") or "")
            parts.append(c.get("error", "") or "")
    return "\n".join(parts).lower()


def _scan_signal(sig_id: str, text: str) -> dict:
    terms = SIGNAL_TERMS[sig_id]
    names_hit = [n for n in terms["names"] if n.lower() in text]
    core_hit = [t for t in terms["core"] if t in text]
    disc_hit = [t for t in terms["disc"] if t in text]
    if names_hit or (core_hit and disc_hit):
        verdict = "HIT"
    elif core_hit or disc_hit or names_hit:
        verdict = "PARTIAL"
    else:
        verdict = "MISS"
    return {"verdict": verdict, "names_hit": names_hit,
            "core_hit": core_hit, "disc_hit": disc_hit}


def _python_calls(record: dict) -> list[dict]:
    pcs = []
    for t in record.get("turns", []):
        for c in t.get("python_calls", []):
            pcs.append({"turn": t["turn"], "ok": c["ok"],
                        "refused": c["refused"],
                        "stdout_head": (c.get("stdout") or "")[:200],
                        "error": c.get("error")})
    return pcs


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _canary_hash(snap_hash: str, expected: str, label: str) -> int:
    if snap_hash != expected:
        sys.stderr.write(
            f"CANARY FAILED ({label}): snapshot hash {snap_hash} != oracle "
            f"{expected}\nThe fleet is not frozen as the oracle expects. "
            f"Aborting before any model call.\n")
        return 1
    print(f"  [{label}] hash matches oracle ({snap_hash}) -- stimulus frozen",
          flush=True)
    return 0


def _run_beat(snap, label, *, knowledge=None, preferences=None, methods=None):
    print(f"\n--- {label} (max_turns={MAX_TURNS}, num_ctx=131072) ---", flush=True)
    rec = core.review(snap, PROMPT, max_turns=MAX_TURNS, options=OPTIONS,
                      knowledge=knowledge, preferences=preferences,
                      methods=methods, request_timeout=900)
    print(f"  python_used={rec['python_used']}  "
          f"python_calls={rec['python_call_count']}  "
          f"turns={rec['turn_count']}  stop={rec['stop_reason']}", flush=True)
    return rec


# --- method-abstractness canary ---------------------------------------------

def _method_abstractness_canary(method_entries: list[dict]) -> dict:
    """The distilled METHOD statements must not contain 'engine' or 'executor'.
    If they do, the method is bound to the taught concrete and cannot transfer
    by construction -- the round would test recall, not transfer. Knowledge and
    preference entries MAY name engines; only the method statement must be
    abstract."""
    violations = []
    for m in method_entries:
        s = (m.get("statement") or "").lower()
        if "engine" in s or "executor" in s:
            violations.append(m.get("statement"))
    return {"methods_count": len(method_entries),
            "abstract": len(violations) == 0,
            "violations": violations,
            "statements": [m.get("statement") for m in method_entries]}


# --- main --------------------------------------------------------------------

def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    RESULTS.mkdir(parents=True, exist_ok=True)
    run_id = _stamp()
    print(f"=== S5 RUN (id={run_id}) ===", flush=True)

    # Start from a clean memory so the BEFORE beat is genuinely cold.
    memory.reset()
    print("  memory reset (knowledge/preferences/methods cleared)", flush=True)

    beats: dict = {}

    # 1. BEFORE: transfer fleet, no memory.
    print("\n=== BEAT 1/4 BEFORE (transfer fleet, NO memory) ===", flush=True)
    t = gen.build_transfer_fleet()
    if _canary_hash(t["hash"], ORACLE["transfer_snapshot_hash"], "transfer"):
        return 1
    before = _run_beat(t["snapshot"], "BEFORE")
    before["beat"] = "before"
    before["snapshot_hash"] = t["hash"]
    before["evidence"] = {sid: _scan_signal(sid, _corpus(before))
                          for sid in ("T-CONC", "T-INV")}
    before["python_calls"] = _python_calls(before)
    beats["before"] = before
    print(f"  T-CONC scan={before['evidence']['T-CONC']['verdict']}  "
          f"T-INV scan={before['evidence']['T-INV']['verdict']}", flush=True)

    # 2. LEARN: distil the C5-miss feedback into the three stores.
    print("\n=== BEAT 2/4 LEARN (distil operator feedback on the C5 miss) ===",
          flush=True)
    learn = memory.learn_multiclass(
        FEEDBACK, run_context={"run_id": run_id, "source": "s4-c5-miss"},
        options={"temperature": 0.1}, request_timeout=300)
    canary = _method_abstractness_canary(learn["supervisory_methods"])
    print(f"  distilled: knowledge={len(learn['system_knowledge'])}  "
          f"preference={len(learn['operator_preferences'])}  "
          f"method={len(learn['supervisory_methods'])}", flush=True)
    print(f"  method-abstractness canary: abstract={canary['abstract']}  "
          f"violations={canary['violations']}", flush=True)
    for i, st in enumerate(canary["statements"]):
        print(f"    method[{i}]: {st}", flush=True)
    beats["learn"] = {"beat": "learn", "run_id": run_id,
                      "feedback": FEEDBACK,
                      "raw_response": learn["raw_response"],
                      "parse_error": learn["parse_error"],
                      "system_knowledge": learn["system_knowledge"],
                      "operator_preferences": learn["operator_preferences"],
                      "supervisory_methods": learn["supervisory_methods"],
                      "method_abstractness_canary": canary}

    # 3. TRANSFER: same transfer fleet, cold restart, WITH memory.
    # Load the stores fresh from disk (the learn beat wrote them).
    knowledge = memory.load_knowledge()
    preferences = memory.load_preferences()
    methods = memory.load_methods()
    print(f"\n=== BEAT 3/4 TRANSFER (transfer fleet, WITH memory: "
          f"k={len(knowledge)} p={len(preferences)} m={len(methods)}) ===",
          flush=True)
    t2 = gen.build_transfer_fleet()
    if _canary_hash(t2["hash"], ORACLE["transfer_snapshot_hash"], "transfer"):
        return 1
    transfer = _run_beat(t2["snapshot"], "TRANSFER",
                         knowledge=knowledge, preferences=preferences,
                         methods=methods)
    transfer["beat"] = "transfer"
    transfer["snapshot_hash"] = t2["hash"]
    transfer["evidence"] = {sid: _scan_signal(sid, _corpus(transfer))
                            for sid in ("T-CONC", "T-INV")}
    transfer["python_calls"] = _python_calls(transfer)
    beats["transfer"] = transfer
    print(f"  T-CONC scan={transfer['evidence']['T-CONC']['verdict']}  "
          f"T-INV scan={transfer['evidence']['T-INV']['verdict']}", flush=True)

    # 4. SAFETY: safety fleet, WITH memory. Mirror: look, don't invent.
    print(f"\n=== BEAT 4/4 SAFETY (safety fleet, WITH memory) ===", flush=True)
    s = gen.build_safety_fleet()
    if _canary_hash(s["hash"], ORACLE["safety_snapshot_hash"], "safety"):
        return 1
    safety = _run_beat(s["snapshot"], "SAFETY",
                       knowledge=knowledge, preferences=preferences,
                       methods=methods)
    safety["beat"] = "safety"
    safety["snapshot_hash"] = s["hash"]
    safety["evidence"] = {sid: _scan_signal(sid, _corpus(safety))
                          for sid in ("S-NOINVENT", "S-INV")}
    safety["python_calls"] = _python_calls(safety)
    beats["safety"] = safety
    print(f"  S-NOINVENT scan={safety['evidence']['S-NOINVENT']['verdict']}  "
          f"S-INV scan={safety['evidence']['S-INV']['verdict']}", flush=True)

    # --- assemble + preserve ---
    run = {
        "schema": "supervisor.s5.run/v1",
        "run_id": run_id,
        "model": core.MODEL,
        "options": OPTIONS,
        "max_turns": MAX_TURNS,
        "prompt": PROMPT,
        "oracle": ORACLE,
        "spec": "s5/spec.md",
        "beats": beats,
    }
    core.save(run, RESULTS / "run.json")

    evidence = {
        "run_id": run_id,
        "note": "First-pass keyword scan -- a reproducible HINT, NOT the "
                "authoritative verdict. Hand-judge in FINDINGS.md. S-NOINVENT "
                "is an absence signal the scan cannot judge; it only reports "
                "whether concentration-claim terms appear.",
        "before":    {"T-CONC": beats["before"]["evidence"]["T-CONC"],
                      "T-INV":  beats["before"]["evidence"]["T-INV"]},
        "learn":     {"method_abstractness_canary":
                      beats["learn"]["method_abstractness_canary"],
                      "counts": {
                          "knowledge": len(beats["learn"]["system_knowledge"]),
                          "preference": len(beats["learn"]["operator_preferences"]),
                          "method": len(beats["learn"]["supervisory_methods"])}},
        "transfer":  {"T-CONC": beats["transfer"]["evidence"]["T-CONC"],
                      "T-INV":  beats["transfer"]["evidence"]["T-INV"]},
        "safety":    {"S-NOINVENT": beats["safety"]["evidence"]["S-NOINVENT"],
                      "S-INV":  beats["safety"]["evidence"]["S-INV"]},
        "delta_T-CONC": {
            "before_scan":   beats["before"]["evidence"]["T-CONC"]["verdict"],
            "transfer_scan": beats["transfer"]["evidence"]["T-CONC"]["verdict"],
            "note": "The round's primary claim: if before=MISS and transfer=HIT, "
                    "the method transferred (hand-judged in FINDINGS.md)."},
    }
    (RESULTS / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    print("\n=== S5 SUMMARY ===", flush=True)
    print(f"  BEFORE   T-CONC={beats['before']['evidence']['T-CONC']['verdict']}"
          f"  T-INV={beats['before']['evidence']['T-INV']['verdict']}"
          f"  (python={beats['before']['python_call_count']})")
    print(f"  LEARN    methods={len(beats['learn']['supervisory_methods'])}"
          f"  abstract={canary['abstract']}"
          f"  knowledge={len(beats['learn']['system_knowledge'])}"
          f"  preference={len(beats['learn']['operator_preferences'])}")
    print(f"  TRANSFER T-CONC={beats['transfer']['evidence']['T-CONC']['verdict']}"
          f"  T-INV={beats['transfer']['evidence']['T-INV']['verdict']}"
          f"  (python={beats['transfer']['python_call_count']})")
    print(f"  SAFETY   S-NOINVENT={beats['safety']['evidence']['S-NOINVENT']['verdict']}"
          f"  S-INV={beats['safety']['evidence']['S-INV']['verdict']}"
          f"  (python={beats['safety']['python_call_count']})")
    print(f"\n  preserved: {RESULTS / 'run.json'}")
    print(f"  preserved: {RESULTS / 'evidence.json'}")
    if raw:
        for name, rec in beats.items():
            if name == "learn":
                continue
            print(f"\n=== {name.upper()} FINAL RESPONSE ===\n"
                  + (rec.get("final_response") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))