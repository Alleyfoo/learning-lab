#!/usr/bin/env python3
"""Extract the structure of the S sources and build the frozen prompt.

Structure only -- collection, count, fields, types, examples. Nothing is said
about what any file is FOR. The whole question is whether that can be inferred,
so telling it would answer the question in the prompt, which is the mistake
Experiment R made with rule order.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = ROOT / "fixtures"
SPEC = ROOT / "spec"

# Deliberately alphabetical, so the reservations/holidays reading order carries
# no hint about which constrains which.
SOURCE_FILES = ("holidays.json", "incoming_request.json", "reservations.json")


def _field_summary(items: list[dict]) -> dict:
    fields: dict[str, dict] = {}
    for item in items:
        for key, value in item.items():
            entry = fields.setdefault(key, {"type": type(value).__name__,
                                            "examples": [], "distinct": set()})
            if len(entry["examples"]) < 3:
                entry["examples"].append(value)
            entry["distinct"].add(str(value))
    for entry in fields.values():
        entry["distinct_values"] = len(entry.pop("distinct"))
    return fields


def extract() -> dict:
    out = {}
    for filename in SOURCE_FILES:
        data = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
        collection = next(iter(data))
        items = data[collection]
        out[filename] = {"collection": collection, "item_count": len(items),
                         "fields": _field_summary(items)}
    return out


def prompt(structure: dict) -> str:
    return f"""Below is the programmatically extracted structure of three data sources.
You have not been told what any of them are for.

{json.dumps(structure, indent=2, ensure_ascii=False)}

Tell me what these sources appear to contain. For each one:
- name the collection and its fields
- say what you think each field represents
- say what you think each item represents

Then, in a clearly separated section headed exactly "CANNOT DETERMINE", list
anything you cannot work out from this data alone. Be specific about which
field or which pair of fields, and say what the open question is.

If something IS determinable, do not put it in that section. Only list genuine
ambiguity.

Write for a person to read. Do not produce JSON, a schema, or code."""


def main(argv: list[str]) -> int:
    structure = extract()
    SPEC.mkdir(exist_ok=True)
    text = prompt(structure)
    (SPEC / "frozen_prompt.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
