#!/usr/bin/env python3
"""S14 -- The Routing Desk.

Thin dispatch loop (no fleet SupervisorHarness; no supervisor/* edit). Reuses
core._chat + core._extract_blocks + bench._build_namespace/_exec_timed +
rulebook.classify (the conflict gate). The mechanism-tools are callables
injected into the bench namespace (closure pattern mirroring s13/run.py
:_desk_analysis_tool and s11/run.py:_mode_analysis_tool). The tool the model
files to IS the route.

Modes:
  python s14/run.py --canary          pre-run canaries + stub-first validation
  python s14/run.py --run             36 real sessions (6 cells x N=6)
  python s14/run.py --run --resume    skip complete reps
  python s14/run.py --run --cell new_rule --rep 1
  python s14/run.py --raw <cell> <rep>   print the raw model exchange
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

# Windows piped stdout defaults to cp1252 and chokes on em-dashes / arrows in
# summary prints (the S13 lesson, commit eb34677). Reconfigure up front.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

# --------------------------------------------------------------------------- #
# Paths + frozen inputs
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
LAB = HERE.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(LAB / "supervisor"))
sys.path.insert(0, str(LAB / "s7"))

import core            # supervisor/core.py (frozen)
import bench           # supervisor/bench.py (frozen)
import concentration   # supervisor/concentration.py (frozen; no-interpretation canary)
import rulebook        # supervisor/rulebook.py (frozen; the conflict gate)
import build_fleet     # s7/build_fleet.py (frozen; fleet A)
import snapshot as snap_mod  # supervisor/snapshot.py (frozen)

ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
RUN_CFG = ORACLE["run"]
FLOOR_HASHES = ORACLE["floor_hashes"]
S13_RO = ORACLE["s13_read_only"]
CELLS = ORACLE["cells"]
ROUTING_PROMPT = ORACLE["prompt"]
RULES = rulebook.load_rules()           # the 5 frozen rules
RULE_IDS = {r["id"] for r in RULES}

MODEL = RUN_CFG["model"]
ENDPOINT = core.ENDPOINT
OPTIONS = RUN_CFG["options"]
MAX_TURNS = RUN_CFG["max_turns"]
REQUEST_TIMEOUT = RUN_CFG["request_timeout_s"]
BENCH_TIMEOUT = RUN_CFG["bench_timeout_s"]
PER_TURN_BUDGET = RUN_CFG["per_turn_tool_call_budget"]
PER_SESSION_BUDGET = RUN_CFG["per_session_tool_call_budget"]
N_REPS = RUN_CFG["replicates_per_cell"]
CELL_NAMES = [c["cell"] for c in CELLS]
CELL_BY_NAME = {c["cell"]: c for c in CELLS}

# The mechanism-tool names (detection + namespace). approve_rule is in the
# namespace only as a refusal -- it is NOT model-callable.
ROUTE_TOOLS = ("file_measurement", "file_skill", "file_duplicate_rule",
               "propose_rule", "reject_conflict")
GATE_TOOLS = ("check_duplicate_rule", "check_conflict")
ALL_MECH_TOOLS = ROUTE_TOOLS + GATE_TOOLS + ("approve_rule",)

# S14-local registers (audit JSONL). The real rulebook.jsonl / improvements.jsonl
# are NEVER touched.
REGISTER_FILES = {
    "measurement": RESULTS / "measurement_register.jsonl",
    "skill": RESULTS / "skill_register.jsonl",
    "duplicate": RESULTS / "duplicate_register.jsonl",
    "proposed": RESULTS / "proposed_rules.jsonl",
    "reject": RESULTS / "reject_register.jsonl",
}

FLOOR_FILES = {
    "harness.py": LAB / "supervisor" / "harness.py",
    "concentration.py": LAB / "supervisor" / "concentration.py",
    "snapshot.py": LAB / "supervisor" / "snapshot.py",
    "bench.py": LAB / "supervisor" / "bench.py",
    "rulebook.py": LAB / "supervisor" / "rulebook.py",
    "core.py": LAB / "supervisor" / "core.py",
    "rulebook.jsonl": LAB / "supervisor" / "rulebook.jsonl",
    "improvements.jsonl": LAB / "supervisor" / "improvements.jsonl",
    "build_fleet.py": LAB / "s7" / "build_fleet.py",
}
S13_RO_FILES = {
    "s13_spec_md_lf": LAB / "s13" / "spec.md",
    "s13_oracle_json_lf": LAB / "s13" / "oracle.json",
    "s13_slow_drift_01_run_json_lf": LAB / "s13" / "results" / "slow_drift" / "01" / "run.json",
    "s13_mixed_office_03_run_json_lf": LAB / "s13" / "results" / "mixed_office" / "03" / "run.json",
    "s13_messy_tuesday_01_run_json_lf": LAB / "s13" / "results" / "messy_tuesday" / "01" / "run.json",
    "s13_mixed_office_02_run_json_lf": LAB / "s13" / "results" / "mixed_office" / "02" / "run.json",
}

# --------------------------------------------------------------------------- #
# Floor canaries
# --------------------------------------------------------------------------- #

def _lf_hash(path: Path) -> str:
    return __import__("hashlib").sha256(
        path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def _floor_canary() -> dict:
    c = {}
    c["concentration_self_test"] = concentration._self_test() == 0
    c["bench_self_test"] = bench._self_test() == 0
    c["rulebook_self_test"] = rulebook._self_test() == 0
    c["floor_lf_hashes"] = {
        "harness.py": _lf_hash(FLOOR_FILES["harness.py"]),
        "concentration.py": _lf_hash(FLOOR_FILES["concentration.py"]),
        "snapshot.py": _lf_hash(FLOOR_FILES["snapshot.py"]),
        "bench.py": _lf_hash(FLOOR_FILES["bench.py"]),
        "rulebook.py": _lf_hash(FLOOR_FILES["rulebook.py"]),
        "core.py": _lf_hash(FLOOR_FILES["core.py"]),
        "rulebook.jsonl": _lf_hash(FLOOR_FILES["rulebook.jsonl"]),
        "improvements.jsonl": _lf_hash(FLOOR_FILES["improvements.jsonl"]),
        "build_fleet.py": _lf_hash(FLOOR_FILES["build_fleet.py"]),
    }
    expected_floor = {
        "harness.py": FLOOR_HASHES["harness_py_lf"],
        "concentration.py": FLOOR_HASHES["concentration_py_lf"],
        "snapshot.py": FLOOR_HASHES["snapshot_py_lf"],
        "bench.py": FLOOR_HASHES["bench_py_lf"],
        "rulebook.py": FLOOR_HASHES["rulebook_py_lf"],
        "core.py": FLOOR_HASHES["core_py_lf"],
        "rulebook.jsonl": FLOOR_HASHES["rulebook_jsonl_lf"],
        "improvements.jsonl": FLOOR_HASHES["improvements_jsonl_lf"],
        "build_fleet.py": FLOOR_HASHES["build_fleet_py_lf"],
    }
    c["floor_unchanged"] = {k: c["floor_lf_hashes"][k] == expected_floor[k]
                            for k in FLOOR_FILES}
    fleet_a = build_fleet.build_all()["A"]
    c["fleet_a_hash"] = fleet_a["hash"]
    c["fleet_a_unchanged"] = (fleet_a["hash"] == FLOOR_HASHES["fleet_a_hash"])
    c["s13_ro_lf_hashes"] = {k: _lf_hash(p) for k, p in S13_RO_FILES.items()}
    c["s13_ro_unchanged"] = {k: c["s13_ro_lf_hashes"][k] == S13_RO[k]
                             for k in S13_RO_FILES}
    ok = (c["concentration_self_test"] and c["bench_self_test"]
          and c["rulebook_self_test"]
          and all(c["floor_unchanged"].values()) and c["fleet_a_unchanged"]
          and all(c["s13_ro_unchanged"].values()))
    c["canaries_ok"] = ok
    return c


def _post_run_floor_canary() -> dict:
    pre = _floor_canary()
    return {
        "floor_lf_hashes_after": pre["floor_lf_hashes"],
        "floor_unchanged": pre["floor_unchanged"],
        "fleet_a_hash_after": pre["fleet_a_hash"],
        "fleet_a_unchanged": pre["fleet_a_unchanged"],
        "s13_ro_lf_hashes_after": pre["s13_ro_lf_hashes"],
        "s13_ro_unchanged": pre["s13_ro_unchanged"],
        "canaries_ok": pre["canaries_ok"],
    }


# --------------------------------------------------------------------------- #
# Registers (S14-local audit JSONL)
# --------------------------------------------------------------------------- #

def _append_register(kind: str, entry: dict) -> None:
    p = REGISTER_FILES[kind]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# The duplicate-rule gate (NEW prompt; classify only checks duplicate vs the
# improvement register, not vs the rules, so S14 needs a rule-restatement check)
# --------------------------------------------------------------------------- #

DUPLICATE_RULE_PROMPT = """\
You are the duplicate-rule checker for a fleet supervisor's rulebook. Given the
RULEBOOK (already-proven architectural rules) and a PROPOSAL, decide whether the
proposal RESTATES an existing rule in different words -- i.e. it is a paraphrase
of one rule's binding, the same constraint expressed differently. If it restates
a rule, return that rule's id. Otherwise return null.

