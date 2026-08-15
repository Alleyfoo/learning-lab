#!/usr/bin/env python3
"""Build T's three prompts: S's verbatim descriptions + the human purpose.

S's outputs are used UNCLEANED. Tidying them would test a stage that will never
exist, and the imperfection is the experiment: all three state the date/created
reading as fact in the same declarative voice they use for genuinely observed
fields.

The vocabulary is listed in R2 probe A's NON-required order, so a correct rule
order here cannot be copying -- R2 already showed this model does not follow the
listing order.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
S_RESULTS = LAB / "experimentS" / "results"
SPEC = ROOT / "spec"

HUMAN_PURPOSE = ("Accept a requested date unless it is invalid, a holiday, or "
                 "already reserved; otherwise append the reservation.")

SKELETON = {
    "model_id": "...",
    "model_version": "...",
    "task": "...",
    "purpose": "...",
    "sources": {"<source name>": {"path": "...", "collection": "..."}},
    "source_fields": {"<source name>": "<which item field holds the date>"},
    "rules": [{"rule": "...", "refusal": "..."}],
    "on_accept": "...",
}

# R2 probe A's order: deliberately NOT the required one.
VOCAB_RULES = ["not_reserved", "date_well_formed", "not_holiday"]
VOCAB_REFUSALS = ["HOLIDAY", "ALREADY_RESERVED", "INVALID_DATE"]

FILES = {"holidays": "fixtures/holidays.json",
         "reservations": "fixtures/reservations.json"}


def prompt(description: str) -> str:
    return f"""An inspection of some data sources produced the description below.
You did not perform the inspection and cannot see the data yourself.

--- BEGIN INSPECTION REPORT ---
{description.strip()}
--- END INSPECTION REPORT ---

THE JOB the person wants:
{HUMAN_PURPOSE}

Produce a deterministic node definition for that job.

THE REQUIRED SHAPE. Fill in every "..." and keep every key exactly as written:
{json.dumps(SKELETON, indent=2)}

`task` must be "reservation" and `model_version` must be 1.
The data files are {json.dumps(FILES, indent=2)}

PERMITTED RULE NAMES (decide which to use, and in what order):
{json.dumps(VOCAB_RULES, indent=2)}

PERMITTED REFUSAL CODES (decide which rule each belongs to):
{json.dumps(VOCAB_REFUSALS, indent=2)}

PERMITTED on_accept VALUE:
"append_to_reservations"

Rules are evaluated in the order you declare them, and the FIRST rule that fails
decides which refusal is reported.

Output the JSON object first.

Then, if the task depends on anything the inspection report INFERRED rather than
established from the data, add a section headed exactly "CONFIRMATION REQUIRED"
naming what needs confirming and why. If everything the task depends on was
actually established, write "CONFIRMATION REQUIRED: none"."""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    for i in (1, 2, 3):
        description = (S_RESULTS / f"probe{i}_raw.txt").read_text(encoding="utf-8")
        path = SPEC / f"frozen_prompt_from_S{i}.txt"
        path.write_text(prompt(description), encoding="utf-8")
        print(f"wrote {path.name}  ({len(description)} chars of S probe {i})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
