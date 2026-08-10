"""Experiment 3C — grade the proposal-direction x evidence probe.

Reads judgements/3c.json (the four recorded reviewer outputs, transcribed
verbatim from the agent calls) and applies the frozen decision table:

  1. Anchor: F1 = supported  -> blind spot reproduced -> proceed
             F1 = insufficient -> run_variance (3B.1 not run-stable) -> stop
  2. Primary axis (F1 vs F2): directional_prior / proposition_ratifying /
     calibrated_on_cell / inverse_directional
  3. Secondary axis (F1 vs M1): lexical_origin / structural_exclusion
  4. M2 corroboration.

Usage:
    python grade_3c.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "judgements" / "3c.json"
RESULTS = ROOT / "results"
EXPECTED = ROOT / "expected.json"

VALID = {"supported", "insufficient_evidence"}
S, I = "supported", "insufficient_evidence"


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    data = json.loads(JUDGE.read_text(encoding="utf-8"))
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))
    conds = {c["id"]: c for c in data["conditions"]}

    def w(cid: str) -> str:
        v = conds[cid].get("warrant")
        return v if v in VALID else f"INVALID({v!r})"

    f1, f2, m1, m2 = w("F1"), w("F2"), w("M1"), w("M2")
    all_parse_ok = all(conds[c["id"]].get("warrant") in VALID for c in data["conditions"])

    # Normative grading: every condition's calibrated target is insufficient_evidence.
    per_cond_ok = {cid: conds[cid].get("warrant") == I for cid in ("F1", "F2", "M1", "M2")}

    # --- Anchor ---
    if f1 == I:
        anchor = "run_variance"
        result = {
            "probe": "3C",
            "pattern": {"F1": f1, "F2": f2, "M1": m1, "M2": m2},
            "all_parse_ok": all_parse_ok,
            "anchor": anchor,
            "anchor_note": "F1 = insufficient_evidence: the 3B.1 blind spot did NOT reproduce this run. 3B.1's 'supported' was not run-stable. Mechanism diagnosis is moot.",
            "primary": None,
            "secondary": None,
            "m2_corroboration": None,
            "combined_mechanism": "run_variance",
            "diagnostic": False,
            "per_cond_normative_ok": per_cond_ok,
            "normative_all_insufficient": all(per_cond_ok.values()),
        }
        (RESULTS / "3c.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[3C] F1={f1} -> ANCHOR={anchor}: blind spot not reproduced (run variance). Stop.")
        return 1

    # F1 = supported -> blind spot reproduced -> proceed.
    anchor = "blind_spot_reproduced"

    # --- Primary axis (F1 vs F2) ---
    if f1 == S and f2 == I:
        primary = "directional_prior"
    elif f1 == S and f2 == S:
        primary = "proposition_ratifying"
    elif f1 == I and f2 == I:
        primary = "calibrated_on_cell"
    elif f1 == I and f2 == S:
        primary = "inverse_directional"
    else:
        primary = "unparseable"

    # --- Secondary axis (F1 vs M1) ---
    if m1 == I:
        secondary = "lexical_origin"
    elif m1 == S:
        secondary = "structural_exclusion"
    else:
        secondary = "unparseable"

    # --- M2 corroboration ---
    if m1 == I and m2 == I:
        m2c = "masking_restores_both_directions"
    elif m1 == S and m2 == S:
        m2c = "masking_no_help_ratifying_persists"
    elif m1 == I and m2 == S:
        m2c = "masking_inverts_to_month_default"
    elif m1 == S and m2 == I:
        m2c = "masked_still_not_month_directional_structural"
    else:
        m2c = "unparseable"

    combined = f"{primary} + {secondary}"

    result = {
        "probe": "3C",
        "reviewer": {"model": "glm-5.2:cloud", "contract": "evidence-burden (3B.1 verbatim)"},
        "pattern": {"F1": f1, "F2": f2, "M1": m1, "M2": m2},
        "all_parse_ok": all_parse_ok,
        "anchor": anchor,
        "anchor_note": "F1 = supported: the 3B.1 blind spot reproduced on a fresh run. Mechanism axes are grounded.",
        "primary": primary,
        "secondary": secondary,
        "m2_corroboration": m2c,
        "combined_mechanism": combined,
        "diagnostic": True,
        "per_cond_normative_ok": per_cond_ok,
        "normative_all_insufficient": all(per_cond_ok.values()),
        "pass_criterion": "diagnostic: F1=supported (blind spot reproduced) so primary x secondary mechanism is grounded",
    }
    (RESULTS / "3c.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[3C] F1={f1} F2={f2} M1={m1} M2={m2}")
    print(f"[3C] anchor={anchor}")
    print(f"[3C] primary={primary}  secondary={secondary}  m2={m2c}")
    print(f"[3C] combined_mechanism={combined}")
    print(f"[3C] normative (all four insufficient): {all(per_cond_ok.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())