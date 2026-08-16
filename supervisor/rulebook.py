#!/usr/bin/env python3
"""S3 -- the smallest durable Rulebook and Improvement register.

The Rulebook holds a handful of ALREADY-PROVEN architectural rules for the
inherited fleet. It is seeded once and not modified in S3: there is no rule
creation and no promotion of proposals into rules (both deferred). The
Improvement register is an append-only record of proposals a supervisor or
operator raises, each carrying an explicit verdict -- is it a paraphrase of an
improvement already registered, and does it conflict with any rule?

Conflict is allowed but must be EXPLICIT: a conflicting proposal is still
recorded, with `conflicts_with` naming the rule(s). Nothing is implemented
automatically; the register only records and classifies.

Classification is semantic, not positional. The supervisor model judges
duplication (paraphrase) and conflict by meaning, not by wording or by where a
rule sits in the list. The rule-order permutation test in `s3/run.py` proves
conflict selection is not positional.

Two boring stores, same shape as the S2 memory stores:

  supervisor/rulebook.jsonl       seeded rules (id, area, statement, provenance)
  supervisor/improvements.jsonl   registered proposals + verdict + provenance
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

RULEBOOK_FILE = HERE / "rulebook.jsonl"
IMPROVEMENTS_FILE = HERE / "improvements.jsonl"

_JSON_BLOCK = re.compile(r"```json\n?(.*?)```", re.DOTALL)

# A handful of already-proven architectural rules from the inherited floor.
# Each is a closed, canaried property of the deterministic fleet -- not a
# learned practice and not an operator preference. Seeded once; not grown.
SEED_RULES = [
    {"id": "R-CONFIRM-VERSION", "area": "confirmations",
     "statement": "A confirmation is version-bound. A promoted version does not "
                  "inherit a prior version's confirmation, and no retroactive "
                  "authority is granted; the truth must be established again for "
                  "the new version.",
     "provenance": "42b9b24 / 497ac32 -- closed and canaried (v1 untouched when v2 "
                   "answers; v2 gets neither v1's confirmation nor its authority)"},
    {"id": "R-REFUSAL-NOT-EXCEPTION", "area": "exceptions",
     "statement": "A declared refusal under a still-valid binding is the worker "
                  "applying its own on_missing policy. It completes, files as "
                  "processed, and wakes no investigator. A refusal is not an "
                  "exception.",
     "provenance": "fleet/investigation.py --self-test -- permanently canaried"},
    {"id": "R-EFFECT-VERIFIED", "area": "effects",
     "statement": "An effect counts as applied only when verified by re-reading "
                  "state from disk and confirming the change present. A write "
                  "that returned is not evidence of an applied effect.",
     "provenance": "26aa00a -- committing runtime, canaried both ways"},
    {"id": "R-PROMOTION-IMMUTABLE", "area": "versions",
     "statement": "Promotion is append-only and structurally immutable. A new "
                  "version appends and touches nothing earlier; an older "
                  "version's model, runs and history stay byte-identical.",
     "provenance": "fleet -- canaried across promotion"},
    {"id": "R-ITEM-IDENTITY", "area": "inbox",
     "statement": "An inbox work item's identity is the sha256 of its bytes; a "
                  "resend is the same work item and produces no run. Items are "
                  "claimed before they run, so a duplicate produces neither a "
                  "second effect nor a second run.",
     "provenance": "74fd5dc / e6966c9 -- inbox + recovery, canaried"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def _write(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as h:
        for e in entries:
            h.write(json.dumps(e, ensure_ascii=False) + "\n")


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_rules() -> list[dict]:
    return _read(RULEBOOK_FILE)


def load_improvements() -> list[dict]:
    return _read(IMPROVEMENTS_FILE)


def append_improvement(entry: dict) -> dict:
    _append(IMPROVEMENTS_FILE, entry)
    return entry


def seed_rules(*, force: bool = False) -> list[dict]:
    """Seed the rulebook with the proven architectural rules.

    Idempotent: if rules already exist and `force` is false, leave them. With
    `force`, rewrite the file to exactly the seed (used by s3/run.py for a
    reproducible clean slate). This is initialisation, not creation/promotion:
    no rule is ever added from a proposal in S3.
    """
    if not force and load_rules():
        return load_rules()
    RULEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    seeded = [{"at": _now(), "seeded": True, **r} for r in SEED_RULES]
    _write(RULEBOOK_FILE, seeded)
    return seeded


def reset_improvements() -> None:
    if IMPROVEMENTS_FILE.is_file():
        IMPROVEMENTS_FILE.unlink()


def reset() -> None:
    """Clear both stores. s3/run.py reseeds the rulebook after this."""
    reset_improvements()
    if RULEBOOK_FILE.is_file():
        RULEBOOK_FILE.unlink()


# --- classification ---------------------------------------------------------

CLASSIFY_PROMPT = """\
You are the rulebook classifier for a fleet supervisor. You are given the
RULEBOOK (already-proven architectural rules), the REGISTER of improvements
already proposed, and a NEW PROPOSAL. Decide two things, by MEANING not by
wording:

