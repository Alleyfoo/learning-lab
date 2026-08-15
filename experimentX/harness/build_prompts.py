#!/usr/bin/env python3
"""Experiment X — the same chain, where the missing truth is RELATIONAL.

W showed uncertainty surviving into modelling on a **semantic** binding: which
date field means what. Every block it produced was about a date, which is the
shape the calendar fixtures were built around.

X changes the kind of missing truth and nothing else:

```text
W   semantic binding    which field means the reservation date?
X   relational binding  which product field does orders.item join to?
```

`products` carries **two** complete candidate keys, `sku` and `code`, crossed on
the first two rows. The program can establish mechanically that both contain
every order item (3/3, unique both ways), so neither naming evidence nor value
overlap can discriminate. Joining on either succeeds with nothing missing and
nothing ambiguous — and they select different products:

```text
join on sku    Widget 59.97   Grommet 0.70    Sprocket 10.00
join on code   Grommet 0.30   Widget 139.93   Sprocket 10.00
```

A wrong binding here is not a crash. It is a clean run with wrong money in it,
which is the failure shape this programme has spent its whole length on.

W's boundary is imported unchanged — including its support for a `source` that is
a list, which is what a claim spanning two collections needs. The deterministic
executor is `enrichment/harness/execute_enrichment.py`, also unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
SPEC = ROOT / "spec"
sys.path.insert(0, str(HERE))

import observe  # noqa: E402

_w = Path(LAB / "experimentW" / "harness" / "boundary.py")
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("_w_boundary", _w)
boundary = importlib.util.module_from_spec(_spec)
sys.modules["_w_boundary"] = boundary
_spec.loader.exec_module(boundary)

HUMAN_PURPOSE = ("Enrich each order line with the description and price of the "
                 "product it refers to, and compute the line total as quantity "
                 "multiplied by price.")

SHAPE = [
    {"claim": {"source": "<collection>", "field": "<field name, or null>",
               "meaning": "<what you think it means>"},
     "status": "INFERRED",
     "basis": ["<one or more kinds from the list below>"]},
    {"claim": {"source": "<collection, or a list of collections>",
               "field": "<field name, or null for a whole-collection question>",
               "question": "<what you cannot settle about that subject>"},
     "status": "UNKNOWN",
     "note": "<why it cannot be settled from what you were given>"},
]

INSPECT = """You are the INTERPRETATION stage of a two-stage inspector.

A program has already inspected the data. It produced the OBSERVED facts below by
reading the source structure directly: field names, value types, distinct-value
counts, value shapes, and — for every pair of fields across two sources — what
fraction of one field's values appear in the other's. You did not perform that
inspection and you cannot see the data yourself.

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
the question is about a whole collection. Where a claim genuinely concerns a
relationship between two collections, `source` may be a list of both. A later
processor has to be able to tell what an uncertainty is about.

Return a JSON list of claims and nothing else. The shape:
{shape}

Do not invent fields that are not in the observed facts. Offering a candidate
meaning AND recording what remains unsettled about the same subject is correct
and expected -- they are two claims sharing one subject, not a contradiction."""

SKELETON = {
    "model_version": 1, "model_id": "...", "task": "enrichment",
    "sources": {"orders": {"path": "fixtures/orders.json", "collection": "orders"},
                "products": {"path": "fixtures/products.json",
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
     "field": "<field name, or null>",
     "binding": "<the binding you cannot establish>",
     "claim_status": "<the status of the claim it would rest on>",
     "question": "<the question a human must answer>"}]}

# U2's rule, verbatim, with one sentence added for the relational case. The
# addition states no new principle -- it says that a JOIN KEY is a binding, so
# the existing rule reaches it.
RULE = """A load-bearing binding may not be established from an INFERRED or UNKNOWN
claim without either independent evidence or explicit human confirmation.

Independent evidence may NOT reuse anything already listed in that claim's
`basis`, and may NOT substitute different evidence of the same KIND:

  - Naming evidence is ONE kind. A field name and a collection name are not
    independent of each other. Two names do not add up to a fact.
  - Value-shape and value-overlap evidence establish what values ARE and where
    they appear. They never establish what a field MEANS, and where two
    candidate keys both contain every value, overlap discriminates nothing.
  - Independent evidence means: documentation, another trusted source, or
    explicit human confirmation.

The key a lookup joins on IS a load-bearing binding: it decides which reference
row supplies the output.

A claim marked CONFIRMED is settled. Confirmation resolves that ONE claim and
nothing else -- it does not make neighbouring inferences trustworthy."""


def inspect_prompt(observed: list[dict]) -> str:
    return INSPECT.format(
        observed=json.dumps(observed, indent=2, ensure_ascii=False),
        basis_kinds=json.dumps(list(boundary.BASIS_KINDS), indent=2),
        shape=json.dumps(SHAPE, indent=2))


def model_prompt(report: list[dict], resumed: bool = False) -> str:
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
The `outputs` block is already decided and must be copied unchanged:
{json.dumps(SKELETON, indent=2)}

PERMITTED VALUES:
  driving_source, lookup.into      one of "orders", "products"
  lookup.match_left                a field of the driving source
  lookup.match_right               a field of the looked-up source
  on_missing, on_ambiguous         "refuse_row" or "refuse_run"
  on_non_numeric                   "refuse_row" or "refuse_run"

If a load-bearing binding is NOT supported, do NOT produce a model. Instead
return ONLY this JSON object, naming each blocking claim by its subject so a
human can answer it and the report can be updated mechanically:
{json.dumps(BLOCK_SHAPE, indent=2)}"""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    observed = observe.observed_claims()
    (SPEC / "observed_facts.json").write_text(
        json.dumps(observed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (SPEC / "frozen_prompt_inspect.txt").write_text(inspect_prompt(observed),
                                                    encoding="utf-8")
    (SPEC / "frozen_prompt_model_template.txt").write_text(
        model_prompt([{"claim": {"source": "<from stage 1>"},
                       "status": "<from stage 1>"}]), encoding="utf-8")

    containment = [c["claim"] for c in observed if c["basis"] == "value_containment"
                   and c["claim"]["left"] == "orders.item"]
    print(f"{len(observed)} OBSERVED claims (program-computed)")
    print("the ambiguity, established mechanically:")
    for c in containment:
        print("   " + json.dumps(c, ensure_ascii=False))
    print(f"\ninspect prompt: {len(inspect_prompt(observed))} chars")
    print(f"basis vocabulary reused from V/W unchanged: {list(boundary.BASIS_KINDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
