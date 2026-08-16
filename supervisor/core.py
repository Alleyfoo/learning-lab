#!/usr/bin/env python3
"""The supervisor core: a UI-free `review()` that lets an LLM inspect a fleet
snapshot and decide what, if anything, is worth telling the operator.

This is the S1 vertical slice. It deliberately does NOT prescribe an output
schema (report / observation / improvement). We want to see what form the LLM
chooses before we fix one. We preserve the raw response and every tool call.

## The loop

The supervisor gets the snapshot as explicit knowledge (its JSON is in the first
user message) and one optional tool, `run_python`, described in the system
prompt. The tool protocol is text, not native function-calling:

  - to compute something, the model emits a fenced ```python block;
  - we execute it in the bench against a COPY of the snapshot and feed stdout
    (and any error) back as the next user message;
  - when it is ready to answer, it writes plain prose with no code block, and
    that becomes the final response.

Python is never prompted for. Whether and why the model reaches for it is
itself research evidence, so the prompt stays broad.

## Model

Local Ollama, the same `glm-5.2:cloud` the operator console already uses. The
console's model call is the only precedent in this repo, and the standing steer
is local/self-hosted first. No cloud API.

## What a run records

snapshot hash, the frozen prompt, model + settings, every turn (assistant text,
the python blocks it emitted, each block's stdout/error), the final response, an
explicit expectation slot, and a post-run assessment slot left blank for the
human to fill from the evidence.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench  # noqa: E402
import snapshot as snap_mod  # noqa: E402

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/chat"
DEFAULT_MAX_TURNS = 6
BENCH_TIMEOUT = 10.0

# The tool protocol and the authority boundaries. The broad *question* ("you are
# supervising this fleet; tell the operator anything worth their attention...") is
# passed in as `prompt` and kept frozen in s1/prompt.txt so the experiment is
# reproducible and the expected answers are NOT baked into the prompt.
TOOL_PROTOCOL = """\
You have one optional tool for inspecting the fleet: a Python analysis bench.

