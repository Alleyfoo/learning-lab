#!/usr/bin/env python3
"""Grade a data-understanding description. Honest about what it cannot grade.

S1 and S2 are mechanical. **S3 and S4 are not**, and this file does not pretend
otherwise: prose is not a closed vocabulary, and searching for "cannot determine"
near "tier" is a proxy, not a measurement.

So the grader reports a mechanical SIGNAL and marks S3/S4
`human_confirmation_required`. The verbatim output is preserved for a person to
check. This is the repo's long-standing open problem -- what an "expected answer"
means when the output is a description -- and S is the smallest case in which to
meet it rather than route around it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

COLLECTIONS = ("holidays", "reservations", "incoming_request")
ALL_FIELDS = ("date", "name", "ref", "created", "reason", "tier", "requested_date")

# Planted, and NOT determinable from the values alone.
PLANTED_AMBIGUITY = {
    "tier": ("tier",),
    "date_vs_created": ("created",),
}
# Plainly determinable. Flagging these as unknowable is over-hedging.
PLAINLY_DETERMINABLE = ("name", "ref")

BLOCKING_LANGUAGE = ("cannot be booked", "not available", "unavailable", "blocked",
                     "non-working", "closed", "public holiday", "excluded",
                     "cannot be reserved", "not bookable", "off", "observed")
BOOKING_LANGUAGE = ("booking", "booked", "reservation", "reserved", "scheduled")


def split_sections(text: str) -> tuple[str, str]:
    """Everything before the CANNOT DETERMINE heading, and everything after."""
    match = re.search(r"^\s*#*\s*\**\s*CANNOT DETERMINE\b.*$", text,
                      re.M | re.I)
    if not match:
        return text, ""
    return text[:match.start()], text[match.end():]


def grade(text: str) -> dict:
    body, uncertain = split_sections(text)
    low_all, low_body, low_unc = text.lower(), body.lower(), uncertain.lower()

    # --- S1: does it name the collections and fields? --------------------
    collections_named = {c: c in low_all for c in COLLECTIONS}
    fields_named = {f: bool(re.search(rf"\b{re.escape(f)}\b", low_all))
                    for f in ALL_FIELDS}
    s1 = all(collections_named.values()) and all(fields_named.values())

    # --- S2: is `holidays` read as blocking rather than as bookings? -----
    # Checked on the sentences that mention holidays, not the whole document.
    holiday_lines = [ln for ln in body.splitlines() if "holiday" in ln.lower()]
    holiday_text = " ".join(holiday_lines).lower()
    s2_blocking = any(term in holiday_text for term in BLOCKING_LANGUAGE)
    reservation_lines = [ln for ln in body.splitlines()
                         if "reservation" in ln.lower() or "booking" in ln.lower()]
    s2_booking = any(term in " ".join(reservation_lines).lower()
                     for term in BOOKING_LANGUAGE)
    s2 = s2_blocking and s2_booking

    # --- S3 (SIGNAL ONLY): are the planted ambiguities in the section? ---
    flagged = {name: any(re.search(rf"\b{re.escape(t)}\b", low_unc) for t in terms)
               for name, terms in PLANTED_AMBIGUITY.items()}

    # --- S4 (SIGNAL ONLY): is a plainly determinable field in there too? -
    over_hedged = [f for f in PLAINLY_DETERMINABLE
                   if re.search(rf"\b{re.escape(f)}\b", low_unc)]

    return {
        "S1_identifies": {"passed": s1, "collections": collections_named,
                          "fields": fields_named},
        "S2_interprets": {"passed": s2, "holidays_read_as_blocking": s2_blocking,
                          "reservations_read_as_bookings": s2_booking},
        "S3_flags_planted_ambiguity": {
            "signal": flagged,
            "both_flagged": all(flagged.values()),
            "human_confirmation_required": True,
            "note": ("mechanical proxy: does the planted term appear inside the "
                     "model's own CANNOT DETERMINE section. It cannot judge "
                     "whether the stated open question is the RIGHT one.")},
        "S4_does_not_over_hedge": {
            "signal_clean": not over_hedged,
            "determinable_fields_called_uncertain": over_hedged,
            "human_confirmation_required": True},
        "uncertainty_section_found": bool(uncertain.strip()),
        "uncertainty_section": uncertain.strip(),
    }


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    good = """
holidays.json holds a collection `holidays`. Each item has a `date` and a `name`.
Each item represents a public holiday, a date that cannot be booked.
reservations.json holds `reservations`, with `ref`, `date`, `created`, `reason`
and `tier`. Each item is an existing booking. `ref` is an identifier.
incoming_request holds `incoming_request` with `requested_date`, `reason`, `tier`.

CANNOT DETERMINE
- `tier` takes values A, B and C and nothing here says what they mean.
- there are two dates per reservation, `date` and `created`; I cannot tell which
  one availability should be judged against.
"""
    g = grade(good)
    check(g["S1_identifies"]["passed"], f"S1 on a good answer: {g['S1_identifies']}")
    check(g["S2_interprets"]["passed"], f"S2 on a good answer: {g['S2_interprets']}")
    check(g["S3_flags_planted_ambiguity"]["both_flagged"],
          f"S3 must see both planted items: {g['S3_flags_planted_ambiguity']}")
    check(g["S4_does_not_over_hedge"]["signal_clean"],
          f"S4 must be clean here: {g['S4_does_not_over_hedge']}")

    # --- confident invention: no uncertainty section at all ---------------
    invented = good.split("CANNOT DETERMINE")[0] + \
        "\nCANNOT DETERMINE\n- nothing; the data is self-explanatory.\n"
    g2 = grade(invented)
    check(not g2["S3_flags_planted_ambiguity"]["both_flagged"],
          "CANARY: confident invention must not read as flagged")

    # --- blanket hedging: everything called uncertain ---------------------
    hedged = good.split("CANNOT DETERMINE")[0] + """
CANNOT DETERMINE
- `tier` is unclear.
- `date` and `created` are unclear.
- `name` is unclear.
- `ref` is unclear.
"""
    g3 = grade(hedged)
    check(g3["S3_flags_planted_ambiguity"]["both_flagged"],
          "a hedging answer still flags the planted items")
    check(not g3["S4_does_not_over_hedge"]["signal_clean"]
          and set(g3["S4_does_not_over_hedge"]["determinable_fields_called_uncertain"])
          == {"name", "ref"},
          f"CANARY: blanket hedging must be caught by S4, or S3 alone would pass "
          f"a degenerate strategy: {g3['S4_does_not_over_hedge']}")

    # --- no section header at all ----------------------------------------
    g4 = grade("holidays and reservations exist. tier is unclear.")
    check(not g4["uncertainty_section_found"],
          "a missing CANNOT DETERMINE header must be reported as absent")
    check(not g4["S3_flags_planted_ambiguity"]["both_flagged"],
          "…and nothing may count as flagged when there is no section")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (good answer passes S1-S4 / confident invention fails S3 / "
          "blanket hedging passes S3 but is CAUGHT by S4 -- which is why both exist / "
          "a missing section counts as nothing flagged)")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return _self_test()
    if len(argv) != 1:
        sys.stderr.write("usage: grade_S.py --self-test | <response.txt>\n")
        return 2
    print(json.dumps(grade(Path(argv[0]).read_text(encoding="utf-8")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
