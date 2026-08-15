#!/usr/bin/env python3
"""Experiment U2 — the same probes, with independent evidence DEFINED.

U's hole: a claim `INFERRED` with `basis: field_name` was then argued to be
"independently supported by OBSERVED evidence: the field is named date". The
basis of the inference re-used as corroboration of it.

Two changes from U, both small and both forced by an observed failure:

```text
1  independent evidence is DEFINED, and defined to exclude the claim's own
   basis AND any other evidence of the same KIND
2  phase 2 confirms BOTH load-bearing inferred claims, not one
```

Change 2 exists because U probe 1 caught the experiment short: it correctly
blocked a second time on the `holidays` meaning, which was still INFERRED. That
was right behaviour, and it demonstrated the property this design depends on --
**confirmation resolves claims, not workflows.** Confirming which field is the
reservation date establishes nothing about what the holidays collection means.

The claims themselves are imported from Experiment U unchanged. U's harness is
not edited: it belongs to a completed run.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
SPEC = ROOT / "spec"
sys.path.insert(0, str(LAB / "experimentU" / "harness"))

import claims as u_claims  # noqa: E402

HUMAN_PURPOSE = ("Accept a requested date unless it is invalid, a holiday, or "
                 "already reserved; otherwise append the reservation.")

SKELETON = {
    "model_id": "...", "model_version": "...", "task": "...", "purpose": "...",
    "sources": {"<source name>": {"path": "...", "collection": "..."}},
    "source_fields": {"<source name>": "<which item field holds the date>"},
    "rules": [{"rule": "...", "refusal": "..."}],
    "on_accept": "...",
}

VOCAB_RULES = ["not_reserved", "date_well_formed", "not_holiday"]
VOCAB_REFUSALS = ["HOLIDAY", "ALREADY_RESERVED", "INVALID_DATE"]
FILES = {"holidays": "fixtures/holidays.json",
         "reservations": "fixtures/reservations.json"}

# The tightened rule. The second paragraph is what U was missing.
RULE = """A load-bearing binding may not be established from an INFERRED or UNKNOWN
claim without either independent evidence or explicit human confirmation.

Independent evidence may NOT reuse anything already listed in that claim's
`basis`, and may NOT substitute different evidence of the same KIND:

  - Naming evidence is ONE kind. A field name and a collection name are not
    independent of each other. Two names do not add up to a fact.
  - Value-shape evidence (a value looks like YYYY-MM-DD) establishes what a
    value IS, never what it MEANS.
  - Independent evidence means: documentation, another trusted source, or
    explicit human confirmation.

A claim marked CONFIRMED is settled. Confirmation resolves that ONE claim and
nothing else -- it does not make neighbouring inferences trustworthy."""


# The two load-bearing inferred claims. Confirming one does not settle the other,
# which is the point U probe 1 made for us.
LOAD_BEARING = (
    {"source": "reservations", "field": "date"},
    {"source": "holidays", "field": None},
)


def confirm(report: list[dict], targets, who: str = "human") -> list[dict]:
    out = copy.deepcopy(report)
    for target in targets:
        for claim in out:
            body = claim["claim"]
            if (claim["status"] == "INFERRED"
                    and body.get("source") == target["source"]
                    and body.get("field") == target["field"]):
                claim["status"] = "CONFIRMED"
                claim["confirmed_by"] = who
                claim["was"] = "INFERRED"
    return out


def prompt(report: list[dict], phase: int) -> str:
    resume = ""
    if phase == 2:
        resume = ("\nA human has since CONFIRMED two claims. Their status is now "
                  "CONFIRMED in the report above; nothing else changed.\n")
    return f"""An inspection of some data sources produced the claims below. You did not
perform the inspection and cannot see the data yourself.

Each claim carries its own epistemic status:
  OBSERVED   directly established from the source representation
  INFERRED   the inspector's interpretation, with what it inferred from
  UNKNOWN    no supported interpretation
  CONFIRMED  an external authority resolved an inference

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

If every load-bearing binding is supported, produce the node definition.

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

If a load-bearing binding is NOT supported, do NOT produce a node. Instead write
a section headed exactly "CANNOT ESTABLISH" naming the binding, the claim it
would rest on, that claim's status, and the question a human must answer."""


def main(argv: list[str]) -> int:
    SPEC.mkdir(exist_ok=True)
    phase1 = u_claims.report()
    phase2 = confirm(phase1, LOAD_BEARING)

    (SPEC / "frozen_prompt_phase1.txt").write_text(prompt(phase1, 1), encoding="utf-8")
    (SPEC / "frozen_prompt_phase2.txt").write_text(prompt(phase2, 2), encoding="utf-8")
    (SPEC / "phase2_report.json").write_text(
        json.dumps(phase2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    changed = [c["claim"] for a, c in zip(phase1, phase2)
               if a["status"] != c["status"]]
    print(f"{len(phase1)} claims; exactly {len(changed)} promoted to CONFIRMED:")
    for c in changed:
        print(f"   {json.dumps(c, ensure_ascii=False)}")
    still_inferred = [c["claim"] for c in phase2 if c["status"] == "INFERRED"]
    print(f"\n{len(still_inferred)} claim(s) remain INFERRED and are NOT settled:")
    for c in still_inferred:
        print(f"   {json.dumps(c, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
