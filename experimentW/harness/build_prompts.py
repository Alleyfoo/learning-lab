#!/usr/bin/env python3
"""Experiment W — the whole chain, end to end, with real inspection output.

```text
raw data
  -> PROGRAM produces OBSERVED claims                  (U's claims.py, unchanged)
  -> LLM produces INFERRED + UNKNOWN, both addressed   (stage 1, W's boundary)
  -> MODELLER receives all three, referents intact     (stage 2, U2's rule)
  -> load-bearing INFERRED/UNKNOWN -> block, BY REFERENT
  -> human confirms exactly those referents            (mechanical)
  -> MODELLER resumes                                  (stage 3)
```

The difference from U2 is the one that matters: U2's report was hand-built, so
the load-bearing claims were known to the experimenter in advance. Here the
modeller receives **whatever the inspector actually produced**, and the
confirmation step settles exactly what the modeller asked about — nothing chosen
by hand.

U2's rule, skeleton, vocabulary and purpose are imported unchanged. Only the
report's origin differs, which is what makes this a chain test rather than a new
experiment.

The block is structured for the same reason the claims are. A modeller that
blocks in prose cannot have its question answered mechanically, and V has already
shown what happens to anything left in prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
SPEC = ROOT / "spec"
sys.path.insert(0, str(LAB / "experimentU" / "harness"))

import claims as u_claims  # noqa: E402
import boundary  # noqa: E402  (W's own; adds the referent requirement)

# U2's module is also called `build_prompts`, so it is loaded by path.
u2 = boundary._load("_u2_prompts",
                    LAB / "experimentU2" / "harness" / "build_prompts.py")

# UNKNOWN is now structurally parallel to INFERRED. That is the whole fix.
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
reading the source structure directly: field names, value types, a date-shape
regex, and distinct-value counts. You did not perform that inspection and you
cannot see the data yourself.

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
the question is about a whole collection. A later processor has to be able to
tell which field an uncertainty is about. "I don't know what this means" is only
useful if it says what "this" is.

Return a JSON list of claims and nothing else. The shape:
{shape}

Do not invent fields that are not in the observed facts. Offering a candidate
meaning AND recording what remains unsettled about the same field is correct and
expected -- they are two claims sharing one subject, not a contradiction."""

BLOCK_SHAPE = {"CANNOT_ESTABLISH": [
    {"source": "<collection>", "field": "<field name, or null>",
     "binding": "<the binding you cannot establish>",
     "claim_status": "<the status of the claim it would rest on>",
     "question": "<the question a human must answer>"}]}


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
{u2.HUMAN_PURPOSE}

THE RULE YOU MUST FOLLOW:
{u2.RULE}

Not every INFERRED or UNKNOWN claim matters. Only those the job's decisions
actually depend on are load-bearing. Judge which.

If every load-bearing binding is supported, produce the node definition.

THE REQUIRED SHAPE. Fill in every "..." and keep every key exactly as written:
{json.dumps(u2.SKELETON, indent=2)}

`task` must be "reservation" and `model_version` must be 1.
The data files are {json.dumps(u2.FILES, indent=2)}

PERMITTED RULE NAMES (decide which to use, and in what order):
{json.dumps(u2.VOCAB_RULES, indent=2)}

PERMITTED REFUSAL CODES (decide which rule each belongs to):
{json.dumps(u2.VOCAB_REFUSALS, indent=2)}

PERMITTED on_accept VALUE:
"append_to_reservations"

Rules are evaluated in the order you declare them, and the FIRST rule that fails
decides which refusal is reported.

If a load-bearing binding is NOT supported, do NOT produce a node. Instead return
ONLY this JSON object, naming each blocking claim by its subject so a human can
answer it and the report can be updated mechanically:
{json.dumps(BLOCK_SHAPE, indent=2)}"""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    observed = u_claims.observed_claims()
    (SPEC / "observed_facts.json").write_text(
        json.dumps(observed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (SPEC / "frozen_prompt_inspect.txt").write_text(inspect_prompt(observed),
                                                    encoding="utf-8")
    # The stage-2 prompt depends on stage-1 output, so only its TEMPLATE is
    # frozen here -- rendered against a placeholder report so the wording is
    # fixed before any run.
    (SPEC / "frozen_prompt_model_template.txt").write_text(
        model_prompt([{"claim": {"source": "<from stage 1>"},
                       "status": "<from stage 1>"}]), encoding="utf-8")

    print(f"{len(observed)} OBSERVED claims (program-computed, unchanged from U)")
    print(f"inspect prompt: {len(inspect_prompt(observed))} chars")
    print(f"model template: {len((SPEC / 'frozen_prompt_model_template.txt').read_text(encoding='utf-8'))} chars")
    print(f"\nU2 artifacts reused unchanged: RULE({len(u2.RULE)}c), SKELETON, "
          f"VOCAB_RULES={u2.VOCAB_RULES}, FILES={list(u2.FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