1. DUPLICATE. Is the proposal a paraphrase or restatement of an improvement
   already in the register? A paraphrase is the SAME underlying proposal in
   different words. A genuinely different proposal in the same area is NOT a
   duplicate. If it is a duplicate, put that improvement's id in `duplicate_of`;
   otherwise null.

2. CONFLICT. Does the proposal ADVOCATE something a rule forbids or contradicts?
   - A proposal that respects, references, or operates within a rule is NOT a
     conflict.
   - A proposal that asks to VIOLATE, weaken, or undo a rule IS a conflict.
   Name every conflicting rule id in `conflicts_with`. A compatible proposal
   conflicts with nothing (empty list).

Return ONLY a fenced ```json block in this exact shape:

```json
{
  "duplicate_of": "<improvement_id or null>",
  "conflicts_with": ["<rule_id>", ...],
  "compatible": true,
  "rationale": "<one or two sentences>"
}
```

`compatible` must be true iff `conflicts_with` is empty. Use the exact rule ids
and improvement ids given below.
"""


def _render_rules(rules: list[dict]) -> str:
    if not rules:
        return "(none)"
    return "\n".join(f"- {r['id']} ({r.get('area', '?')}): {r['statement']}"
                     for r in rules)


def _render_register(improvements: list[dict]) -> str:
    if not improvements:
        return "(none yet)"
    return "\n".join(f"- {r['id']}: {r['proposal']}" for r in improvements)


def _parse_verdict(text: str) -> dict:
    m = _JSON_BLOCK.search(text)
    raw = m.group(1) if m else text
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"duplicate_of": None, "conflicts_with": [], "compatible": None,
                "rationale": "", "parse_error": "could not parse JSON from verdict"}
    return obj


def classify(proposal: str, *, rules: list[dict], improvements: list[dict],
             model: str = core.MODEL, endpoint: str = core.ENDPOINT,
             options: Optional[dict] = None,
             request_timeout: float = 300.0) -> dict:
    """Classify one proposal against a rulebook and register (both passed in).

    Returns the verdict: {duplicate_of, conflicts_with, compatible, rationale,
    parse_error?}. Passing the lists in (rather than loading from disk) lets the
    permutation test pass a reordered rulebook to prove conflict selection is
    not positional.
    """
    opts = options or {"temperature": 0.1}
    user = (f"RULEBOOK:\n{_render_rules(rules)}\n\n"
            f"REGISTER:\n{_render_register(improvements)}\n\n"
            f"NEW PROPOSAL:\n{proposal}")
    raw = core._chat(
        [{"role": "system", "content": CLASSIFY_PROMPT},
         {"role": "user", "content": user}],
        model=model, endpoint=endpoint, options=opts, timeout=request_timeout)
    verdict = _parse_verdict(raw)
    verdict["raw_response"] = raw
    return verdict


def register(proposal: str, *, source: str = "s3",
             model: str = core.MODEL, endpoint: str = core.ENDPOINT,
             options: Optional[dict] = None,
             request_timeout: float = 300.0) -> dict:
    """Classify a proposal against the on-disk rulebook + register, then append.

    The proposal is ALWAYS recorded -- conflict and duplicate are explicit
    metadata, never reasons to reject. Nothing is implemented. Returns the
    appended entry (with its IMP id and verdict).
    """
    rules = load_rules()
    improvements = load_improvements()
    verdict = classify(proposal, rules=rules, improvements=improvements,
                       model=model, endpoint=endpoint, options=options,
                       request_timeout=request_timeout)
    imp_id = f"IMP-{len(improvements) + 1:03d}"
    entry = {"at": _now(), "id": imp_id, "source": source, "proposal": proposal,
             "duplicate_of": verdict.get("duplicate_of"),
             "conflicts_with": verdict.get("conflicts_with", []),
             "compatible": verdict.get("compatible"),
             "rationale": verdict.get("rationale"),
             "parse_error": verdict.get("parse_error")}
    append_improvement(entry)
    return entry


# --- self-test --------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    tmp = Path(tempfile.mkdtemp())
    global RULEBOOK_FILE, IMPROVEMENTS_FILE
    rfile, ifile = RULEBOOK_FILE, IMPROVEMENTS_FILE
    RULEBOOK_FILE = tmp / "rulebook.jsonl"
    IMPROVEMENTS_FILE = tmp / "improvements.jsonl"
    try:
        # --- seed is idempotent and writes exactly the proven rules -------
        seeded = seed_rules()
        check(len(seeded) == 5, f"seed writes 5 rules: {len(seeded)}")
        check(len(load_rules()) == 5, "rulebook load round-trips")
        check(len(seed_rules()) == 5 and len(load_rules()) == 5,
              "CANARY: seed is idempotent (no duplication on re-seed without force)")
        check({r["id"] for r in load_rules()} ==
              {"R-CONFIRM-VERSION", "R-REFUSAL-NOT-EXCEPTION", "R-EFFECT-VERIFIED",
               "R-PROMOTION-IMMUTABLE", "R-ITEM-IDENTITY"},
              "the five proven rule ids are present")
        # force re-seed rewrites exactly
        check(len(seed_rules(force=True)) == 5 and len(load_rules()) == 5,
              "force re-seed rewrites to exactly the seed (no growth)")

        # --- classify parses a clean verdict ------------------------------
        good = ('```json\n{"duplicate_of": null, "conflicts_with": '
                '["R-CONFIRM-VERSION"], "compatible": false, "rationale": "x"}\n```')
        v = _parse_verdict(good)
        check(v["conflicts_with"] == ["R-CONFIRM-VERSION"] and v["compatible"] is False,
              f"classify parses a conflict verdict: {v}")
        bad = "no json here"
        vbad = _parse_verdict(bad)
        check(vbad.get("parse_error") and vbad["compatible"] is None,
              "CANARY: a non-JSON verdict surfaces a parse_error and does not claim compatible")

        # --- register appends with the verdict and assigns IMP ids -------
        stub = ('```json\n{"duplicate_of": null, "conflicts_with": [], '
                '"compatible": true, "rationale": "compatible"}\n```')
        g_core = vars(core)
        orig = core._chat
        g_core["_chat"] = lambda *a, **k: stub
        try:
            e1 = register("proposal one", source="test")
            e2 = register("proposal two", source="test")
        finally:
            g_core["_chat"] = orig
        check(e1["id"] == "IMP-001" and e2["id"] == "IMP-002",
              f"register assigns sequential IMP ids: {e1['id']} {e2['id']}")
        check(len(load_improvements()) == 2, "register appends to the store")
        check(e1["compatible"] is True and e1["conflicts_with"] == [],
              "the verdict is carried into the recorded entry")
        check(e1["proposal"] == "proposal one",
              "the original proposal text is preserved (provenance)")

        # --- a duplicate verdict is recorded, not rejected ----------------
        dup = ('```json\n{"duplicate_of": "IMP-001", "conflicts_with": [], '
               '"compatible": true, "rationale": "paraphrase of IMP-001"}\n```')
        g_core["_chat"] = lambda *a, **k: dup
        try:
            e3 = register("proposal one restated", source="test")
        finally:
            g_core["_chat"] = orig
        check(e3["id"] == "IMP-003" and e3["duplicate_of"] == "IMP-001",
              "CANARY: a duplicate is still recorded (append-only) with duplicate_of set -- "
              "nothing is rejected or implemented automatically")

        # --- the register renders for the prompt without ids leaking wrong -
        rendered = _render_register(load_improvements())
        check("IMP-001" in rendered and "proposal one" in rendered,
              "register renders id + proposal for the classifier")

        reset_improvements()
        check(not load_improvements(), "reset_improvements clears the register")
        check(len(load_rules()) == 5, "reset_improvements leaves the rulebook intact")
    finally:
        RULEBOOK_FILE, IMPROVEMENTS_FILE = rfile, ifile
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (seed writes 5 proven rules and is idempotent / force "
          "re-seed rewrites exactly / classify parses a conflict verdict and "
          "surfaces parse errors without claiming compatible / register assigns "
          "IMP ids and carries the verdict / a duplicate is recorded with "
          "duplicate_of, never rejected / reset clears the register only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)