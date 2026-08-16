#!/usr/bin/env python3
"""A deliverable manifest for DEFINE. Small, and honest about its scope.

The reconciliation job asked for *"missing from either side OR WHERE THE AMOUNTS
DIFFER"* and produced a matched/missing report. The shape was right, half the
deliverable was gone, and the output was valid, executable and quietly
incomplete — the hardest kind to notice.

## What this does

Each load-bearing clause the definer IDENTIFIES in the request becomes an
addressable obligation. Before a model may be established, every obligation must
be discharged in exactly one of three ways:

```text
construct     it names a referent from the task's own construct INVENTORY
question      it was put to the person, and is waiting on them
unsupported   it cannot be expressed, and says why
```

The teeth are in the first, and they are the TASK's teeth, not this layer's.
**This module knows no paths and no task semantics.** It receives an inventory of
semantic referents that a validated body reports itself as genuinely containing,
and a discharge naming anything outside it fails.

That replaces an earlier dotted-path check which was too weak to be worth much:
a path could resolve to `classify.both_different` — a LABEL — and so discharge
"show me where the amounts differ" for a model containing no comparison at all.
A referent like `compare:Amount` exists only when the comparison does.

## What this does NOT do

**It does not prove the obligations are a complete reading of the prose.** They
come from a model reading a sentence, and nothing here can verify a clause was
not missed. What it prevents is narrower and still worth having: a requirement
that WAS surfaced disappearing on the way to the model.

Under-reading remains uncaught. This closes the gap between *identified* and
*delivered*, not between *asked* and *identified*.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

DISCHARGES = ("construct", "question", "unsupported")

OBLIGATIONS_PROMPT = """Read what a person asked for and list the SEPARATE things they
require of the result. One entry per requirement. Do not merge two requirements
into one entry, and do not invent requirements they did not state.

WHAT THEY SAID:
{goal}

Return only:

