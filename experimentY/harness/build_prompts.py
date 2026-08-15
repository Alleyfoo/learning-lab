#!/usr/bin/env python3
"""Experiment Y — selective autonomy. Three conditions, one job, one rule.

W and X showed the chain STOPS when a load-bearing fact is unsupported. The
question has flipped: can it avoid stopping when the evidence really does settle
the answer?

```text
A   orders.item -> products.sku   3/3 unique   products.code  2/3 unique
    expected: use sku, NO human confirmation

B   orders.item -> products.sku   2/3 unique   products.code  3/3 unique
    expected: use code, NO human confirmation

C   orders.item -> products.sku   3/3 unique   products.code  3/3 unique
    expected: BLOCK and ask which relationship is intended
```

A and B are mirrors, which is the point: **the field name cannot be the answer.**
The same model has to move its binding when the evidence moves, and refuse when
the evidence stops distinguishing.

## The sufficiency rule is preregistered, not improvised

The model is not asked to decide what counts as enough evidence. The policy says
so before the run, and the model applies it to measurements the program made.

Note the asymmetry the fixtures create, which is why coverage is the right
discriminator: in A and B the wrong key REFUSES a row at runtime, so the mistake
is detectable. In C both keys run clean and a wrong choice is silent. C is the
only condition where blocking is the sole protection.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
SPEC = ROOT / "spec"
sys.path.insert(0, str(LAB / "inspector"))

import observe  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


boundary = _load("_w_boundary", LAB / "experimentW" / "harness" / "boundary.py")

CONDITIONS = ("A", "B", "C")

HUMAN_PURPOSE = ("Enrich each order line with the description and price of the "
                 "product it refers to, and compute the line total as quantity "
                 "multiplied by price.")

SHAPE = [
    {"claim": {"source": "<collection>", "field": "<field name, or null>",
               "meaning": "<what you think it means>"},
     "status": "INFERRED", "basis": ["<kinds from the list below>"]},
    {"claim": {"source": "<collection, or a list of collections>",
               "field": "<field name, or null for a whole-collection question>",
               "question": "<what you cannot settle about that subject>"},
     "status": "UNKNOWN", "note": "<why it cannot be settled>"},
]

INSPECT = """You are the INTERPRETATION stage of a two-stage inspector.

A program has already inspected the data. It produced the OBSERVED facts below by
reading the source structure directly: field names, value kinds, example values,
distinct counts, and — for every pair of fields across two sources — a
`candidate_relationship` reporting how much of the left field's values are
present on the right (`left_coverage`) and whether the right field identifies at
most one row per value (`right_unique`). Those are measurements. The program does
not say which pairing is intended.

--- BEGIN OBSERVED FACTS (produced by the program) ---
{observed}
--- END OBSERVED FACTS ---

Your job is to say what this data probably MEANS, and to be honest about what
cannot be settled from it.

THE ONLY STATUSES AVAILABLE TO YOU:
  INFERRED   your interpretation. Must carry the basis it rests on.
  UNKNOWN    you have no supported interpretation.

BASIS IS A CLOSED VOCABULARY. An INFERRED claim's `basis` must be a list drawn
from exactly these kinds, and nothing else:
{basis_kinds}

EVERY CLAIM MUST NAME ITS SUBJECT. This applies to UNKNOWN exactly as much as to
INFERRED: `source` is required, and `field` is required but may be `null` when
the question is about a whole collection. Where a claim concerns a relationship
between two collections, `source` may be a list of both.

Return a JSON list of claims and nothing else. The shape:
{shape}

Do not invent fields that are not in the observed facts. Offering a candidate
meaning AND recording what remains unsettled about the same subject is correct
and expected."""

SKELETON = {
    "model_version": 1, "model_id": "...", "task": "enrichment",
    "sources": {"orders": {"path": "fixtures/{cond}/orders.json",
                           "collection": "orders"},
                "products": {"path": "fixtures/{cond}/products.json",
                             "collection": "products"}},
    "driving_source": "...",
    "lookup": {"into": "...", "match_left": "...", "match_right": "...",
               "on_missing": "...", "on_ambiguous": "..."},
    "outputs": [
        {"target": "item", "from": "orders", "field": "item"},
        {"target": "description", "from": "products", "field": "description"},
        {"target": "quantity", "from": "orders", "field": "quantity",
         "type": "number"},
        {"target": "price", "from": "products", "field": "price",
         "type": "number"},
        {"target": "line_total", "compute": {
            "op": "multiply",
            "left": {"from": "orders", "field": "quantity"},
            "right": {"from": "products", "field": "price"}}}],
    "on_non_numeric": "...",
}

BLOCK_SHAPE = {"CANNOT_ESTABLISH": [
    {"source": "<collection, or a list of collections>",
     "field": "<field name, or null>", "binding": "<what you cannot establish>",
     "claim_status": "<status of the claim it would rest on>",
     "question": "<the question a human must answer>"}]}

# U2's rule, plus ONE preregistered policy paragraph. The policy states what
# counts as sufficient evidence for a relationship binding, so the model applies
# a stated rule to measurements rather than deciding sufficiency on the fly.
RULE = """A load-bearing binding may not be established from an INFERRED or UNKNOWN
claim without either independent evidence or explicit human confirmation.

