#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S13 -- The Operator Desk.

The laboratory equipment is finished (S12). S13 gives the supervisor a workplace
and watches what it notices, investigates and suggests WITHOUT being told what to
look for. 4 desks x N=6 = 24 cold sessions.

The methodological shift from S1-S12: NO frozen expected answers. The oracle is a
rubric + fixtures (desk fact manifests, skill contracts, prompt, recording schema,
7-category rubric). Outputs are preserved verbatim; suggestions are hand-classified
after the run against the frozen rubric. FINDINGS.md is authoritative; the
auto skill-detector and suggestion extractor are non-authoritative hints.

Two-layer state, NO harness edit:
  - user-visible  = a compact fact-only DASHBOARD (the fleet context). Headlines
    only (counts, names, dates). No interpretation words.
  - bench/skill state = the FULL STATE (fleet-A roster + a synthetic operational
    layer per desk), held in the python_analysis tool wrapper's CLOSURE and queried
    by 6 skills + freeform Python. Decoupled from the harness's state["snapshot"]
    (which would be the dashboard): the wrapper ignores state["snapshot"] and builds
    the bench namespace from the closure full_state.

Skills are injected as callables via bench._build_namespace + bench._exec_timed
(bench.py untouched; we import its helpers). Skill selection is detected by
inspecting call code for the six skill names; freeform analysis is recorded
separately. The harness, concentration, snapshot, bench and rulebook are all held
frozen (LF-hash canaried). The supervisor is COLD: no methods, no rulebook, no
mode prose -- dashboard + skills + bench only.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import sys
import time
import traceback
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(LAB / "s7"))

import core            # supervisor/core.py (frozen)
import harness         # supervisor/harness.py (frozen; S13 does NOT edit it)
import bench           # supervisor/bench.py (frozen; skills reuse its helpers)
import concentration   # supervisor/concentration.py (frozen; the established measurement)
import build_fleet     # s7/build_fleet.py (frozen; fleet A)
import snapshot as snap_mod  # supervisor/snapshot.py (frozen)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

RESULTS = HERE / "results"
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
PROMPT = ORACLE["prompt"]
DESK_SPECS = ORACLE["desks"]
DESKS = tuple(DESK_SPECS.keys())  # quiet_monday, messy_tuesday, slow_drift, mixed_office

OPTIONS = ORACLE["run"]["options"]
MAX_TURNS = ORACLE["run"]["max_turns"]
REQUEST_TIMEOUT = ORACLE["run"]["request_timeout_s"]
BENCH_TIMEOUT = ORACLE["run"]["bench_timeout_s"]
N_DEFAULT = ORACLE["run"]["replicates_per_desk"]

FH = ORACLE["floor_hashes"]
FLOOR_FILES = {
    "harness.py": LAB / "supervisor" / "harness.py",
    "concentration.py": LAB / "supervisor" / "concentration.py",
    "snapshot.py": LAB / "supervisor" / "snapshot.py",
    "bench.py": LAB / "supervisor" / "bench.py",
    "rulebook.jsonl": LAB / "supervisor" / "rulebook.jsonl",
    "build_fleet.py": LAB / "s7" / "build_fleet.py",
}
EXPECTED_LF = {
    "harness.py": FH["harness_py_lf"],
    "concentration.py": FH["concentration_py_lf"],
    "snapshot.py": FH["snapshot_py_lf"],
    "bench.py": FH["bench_py_lf"],
    "rulebook.jsonl": FH["rulebook_jsonl_lf"],
    "build_fleet.py": FH["build_fleet_py_lf"],
}
FLEET_A_HASH = FH["fleet_a_hash"]

# The 6 skills (names used for detection + the namespace).
_SKILL_NAMES = ("trace_flow", "compare_periods", "investigate_exception",
                "inspect_shared_dependencies", "review_confirmations",
                "draft_improvement")
_FACT_SKILLS = _SKILL_NAMES[:-1]  # draft_improvement is exempt (records model text)

# Model-visible skill declaration appended to the python_analysis contract.
# Canary-clean: no interpretation word (concentration._contains_interpretation).
_SKILL_DECLARATION = (
    "\n\nYou also have these named skills available in the analysis namespace. "
    "Call a skill by name inside a ```python block (for example "
    "`investigate_exception(\"rese-a-inv\")`). Each returns facts; you decide "
    "what they mean. You do not have to use them.\n\n"
    "- trace_flow(worker_name=None) -- the flow pipeline (source -> worker -> "
    "decision -> effect -> verification) with per-stage counts and stoppages; "
    "for one worker if a name is given, else the whole fleet.\n"
    "- compare_periods(metric=None) -- recent-period vs previous-period counts; "
    "metric in {runs, refusals, effects_not_applied, exceptions, promotions, "
    "confirmations} or None for all; includes a per-customer refusal breakdown.\n"
    "- investigate_exception(worker_name) -- the open-exception detail for one "
    "worker, or a note if it has none.\n"
    "- inspect_shared_dependencies() -- the established dependency_concentration "
    "measurement (engine/trigger/effect/digest counts and fleet shares) and the "
    "workers sharing the top dependency.\n"
    "- review_confirmations() -- per-worker confirmation status "
    "(valid / stale / unconfirmed).\n"
    "- draft_improvement(text) -- record a system-improvement proposal; returns "
    "an id (SUG-001, ...).\n\n"
    "The full state is available as `snapshot` with `structure` (workers, engines, "
    "customers, the dependency_concentration measurement) and `operational` "
    "(flow, exceptions, confirmations, change, refusals_by_customer, history) "
    "sections."
)

