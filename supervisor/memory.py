#!/usr/bin/env python3
"""Memory v0 for the supervisor: two boring append-only stores, nothing more.

S1 exposed that the supervisor's failure was not missing memory but missing
*meaning* -- it misread real fleet fields. S2 splits the fix into two classes
that must not collapse into one memory:

  system knowledge   "what does this system mean?"   (true for any operator)
  operator preference "what does this operator care about?" (supervision taste)

So there are two files, `knowledge.jsonl` and `preferences.jsonl`, and a `learn()`
that takes operator feedback prose and distils it into the two classes. Each entry
keeps the original human statement plus the structured interpretation the model
made.

This is deliberately not a framework. No embeddings, no vector store, no
confidence, no decay, no retrieval scoring. Load every line and put it in front
of the model. We have ten lines' worth of memory; let's enjoy that luxury.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import core  # noqa: E402  (reuses the local-Ollama chat helper)

KNOWLEDGE_FILE = HERE / "knowledge.jsonl"
PREFERENCES_FILE = HERE / "preferences.jsonl"
METHODS_FILE = HERE / "methods.jsonl"

_JSON_BLOCK = re.compile(r"```json\n?(.*?)```", re.DOTALL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_knowledge() -> list[dict]:
    return _read(KNOWLEDGE_FILE)


def load_preferences() -> list[dict]:
    return _read(PREFERENCES_FILE)


def load_methods() -> list[dict]:
    return _read(METHODS_FILE)


def append_knowledge(entry: dict) -> dict:
    _append(KNOWLEDGE_FILE, entry)
    return entry


def append_preferences(entry: dict) -> dict:
    _append(PREFERENCES_FILE, entry)
    return entry


def append_method(entry: dict) -> dict:
    _append(METHODS_FILE, entry)
    return entry


def reset() -> None:
    """Clear all stores. S2 runs from a clean slate so it is reproducible.

    Clears knowledge + preferences (S2) and methods (S5). S2 never creates a
    methods file, so clearing it is a no-op for S2 -- backward compatible.
    """
    for p in (KNOWLEDGE_FILE, PREFERENCES_FILE, METHODS_FILE):
        if p.is_file():
            p.unlink()


# --- distillation -----------------------------------------------------------

DISTILL_PROMPT = """\
You are distilling an operator's feedback after a fleet review into two classes
of memory. Read the feedback carefully and split it.

SYSTEM KNOWLEDGE -- facts about how this system works that are true for ANY
operator. These correct the supervisor's understanding of what fleet fields mean.
Example: "enrichment workers are non-committing by design".

OPERATOR PREFERENCE -- what THIS operator wants surfaced or suppressed during
supervision. These are supervision taste, not system facts.
Example: "do not report thin run history by itself".