Independent evidence may NOT reuse anything already listed in that claim's
`basis`, and may NOT substitute different evidence of the same KIND:

  - Naming evidence is ONE kind. A field name and a collection name are not
    independent of each other. Two names do not add up to a fact.
  - Value-kind and example evidence establish what values ARE, never what a
    field MEANS.
  - Independent evidence means: documentation, another trusted source, explicit
    human confirmation, or the mechanical sufficiency defined below.

The key a lookup joins on IS a load-bearing binding: it decides which reference
row supplies the output.

MECHANICAL SUFFICIENCY FOR A RELATIONSHIP BINDING:

A candidate relationship is MECHANICALLY SUFFICIENT when it is the SOLE candidate
for that left field having BOTH complete left coverage (every left value present
on the right) AND unique right-side keys.

A mechanically sufficient candidate IS established, by OBSERVED evidence. Use it,
and do NOT ask a human to confirm it.

If two or more candidates for the same left field are mechanically sufficient, or
none is, the binding is NOT established: block and ask which is intended.

A claim marked CONFIRMED is settled. Confirmation resolves that ONE claim and
nothing else -- it does not make neighbouring inferences trustworthy."""


def inspect_prompt(observed: list[dict]) -> str:
    return INSPECT.format(
        observed=json.dumps(observed, indent=2, ensure_ascii=False),
        basis_kinds=json.dumps(list(boundary.BASIS_KINDS), indent=2),
        shape=json.dumps(SHAPE, indent=2))


def skeleton_for(cond: str) -> dict:
    return json.loads(json.dumps(SKELETON).replace("{cond}", cond))


def model_prompt(report: list[dict], cond: str, resumed: bool = False) -> str:
    resume = ""
    if resumed:
        resume = ("\nA human has since answered your questions. The claims you "
                  "asked about are now CONFIRMED in the report above; nothing "
                  "else changed.\n")
    return f"""An inspection of some data sources produced the claims below. You did not
perform the inspection and cannot see the data yourself.

Each claim carries its own epistemic status:
  OBSERVED   directly established from the source representation
  INFERRED   the inspector's interpretation, with what it inferred from
  UNKNOWN    no supported interpretation, naming the subject it is about
  CONFIRMED  an external authority resolved an inference or an unknown

--- BEGIN INSPECTION CLAIMS ---
{json.dumps(report, indent=2, ensure_ascii=False)}
--- END INSPECTION CLAIMS ---
{resume}
THE JOB the person wants:
{HUMAN_PURPOSE}

THE RULE YOU MUST FOLLOW:
{RULE}

Not every INFERRED or UNKNOWN claim matters. Only those the job's decisions
actually depend on are load-bearing. Judge which.

If every load-bearing binding is supported, produce the model definition.

THE REQUIRED SHAPE. Fill in every "..." and keep every key exactly as written.
The `sources` and `outputs` blocks are already decided and must be copied
unchanged:
{json.dumps(skeleton_for(cond), indent=2)}

PERMITTED VALUES:
  driving_source, lookup.into      one of "orders", "products"
  lookup.match_left                a field of the driving source
  lookup.match_right               a field of the looked-up source
  on_missing, on_ambiguous         "refuse_row" or "refuse_run"
  on_non_numeric                   "refuse_row" or "refuse_run"

If a load-bearing binding is NOT supported, do NOT produce a model. Instead
return ONLY this JSON object:
{json.dumps(BLOCK_SHAPE, indent=2)}"""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    for cond in CONDITIONS:
        observed = observe.observed_claims(ROOT / "fixtures" / cond)
        (SPEC / f"observed_facts_{cond}.json").write_text(
            json.dumps(observed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (SPEC / f"frozen_prompt_inspect_{cond}.txt").write_text(
            inspect_prompt(observed), encoding="utf-8")
        rels = [c["claim"]["candidate_relationship"] for c in observed
                if "candidate_relationship" in c["claim"]
                and c["claim"]["candidate_relationship"]["left"] == "orders.item"]
        summary = {r["right"].split(".")[1]: (r["left_coverage"], r["right_unique"])
                   for r in rels}
        sufficient = [k for k, (cov, uniq) in summary.items()
                      if cov.split("/")[0] == cov.split("/")[1] and uniq]
        print(f"{cond}: {summary}  -> mechanically sufficient: {sufficient} "
              f"({'PROCEED' if len(sufficient) == 1 else 'BLOCK'} expected)")
    (SPEC / "frozen_prompt_model_template.txt").write_text(
        model_prompt([{"claim": {"source": "<stage 1>"}, "status": "<stage 1>"}], "A"),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
