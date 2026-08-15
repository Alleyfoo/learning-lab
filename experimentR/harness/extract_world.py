#!/usr/bin/env python3
"""Extract the node's local world -- structure, not raw files.

The designer's framing: give the model the programmatically extracted data
structure rather than arbitrary raw junk. So this reads the job's sources and
reports what a node needs to know about them -- collection name, element type,
count, and a few examples -- and nothing else.

Deliberately NOT passed on: file paths, the `_note` fields, the full contents.
A node's world is what it receives, and the whole point of the capability
framing is that nothing else exists for it.
"""
from __future__ import annotations

import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
JOB = LAB / "calendar_job"

# Verbatim, as the designer wrote it. Frozen in the preregistration.
HUMAN_DESCRIPTION = (
    "Incoming requests contain a date. This reservation list contains booked "
    "dates. This holiday list contains dates that cannot be booked. Add a "
    "request unless the date is invalid, a holiday or already booked."
)

REQUEST_SHAPE = {"request_date": "string, one per request"}


def _element_type(values: list) -> str:
    kinds = {type(v).__name__ for v in values}
    return kinds.pop() if len(kinds) == 1 else f"mixed({sorted(kinds)})"


def extract(job: Path = JOB) -> dict:
    """The data structure a definition would be written against."""
    sources = {}
    for name, filename, collection in (
            ("holidays", "holidays.json", "holidays"),
            ("reservations", "reservations.json", "reservations")):
        data = json.loads((job / "fixtures" / filename).read_text(encoding="utf-8"))
        values = data[collection]
        sources[name] = {
            "collection": collection,
            "element_type": _element_type(values),
            "count": len(values),
            "examples": values[:3],
        }
    return {"request": REQUEST_SHAPE, "sources": sources,
            "description": HUMAN_DESCRIPTION}


def vocabularies() -> dict:
    """What this node is ALLOWED to say.

    Supplied on purpose (preregistration, "What the LLM is given"): a node's
    world includes its permitted vocabulary. Withholding it would measure
    whether the model can guess private token names, which is not the question.
    """
    import sys

    sys.path.insert(0, str(LAB / "reservation" / "harness"))
    sys.path.insert(0, str(LAB / "taskmodel"))
    import reservation_model as rm

    return {
        "envelope_keys": ["model_version", "model_id", "task", "sources"],
        "task": "reservation",
        "model_version": 1,
        "rules": list(rm.RULES),
        "refusals": list(rm.REFUSALS),
        "on_accept": list(rm.ON_ACCEPT),
        "source_spec": {"path": "<file path>", "collection": "<key in that file>"},
        "note": ("rules are evaluated in the order declared, and the FIRST rule "
                 "that fails decides the refusal"),
    }


def prompt(world: dict, vocab: dict) -> str:
    """The exact text sent to the model. Frozen with the experiment."""
    return f"""You are defining a small deterministic node. Its entire world is below.

THE JOB, as described by the person who wants it:
{world['description']}

WHAT THE NODE RECEIVES, once per run:
{json.dumps(world['request'], indent=2)}

THE DATA IT MAY READ:
{json.dumps(world['sources'], indent=2)}

THE ONLY VOCABULARY YOU MAY USE:
{json.dumps(vocab, indent=2)}

Produce the node definition as JSON. Requirements:
- use only the rule names, refusal names and on_accept value listed above
- `sources` must name each file and the collection inside it; the files are
  "fixtures/holidays.json" and "fixtures/reservations.json"
- every rule needs its refusal reason
- include a short "purpose" string saying what this node is for

Output ONLY the JSON object. No explanation, no markdown fence."""


if __name__ == "__main__":
    w, v = extract(), vocabularies()
    print(prompt(w, v))
