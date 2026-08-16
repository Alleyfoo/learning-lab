#!/usr/bin/env python3
"""S6 -- the SupervisorHarness: one explicit boundary around supervisor execution.

S1-S5 ran the supervisor through `core.review` -- a home-grown agent loop that
mixes prompt assembly, model calls, tool dispatch and recording. S4 and S5
showed the supervisor genuinely performs multi-turn tool-assisted investigation,
but they also exposed repeated runtime/tool mechanics unrelated to supervisory
intelligence -- above all the fresh-Python-namespace `NameError` (the model
assumed bench bindings persist across calls; they do not). Whether that is "the
model misunderstood the tool" or "the harness never stated the tool's semantics"
could not be answered, because there was no explicit tool contract to point at.

S6 wraps what already exists behind a small explicit contract so later
experiments study the supervisor, not the quirks of `core.py`. It is a
refactor/proof round, not a new intelligence experiment.

## The boundary

```
trigger / operator request
         |
     SESSION
         |
SupervisorHarness
   +- context providers      (what the model is given to see)
   +- model interaction      (reuses core._chat -- the existing local-Ollama call)
   +- tool registry          (explicit contracts: name, description, schemas,
   |                          authority class, execute)
   +- tool policy            (ALLOW / NEVER -- authority is bounded and checked)
   +- append-only events     (the session record; reconstructable)
         |
    Supervisor LLM
         |
     0..N steps
         |
   final output / none
```

## Existing code becomes providers/capabilities, it is NOT rewritten

```
snapshot.py  -> FleetContext  (the fleet snapshot as the primary stimulus)
bench.py     -> python_analysis tool  (restricted-namespace analysis of a COPY)
memory.py    -> MemoryContext  (knowledge / preferences / methods preamble)
rulebook.py  -> RulebookContext  (rules / improvement register preamble)
core.py      -> core._chat  (the model round-trip; core.review stays available)
```

`core.review` is untouched and remains the S1-S5 path. The harness is a NEW
path through the same primitives.

## The reconstructability invariant (the DeepSeek-Harness idea we keep)

> Anything model-visible must be reconstructable from the session record.

Every context body, every model request, every model response, every tool call
and result is an append-only event. A `replay(events)` rebuilds the exact
per-turn message lists from events alone -- the self-test asserts it matches
what was actually sent. We do NOT copy DeepSeek's whole event system; we keep
the one idea that matters for a research instrument: the session is a faithful,
reconstructable transcript.

## Tool contracts and the fresh-namespace declaration

A tool has an explicit contract: name, description, input schema, output schema,
authority class, and an `execute`. The `python_analysis` tool's description
STATES the fresh-namespace semantics up front ("each call runs in a fresh
namespace; bindings do not persist; re-bind what you need on every call"). We do
NOT silently turn the bench into a persistent kernel to eliminate the S4/S5
NameError -- that would hide a real tool-semantics question. With the contract
declared, a future NameError is "the model misunderstood the tool" (the contract
said fresh namespace), separable from "the harness failed to state it".

## Authority -- preserve the floor, do not widen it

ALLOW:  read fleet state; analyse a copied snapshot; read knowledge/preferences/
        methods/rules; write supervisor session history; write supervisor-owned
        improvement proposals.
NEVER:  modify workers/models; promote versions; execute production runtime;
        apply effects; alter customer/source data; unrestricted filesystem;
        shell; network.

Harnessing the supervisor must not accidentally give it more power. The policy
checks every registered tool's authority class is in ALLOW and refuses any in
NEVER. The bench's restricted namespace (no open/shell/network, deepcopy of the
snapshot) is the enforcement behind the `analyse_copied_data` class; the policy
is the declarative layer that makes the bound inspectable.
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench  # noqa: E402
import core   # noqa: E402  (reuses core._chat; core.review stays as the legacy path)


# --- authority ---------------------------------------------------------------

# The closed vocabulary of authority classes. A tool or context provider must
# declare one of the ALLOW classes; declaring a NEVER class is refused at
# registration. This is the explicit bound -- harnessing must not widen power.
ALLOW = (
    "read_fleet",            # see fleet state (snapshot)
    "analyse_copied_data",   # run analysis against a deepcopy of the snapshot
    "read_memory",           # read knowledge / preferences / methods
    "read_rulebook",         # read rules / improvement register
    "write_session_log",     # append to the supervisor session record
    "write_improvement_proposals",  # raise supervisor-owned improvement proposals
)
NEVER = (
    "modify_workers", "modify_models", "promote_versions", "execute_runtime",
    "apply_effects", "alter_customer_data", "filesystem_unrestricted",
    "shell", "network",
)

# What the model is told about its authority. Rendered into the system message.
AUTHORITY_TEXT = """\
You are supervising, not operating. Your authority is read-only and bounded.

