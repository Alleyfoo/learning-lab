#!/usr/bin/env python3
"""Experiment I — wide/long/unknown format classification.

FROZEN HARNESS. Do not modify after the freeze commit. Grading is frozen in
expected.json; pass criteria are not relaxed after the fact.

Architecture
------------
Input per probe: a small CSV = header row (row 1) + 3-5 data rows. The header
has already been located (Experiment H); I isolates the *representation*
classification variable only.

LLM contract: given the rendered rows, output ONLY JSON
{"format": "wide" | "long" | "unknown"}.

Three layers, mirroring H's division of labour but adapted for a
three-way classification:

  1. Deterministic classifier (deterministic-first / counterfactual):
        hw = distinct reference months present in the HEADER row (tolerant)
        dl = max distinct reference months present in any single DATA column
        hw >= K_w (3) -> "wide"
        dl >= K_l (3) -> "long"   (only if not wide; wide takes precedence)
        else      -> "unknown"
     This reuses the frozen month reference (experimentH/reference/months.json)
     and H's suffix-tolerant prefix match verbatim. It is recorded for every
     probe as the COUNTERFACTUAL: would a rule alone give the right label?

  2. Verifier gate (objective, code, not LLM):
        For the LLM's claimed label, check the SAME objective token criteria:
          wide    supported iff hw >= K_w
          long    supported iff dl >= K_l
          unknown supported iff hw < K_w AND dl < K_l
        A label that is not objectively supported is flagged `supported=False`
        (the LLM asserted a representation the evidence does not establish).
        The gate does NOT substitute its own answer — it records agreement
        and support. (Unlike H's coverage==12 authority, here the criteria are
        a coarse heuristic and can be wrong on tricky structures; see the
        stated limitations. So the gate verifies, it does not override.)

  3. Grader (frozen in expected.json):
        i_pass  = (llm_label == expected) AND (gate supported)
        det_ok  = (det_classify == expected)   # counterfactual: rule suffices?
        overall = all probes i_pass

The deterministic-first PRODUCTION rule (skip the LLM when the classifier is
confident wide/long) is recorded as a derived recommendation, not enforced in
the experiment: I's purpose is to MEASURE the LLM's classification on all
probes, so the LLM is invoked on every probe. The counterfactual tells us
whether the LLM was needed.

Stage-aware grading (as in H): probes present in judgements/I.json are graded;
`i1_i2` requires I1 AND I2; `overall` requires all graded probes to pass.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = Path(__file__).resolve().parents[2] / "experimentH" / "reference" / "months.json"
EXPECTED_PATH = ROOT / "expected.json"

# Frozen thresholds: enough distinct months to recognise a month axis.
K_W = 3
K_L = 3

LABELS = ("wide", "long", "unknown")


def _load_ref() -> list[str]:
    ref = json.loads(REF_PATH.read_text(encoding="utf-8"))
    return ref["months"]


REF = _load_ref()
N_REF = len(REF)


def _norm(s: str) -> str:
    return s.strip().lower()


def exact_match(cell: str, ref: str) -> bool:
    return _norm(cell) == _norm(ref)


def tolerant_match(cell: str, ref: str) -> bool:
    """Suffix-tolerant prefix match (frozen, identical to H)."""
    c, r = _norm(cell), _norm(ref)
    if not c.startswith(r):
        return False
    if len(c) == len(r):
        return True
    # next char must be a boundary (non-letter) so 'Maalis_total' counts but
    # 'Maaliskuu' would not be misread as 'Maalis'... see limitations.
    return not c[len(r)].isalpha()


def coverage(cells: list[str], match_fn) -> int:
    """Distinct reference months present in the given cells."""
    return sum(1 for ref in REF if any(match_fn(cell, ref) for cell in cells))


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    header = rows[0]
    data = rows[1:]
    return header, data


def _column(cells_rows: list[list[str]], col: int) -> list[str]:
    return [r[col] for r in cells_rows if col < len(r)]


def measures(header: list[str], data: list[list[str]]) -> tuple[int, int]:
    """Return (hw, dl): distinct months in header, max distinct months in any
    single data column (tolerant)."""
    hw = coverage(header, tolerant_match)
    dl = 0
    if data:
        n_cols = max(len(r) for r in data)
        for col in range(n_cols):
            c = coverage(_column(data, col), tolerant_match)
            if c > dl:
                dl = c
    return hw, dl


def det_classify(header: list[str], data: list[list[str]]) -> str:
    hw, dl = measures(header, data)
    if hw >= K_W:
        return "wide"
    if dl >= K_L:
        return "long"
    return "unknown"


def gate(label: str, header: list[str], data: list[list[str]]) -> dict:
    """Verifier gate: is the LLM's claimed label objectively supported?"""
    hw, dl = measures(header, data)
    if label == "wide":
        supported = hw >= K_W
    elif label == "long":
        supported = dl >= K_L
    elif label == "unknown":
        supported = hw < K_W and dl < K_L
    else:
        supported = False  # invalid label
    return {
        "llm_label": label,
        "hw": hw,
        "dl": dl,
        "supported": supported,
        "det_classify": det_classify(header, data),
    }


