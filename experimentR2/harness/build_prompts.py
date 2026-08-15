#!/usr/bin/env python3
"""Build the three R2 prompts: same job, same skeleton, PERMUTED vocabulary.

The only thing that differs between probes is the order in which permitted rule
names and refusal codes are listed. Everything else is byte-identical, which is
what makes a difference in the answers attributable to the permutation.

Rules and refusals are listed SEPARATELY and permuted INDEPENDENTLY, so no probe
shows the pairing pre-assembled. R's prompt effectively did show it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
SPEC = HERE.parent / "spec"
sys.path.insert(0, str(LAB / "experimentR" / "harness"))

from extract_world import HUMAN_DESCRIPTION, REQUEST_SHAPE, extract  # noqa: E402

# The real key names, blanked. The designer's sketch used `file`/`on_fail`; a
# skeleton that teaches the wrong socket teaches nothing, so these are the keys
# the validator actually reads.
SKELETON = {
    "model_id": "...",
    "model_version": "...",
    "task": "...",
    "purpose": "...",
    "sources": {"<source name>": {"path": "...", "collection": "..."}},
    "rules": [{"rule": "...", "refusal": "..."}],
    "on_accept": "...",
}

# Independently permuted. Probe C's rule order happens to match the required
# answer and is therefore the probe to distrust; A and B carry the evidence.
PERMUTATIONS = {
    "A": {"rules": ["not_reserved", "date_well_formed", "not_holiday"],
          "refusals": ["HOLIDAY", "ALREADY_RESERVED", "INVALID_DATE"]},
    "B": {"rules": ["not_holiday", "not_reserved", "date_well_formed"],
          "refusals": ["ALREADY_RESERVED", "INVALID_DATE", "HOLIDAY"]},
    "C": {"rules": ["date_well_formed", "not_holiday", "not_reserved"],
          "refusals": ["INVALID_DATE", "HOLIDAY", "ALREADY_RESERVED"]},
}

REQUIRED_ORDER = ["date_well_formed", "not_holiday", "not_reserved"]
REQUIRED_PAIRING = {"date_well_formed": "INVALID_DATE",
                    "not_holiday": "HOLIDAY",
                    "not_reserved": "ALREADY_RESERVED"}


def prompt(probe: str) -> str:
    world = extract()
    vocab = PERMUTATIONS[probe]
    return f"""You are defining a small deterministic node. Its entire world is below.

THE JOB, as described by the person who wants it:
{HUMAN_DESCRIPTION}

WHAT THE NODE RECEIVES, once per run:
{json.dumps(REQUEST_SHAPE, indent=2)}

THE DATA IT MAY READ:
{json.dumps(world['sources'], indent=2)}

The two files are "fixtures/holidays.json" and "fixtures/reservations.json".

THE REQUIRED SHAPE. Fill in every "..." and keep every key exactly as written:
{json.dumps(SKELETON, indent=2)}

`task` must be "reservation" and `model_version` must be 1.

PERMITTED RULE NAMES (you must decide which to use, and in what order):
{json.dumps(vocab['rules'], indent=2)}

PERMITTED REFUSAL CODES (you must decide which rule each belongs to):
{json.dumps(vocab['refusals'], indent=2)}

PERMITTED on_accept VALUE:
"append_to_reservations"

Rules are evaluated in the order you declare them, and the FIRST rule that fails
decides which refusal is reported.

Output ONLY the JSON object. No explanation, no markdown fence."""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    for probe in PERMUTATIONS:
        path = SPEC / f"frozen_prompt_{probe}.txt"
        path.write_text(prompt(probe), encoding="utf-8")
        print(f"wrote {path.name}  (rules listed: {PERMUTATIONS[probe]['rules']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