You MAY: read fleet state; analyse a COPY of the fleet snapshot; read stored
knowledge, preferences, methods and rules; write your own session history; and
raise improvement proposals to the operator.

You MAY NOT: modify workers or models; promote versions; execute production
runtime; apply effects; alter customer or source data; or access the filesystem,
shell or network. Anything you suggest about improving the system is a
suggestion to the operator, not an action you can take. Do not change the fleet.
"""


class PolicyViolation(Exception):
    """A tool or context provider declares an authority class outside ALLOW."""


class Policy:
    """The explicit authority bound. Validates tools and contexts at registration."""

    def __init__(self, allow: tuple = ALLOW, never: tuple = NEVER) -> None:
        self.allow = allow
        self.never = never

    def assert_allowed(self, authority_class: str, what: str, name: str) -> None:
        if authority_class in self.never:
            raise PolicyViolation(
                f"{what} {name!r} declares authority class {authority_class!r} "
                f"which is in NEVER -- harnessing must not widen power")
        if authority_class not in self.allow:
            raise PolicyViolation(
                f"{what} {name!r} declares authority class {authority_class!r} "
                f"which is not in ALLOW {self.allow}")


# --- tools -------------------------------------------------------------------

@dataclass
class Tool:
    """An explicit tool contract.

    `execute(input, state) -> output` where `input` is the parsed tool input and
    `state` is harness-provided session state (e.g. the snapshot for analysis).
    `description` is rendered to the model; it must state the tool's semantics
    honestly (for python_analysis: the fresh-namespace rule).
    """
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    authority_class: str
    execute: Callable[[dict, dict], dict]


def python_analysis_tool(*bench_timeout: float) -> Tool:
    """The built-in analysis tool: bench.run behind an explicit contract.

    The description declares the fresh-namespace semantics up front. This is the
    S6 answer to the S4/S5 NameError: the contract says bindings do not persist,
    so a future NameError is the model misunderstanding a stated contract, not
    the harness failing to state one. The bench is NOT made a persistent kernel.
    """
    timeout = bench_timeout[0] if bench_timeout else 10.0

    def execute(inp: dict, state: dict) -> dict:
        code = inp.get("code", "")
        snap = state.get("snapshot", {})
        return bench.run(code, snap, timeout=timeout)

    return Tool(
        name="python_analysis",
        description=(
            "Run a Python analysis snippet against a COPY of the fleet snapshot "
            "to help you decide what is worth the operator's attention. You do "
            "not have to use it.\n\n"
            "IMPORTANT -- fresh namespace per call: each call runs in a fresh, "
            "INDEPENDENT namespace. Variables, imports and bindings you create "
            "in one call DO NOT persist to the next call. Re-bind anything you "
            "need at the top of EVERY call (for example "
            "`workers = snapshot[\"workers\"]`). Do not assume a variable from a "
            "previous call still exists.\n\n"
            "The snapshot is available as `snapshot` (a plain Python dict). "
            "`json`, `math`, `re`, `collections` and `pandas` (as `pd`) are "
            "available; any other import is refused. There is no file, shell or "
            "network access. Output you `print()` is returned to you.\n\n"
            "To use it, emit a fenced ```python block containing your code. "
            "When you are ready to tell the operator your findings, write plain "
            "prose with NO ```python block -- that ends the session."
        ),
        input_schema={"type": "object",
                      "properties": {"code": {"type": "string"}},
                      "required": ["code"]},
        output_schema={"type": "object",
                      "properties": {
                          "ok": {"type": "boolean"},
                          "stdout": {"type": "string"},
                          "error": {"type": ["string", "null"]},
                          "refused": {"type": "boolean"},
                          "stdout_truncated": {"type": "boolean"}}},
        authority_class="analyse_copied_data",
        execute=execute,
    )


# --- context providers -------------------------------------------------------

@dataclass
class ContextProvider:
    """A source of model-visible context.

    `placement` is "system" (a labelled block appended to the system message,
    e.g. memory / rulebook preambles) or "user" (the primary stimulus rendered
    as the first user message, e.g. the fleet snapshot). `provide()` returns the
    full text; it is recorded verbatim in a `context_added` event so the session
    record reconstructs everything the model saw.
    """
    name: str
    authority_class: str
    placement: str  # "system" | "user"
    provide: Callable[[], str]


def FleetContext(snapshot: dict) -> ContextProvider:
    """The fleet snapshot as the primary stimulus (first user message)."""
    text = json.dumps(snapshot, indent=2, ensure_ascii=False)
    return ContextProvider(
        name="fleet",
        authority_class="read_fleet",
        placement="user",
        provide=lambda: text,
    )


def MemoryContext(knowledge: list, preferences: list,
                  methods: Optional[list] = None) -> ContextProvider:
    """The S2/S3 memory preamble (knowledge / preferences / methods). Reuses
    core._memory_preamble so the rendered text is identical to core.review."""
    def provide() -> str:
        return core._memory_preamble(knowledge, preferences, methods)
    return ContextProvider(
        name="memory",
        authority_class="read_memory",
        placement="system",
        provide=provide,
    )


def RulebookContext(rules: list, improvements: list) -> ContextProvider:
    """The S3 rulebook + improvement register as a system-preamble block."""
    def provide() -> str:
        import rulebook  # local import; rulebook is optional context
        parts = []
        if rules:
            parts.append(rulebook._render_rules(rules))
        if improvements:
            parts.append(rulebook._render_register(improvements))
        return "\n\n".join(parts) + ("\n\n" if parts else "")
    return ContextProvider(
        name="rulebook",
        authority_class="read_rulebook",
        placement="system",
        provide=provide,
    )


# --- the append-only session record ------------------------------------------

# Event types, in the order they appear in a session:
#   session_started, context_added, tools_declared, authority_declared,
#   model_request, model_response, tool_call, tool_result,
#   supervisor_output, session_finished.
EVENT_TYPES = (
    "session_started", "context_added", "tools_declared", "authority_declared",
    "model_request", "model_response", "tool_call", "tool_result",
    "supervisor_output", "session_finished",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EventLog:
    """Append-only event log. Each event: {seq, type, at, turn?, ...payload}.

    The DeepSeek-Harness invariant we keep: anything model-visible is
    reconstructable from this log. `replay()` rebuilds the per-turn message
    lists from events alone -- no external state.
    """

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._seq = 0

    def emit(self, type: str, **payload) -> dict:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type!r}")
        self._seq += 1
        ev = {"seq": self._seq, "type": type, "at": _now()}
        ev.update(payload)
        self._events.append(ev)
        return ev

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in self._events)


# --- reconstructability: replay events -> per-turn messages ------------------

def replay(events: list[dict]) -> list[list[dict]]:
    """Rebuild the exact messages list sent on each model turn, from events ALONE.

    This is the reconstructability invariant made executable: the session record
    is a sufficient description of everything the model saw. System message =
    operator_prompt + system-placement context blocks + tool contracts + the
    authority statement. The first user message = the user-placement context
    block(s). Each subsequent turn appends the prior assistant response and the
    tool-result user message built from tool_call/tool_result events.
    """
    started = next((e for e in events if e["type"] == "session_started"), None)
    operator_prompt = (started or {}).get("operator_prompt", "")
    system_blocks: list[str] = [operator_prompt] if operator_prompt else []
    user_blocks: list[str] = []
    tools_text = ""
    authority_text = ""
    for e in events:
        if e["type"] == "context_added":
            if e.get("placement") == "system":
                system_blocks.append(e["text"])
            else:
                user_blocks.append(e["text"])
        elif e["type"] == "tools_declared":
            tools_text = e.get("text", "")
        elif e["type"] == "authority_declared":
            authority_text = e.get("text", "")
    if tools_text:
        system_blocks.append(tools_text)
    if authority_text:
        system_blocks.append(authority_text)
    system_msg = {"role": "system", "content": "\n\n".join(system_blocks)}
    user_msg = {"role": "user",
                "content": "Here is the current fleet snapshot as JSON. Review it "
                           "and tell the operator anything you consider worth their "
                           "attention.\n\n" + "\n\n".join(user_blocks)}
    messages: list[dict] = [system_msg, user_msg]

    # Walk the turn events in order, reconstructing the messages at the start
    # of each turn and the assistant/user exchanges that follow it.
    per_turn: list[list[dict]] = []
    turn = -1
    i = 0
    evs = [e for e in events if e["type"] in
           ("model_request", "model_response", "tool_call", "tool_result",
            "supervisor_output")]
    while i < len(evs):
        e = evs[i]
        if e["type"] == "model_request":
            turn = e.get("turn", turn + 1)
            per_turn.append([dict(m) for m in messages])  # messages at turn start
            # consume the model_response for this turn
            j = i + 1
            assistant_text = ""
            tool_results: list[str] = []
            while j < len(evs) and evs[j]["type"] in ("model_response", "tool_call",
                                                      "tool_result"):
                if evs[j]["type"] == "model_response":
                    assistant_text = evs[j].get("text", "")
                elif evs[j]["type"] == "tool_result":
                    tool_results.append(evs[j].get("feedback_text", ""))
                j += 1
            messages.append({"role": "assistant", "content": assistant_text})
            if tool_results:
                # each feedback_text already carries its own "Python bench
                # output:" prefix (as recorded in the tool_result event), so
                # join them verbatim -- no extra prefix -- to match run().
                messages.append({"role": "user",
                                 "content": "\n\n".join(tool_results)})
            i = j
        else:
            i += 1
    return per_turn


# --- the harness -------------------------------------------------------------

class SupervisorHarness:
    """One explicit boundary around supervisor execution.

    Construct with tools, context providers and a policy; call `run()` with the
    operator's prompt. Reuses core._chat for the model round-trip and bench.run
    (via the python_analysis tool) for analysis. Emits an append-only EventLog.
    core.review is NOT used and NOT modified -- the harness is a parallel path.
    """

    def __init__(self, *, tools: list[Tool],
                 contexts: list[ContextProvider],
                 policy: Optional[Policy] = None,
                 model: str = core.MODEL, endpoint: str = core.ENDPOINT,
                 options: Optional[dict] = None,
                 request_timeout: float = 600.0,
                 bench_timeout: float = 10.0) -> None:
        self.policy = policy or Policy()
        self.model = model
        self.endpoint = endpoint
        self.options = options or {"temperature": 0.2}
        self.request_timeout = request_timeout
        self.bench_timeout = bench_timeout
        self.tools: dict[str, Tool] = {}
        for t in tools:
            self.policy.assert_allowed(t.authority_class, "tool", t.name)
            self.tools[t.name] = t
        self.contexts: list[ContextProvider] = []
        for c in contexts:
            self.policy.assert_allowed(c.authority_class, "context", c.name)
            self.contexts.append(c)
        # the python_analysis tool must be present (the bench path); required so
        # the model has an analysis surface. Other tools may be added later.
        if "python_analysis" not in self.tools:
            # do not silently add -- the caller declares the tool set explicitly
            pass

    # -- system-message assembly, rendered from contracts (not core's prose) --

    def _render_tools(self) -> str:
        parts = ["You have the following tool(s) available. Each has an explicit "
                 "contract; use a tool only within its stated authority."]
        for t in self.tools.values():
            parts.append(f"\n## tool: {t.name}\nauthority: {t.authority_class}\n"
                         f"{t.description}\n"
                         f"input schema: {json.dumps(t.input_schema)}\n"
                         f"output schema: {json.dumps(t.output_schema)}")
        parts.append("\nTo call a tool, emit a fenced ```python block. When you "
                     "are ready to answer, write plain prose with NO ```python "
                     "block; that is your final response and ends the session.")
        return "\n".join(parts)

    def run(self, operator_prompt: str, *, max_turns: int = 6) -> dict:
        """Run one supervisor session. Returns a session record with the EventLog.

        `operator_prompt` is the broad supervision question (s1/prompt.txt) --
        it must NOT encode expected answers. Context providers supply the rest.
        """
        log = EventLog()
        log.emit("session_started", operator_prompt=operator_prompt,
                 model=self.model, endpoint=self.endpoint,
                 options=self.options, max_turns=max_turns,
                 tool_names=list(self.tools),
                 context_names=[c.name for c in self.contexts])

        # 1. context -- emit each provider's full text (reconstructable).
        system_blocks: list[str] = [operator_prompt] if operator_prompt else []
        user_blocks: list[str] = []
        for c in self.contexts:
            text = c.provide()
            log.emit("context_added", name=c.name,
                     authority_class=c.authority_class, placement=c.placement,
                     text=text)
            if c.placement == "system" and text:
                system_blocks.append(text)
            elif c.placement == "user":
                user_blocks.append(text)

        # 2. tools + authority, declared to the model and recorded as events.
        tools_text = self._render_tools()
        log.emit("tools_declared", text=tools_text,
                 contracts=[{k: v for k, v in {
                     "name": t.name, "authority_class": t.authority_class,
                     "input_schema": t.input_schema,
                     "output_schema": t.output_schema}.items()}
                     for t in self.tools.values()])
        log.emit("authority_declared", text=AUTHORITY_TEXT,
                 allow=list(ALLOW), never=list(NEVER))
        system_blocks.append(tools_text)
        system_blocks.append(AUTHORITY_TEXT)

        system_msg = {"role": "system", "content": "\n\n".join(system_blocks)}
        user_msg = {"role": "user",
                    "content": "Here is the current fleet snapshot as JSON. "
                               "Review it and tell the operator anything you "
                               "consider worth their attention.\n\n"
                               + "\n\n".join(user_blocks)}
        messages: list[dict] = [system_msg, user_msg]

        turns: list[dict] = []
        final_response: Optional[str] = None
        stop_reason = "final"
        state = {"snapshot": _snapshot_from_contexts(self.contexts)}
        for turn_idx in range(max_turns):
            log.emit("model_request", turn=turn_idx,
                     messages=[dict(m) for m in messages])
            t0 = time.time()
            assistant_text = core._chat(
                messages, model=self.model, endpoint=self.endpoint,
                options=self.options, timeout=self.request_timeout)
            elapsed = round(time.time() - t0, 3)
            log.emit("model_response", turn=turn_idx, text=assistant_text,
                     elapsed_seconds=elapsed)
            blocks = core._extract_blocks(assistant_text)
            turn_rec = {"turn": turn_idx, "assistant": assistant_text,
                        "python_calls": [], "ended_run": False}
            if not blocks:
                final_response = assistant_text
                turn_rec["ended_run"] = True
                turns.append(turn_rec)
                log.emit("supervisor_output", turn=turn_idx, text=assistant_text)
                stop_reason = "final"
                break
            tool_outputs: list[str] = []
            for code in blocks:
                log.emit("tool_call", turn=turn_idx, tool_name="python_analysis",
                         input={"code": code})
                outcome = self.tools["python_analysis"].execute(
                    {"code": code}, state)
                # the user-facing feedback text, recorded for reconstruction
                fb_parts = []
                if outcome.get("error"):
                    fb_parts.append(f"Error: {outcome['error']}")
                if outcome.get("stdout"):
                    fb_parts.append(outcome["stdout"])
                if not outcome.get("stdout") and not outcome.get("error"):
                    fb_parts.append("(no output)")
                feedback = "Python bench output:\n\n" + "\n\n".join(fb_parts)
                log.emit("tool_result", turn=turn_idx, tool_name="python_analysis",
                         output=outcome, feedback_text=feedback)
                turn_rec["python_calls"].append({
                    "code": code, "ok": outcome["ok"],
                    "stdout": outcome["stdout"],
                    "stdout_truncated": outcome["stdout_truncated"],
                    "error": outcome["error"], "refused": outcome["refused"]})
                tool_outputs.append(feedback)
            turns.append(turn_rec)
            messages.append({"role": "assistant", "content": assistant_text})
            messages.append({"role": "user", "content": "\n\n".join(tool_outputs)})
        else:
            stop_reason = "max_turns"
            final_response = turns[-1]["assistant"] if turns else ""

        log.emit("session_finished", stop_reason=stop_reason,
                 turn_count=len(turns),
                 python_used=any(t["python_calls"] for t in turns),
                 python_call_count=sum(len(t["python_calls"]) for t in turns))

        # reconstructability canary: replay(events) must equal what was sent.
        replayed = replay(log.events)
        actual = []
        # re-derive the actual per-turn messages from the loop's `messages`
        # history: messages at the start of each turn = the list before the
        # assistant/user append for that turn.
        # (Computed inline during the loop would be cleaner; we recompute here
        # from the recorded model_request events to stay independent of `messages`.)
        # The authoritative comparison is done in the self-test; for the run
        # record we store the replayed length as a canary field.
        return {
            "schema": "supervisor.harness.session/v1",
            "model": self.model,
            "endpoint": self.endpoint,
            "options": self.options,
            "max_turns": max_turns,
            "operator_prompt": operator_prompt,
            "tool_names": list(self.tools),
            "context_names": [c.name for c in self.contexts],
            "authority": {"allow": list(ALLOW), "never": list(NEVER)},
            "stop_reason": stop_reason,
            "turn_count": len(turns),
            "python_used": any(t["python_calls"] for t in turns),
            "python_call_count": sum(len(t["python_calls"]) for t in turns),
            "turns": turns,
            "final_response": final_response,
            "events": log.events,
            "event_log_jsonl": log.to_jsonl(),
            "reconstructability": {
                "replayed_turns": len(replayed),
                "event_count": len(log.events),
            },
        }


def _snapshot_from_contexts(contexts: list[ContextProvider]) -> dict:
    """Recover the snapshot dict a FleetContext was built from, for tool state.

    The FleetContext provider stores the rendered JSON text; the tool needs the
    dict. We parse it back. (The snapshot is pure/deterministic, so this is
    exact.) If no fleet context, tools get {} -- analysis over nothing.
    """
    for c in contexts:
        if c.name == "fleet" and c.placement == "user":
            try:
                return json.loads(c.provide())
            except Exception:
                return {}
    return {}


def save(session: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def save_events_jsonl(session: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session["event_log_jsonl"] + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# self-test (no model call) -- the boundary, the contract, the invariant
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- policy refuses a NEVER-class tool at registration -------------------
    evil = Tool(name="apply_effects_tool", description="writes to the store",
                input_schema={}, output_schema={},
                authority_class="apply_effects", execute=lambda i, s: {})
    try:
        SupervisorHarness(tools=[evil], contexts=[])
        failures.append("CANARY FAILED: a NEVER-authority tool was registered")
    except PolicyViolation:
        pass  # expected
    check(True, "policy refuses a NEVER-authority tool at registration")

    # --- policy refuses an unknown-class tool --------------------------------
    weird = Tool(name="x", description="x", input_schema={}, output_schema={},
                 authority_class="teleport", execute=lambda i, s: {})
    try:
        SupervisorHarness(tools=[weird], contexts=[])
        failures.append("CANARY FAILED: an unknown-authority tool was registered")
    except PolicyViolation:
        pass

    # --- the python_analysis tool contract declares the fresh namespace ------
    pt = python_analysis_tool()
    check("fresh" in pt.description.lower() and "persist" in pt.description.lower(),
          "python_analysis description declares the fresh-namespace semantics")
    check(pt.authority_class == "analyse_copied_data",
          "python_analysis authority class is analyse_copied_data")
    check(pt.execute({"code": "print(1+1)"}, {"snapshot": {}})["stdout"].strip()
          == "2", "python_analysis.execute runs bench.run against the snapshot")

    # --- a full session with a stub model, through the boundary --------------
    snap = {"workers": [{"name": "a", "recent_runs": [{"ok": False}]}]}
    harness = SupervisorHarness(
        tools=[python_analysis_tool()],
        contexts=[FleetContext(snap)],
        options={"temperature": 0.2}, request_timeout=10, bench_timeout=5)
    calls = {"n": 0}

    def stub_chat(messages, *, model, endpoint, options, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return ("Let me count failures.\n```python\n"
                    "workers = snapshot['workers']\n"
                    "print(sum(1 for w in workers for r in w['recent_runs'] if not r['ok']))\n"
                    "```")
        return "There is 1 failed run worth your attention."

    orig = core._chat
    core._chat = stub_chat
    try:
        rec = harness.run("You are supervising this fleet.", max_turns=4)
    finally:
        core._chat = orig

    check(rec["stop_reason"] == "final", f"session ended on final prose: {rec['stop_reason']}")
    check(rec["python_used"] is True and rec["python_call_count"] == 1,
          f"python used exactly once: {rec['python_used']} {rec['python_call_count']}")
    check(rec["turn_count"] == 2, f"two turns (compute, then answer): {rec['turn_count']}")
    check("1 failed run" in (rec["final_response"] or ""),
          f"final prose preserved: {rec['final_response']!r}")

    # --- the append-only event log has the expected shape --------------------
    types = [e["type"] for e in rec["events"]]
    check(types[0] == "session_started" and types[-1] == "session_finished",
          f"events start with session_started and end with session_finished: {types[:1]}{types[-1:]}")
    for need in ("context_added", "tools_declared", "authority_declared",
                 "model_request", "model_response", "tool_call", "tool_result",
                 "supervisor_output"):
        check(need in types, f"event type {need!r} present in the session log")

    # --- RECONSTRUCTABILITY INVARIANT: replay(events) == actual per-turn msgs -
    # Re-derive the actual messages sent on each turn by re-running the loop
    # logic against the recorded events independently, and compare to replay().
    # Simpler and stronger: rebuild actual from the stub's view. We reconstruct
    # the actual per-turn message lists by replaying the same assembly.
    replayed = replay(rec["events"])
    # turn 0 messages: system + user(fleet). The system content must contain the
    # operator prompt, the fresh-namespace declaration, and the authority text.
    sys0 = replayed[0][0]["content"]
    check("You are supervising this fleet." in sys0
          and "fresh" in sys0.lower()
          and "MAY NOT" in sys0,
          "replayed system message contains operator prompt, fresh-namespace "
          "declaration and authority text")
    check(replayed[0][1]["content"].startswith("Here is the current fleet snapshot"),
          "replayed first user message is the fleet stimulus")
    # turn 1 messages must include the turn-0 assistant response + tool result
    check(replayed[1][-2]["role"] == "assistant"
          and "Let me count failures" in replayed[1][-2]["content"],
          "replayed turn-1 messages include the turn-0 assistant response")
    check(replayed[1][-1]["role"] == "user"
          and "1" in replayed[1][-1]["content"],
          "replayed turn-1 messages include the tool-result user message")
    check(len(replayed) == rec["turn_count"],
          f"replay produced one message-list per turn: {len(replayed)} vs {rec['turn_count']}")

    # Stronger reconstructability: the model_request events' messages must equal
    # replay() -- the event log alone is a sufficient description.
    req_msgs = [e["messages"] for e in rec["events"] if e["type"] == "model_request"]
    check(req_msgs == replayed,
          "RECONSTRUCTABILITY CANARY: model_request.messages == replay(events) "
          "-- the session record alone reconstructs everything the model saw")

    # --- authority not widened: the bench still refuses file/shell/network ----
    r = pt.execute({"code": "import os; os.listdir('.')"}, {"snapshot": {}})
    check(not r["ok"] and "os" in (r["error"] or ""),
          "behind the harness, the bench still refuses os (authority not widened)")
    r = pt.execute({"code": "open('x').read()"}, {"snapshot": {}})
    check(not r["ok"], "behind the harness, open() is still unreachable")

    # --- core.review is still importable and unchanged (the legacy path) -----
    check(callable(core.review), "core.review remains available (S1-S5 path intact)")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (policy refuses NEVER/unknown authority tools / "
          "python_analysis contract declares the fresh namespace / a stub session "
          "runs through the boundary / the append-only event log has all event "
          "types / RECONSTRUCTABILITY CANARY: replay(events) == model_request "
          "messages / the bench still refuses os and open behind the harness / "
          "core.review remains available)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)