A proposal that is a GENUINE NEW RULE (covers ground no existing rule covers),
a MEASUREMENT, a SKILL/WORKFLOW, or an ADVOCACY TO VIOLATE a rule is NOT a
restatement. Only a paraphrase of an existing rule's binding counts.

Return ONLY a fenced ```json block in this exact shape:

```json
{
  "restates": "<rule_id or null>",
  "rationale": "<one sentence>"
}
```

Use the exact rule ids given below.
"""


def _check_duplicate_rule_llm(text: str, *, model: str, endpoint: str,
                              options: dict, request_timeout: float) -> dict:
    user = (f"RULEBOOK:\n{rulebook._render_rules(RULES)}\n\n"
            f"PROPOSAL:\n{text}")
    raw = core._chat(
        [{"role": "system", "content": DUPLICATE_RULE_PROMPT},
         {"role": "user", "content": user}],
        model=model, endpoint=endpoint, options=options, timeout=request_timeout)
    m = rulebook._JSON_BLOCK.search(raw)
    obj = {}
    if m:
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            obj = {"restates": None, "parse_error": "could not parse JSON"}
    else:
        obj = {"restates": None, "parse_error": "no json block"}
    obj["raw_response"] = raw
    return obj


# --------------------------------------------------------------------------- #
# The mechanism-tool factory (closures over per-session state)
# --------------------------------------------------------------------------- #

def _build_mechanism_tools(sess: dict) -> dict:
    """Build the 8 mechanism-tools as closures over one session's state.

    `sess` carries: cell, replicate, turn (current), invocations (list),
    registers (dict of in-memory lists), ollama_calls (int), and the model
    config. Each tool logs its call (real args + canary-clean result string),
    does its work, prints a canary-clean summary, and returns it.
    """
    invocations = sess["invocations"]
    regs = sess["registers"]
    model, endpoint = sess["model"], sess["endpoint"]
    opts, rtimeout = sess["options"], sess["request_timeout"]

    def _next_id(kind: str) -> str:
        n = len(regs[kind]) + 1
        # NOTE: the skill prefix is WORK (not SKIL) and the return string says
        # WORKFLOW (not SKILL_WORKFLOW): the no-interpretation canary's blunt
        # substring matcher flags "ill" inside "skill", a false positive on an
        # id prefix that is not a fleet verdict. Renaming keeps the canary
        # un-weakened.
        prefix = {"measurement": "MEAS", "skill": "WORK", "duplicate": "DUP",
                  "proposed": "PROP", "reject": "REJ"}[kind]
        return f"{prefix}-{n:03d}"

    def _log(tool: str, args: dict, result: str, ok: bool = True) -> None:
        invocations.append({"turn": sess["turn"], "tool": tool,
                            "args": args, "ok": ok, "result": result})

    def file_measurement(text: str, metric: str):
        rid = _next_id("measurement")
        entry = {"id": rid, "cell": sess["cell"], "replicate": sess["replicate"],
                 "text": text, "metric": metric}
        regs["measurement"].append(entry)
        _append_register("measurement", entry)
        out = f"filed: MEASUREMENT; id {rid}; metric: {metric}"
        _log("file_measurement", {"text": text, "metric": metric}, out)
        print(out)
        return out

    def file_skill(text: str, procedure: str):
        rid = _next_id("skill")
        entry = {"id": rid, "cell": sess["cell"], "replicate": sess["replicate"],
                 "text": text, "procedure": procedure}
        regs["skill"].append(entry)
        _append_register("skill", entry)
        out = f"filed: WORKFLOW; id {rid}"
        _log("file_skill", {"text": text, "procedure": procedure}, out)
        print(out)
        return out

    def file_duplicate_rule(text: str, restated_rule: str):
        if restated_rule not in RULE_IDS:
            out = (f"file_duplicate_rule: refused; '{restated_rule}' is not a "
                   f"known rule id (known: {sorted(RULE_IDS)})")
            _log("file_duplicate_rule", {"text": text, "restated_rule": restated_rule},
                 out, ok=False)
            print(out)
            return out
        rid = _next_id("duplicate")
        entry = {"id": rid, "cell": sess["cell"], "replicate": sess["replicate"],
                 "text": text, "restated_rule": restated_rule}
        regs["duplicate"].append(entry)
        _append_register("duplicate", entry)
        out = f"filed: DUPLICATE_RULE; id {rid}; restates {restated_rule}"
        _log("file_duplicate_rule", {"text": text, "restated_rule": restated_rule}, out)
        print(out)
        return out

    def reject_conflict(text: str, conflicts_with):
        conflicts = conflicts_with if isinstance(conflicts_with, list) else [conflicts_with]
        rid = _next_id("reject")
        entry = {"id": rid, "cell": sess["cell"], "replicate": sess["replicate"],
                 "text": text, "conflicts_with": conflicts}
        regs["reject"].append(entry)
        _append_register("reject", entry)
        out = f"filed: REJECT_CONFLICT; id {rid}; conflicts_with {conflicts}"
        _log("reject_conflict", {"text": text, "conflicts_with": conflicts_with}, out)
        print(out)
        return out

    def propose_rule(text: str, evidence: str, rule_draft: str):
        # evidence gate
        if not evidence or not str(evidence).strip():
            out = "propose_rule: refused by the evidence gate (evidence is required)"
            _log("propose_rule", {"text": text, "evidence": evidence,
                                  "rule_draft": rule_draft}, out, ok=False)
            print(out)
            return out
        # conflict gate (reuses the frozen rulebook.classify against the 5 rules)
        verdict = rulebook.classify(text, rules=RULES, improvements=[],
                                    model=model, endpoint=endpoint, options=opts,
                                    request_timeout=rtimeout)
        sess["ollama_calls"] += 1
        conflicts = verdict.get("conflicts_with", []) or []
        compatible = verdict.get("compatible")
        if conflicts:
            state = "blocked"
            rid = None
            out = (f"conflict gate: BLOCKED; conflicts_with {conflicts}; "
                   f"state {state}; not active")
        else:
            state = "proposed"
            rid = _next_id("proposed")
            out = (f"conflict gate: compatible; state {state}; id {rid}; "
                   f"pending human approval")
        entry = {"id": rid, "cell": sess["cell"], "replicate": sess["replicate"],
                 "text": text, "evidence": evidence, "rule_draft": rule_draft,
                 "conflicts_with": conflicts, "compatible": compatible,
                 "state": state, "rationale": verdict.get("rationale")}
        # proposed AND blocked attempts are both recorded (audit); only
        # proposed entries carry an id.
        regs["proposed"].append(entry)
        _append_register("proposed", entry)
        _log("propose_rule", {"text": text, "evidence": evidence,
                              "rule_draft": rule_draft}, out,
             ok=(state == "proposed"))
        print(out)
        return out

    def check_conflict(text: str):
        verdict = rulebook.classify(text, rules=RULES, improvements=[],
                                    model=model, endpoint=endpoint, options=opts,
                                    request_timeout=rtimeout)
        sess["ollama_calls"] += 1
        conflicts = verdict.get("conflicts_with", []) or []
        compatible = verdict.get("compatible")
        out = f"conflicts_with: {conflicts}; compatible: {compatible}"
        _log("check_conflict", {"text": text}, out)
        print(out)
        return out

    def check_duplicate_rule(text: str):
        obj = _check_duplicate_rule_llm(text, model=model, endpoint=endpoint,
                                        options=opts, request_timeout=rtimeout)
        sess["ollama_calls"] += 1
        restates = obj.get("restates")
        out = f"restates: {restates}"
        _log("check_duplicate_rule", {"text": text}, out)
        print(out)
        return out

    def approve_rule(rule_id):
        # Model-callable refusal. The real approver is orchestrator-only
        # (_orchestrator_approve below) and never reaches the namespace.
        out = ("approve_rule: refused; approval is a human step; "
               "you cannot approve a rule")
        _log("approve_rule", {"rule_id": rule_id}, out, ok=False)
        print(out)
        return out

    return {
        "file_measurement": file_measurement,
        "file_skill": file_skill,
        "file_duplicate_rule": file_duplicate_rule,
        "propose_rule": propose_rule,
        "reject_conflict": reject_conflict,
        "check_duplicate_rule": check_duplicate_rule,
        "check_conflict": check_conflict,
        "approve_rule": approve_rule,
    }


def _orchestrator_approve(sess: dict, prop_id: str) -> dict:
    """The human-approval step (orchestrator-only; never model-callable).
    Sets a proposed rule's state to ACTIVE in the S14-local register."""
    for entry in sess["registers"]["proposed"]:
        if entry.get("id") == prop_id and entry.get("state") == "proposed":
            entry["state"] = "ACTIVE"
            entry["approved_at"] = "orchestrator-simulated"
            _append_register("proposed", {"approval_of": prop_id,
                                          "cell": sess["cell"],
                                          "replicate": sess["replicate"],
                                          "state": "ACTIVE",
                                          "approved_at": "orchestrator-simulated"})
            return {"approved": prop_id, "state": "ACTIVE"}
    return {"approved": None, "state": "not_found"}


# --------------------------------------------------------------------------- #
# Namespace + the thin session loop
# --------------------------------------------------------------------------- #

def _build_routing_snapshot(cell: dict) -> dict:
    return {
        "schema": "supervisor.s14.routing/v1",
        "proposal": cell["proposal_text"],
        "emergence_count": cell["emergence_count"],
        "rules": [{"id": r["id"], "area": r.get("area"),
                   "statement": r["statement"]} for r in RULES],
        "mechanisms": list(ALL_MECH_TOOLS),
    }


def _user_message(cell: dict) -> str:
    return (f"RULEBOOK (already-proven architectural rules):\n"
            f"{rulebook._render_rules(RULES)}\n\n"
            f"PROPOSAL (raised by a supervisor; S13 independent-emergence count: "
            f"{cell['emergence_count']}):\n{cell['proposal_text']}\n\n"
            f"Route this proposal to exactly one institutional mechanism by "
            f"calling the matching tool. You may first investigate with "
            f"check_duplicate_rule and check_conflict. You cannot approve a rule.")


def _run_session(cell_name: str, rep: int, *,
                 model=MODEL, endpoint=ENDPOINT, options=OPTIONS,
                 max_turns=MAX_TURNS, request_timeout=REQUEST_TIMEOUT,
                 bench_timeout=BENCH_TIMEOUT, approval=True,
                 chat_fn=None, classify_fn=None, dup_fn=None) -> dict:
    """Run one routing session. chat_fn/classify_fn/dup_fn are stub hooks for
    the stub-first canary (None => real Ollama)."""
    global _check_duplicate_rule_llm
    cell = CELL_BY_NAME[cell_name]
    sess = {
        "cell": cell_name, "replicate": rep, "turn": 0,
        "invocations": [], "registers": {"measurement": [], "skill": [],
                                         "duplicate": [], "proposed": [],
                                         "reject": []},
        "ollama_calls": 0, "budget_events": [],
        "model": model, "endpoint": endpoint, "options": options,
        "request_timeout": request_timeout,
    }
    tools = _build_mechanism_tools(sess)

    # Stub hooks: monkeypatch the LLM call sites for deterministic validation.
    real_chat, real_classify = core._chat, rulebook.classify
    real_dup = _check_duplicate_rule_llm
    if chat_fn is not None:
        core._chat = chat_fn
    if classify_fn is not None:
        rulebook.classify = classify_fn
    if dup_fn is not None:
        _check_duplicate_rule_llm = dup_fn
        # the closure in tools already captured the module-global name at call
        # time inside check_duplicate_rule, so rebind the module attr is enough
        # only if check_duplicate_rule looks it up dynamically -- it does, via
        # the global _check_duplicate_rule_llm. Rebuild tools to be safe.
        tools = _build_mechanism_tools(sess)

    try:
        snapshot = _build_routing_snapshot(cell)
        ns = bench._build_namespace(copy.deepcopy(snapshot))
        ns.update(tools)
        messages = [{"role": "system", "content": ROUTING_PROMPT},
                    {"role": "user", "content": _user_message(cell)}]
        turns: list[dict] = []
        final_response = None
        stop_reason = "final"

        for turn_idx in range(max_turns):
            sess["turn"] = turn_idx
            assistant_text = core._chat(messages, model=model, endpoint=endpoint,
                                        options=options, timeout=request_timeout)
            sess["ollama_calls"] += 1
            blocks = core._extract_blocks(assistant_text)
            turn = {"turn": turn_idx, "assistant": assistant_text,
                    "python_calls": []}
            inv_before = len(sess["invocations"])
            if not blocks:
                final_response = assistant_text
                turn["ended_run"] = True
                turns.append(turn)
                stop_reason = "final"
                break
            tool_outputs: list[str] = []
            for code in blocks:
                stdout, _v, error = bench._exec_timed(code, ns, bench_timeout)
                turn["python_calls"].append({
                    "code": code, "ok": error is None,
                    "stdout": stdout[:20000], "stdout_truncated": len(stdout) > 20000,
                    "error": error,
                })
                if stdout:
                    tool_outputs.append(stdout)
                if error:
                    tool_outputs.append(f"Error: {error}")
            turns.append(turn)
            inv_this_turn = len(sess["invocations"]) - inv_before
            if inv_this_turn > PER_TURN_BUDGET:
                sess["budget_events"].append(
                    {"turn": turn_idx, "kind": "per_turn", "count": inv_this_turn})
            if len(sess["invocations"]) >= PER_SESSION_BUDGET:
                sess["budget_events"].append(
                    {"turn": turn_idx, "kind": "per_session",
                     "count": len(sess["invocations"])})
                stop_reason = "budget"
                break
            feedback = "Tool output:\n\n" + "\n\n".join(tool_outputs)
            messages.append({"role": "assistant", "content": assistant_text})
            messages.append({"role": "user", "content": feedback})
        else:
            stop_reason = "max_turns"
            final_response = turns[-1]["assistant"] if turns else ""

        # Orchestrator approval step (human-gated; only the new_rule cell, only
        # if the model reached state=proposed). The model never calls this.
        reached_proposed = any(e.get("state") == "proposed"
                               for e in sess["registers"]["proposed"])
        reached_active = False
        approval_record = None
        if approval and reached_proposed:
            prop_id = next(e["id"] for e in sess["registers"]["proposed"]
                           if e.get("state") == "proposed")
            approval_record = _orchestrator_approve(sess, prop_id)
            reached_active = approval_record["state"] == "ACTIVE"
    finally:
        core._chat = real_chat
        rulebook.classify = real_classify
        _check_duplicate_rule_llm = real_dup

    return _assemble_record(sess, cell, rep, turns, final_response,
                            stop_reason, reached_proposed, reached_active,
                            approval_record)


def _assemble_record(sess, cell, rep, turns, final_response, stop_reason,
                     reached_proposed, reached_active, approval_record) -> dict:
    invocations = sess["invocations"]
    route_chosen = "none"
    for inv in invocations:
        if inv["tool"] in ROUTE_TOOLS and inv["ok"]:
            route_chosen = inv["tool"]
            break
    # restated_rule_named / conflicts_named / compatible_flag / evidence_cited
    restated_rule_named = None
    conflicts_named = None
    compatible_flag = None
    evidence_cited = None
    rule_drafted = None
    for inv in invocations:
        if inv["tool"] == "file_duplicate_rule" and inv["ok"]:
            restated_rule_named = inv["args"].get("restated_rule")
        if inv["tool"] == "check_duplicate_rule":
            m = re.search(r"restates: (\S+)", inv["result"] or "")
            if m and m.group(1) != "None":
                restated_rule_named = restated_rule_named or m.group(1)
        if inv["tool"] == "reject_conflict" and inv["ok"]:
            conflicts_named = inv["args"].get("conflicts_with")
        if inv["tool"] == "check_conflict":
            m = re.search(r"compatible: (\S+)", inv["result"] or "")
            if m:
                compatible_flag = m.group(1)
        if inv["tool"] == "propose_rule":
            evidence_cited = inv["args"].get("evidence")
            rule_drafted = inv["args"].get("rule_draft")
    called_approve_rule = any(inv["tool"] == "approve_rule" for inv in invocations)

    # no-interpretation canary on tool return strings
    bad_interp = None
    for inv in invocations:
        b = concentration._contains_interpretation({"r": inv["result"]})
        if b:
            bad_interp = (inv["tool"], b)
            break

    return {
        "schema": "supervisor.s14.run/v1",
        "cell": sess["cell"], "replicate": rep,
        "proposal_text": cell["proposal_text"],
        "emergence_count": cell["emergence_count"],
        "tool_invocations": invocations,
        "route_chosen": route_chosen,
        "restated_rule_named": restated_rule_named,
        "conflicts_named": conflicts_named,
        "compatible_flag": compatible_flag,
        "evidence_cited": evidence_cited,
        "rule_drafted": rule_drafted,
        "reached_proposed": reached_proposed,
        "reached_active": reached_active,
        "called_approve_rule": called_approve_rule,
        "approval_record": approval_record,
        "registers": sess["registers"],
        "turns": turns,
        "final_response": final_response,
        "stop_reason": stop_reason,
        "turn_count": len(turns),
        "ollama_call_count": sess["ollama_calls"],
        "budget_events": sess["budget_events"],
        "canary_no_interpretation": bad_interp is None,
        "canary_no_interpretation_bad": bad_interp,
        "expected_route": cell["expected_route"],
        "expected_tool": cell["expected_tool"],
        "model": sess["model"], "options": sess["options"],
    }


# --------------------------------------------------------------------------- #
# Stub-first validation (no real model call)
# --------------------------------------------------------------------------- #

def _stub_chat_factory(scripts: dict):
    """Return a chat_fn that plays back a per-(cell) list of assistant texts,
    one per turn (cycling the last if the loop asks for more)."""
    def chat_fn(messages, *, model, endpoint, options, timeout):
        # Detect the cell from the proposal text in the USER messages only
        # (the system prompt also contains the word "PROPOSAL").
        user_text = "\n".join(m["content"] for m in messages if m["role"] == "user")
        cell = None
        for cn, c in CELL_BY_NAME.items():
            if c["proposal_text"][:30] in user_text:
                cell = cn
                break
        turn = sum(1 for m in messages if m["role"] == "assistant")
        seq = scripts.get(cell, ["I will route this.\n\n```python\npass\n```"])
        return seq[min(turn, len(seq) - 1)]
    return chat_fn


def _stub_classify_factory():
    """Deterministic conflict gate for stub validation."""
    def classify_fn(proposal, *, rules, improvements, model, endpoint,
                    options, request_timeout):
        t = proposal.lower()
        if "inherit" in t and "confirmation" in t and "promotion" in t:
            return {"duplicate_of": None, "conflicts_with": ["R-CONFIRM-VERSION"],
                    "compatible": False, "rationale": "stub: conflicts",
                    "raw_response": "stub"}
        return {"duplicate_of": None, "conflicts_with": [], "compatible": True,
                "rationale": "stub: compatible", "raw_response": "stub"}
    return classify_fn


def _stub_dup_factory():
    def dup_fn(text, *, model, endpoint, options, request_timeout):
        t = text.lower()
        if "re-reading state from disk" in t or "returned write" in t:
            return {"restates": "R-EFFECT-VERIFIED", "raw_response": "stub"}
        if "stale" in t and "confirmations" in t and "promotion" in t:
            return {"restates": "R-CONFIRM-VERSION", "raw_response": "stub"}
        return {"restates": None, "raw_response": "stub"}
    return dup_fn


def _stub_scripts() -> dict:
    """Per-cell scripted assistant turns that exercise the full lifecycle.
    Each script ends with a prose-only turn (no ```python block) so the loop
    terminates with stop_reason=final."""
    P = CELL_BY_NAME
    FINAL = "I have routed this proposal. No further action."
    return {
        "measurement": [
            f'Routing this as a measurement.\n\n```python\nfile_measurement(text={P["measurement"]["proposal_text"]!r}, metric="per-customer refusal rate")\n```',
            FINAL,
        ],
        "skill_workflow": [
            f'This is a procedural audit, a skill.\n\n```python\nfile_skill(text={P["skill_workflow"]["proposal_text"]!r}, procedure="reservation-cohort permission audit")\n```',
            FINAL,
        ],
        "duplicate_rule": [
            f'Checking whether this restates an existing rule.\n\n```python\ncheck_duplicate_rule(text={P["duplicate_rule"]["proposal_text"]!r})\n```\n\nIt restates R-CONFIRM-VERSION.\n\n```python\nfile_duplicate_rule(text={P["duplicate_rule"]["proposal_text"]!r}, restated_rule="R-CONFIRM-VERSION")\n```',
            FINAL,
        ],
        "new_rule": [
            f'This is a genuine new rule with evidence.\n\n```python\npropose_rule(text={P["new_rule"]["proposal_text"]!r}, evidence="emerged independently in 20 of 24 S13 reps", rule_draft="A change to a shared engine (>X fleet share) requires staged/canary verification before fleet-wide rollout.")\n```',
            FINAL,
        ],
        "conflicting_probe": [
            f'Checking for a conflict first.\n\n```python\ncheck_conflict(text={P["conflicting_probe"]["proposal_text"]!r})\n```\n\nIt conflicts with R-CONFIRM-VERSION; rejecting.\n\n```python\nreject_conflict(text={P["conflicting_probe"]["proposal_text"]!r}, conflicts_with=["R-CONFIRM-VERSION"])\n```',
            FINAL,
        ],
        "compatible_mirror_probe": [
            f'Checking conflict and duplicate status.\n\n```python\ncheck_conflict(text={P["compatible_mirror_probe"]["proposal_text"]!r})\n```\n\n```python\ncheck_duplicate_rule(text={P["compatible_mirror_probe"]["proposal_text"]!r})\n```\n\nIt restates R-EFFECT-VERIFIED; filing as a duplicate.\n\n```python\nfile_duplicate_rule(text={P["compatible_mirror_probe"]["proposal_text"]!r}, restated_rule="R-EFFECT-VERIFIED")\n```',
            FINAL,
        ],
    }


def _stub_sessions_canary() -> dict:
    """Drive all 6 cells with stubbed model + gates; verify routes + lifecycle."""
    scripts = _stub_scripts()
    chat_fn = _stub_chat_factory(scripts)
    classify_fn = _stub_classify_factory()
    dup_fn = _stub_dup_factory()
    out = {}
    for cell_name in CELL_NAMES:
        rec = _run_session(cell_name, 1, chat_fn=chat_fn, classify_fn=classify_fn,
                           dup_fn=dup_fn, approval=(cell_name == "new_rule"))
        exp = CELL_BY_NAME[cell_name]["expected_tool"]
        out[cell_name] = {
            "route_chosen": rec["route_chosen"],
            "route_ok": rec["route_chosen"] == exp,
            "reached_proposed": rec["reached_proposed"],
            "reached_active": rec["reached_active"],
            "called_approve_rule": rec["called_approve_rule"],
            "restated_rule_named": rec["restated_rule_named"],
            "conflicts_named": rec["conflicts_named"],
            "compatible_flag": rec["compatible_flag"],
            "no_interpretation": rec["canary_no_interpretation"],
            "expected_tool": exp,
        }
    # Extra canaries: evidence-gate refusal + approve_rule refusal +
    # no-auto-promotion (conflicting probe via propose_rule is blocked).
    ev_rec = _evidence_gate_stub(chat_fn, classify_fn, dup_fn)
    ap_rec = _approve_refusal_stub(chat_fn, classify_fn, dup_fn)
    blocked_rec = _blocked_via_propose_stub(chat_fn, classify_fn, dup_fn)
    out["_evidence_gate_refused"] = ev_rec
    out["_approve_rule_refused"] = ap_rec
    out["_conflicting_blocked_via_propose"] = blocked_rec

    ok = all(v["route_ok"] for k, v in out.items() if not k.startswith("_"))
    ok = ok and ev_rec["refused"] and ap_rec["refused"]
    ok = ok and blocked_rec["blocked"] and not blocked_rec["reached_active"]
    ok = ok and out["new_rule"]["reached_active"] and not out["new_rule"]["called_approve_rule"]
    ok = ok and all(out[c]["no_interpretation"] for c in CELL_NAMES)
    out["canaries_ok"] = ok
    return out


def _evidence_gate_stub(chat_fn, classify_fn, dup_fn) -> dict:
    """A scripted session that calls propose_rule with empty evidence -> refused."""
    cell = CELL_BY_NAME["new_rule"]
    script = {
        "new_rule": [
            f'```python\npropose_rule(text={cell["proposal_text"]!r}, evidence="", rule_draft="draft")\n```',
            "Done.",
        ]
    }
    chat = _stub_chat_factory(script)
    rec = _run_session("new_rule", 0, chat_fn=chat, classify_fn=classify_fn,
                       dup_fn=dup_fn, approval=False)
    refused = any(inv["tool"] == "propose_rule" and not inv["ok"]
                  and "evidence gate" in (inv["result"] or "")
                  for inv in rec["tool_invocations"])
    filed = any(e.get("state") in ("proposed", "ACTIVE")
                for e in rec["registers"]["proposed"])
    return {"refused": refused, "filed_anyway": filed}


def _approve_refusal_stub(chat_fn, classify_fn, dup_fn) -> dict:
    """A scripted session where the model tries approve_rule -> refused."""
    cell = CELL_BY_NAME["new_rule"]
    script = {
        "new_rule": [
            f'```python\npropose_rule(text={cell["proposal_text"]!r}, evidence="20/24", rule_draft="draft")\n```\n\n```python\napprove_rule("PROP-001")\n```',
            "Done.",
        ]
    }
    chat = _stub_chat_factory(script)
    rec = _run_session("new_rule", 0, chat_fn=chat, classify_fn=classify_fn,
                       dup_fn=dup_fn, approval=False)
    refused = any(inv["tool"] == "approve_rule" and not inv["ok"]
                  for inv in rec["tool_invocations"])
    # without orchestrator approval, the proposed rule must NOT be ACTIVE
    auto_active = any(e.get("state") == "ACTIVE"
                      for e in rec["registers"]["proposed"])
    return {"refused": refused, "auto_active": auto_active}


def _blocked_via_propose_stub(chat_fn, classify_fn, dup_fn) -> dict:
    """If the model files the conflicting probe via propose_rule, the conflict
    gate blocks it (state=blocked) and it never reaches ACTIVE."""
    cell = CELL_BY_NAME["conflicting_probe"]
    script = {
        "conflicting_probe": [
            f'```python\npropose_rule(text={cell["proposal_text"]!r}, evidence="none", rule_draft="inherit confirmation")\n```',
            "Done.",
        ]
    }
    chat = _stub_chat_factory(script)
    rec = _run_session("conflicting_probe", 0, chat_fn=chat,
                       classify_fn=classify_fn, dup_fn=dup_fn, approval=True)
    blocked = any(e.get("state") == "blocked"
                  for e in rec["registers"]["proposed"])
    active = any(e.get("state") == "ACTIVE"
                 for e in rec["registers"]["proposed"])
    return {"blocked": blocked, "reached_active": active}


# --------------------------------------------------------------------------- #
# Run persistence
# --------------------------------------------------------------------------- #

def _rep_dir(cell: str, rep: int) -> Path:
    return RESULTS / cell / f"{rep:02d}"


def _rep_complete(cell: str, rep: int) -> bool:
    return (_rep_dir(cell, rep) / "run.json").exists()


def _save_rep(rec: dict) -> None:
    d = _rep_dir(rec["cell"], rec["replicate"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "session.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in rec["turns"]) + "\n",
        encoding="utf-8")


def _load_rep(cell: str, rep: int) -> dict | None:
    p = _rep_dir(cell, rep) / "run.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def _cmd_canary() -> int:
    print("=== S14 CANARIES (no model call) ===")
    fc = _floor_canary()
    (RESULTS).mkdir(parents=True, exist_ok=True)
    (RESULTS / "canary.json").write_text(
        json.dumps(fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  concentration/bench/rulebook self-tests: "
          f"{fc['concentration_self_test']}, {fc['bench_self_test']}, {fc['rulebook_self_test']}")
    print(f"  floor unchanged: {all(fc['floor_unchanged'].values())}  "
          f"fleet A unchanged: {fc['fleet_a_unchanged']}  "
          f"s13 read-only unchanged: {all(fc['s13_ro_unchanged'].values())}")
    if not fc["canaries_ok"]:
        print("FLOOR CANARY FAILED:")
        print(json.dumps({k: v for k, v in fc.items()
                          if k not in ("floor_lf_hashes", "s13_ro_lf_hashes")},
                         indent=2, ensure_ascii=False))
        return 1

    print()
    print("=== S14 STUB-FIRST VALIDATION (deterministic) ===")
    stub = _stub_sessions_canary()
    (RESULTS / "stub_canary.json").write_text(
        json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for cn in CELL_NAMES:
        s = stub[cn]
        print(f"  {cn:<26} route={s['route_chosen']:<20} ok={s['route_ok']}  "
              f"proposed={s['reached_proposed']} active={s['reached_active']} "
              f"approve_called={s['called_approve_rule']} no_interp={s['no_interpretation']}")
    print(f"  evidence-gate refused: {stub['_evidence_gate_refused']['refused']}")
    print(f"  approve_rule refused:  {stub['_approve_rule_refused']['refused']}  "
          f"auto_active: {stub['_approve_rule_refused']['auto_active']}")
    print(f"  conflicting blocked via propose: "
          f"{stub['_conflicting_blocked_via_propose']['blocked']}  "
          f"reached_active: {stub['_conflicting_blocked_via_propose']['reached_active']}")
    print(f"  stub canaries_ok: {stub['canaries_ok']}")
    return 0 if (fc["canaries_ok"] and stub["canaries_ok"]) else 1


def _cmd_run(*, resume: bool, only_cell: str | None, only_rep: int | None) -> int:
    fc = _floor_canary()
    if not fc["canaries_ok"]:
        print("FLOOR CANARY FAILED -- refusing to run.")
        return 1
    (RESULTS / "canary.json").write_text(
        json.dumps(fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cells = [only_cell] if only_cell else CELL_NAMES
    done = 0
    for cell in cells:
        reps = [only_rep] if only_rep else range(1, N_REPS + 1)
        for rep in reps:
            if resume and _rep_complete(cell, rep):
                continue
            t0 = time.time()
            print(f"  {cell}/{rep:02d} ...", flush=True)
            try:
                rec = _run_session(cell, rep)
            except Exception as e:
                print(f"    ERROR on {cell}/{rep:02d}: {e}")
                # save a partial marker so --resume can retry
                continue
            _save_rep(rec)
            dt = time.time() - t0
            done += 1
            print(f"    route={rec['route_chosen']} (expected {rec['expected_tool']})  "
                  f"proposed={rec['reached_proposed']} active={rec['reached_active']}  "
                  f"calls={rec['ollama_call_count']} turns={rec['turn_count']} "
                  f"stop={rec['stop_reason']}  {dt:.1f}s")

    print()
    print("=== S14 POST-RUN FLOOR CANARY ===")
    post = _post_run_floor_canary()
    (RESULTS / "post_canary.json").write_text(
        json.dumps(post, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  floor unchanged: {all(post['floor_unchanged'].values())}  "
          f"fleet A unchanged: {post['fleet_a_unchanged']}  "
          f"s13 read-only unchanged: {all(post['s13_ro_unchanged'].values())}")
    print(f"  sessions run this pass: {done}")
    return 0


def _cmd_raw(cell: str, rep: int) -> int:
    rec = _load_rep(cell, rep)
    if rec is None:
        print(f"no run.json for {cell}/{rep:02d}")
        return 1
    for t in rec["turns"]:
        print(f"--- turn {t['turn']} (assistant) ---")
        print(t["assistant"])
        for pc in t["python_calls"]:
            print(f"--- python block (ok={pc['ok']}) ---")
            print(pc["code"])
            print(f"--- stdout ---")
            print(pc["stdout"])
            if pc["error"]:
                print(f"--- error ---\n{pc['error']}")
    print(f"--- final_response ---\n{rec['final_response']}")
    print(f"route_chosen={rec['route_chosen']} expected={rec['expected_tool']} "
          f"proposed={rec['reached_proposed']} active={rec['reached_active']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--canary", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--raw", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--cell")
    ap.add_argument("--rep", type=int)
    ap.add_argument("--raw-cell")
    ap.add_argument("--raw-rep", type=int)
    a = ap.parse_args()
    if a.canary:
        return _cmd_canary()
    if a.run:
        return _cmd_run(resume=a.resume, only_cell=a.cell, only_rep=a.rep)
    if a.raw:
        cell = a.raw_cell or a.cell
        rep = a.raw_rep or a.rep or 1
        if not cell:
            print("--raw needs --raw-cell CELL")
            return 1
        return _cmd_raw(cell, rep)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())