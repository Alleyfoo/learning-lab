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
construct     it maps to a path that actually EXISTS in the model
question      it was put to the person, and is waiting on them
unsupported   it cannot be expressed, and says why
```

The teeth are in the first. A discharge claiming `compare` is checked against
the model, so a manifest asserting a requirement was met by a construct that is
not there fails — and an otherwise valid model becomes unestablishable.

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


def check(obligations_list: list[dict], manifest: dict, model: Optional[dict],
          asked: Optional[list] = None) -> list[str]:
    """Problems preventing establishment. Empty means every obligation landed."""
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
            path = entry.get("path", "")
            if model is None or resolve_path(model, path) in (None, [], {}):
                problems.append(
                    f"{oid} claims {clause!r} is met by `{path}`, which is not "
                    f"in the model -- the requirement was identified and then "
                    f"dropped")
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

    obs = [{"id": "o1", "clause": "anything missing from either side"},
           {"id": "o2", "clause": "where the amounts differ"}]
    compared = {"task": "reconciliation",
                "match_on": {"left_field": "Invoice", "right_field": "Their ref"},
                "compare": [{"field": "Amount", "comparison": "exact"}],
                "classify": {"both_same": "matched",
                             "both_different": "amount_differs",
                             "only_left": "a", "only_right": "b"}}
    manifest = {"o1": {"via": "construct", "path": "classify"},
                "o2": {"via": "construct", "path": "compare"}}
    ok(check(obs, manifest, compared) == [],
       f"a model carrying both constructs establishes: "
       f"{check(obs, manifest, compared)}")

    # --- THE CANARY: remove the requested construct, keep everything else ----
    stripped = json.loads(json.dumps(compared))
    stripped.pop("compare")
    stripped["classify"] = {"both": "x", "only_left": "a", "only_right": "b"}
    problems = check(obs, manifest, stripped)
    ok(len(problems) == 1 and "o2" in problems[0] and "compare" in problems[0],
       f"CANARY: an otherwise valid model missing the requested construct must "
       f"be UNESTABLISHABLE: {problems}")

    ok(check(obs, {"o1": manifest["o1"]}, compared),
       "CANARY: an obligation nobody accounts for must block")
    ok(check(obs, {**manifest, "o2": {"via": "question"}}, compared,
             asked=[1]) == [],
       "an obligation waiting on a person is discharged")
    ok(check(obs, {**manifest, "o2": {"via": "question"}}, compared, asked=[]),
       "CANARY: claiming a question was asked when none was must block")
    ok(check(obs, {**manifest, "o2": {"via": "unsupported"}}, compared),
       "CANARY: unsupported without a reason must block")
    ok(check(obs, {**manifest, "o2": {"via": "unsupported",
                                      "reason": "no construct exists"}},
             compared) == [],
       "unsupported WITH a reason is an honest discharge")
    ok(check(obs, {**manifest, "o2": {"via": "magic"}}, compared),
       "CANARY: an invented discharge kind must block")
    ok(resolve_path(compared, "compare.0.field") == "Amount"
       and resolve_path(compared, "compare.0.nope") is None,
       "paths resolve into lists and report absence")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (both constructs present establishes / CANARY an "
          "otherwise valid model missing the requested compare is "
          "unestablishable / an unaccounted obligation blocks / a question "
          "discharges only when one was asked / unsupported needs a reason / an "
          "invented discharge kind blocks / paths resolve into lists)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
