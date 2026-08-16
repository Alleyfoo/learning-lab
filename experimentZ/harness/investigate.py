#!/usr/bin/env python3
"""INVESTIGATE — the only stage that wakes an LLM, and only on an exception.

```text
run 438 fails the established contract
        -> deterministic exception packet          worker/worker.py
        -> investigator reads ONLY that packet     here
        -> evidence sufficient?  yes -> propose replacements -> v2
                                 no  -> one precise question
```

## What the investigator may return

Replacements, never a model:

```json
{"REPLACEMENTS": [{"source": "staff", "from": "staff_id", "to": "employee_id"}]}
```

`worker.apply_replacements` applies them mechanically, so a proposal cannot
alter a policy or drop a column on the way past. Or it blocks, in the same
structured shape every other stage in this programme blocks in.

## The program is not taking its word for it

A proposed replacement for a join target is checked against Experiment Y's
sufficiency policy before it is applied: the new field must be the SOLE
candidate with complete coverage and unique keys. That is the same rule that
established the binding in the first place, reused, so a repair cannot be
weaker evidence than an original.

Naming is worth nothing here, and that is deliberate. `employee_id` looking like
an identifier is the provenance laundering Experiment T exhibited and U2 closed.
What settles condition A is that the values still line up 4/4 with unique keys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(LAB / "worker"))
sys.path.insert(0, str(LAB / "modeller"))

import pipeline  # noqa: E402  (sufficiency policy, boundary, _w_run)
import worker  # noqa: E402

_w_run = pipeline._w_run

BLOCK_SHAPE = {"CANNOT_ESTABLISH": [
    {"source": "<collection>", "field": "<the declared field that vanished>",
     "binding": "<what you cannot establish>",
     "question": "<the question a human must answer>"}]}

PROMPT = """An established, deterministic worker has just refused a run. You are being
woken only because of this exception. You cannot see the data; everything known
is in the packet below, and every measurement in it was made by a program.

--- BEGIN EXCEPTION PACKET ---
{packet}
--- END EXCEPTION PACKET ---

WHAT THE WORKER IS. A declarative model executed by a fixed engine. It reads the
driving source, looks up a matching row in the other source on a declared join
key, and emits declared columns. It has run {runs} time(s) before this.

YOUR ONLY QUESTION: does this changed world still fit the established task, and
if so what is the smallest change that restores it?

WHAT YOU MAY PROPOSE. Field replacements, and nothing else. You cannot rewrite
the model, add or remove columns, or change a policy:
{replacements}

THE RULE YOU MUST FOLLOW:

A replacement for a load-bearing binding may not be established from a name. A
field being called `employee_id` where `staff_id` used to be is naming evidence,
and naming evidence alone establishes nothing.

MECHANICAL SUFFICIENCY. A candidate relationship is sufficient when it is the
SOLE candidate for that left field having BOTH complete left coverage AND unique
right-side keys. `measured_relationships` in the packet reports exactly this. A
mechanically sufficient candidate IS established by that measurement -- propose
it, and do not ask a human to confirm it.

If two or more candidates are mechanically sufficient, or none is, the
replacement is NOT established. Do not guess and do not propose a partial
repair. Return ONLY:
{block}