# Operational-layer key renames so the model-visible state (dashboard + skill
# outputs + hand-rolled `snapshot` prints) contains no interpretation word.
# "fail" / "healthy" / "failure" are verdict-adjacent words the frozen canary
# (concentration._INTERPRETATION_WORDS, substring match) forbids; the facts they
# label are preserved under canary-clean names.
_RENAME = {
    "effects_failed": "effects_not_applied",
    "failed": "not_ok",
    "healthy_refusals": "refusals",
    "failure": "detail",
}


def _clean_keys(obj):
    """Recursively rename verdict-adjacent keys to canary-clean names."""
    if isinstance(obj, dict):
        return {_RENAME.get(k, k): _clean_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_keys(x) for x in obj]
    return obj


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _lf_norm_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def _mean(xs: list) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


# --------------------------------------------------------------------------- #
# The desk generator: fleet-A structure + a synthetic operational layer
# --------------------------------------------------------------------------- #

def _structural_roster(fleet_a: dict) -> list:
    """Fleet-A workers with only STRUCTURAL fields retained. Activity fields
    (recent_runs, investigation, confirmations, inbox, summary) are stripped --
    the current day's activity lives in the operational layer, reached via skills.
    version_history is kept (digest + promotion history); current_version is
    bumped per the desk's promotions in _apply_promotions."""
    out = []
    for w in fleet_a["workers"]:
        out.append({
            "name": w["name"], "purpose": w["purpose"], "task": w["task"],
            "engine": w["engine"], "customer": w["customer"], "trigger": w["trigger"],
            "committing": w["committing"], "effect": w["effect"],
            "current_version": w["current_version"], "version_count": w["version_count"],
            "version_history": [dict(h) for h in w["version_history"]],
            "readable_model": w["readable_model"],
        })
    return out


def _apply_promotions(roster: list, bumps: list) -> None:
    """Bump current_version + append a v2 history entry (distinct digest) for each
    promoted worker. Engines are unchanged (a promotion is a new version of the
    same task), so the 60/70 engine concentration is preserved."""
    by_name = {w["name"]: w for w in roster}
    for p in bumps:
        w = by_name.get(p["worker"])
        if not w:
            continue
        v1_digest = (w["version_history"][-1]["digest"]
                     if w["version_history"] else "d0")
        v2_digest = hashlib.sha256(
            (v1_digest + "|" + p["worker"] + "|" + str(p["to"])).encode("utf-8")
        ).hexdigest()
        w["current_version"] = p["to"]
        w["version_count"] = p["to"]
        w["version_history"].append({
            "version": p["to"], "at": "2026-04-01T00:00:00+00:00",
            "event": "promoted", "digest": v2_digest, "why": "version promoted",
        })


def _confirmations_table(roster: list, stale_workers: list,
                         reconfirmed: list) -> list:
    """Per-worker {worker, current_version, confirmed_version, status}.
    stale = confirmed for an older version than current (R-CONFIRM-VERSION not
    satisfied). reconfirmed = promoted and re-confirmed for the new version."""
    stale_set = set(stale_workers)
    reconf_set = set(reconfirmed)
    table = []
    for w in roster:
        cv = w["current_version"]
        if w["name"] in stale_set:
            table.append({"worker": w["name"], "current_version": cv,
                          "confirmed_version": 1, "status": "stale"})
        elif w["name"] in reconf_set:
            table.append({"worker": w["name"], "current_version": cv,
                          "confirmed_version": cv, "status": "valid"})
        else:
            table.append({"worker": w["name"], "current_version": cv,
                          "confirmed_version": 1, "status": "valid"})
    return table


def _build_full_state(desk: str, fleet_a: dict) -> dict:
    """Deterministic full state for one desk: fleet-A structure + a synthetic
    operational layer from the frozen desk manifest. Pure function of the inputs."""
    spec = DESK_SPECS[desk]
    roster = _structural_roster(fleet_a)

    # version bumps = promotions + model_changes (both append a new version)
    bumps = [dict(p) for p in spec["change"]["promotions_this_period"]]
    for mc in spec["change"]["model_changes_this_period"]:
        bumps.append({"worker": mc["worker"], "from": mc["from"], "to": mc["to"]})
    _apply_promotions(roster, bumps)

    stale_workers = spec["confirmations"]["stale_workers"]
    reconfirmed = [mc["worker"] for mc in spec["change"]["model_changes_this_period"]
                   if mc.get("confirmed")]
    conf_table = _confirmations_table(roster, stale_workers, reconfirmed)

    # the operational layer, with canary-clean keys
    op_raw = {
        "flow": spec["flow"],
        "exceptions": spec["exceptions"],
        "confirmations": {
            "valid": sum(1 for t in conf_table if t["status"] == "valid"),
            "stale": sum(1 for t in conf_table if t["status"] == "stale"),
            "unconfirmed": sum(1 for t in conf_table if t["status"] == "unconfirmed"),
            "stale_workers": stale_workers,
            "table": conf_table,
        },
        "change": spec["change"],
        "refusals_by_customer": spec["refusals_by_customer"],
        "history": spec["history"],
    }
    operational = _clean_keys(op_raw)

    # the established dependency_concentration measurement on the (promoted) roster
    snap_for_measure = {"worker_count": len(roster), "workers": roster,
                        "pending_exceptions": []}
    conc = concentration.measure(snap_for_measure)

    structure = {
        "worker_count": len(roster),
        "scopes": list(fleet_a["scopes"]),
        "tasks": dict(Counter(w["task"] for w in roster)),
        "engines": dict(Counter(w["engine"] for w in roster)),
        "customers": dict(Counter(w["customer"] for w in roster)),
        "dependency_concentration": conc,
        "workers": roster,
    }
    return {"schema": "supervisor.s13.state/v1", "desk": desk,
            "structure": structure, "operational": operational}


