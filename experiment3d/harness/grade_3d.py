"""Experiment 3D — grade the symmetric-classification probe.

Reads judgements/3d.json (the four recorded reviewer outputs, transcribed
verbatim from the agent calls) and applies the frozen decision table:

  1. Controls: CTRL-MONTH (Tammi) == A AND CTRL-NONMONTH (Tuote) == B
     -> controls_pass; else controls_broken (record which).
  2. Primary axis (3D-FULL, Jakso A): C=framing_was_the_problem /
     B=closed_world_prior_persists / A=surprising_month_established.
  3. Secondary axis (3D-MASKED, [TARGET]): A=structure_establishes_month /
     C=structure_insufficient_under_symmetric / B=masked_defaults_not_month.
  4. Combined named outcome + pass/partial-pass.

Usage:
    python grade_3d.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "judgements" / "3d.json"
RESULTS = ROOT / "results"
EXPECTED = ROOT / "expected.json"

VALID = {"A", "B", "C"}


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    data = json.loads(JUDGE.read_text(encoding="utf-8"))
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))
    probes = {p["id"]: p for p in data["probes"]}

    def v(pid: str) -> str:
        val = probes[pid].get("established")
        return val if val in VALID else f"INVALID({val!r})"

    cm, cn, full, masked = v("CTRL-MONTH"), v("CTRL-NONMONTH"), v("3D-FULL"), v("3D-MASKED")
    all_parse_ok = all(probes[p["id"]].get("established") in VALID for p in data["probes"])

    per_probe_ok = {
        "CTRL-MONTH": probes["CTRL-MONTH"].get("established") == "A",
        "CTRL-NONMONTH": probes["CTRL-NONMONTH"].get("established") == "B",
        "3D-FULL": probes["3D-FULL"].get("established") == "C",
        "3D-MASKED": probes["3D-MASKED"].get("established") == "A",
    }

    # --- Controls ---
    controls_status = None
    if cm == "A" and cn == "B":
        controls_status = "controls_pass"
    elif cm == "C":
        controls_status = "control_broken_month"
    elif cn == "C":
        controls_status = "control_broken_nonmonth"
    elif cm == "B":
        controls_status = "control_misclassified_month"
    elif cn == "A":
        controls_status = "control_misclassified_nonmonth"
    else:
        controls_status = "controls_broken_other"

    controls_pass = (controls_status == "controls_pass")

    # --- Primary / secondary (only meaningful if controls pass) ---
    primary = {  # 3D-FULL
        "C": "framing_was_the_problem",
        "B": "closed_world_prior_persists",
        "A": "surprising_month_established",
    }.get(full if full in VALID else None, "unparseable")

    secondary = {  # 3D-MASKED
        "A": "structure_establishes_month",
        "C": "structure_insufficient_under_symmetric",
        "B": "masked_defaults_not_month",
    }.get(masked if masked in VALID else None, "unparseable")

    combined_key = f"FULL={full}_MASKED={masked}"
    combined_map = {
        "FULL=C_MASKED=A": "framing_was_the_problem + structure_establishes_month (clean win)",
        "FULL=B_MASKED=A": "closed_world_prior_persists + structure_establishes_month",
        "FULL=C_MASKED=C": "framing_was_the_problem + structure_insufficient_under_symmetric (partial)",
        "FULL=B_MASKED=C": "closed_world_persists + structure_insufficient",
        "FULL=B_MASKED=B": "closed_world_persists + masked_defaults_not_month",
        "FULL=C_MASKED=B": "framing_was_the_problem + masked_defaults_not_month (unexpected)",
        "FULL=A_MASKED=A": "surprising_month_established + structure_establishes_month (unexpected)",
        "FULL=A_MASKED=C": "surprising_month_established + structure_insufficient (unexpected)",
        "FULL=A_MASKED=B": "surprising_month_established + masked_defaults_not_month (unexpected)",
    }
    combined = combined_map.get(combined_key, f"unmapped_pattern: {combined_key}")

    # --- Pass logic ---
    clean_win = controls_pass and full == "C" and masked == "A"
    partial_pass = controls_pass and full == "C" and masked == "C"
    # "framing solved escalation" = symmetric framing makes the gate receive C on
    # the failure cell (Jakso A), regardless of the masked outcome. This is the
    # architecturally relevant bar: does the gate get its signal?
    framing_solves_escalation = controls_pass and full == "C"

    result = {
        "probe": "3D",
        "reviewer": {"model": "glm-5.2:cloud", "contract": "symmetric A/B/C, no handed proposal"},
        "pattern": {"CTRL-MONTH": cm, "CTRL-NONMONTH": cn, "3D-FULL": full, "3D-MASKED": masked},
        "all_parse_ok": all_parse_ok,
        "per_probe_ok": per_probe_ok,
        "controls_status": controls_status,
        "controls_pass": controls_pass,
        "primary": primary if controls_pass else None,
        "secondary": secondary if controls_pass else None,
        "combined_mechanism": combined if controls_pass else None,
        "clean_win": clean_win,
        "partial_pass": partial_pass,
        "framing_solves_escalation": framing_solves_escalation,
        "pass_criterion": "controls_pass AND 3D-FULL=C AND 3D-MASKED=A",
        "interpretation_note": "framing_solves_escalation = controls pass AND Jakso A -> C (the gate would receive the escalation signal on the failure cell). clean_win additionally requires [TARGET] -> A.",
    }
    (RESULTS / "3d.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[3D] CTRL-MONTH(Tammi)={cm}  CTRL-NONMONTH(Tuote)={cn}  3D-FULL(Jakso A)={full}  3D-MASKED([TARGET])={masked}")
    print(f"[3D] controls={controls_status}")
    if controls_pass:
        print(f"[3D] primary={primary}")
        print(f"[3D] secondary={secondary}")
        print(f"[3D] combined={combined}")
    print(f"[3D] clean_win={clean_win}  partial_pass={partial_pass}  framing_solves_escalation={framing_solves_escalation}")
    return 0 if clean_win else 1


if __name__ == "__main__":
    raise SystemExit(main())