Your whole answer must be one JSON object and nothing else."""

REPLACEMENT_SHAPE = {"REPLACEMENTS": [
    {"source": "<collection>", "from": "<field the model declares>",
     "to": "<field that should replace it>"}]}


def prompt(packet: dict) -> str:
    return PROMPT.format(
        packet=json.dumps(packet, indent=2, ensure_ascii=False),
        runs=packet.get("history", {}).get("runs", 0),
        replacements=json.dumps(REPLACEMENT_SHAPE, indent=2),
        block=json.dumps(BLOCK_SHAPE, indent=2))


def _replacements_of(text: str):
    for obj in _w_run._objects(text):
        if isinstance(obj, dict) and isinstance(obj.get("REPLACEMENTS"), list):
            return obj["REPLACEMENTS"]
    return None


def check_replacement(packet: dict, replacements: list, model: dict):
    """The program's own verdict, before anything is applied.

    Returns None when the repair is supported, or the reason it is refused.
    """
    lookup = model.get("lookup") or {}
    driving, into = model.get("driving_source"), lookup.get("into")
    left = f"{driving}.{lookup.get('match_left')}"
    observed = [{"claim": {"candidate_relationship": r}, "status": "OBSERVED",
                 "basis": "value_containment"}
                for r in packet.get("measured_relationships", [])]
    fit = pipeline.sufficiency(observed, left)

    for rep in replacements:
        if rep.get("source") != into or rep.get("from") != lookup.get("match_right"):
            continue                      # not a join repair; nothing to check
        if not fit["established"]:
            return (f"{left} has {len(fit['sufficient'])} mechanically sufficient "
                    f"candidate(s); the replacement is not established by "
                    f"measurement")
        settled = fit["sufficient"][0]["right"]
        proposed = f"{rep.get('source')}.{rep.get('to')}"
        if settled != proposed:
            return (f"the proposed {proposed} is not the mechanically sufficient "
                    f"candidate ({settled})")
    return None


def investigate(est: worker.Established, packet: dict, ask):
    """Returns (replacements, block, refusal). At most one is not None."""
    text = ask(prompt(packet))
    replacements = _replacements_of(text)
    if replacements is not None:
        refusal = check_replacement(packet, replacements, est.model)
        return (None, None, refusal) if refusal else (replacements, None, None)
    return None, _w_run.block_of(text), None


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    model = json.loads((LAB / "worker" / "established" /
                        "timesheet-cost-v1.json").read_text(encoding="utf-8"))

    def packet_for(cond: str) -> dict:
        est = worker.Established("timesheet-cost", 1, model,
                                 LAB / "experimentZ" / "fixtures" / cond,
                                 "2026-08-16")
        out = worker.run(est)
        assert not out.ok, f"{cond} must fail the contract"
        return out.packet

    good = [{"source": "staff", "from": "staff_id", "to": "employee_id"}]

    # --- A: the measurement settles it -------------------------------------
    check(check_replacement(packet_for("A"), good, model) is None,
          f"A: the sole complete unique candidate must be accepted: "
          f"{check_replacement(packet_for('A'), good, model)}")

    # --- CANARY: B has two, so nothing may be applied -----------------------
    why = check_replacement(packet_for("B"), good, model)
    check(why and "2 mechanically sufficient" in why,
          f"CANARY: B must be refused for ambiguity even though the proposal "
          f"names a real field: {why}")

    # --- CANARY: C has none -------------------------------------------------
    why = check_replacement(packet_for("C"), good, model)
    check(why and "0 mechanically sufficient" in why,
          f"CANARY: C must be refused -- nothing to repair with: {why}")

    # --- CANARY: a plausible but unmeasured proposal in A -------------------
    wrong = [{"source": "staff", "from": "staff_id", "to": "name"}]
    why = check_replacement(packet_for("A"), wrong, model)
    check(why and "not the mechanically sufficient candidate" in why,
          f"CANARY: a proposal the measurements do not support must be refused: "
          f"{why}")

    # --- parsing -------------------------------------------------------------
    check(_replacements_of(json.dumps({"REPLACEMENTS": good})) == good,
          "a replacement object must parse")
    check(_replacements_of("I cannot establish this.") is None,
          "prose is not a replacement")
    blocked = json.dumps({"CANNOT_ESTABLISH": [{"source": "staff",
                                                "field": "staff_id",
                                                "question": "which?"}]})
    check(_replacements_of(blocked) is None and _w_run.block_of(blocked),
          "a block is a block, not an empty proposal")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (A's sole complete unique candidate is accepted / B "
          "is refused for ambiguity even though the proposal names a real field "
          "/ C is refused with nothing to repair with / a proposal the "
          "measurements do not support is refused / replacements parse, prose "
          "does not, and a block is not an empty proposal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
