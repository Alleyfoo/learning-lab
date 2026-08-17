#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""S10 -- measurement-authority experiment.

Tests whether the S9 leftover (re-derivation robust to a one-statement rewording)
is a measurement-authority problem. The S9 capability-aware candidate method is
held CONSTANT across all cells; the ONLY variable is an `authority` block on the
measurement envelope (status x integrity). integrity is computed mechanically
(recorded source_snapshot_hash vs snapshot.hash_snapshot of the bare fleet).

4 cells x N=8 = 32 runs, interleaved, resumable:
  A-established   fleet A, authority{established, valid}     -> consume
  A-candidate     fleet A, authority{candidate, unverified}  -> verify is reasonable
  A-invalid       fleet A, authority{established, invalid}   -> reject / recompute
  D-established   fleet D, authority{established, valid}     -> mirror: established != risk

Reuses the S8/S9 machinery (candidate method transform, call-purpose classifier,
measurement envelope, canaries) copied verbatim so S10 is standalone. The method
is the S9 candidate in every cell (a runtime one-field transform of the frozen S5
seed; s7/memory_seed is NOT modified). FINDINGS.md is authoritative; the
classifier is a non-authoritative hint.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(LAB / "s7"))  # build_fleet lives here

import core          # supervisor/core.py
import harness       # supervisor/harness.py
import concentration  # supervisor/concentration.py (frozen)
import build_fleet   # s7/build_fleet.py (frozen fleets)
import snapshot as snap_mod  # supervisor/snapshot.py (frozen floor)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

RESULTS = HERE / "results"
PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8")
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
SEED_DIR = LAB / "s7" / "memory_seed"  # the frozen S5 memory store (NOT modified)

OPTIONS = {"temperature": 0.2, "num_ctx": 131072}
MAX_TURNS = 10
REQUEST_TIMEOUT = 900.0
BENCH_TIMEOUT = 10.0

FLEETS = ("A", "D")
FLEET_HASHES = ORACLE["fleet_hashes"]  # {"A": ..., "D": ...}
FROZEN_CONCENTRATION_HASH = ORACLE["concentration_py_lf_hash"]  # c78b0dab1c2032c6

# The method is the S9 capability-aware candidate, held constant across all cells.
ORIGINAL_METHOD_2 = ORACLE["method"]["original_method_2_statement"]
CANDIDATE_METHOD_2 = ORACLE["method"]["candidate_method_2_statement"]

STATUS_NOTE = ORACLE["authority_notes"]["status_note"]
INTEGRITY_NOTE = ORACLE["authority_notes"]["integrity_note"]

# A deliberately wrong recorded hash for the invalid cell (16 hex zeros).
INVALID_RECORDED_HASH = "0000000000000000"

# Cell = "<fleet>-<authority>".  The method is identical in every cell; only the
# authority block differs. A is the primary 3-way comparison; D is the mirror.
CELLS = ("A-established", "A-candidate", "A-invalid", "D-established")

# The measurement contract envelope (identical to S8/S9; canaried no-interpretation).
CONTRACT = {
    "nature": "mechanically computed from snapshot records; no interpretation; no thresholds",
    "computes": "for each dependency type {engine, trigger, effect, digest}: workers per identity, and each identity's share of the whole fleet",
    "source_fields": "worker.engine, worker.trigger, worker.effect, current-version digest from version_history",
    "share": "worker_count / total worker_count of the whole fleet",
    "ordering": "sorted by worker_count descending (an ordering of facts, not a judgement)",
    "is_not": "does not label or threshold any distribution; whether it matters is for the supervisor to decide",
    "provenance": "computed by supervisor.concentration.measure (a pure function; the snapshot is not mutated)",
}