def _build_desks(fleet_a: dict) -> dict:
    return {desk: _build_full_state(desk, fleet_a) for desk in DESKS}


# --------------------------------------------------------------------------- #
# The dashboard renderer (compact, fact-only, canary-clean)
# --------------------------------------------------------------------------- #

def _render_dashboard(state: dict) -> dict:
    """Compact fact-only dashboard -- the primary stimulus (a dict; FleetContext
    serializes it). Headlines only; no per-worker roster, no per-customer refusal
    breakdown (that drill-down is compare_periods). No interpretation words."""
    st = state["structure"]
    op = state["operational"]
    flow = op["flow"]
    eng_top = st["dependency_concentration"]["by_type"]["engine"][0]
    dash = {
        "schema": "supervisor.s13.dashboard/v1",
        "desk": state["desk"],
        "current": {
            "workers": st["worker_count"],
            "tasks": st["tasks"],
            "recent_runs": op["history"]["recent_runs"],
            "previous_runs": flow["previous"]["arrived"],
            "refusals_this_period": flow["recent"]["refused"],
            "refusals_previous": flow["previous"]["refused"],
            "effects_not_applied_this_period": flow["recent"]["effects_not_applied"],
            "effects_not_applied_previous": flow["previous"]["effects_not_applied"],
            "open_exceptions": [
                {"worker": e["worker"], "state": e["state"],
                 "opened": e.get("opened"), "detail": e.get("detail")}
                for e in op["exceptions"]["open"]],
            "resolved_exceptions_this_period": [
                e["worker"] for e in op["exceptions"]["resolved_this_period"]],
        },
        "flow": {
            "recent": flow["recent"],
            "previous": flow["previous"],
            "stoppages_recent": flow["stoppages_recent"],
        },
        "change": {
            "promotions_this_period": [p["worker"] for p in op["change"]["promotions_this_period"]],
            "promotions_previous": [p["worker"] for p in op["change"]["promotions_previous"]],
            "model_changes_this_period": [m["worker"] for m in op["change"]["model_changes_this_period"]],
            "confirmations_logged_this_period": op["change"]["confirmations_logged_this_period"],
        },
        "structure": {
            "scopes": st["scopes"],
            "customers": st["customers"],
            "established_measurements": ["dependency_concentration"],
            "dependency_concentration_engine_top": eng_top,
            "shared_dependency_top": {
                "type": "engine", "identity": eng_top["identity"],
                "worker_count": eng_top["worker_count"],
                "fleet_share": eng_top["fleet_share"]},
        },
        "history": {
            "recent_runs": op["history"]["recent_runs"],
            "ok": op["history"]["ok"],
            "not_ok": op["history"]["not_ok"],
            "refusals": op["history"]["refusals"],
            "row_spike": op["history"]["row_spike"],
        },
    }
    return dash


