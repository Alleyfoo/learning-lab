#!/usr/bin/env python3
"""Run S8: composition -- METHOD (attention policy) x MEASUREMENT (cheap fact).

S7 froze the loop end-to-end and left one honest negative: on the distributed
mirror, a COLD supervisor with the measurement re-derived the distribution by
hand rather than read it, because nothing told it the measurement was the answer
to the question it should be asking. S8 tests the hypothesis that the learned
METHOD supplies that missing piece: it is the attention policy that says "ask the
concentration question", and once the measurement answers it the supervisor moves
on instead of re-deriving.

```text
the LLM        learns what questions are worth asking        (METHOD)
the platform   learns to answer repeated factual questions cheaply (MEASUREMENT)
the LLM        remains responsible for what the answers mean  (INTERPRETATION)
```

S8 is a COMPOSITION experiment, not another learning class. It reuses frozen S7
fleets A and D and the frozen S5 method, and compares three conditions under the
frozen S6 harness:

  METHOD-only            full S5 memory, NO measurement          (= S7 Phase A)
  MEASUREMENT-only       COLD, measurement attached WITH contract (= S7 Phase D)
  METHOD+MEASUREMENT     full S5 memory AND measurement + contract (NEW)

The new instrument: each preserved Python call is classified by WHAT it is
calculating (concentration_rederivation / measurement_read / complementary /
probe), not just counted. The call MIX is the headline. The classifier is a
non-authoritative hint; FINDINGS.md is authoritative, hand-judged from the
preserved code and final responses.

The concentration computation is NOT changed. `supervisor/concentration.py` is
frozen (canaried by LF-normalized hash vs the S7 `a56e180` blob). S8 attaches a
minimal mechanical CONTRACT / provenance envelope around the unchanged
`measure()` output; the contract carries no interpretation and no thresholds
(canaried with concentration._contains_interpretation).

Usage:
  python s8/run.py                 # full run (6 harnessed runs: A,D x 3 conditions)
  python s8/run.py --condition=METHOD-only
  python s8/run.py --fleet=A
  python s8/run.py --raw           # also print each run's final response
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(LAB / "s7"))  # build_fleet lives here; s7 is a namespace pkg

import core          # noqa: E402
import harness       # noqa: E402  (the S6 boundary)
import concentration  # noqa: E402  (the frozen S7 measurement; NOT modified)
import build_fleet    # noqa: E402  (the frozen S7 fleets; build_all() is pure)

RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8")
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
SEED_DIR = LAB / "s7" / "memory_seed"

OPTIONS = {"temperature": 0.2, "num_ctx": 131072}
MAX_TURNS = 10
REQUEST_TIMEOUT = 900.0
BENCH_TIMEOUT = 10.0

# Fleet A has an engine concentration (60/70 on execute_enrichment.py); D is the
# distributed mirror (no majority concentration; a real 17/70 reservation cohort
# + 1 open investigation). Reused frozen from S7.
DOMINANT = {"A": ("engine", 60, "enrichment/harness/execute_enrichment.py"),
            "D": None}
CONDITIONS = ("METHOD-only", "MEASUREMENT-only", "METHOD+MEASUREMENT")
FLEETS = ("A", "D")

# The frozen concentration.py blob hash (LF-normalized) at S7 commit a56e180.
# S8 must NOT change the computation; we canary the file's normalized content
# against this. (Raw bytes differ only by CRLF on Windows; normalized is stable.)
FROZEN_CONCENTRATION_HASH = "c78b0dab1c2032c6"


# --- the measurement contract (S8 layer; concentration.py is NOT modified) ----

# A minimal mechanical contract + provenance carried AROUND the unchanged
# measure() output. It describes what the measurement IS mechanically and what
# it is NOT; it carries no interpretation and no thresholds (canaried below).
# The supervisor sees it inline in the rendered snapshot JSON.
CONTRACT = {
    "nature": "mechanically computed from snapshot records; no interpretation; "
              "no thresholds",
    "computes": ("for each dependency type {engine, trigger, effect, digest}: "
                 "workers per identity, and each identity's share of the whole "
                 "fleet"),
    "source_fields": ("worker.engine, worker.trigger, worker.effect, "
                      "current-version digest from version_history"),
    "share": "worker_count / total worker_count of the whole fleet",
    "ordering": "sorted by worker_count descending (an ordering of facts, "
                "not a judgement)",
    "is_not": ("does not label or threshold any distribution; whether it "
               "matters is for the supervisor to decide"),
    "provenance": ("computed by supervisor.concentration.measure (a pure "
                  "function; the snapshot is not mutated)"),
}


def _attach_measurement(snap: dict) -> dict:
    """Return a snapshot with the measurement + contract envelope attached.

    The S8 authorization switch: METHOD-only runs WITHOUT this; the two
    MEASUREMENT-bearing conditions run WITH it. The envelope wraps the
    unchanged concentration.measure(snap) output; concentration.py is not
    touched and the snapshot is not mutated by measure() (canaried).
    """
    out = dict(snap)
    out["dependency_concentration"] = {
        "schema": concentration.SCHEMA,
        "contract": CONTRACT,
        "measurement": concentration.measure(snap),
    }
    return out


# --- helpers ----------------------------------------------------------------

def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_seed(name: str) -> list[dict]:
    path = SEED_DIR / f"{name}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _lf_norm_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


# --- the call-purpose classifier (non-authoritative hint) -------------------

_DEP_DIMS = ("engine", "trigger", "effect")
# complementary (non-dependency) fields a call might compute over
_COMP_FIELDS = ("task", "customer", "name", "pending_exceptions", "investigation",
                "recent_runs", "runs_total", "version_history", "confirmations",
                "summary", "scope", "purpose", "committing", "readable_model",
                "inbox", "current_version", "promote")


def _classify_call(code: str) -> dict:
    """Tag one preserved Python call by WHAT it is calculating.

    Heuristic (regex on the code). Non-authoritative; FINDINGS.md is
    authoritative. Returns the set of purposes detected, a primary tag, and the
    evidence that triggered each tag.

    concentration_rederivation : recomputes what the measurement already gives
                                 (group/count/share over engine/trigger/effect/
                                 digest from worker records).
    measurement_read           : reads the precomputed measurement / contract /
                                 by_type instead of re-counting workers.
    complementary              : computes something the measurement does NOT give
                                 (task/customer/name breakdowns, the reservation
                                 cohort, the open investigation, run/version
                                 histories).
    probe                     : no clear intent / exploratory / fallback.
    """
    c = code.lower()
    purposes: set[str] = set()
    ev: dict[str, str] = {}

    # --- measurement_read: accesses the precomputed measurement / contract ---
    if re.search(r'dependency_concentration|by_type|\.get\("contract"|"contract"|\["contract"\]',
                 c):
        purposes.add("measurement_read")
        ev["measurement_read"] = "accesses dependency_concentration/by_type/contract"

    # --- concentration_rederivation: aggregates dependency dims from worker recs
    dep_dims = []
    for d in _DEP_DIMS:
        if re.search(rf"\b{d}\b", c):
            dep_dims.append(d)
    if re.search(r"\bdigest\b", c):
        dep_dims.append("digest")
    aggregates = bool(re.search(
        r"counter\(|defaultdict|groupby|value_counts|most_common|\.count\(|"
        r"for w in workers|for w in snapshot|for w in snapshot\[", c))
    shares = bool(re.search(
        r"/\s*len|/\s*total|/\s*70|worker_count|share|percent|\*\s*100|round\(", c))
    if dep_dims and (aggregates or shares or re.search(r"for w in|for r in", c)):
        purposes.add("concentration_rederivation")
        ev["concentration_rederivation"] = f"aggregates deps {dep_dims} from worker records"

    # --- complementary: non-dependency fields, and not a re-derivation ---
    comp_fields = [f for f in _COMP_FIELDS if re.search(rf"\b{re.escape(f)}\b", c)]
    if comp_fields and "concentration_rederivation" not in purposes:
        purposes.add("complementary")
        ev["complementary"] = f"touches {comp_fields}"

    if not purposes:
        purposes.add("probe")
        ev["probe"] = "no clear dependency-aggregation or complementary signal"

    priority = ["measurement_read", "concentration_rederivation",
                "complementary", "probe"]
    primary = next((p for p in priority if p in purposes), "probe")
    return {"purposes": sorted(purposes), "primary": primary, "evidence": ev}


def _classify_session_calls(session: dict) -> list[dict]:
    """Classify every preserved Python call in a session. One row per call."""
    rows = []
    for t in session.get("turns", []):
        for pc in t.get("python_calls", []):
            cls = _classify_call(pc.get("code", ""))
            rows.append({
                "turn": t["turn"],
                "ok": pc["ok"],
                "refused": pc["refused"],
                "error": pc.get("error"),
                "purposes": cls["purposes"],
                "primary": cls["primary"],
                "evidence": cls["evidence"],
                "code_head": (pc.get("code") or "")[:220],
            })
    return rows


def _call_mix(rows: list[dict]) -> dict:
    """Aggregate per-call purposes into a condition-level mix."""
    def n(purpose: str) -> int:
        return sum(1 for r in rows if purpose in r["purposes"])
    return {
        "total_calls": len(rows),
        "concentration_rederivation": n("concentration_rederivation"),
        "measurement_read": n("measurement_read"),
        "complementary": n("complementary"),
        "probe": n("probe"),
        "failed_calls": sum(1 for r in rows if not r["ok"]),
        "nameerrors": sum(1 for r in rows if r["error"] and "NameError" in r["error"]),
    }


def _classify_response(text: str, fleet_key: str) -> dict:
    """Hint: what the final response grounds in / claims. Non-authoritative."""
    t = (text or "").lower()
    out = {
        "cites_measurement": bool(re.search(
            r"dependency_concentration|concentration (measurement|profile)|"
            r"the measurement|by_type|the platform (already )?(compute|report)", t)),
        "cites_share": bool(re.search(
            r"0\.857|0\.243|0\.24|\b60\s*/\s*70\b|85\.7|17\s*/\s*70|\bshare\b", t)),
        "interpretation_with_llm": bool(re.search(
            r"blast|affect|risk|single bug|would impact|concern|worth|"
            r"attention|recommend|suggest|move|diversif", t)),
        "claims_measurement_says_risk": bool(re.search(
            r"(measurement|dependency_concentration|contract).{0,80}\b(risk|safe|dangerous|risky)\b", t)),
    }
    if fleet_key == "A":
        out["identifies_engine_concentration"] = bool(re.search(
            r"enrichment.*60|60.*enrichment|60\s*/\s*70|85\.7|single engine|"
            r"one engine|same engine|all.*engine|engine.*concentrat", t))
    if fleet_key == "D":
        # a false concentration would assert a large majority (60/70, 55/70, 85/86%)
        out["invents_false_concentration"] = bool(re.search(
            r"\b(60|55)\s*/\s*70\b|85\s*%|86\s*%|79\s*%|78\s*%|"
            r"\bdominant\b.{0,40}\b(engine|trigger|digest)\b.{0,40}\b(60|55|85|86)\b", t))
        out["finds_no_majority_concentration"] = not out["invents_false_concentration"]
    return out


# --- run one condition ------------------------------------------------------

def _contexts_for(snap: dict, condition: str) -> list:
    """Build the context list for a condition over a snapshot.

    METHOD-only / METHOD+MEASUREMENT carry the full S5 memory; MEASUREMENT-only
    is cold. MEASUREMENT-bearing conditions attach the measurement+contract to
    the snapshot that FleetContext renders.
    """
    contexts = [harness.FleetContext(snap)]
    if condition in ("METHOD-only", "METHOD+MEASUREMENT"):
        knowledge = _load_seed("knowledge")
        preferences = _load_seed("preferences")
        methods = _load_seed("methods")
        contexts.append(harness.MemoryContext(knowledge, preferences, methods))
    return contexts


def _snapshot_for(fleet_snap: dict, condition: str) -> dict:
    if condition in ("MEASUREMENT-only", "METHOD+MEASUREMENT"):
        return _attach_measurement(fleet_snap)
    return fleet_snap


def _run_condition(fleet_key: str, condition: str, fleet_snap: dict) -> dict:
    snap = _snapshot_for(fleet_snap, condition)
    has_meas = condition in ("MEASUREMENT-only", "METHOD+MEASUREMENT")
    has_method = condition in ("METHOD-only", "METHOD+MEASUREMENT")
    print(f"\n-- [{condition}] fleet {fleet_key} (dominant={DOMINANT[fleet_key]}) "
          f"method={has_method} measurement={has_meas} "
          f"workers={snap['worker_count']}", flush=True)
    contexts = _contexts_for(snap, condition)
    h = harness.SupervisorHarness(
        tools=[harness.python_analysis_tool(BENCH_TIMEOUT)],
        contexts=contexts,
        options=OPTIONS, request_timeout=REQUEST_TIMEOUT,
        bench_timeout=BENCH_TIMEOUT)
    session = h.run(PROMPT, max_turns=MAX_TURNS)
    session["run_id"] = _stamp()
    session["fleet"] = fleet_key
    session["condition"] = condition
    session["has_method"] = has_method
    session["has_measurement"] = has_meas
    session["dominant"] = DOMINANT[fleet_key]
    rows = _classify_session_calls(session)
    session["call_purposes"] = rows
    session["call_mix"] = _call_mix(rows)
    session["response_hints"] = _classify_response(
        session.get("final_response") or "", fleet_key)
    _print_summary(session)
    return session


def _print_summary(session: dict) -> None:
    m = session["call_mix"]
    print(f"    python_calls={m['total_calls']} turns={session['turn_count']} "
          f"stop={session['stop_reason']} "
          f"rederive={m['concentration_rederivation']} "
          f"read={m['measurement_read']} "
          f"complement={m['complementary']} "
          f"probe={m['probe']} failed={m['failed_calls']} "
          f"nameerrors={m['nameerrors']}", flush=True)
    rh = session["response_hints"]
    print(f"    response: cites_measurement={rh['cites_measurement']} "
          f"interpretation_llm={rh['interpretation_with_llm']} "
          f"claims_meas_risk={rh['claims_measurement_says_risk']}", flush=True)


def _save_run(session: dict) -> Path:
    cond = session["condition"]
    fleet = session["fleet"]
    d = RESULTS / cond / fleet
    d.mkdir(parents=True, exist_ok=True)
    harness.save(session, d / "run.json")
    harness.save_events_jsonl(session, d / "session.jsonl")
    (d / "calls.json").write_text(
        json.dumps(session["call_purposes"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return d / "run.json"


# --- canaries (no model call) ------------------------------------------------

def _run_canaries() -> dict:
    """Pre-run canaries: harness + concentration self-tests, concentration.py
    unchanged, contract has no interpretation/threshold word, floor files hashed
    (compared again post-run)."""
    print("=== S8 CANARIES (no model call) ===", flush=True)
    c = {"harness_self_test": harness._self_test() == 0,
         "concentration_self_test": concentration._self_test() == 0}
    if not c["harness_self_test"]:
        sys.stderr.write("harness self-test FAILED.\n")
    if not c["concentration_self_test"]:
        sys.stderr.write("concentration self-test FAILED.\n")

    # concentration.py unchanged vs the frozen S7 blob (LF-normalized).
    conc_py = LAB / "supervisor" / "concentration.py"
    c["concentration_py_normalized_hash"] = _lf_norm_hash(conc_py)
    c["concentration_py_unchanged"] = (
        c["concentration_py_normalized_hash"] == FROZEN_CONCENTRATION_HASH)
    print(f"  concentration.py LF-hash={c['concentration_py_normalized_hash']} "
          f"frozen={FROZEN_CONCENTRATION_HASH} unchanged="
          f"{c['concentration_py_unchanged']}", flush=True)

    # contract carries no interpretation / threshold word (the measurement's own
    # canary, applied to the S8 contract envelope).
    bad = concentration._contains_interpretation(CONTRACT)
    c["contract_no_interpretation_word"] = bad is None
    c["contract_bad_word"] = bad
    if bad is not None:
        sys.stderr.write(f"CONTRACT CANARY FAILED: interpretation word '{bad}' "
                         f"in the contract.\n")
    # also canary the FULL envelope (contract + measurement) on a real fleet.
    fleets = build_fleet.build_all()
    env = _attach_measurement(fleets["A"]["snapshot"])["dependency_concentration"]
    bad_env = concentration._contains_interpretation(env)
    c["envelope_no_interpretation_word"] = bad_env is None
    c["envelope_bad_word"] = bad_env
    print(f"  contract no interpretation word: "
          f"{c['contract_no_interpretation_word']} (bad={bad})  "
          f"envelope={c['envelope_no_interpretation_word']}", flush=True)

    # measure() is still pure: snapshot hash unchanged by attaching the envelope.
    import snapshot as snap_mod
    s = fleets["A"]["snapshot"]
    h_before = snap_mod.hash_snapshot(s)
    _attach_measurement(s)  # does not mutate s
    h_after = snap_mod.hash_snapshot(s)
    c["measure_pure_snapshot_unchanged"] = h_before == h_after
    print(f"  measure pure (snapshot unchanged by attachment): "
          f"{c['measure_pure_snapshot_unchanged']}", flush=True)

    # floor files hashed now; compared again at the end to prove nothing changed.
    snap_py = LAB / "supervisor" / "snapshot.py"
    rulebook_jsonl = LAB / "supervisor" / "rulebook.jsonl"
    c["floor_hashes_before"] = {str(p): _file_hash(p) for p in
                                (snap_py, rulebook_jsonl, conc_py)}
    return c


def _post_run_floor_canary(canary: dict) -> dict:
    snap_py = LAB / "supervisor" / "snapshot.py"
    rulebook_jsonl = LAB / "supervisor" / "rulebook.jsonl"
    conc_py = LAB / "supervisor" / "concentration.py"
    after = {str(p): _file_hash(p) for p in (snap_py, rulebook_jsonl, conc_py)}
    unchanged = after == canary["floor_hashes_before"]
    print(f"  floor files unchanged across all runs: {unchanged}", flush=True)
    return {"floor_hashes_after": after, "floor_files_unchanged": unchanged,
            "concentration_py_still_unchanged":
                _lf_norm_hash(conc_py) == FROZEN_CONCENTRATION_HASH}


# --- fleet loading + hash assertion ----------------------------------------

def _load_fleets() -> dict:
    fleets = build_fleet.build_all()
    for key in FLEETS:
        h = fleets[key]["hash"]
        oracle_h = ORACLE["fleet_hashes"][key]
        if h != oracle_h:
            sys.stderr.write(f"CANARY FAILED: fleet {key} hash {h} != frozen "
                             f"oracle {oracle_h} -- stimulus drifted. Aborting.\n")
            raise SystemExit(1)
    return fleets


# --- comparison + summary ---------------------------------------------------

def build_comparison(runs: dict) -> dict:
    """3 conditions x 2 fleets call-mix + response-hint comparison."""
    comp: dict = {}
    for fleet in FLEETS:
        comp[fleet] = {"dominant": DOMINANT[fleet], "by_condition": {}}
        for cond in CONDITIONS:
            s = runs.get(fleet, {}).get(cond)
            if not s:
                continue
            m = s["call_mix"]
            comp[fleet]["by_condition"][cond] = {
                "has_method": s["has_method"],
                "has_measurement": s["has_measurement"],
                "python_calls": m["total_calls"],
                "turns": s["turn_count"],
                "stop_reason": s["stop_reason"],
                "concentration_rederivation": m["concentration_rederivation"],
                "measurement_read": m["measurement_read"],
                "complementary": m["complementary"],
                "probe": m["probe"],
                "failed_calls": m["failed_calls"],
                "nameerrors": m["nameerrors"],
                "response_hints": s["response_hints"],
            }
    return comp


def _comparison_md(comp: dict) -> str:
    lines = [
        "# S8 -- composition: METHOD x MEASUREMENT (call MIX, not just count)",
        "",
        "> METHOD-only = full S5 memory, no measurement.  "
        "MEASUREMENT-only = COLD, measurement+contract attached.  "
        "METHOD+MEASUREMENT = full memory AND measurement+contract.",
        "> The headline is the CALL MIX: rederive (re-computes the concentration "
        "by hand) / read (uses the precomputed measurement) / complementary "
        "(task/customer/investigation) / probe. Non-authoritative; FINDINGS.md is "
        "authoritative.",
        ""]
    for fleet in FLEETS:
        dom = comp[fleet]["dominant"]
        dom_s = ("none (distributed mirror)" if dom is None
                 else f"{dom[0]} {dom[1]}/70")
        lines.append(f"## fleet {fleet} -- dominant: {dom_s}")
        lines.append("")
        lines.append("| condition | calls | turns | rederive | read | complement | "
                     "probe | failed | nameerr |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for cond in CONDITIONS:
            c = comp[fleet]["by_condition"].get(cond)
            if not c:
                continue
            lines.append(
                f"| {cond} | {c['python_calls']} | {c['turns']} | "
                f"{c['concentration_rederivation']} | {c['measurement_read']} | "
                f"{c['complementary']} | {c['probe']} | {c['failed_calls']} | "
                f"{c['nameerrors']} |")
        lines.append("")
        lines.append(f"### fleet {fleet} -- response hints")
        lines.append("")
        lines.append("| condition | cites_measurement | interpretation_llm | "
                     "claims_meas_risk | A:identifies / D:no-false-conc |")
        lines.append("|---|---|---|---|---|")
        for cond in CONDITIONS:
            c = comp[fleet]["by_condition"].get(cond)
            if not c:
                continue
            rh = c["response_hints"]
            if fleet == "A":
                verdict = str(rh.get("identifies_engine_concentration"))
            else:
                verdict = ("no-false-conc=" + str(rh.get("finds_no_majority_concentration")))
            lines.append(f"| {cond} | {rh['cites_measurement']} | "
                         f"{rh['interpretation_with_llm']} | "
                         f"{rh['claims_measurement_says_risk']} | {verdict} |")
        lines.append("")
    lines.append("The authoritative verdicts (did it compose? did interpretation "
                 "stay with the LLM? did the mirror move on?) are hand-judged in "
                 "`FINDINGS.md` from the preserved runs.")
    return "\n".join(lines) + "\n"


# --- main -------------------------------------------------------------------

def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    cond_only = next((a.split("=")[1] for a in argv
                      if a.startswith("--condition=")), None)
    fleet_only = next((a.split("=")[1] for a in argv
                      if a.startswith("--fleet=")), None)
    RESULTS.mkdir(parents=True, exist_ok=True)

    canary = _run_canaries()
    if not (canary["harness_self_test"]
            and canary["concentration_self_test"]
            and canary["concentration_py_unchanged"]
            and canary["contract_no_interpretation_word"]
            and canary["envelope_no_interpretation_word"]
            and canary["measure_pure_snapshot_unchanged"]):
        sys.stderr.write("CANARY FAILED -- aborting before any model call.\n")
        (RESULTS / "canary.json").write_text(
            json.dumps(canary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1
    (RESULTS / "canary.json").write_text(
        json.dumps(canary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fleets = _load_fleets()
    conds = [cond_only] if cond_only else list(CONDITIONS)
    keys = [fleet_only] if fleet_only else list(FLEETS)

    runs: dict[str, dict] = {k: {} for k in keys}
    print("\n" + "=" * 70 + "\n=== S8 RUNS (3 conditions x 2 fleets under S6 "
          "harness) ===\n" + "=" * 70, flush=True)
    for fleet in keys:
        for cond in conds:
            session = _run_condition(fleet, cond, fleets[fleet]["snapshot"])
            _save_run(session)
            runs[fleet][cond] = session

    post = _post_run_floor_canary(canary)
    comp = build_comparison(runs)
    (RESULTS / "comparison.json").write_text(
        json.dumps(comp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / "comparison.md").write_text(_comparison_md(comp), encoding="utf-8")

    summary = {
        "run_id": _stamp(), "model": core.MODEL,
        "conditions": list(conds), "fleets": list(keys),
        "canary": {"concentration_py_unchanged":
                    canary["concentration_py_unchanged"],
                   "contract_no_interpretation_word":
                    canary["contract_no_interpretation_word"],
                   "measure_pure_snapshot_unchanged":
                    canary["measure_pure_snapshot_unchanged"],
                   "floor_files_unchanged": post["floor_files_unchanged"]},
        "comparison": comp,
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n" + "=" * 70 + "\n=== S8 COMPLETE ===\n" + "=" * 70, flush=True)
    print(f"  floor unchanged: {post['floor_files_unchanged']}  "
          f"concentration.py still unchanged: "
          f"{post['concentration_py_still_unchanged']}", flush=True)
    for fleet in keys:
        print(f"  fleet {fleet}:", flush=True)
        for cond in conds:
            c = comp[fleet]["by_condition"][cond]
            print(f"    {cond:22s} calls={c['python_calls']} "
                  f"rederive={c['concentration_rederivation']} "
                  f"read={c['measurement_read']} "
                  f"complement={c['complementary']} "
                  f"failed={c['failed_calls']}", flush=True)
    print(f"\n  results: {RESULTS}", flush=True)
    if raw:
        for fleet in keys:
            for cond in conds:
                s = runs[fleet][cond]
                print(f"\n=== {cond} / fleet {fleet} FINAL RESPONSE ===\n"
                      + (s.get("final_response") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))