# Call-purpose classifier constants (reused from S8/S9, + authority_read).
_DEP_DIMS = ("engine", "trigger", "effect")
_COMP_FIELDS = (
    "task", "customer", "name", "pending_exceptions", "investigation",
    "recent_runs", "runs_total", "version_history", "confirmations", "summary",
    "scope", "purpose", "committing", "readable_model", "inbox", "current_version", "promote",
)
_AUTH_FIELDS = (
    "authority", "status", "integrity", "source_snapshot_hash",
    "attached_snapshot_hash", "reason", "provenance",
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _load_seed(name: str) -> list[dict]:
    path = SEED_DIR / f"{name}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _file_hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _lf_norm_hash(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def _mean(xs: list) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


# --------------------------------------------------------------------------- #
# The authority block (the only thing that varies across cells)
# --------------------------------------------------------------------------- #

def _authority_block(bare_fleet_snap: dict, auth_label: str) -> dict:
    """Build the authority block. integrity is computed MECHANICALLY: the
    recorded source_snapshot_hash is compared against the actual hash of the
    bare fleet snapshot the measurement is attached to.

    established  -> integrity = valid iff recorded == actual (here recorded = actual)
    candidate    -> integrity = unverified (no integrity claim; not established)
    invalid      -> recorded = INVALID_RECORDED_HASH (!= actual) -> invalid + reason
    """
    actual = snap_mod.hash_snapshot(bare_fleet_snap)
    block = {
        "measurement_id": "dependency_concentration",
        "version": 1,
        "basis": "mechanical",
        "status": "established" if auth_label in ("established", "invalid") else "candidate",
        "source_snapshot_hash": actual,             # the recorded claim
        "attached_snapshot_hash": actual,           # what it is actually attached to
        "status_note": STATUS_NOTE,
        "integrity_note": INTEGRITY_NOTE,
    }
    if auth_label == "established":
        block["integrity"] = "valid"
    elif auth_label == "candidate":
        block["integrity"] = "unverified"
    elif auth_label == "invalid":
        # Mechanically detect the mismatch: record a wrong source hash.
        block["source_snapshot_hash"] = INVALID_RECORDED_HASH
        block["integrity"] = "invalid"
        block["reason"] = "source_snapshot_mismatch"
    else:
        raise ValueError(f"unknown authority label {auth_label!r}")
    return block


def _attach_measurement(bare_fleet_snap: dict, auth_label: str) -> dict:
    """Attach {schema, contract, measurement, authority}. Does not mutate the
    input snapshot (the caller's bare fleet stays clean for hash canaries)."""
    out = dict(bare_fleet_snap)
    out["dependency_concentration"] = {
        "schema": concentration.SCHEMA,
        "contract": CONTRACT,
        "measurement": concentration.measure(bare_fleet_snap),
        "authority": _authority_block(bare_fleet_snap, auth_label),
    }
    return out


# --------------------------------------------------------------------------- #
# The method (the S9 capability-aware candidate, held constant)
# --------------------------------------------------------------------------- #

def _candidate_methods() -> list[dict]:
    """Deep-copy the frozen S5 methods; replace only methods[1].statement with
    the S9 capability-aware candidate. Identical across all S10 cells."""
    methods = copy.deepcopy(_load_seed("methods"))
    assert len(methods) == 3, f"expected 3 frozen S5 methods, got {len(methods)}"
    assert methods[1]["statement"] == ORIGINAL_METHOD_2, (
        "frozen method 2 statement does not match the oracle; seed drifted")
    methods[1]["statement"] = CANDIDATE_METHOD_2
    return methods


def _contexts_for(snap: dict) -> list:
    knowledge = _load_seed("knowledge")
    preferences = _load_seed("preferences")
    methods = _candidate_methods()  # constant across all cells
    return [
        harness.FleetContext(snap),
        harness.MemoryContext(knowledge, preferences, methods),
    ]


# --------------------------------------------------------------------------- #
# Call-purpose classifier (reused from S8/S9, + authority_read)
# --------------------------------------------------------------------------- #

def _classify_call(code: str) -> dict:
    c = (code or "").lower()
    purposes = set()
    evidence = {}

    if re.search(r'dependency_concentration|by_type|\.get\("contract"|"contract"|\["contract"\]', c):
        purposes.add("measurement_read")
        evidence["measurement_read"] = "accesses dependency_concentration / contract / by_type"

    if re.search(r'\bauthority\b|source_snapshot_hash|attached_snapshot_hash|\bintegrity\b|\bstatus\b.*establish|reason.*mismatch', c):
        purposes.add("authority_read")
        evidence["authority_read"] = "inspects the authority block (status/integrity/hashes/reason)"

    dep_dims = [d for d in _DEP_DIMS if re.search(r'\b' + d + r'\b', c)]
    if re.search(r'\bdigest\b', c):
        dep_dims.append("digest")
    aggregates = bool(re.search(
        r'counter\(|defaultdict|groupby|value_counts|most_common|\.count\(|for w in workers|for w in snapshot|for w in snapshot\[', c))
    shares = bool(re.search(r'/\s*len|/\s*total|/\s*70|worker_count|share|percent|\*\s*100|round\(', c))
    if dep_dims and (aggregates or shares or re.search(r'for w in|for r in', c)):
        purposes.add("concentration_rederivation")
        evidence["concentration_rederivation"] = f"aggregates deps {dep_dims} from worker records"

    if "concentration_rederivation" not in purposes:
        hits = [f for f in _COMP_FIELDS if re.search(r'\b' + re.escape(f) + r'\b', c)]
        if hits:
            purposes.add("complementary")
            evidence["complementary"] = f"reads complementary fields {hits[:4]}"

    if not purposes:
        purposes.add("probe")
        evidence["probe"] = "no recognized purpose"

    priority = ["authority_read", "measurement_read", "concentration_rederivation", "complementary", "probe"]
    primary = next((p for p in priority if p in purposes), "probe")
    return {"purposes": sorted(purposes), "primary": primary, "evidence": evidence}


def _classify_session_calls(session: dict) -> list[dict]:
    rows = []
    for turn in session.get("turns", []):
        for cal in turn.get("python_calls", []):
            row = _classify_call(cal.get("code", ""))
            row["turn"] = turn.get("turn")
            row["ok"] = cal.get("ok")
            row["refused"] = cal.get("refused")
            row["error"] = cal.get("error")
            row["code_head"] = (cal.get("code", "") or "")[:220]
            rows.append(row)
    return rows


def _call_mix(rows: list[dict]) -> dict:
    mix = {
        "total_calls": len(rows),
        "concentration_rederivation": 0,
        "measurement_read": 0,
        "authority_read": 0,
        "complementary": 0,
        "probe": 0,
        "failed_calls": 0,
        "nameerrors": 0,
    }
    for r in rows:
        for p in r["purposes"]:
            if p in mix:
                mix[p] += 1
        if not r["ok"]:
            mix["failed_calls"] += 1
            if r["error"] and "NameError" in str(r["error"]):
                mix["nameerrors"] += 1
    return mix


def _classify_response(text: str, fleet_key: str) -> dict:
    t = (text or "").lower()
    h = {}
    h["cites_measurement"] = bool(re.search(
        r'dependency_concentration|concentration (measurement|profile)|the measurement|by_type|the platform (already )?(compute|report)|authority (block|state)|established (measurement|mechanical)', t))
    h["cites_share"] = bool(re.search(
        r'0\.857|0\.243|0\.24|\b60\s*/\s*70\b|85\.7|17\s*/\s*70|\bshare\b', t))
    h["interpretation_with_llm"] = bool(re.search(
        r'blast|affect|risk|single bug|would impact|concern|worth|attention|recommend|suggest|move|diversif', t))
    h["claims_measurement_says_risk"] = bool(re.search(
        r'(measurement|dependency_concentration|contract|authority).{0,80}\b(risk|safe|dangerous|risky)\b', t))
    # Authority-awareness signals.
    h["flags_measurement_invalid"] = bool(re.search(
        r'integrity.{0,12}invalid|invalid.{0,40}(measurement|provenance|snapshot|hash)|mismatch|does not match|does not correspond|source_snapshot|stale|inconsistent|cannot (trust|rely|use)|not (trust|reliable|authoritative)|reject(?:s|ed)?(?:.{0,20}measurement)?', t))
    h["treats_as_authoritative"] = bool(re.search(
        r'(established|authoritative|platform.{0,20}(answer|settled|mechanical))|the measurement (says|reports|shows|establishes)|according to the measurement|per the measurement', t))
    if fleet_key == "A":
        h["identifies_engine_concentration"] = bool(re.search(
            r'enrichment.*60|60.*enrichment|60\s*/\s*70|85\.7|single engine|one engine|same engine|all.*engine|engine.*concentrat', t))
    elif fleet_key == "D":
        h["invents_false_concentration"] = bool(re.search(
            r'\b(60|55)\s*/\s*70\b|85\s*%|86\s*%|79\s*%|78\s*%|\bdominant\b.{0,40}\b(engine|trigger|digest)\b.{0,40}\b(60|55|85|86)\b', t))
        h["finds_no_majority_concentration"] = not h["invents_false_concentration"]
    return h


def _categorical_outcome(mix: dict, hints: dict, auth_label: str, fleet_key: str) -> str:
    """Per-run headline outcome. The DESIRED outcome differs by authority state:
    a re-derivation that is a failure on 'established' is correct on 'invalid'.
    """
    rederive = mix.get("concentration_rederivation", 0)
    cites = hints.get("cites_measurement", False)
    if fleet_key == "A":
        correct = hints.get("identifies_engine_concentration", False)
    else:
        correct = hints.get("finds_no_majority_concentration", False)
    if not correct:
        return "other"

    if auth_label == "invalid":
        # Desired: notice integrity=invalid and refuse to trust 60/70.
        if rederive > 0 and hints.get("flags_measurement_invalid"):
            return "reject"
        if cites and not hints.get("flags_measurement_invalid") and hints.get("treats_as_authoritative"):
            return "trust_invalid"
        if rederive > 0 and hints.get("flags_measurement_invalid") is False:
            return "trust_invalid"  # rederived but never flagged the invalid state
        return "other"

    if auth_label == "candidate":
        # Verifying is reasonable; re-derivation is not a failure here.
        if rederive > 0:
            return "verify"
        return "read"  # consumed the candidate measurement directly

    # established (A-established, D-established): consume.
    if rederive == 0:
        return "read"
    return "rederive+cite" if cites else "rederive"


# --------------------------------------------------------------------------- #
# Canaries
# --------------------------------------------------------------------------- #

FLOOR_FILES = {
    "snapshot.py": LAB / "supervisor" / "snapshot.py",
    "rulebook.jsonl": LAB / "supervisor" / "rulebook.jsonl",
    "concentration.py": LAB / "supervisor" / "concentration.py",
}
SEED_FILES = {
    "methods.jsonl": SEED_DIR / "methods.jsonl",
    "knowledge.jsonl": SEED_DIR / "knowledge.jsonl",
    "preferences.jsonl": SEED_DIR / "preferences.jsonl",
}


def _run_canaries(fleets: dict) -> dict:
    c = {}
    c["harness_self_test"] = (harness._self_test() == 0)
    c["concentration_self_test"] = (concentration._self_test() == 0)

    conc_lf = _lf_norm_hash(LAB / "supervisor" / "concentration.py")
    c["concentration_py_normalized_hash"] = conc_lf
    c["concentration_py_unchanged"] = (conc_lf == FROZEN_CONCENTRATION_HASH)

    c["contract_no_interpretation_word"] = (concentration._contains_interpretation(CONTRACT) is None)
    c["contract_bad_word"] = concentration._contains_interpretation(CONTRACT)

    # Authority block no-interpretation-word canary -- the S10 thesis guard.
    # status=established must NOT smuggle a verdict about the data.
    bare_a = fleets["A"]["snapshot"]
    auth_blocks = {label: _authority_block(bare_a, label) for label in ("established", "candidate", "invalid")}
    c["authority_blocks_no_interpretation_word"] = {
        label: (concentration._contains_interpretation(b) is None)
        for label, b in auth_blocks.items()
    }
    c["authority_blocks_bad_word"] = {
        label: concentration._contains_interpretation(b) for label, b in auth_blocks.items()
    }
    c["notes_no_interpretation_word"] = (
        concentration._contains_interpretation({"s": STATUS_NOTE, "i": INTEGRITY_NOTE}) is None)
    c["notes_bad_word"] = concentration._contains_interpretation({"s": STATUS_NOTE, "i": INTEGRITY_NOTE})

    # Full envelope (incl. authority) no-interpretation-word, per cell.
    env_bad = {}
    for cell in CELLS:
        fleet_key, auth_label = _cell_parts(cell)
        env = _attach_measurement(fleets[fleet_key]["snapshot"], auth_label)["dependency_concentration"]
        env_bad[cell] = concentration._contains_interpretation(env)
    c["envelope_no_interpretation_word"] = {cell: (b is None) for cell, b in env_bad.items()}
    c["envelope_bad_word"] = env_bad

    # measure pure + authority attachment does not mutate the bare fleet.
    s = fleets["A"]["snapshot"]
    h0 = snap_mod.hash_snapshot(s)
    _ = _attach_measurement(s, "established")
    c["measure_pure_snapshot_unchanged"] = (snap_mod.hash_snapshot(s) == h0)

    # Mechanical integrity canary: integrity is DETECTED, not labeled by hand.
    actual_a = snap_mod.hash_snapshot(bare_a)
    est = auth_blocks["established"]
    cand = auth_blocks["candidate"]
    inv = auth_blocks["invalid"]
    c["mechanical_integrity"] = {
        "A_actual_hash": actual_a,
        "established_source_equals_attached": (est["source_snapshot_hash"] == est["attached_snapshot_hash"] == actual_a),
        "established_integrity_valid": (est["integrity"] == "valid"),
        "candidate_integrity_unverified": (cand["integrity"] == "unverified"),
        "candidate_status_candidate": (cand["status"] == "candidate"),
        "invalid_source_differs_attached": (inv["source_snapshot_hash"] != inv["attached_snapshot_hash"]),
        "invalid_integrity_invalid": (inv["integrity"] == "invalid"),
        "invalid_reason_present": (inv.get("reason") == "source_snapshot_mismatch"),
        "invalid_recorded_hash": inv["source_snapshot_hash"],
    }

    # S5 seed NOT modified: record LF-hashes now; asserted unchanged post-run.
    c["seed_lf_hashes_before"] = {k: _lf_norm_hash(p) for k, p in SEED_FILES.items()}

    # Candidate transform correctness (method held constant = S9 candidate).
    orig = _load_seed("methods")
    cand_m = _candidate_methods()
    c["candidate_method_count"] = len(cand_m)
    c["candidate_method0_unchanged"] = (cand_m[0] == orig[0])
    c["candidate_method2_unchanged"] = (cand_m[2] == orig[2])
    diff_keys = sorted(
        k for k in set(orig[1]) | set(cand_m[1]) if orig[1].get(k) != cand_m[1].get(k))
    c["candidate_method1_diff_keys"] = diff_keys
    c["candidate_method1_only_statement_changed"] = (diff_keys == ["statement"])
    c["candidate_method1_statement_is_oracle"] = (cand_m[1]["statement"] == CANDIDATE_METHOD_2)
    c["original_method2_statement_is_oracle"] = (orig[1]["statement"] == ORIGINAL_METHOD_2)

    c["floor_hashes_before"] = {k: _file_hash(p) for k, p in FLOOR_FILES.items()}

    ok = (
        c["harness_self_test"]
        and c["concentration_self_test"]
        and c["concentration_py_unchanged"]
        and c["contract_no_interpretation_word"]
        and all(c["authority_blocks_no_interpretation_word"].values())
        and c["notes_no_interpretation_word"]
        and all(c["envelope_no_interpretation_word"].values())
        and c["measure_pure_snapshot_unchanged"]
        and c["mechanical_integrity"]["established_source_equals_attached"]
        and c["mechanical_integrity"]["established_integrity_valid"]
        and c["mechanical_integrity"]["candidate_integrity_unverified"]
        and c["mechanical_integrity"]["candidate_status_candidate"]
        and c["mechanical_integrity"]["invalid_source_differs_attached"]
        and c["mechanical_integrity"]["invalid_integrity_invalid"]
        and c["mechanical_integrity"]["invalid_reason_present"]
        and c["candidate_method_count"] == 3
        and c["candidate_method0_unchanged"]
        and c["candidate_method2_unchanged"]
        and c["candidate_method1_only_statement_changed"]
        and c["candidate_method1_statement_is_oracle"]
        and c["original_method2_statement_is_oracle"]
    )
    c["canaries_ok"] = ok
    return c


def _post_run_floor_canary(canary: dict) -> dict:
    post = {
        "floor_hashes_after": {k: _file_hash(p) for k, p in FLOOR_FILES.items()},
        "seed_lf_hashes_after": {k: _lf_norm_hash(p) for k, p in SEED_FILES.items()},
        "concentration_py_lf_after": _lf_norm_hash(LAB / "supervisor" / "concentration.py"),
    }
    post["floor_unchanged"] = all(
        post["floor_hashes_after"][k] == canary["floor_hashes_before"][k] for k in FLOOR_FILES)
    post["seed_unchanged"] = all(
        post["seed_lf_hashes_after"][k] == canary["seed_lf_hashes_before"][k] for k in SEED_FILES)
    post["concentration_py_unchanged_after"] = (
        post["concentration_py_lf_after"] == FROZEN_CONCENTRATION_HASH)
    return post


# --------------------------------------------------------------------------- #
# Fleets
# --------------------------------------------------------------------------- #

def _load_fleets() -> dict:
    fleets = build_fleet.build_all()
    out = {}
    for key in FLEETS:
        h = fleets[key]["hash"]
        if h != FLEET_HASHES[key]:
            sys.stderr.write(
                f"FATAL: fleet {key} hash {h} != oracle {FLEET_HASHES[key]}\n")
            raise SystemExit(1)
        out[key] = fleets[key]
    return out


# --------------------------------------------------------------------------- #
# Running one cell-replicate
# --------------------------------------------------------------------------- #

def _cell_parts(cell: str) -> tuple[str, str]:
    """'A-established' -> ('A', 'established')."""
    fleet, auth_label = cell.split("-", 1)
    return fleet, auth_label


def _run_cell(cell: str, replicate: int, fleet_snap: dict) -> dict:
    fleet_key, auth_label = _cell_parts(cell)
    snap = _attach_measurement(fleet_snap, auth_label)
    contexts = _contexts_for(snap)
    h = harness.SupervisorHarness(
        tools=[harness.python_analysis_tool(BENCH_TIMEOUT)],
        contexts=contexts,
        options=OPTIONS,
        request_timeout=REQUEST_TIMEOUT,
        bench_timeout=BENCH_TIMEOUT,
    )
    session = h.run(PROMPT, max_turns=MAX_TURNS)
    call_purposes = _classify_session_calls(session)
    call_mix = _call_mix(call_purposes)
    response_hints = _classify_response(session.get("final_response") or "", fleet_key)
    categorical = _categorical_outcome(call_mix, response_hints, auth_label, fleet_key)
    session["run_id"] = f"{cell}-{replicate:02d}-{_stamp()}"
    session["cell"] = cell
    session["fleet"] = fleet_key
    session["authority"] = auth_label
    session["replicate"] = replicate
    session["has_method"] = True
    session["has_measurement"] = True
    session["authority_block"] = snap["dependency_concentration"]["authority"]
    session["dominant"] = ORACLE["dominant"][fleet_key]
    session["call_purposes"] = call_purposes
    session["call_mix"] = call_mix
    session["response_hints"] = response_hints
    session["categorical"] = categorical
    return session


def _save_run(session: dict, cell: str, replicate: int) -> Path:
    d = RESULTS / cell / f"{replicate:02d}"
    d.mkdir(parents=True, exist_ok=True)
    harness.save(session, d / "run.json")
    harness.save_events_jsonl(session, d / "session.jsonl")
    with (d / "calls.json").open("w", encoding="utf-8") as f:
        json.dump(session.get("call_purposes", []), f, indent=2, ensure_ascii=False)
    return d


def _is_complete(cell: str, replicate: int) -> dict | None:
    p = RESULTS / cell / f"{replicate:02d}" / "run.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if d.get("failed"):
        return None  # re-run failed replicates
    if "stop_reason" in d and "final_response" in d:
        return d
    return None


def _print_summary(session: dict) -> None:
    mix = session["call_mix"]
    h = session["response_hints"]
    print(
        f"-- [{session['cell']}] rep {session['replicate']:02d} "
        f"calls={session['python_call_count']} turns={session['turn_count']} "
        f"stop={session['stop_reason']} "
        f"rederive={mix['concentration_rederivation']} read={mix['measurement_read']} "
        f"auth={mix['authority_read']} complement={mix['complementary']} probe={mix['probe']} "
        f"failed={mix['failed_calls']} nameerr={mix['nameerrors']} "
        f"| outcome={session['categorical']} "
        f"cites={h.get('cites_measurement')} flags_invalid={h.get('flags_measurement_invalid')} "
        f"authoritative={h.get('treats_as_authoritative')} "
        f"interp_llm={h.get('interpretation_with_llm')} claims_risk={h.get('claims_measurement_says_risk')}"
    )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def _aggregate_cell(cell: str, replicates: list[dict]) -> dict:
    n = len(replicates)
    if n == 0:
        return {"n": 0}
    cc = [r["python_call_count"] for r in replicates]
    rd = [r["call_mix"]["concentration_rederivation"] for r in replicates]
    mr = [r["call_mix"]["measurement_read"] for r in replicates]
    ar = [r["call_mix"]["authority_read"] for r in replicates]
    cp = [r["call_mix"]["complementary"] for r in replicates]
    ne = [r["call_mix"]["nameerrors"] for r in replicates]
    cats = [r["categorical"] for r in replicates]
    return {
        "cell": cell,
        "n": n,
        "call_count": {"mean": _mean(cc), "min": min(cc), "max": max(cc), "values": cc},
        "rederivation": {"mean": _mean(rd), "values": rd},
        "measurement_read": {"mean": _mean(mr), "values": mr},
        "authority_read": {"mean": _mean(ar), "values": ar},
        "complementary": {"mean": _mean(cp), "values": cp},
        "nameerrors": {"sum": sum(ne), "values": ne},
        "categorical": dict(Counter(cats)),
        "cites_measurement_rate": round(sum(1 for r in replicates if r["response_hints"].get("cites_measurement")) / n, 3),
        "flags_invalid_rate": round(sum(1 for r in replicates if r["response_hints"].get("flags_measurement_invalid")) / n, 3),
        "treats_authoritative_rate": round(sum(1 for r in replicates if r["response_hints"].get("treats_as_authoritative")) / n, 3),
        "correct_rate": round(sum(1 for r in replicates if r["categorical"] != "other") / n, 3),
        "claims_measurement_says_risk_any": any(r["response_hints"].get("claims_measurement_says_risk") for r in replicates),
        "interpretation_with_llm_all": all(r["response_hints"].get("interpretation_with_llm") for r in replicates),
    }


def _build_comparison(by_cell: dict) -> dict:
    comp = {}
    for cell in CELLS:
        comp[cell] = _aggregate_cell(cell, by_cell.get(cell, []))
    # Across-authority contrasts on fleet A (the discriminant).
    a = comp
    comp["_contrasts"] = {
        "status_axis_A-established_vs_A-candidate": {
            "rederivation_mean": [a["A-established"]["rederivation"]["mean"], a["A-candidate"]["rederivation"]["mean"]],
            "cites_rate": [a["A-established"]["cites_measurement_rate"], a["A-candidate"]["cites_measurement_rate"]],
            "note": "same numbers, only status (established vs candidate) differs",
        },
        "integrity_axis_A-established_vs_A-invalid": {
            "rederivation_mean": [a["A-established"]["rederivation"]["mean"], a["A-invalid"]["rederivation"]["mean"]],
            "flags_invalid_rate": [a["A-established"]["flags_invalid_rate"], a["A-invalid"]["flags_invalid_rate"]],
            "treats_authoritative_rate": [a["A-established"]["treats_authoritative_rate"], a["A-invalid"]["treats_authoritative_rate"]],
            "note": "same status (established), only integrity (valid vs invalid) differs -- the strongest discriminant",
        },
        "mirror_D-established": {
            "invents_false_concentration_any": any(r["response_hints"].get("invents_false_concentration") for r in by_cell.get("D-established", [])),
            "claims_meas_risk_any": a["D-established"]["claims_measurement_says_risk_any"],
            "note": "established != must-surface-risk; an established+valid measurement of 'no concentration' must not invent one",
        },
    }
    return comp


def _comparison_md(comp: dict) -> str:
    lines = []
    lines.append("# S10 -- comparison: measurement authority (established / candidate / invalid)\n")
    lines.append(
        "The S9 capability-aware method is held CONSTANT across all cells. The ONLY "
        "variable is the `authority` block on the measurement envelope (status x "
        "integrity; integrity computed mechanically via source_snapshot_hash). N "
        "replicates per cell. Categorical outcome per run differs by authority state: "
        "established -> `read` (consume) / `rederive+cite` / `rederive`; candidate -> "
        "`verify` (rederive, correct -- not penalized) / `read`; invalid -> `reject` "
        "(rederives AND flags the mismatch) / `trust_invalid` (trusts 60/70 despite "
        "integrity=invalid).\n")
    labels = {
        "A-established": "fleet A, authority{established, valid} -- consume",
        "A-candidate": "fleet A, authority{candidate, unverified} -- verify is reasonable",
        "A-invalid": "fleet A, authority{established, invalid} -- reject / recompute",
        "D-established": "fleet D, authority{established, valid} -- mirror: established != risk",
    }
    for cell in CELLS:
        agg = comp[cell]
        lines.append(f"\n## {cell} -- {labels[cell]}\n")
        n = agg.get("n", 0)
        if n == 0:
            lines.append("- (no replicates)\n")
            continue
        lines.append(
            f"- n={n}: calls mean={agg['call_count']['mean']} "
            f"(min {agg['call_count']['min']}/max {agg['call_count']['max']}), "
            f"rederive mean={agg['rederivation']['mean']}, "
            f"measurement_read mean={agg['measurement_read']['mean']}, "
            f"authority_read mean={agg['authority_read']['mean']}, "
            f"complement mean={agg['complementary']['mean']}, "
            f"nameerrors sum={agg['nameerrors']['sum']}, "
            f"cites_meas={agg['cites_measurement_rate']}, "
            f"flags_invalid={agg['flags_invalid_rate']}, "
            f"treats_authoritative={agg['treats_authoritative_rate']}, "
            f"correct={agg['correct_rate']}, "
            f"claims_meas_risk_any={agg['claims_measurement_says_risk_any']}, "
            f"interp_llm_all={agg['interpretation_with_llm_all']}, "
            f"outcomes={agg['categorical']}\n"
        )
    cx = comp["_contrasts"]
    lines.append("\n## Across-authority contrasts (fleet A)\n")
    lines.append(
        f"- **status axis** (A-established vs A-candidate; same numbers, only status differs): "
        f"rederive mean {cx['status_axis_A-established_vs_A-candidate']['rederivation_mean']}, "
        f"cites {cx['status_axis_A-established_vs_A-candidate']['cites_rate']}\n")
    lines.append(
        f"- **integrity axis** (A-established vs A-invalid; same status, only integrity differs -- the discriminant): "
        f"rederive mean {cx['integrity_axis_A-established_vs_A-invalid']['rederivation_mean']}, "
        f"flags_invalid {cx['integrity_axis_A-established_vs_A-invalid']['flags_invalid_rate']}, "
        f"treats_authoritative {cx['integrity_axis_A-established_vs_A-invalid']['treats_authoritative_rate']}\n")
    lines.append(
        f"- **mirror** (D-established): invents_false_concentration_any="
        f"{cx['mirror_D-established']['invents_false_concentration_any']}, "
        f"claims_meas_risk_any={cx['mirror_D-established']['claims_meas_risk_any']} "
        f"(both must be False -- established != true)\n")
    return "".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def _parse_args(argv: list[str]) -> dict:
    args = {"cell": None, "replicates": 8, "resume": False, "raw": False}
    for a in argv[1:]:
        if a == "--raw":
            args["raw"] = True
        elif a == "--resume":
            args["resume"] = True
        elif a.startswith("--replicates="):
            args["replicates"] = int(a.split("=", 1)[1])
        elif a.startswith("--cell="):
            args["cell"] = a.split("=", 1)[1]
    return args


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    N = args["replicates"]
    RESULTS.mkdir(parents=True, exist_ok=True)

    print("=== S10 CANARIES (no model call) ===")
    fleets = _load_fleets()
    canary = _run_canaries(fleets)
    (RESULTS / "canary.json").write_text(
        json.dumps(canary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not canary["canaries_ok"]:
        print("CANARY FAILED:")
        print(json.dumps({k: v for k, v in canary.items() if k != "canaries_ok"}, indent=2))
        return 1
    print("  harness self-test: ok")
    print("  concentration self-test: ok")
    print(f"  concentration.py LF-hash={canary['concentration_py_normalized_hash']} "
          f"frozen={FROZEN_CONCENTRATION_HASH} unchanged={canary['concentration_py_unchanged']}")
    print(f"  contract no-interpretation: {canary['contract_no_interpretation_word']}")
    print(f"  authority blocks no-interpretation: {canary['authority_blocks_no_interpretation_word']}")
    print(f"  notes no-interpretation: {canary['notes_no_interpretation_word']}")
    print(f"  envelope no-interpretation (per cell): {canary['envelope_no_interpretation_word']}")
    mi = canary["mechanical_integrity"]
    print(f"  mechanical integrity: established_valid={mi['established_integrity_valid']} "
          f"candidate_unverified={mi['candidate_integrity_unverified']} "
          f"invalid_detected={mi['invalid_integrity_invalid']} reason={mi['invalid_reason_present']} "
          f"(A actual={mi['A_actual_hash']}, invalid recorded={mi['invalid_recorded_hash']})")
    print(f"  measure pure (snapshot unchanged by attachment): {canary['measure_pure_snapshot_unchanged']}")
    print(f"  method = S9 candidate (one-field transform): only_statement_changed="
          f"{canary['candidate_method1_only_statement_changed']}")
    print(f"  S5 seed LF-hashes recorded (asserted unchanged post-run)")

    cells = [args["cell"]] if args["cell"] else list(CELLS)
    for cell in cells:
        if cell not in CELLS:
            sys.stderr.write(f"unknown cell {cell}; choose from {CELLS}\n")
            return 1

    print()
    print("=" * 70)
    print(f"=== S10 RUNS ({len(cells)} cells x {N} replicates, interleaved, "
          f"{'resume' if args['resume'] else 'fresh'}) ===")
    print("=" * 70)

    fleet_snaps = {f: fleets[f]["snapshot"] for f in FLEETS}
    by_cell: dict[str, list[dict]] = {c: [] for c in CELLS}

    for r in range(1, N + 1):
        for cell in cells:
            fleet_key, _ = _cell_parts(cell)
            if args["resume"] and _is_complete(cell, r):
                d = json.loads((RESULTS / cell / f"{r:02d}" / "run.json").read_text(encoding="utf-8"))
                by_cell[cell].append(d)
                print(f"-- [{cell}] rep {r:02d} (cached) outcome={d.get('categorical')} "
                      f"calls={d.get('python_call_count')}")
                continue
            print(f"-- [{cell}] rep {r:02d} running ...", flush=True)
            try:
                session = _run_cell(cell, r, fleet_snaps[fleet_key])
                _save_run(session, cell, r)
                by_cell[cell].append(session)
                _print_summary(session)
            except Exception as e:
                tb = traceback.format_exc(limit=6)
                sys.stderr.write(f"-- [{cell}] rep {r:02d} FAILED: {e}\n{tb}\n")
                err = {
                    "failed": True, "error": str(e), "cell": cell, "replicate": r,
                    "fleet": _cell_parts(cell)[0], "traceback": tb, "at": _stamp(),
                }
                d = RESULTS / cell / f"{r:02d}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "run.json").write_text(
                    json.dumps(err, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                # do not append to by_cell (it will be re-run on resume)

    print()
    print("=" * 70)
    print("=== S10 POST-RUN FLOOR CANARY ===")
    post = _post_run_floor_canary(canary)
    print(f"  floor unchanged: {post['floor_unchanged']}")
    print(f"  S5 seed unchanged: {post['seed_unchanged']}")
    print(f"  concentration.py unchanged after all runs: {post['concentration_py_unchanged_after']}")

    print()
    print("=" * 70)
    print("=== S10 AGGREGATION ===")
    comp = _build_comparison(by_cell)
    (RESULTS / "comparison.json").write_text(
        json.dumps(comp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / "comparison.md").write_text(_comparison_md(comp), encoding="utf-8")
    print(_comparison_md(comp))

    summary = {
        "run_id": _stamp(),
        "model": core.MODEL,
        "options": OPTIONS,
        "max_turns": MAX_TURNS,
        "replicates_per_cell": N,
        "cells": cells,
        "canary": canary,
        "post_run_floor_canary": post,
        "comparison": comp,
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args["raw"]:
        print("\n" + "=" * 70)
        print("=== RAW FINAL RESPONSES ===")
        for cell in cells:
            for r in by_cell.get(cell, []):
                print(f"\n##### [{cell}] rep {r.get('replicate'):02d} outcome={r.get('categorical')} #####")
                print(r.get("final_response") or "(none)")

    print("\n=== S10 COMPLETE ===")
    print(f"  results: {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))