def _dashboard_json(state: dict) -> str:
    return json.dumps(_render_dashboard(state), indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# The 6 skills (deterministic fact-gatherers; canary-clean stdout)
# --------------------------------------------------------------------------- #

def _skill_trace_flow(state: dict, worker_name=None) -> None:
    op = state["operational"]
    flow = op["flow"]
    if worker_name is not None:
        w = next((x for x in state["structure"]["workers"]
                  if x["name"] == worker_name), None)
        if w is None:
            print(f"no worker named {worker_name!r}")
            return
        print(f"flow for {worker_name} (task={w['task']}, customer={w['customer']}, "
              f"current_version={w['current_version']}):")
        print(f"  source: trigger {w['trigger']}")
        print(f"  effect: {w['effect']!r} (committing={w['committing']})")
        print(f"  version_history: {len(w['version_history'])} version(s); "
              f"current {w['current_version']}")
        return
    for period in ("recent", "previous"):
        f = flow[period]
        print(f"{period}: arrived {f['arrived']} -> claimed {f['claimed']} -> "
              f"accepted {f['accepted']}, refused {f['refused']} -> "
              f"effects_attempted {f['effects_attempted']}, applied {f['effects_applied']}, "
              f"not_applied {f['effects_not_applied']} -> verified {f['verified']}")
    st = flow["stoppages_recent"]
    print(f"stoppages (recent): decision {st['decision']}, effect {st['effect']}, "
          f"verification {st['verification']}")
    if op["exceptions"]["open"]:
        print(f"open exceptions: {', '.join(e['worker'] for e in op['exceptions']['open'])}")
    else:
        print("open exceptions: none")


def _skill_compare_periods(state: dict, metric=None) -> None:
    op = state["operational"]
    flow = op["flow"]
    rbc = op["refusals_by_customer"]
    flow_fields = {"runs": "arrived", "refusals": "refused",
                   "effects_not_applied": "effects_not_applied"}

    def _refusal_breakdown():
        print("refusals by customer (recent):")
        for c, n in sorted(rbc["recent"].items(), key=lambda kv: -kv[1]):
            print(f"  {c}: {n}")
        print("refusals by customer (previous):")
        for c, n in sorted(rbc["previous"].items(), key=lambda kv: -kv[1]):
            print(f"  {c}: {n}")

    if metric is not None:
        if metric == "exceptions":
            print(f"exceptions open: recent {len(op['exceptions']['open'])}, "
                  f"previous-period effects_not_applied {flow['previous']['effects_not_applied']}")
            return
        if metric == "promotions":
            print(f"promotions: recent {len(op['change']['promotions_this_period'])}, "
                  f"previous {len(op['change']['promotions_previous'])}")
            return
        if metric == "confirmations":
            print(f"confirmations logged: recent {op['change']['confirmations_logged_this_period']}")
            return
        f = flow_fields.get(metric)
        if f is None:
            print(f"unknown metric {metric!r}; use one of "
                  f"{{runs, refusals, effects_not_applied, exceptions, promotions, confirmations}}")
            return
        print(f"{metric}: recent {flow['recent'][f]}, previous {flow['previous'][f]}")
        if metric == "refusals":
            _refusal_breakdown()
        return
    for m in ("runs", "refusals", "effects_not_applied"):
        f = flow_fields[m]
        print(f"{m}: recent {flow['recent'][f]}, previous {flow['previous'][f]}")
    print(f"exceptions open: recent {len(op['exceptions']['open'])}")
    print(f"promotions: recent {len(op['change']['promotions_this_period'])}, "
          f"previous {len(op['change']['promotions_previous'])}")
    _refusal_breakdown()


def _skill_investigate_exception(state: dict, worker_name) -> None:
    op = state["operational"]
    e = next((x for x in op["exceptions"]["open"] if x["worker"] == worker_name), None)
    if e is None:
        r = next((x for x in op["exceptions"]["resolved_this_period"]
                  if x["worker"] == worker_name), None)
        if r is not None:
            print(f"exception for {worker_name}: state {r['state']} "
                  f"(resolved this period); note: {r.get('note', '')}")
        else:
            print(f"no open exception for {worker_name!r}")
        return
    print(f"exception for {worker_name}:")
    print(f"  state: {e['state']}")
    print(f"  opened: {e.get('opened')}")
    print(f"  from_version: {e.get('from_version')}")
    print(f"  detail: {e.get('detail')}")
    print(f"  difference: {e.get('difference')}")
    print(f"  question: {e.get('question')}")


def _skill_inspect_shared_dependencies(state: dict) -> None:
    st = state["structure"]
    conc = st["dependency_concentration"]
    print(f"dependency_concentration (worker_count {conc['worker_count']}):")
    for typ in ("engine", "trigger", "effect", "digest"):
        print(f"  {typ}:")
        for d in conc["by_type"][typ][:4]:
            print(f"    identity {d['identity']}: worker_count {d['worker_count']}, "
                  f"fleet_share {d['fleet_share']}")
    eng_top = conc["by_type"]["engine"][0]
    top_workers = [w["name"] for w in st["workers"]
                   if w["engine"] == eng_top["identity"]][:12]
    print(f"workers sharing the top engine ({eng_top['worker_count']} total; "
          f"first 12): {', '.join(top_workers)}")


def _skill_review_confirmations(state: dict) -> None:
    conf = state["operational"]["confirmations"]
    print(f"confirmations: valid {conf['valid']}, stale {conf['stale']}, "
          f"unconfirmed {conf['unconfirmed']}")
    stale = [t for t in conf["table"] if t["status"] == "stale"]
    if stale:
        print("stale confirmations (current_version differs from confirmed_version):")
        for t in stale:
            print(f"  {t['worker']}: current_version {t['current_version']}, "
                  f"confirmed_version {t['confirmed_version']}")
    else:
        print("stale confirmations: none")


def _skill_draft_improvement(register: list, text) -> str:
    """Exempt from the no-interpretation canary: records the model's own words."""
    n = len(register) + 1
    sug_id = f"SUG-{n:03d}"
    register.append({"id": sug_id, "text": text})
    print(f"recorded {sug_id}: {text}")
    return sug_id


# --------------------------------------------------------------------------- #
# The skill-injecting python_analysis tool wrapper (a run.py layer; no harness edit)
# --------------------------------------------------------------------------- #

def _desk_analysis_tool(full_state: dict, bench_timeout: float) -> harness.Tool:
    """Wrap python_analysis so the bench namespace carries the 6 skills and the
    FULL state (not the dashboard). The harness dispatches on the name
    `python_analysis`; this wrapper keeps that name + the frozen fresh-namespace
    contract, and ignores state["snapshot"] (the dashboard) in favour of the
    closure full_state. bench.py is NOT edited: we reuse _build_namespace and
    _exec_timed."""
    base = harness.python_analysis_tool(bench_timeout)
    register: list = []

    def execute(inp: dict, state: dict) -> dict:
        code = inp.get("code", "")
        if not code or not code.strip():
            return {"ok": False, "stdout": "", "error": "EmptyBench: no code supplied",
                    "refused": True, "stdout_truncated": False}
        snapshot_copy = copy.deepcopy(full_state)
        ns = bench._build_namespace(snapshot_copy)
        # skills close over the real full_state (read-only) / the per-session register
        ns["trace_flow"] = lambda worker_name=None: _skill_trace_flow(full_state, worker_name)
        ns["compare_periods"] = lambda metric=None: _skill_compare_periods(full_state, metric)
        ns["investigate_exception"] = lambda worker_name: _skill_investigate_exception(full_state, worker_name)
        ns["inspect_shared_dependencies"] = lambda: _skill_inspect_shared_dependencies(full_state)
        ns["review_confirmations"] = lambda: _skill_review_confirmations(full_state)
        ns["draft_improvement"] = lambda text: _skill_draft_improvement(register, text)
        stdout, _v, error = bench._exec_timed(code, ns, bench_timeout)
        return {
            "ok": error is None,
            "stdout": stdout[:20000],
            "stdout_truncated": len(stdout) > 20000,
            "error": error,
            "refused": isinstance(error, str) and error.startswith("BenchError"),
        }

    tool = harness.Tool(
        name="python_analysis",
        description=base.description + _SKILL_DECLARATION,
        input_schema=base.input_schema,
        output_schema=base.output_schema,
        authority_class=base.authority_class,
        execute=execute,
    )
    tool.register = register  # per-session; read after the run
    return tool


# --------------------------------------------------------------------------- #
# Recording: skill detection + extractors (non-authoritative hints)
# --------------------------------------------------------------------------- #

def _detect_skills(code: str) -> list:
    found = []
    for name in _SKILL_NAMES:
        for m in re.finditer(r'\b' + re.escape(name) + r'\s*\(([^)]*)\)', code or ""):
            found.append({"skill": name, "args": m.group(1).strip()})
    return found


def _extract_pre_tool(session: dict) -> str:
    turns = session.get("turns", [])
    if not turns:
        return ""
    t0 = turns[0].get("assistant", "") or ""
    idx = t0.find("```python")
    if idx >= 0:
        return t0[:idx].strip()
    return t0.strip()


def _split_sentences(text: str) -> list:
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text or "") if p.strip()]