def counterfactual_scan(fixture_path: Path) -> dict:
    """Non-scoring diagnostic: apply the deterministic classifier to the fixture
    and report its label plus the coverage measures. Answers 'would the rule
    alone have classified this, and how?'."""
    header, data = _read_csv(fixture_path)
    hw, dl = measures(header, data)
    return {
        "fixture": str(fixture_path.relative_to(ROOT)),
        "det_classify": det_classify(header, data),
        "hw": hw,
        "dl": dl,
        "K_w": K_W,
        "K_l": K_L,
    }


# ---------------------------------------------------------------------------
# Grader
# ---------------------------------------------------------------------------

def grade(judgements_path: Path) -> dict:
    judgements = json.loads(judgements_path.read_text(encoding="utf-8"))
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    probes_expected = expected["per_probe"]
    grader_map = expected.get("grader_per_probe", {})

    present = [p for p in ("I1", "I2", "I3", "I4", "I5", "I6") if p in judgements]
    per_probe = {}
    for p in present:
        j = judgements[p]
        exp = probes_expected[p]["expected_format"]
        fixture_path = ROOT / probes_expected[p]["fixture"]
        header, data = _read_csv(fixture_path)
        llm_label = j.get("llm_answer", {}).get("format")
        g = gate(llm_label, header, data)
        grader = grader_map.get(p, "verifier")
        if grader == "oracle":
            # Verifier SUSPENDED for this probe: the frozen fixture expectation is
            # the grader. (For I4, dl=12 would make supported(long)=true and
            # supported(unknown)=false, but that evidence rule is exactly what I4
            # falsifies -- record it, do not let it gate i_pass.)
            i_pass = (llm_label == exp)
        else:
            i_pass = (llm_label == exp) and g["supported"]
        per_probe[p] = {
            "expected": exp,
            "llm_label": llm_label,
            "det_classify": g["det_classify"],
            "hw": g["hw"],
            "dl": g["dl"],
            "supported": g["supported"],   # evidence; for I4 does NOT gate i_pass
            "grader": grader,
            "i_pass": i_pass,
            "det_ok": g["det_classify"] == exp,  # counterfactual (miss on I4)
        }

    all_pass = all(pp["i_pass"] for pp in per_probe.values())
    i1_i2 = ("I1" in per_probe and "I2" in per_probe
             and per_probe["I1"]["i_pass"] and per_probe["I2"]["i_pass"])
    i1_i2_i3 = (all(p in per_probe for p in ("I1", "I2", "I3"))
                and all(per_probe[p]["i_pass"] for p in ("I1", "I2", "I3")))
    i4 = ("I4" in per_probe and per_probe["I4"]["i_pass"])
    i5 = ("I5" in per_probe and per_probe["I5"]["i_pass"])
    i6 = ("I6" in per_probe and per_probe["I6"]["i_pass"])
    overall = all_pass  # all present probes pass

    stage = judgements.get("stage", "partial")
    return {
        "probe": "I",
        "stage": stage,
        "present": present,
        "per_probe": per_probe,
        "i1_i2_pass": i1_i2,
        "i1_i2_i3_pass": i1_i2_i3,
        "i4_pass": i4,
        "i5_pass": i5,
        "i6_pass": i6,
        "all_probes_pass": all_pass,
        "overall": overall,
        "counterfactual": [counterfactual_scan(ROOT / probes_expected[p]["fixture"]) for p in present],
    }