Return ONLY a fenced ```json block in this exact shape:

```json
{
  "system_knowledge": [
    {"statement": "...", "original": "...", "scope": {"...": "..."}}
  ],
  "operator_preferences": [
    {"statement": "...", "original": "...", "scope": {"...": "..."}}
  ]
}
```

`statement` is your concise distilled claim. `original` is the exact words from
the feedback that this entry distils (provenance). `scope` is a short object
narrowing where it applies, e.g. {"task_type": "enrichment"} or
{"applies": "supervision"} or {"applies": "inbox_ledger"}. Put each distinct idea
in its own entry. If the feedback contains nothing for a class, return an empty
list for it.
"""


def _parse_distillation(text: str) -> dict:
    m = _JSON_BLOCK.search(text)
    raw = m.group(1) if m else text
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"system_knowledge": [], "operator_preferences": [],
                "parse_error": "could not parse JSON from distillation"}
    return obj


def learn(feedback: str, *, run_context: Optional[dict] = None,
          model: str = core.MODEL, endpoint: str = core.ENDPOINT,
          options: Optional[dict] = None, request_timeout: float = 300.0) -> dict:
    """Distil operator `feedback` into system_knowledge + operator_preferences.

    Calls the model, parses the JSON, appends each entry to its store (with
    provenance: basis, the original statement, when, and the run that prompted
    it), and returns the full record. The two classes are written to two files.
    """
    opts = options or {"temperature": 0.1}
    messages = [
        {"role": "system", "content": DISTILL_PROMPT},
        {"role": "user", "content": f"Operator feedback to distil:\n\n{feedback}"},
    ]
    raw = core._chat(messages, model=model, endpoint=endpoint,
                     options=opts, timeout=request_timeout)
    parsed = _parse_distillation(raw)

    knowledge_entries: list[dict] = []
    for item in parsed.get("system_knowledge", []) or []:
        entry = {"at": _now(), "kind": "system_knowledge",
                 "basis": "operator_correction",
                 "statement": item.get("statement", ""),
                 "original": item.get("original", ""),
                 "scope": item.get("scope", {}),
                 "from_run": (run_context or {}).get("run_id")}
        append_knowledge(entry)
        knowledge_entries.append(entry)

    preference_entries: list[dict] = []
    for item in parsed.get("operator_preferences", []) or []:
        entry = {"at": _now(), "kind": "operator_preference",
                 "basis": "operator_feedback",
                 "statement": item.get("statement", ""),
                 "original": item.get("original", ""),
                 "scope": item.get("scope", {}),
                 "from_run": (run_context or {}).get("run_id")}
        append_preferences(entry)
        preference_entries.append(entry)

    return {"feedback": feedback, "raw_response": raw,
            "parse_error": parsed.get("parse_error"),
            "system_knowledge": knowledge_entries,
            "operator_preferences": preference_entries}


# --- three-class distillation (S5): adds supervisory METHOD ------------------
#
# S4 exposed a third kind of lesson the two-class distiller cannot capture: a
# lesson about HOW TO SUPERVISE -- how to investigate, what to check, how to use
# the tools -- learned either from operator feedback ("you missed X; when
# reviewing, consider Y") or from the supervisor's own outcome (a tool error, a
# weak generalisation). Method is prescriptive ("when X, do Y"), distinct from
# knowledge (descriptive: what things mean) and preference (thresholdal: what
# matters). One feedback event can yield entries in several classes at once, so
# learn_multiclass routes a single note into all three stores.

DISTILL_PROMPT_3 = """\
You are distilling an operator's feedback after a fleet review into THREE
classes of memory. Read the feedback carefully and split it -- one sentence may
yield entries in more than one class.

SYSTEM KNOWLEDGE -- facts about how this system works, true for ANY operator.
These correct what fleet fields and fleet structure MEAN.
Example: "a shared executor is a fleet-wide dependency: one shared component can
affect many workers that each look healthy".

OPERATOR PREFERENCE -- what THIS operator wants surfaced or suppressed. These
are supervision taste, not facts and not methods.
Example: "I care about systemic concentration risk and want it flagged".

SUPERVISORY METHOD -- a lesson about HOW to supervise well: what to check, how to
investigate, how to use the analysis tools. These are PRESCRIPTIVE ("when X, do
Y"), not facts and not taste. Abstract them away from the specific occasion so
they transfer to new situations -- do NOT tie a method to the particular worker,
field name or component that triggered it.
Example: "during fleet review, consider shared dependencies and concentration
across dependency dimensions, not only individual worker health".

Return ONLY a fenced ```json block in this exact shape:

```json
{
  "system_knowledge": [
    {"statement": "...", "original": "...", "scope": {"...": "..."}}
  ],
  "operator_preferences": [
    {"statement": "...", "original": "...", "scope": {"...": "..."}}
  ],
  "supervisory_methods": [
    {"statement": "...", "original": "...", "scope": {"...": "..."}}
  ]
}
```

