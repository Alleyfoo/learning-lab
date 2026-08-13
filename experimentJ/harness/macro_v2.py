#!/usr/bin/env python3
"""Experiment J — macro v2: the human-reviewed amendment of the saved recipe.

FROZEN RULE TEXT lives in `spec/preregistration.md` and `expected.json`. This
file IMPLEMENTS that text; the text is authority. If this code and the text
disagree, this code is wrong (see the fidelity policy in expected.json).

v1 (`det_classify`) and the month reference machinery (`tolerant_match`,
`coverage`, `REF`, `K_W`, `K_L`) are imported VERBATIM from Experiment I's
frozen `gate_I.py`. Its sha256 is verified on import; a mismatch VOIDS the run.

The amendment, in one sentence: v1 concluded `long` from "month tokens run down
a data column", which I4 falsified (a transposed monthly table has months down
a column too). v2 keeps that trigger but then asks *how many non-month columns
carry values* — one measure column is canonical long, two or more means the
values are spread across a second axis, which is out of contract.

    R1  hw >= K_w                  -> wide
    R2  exactly one month column:
          R2a  n_num >= 2          -> unknown   (transposed / out of contract)
          R2b  n_num == 1          -> long      (canonical long)
          R2c  n_num == 0          -> unknown   (no measure column)
    R3  two or more month columns  -> unknown   (ambiguous month axis)
    R4  otherwise                  -> unknown

Self-test scope note: the self-test deliberately asserts only STRUCTURAL
properties (numeric parsing, month-column detection, R1 precedence, totality,
the v1 hash) on inputs constructed here. It does NOT assert v2's label on any
graded fixture -- that would make the experiment pass by construction. The
graded outcome appears only in `grade_J.py`'s replay.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
GATE_I = LAB / "experimentI" / "harness" / "gate_I.py"

# Frozen in expected.json. A mismatch means v1 is not the arm J claims to
# compare against, so the comparison is meaningless.
V1_SHA256 = "da76ed982614a7874b0272f390f9b898cef47b64b2983645a21feb25ff95a941"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_v1_source() -> str:
    actual = _sha256(GATE_I)
    if actual != V1_SHA256:
        raise SystemExit(
            f"VOID: {GATE_I} sha256 {actual} != frozen {V1_SHA256}. "
            "v1 must be imported unmodified; the run is void."
        )
    return actual


verify_v1_source()
sys.path.insert(0, str(GATE_I.parent))
from gate_I import (  # noqa: E402  (import after hash verification, by design)
    K_L,
    K_W,
    REF,
    _read_csv,
    coverage,
    det_classify,
    tolerant_match,
)

LABELS = ("wide", "long", "unknown")

# numeric(): frozen parse. Optional sign, digits, optional single decimal
# separator ('.' or ',' -- Finnish sources use the comma). Deliberately narrow:
# J's hard stop forbids real numeric-format parsing (thousands separators,
# currency symbols, parentheses-negatives). The fixtures are clean integers.
_NUMBER = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


def is_number(cell: str) -> bool:
    return bool(_NUMBER.match(cell.strip()))


def _column(data: list[list[str]], col: int) -> list[str]:
    return [r[col] for r in data if col < len(r)]


def n_data_cols(data: list[list[str]]) -> int:
    return max((len(r) for r in data), default=0)


def month_columns(data: list[list[str]]) -> list[int]:
    """Data columns carrying >= K_l distinct reference months (tolerant match).

    Same measure v1 uses for `dl`; v2 keeps the trigger and amends only what
    follows it.
    """
    return [
        c
        for c in range(n_data_cols(data))
        if coverage(_column(data, c), tolerant_match) >= K_L
    ]


def is_numeric_column(data: list[list[str]], col: int) -> bool:
    """>= 1 non-empty cell AND every non-empty cell parses as a number."""
    cells = [c for c in _column(data, col) if c.strip() != ""]
    return bool(cells) and all(is_number(c) for c in cells)


def evidence(header: list[str], data: list[list[str]]) -> dict:
    """All measures v2 consults, recorded for every fixture."""
    hw = coverage(header, tolerant_match)
    mcols = month_columns(data)
    other = [c for c in range(n_data_cols(data)) if c not in mcols]
    numeric_other = [c for c in other if is_numeric_column(data, c)]
    return {
        "hw": hw,
        "month_cols": mcols,
        "other_cols": other,
        "numeric_other_cols": numeric_other,
        "n_num": len(numeric_other),
    }


def classify_v2(header: list[str], data: list[list[str]]) -> tuple[str, str]:
    """Return (label, rule_fired). Implements the frozen rule text."""
    ev = evidence(header, data)
    if ev["hw"] >= K_W:
        return "wide", "R1"
    if len(ev["month_cols"]) == 1:
        if ev["n_num"] >= 2:
            return "unknown", "R2a"
        if ev["n_num"] == 1:
            return "long", "R2b"
        return "unknown", "R2c"
    if len(ev["month_cols"]) >= 2:
        return "unknown", "R3"
    return "unknown", "R4"


def classify_file(path: Path) -> dict:
    header, data = _read_csv(path)
    label, rule = classify_v2(header, data)
    ev = evidence(header, data)
    return {
        "v1": det_classify(header, data),
        "v2": label,
        "rule": rule,
        "header": header,
        **ev,
    }


# ---------------------------------------------------------------------------
# Self-test — structural properties only (see module docstring)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []

    if len(REF) != 12:
        failures.append(f"reference vocabulary should have 12 months, got {len(REF)}")

    # numeric parsing
    for good in ("10", "-3", "0", "12.5", "12,5", " 7 "):
        if not is_number(good):
            failures.append(f"is_number({good!r}) should be True")
    for bad in ("", "ART-001", "10 kpl", "1.2.3", "Tammi", "N/A", "1 000"):
        if is_number(bad):
            failures.append(f"is_number({bad!r}) should be False")

    # A constructed canonical long: one label col, one month col, one measure.
    h = ["Tuote", "Kuukausi", "Myynti"]
    d = [["A", "Tammi", "1"], ["A", "Helmi", "2"], ["A", "Maalis", "3"]]
    ev = evidence(h, d)
    if ev["month_cols"] != [1]:
        failures.append(f"month_cols should be [1], got {ev['month_cols']}")
    if ev["n_num"] != 1:
        failures.append(f"n_num should be 1 (Myynti), got {ev['n_num']}")
    if classify_v2(h, d) != ("long", "R2b"):
        failures.append(f"constructed long -> {classify_v2(h, d)}, expected (long, R2b)")

    # Same shape with a second numeric column -> R2a. This is the constructed
    # analogue of the frozen J3 prediction; asserting it here is a statement
    # about the RULE, not about a graded fixture.
    h2 = ["Tuote", "Kuukausi", "Myynti", "Kate"]
    d2 = [["A", "Tammi", "1", "9"], ["A", "Helmi", "2", "8"], ["A", "Maalis", "3", "7"]]
    if classify_v2(h2, d2) != ("unknown", "R2a"):
        failures.append(f"two numeric non-month cols -> {classify_v2(h2, d2)}, expected (unknown, R2a)")

    # Label columns must NOT count toward n_num (the J2 trap, constructed).
    h3 = ["Tuote", "Maa", "Kuukausi", "Myynti"]
    d3 = [["A", "FI", "Tammi", "1"], ["A", "SE", "Helmi", "2"], ["B", "FI", "Maalis", "3"]]
    if evidence(h3, d3)["n_num"] != 1:
        failures.append("non-numeric label columns must not count toward n_num")

    # R1 precedence: months in the header win even when a data column also
    # carries months.
    h4 = ["Kuukausi", "Tammi", "Helmi", "Maalis"]
    d4 = [["Tammi", "1", "2", "3"], ["Helmi", "4", "5", "6"], ["Maalis", "7", "8", "9"]]
    if classify_v2(h4, d4)[1] != "R1":
        failures.append("R1 must take precedence over the data-column branch")

    # R3: two month columns -> ambiguous.
    h5 = ["Alku", "Loppu", "Myynti"]
    d5 = [["Tammi", "Helmi", "1"], ["Helmi", "Maalis", "2"], ["Maalis", "Huhti", "3"]]
    if classify_v2(h5, d5) != ("unknown", "R3"):
        failures.append(f"two month columns -> {classify_v2(h5, d5)}, expected (unknown, R3)")

    # R2c: month column, no numeric column at all.
    h6 = ["Kuukausi", "Huomio"]
    d6 = [["Tammi", "ok"], ["Helmi", "ok"], ["Maalis", "puuttuu"]]
    if classify_v2(h6, d6) != ("unknown", "R2c"):
        failures.append(f"no measure column -> {classify_v2(h6, d6)}, expected (unknown, R2c)")

    # Totality: every input yields one of the three frozen labels.
    for hh, dd in ((h, d), (h2, d2), (h3, d3), (h4, d4), (h5, d5), (h6, d6), ([], [])):
        if classify_v2(hh, dd)[0] not in LABELS:
            failures.append(f"non-label output for header {hh}")

    # Thresholds carried unchanged.
    if (K_W, K_L) != (3, 3):
        failures.append(f"thresholds must be unchanged (3,3), got ({K_W},{K_L})")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (v1 hash verified / numeric parse / month-col detection / "
        "R1 precedence / R2a R2b R2c R3 / totality / thresholds unchanged)\n"
    )
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        raise SystemExit(_self_test())
    if argv and argv[0] == "--classify":
        import json

        p = Path(argv[1])
        sys.stdout.write(json.dumps(classify_file(p), ensure_ascii=False, indent=2) + "\n")
        raise SystemExit(0)
    sys.stderr.write("usage: macro_v2.py --self-test | --classify <fixture.csv>\n")
    raise SystemExit(2)
