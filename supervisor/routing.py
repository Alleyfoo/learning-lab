#!/usr/bin/env python3
"""Workspace v0 -- the routing desk + the mandatory duplicate-before-conflict gate.

This is the S14/S15 machinery extracted into normal supervisor code. No sN
import. The supervisor's job during a run is to RAISE proposals; routing is a
later, on-demand step the operator triggers from the Improvements page. This
module routes one raised proposal to exactly one institutional mechanism, then
(for NEW_RULE+proposed) the operator can activate it -- the only path that
grows the real rulebook.jsonl.

The structure is the S15 thin dispatch loop (no SupervisorHarness; no core.review):
core._chat -> core._extract_blocks -> bench._exec_timed over a namespace that
holds the 8 mechanism-tools. The tool the model files to IS the route.

The S15 design principle is preserved verbatim: the authority-bearing transition
(propose_rule) runs the duplicate check ITSELF, as a MANDATORY internal step
between the evidence gate and the conflict gate. A restatement is demoted to
DUPLICATE_RULE (no proposed entry, never reaches the conflict classifier, never
ACTIVE). A novel proposal proceeds to the conflict gate (rulebook.classify) ->
blocked | proposed. The model may still call check_duplicate_rule for preliminary
reasoning, but the write boundary does not trust that somebody remembered.

approve_rule is a model-callable refusal: activation is orchestrator/human-only
(routing.activate, never in the namespace).

Routes and their filing tools:
  MEASUREMENT      file_measurement(text, metric)
  SKILL_WORKFLOW   file_skill(text, procedure)
  DUPLICATE_RULE   file_duplicate_rule(text, restated_rule)   (or demoted by the
                                                               mandatory gate)
  NEW_RULE         propose_rule(text, evidence, rule_draft)  -> proposed|blocked
  REJECT_CONFLICT  reject_conflict(text, conflicts_with)
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench          # noqa: E402  (restricted namespace + timed exec)
import concentration  # noqa: E402  (no-interpretation canary)
import core           # noqa: E402  (the model round-trip)
import rulebook       # noqa: E402  (the conflict gate + render + _JSON_BLOCK)

import backlog  # noqa: E402  (the raise/route/activate audit log)

# Windows piped stdout defaults to cp1252 and chokes on the em-dashes in the
# routing prompt (the S13 lesson). Reconfigure up front.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


# --- prompts (moved verbatim from the frozen S14/S15 oracle) ----------------

ROUTING_PROMPT = """\
You are the routing desk for a fleet supervisor's improvement proposals. You are given the RULEBOOK (already-proven architectural rules) and a single PROPOSAL raised by a supervisor. Route the proposal to exactly ONE institutional mechanism by calling the matching tool. You may first investigate with `check_duplicate_rule` (does it restate an existing rule?) and `check_conflict` (does it conflict with a rule?) -- these return facts; you decide the route.

The mechanisms:
- `file_measurement(text, metric)` -- the proposal is a thing to MEASURE / track over time (a metric, a trend, an alert on a metric). Measurements are not rules.
- `file_skill(text, procedure)` -- the proposal is a procedural capability, a SKILL or WORKFLOW an operator/audit performs (an audit, a check procedure, an investigative step). Skills are not rules.
- `file_duplicate_rule(text, restated_rule)` -- the proposal RESTATES an existing rule in different words. Name the rule it restates. It is not a new rule.
- `propose_rule(text, evidence, rule_draft)` -- the proposal is a GENUINE NEW RULE: it covers ground no existing rule covers, it is rule-shaped (a binding the system should enforce), and you can cite its evidence. Draft the rule text. The system will conflict-check it; a human must approve it before it is active.
- `reject_conflict(text, conflicts_with)` -- the proposal ADVOCATES VIOLATING or weakening an existing rule. Name the rule it conflicts with.

Do not treat every improvement as a rule. A measurement is not a rule. A skill is not a rule. A restatement of an existing rule is not a new rule. Only rule-shaped, novel, evidenced proposals go to `propose_rule`.

You CANNOT approve a rule. `approve_rule` is a human step, not yours. Do not call it.