{{"OBLIGATIONS": [{{"id": "o1", "clause": "<the requirement, in their terms>"}}]}}"""


def obligations(goal: str, ask, objects) -> list[dict]:
    """Load-bearing clauses the definer identifies. Not proven complete."""
    for obj in objects(ask(OBLIGATIONS_PROMPT.format(goal=goal))):
        if isinstance(obj, dict) and isinstance(obj.get("OBLIGATIONS"), list):
            return [{"id": str(o.get("id") or f"o{i}"),
                     "clause": str(o.get("clause", ""))}
                    for i, o in enumerate(obj["OBLIGATIONS"], 1)
                    if isinstance(o, dict)]
    return []


def resolve_path(model: dict, path: str):
    """Walk a dotted path into the model. None if it is not there."""
    node = model
    for part in str(path).split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
                continue
            except (ValueError, IndexError):
                return None
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def check(obligations_list: list[dict], manifest: dict,
          inventory: Optional[tuple] = None,
          asked: Optional[list] = None) -> list[str]:
    """Problems preventing establishment. Empty means every obligation landed.

    `inventory` is the task's own report of what its validated body contains.
    This function never inspects a model and knows no task vocabulary.
    """
    inventory = tuple(inventory or ())
    problems: list[str] = []
    manifest = manifest or {}
    for obligation in obligations_list:
        oid, clause = obligation["id"], obligation["clause"]
        entry = manifest.get(oid)
        if not isinstance(entry, dict):
            problems.append(f"{oid} undischarged: {clause!r} was identified as "
                            f"required and nothing accounts for it")
            continue
        via = entry.get("via")
        if via not in DISCHARGES:
            problems.append(f"{oid} discharge {via!r} is not one of {DISCHARGES}")
            continue
        if via == "construct":
            referent = str(entry.get("construct") or entry.get("path") or "")
            if referent not in inventory:
                problems.append(
                    f"{oid} claims {clause!r} is met by `{referent}`, which the "
                    f"body does not contain. Available: {list(inventory)}")
        elif via == "question" and not asked:
            problems.append(f"{oid} claims {clause!r} was put to the person, "
                            f"but no question was asked")
        elif via == "unsupported" and not entry.get("reason"):
            problems.append(f"{oid} is unsupported but gives no reason")
    return problems


def _self_test() -> int:
    failures: list[str] = []

    def ok(cond, msg):
        if not cond:
            failures.append(msg)

    LAB = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(LAB / "modeller"))
    import builder

    obs = [{"id": "o1", "clause": "anything missing from either side"},
           {"id": "o2", "clause": "where the amounts differ"}]
    man = {"o1": {"via": "construct", "construct": "peer_presence_classification"},
           "o2": {"via": "construct", "construct": "compare:Amount"}}

    base = LAB / "data"
    model = json.loads((base / "xlsx-statement" / "established_model.json")
                       .read_text(encoding="utf-8"))
    inventory = builder.constructs_of("reconciliation", model, base)
    ok("compare:Amount" in inventory and "match_binding" in inventory
       and "peer_presence_classification" in inventory,
       f"a validated body reports its own constructs: {inventory}")
    ok(check(obs, man, inventory) == [],
       f"both obligations discharge against real referents: "
       f"{check(obs, man, inventory)}")

    # --- THE CANARY: strip compare, KEEP the label ------------------------
    stripped = json.loads(json.dumps(model))
    stripped.pop("compare")
    ok(stripped["classify"].get("both_different"),
       "the canary must keep the LABEL, or it proves nothing")
    # The INVENTORY itself, isolated from validity: the body's own report on
    # the stripped shape. This is the claim under test -- a label surviving must
    # not keep a referent alive.
    import sys as _s
    _s.path.insert(0, str(LAB / "reconciliation" / "harness"))
    _s.path.insert(0, str(LAB / "taskmodel"))
    import reconciliation_model as RM
    import task_model as TM
    direct = RM.constructs(TM.parse(stripped))
    ok("compare:Amount" not in direct,
       f"CANARY: removing compare must remove compare:Amount even though "
       f"classify.both_different remains: {direct}")
    ok("difference_classification" not in direct,
       f"CANARY: and the difference classification with it: {direct}")
    ok("peer_presence_classification" in direct,
       f"…while constructs that ARE still there survive: {direct}")
    problems = check(obs, man, direct)
    ok(len(problems) == 1 and "o2" in problems[0],
       f"CANARY: so exactly the differ-obligation becomes undischargeable: "
       f"{problems}")

    # And through the builder, where validity gates it: an invalid body earns
    # nothing, so EVERY obligation blocks.
    left = builder.constructs_of("reconciliation", stripped, base)

    # --- the task validator rejects it INDEPENDENTLY ----------------------
    report = builder.validate_raw("reconciliation", stripped, base=base)
    ok(not report.valid
       and any("classify_split_mismatch" in str(p) for p in report.problems),
       f"CANARY: the reconciliation validator must reject the malformed model "
       f"on its own: {[str(p) for p in report.problems][:2]}")
    ok(left == (),
       f"an INVALID body reports no constructs at all: {left}")

    # --- the generic layer knows nothing task-specific --------------------
    source = Path(__file__).read_text(encoding="utf-8")
    body = source[source.index("def check("):source.index("def _self_test")]
    for word in ("classify", "match_on", "reconciliation", "compare"):
        ok(word not in body,
           f"CANARY: check() must contain no task vocabulary, found {word!r}")

    ok(check(obs, {"o1": man["o1"]}, inventory),
       "CANARY: an obligation nobody accounts for must block")
    ok(check(obs, {**man, "o2": {"via": "question"}}, inventory, asked=[1]) == [],
       "an obligation waiting on a person discharges")
    ok(check(obs, {**man, "o2": {"via": "question"}}, inventory, asked=[]),
       "CANARY: claiming a question was asked when none was must block")
    ok(check(obs, {**man, "o2": {"via": "unsupported"}}, inventory),
       "CANARY: unsupported without a reason must block")
    ok(check(obs, {**man, "o2": {"via": "unsupported", "reason": "none exists"}},
             inventory) == [], "unsupported WITH a reason is honest")
    ok(check(obs, {**man, "o2": {"via": "magic"}}, inventory),
       "CANARY: an invented discharge kind must block")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (a validated body reports its own constructs and "
          "both obligations discharge / CANARY removing compare removes "
          "compare:Amount even though classify.both_different remains, so the "
          "obligation becomes undischargeable / the reconciliation validator "
          "rejects the malformed model independently with "
          "classify_split_mismatch / an invalid body reports nothing / check() "
          "contains no task vocabulary / unaccounted, unasked, reasonless and "
          "invented discharges all block)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