`statement` is your concise distilled claim. `original` is the exact words from
the feedback that this entry distils (provenance). `scope` is a short object
narrowing where it applies. Put each distinct idea in its own entry. If the
feedback contains nothing for a class, return an empty list for it. A method
statement must be ABSTRACT: it must not name the specific component that
triggered the lesson (e.g. do not write "count engines" -- write "consider
shared-dependency concentration").
"""


def learn_multiclass(feedback: str, *, run_context: Optional[dict] = None,
                     model: str = core.MODEL, endpoint: str = core.ENDPOINT,
                     options: Optional[dict] = None,
                     request_timeout: float = 300.0) -> dict:
    """Distil `feedback` into system_knowledge + operator_preferences +
    supervisory_methods, routing each entry to its own store.

    One feedback event may populate several classes. The method class is the S5
    addition; knowledge and preference are the S2 classes, unchanged. Returns
    the full record with provenance.
    """
    opts = options or {"temperature": 0.1}
    messages = [
        {"role": "system", "content": DISTILL_PROMPT_3},
        {"role": "user", "content": f"Operator feedback to distil:\n\n{feedback}"},
    ]
    raw = core._chat(messages, model=model, endpoint=endpoint,
                     options=opts, timeout=request_timeout)
    parsed = _parse_distillation(raw)

    knowledge_entries: list[dict] = []
    for item in parsed.get("system_knowledge", []) or []:
        entry = {"at": _now(), "kind": "system_knowledge",
                 "basis": "operator_correction",
                 "statement": item.get("statement", ""),
                 "original": item.get("original", ""),
                 "scope": item.get("scope", {}),
                 "from_run": (run_context or {}).get("run_id")}
        append_knowledge(entry)
        knowledge_entries.append(entry)

    preference_entries: list[dict] = []
    for item in parsed.get("operator_preferences", []) or []:
        entry = {"at": _now(), "kind": "operator_preference",
                 "basis": "operator_feedback",
                 "statement": item.get("statement", ""),
                 "original": item.get("original", ""),
                 "scope": item.get("scope", {}),
                 "from_run": (run_context or {}).get("run_id")}
        append_preferences(entry)
        preference_entries.append(entry)

    method_entries: list[dict] = []
    for item in parsed.get("supervisory_methods", []) or []:
        entry = {"at": _now(), "kind": "supervisory_method",
                 "basis": "operator_feedback",
                 "statement": item.get("statement", ""),
                 "original": item.get("original", ""),
                 "scope": item.get("scope", {}),
                 "from_run": (run_context or {}).get("run_id")}
        append_method(entry)
        method_entries.append(entry)

    return {"feedback": feedback, "raw_response": raw,
            "parse_error": parsed.get("parse_error"),
            "system_knowledge": knowledge_entries,
            "operator_preferences": preference_entries,
            "supervisory_methods": method_entries}


# --- self-test --------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # point the stores at a temp dir so the real files are untouched
    tmp = Path(tempfile.mkdtemp())
    global KNOWLEDGE_FILE, PREFERENCES_FILE, METHODS_FILE
    kfile, pfile, mfile = KNOWLEDGE_FILE, PREFERENCES_FILE, METHODS_FILE
    KNOWLEDGE_FILE = tmp / "knowledge.jsonl"
    PREFERENCES_FILE = tmp / "preferences.jsonl"
    METHODS_FILE = tmp / "methods.jsonl"
    try:
        # --- stores round-trip and reset ----------------------------------
        append_knowledge({"at": "t", "kind": "system_knowledge",
                          "statement": "X", "original": "x", "scope": {}})
        append_preferences({"at": "t", "kind": "operator_preference",
                            "statement": "Y", "original": "y", "scope": {}})
        check(len(load_knowledge()) == 1 and len(load_preferences()) == 1,
              "append then load round-trips")
        reset()
        check(not load_knowledge() and not load_preferences(),
              "CANARY: reset clears both stores")

        # --- learn() distils and classifies with a stub model -------------
        stub_response = (
            '```json\n'
            '{"system_knowledge": ['
            '  {"statement": "Enrichment workers are non-committing by design.",'
            '   "original": "Non-committing is normal for enrichment",'
            '   "scope": {"task_type": "enrichment"}},'
            '  {"statement": "Inbox ledger lines are lifecycle entries, not output row counts.",'
            '   "original": "Ledger lines aren\'t output rows",'
            '   "scope": {"applies": "inbox_ledger"}}],'
            ' "operator_preferences": ['
            '  {"statement": "Do not report thin run history by itself.",'
            '   "original": "I don\'t need warnings merely because a new healthy worker has little history",'
            '   "scope": {"applies": "supervision"}},'
            '  {"statement": "Do not suggest exercising refusal conditions during ordinary review.",'
            '   "original": "or hasn\'t exercised every refusal condition",'
            '   "scope": {"applies": "supervision"}}]}'
            '\n```')
        g = globals()
        orig_chat = core._chat
        g_core = vars(core)
        g_core["_chat"] = lambda *a, **k: stub_response
        try:
            rec = learn("Non-committing is normal for enrichment; that isn't a "
                        "concern. Ledger lines aren't output rows. I don't need "
                        "warnings merely because a new healthy worker has little "
                        "history or hasn't exercised every refusal condition.",
                        run_context={"run_id": "before-1"})
        finally:
            g_core["_chat"] = orig_chat

        check(len(rec["system_knowledge"]) == 2,
              f"two knowledge entries distilled: {len(rec['system_knowledge'])}")
        check(len(rec["operator_preferences"]) == 2,
              f"two preference entries distilled: {len(rec['operator_preferences'])}")
        # the two classes went to two different files
        check(len(load_knowledge()) == 2 and len(load_preferences()) == 2,
              "CANARY: the two classes are stored in separate files, not one")
        # provenance preserved
        k0 = load_knowledge()[0]
        check(k0["basis"] == "operator_correction" and k0["original"]
              and k0["from_run"] == "before-1",
              f"knowledge entry carries basis/original/from_run: {k0}")
        p0 = load_preferences()[0]
        check(p0["basis"] == "operator_feedback" and p0["original"],
              f"preference entry carries basis/original: {p0}")
        # the classes are genuinely distinct in content
        check(any("non-committing" in e["statement"] for e in load_knowledge()),
              "the system-knowledge correction about non-committing landed")
        check(any("thin run history" in e["statement"] for e in load_preferences()),
              "the operator-preference about thin history landed")

        # --- learn_multiclass() distils into THREE classes with a stub -------
        reset()
        check(not load_knowledge() and not load_preferences() and not load_methods(),
              "CANARY: reset clears all three stores")
        stub3 = (
            '```json\n'
            '{"system_knowledge": ['
            '  {"statement": "A shared executor is a fleet-wide dependency: one shared component can affect many workers that each look healthy.",'
            '   "original": "most of the fleet depended on the same executor",'
            '   "scope": {"applies": "fleet_structure"}}],'
            ' "operator_preferences": ['
            '  {"statement": "I care about systemic concentration risk and want it flagged.",'
            '   "original": "That is something I care about because it is systemic concentration risk",'
            '   "scope": {"applies": "supervision"}}],'
            ' "supervisory_methods": ['
            '  {"statement": "During fleet review, consider shared dependencies and concentration across dependency dimensions, not only individual worker health.",'
            '   "original": "When reviewing the fleet, do not only look for failing workers; consider shared dependencies and concentration",'
            '   "scope": {"applies": "fleet_review"}}]}'
            '\n```')
        g_core["_chat"] = lambda *a, **k: stub3
        try:
            rec = learn_multiclass(
                "You missed a systemic risk: most of the fleet depended on the "
                "same executor. When reviewing the fleet, do not only look for "
                "failing workers; consider shared dependencies and concentration. "
                "That is something I care about because it is systemic "
                "concentration risk.",
                run_context={"run_id": "s4-c5"})
        finally:
            g_core["_chat"] = orig_chat

        check(len(rec["system_knowledge"]) == 1
              and len(rec["operator_preferences"]) == 1
              and len(rec["supervisory_methods"]) == 1,
              "one entry per class distilled from one feedback note")
        check(len(load_knowledge()) == 1 and len(load_preferences()) == 1
              and len(load_methods()) == 1,
              "CANARY: the three classes are stored in three separate files")
        m0 = load_methods()[0]
        check(m0["kind"] == "supervisory_method" and m0["basis"] == "operator_feedback"
              and m0["from_run"] == "s4-c5",
              f"method entry carries kind/basis/from_run: {m0}")
        # the method is ABSTRACT -- not tied to the triggering component
        check("executor" not in m0["statement"].lower()
              and "engine" not in m0["statement"].lower(),
              f"CANARY: method statement is abstract (no 'engine'/'executor'): {m0['statement']}")
        check(any("shared" in e["statement"].lower() for e in load_methods()),
              "the method about shared-dependency concentration landed")
    finally:
        KNOWLEDGE_FILE, PREFERENCES_FILE, METHODS_FILE = kfile, pfile, mfile
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (stores round-trip and reset / learn() distils "
          "operator feedback into system_knowledge + operator_preferences / the "
          "two classes are stored in separate files / provenance basis, original "
          "and from_run are preserved / the correction about non-committing lands "
          "in knowledge and the thin-history preference lands in preferences / "
          "learn_multiclass() distils one note into THREE classes stored in three "
          "files / reset clears all three / the method statement is abstract with "
          "no 'engine'/'executor')")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)