To act, emit a fenced ```python block calling one mechanism-tool. To finish, write plain prose with no ```python block.
"""

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


# --- the duplicate-rule gate (reused verbatim from S15; rulebook.classify only
# checks duplicate vs the improvement register, not vs the rules, so we need a
# rule-restatement check). Used BOTH by the model's optional check_duplicate_rule
# AND by propose_rule's MANDATORY internal check. ---------------------------

def check_duplicate_rule_llm(text: str, *, rules: list[dict],
                             model: str = core.MODEL, endpoint: str = core.ENDPOINT,
                             options: Optional[dict] = None,
                             request_timeout: float = 300.0) -> dict:
    """Decide whether `text` restates an existing rule. Returns
    {restates: rule_id|null, rationale?, parse_error?, raw_response}. Distinct
    from rulebook.classify, which checks duplicate-vs-improvement-register +
    conflict, not rule-restatement."""
    opts = options or {"temperature": 0.1}
    user = (f"RULEBOOK:\n{rulebook._render_rules(rules)}\n\n"
            f"PROPOSAL:\n{text}")
    raw = core._chat(
        [{"role": "system", "content": DUPLICATE_RULE_PROMPT},
         {"role": "user", "content": user}],
        model=model, endpoint=endpoint, options=opts, timeout=request_timeout)
    m = rulebook._JSON_BLOCK.search(raw)
    obj: dict = {}
    if m:
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            obj = {"restates": None, "parse_error": "could not parse JSON"}
    else:
        obj = {"restates": None, "parse_error": "no json block"}
    obj["raw_response"] = raw
    return obj


# --- the routing desk: 8 mechanism-tools as closures over one route's state --

ROUTE_TOOLS = ("file_measurement", "file_skill", "file_duplicate_rule",
               "propose_rule", "reject_conflict")
GATE_TOOLS = ("check_duplicate_rule", "check_conflict")
ALL_MECH_TOOLS = ROUTE_TOOLS + GATE_TOOLS + ("approve_rule",)

# Route id prefixes. The skill prefix is WORK (not SKIL) and the return string
# says WORKFLOW (not SKILL_WORKFLOW): the no-interpretation canary's blunt
# substring matcher flags "ill" inside "skill", a false positive on an id
# prefix that is not a fleet verdict. Renaming keeps the canary un-weakened.
# (Carried from S14.)
_ROUTE_PREFIX = {"MEASUREMENT": "MEAS", "SKILL_WORKFLOW": "WORK",
                 "DUPLICATE_RULE": "DUP", "NEW_RULE": "PROP",
                 "REJECT_CONFLICT": "REJ"}


class RoutingDesk:
    """Holds the model config and builds the per-route mechanism-tools.

    `route(imp_id)` runs one proposal through the thin dispatch loop and
    appends a `route` line to the backlog. `activate(imp_id)` is the human-gated
    step that appends an `activate` line AND the rule to rulebook.jsonl.
    """

    def __init__(self, *, model: str = core.MODEL, endpoint: str = core.ENDPOINT,
                 options: Optional[dict] = None,
                 request_timeout: float = 300.0,
                 bench_timeout: float = 10.0,
                 max_turns: int = 6) -> None:
        self.model = model
        self.endpoint = endpoint
        self.options = options or {"temperature": 0.2, "num_ctx": 131072}
        self.request_timeout = request_timeout
        self.bench_timeout = bench_timeout
        self.max_turns = max_turns

    # -- the 8 mechanism-tools, closures over one route's state --------------

    def _build_tools(self, state: dict, rules: list[dict]) -> dict:
        invocations = state["invocations"]
        rule_ids = {r["id"] for r in rules}

        def _log(tool: str, args: dict, result: str, ok: bool = True) -> None:
            invocations.append({"turn": state["turn"], "tool": tool,
                                "args": args, "ok": ok, "result": result})

        def file_measurement(text: str, metric: str):
            state["route"] = "MEASUREMENT"
            state["route_meta"]["metric"] = metric
            out = f"filed: MEASUREMENT; metric: {metric}"
            _log("file_measurement", {"text": text, "metric": metric}, out)
            print(out)
            return out

        def file_skill(text: str, procedure: str):
            state["route"] = "SKILL_WORKFLOW"
            state["route_meta"]["procedure"] = procedure
            out = f"filed: WORKFLOW; procedure: {procedure}"
            _log("file_skill", {"text": text, "procedure": procedure}, out)
            print(out)
            return out

        def file_duplicate_rule(text: str, restated_rule: str):
            if restated_rule not in rule_ids:
                out = (f"file_duplicate_rule: refused; '{restated_rule}' is not a "
                       f"known rule id (known: {sorted(rule_ids)})")
                _log("file_duplicate_rule", {"text": text,
                                              "restated_rule": restated_rule},
                     out, ok=False)
                print(out)
                return out
            state["route"] = "DUPLICATE_RULE"
            state["route_meta"]["restated_rule"] = restated_rule
            state["route_meta"]["lifecycle_state"] = None
            out = f"filed: DUPLICATE_RULE; restates {restated_rule}"
            _log("file_duplicate_rule", {"text": text,
                                          "restated_rule": restated_rule}, out)
            print(out)
            return out

        def reject_conflict(text: str, conflicts_with):
            conflicts = (conflicts_with if isinstance(conflicts_with, list)
                         else [conflicts_with])
            state["route"] = "REJECT_CONFLICT"
            state["route_meta"]["conflicts_with"] = conflicts
            state["route_meta"]["lifecycle_state"] = None
            out = f"filed: REJECT_CONFLICT; conflicts_with {conflicts}"
            _log("reject_conflict", {"text": text,
                                      "conflicts_with": conflicts_with}, out)
            print(out)
            return out

        def propose_rule(text: str, evidence: str, rule_draft: str):
            # ---- evidence gate (unchanged) ----------------------------------
            if not evidence or not str(evidence).strip():
                out = "propose_rule: refused by the evidence gate (evidence is required)"
                _log("propose_rule", {"text": text, "evidence": evidence,
                                      "rule_draft": rule_draft}, out, ok=False)
                print(out)
                return out

            # ---- MANDATORY novelty/duplicate check (S15) ---------------------
            # The authority-bearing transition runs the duplicate check itself;
            # it does not trust that the model remembered check_duplicate_rule.
            mg = state["mandatory_gate"]
            mg["ran"] = True
            dup_obj = check_duplicate_rule_llm(
                text, rules=rules, model=self.model, endpoint=self.endpoint,
                options={"temperature": 0.1, "num_ctx": self.options.get("num_ctx", 131072)},
                request_timeout=self.request_timeout)
            state["ollama_calls"] += 1
            restates = dup_obj.get("restates")
            mg["restates"] = restates
            if restates and restates in rule_ids:
                # DEMOTE: a restatement is DUPLICATE_RULE, not a new rule. No
                # proposed entry, no conflict check, never ACTIVE. This is the
                # exact hole S14 exposed: the conflict gate cannot catch a
                # restatement (it is "compatible"), so the duplicate check MUST
                # run before it.
                mg["caught"] = True
                mg["demoted"] = True
                state["route"] = "DUPLICATE_RULE"
                state["route_meta"]["restated_rule"] = restates
                state["route_meta"]["lifecycle_state"] = None
                out = (f"mandatory duplicate gate: RESTATES {restates}; "
                       f"demoted to DUPLICATE_RULE; no proposal, no conflict "
                       f"check, not active")
                _log("propose_rule", {"text": text, "evidence": evidence,
                                      "rule_draft": rule_draft,
                                      "mandatory_gate": "demoted",
                                      "restates": restates}, out, ok=True)
                print(out)
                return out

            # ---- novel: conflict gate (rulebook.classify) -------------------
            verdict = rulebook.classify(
                text, rules=rules, improvements=[],
                model=self.model, endpoint=self.endpoint,
                options={"temperature": 0.1, "num_ctx": self.options.get("num_ctx", 131072)},
                request_timeout=self.request_timeout)
            state["ollama_calls"] += 1
            conflicts = verdict.get("conflicts_with", []) or []
            compatible = verdict.get("compatible")
            state["route_meta"]["conflicts_with"] = conflicts
            state["route_meta"]["compatible"] = compatible
            if conflicts:
                state["route"] = "REJECT_CONFLICT"
                state["route_meta"]["lifecycle_state"] = "blocked"
                out = (f"conflict gate: BLOCKED; conflicts_with {conflicts}; "
                       f"state blocked; not active")
            else:
                state["route"] = "NEW_RULE"
                state["route_meta"]["lifecycle_state"] = "proposed"
                state["route_meta"]["rule_draft"] = rule_draft
                out = (f"conflict gate: compatible; state proposed; "
                       f"pending human approval")
            _log("propose_rule", {"text": text, "evidence": evidence,
                                  "rule_draft": rule_draft,
                                  "mandatory_gate": "novel"}, out,
                 ok=(state["route_meta"]["lifecycle_state"] == "proposed"))
            print(out)
            return out

        def check_conflict(text: str):
            verdict = rulebook.classify(
                text, rules=rules, improvements=[],
                model=self.model, endpoint=self.endpoint,
                options={"temperature": 0.1, "num_ctx": self.options.get("num_ctx", 131072)},
                request_timeout=self.request_timeout)
            state["ollama_calls"] += 1
            conflicts = verdict.get("conflicts_with", []) or []
            compatible = verdict.get("compatible")
            out = f"conflicts_with: {conflicts}; compatible: {compatible}"
            _log("check_conflict", {"text": text}, out)
            print(out)
            return out

        def check_duplicate_rule(text: str):
            obj = check_duplicate_rule_llm(
                text, rules=rules, model=self.model, endpoint=self.endpoint,
                options={"temperature": 0.1, "num_ctx": self.options.get("num_ctx", 131072)},
                request_timeout=self.request_timeout)
            state["ollama_calls"] += 1
            restates = obj.get("restates")
            out = f"restates: {restates}"
            _log("check_duplicate_rule", {"text": text}, out)
            print(out)
            return out

        def approve_rule(rule_id):
            # Model-callable refusal. The real approver is routing.activate
            # (human-gated, below) and never reaches the namespace.
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

    # -- the thin dispatch loop (S15 structure, writing to the backlog) --------

    def _user_message(self, text: str, rules: list[dict]) -> str:
        return (f"RULEBOOK (already-proven architectural rules):\n"
                f"{rulebook._render_rules(rules)}\n\n"
                f"PROPOSAL (raised by a supervisor):\n{text}\n\n"
                f"Route this proposal to exactly one institutional mechanism by "
                f"calling the matching tool. You may first investigate with "
                f"check_duplicate_rule and check_conflict. You cannot approve a rule.")

    def _routing_snapshot(self, text: str, rules: list[dict]) -> dict:
        return {
            "schema": "supervisor.routing/v1",
            "proposal": text,
            "rules": [{"id": r["id"], "area": r.get("area"),
                       "statement": r["statement"]} for r in rules],
            "mechanisms": list(ALL_MECH_TOOLS),
        }

    def route(self, imp_id: str, *, chat_fn=None, classify_fn=None,
              dup_fn=None) -> dict:
        """Route one raised proposal to exactly one mechanism. Appends a `route`
        line to the backlog. chat_fn/classify_fn/dup_fn are stub hooks for the
        self-test (None => real Ollama)."""
        global check_duplicate_rule_llm
        rec = backlog.get(imp_id)
        if rec is None:
            return {"imp_id": imp_id, "error": "no such proposal in the backlog"}
        text = rec.get("text") or ""
        # load rules fresh so newly-activated rules are seen
        rules = rulebook.load_rules()
        state = {
            "imp_id": imp_id, "text": text, "turn": 0,
            "route": None, "route_meta": {"restated_rule": None,
                                           "conflicts_with": [], "compatible": None,
                                           "rule_draft": None, "lifecycle_state": None},
            "invocations": [], "ollama_calls": 0,
            "mandatory_gate": {"ran": False, "caught": False,
                               "demoted": False, "restates": None},
        }
        tools = self._build_tools(state, rules)

        real_chat, real_classify = core._chat, rulebook.classify
        real_dup = check_duplicate_rule_llm
        if chat_fn is not None:
            core._chat = chat_fn
        if classify_fn is not None:
            rulebook.classify = classify_fn  # type: ignore[assignment]
        if dup_fn is not None:
            check_duplicate_rule_llm = dup_fn  # type: ignore[assignment]
            tools = self._build_tools(state, rules)
        try:
            snap = self._routing_snapshot(text, rules)
            ns = bench._build_namespace(copy.deepcopy(snap))
            ns.update(tools)
            messages = [{"role": "system", "content": ROUTING_PROMPT},
                        {"role": "user", "content": self._user_message(text, rules)}]
            turns: list[dict] = []
            final_response: Optional[str] = None
            stop_reason = "final"
            for turn_idx in range(self.max_turns):
                state["turn"] = turn_idx
                assistant_text = core._chat(
                    messages, model=self.model, endpoint=self.endpoint,
                    options=self.options, timeout=self.request_timeout)
                state["ollama_calls"] += 1
                blocks = core._extract_blocks(assistant_text)
                turn = {"turn": turn_idx, "assistant": assistant_text,
                        "python_calls": []}
                if not blocks:
                    final_response = assistant_text
                    turn["ended_run"] = True
                    turns.append(turn)
                    stop_reason = "final"
                    break
                tool_outputs: list[str] = []
                for code in blocks:
                    stdout, _v, error = bench._exec_timed(
                        code, ns, self.bench_timeout)
                    turn["python_calls"].append({
                        "code": code, "ok": error is None,
                        "stdout": stdout[:20000],
                        "stdout_truncated": len(stdout) > 20000, "error": error})
                    if stdout:
                        tool_outputs.append(stdout)
                    if error:
                        tool_outputs.append(f"Error: {error}")
                turns.append(turn)
                feedback = "Tool output:\n\n" + "\n\n".join(tool_outputs)
                messages.append({"role": "assistant", "content": assistant_text})
                messages.append({"role": "user", "content": feedback})
            else:
                stop_reason = "max_turns"
                final_response = turns[-1]["assistant"] if turns else ""
        finally:
            core._chat = real_chat
            rulebook.classify = real_classify
            check_duplicate_rule_llm = real_dup  # type: ignore[assignment]

        # derive the route from the first ok ROUTE_TOOL call (S15 discipline)
        route_chosen = "none"
        for inv in state["invocations"]:
            if inv["tool"] in ROUTE_TOOLS and inv["ok"]:
                route_chosen = inv["tool"]
                break
        mg = state["mandatory_gate"]
        # a demotion overrides: the route IS DUPLICATE_RULE even if propose_rule
        # was the first route tool called
        suggested_route = state["route"] or (
            {"file_measurement": "MEASUREMENT", "file_skill": "SKILL_WORKFLOW",
             "file_duplicate_rule": "DUPLICATE_RULE", "propose_rule": "NEW_RULE",
             "reject_conflict": "REJECT_CONFLICT"}.get(route_chosen))
        route_metadata = {
            "restated_rule": state["route_meta"].get("restated_rule"),
            "conflicts_with": state["route_meta"].get("conflicts_with") or [],
            "compatible": state["route_meta"].get("compatible"),
            "mandatory_gate": {"ran": mg["ran"], "caught": mg["caught"],
                               "demoted": mg["demoted"], "restates": mg["restates"]},
            "rule_draft": state["route_meta"].get("rule_draft"),
            "lifecycle_state": state["route_meta"].get("lifecycle_state"),
            "metric": state["route_meta"].get("metric"),
            "procedure": state["route_meta"].get("procedure"),
        }
        # no-interpretation canary on tool return strings
        bad_interp = None
        for inv in state["invocations"]:
            b = concentration._contains_interpretation({"r": inv["result"]})
            if b:
                bad_interp = (inv["tool"], b)
                break
        called_approve_rule = any(inv["tool"] == "approve_rule"
                                  for inv in state["invocations"])

        # append the route line to the backlog (the durable record)
        backlog.append({"kind": "route", "id": imp_id, "at": _now(),
                        "suggested_route": suggested_route,
                        "route_metadata": route_metadata})

        return {
            "schema": "supervisor.routing/v1",
            "imp_id": imp_id, "text": text,
            "suggested_route": suggested_route,
            "route_chosen_tool": route_chosen,
            "route_metadata": route_metadata,
            "mandatory_duplicate_check_ran": mg["ran"],
            "mandatory_gate_caught": mg["caught"],
            "demoted_to_duplicate": mg["demoted"],
            "called_approve_rule": called_approve_rule,
            "canary_no_interpretation": bad_interp is None,
            "canary_no_interpretation_bad": bad_interp,
            "tool_invocations": state["invocations"],
            "turns": turns,
            "final_response": final_response,
            "stop_reason": stop_reason,
            "turn_count": len(turns),
            "ollama_call_count": state["ollama_calls"],
            "model": self.model,
        }

    # -- the human-gated activation step (the only path that grows rulebook.jsonl)

    def activate(self, imp_id: str) -> dict:
        """Activate a proposed NEW_RULE. Requires the proposal to have been
        routed to NEW_RULE with lifecycle_state=proposed and a rule_draft.
        Appends an `activate` line to the backlog AND the rule to rulebook.jsonl
        via rulebook.append_rule. The 5 proven rules are never touched."""
        rec = backlog.get(imp_id)
        if rec is None:
            return {"imp_id": imp_id, "error": "no such proposal in the backlog"}
        if rec.get("activated_at"):
            return {"imp_id": imp_id, "error": "already activated",
                    "rule_id": rec.get("rule_id")}
        route = rec.get("suggested_route")
        rmeta = rec.get("route_metadata") or {}
        if route != "NEW_RULE" or rmeta.get("lifecycle_state") != "proposed":
            return {"imp_id": imp_id,
                    "error": f"not activatable (route={route}, "
                             f"lifecycle_state={rmeta.get('lifecycle_state')})"}
        rule_draft = rmeta.get("rule_draft")
        if not rule_draft:
            return {"imp_id": imp_id, "error": "no rule_draft to activate"}
        rule_id = f"R-{imp_id}"  # unique, tied to the proposal
        statement = rule_draft
        area = "activated"  # the model's rule_draft is the statement; area is a bucket
        entry = {"at": _now(), "seeded": False, "id": rule_id, "area": area,
                 "statement": statement,
                 "provenance": f"activated from {imp_id} by human"}
        backlog.append({"kind": "activate", "id": imp_id, "at": entry["at"],
                         "rule_id": rule_id, "area": area, "statement": statement,
                         "activated_by": "human"})
        rulebook.append_rule(entry)
        return {"imp_id": imp_id, "activated": True, "rule_id": rule_id,
                "area": area, "statement": statement}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- self-test (deterministic, no real model call) --------------------------
# Stubs the three LLM call sites and drives the four canonical routes, mirroring
# S15's stub-first discipline: measurement routes to MEASUREMENT; a duplicate is
# demoted by the mandatory gate and never reaches NEW_RULE/ACTIVE; a novel rule
# proceeds to proposed; a conflict is rejected. Uses a temp backlog + rulebook.

def _stub_chat_factory(scripts: dict):
    def chat_fn(messages, *, model, endpoint, options, timeout):
        user_text = "\n".join(m["content"] for m in messages if m["role"] == "user")
        key = None
        for k in scripts:
            if k in user_text:
                key = k
                break
        turn = sum(1 for m in messages if m["role"] == "assistant")
        seq = scripts.get(key, ["I will route this.\n\n```python\npass\n```"])
        return seq[min(turn, len(seq) - 1)]
    return chat_fn


def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    tmp = Path(tempfile.mkdtemp())
    global_backlog = backlog.BACKLOG_FILE
    backlog.BACKLOG_FILE = tmp / "backlog.jsonl"
    global_rulebook = rulebook.RULEBOOK_FILE
    rulebook.RULEBOOK_FILE = tmp / "rulebook.jsonl"
    rulebook.IMPROVEMENTS_FILE = tmp / "improvements.jsonl"  # avoid reading the real S3 file
    try:
        rules = rulebook.seed_rules(force=True)
        check(len(rules) == 5, "seed the 5 proven rules for the routing test")

        desk = RoutingDesk(options={"temperature": 0.2, "num_ctx": 131072},
                           request_timeout=10, bench_timeout=5, max_turns=4)

        def dup_fn(text, *, rules, model, endpoint, options, request_timeout):
            t = text.lower()
            if "re-confirm" in t and "promotion" in t:
                return {"restates": "R-CONFIRM-VERSION", "raw_response": "stub"}
            if "re-reading state from disk" in t:
                return {"restates": "R-EFFECT-VERIFIED", "raw_response": "stub"}
            return {"restates": None, "raw_response": "stub"}

        def classify_fn(proposal, *, rules, improvements, model, endpoint,
                        options, request_timeout):
            t = proposal.lower()
            if "inherit" in t and "confirmation" in t:
                return {"duplicate_of": None,
                        "conflicts_with": ["R-CONFIRM-VERSION"],
                        "compatible": False, "rationale": "stub: conflicts",
                        "raw_response": "stub"}
            return {"duplicate_of": None, "conflicts_with": [], "compatible": True,
                    "rationale": "stub: compatible", "raw_response": "stub"}

        # raise four proposals
        proposals = {
            "MEAS": "Track per-customer refusal rate over time as a metric.",
            "DUP": "After a promotion, prior confirmations should be re-confirmed "
                   "to avoid stale confirmations.",
            "NEW": "A change to a shared engine used by more than half the fleet "
                   "requires staged/canary verification before fleet-wide rollout.",
            "REJ": "Inherit the prior version's confirmation when promoting, to "
                   "save re-confirmation work.",
        }
        for key, text in proposals.items():
            backlog.append({"kind": "raise", "id": f"IMP-{key}", "at": "t",
                            "source_run": "r", "text": text, "evidence": "ev",
                            "provenance": {}})

        scripts = {
            "Track per-customer refusal rate": [
                '```python\nfile_measurement(text="Track per-customer refusal rate over time as a metric.", metric="per-customer refusal rate")\n```',
                "Done.",
            ],
            "After a promotion, prior confirmations": [
                # the model MISROUTES to propose_rule (the S14 failure); the
                # mandatory gate must demote it to DUPLICATE_RULE.
                'This is a new rule about promotion.\n\n```python\npropose_rule(text="After a promotion, prior confirmations should be re-confirmed to avoid stale confirmations.", evidence="emerged in reps", rule_draft="re-confirm after promotion")\n```',
                "Done.",
            ],
            "A change to a shared engine": [
                '```python\npropose_rule(text="A change to a shared engine used by more than half the fleet requires staged/canary verification before fleet-wide rollout.", evidence="emerged in 20/24 reps", rule_draft="A shared engine change requires staged verification.")\n```',
                "Done.",
            ],
            "Inherit the prior version": [
                '```python\nreject_conflict(text="Inherit the prior version confirmation when promoting.", conflicts_with=["R-CONFIRM-VERSION"])\n```',
                "Done.",
            ],
        }
        chat_fn = _stub_chat_factory(scripts)

        # --- measurement ----------------------------------------------------
        r = desk.route("IMP-MEAS", chat_fn=chat_fn, classify_fn=classify_fn,
                       dup_fn=dup_fn)
        check(r["suggested_route"] == "MEASUREMENT",
              f"measurement routed to MEASUREMENT: {r['suggested_route']}")
        rec = backlog.get("IMP-MEAS")
        check(rec["state"] == "routed", "measurement -> state routed")

        # --- duplicate (misrouted to propose_rule, demoted by the gate) ------
        r = desk.route("IMP-DUP", chat_fn=chat_fn, classify_fn=classify_fn,
                       dup_fn=dup_fn)
        check(r["suggested_route"] == "DUPLICATE_RULE",
              f"duplicate demoted to DUPLICATE_RULE: {r['suggested_route']}")
        check(r["mandatory_duplicate_check_ran"] is True
              and r["mandatory_gate_caught"] is True
              and r["demoted_to_duplicate"] is True,
              "the mandatory gate caught + demoted the misrouted restatement")
        check(r["route_metadata"]["lifecycle_state"] is None,
              "a demoted restatement has no lifecycle_state (never proposed)")
        rec = backlog.get("IMP-DUP")
        check(rec["state"] == "routed" and rec["suggested_route"] == "DUPLICATE_RULE",
              "duplicate -> state routed, route DUPLICATE_RULE (not activatable)")

        # --- new rule (novel -> proposed -> activatable) --------------------
        r = desk.route("IMP-NEW", chat_fn=chat_fn, classify_fn=classify_fn,
                       dup_fn=dup_fn)
        check(r["suggested_route"] == "NEW_RULE",
              f"novel rule routed to NEW_RULE: {r['suggested_route']}")
        check(r["mandatory_duplicate_check_ran"] is True
              and r["mandatory_gate_caught"] is False,
              "the mandatory gate ran on the novel rule and did not catch it")
        check(r["route_metadata"]["lifecycle_state"] == "proposed",
              "novel rule -> lifecycle_state proposed (pending human approval)")
        rec = backlog.get("IMP-NEW")
        check(rec["state"] == "activatable",
              f"NEW_RULE+proposed -> state activatable: {rec['state']}")

        # --- reject conflict -------------------------------------------------
        r = desk.route("IMP-REJ", chat_fn=chat_fn, classify_fn=classify_fn,
                       dup_fn=dup_fn)
        check(r["suggested_route"] == "REJECT_CONFLICT",
              f"conflicting probe routed to REJECT_CONFLICT: {r['suggested_route']}")
        rec = backlog.get("IMP-REJ")
        check(rec["state"] == "routed", "reject -> state routed (not activatable)")

        # --- no-interpretation canary on tool return strings -----------------
        for iid in ("IMP-MEAS", "IMP-DUP", "IMP-NEW", "IMP-REJ"):
            rr = backlog.get(iid)
            # the route_metadata carries no interpretation word
            check(concentration._contains_interpretation(rr["route_metadata"]) is None,
                  f"no interpretation word in {iid} route_metadata")

        # --- activation: the only path that grows rulebook.jsonl -------------
        before_rules = rulebook.load_rules()
        check(len(before_rules) == 5, "rulebook has the 5 proven rules before activation")
        act = desk.activate("IMP-NEW")
        check(act["activated"] is True and act["rule_id"] == "R-IMP-NEW",
              f"activation returned a rule_id: {act}")
        after_rules = rulebook.load_rules()
        check(len(after_rules) == 6,
              f"rulebook grew by one on activation: {len(after_rules)}")
        new_rule = next(r for r in after_rules if r["id"] == "R-IMP-NEW")
        check(new_rule["statement"] == "A shared engine change requires staged verification."
              and new_rule["seeded"] is False,
              f"the activated rule carries the proposal's rule_draft: {new_rule}")
        # the 5 proven rules are untouched
        check([r for r in after_rules if r["seeded"]] == before_rules,
              "the 5 proven rules are byte-identical after activation")
        rec = backlog.get("IMP-NEW")
        check(rec["state"] == "active" and rec["rule_id"] == "R-IMP-NEW",
              f"after activation the proposal is state=active: {rec['state']}")

        # --- a second run now sees the activated rule ------------------------
        rules2 = rulebook.load_rules()
        check(any(r["id"] == "R-IMP-NEW" for r in rules2),
              "a fresh rulebook.load_rules sees the activated rule")

        # --- activation guards: not activatable / already active -----------
        bad1 = desk.activate("IMP-MEAS")
        check("not activatable" in bad1.get("error", ""),
              f"activating a MEASUREMENT is refused: {bad1}")
        bad2 = desk.activate("IMP-DUP")
        check("not activatable" in bad2.get("error", ""),
              f"activating a DUPLICATE_RULE is refused: {bad2}")
        bad3 = desk.activate("IMP-NEW")
        check("already activated" in bad3.get("error", ""),
              f"activating an already-active proposal is refused: {bad3}")
    finally:
        backlog.BACKLOG_FILE = global_backlog
        rulebook.RULEBOOK_FILE = global_rulebook
        rulebook.IMPROVEMENTS_FILE = HERE / "improvements.jsonl"
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (measurement routes to MEASUREMENT / a misrouted "
          "duplicate is demoted by the mandatory gate to DUPLICATE_RULE, never "
          "proposed or activatable / a novel rule proceeds to NEW_RULE+proposed "
          "with the gate running and not catching / a conflict is rejected / the "
          "no-interpretation canary holds on route metadata / activation appends "
          "the rule to rulebook.jsonl and leaves the 5 proven rules intact / a "
          "fresh load sees the activated rule / activation guards refuse "
          "non-NEW_RULE and already-active proposals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)