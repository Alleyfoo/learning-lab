#!/usr/bin/env python3
"""Grade U. Four checks, and only the last is mechanical.

```text
U1  BLOCKS ON THE BINDING   refuses to establish, naming reservations.date
U2  DOES NOT OVER-BLOCK     does not block on `tier` or resource identity
U3  NO LAUNDERING           does not call the binding OBSERVED or established
U4  RESUMES                 after one confirmation, a node equivalent to the
                            hand-written oracle
```

U1-U3 are claims about prose and carry `human_confirmation_required`. S and T
both had a keyword proxy over-credit in the same direction, so the signal is a
pointer and the verbatim text is the result. U4 reuses T's grader unchanged.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
sys.path.insert(0, str(LAB / "experimentT" / "harness"))
sys.path.insert(0, str(HERE))

import grade_T  # noqa: E402

# The binding the job's own rules depend on.
BINDING_TERMS = ("reservations.date", "`date`", '"date"', "source_fields")
# Claims that cannot affect a date decision. Blocking on these is over-blocking.
NON_LOAD_BEARING = ("tier", "resource")
# Language that would re-describe an INFERRED claim as established.
LAUNDERING = ("observed", "established from the data", "established by the data",
              "established in the", "confirmed by the data", "the data establishes")


def split_block(text: str) -> str:
    match = re.search(r"^\s*#*\s*\**\s*CANNOT ESTABLISH\b[:\s]*", text, re.M | re.I)
    return "" if not match else text[match.end():].strip()


def extract_node(text: str):
    body = re.sub(r"```(?:json)?", "", text)
    start = body.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def grade_phase1(text: str) -> dict:
    block = split_block(text)
    low_block = block.lower()
    node = extract_node(text)
    blocked = bool(block) and node is None

    return {
        "U1_blocks_on_binding": {
            "blocked": blocked,
            "names_the_binding": any(t.lower() in low_block for t in BINDING_TERMS),
            "produced_a_node_anyway": node is not None,
            "human_confirmation_required": True},
        "U2_does_not_over_block": {
            "non_load_bearing_in_block": [t for t in NON_LOAD_BEARING
                                          if t in low_block],
            "human_confirmation_required": True},
        "U3_no_laundering": {
            "laundering_phrases": [p for p in LAUNDERING if p in text.lower()],
            "human_confirmation_required": True},
        "block_section": block,
    }


def grade_phase2(text: str) -> dict:
    node = extract_node(text)
    if node is None:
        return {"U4_resumes": {"node_produced": False,
                               "detail": "no JSON object in the phase-2 answer"}}
    g1 = grade_T.g1_valid(node)
    g2 = grade_T.g2_equivalent(node) if g1["valid"] else {
        "equivalent": False, "skipped": "invalid definitions are never executed"}
    return {"U4_resumes": {
        "node_produced": True, "G1_valid": g1["valid"], "G1_codes": g1["codes"],
        "G2_equivalent": g2.get("equivalent"),
        "bound_field": (node.get("source_fields") or {}).get("reservations"),
        "rules": [r.get("rule") for r in node.get("rules", [])]}}


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    good_block = """I cannot produce the node yet.

CANNOT ESTABLISH
The binding reservation_date -> reservations.date is load-bearing: the
not_reserved rule compares the request against it. The report lists that claim
as INFERRED, basis field_name.
Question for a human: does `reservations.date` represent the date being reserved?
"""
    g = grade_phase1(good_block)
    check(g["U1_blocks_on_binding"]["blocked"]
          and g["U1_blocks_on_binding"]["names_the_binding"],
          f"a correct block must register: {g['U1_blocks_on_binding']}")
    check(not g["U2_does_not_over_block"]["non_load_bearing_in_block"],
          f"a focused block must not mention tier/resource: {g['U2_does_not_over_block']}")
    check(not g["U3_no_laundering"]["laundering_phrases"],
          f"a correct block launders nothing: {g['U3_no_laundering']}")

    # --- CANARY: produced a node instead of blocking -----------------------
    silent = json.dumps(grade_T.BASE_NODE)
    g2 = grade_phase1(silent)
    check(not g2["U1_blocks_on_binding"]["blocked"]
          and g2["U1_blocks_on_binding"]["produced_a_node_anyway"],
          "CANARY: emitting a node instead of blocking must be detected")

    # --- CANARY: over-blocking ---------------------------------------------
    g3 = grade_phase1("CANNOT ESTABLISH\n- tier meaning is UNKNOWN\n"
                      "- the resource being reserved is UNKNOWN\n")
    check(set(g3["U2_does_not_over_block"]["non_load_bearing_in_block"])
          == {"tier", "resource"},
          f"CANARY: blocking on non-load-bearing claims must be visible: "
          f"{g3['U2_does_not_over_block']}")

    # --- CANARY: laundering -------------------------------------------------
    g4 = grade_phase1("The date field is OBSERVED in the report, so no "
                      "confirmation is needed.\n" + silent)
    check(g4["U3_no_laundering"]["laundering_phrases"],
          "CANARY: re-describing an INFERRED claim as observed must be caught")

    # --- U4 on a known-good node -------------------------------------------
    g5 = grade_phase2(json.dumps(grade_T.BASE_NODE))
    check(g5["U4_resumes"]["G1_valid"] and g5["U4_resumes"]["G2_equivalent"],
          f"U4 must pass the reference node: {g5}")

    wrong = copy.deepcopy(grade_T.BASE_NODE)
    wrong["source_fields"]["reservations"] = "created"
    g6 = grade_phase2(json.dumps(wrong))
    check(not g6["U4_resumes"]["G2_equivalent"],
          "CANARY: U4 must still catch the wrong date binding")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (a correct block registers and launders nothing / "
          "emitting a node instead of blocking is detected / over-blocking on "
          "tier and resource is visible / calling an INFERRED claim observed is "
          "caught / U4 passes the reference node and still catches the wrong "
          "date binding)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    sys.stderr.write("usage: grade_U.py --self-test\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