# ---------------------------------------------------------------------------
# Self-test (no fixtures on disk required beyond the frozen ones)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures = []

    # I1 wide: header has 6 months, data are numbers.
    h1, d1 = _read_csv(ROOT / "fixtures" / "I1.csv")
    if det_classify(h1, d1) != "wide":
        failures.append(f"I1 det != wide (got {det_classify(h1, d1)})")
    g = gate("wide", h1, d1)
    if not g["supported"]:
        failures.append("I1 gate(wide) not supported")
    if gate("long", h1, d1)["supported"]:
        failures.append("I1 gate(long) should be unsupported")
    if gate("unknown", h1, d1)["supported"]:
        failures.append("I1 gate(unknown) should be unsupported")

    # I2 long: header has 0 months, data col 1 has Tammi/Helmi/Maalis (3 distinct).
    h2, d2 = _read_csv(ROOT / "fixtures" / "I2.csv")
    if det_classify(h2, d2) != "long":
        failures.append(f"I2 det != long (got {det_classify(h2, d2)})")
    if not gate("long", h2, d2)["supported"]:
        failures.append("I2 gate(long) not supported")
    if gate("wide", h2, d2)["supported"]:
        failures.append("I2 gate(wide) should be unsupported")
    if gate("unknown", h2, d2)["supported"]:
        failures.append("I2 gate(unknown) should be unsupported")

    # I3 unknown: quarterly, no month tokens anywhere.
    h3, d3 = _read_csv(ROOT / "fixtures" / "I3.csv")
    if det_classify(h3, d3) != "unknown":
        failures.append(f"I3 det != unknown (got {det_classify(h3, d3)})")
    if not gate("unknown", h3, d3)["supported"]:
        failures.append("I3 gate(unknown) not supported")
    if gate("wide", h3, d3)["supported"]:
        failures.append("I3 gate(wide) should be unsupported")
    if gate("long", h3, d3)["supported"]:
        failures.append("I3 gate(long) should be unsupported")

    # I4 transposed wide: months DOWN rows -> the macro is KNOWINGLY WRONG here.
    # det must say 'long' (frozen wrong prediction); expected is 'unknown'.
    h4, d4 = _read_csv(ROOT / "fixtures" / "I4.csv")
    if det_classify(h4, d4) != "long":
        failures.append(f"I4 det != long (got {det_classify(h4, d4)}); macro must be knowingly WRONG here")
    hw4, dl4 = measures(h4, d4)
    if (hw4, dl4) != (0, 12):
        failures.append(f"I4 measures should be (hw=0, dl=12); got ({hw4}, {dl4})")
    # The coarse verifier evidence: long IS supported (dl=12), unknown is NOT.
    # Both are recorded as evidence; neither gates I4 (oracle grader).
    if not gate("long", h4, d4)["supported"]:
        failures.append("I4 gate(long) should be supported by coarse evidence (dl=12) -- recorded, not gating")
    if gate("unknown", h4, d4)["supported"]:
        failures.append("I4 gate(unknown) should be unsupported (dl=12) -- the evidence rule I4 falsifies")
    # Counterfactual: det_ok must be False (macro wrong on this representation).
    if det_classify(h4, d4) == "unknown":
        failures.append("I4 det_classify should be long (wrong), not unknown -- do not 'fix' the macro")

    # Invalid label -> unsupported.
    if gate("pivoted", h1, d1)["supported"]:
        failures.append("invalid label should be unsupported")

    # Tolerant match boundary: 'Maalis_total' matches Maalis; 'Maaliskuu' does not.
    if not tolerant_match("Maalis_total", "Maalis"):
        failures.append("tolerant Maalis_total should match Maalis")
    if tolerant_match("Maaliskuu", "Maalis"):
        failures.append("tolerant Maaliskuu should NOT match Maalis (boundary)")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write("SELF-TEST PASSED (I1 wide / I2 long / I3 unknown / I4 macro-wrong-long / gate support / boundary)\n")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        raise SystemExit(_self_test())
    if argv and argv[0] == "--grade":
        jp = Path(argv[1])
        r = grade(jp)
        sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
        stage = r["stage"]
        if stage == "full":
            raise SystemExit(0 if r["overall"] is True else 1)
        if stage == "i1_i2":
            raise SystemExit(0 if r["i1_i2_pass"] is True else 1)
        if stage == "i1_i2_i3":
            raise SystemExit(0 if r["i1_i2_i3_pass"] is True else 1)
        if stage == "i4":
            raise SystemExit(0 if r["i4_pass"] is True else 1)
        if stage == "i5":
            raise SystemExit(0 if r["i5_pass"] is True else 1)
        if stage == "i6":
            raise SystemExit(0 if r["i6_pass"] is True else 1)
        # partial / unknown stage: do not fail the run
        raise SystemExit(0)
    sys.stderr.write("usage: gate_I.py --self-test | --grade <judgements.json>\n")
    raise SystemExit(2)