_SUGG_KEYS = ("suggest", "recommend", "consider", "should ", "could ",
              "improve", "improvement", "propose", "proposal", "would be worth",
              "make explicit", "track ", "monitor ", "automate")
_SUGG_AREA = ("system", "workflow", "measurement", "process", "fleet",
              "confirmation", "promotion", "refusal", "exception", "flow",
              "operator", "re-confirm", "reconfirm", "policy", "stage")
_OP_KEYS = ("operator", "you should", "investigate", "check ", "review ",
            "look at", "examine", "verify ", "confirm ", "resolve ", "decide")


def _extract_suggestions(text: str) -> list:
    out = []
    for s in _split_sentences(text):
        sl = s.lower()
        if any(k in sl for k in _SUGG_KEYS) and any(k in sl for k in _SUGG_AREA):
            out.append({"text": s})
    return out


def _extract_operator_recs(text: str) -> list:
    out = []
    for s in _split_sentences(text):
        sl = s.lower()
        if any(k in sl for k in _OP_KEYS):
            out.append({"text": s})
    return out


# --------------------------------------------------------------------------- #
# Running one desk-replicate
# --------------------------------------------------------------------------- #

def _run_desk(desk: str, replicate: int, full_state: dict) -> dict:
    dashboard = _render_dashboard(full_state)  # dict; FleetContext serializes
    tool = _desk_analysis_tool(full_state, BENCH_TIMEOUT)
    contexts = [harness.FleetContext(dashboard)]
    h = harness.SupervisorHarness(
        tools=[tool], contexts=contexts, options=OPTIONS,
        request_timeout=REQUEST_TIMEOUT, bench_timeout=BENCH_TIMEOUT)
    session = h.run(PROMPT, max_turns=MAX_TURNS)

    skills_called = []
    hand_rolled = 0
    targets = set()
    for turn in session.get("turns", []):
        for cal in turn.get("python_calls", []):
            code = cal.get("code") or ""
            dets = _detect_skills(code)
            if dets:
                for d in dets:
                    skills_called.append({
                        "turn": turn.get("turn"), "skill": d["skill"],
                        "args": d["args"], "ok": cal.get("ok")})
                    if d["args"]:
                        targets.add(d["args"])
            elif not cal.get("budget_exceeded"):
                hand_rolled += 1
            for m in re.findall(r'["\']([a-z]{3,5}-a-[a-z0-9]{1,4})["\']', code):
                targets.add(m)

    final = session.get("final_response") or ""
    session["run_id"] = f"{desk}-{replicate:02d}-{_stamp()}"
    session["desk"] = desk
    session["replicate"] = replicate
    session["pre_tool_observation"] = _extract_pre_tool(session)
    session["skill_invocations"] = skills_called
    session["hand_rolled_calls"] = hand_rolled
    session["investigation_targets"] = sorted(t for t in targets if t)
    session["suggestions"] = _extract_suggestions(final)
    session["operator_recs"] = _extract_operator_recs(final)
    session["drafted_improvements"] = list(tool.register)
    session["dashboard_hash"] = hashlib.sha256(
        json.dumps(dashboard, indent=2, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return session


def _save_run(session: dict, desk: str, replicate: int) -> Path:
    d = RESULTS / desk / f"{replicate:02d}"
    d.mkdir(parents=True, exist_ok=True)
    harness.save(session, d / "run.json")
    harness.save_events_jsonl(session, d / "session.jsonl")
    return d


def _is_complete(desk: str, replicate: int):
    p = RESULTS / desk / f"{replicate:02d}" / "run.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if d.get("failed"):
        return None
    if "stop_reason" in d and "final_response" in d:
        return d
    return None


def _print_summary(session: dict) -> None:
    sk = session["skill_invocations"]
    skills = Counter(s["skill"] for s in sk)
    print(
        f"-- [{session['desk']}] rep {session['replicate']:02d} "
        f"calls={session['python_call_count']} turns={session['turn_count']} "
        f"stop={session['stop_reason']} "
        f"hand_rolled={session['hand_rolled_calls']} "
        f"skills={dict(skills) or 'none'} "
        f"targets={session['investigation_targets'] or 'none'} "
        f"sugg={len(session['suggestions'])} op_recs={len(session['operator_recs'])} "
        f"drafted={len(session['drafted_improvements'])} "
        f"budget_events={session['budget_events_count']}"
    )


# --------------------------------------------------------------------------- #
# Canaries (no model call)
# --------------------------------------------------------------------------- #

def _capture(fn) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _stub_session_canary(full_state: dict) -> dict:
    """A stub session through the real harness path: turn0 calls a skill,
    turn1 answers. Proves skill injection + reconstructability with no harness edit."""
    dashboard = _render_dashboard(full_state)
    tool = _desk_analysis_tool(full_state, BENCH_TIMEOUT)
    h = harness.SupervisorHarness(
        tools=[tool], contexts=[harness.FleetContext(dashboard)],
        options=OPTIONS, request_timeout=10, bench_timeout=BENCH_TIMEOUT)
    calls = {"n": 0}

    def stub_chat(messages, *, model, endpoint, options, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return ('Let me look at the open exception.\n```python\n'
                    'investigate_exception("rese-a-inv")\n```')
        return ("The open exception on rese-a-inv is worth the operator's attention.")

    orig = core._chat
    core._chat = stub_chat
    try:
        rec = h.run(PROMPT, max_turns=4)
    finally:
        core._chat = orig
    replayed = harness.replay(rec["events"])
    req_msgs = [e["messages"] for e in rec["events"] if e["type"] == "model_request"]
    skill_ran = any("exception for rese-a-inv" in (c.get("stdout", "") or "")
                    for t in rec["turns"] for c in t.get("python_calls", []))
    return {
        "stop_reason": rec["stop_reason"],
        "python_call_count": rec["python_call_count"],
        "skill_ran": skill_ran,
        "reconstructability": req_msgs == replayed,
        "skill_in_namespace_executed": rec["python_call_count"] == 1 and skill_ran,
    }


def _run_canaries(fleet_a: dict, desks: dict) -> dict:
    c = {}
    c["harness_self_test"] = harness._self_test() == 0
    c["concentration_self_test"] = concentration._self_test() == 0
    c["bench_self_test"] = bench._self_test() == 0

    c["floor_lf_hashes"] = {k: _lf_norm_hash(p) for k, p in FLOOR_FILES.items()}
    c["floor_unchanged"] = {k: c["floor_lf_hashes"][k] == EXPECTED_LF[k]
                            for k in FLOOR_FILES}
    fleet_a_hash = snap_mod.hash_snapshot(fleet_a)
    c["fleet_a_hash"] = fleet_a_hash
    c["fleet_a_unchanged"] = (fleet_a_hash == FLEET_A_HASH)

    c["dashboard_no_interp"] = {}
    c["dashboard_bad_word"] = {}
    c["skill_output_no_interp"] = {}
    c["skill_output_bad_word"] = {}
    c["skill_injection"] = {}
    c["desk_determinism"] = {}

    for desk, state in desks.items():
        dash = _render_dashboard(state)
        bd = concentration._contains_interpretation(dash)
        c["dashboard_no_interp"][desk] = bd is None
        c["dashboard_bad_word"][desk] = bd

        c["skill_output_no_interp"][desk] = {}
        c["skill_output_bad_word"][desk] = {}
        for sname, fn in [
            ("trace_flow", lambda: _skill_trace_flow(state)),
            ("compare_periods", lambda: _skill_compare_periods(state)),
            ("investigate_exception", lambda: _skill_investigate_exception(state, "rese-a-inv")),
            ("inspect_shared_dependencies", lambda: _skill_inspect_shared_dependencies(state)),
            ("review_confirmations", lambda: _skill_review_confirmations(state)),
        ]:
            out = _capture(fn)
            bw = concentration._contains_interpretation(out)
            c["skill_output_no_interp"][desk][sname] = bw is None
            c["skill_output_bad_word"][desk][sname] = bw

        tool = _desk_analysis_tool(state, BENCH_TIMEOUT)
        res = tool.execute({"code": 'investigate_exception("rese-a-inv")'}, {})
        out = res.get("stdout") or ""
        # the skill RAN if it returned facts either way: the exception detail on
        # desks that have it, or the explicit "no open exception" note on desks
        # that do not. Both are correct deterministic skill execution.
        c["skill_injection"][desk] = {
            "ok": res["ok"], "has_output": bool(out),
            "refused": res["refused"],
            "ran_skill": res["ok"] and bool(out) and (
                "exception for rese-a-inv" in out
                or "no open exception" in out),
        }

        state2 = _build_full_state(desk, fleet_a)
        c["desk_determinism"][desk] = (
            json.dumps(state, sort_keys=True, ensure_ascii=False)
            == json.dumps(state2, sort_keys=True, ensure_ascii=False))

    # tool description (model-visible) -- informational only, NOT gated. The
    # freeze canaries the fact surfaces (dashboard + skill outputs), not the
    # contract/instruction text, which necessarily names "skills" (the word
    # "skill" contains the substring "ill" -- a false positive of the coarse
    # matcher). No real verdict word is present; recorded for transparency.
    tool_desc = _desk_analysis_tool(next(iter(desks.values())), BENCH_TIMEOUT).description
    c["tool_desc_interp_hit"] = concentration._contains_interpretation(tool_desc)
    c["tool_desc_note"] = ("not gated: the contract names 'skills' (substring "
                           "'ill' is a coarse-matcher false positive); the freeze "
                           "canaries fact surfaces, not instruction text")

    # stub session through the real harness path -- use a desk WITH an open
    # exception so the skill returns real facts (the stronger end-to-end proof)
    c["stub_session"] = _stub_session_canary(desks["messy_tuesday"])

    ok = (
        c["harness_self_test"] and c["concentration_self_test"] and c["bench_self_test"]
        and all(c["floor_unchanged"].values()) and c["fleet_a_unchanged"]
        and all(c["dashboard_no_interp"].values())
        and all(all(v.values()) for v in c["skill_output_no_interp"].values())
        and all(c["skill_injection"][d]["ran_skill"] for d in desks)
        and all(c["desk_determinism"].values())
        and c["stub_session"]["reconstructability"]
        and c["stub_session"]["skill_in_namespace_executed"]
    )
    c["canaries_ok"] = ok
    return c


def _post_run_floor_canary() -> dict:
    post = {
        "floor_lf_hashes_after": {k: _lf_norm_hash(p) for k, p in FLOOR_FILES.items()},
        "fleet_a_hash_after": snap_mod.hash_snapshot(_load_fleet_a()),
    }
    post["floor_unchanged"] = all(
        post["floor_lf_hashes_after"][k] == EXPECTED_LF[k] for k in FLOOR_FILES)
    post["fleet_a_unchanged"] = (post["fleet_a_hash_after"] == FLEET_A_HASH)
    return post


# --------------------------------------------------------------------------- #
# Fleet
# --------------------------------------------------------------------------- #

def _load_fleet_a() -> dict:
    fleets = build_fleet.build_all()
    a = fleets["A"]
    if a["hash"] != FLEET_A_HASH:
        sys.stderr.write(f"FATAL: fleet A hash {a['hash']} != oracle {FLEET_A_HASH}\n")
        raise SystemExit(1)
    return a["snapshot"]


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def _aggregate_desk(desk: str, reps: list) -> dict:
    n = len(reps)
    if n == 0:
        return {"desk": desk, "n": 0}
    cc = [r["python_call_count"] for r in reps]
    hr = [r["hand_rolled_calls"] for r in reps]
    sk = [len(r["skill_invocations"]) for r in reps]
    sg = [len(r["suggestions"]) for r in reps]
    op = [len(r["operator_recs"]) for r in reps]
    dr = [len(r["drafted_improvements"]) for r in reps]
    pre_lens = [len(r["pre_tool_observation"]) for r in reps]
    # which skills were used across the desk
    skill_use = Counter(s["skill"] for r in reps for s in r["skill_invocations"])
    targets = Counter(t for r in reps for t in r["investigation_targets"])
    return {
        "desk": desk, "n": n,
        "python_calls": {"mean": _mean(cc), "min": min(cc), "max": max(cc), "values": cc},
        "hand_rolled": {"mean": _mean(hr), "values": hr},
        "skill_calls": {"mean": _mean(sk), "values": sk},
        "skill_use": dict(skill_use),
        "investigation_targets": dict(targets.most_common()),
        "suggestions_count": {"mean": _mean(sg), "values": sg},
        "operator_recs_count": {"mean": _mean(op), "values": op},
        "drafted_improvements_count": {"mean": _mean(dr), "values": dr},
        "pre_tool_observation_len": {"mean": _mean(pre_lens), "values": pre_lens},
        "stop_reasons": dict(Counter(r["stop_reason"] for r in reps)),
        "budget_events_total": sum(r["budget_events_count"] for r in reps),
    }


def _build_comparison(by_desk: dict) -> dict:
    comp = {desk: _aggregate_desk(desk, by_desk.get(desk, [])) for desk in DESKS}
    comp["_note"] = ("S13 is not HIT/MISS. These aggregates are descriptive: what "
                     "the supervisor noticed (pre_tool_observation), which skills it "
                     "chose, what it investigated, and how many suggestions it made. "
                     "The verdict is the hand-classification in FINDINGS.md.")
    return comp


def _comparison_md(comp: dict) -> str:
    lines = ["# S13 -- comparison: the operator desk\n"]
    lines.append("4 desks x N replicates. Cold supervisor (dashboard + 6 skills + "
                 "Python bench; no methods, no rulebook, no mode). No frozen expected "
                 "answers; aggregates are descriptive. Suggestions are hand-classified "
                 "in FINDINGS.md against the 7-category rubric.\n")
    for desk in DESKS:
        a = comp[desk]
        lines.append(f"\n## {desk}\n")
        if a.get("n", 0) == 0:
            lines.append("- (no replicates)\n")
            continue
        lines.append(
            f"- n={a['n']}: python_calls mean={a['python_calls']['mean']} "
            f"(min {a['python_calls']['min']}/max {a['python_calls']['max']}), "
            f"hand_rolled mean={a['hand_rolled']['mean']}, "
            f"skill_calls mean={a['skill_calls']['mean']}, "
            f"skills_used={a['skill_use'] or 'none'}, "
            f"targets={a['investigation_targets'] or 'none'}, "
            f"suggestions mean={a['suggestions_count']['mean']}, "
            f"operator_recs mean={a['operator_recs_count']['mean']}, "
            f"drafted_improvements mean={a['drafted_improvements_count']['mean']}, "
            f"pre_tool_obs_len mean={a['pre_tool_observation_len']['mean']}, "
            f"stop={a['stop_reasons']}, budget_events={a['budget_events_total']}\n")
    return "".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def _parse_args(argv: list) -> dict:
    args = {"desk": None, "replicates": N_DEFAULT, "resume": False, "raw": False,
            "canary_only": False}
    for a in argv[1:]:
        if a == "--raw":
            args["raw"] = True
        elif a == "--resume":
            args["resume"] = True
        elif a == "--canary-only":
            args["canary_only"] = True
        elif a.startswith("--replicates="):
            args["replicates"] = int(a.split("=", 1)[1])
        elif a.startswith("--desk="):
            args["desk"] = a.split("=", 1)[1]
    return args


def main(argv: list) -> int:
    args = _parse_args(argv)
    N = args["replicates"]
    RESULTS.mkdir(parents=True, exist_ok=True)

    # Windows piped stdout/stderr default to cp1252; model prose (arrows,
    # smart quotes, etc. captured into investigation_targets) would crash
    # print() and -- via a broad except -- clobber an already-saved good run.
    # Force utf-8 so console/tee never drops a rep. (File saves already use
    # encoding="utf-8"; this only affects the console mirror.)
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=== S13 CANARIES (no model call) ===")
    fleet_a = _load_fleet_a()
    desks = _build_desks(fleet_a)
    canary = _run_canaries(fleet_a, desks)
    (RESULTS / "canary.json").write_text(
        json.dumps(canary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not canary["canaries_ok"]:
        print("CANARY FAILED:")
        print(json.dumps({k: v for k, v in canary.items() if k != "canaries_ok"},
                         indent=2, ensure_ascii=False))
        return 1
    print("  harness/concentration/bench self-tests: ok")
    print(f"  floor unchanged: {canary['floor_unchanged']}")
    print(f"  fleet A hash={canary['fleet_a_hash']} unchanged={canary['fleet_a_unchanged']}")
    print(f"  dashboard no-interpretation: {canary['dashboard_no_interp']}")
    print(f"  skill output no-interpretation: "
          f"{{ {', '.join(f'{d}: all' for d in DESKS)} }}")
    print(f"  skill injection (ran_skill): "
          f"{ {d: canary['skill_injection'][d]['ran_skill'] for d in DESKS} }")
    print(f"  desk determinism: {canary['desk_determinism']}")
    print(f"  tool description: {canary['tool_desc_note']}")
    print(f"  stub session: {canary['stub_session']}")

    if args["canary_only"]:
        print("\n=== S13 CANARY-ONLY COMPLETE ===")
        return 0

    chosen = [args["desk"]] if args["desk"] else list(DESKS)
    for desk in chosen:
        if desk not in DESKS:
            sys.stderr.write(f"unknown desk {desk}; choose from {DESKS}\n")
            return 1

    print()
    print("=" * 70)
    print(f"=== S13 RUNS ({len(chosen)} desks x {N} replicates, interleaved, "
          f"{'resume' if args['resume'] else 'fresh'}) ===")
    print("=" * 70)

    by_desk: dict[str, list[dict]] = {d: [] for d in DESKS}
    for r in range(1, N + 1):
        for desk in chosen:
            if args["resume"] and _is_complete(desk, r):
                d = json.loads((RESULTS / desk / f"{r:02d}" / "run.json")
                               .read_text(encoding="utf-8"))
                by_desk[desk].append(d)
                print(f"-- [{desk}] rep {r:02d} (cached) "
                      f"calls={d.get('python_call_count')} "
                      f"skills={len(d.get('skill_invocations', []))}")
                continue
            print(f"-- [{desk}] rep {r:02d} running ...", flush=True)
            session = None
            try:
                session = _run_desk(desk, r, desks[desk])
                _save_run(session, desk, r)
                by_desk[desk].append(session)
            except Exception as e:
                tb = traceback.format_exc(limit=6)
                sys.stderr.write(f"-- [{desk}] rep {r:02d} FAILED (run/save): {e}\n{tb}\n")
                err = {"failed": True, "error": str(e), "desk": desk,
                       "replicate": r, "traceback": tb, "at": _stamp()}
                d = RESULTS / desk / f"{r:02d}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "run.json").write_text(
                    json.dumps(err, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
            # best-effort console summary -- NEVER clobber a good save. With
            # utf-8 stdout this should not raise; the guard is defense-in-depth.
            if session is not None:
                try:
                    _print_summary(session)
                except Exception as pe:
                    sys.stderr.write(
                        f"-- [{desk}] rep {r:02d} summary print skipped: {pe}\n")

    print()
    print("=" * 70)
    print("=== S13 POST-RUN FLOOR CANARY ===")
    post = _post_run_floor_canary()
    print(f"  floor unchanged: {post['floor_unchanged']}")
    print(f"  fleet A unchanged: {post['fleet_a_unchanged']}")

    print()
    print("=" * 70)
    print("=== S13 AGGREGATION ===")
    comp = _build_comparison(by_desk)
    (RESULTS / "comparison.json").write_text(
        json.dumps(comp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / "comparison.md").write_text(_comparison_md(comp), encoding="utf-8")
    try:
        print(_comparison_md(comp))
    except Exception as pe:
        sys.stderr.write(f"comparison echo skipped: {pe}\n")

    summary = {
        "run_id": _stamp(), "model": core.MODEL, "options": OPTIONS,
        "max_turns": MAX_TURNS, "replicates_per_desk": N, "desks": chosen,
        "canary": canary, "post_run_floor_canary": post, "comparison": comp,
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args["raw"]:
        print("\n" + "=" * 70)
        print("=== RAW FINAL RESPONSES ===")
        for desk in chosen:
            for r in by_desk.get(desk, []):
                print(f"\n##### [{desk}] rep {r.get('replicate'):02d} #####")
                print(r.get("final_response") or "(none)")

    print("\n=== S13 COMPLETE ===")
    print(f"  results: {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))