To run analysis, emit a fenced ```python block. The code runs in a restricted
namespace where the fleet snapshot is available as the variable `snapshot` (a
plain Python dict). `json`, `math`, `re`, `collections` and `pandas` (as `pd`)
are available; other imports are refused. There is no file, shell or network
access. Output you `print` is returned to you.

Use Python only if it helps you decide what is worth the operator's attention.
You do not have to use it.

When you are ready to tell the operator your findings, write plain prose with NO
```python block. That is your final response. If you write prose alongside a
```python block, the prose is noted but the turn continues with the tool call.
"""

BOUNDARIES = """\
You are supervising, not operating. Do not change the fleet. You have read-only
access. Anything you suggest about improving the system is a suggestion to the
operator, not an action you can take.
"""


def _memory_preamble(knowledge: Optional[list], preferences: Optional[list]) -> str:
    """Render the loaded memory as a labelled preamble, or '' if there is none.

    This is Memory v0: load every line and put it in front of the model. No
    retrieval, no scoring. The two classes are kept distinct because system
    knowledge (what the system means) and operator preference (what this operator
    cares about) are different things and must not collapse into one memory.
    """
    parts: list[str] = []
    if knowledge:
        parts.append("System knowledge you have been given -- facts about how this "
                     "system works, true for any operator. Apply them when reading "
                     "fleet state:")
        for entry in knowledge:
            parts.append(f"- {entry.get('statement')}")
    if preferences:
        parts.append("Operator supervision preferences -- what this operator "
                     "considers worth their attention. Respect them when deciding "
                     "what to surface:")
        for entry in preferences:
            parts.append(f"- {entry.get('statement')}")
    return "\n".join(parts) + ("\n\n" if parts else "")


def _chat(messages: list[dict], *, model: str, endpoint: str,
          options: dict, timeout: float) -> str:
    """One round-trip to local Ollama. Returns the assistant message text."""
    payload = json.dumps({"model": model, "messages": messages,
                          "stream": False, "options": options}).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


_PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _extract_blocks(text: str) -> list[str]:
    return [m.group(1) for m in _PYTHON_BLOCK.finditer(text)]


def review(snapshot: dict, prompt: str, *,
           model: str = MODEL, endpoint: str = ENDPOINT,
           max_turns: int = DEFAULT_MAX_TURNS,
           bench_timeout: float = BENCH_TIMEOUT,
           options: Optional[dict] = None,
           request_timeout: float = 600.0,
           knowledge: Optional[list] = None,
           preferences: Optional[list] = None) -> dict:
    """Run the supervisor over `snapshot`. Returns a full run record (UI-free).

    `prompt` is the frozen broad question -- it must NOT encode the expected
    answers. The tool protocol and authority boundaries are added here.

    `knowledge` and `preferences` are the loaded Memory v0 stores. When present
    they are injected as a labelled preamble so the supervisor can apply prior
    system knowledge and operator preferences. When absent the run is exactly the
    S1 baseline. The broad prompt itself never changes.
    """
    opts = options or {"temperature": 0.2}
    snapshot_json = json.dumps(snapshot, indent=2, ensure_ascii=False)
    system = (f"{prompt}\n\n{_memory_preamble(knowledge, preferences)}"
              f"{TOOL_PROTOCOL}\n\n{BOUNDARIES}")
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content":
            "Here is the current fleet snapshot as JSON. Review it and tell the "
            "operator anything you consider worth their attention.\n\n"
            f"{snapshot_json}"},
    ]

    turns: list[dict] = []
    final_response: Optional[str] = None
    stop_reason = "final"
    for turn_idx in range(max_turns):
        assistant_text = _chat(messages, model=model, endpoint=endpoint,
                               options=opts, timeout=request_timeout)
        blocks = _extract_blocks(assistant_text)
        turn = {"turn": turn_idx, "assistant": assistant_text,
                "python_calls": [], "ended_run": False}
        if not blocks:
            final_response = assistant_text
            turn["ended_run"] = True
            turns.append(turn)
            stop_reason = "final"
            break
        # Execute each python block in order; collect outputs to feed back.
        tool_outputs: list[str] = []
        for code in blocks:
            outcome = bench.run(code, snapshot, timeout=bench_timeout)
            turn["python_calls"].append({
                "code": code,
                "ok": outcome["ok"],
                "stdout": outcome["stdout"],
                "stdout_truncated": outcome["stdout_truncated"],
                "error": outcome["error"],
                "refused": outcome["refused"],
            })
            if outcome["error"]:
                tool_outputs.append(f"Error: {outcome['error']}")
            if outcome["stdout"]:
                tool_outputs.append(outcome["stdout"])
            if not outcome["stdout"] and not outcome["error"]:
                tool_outputs.append("(no output)")
        turns.append(turn)
        feedback = "Python bench output:\n\n" + "\n\n".join(tool_outputs)
        messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": feedback})
    else:
        stop_reason = "max_turns"
        final_response = turns[-1]["assistant"] if turns else ""

    python_used = any(t["python_calls"] for t in turns)
    return {
        "schema": "supervisor.run/v1",
        "model": model,
        "endpoint": endpoint,
        "options": opts,
        "max_turns": max_turns,
        "bench_timeout": bench_timeout,
        "snapshot_hash": snap_mod.hash_snapshot(snapshot),
        "prompt": prompt,
        "python_used": python_used,
        "python_call_count": sum(len(t["python_calls"]) for t in turns),
        "turn_count": len(turns),
        "stop_reason": stop_reason,
        "turns": turns,
        "final_response": final_response,
        "expectation": None,       # filled by the harness from the frozen spec
        "assessment": None,        # filled post-run from the evidence
        "elapsed_seconds": None,   # filled by the harness wrapper
    }


def save(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# smoke test (no model call) -- the protocol mechanics, against a stub model
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # block extraction
    blocks = _extract_blocks("here\n```python\nx = 1\nprint(x)\n```\nrest")
    check(blocks == ["x = 1\nprint(x)\n"], f"one python block extracted: {blocks!r}")
    blocks = _extract_blocks("no code here, just prose")
    check(blocks == [], "prose with no block yields no calls")

    # the loop logic with a stub chat that computes then answers
    snap = {"workers": [{"name": "a", "recent_runs": [{"ok": False}]}]}
    calls = {"n": 0, "seen_system": None}

    def stub_chat(messages, *, model, endpoint, options, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            calls["seen_system"] = messages[0]["content"]
            return "Let me count exceptions.\n```python\nprint(sum(1 for w in snapshot['workers'] for r in w['recent_runs'] if not r['ok']))\n```"
        return "There is 1 failed run worth your attention."

    g = globals()
    orig = g["_chat"]
    g["_chat"] = stub_chat
    try:
        rec = review(snap, "You are supervising this fleet.",
                     max_turns=4, request_timeout=10)
    finally:
        g["_chat"] = orig

    check(rec["stop_reason"] == "final", f"run ended on final prose: {rec['stop_reason']}")
    check(rec["python_used"] is True and rec["python_call_count"] == 1,
          f"python was used exactly once: used={rec['python_used']} n={rec['python_call_count']}")
    check(rec["turn_count"] == 2, f"two turns (compute, then answer): {rec['turn_count']}")
    check("1" in rec["turns"][0]["python_calls"][0]["stdout"],
          f"the bench output fed back the count: {rec['turns'][0]['python_calls'][0]['stdout']!r}")
    check("1 failed run" in rec["final_response"],
          f"final prose preserved: {rec['final_response']!r}")
    check(rec["snapshot_hash"], "snapshot hash recorded")
    check(rec["expectation"] is None and rec["assessment"] is None,
          "expectation/assessment slots left blank for the human")

    # --- memory injection: present only when knowledge/preferences given ----
    g2 = globals()

    def capture_chat(messages, *, model, endpoint, options, timeout):
        calls["seen_system"] = messages[0]["content"]
        return "Nothing needs attention."

    g2["_chat"] = capture_chat
    try:
        # no memory -> preamble absent
        calls["seen_system"] = None
        review(snap, "You are supervising.", max_turns=1, request_timeout=10)
        check(calls["seen_system"] is not None
              and "System knowledge you have been given" not in calls["seen_system"]
              and "Operator supervision preferences" not in calls["seen_system"],
              "CANARY: with no memory, the system message has no memory preamble")
        # memory -> preamble present, both classes, broad prompt intact
        calls["seen_system"] = None
        review(snap, "You are supervising this fleet.", max_turns=1,
               request_timeout=10,
               knowledge=[{"statement": "Enrichment is non-committing by design."}],
               preferences=[{"statement": "Do not report thin run history."}])
        sysmsg = calls["seen_system"] or ""
        check("Enrichment is non-committing by design." in sysmsg
              and "Do not report thin run history." in sysmsg
              and "System knowledge you have been given" in sysmsg
              and "Operator supervision preferences" in sysmsg,
              "memory preamble injected with both classes when provided")
        check("You are supervising this fleet." in sysmsg,
              "the broad prompt is unchanged when memory is present")
    finally:
        g2["_chat"] = orig

    # a run that answers immediately, no python
    calls["n"] = 0
    g["_chat"] = lambda *a, **k: "Nothing needs attention."
    try:
        rec = review(snap, "You are supervising.", max_turns=4, request_timeout=10)
    finally:
        g["_chat"] = orig
    check(rec["python_used"] is False and rec["turn_count"] == 1,
          f"immediate prose answer, no python: {rec['python_used']} {rec['turn_count']}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (python blocks extracted / the loop computes then "
          "answers with a stub model / bench output is fed back / final prose is "
          "preserved / snapshot hash and blank expectation+assessment slots "
          "recorded / an immediate no-python answer is captured / memory preamble "
          "is absent with no memory and present with both classes, broad prompt "
          "unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)