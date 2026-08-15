#!/usr/bin/env python3
"""Build the structured inspection report: one claim, one epistemic status.

Four states, and the discipline lives in the first one:

```text
OBSERVED    directly established from the source representation. BORING by
            design -- a field's name, its type, whether its values match a date
            shape. NOT "the model is confident".
INFERRED    a processor's interpretation. Carries what it was inferred FROM.
UNKNOWN     no supported interpretation available.
CONFIRMED   an external authority resolved an inference. A FOURTH state rather
            than mutating INFERRED into OBSERVED, so history is not rewritten:
            afterwards you can still see it began as a guess.
```

## Why the OBSERVED claims are computed here rather than written

Experiment T's probe 3 laundered an inference into "established from the actual
data". If OBSERVED claims in this report were authored by hand or by a model,
the same laundering would simply move upstream into the report itself. So every
OBSERVED claim below is derived by reading the fixtures: names, types, a date
regex, distinct-value counts. Nothing that requires interpretation is OBSERVED.

## Why the INFERRED and UNKNOWN claims come from S

They are the interpretations Experiment S actually produced, transcribed with
their status attached. **U changes the interface, not the information** -- that
is what makes U and T a paired measurement rather than two different
experiments.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
FIXTURES = LAB / "experimentS" / "fixtures"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def observed_claims() -> list[dict]:
    """Everything the source representation establishes on its own."""
    claims: list[dict] = []
    for filename in sorted(p.name for p in FIXTURES.glob("*.json")):
        data = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
        collection = next(iter(data))
        items = data[collection]

        claims.append({
            "claim": {"source": collection, "fields": sorted(items[0])},
            "status": "OBSERVED", "basis": "source_structure"})

        for field in sorted(items[0]):
            values = [item[field] for item in items if field in item]
            entry = {"source": collection, "field": field,
                     "type": type(values[0]).__name__,
                     "distinct_values": len(set(map(str, values)))}
            if all(isinstance(v, str) and ISO_DATE.match(v) for v in values):
                entry["value_shape"] = "YYYY-MM-DD"
            claims.append({"claim": entry, "status": "OBSERVED",
                           "basis": "measured_from_values"})
    return claims


# Transcribed from Experiment S's own output, with the status it never carried.
# The MEANINGS are S's; only the labelling is new.
INTERPRETED_CLAIMS = [
    {"claim": {"source": "reservations", "field": "date",
               "meaning": "the date the booking is for"},
     "status": "INFERRED", "basis": "field_name"},
    {"claim": {"source": "reservations", "field": "created",
               "meaning": "the date the booking was submitted"},
     "status": "INFERRED", "basis": "field_name"},
    {"claim": {"source": "reservations", "field": "ref",
               "meaning": "an identifier for the reservation"},
     "status": "INFERRED", "basis": "field_name_and_value_pattern"},
    {"claim": {"source": "holidays", "field": "name",
               "meaning": "the name of a holiday"},
     "status": "INFERRED", "basis": "field_name_and_values"},
    {"claim": {"source": "holidays",
               "meaning": "dates on which something is observed or closed"},
     "status": "INFERRED", "basis": "collection_name_and_values"},

    {"claim": {"source": "reservations", "field": "tier", "meaning": "?"},
     "status": "UNKNOWN",
     "note": "values A, B, C carry no self-describing content"},
    {"claim": {"question": "whether a reservation may fall on a holiday"},
     "status": "UNKNOWN",
     "note": "nothing in either source relates the two collections"},
    {"claim": {"question": "what resource is being reserved"},
     "status": "UNKNOWN",
     "note": "no field identifies a room, venue or item"},
    {"claim": {"question": "whether the dates are single-day or the start of "
                           "a multi-day booking"},
     "status": "UNKNOWN",
     "note": "no end-date or duration field exists"},
]


def report(confirmations: dict | None = None) -> list[dict]:
    """The full report. `confirmations` promotes named claims to CONFIRMED.

    Promotion adds a FOURTH state rather than turning INFERRED into OBSERVED --
    afterwards it is still visible that the claim began as a guess, and by whom
    it was settled.
    """
    claims = observed_claims() + [dict(c) for c in INTERPRETED_CLAIMS]
    for key, who in (confirmations or {}).items():
        source, _, field = key.partition(".")
        for claim in claims:
            body = claim["claim"]
            if body.get("source") == source and body.get("field") == field \
                    and claim["status"] == "INFERRED":
                claim["status"] = "CONFIRMED"
                claim["confirmed_by"] = who
                claim["was"] = "INFERRED"
    return claims


def render(claims: list[dict]) -> str:
    return json.dumps(claims, indent=2, ensure_ascii=False)


def main(argv: list[str]) -> int:
    claims = report()
    counts: dict[str, int] = {}
    for claim in claims:
        counts[claim["status"]] = counts.get(claim["status"], 0) + 1
    print(f"{len(claims)} claims: {counts}\n")
    print(render(claims)[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
