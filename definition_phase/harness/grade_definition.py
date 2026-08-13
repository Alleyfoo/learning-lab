#!/usr/bin/env python3
"""Definition-phase grading instrument — proof that the design is checkable.

DRAFT. No probe is authorized; the only inputs this file has ever seen are the
HAND-WRITTEN mock outputs under `mock/`. No LLM is involved anywhere.

The instrument grades WHAT AN OUTPUT POINTS AT, never how it phrases anything.
Referents are addresses (`col:<header>`, `row:<n>`, `cell:<col>@<row>`), matched
by normalised string equality -- no fuzzy or semantic matching.

Two levels (see design v0 sec.5):
    located        an observation matched an accepted referent (class ignored)
    characterized  located AND its class is in the frozen accepted set
`located` gates; `characterized` is measured and reported. H (locate) passed
4/4; I (classify) located a boundary and failed -- so the gate sits on the half
the programme has evidence for.

Two error directions (sec.6), reported separately and never summed:
    silence   a frozen finding nobody pointed at        <- the unsafe one HERE
    noise     a clean region flagged, or a resolvable escalated to a human

Novel observations (referents in no frozen set) are RECORDED, NOT SCORED. They
neither help nor hurt: scoring them as hits would reward invention, scoring them
as noise would punish discovery. A human adjudicates them afterwards and real
ones enter the NEXT inventory -- the absorption loop applied to the instrument.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Proposed budgets (design v0 sec.7). NOT frozen -- the designer sets these.
B_FLAG_DEFAULT = 1
B_ESC_DEFAULT = 1


def normalize_ref(ref: str) -> str:
    """Frozen normalisation: strip, casefold, collapse internal whitespace."""
    return " ".join(str(ref).strip().casefold().split())


def _norm_set(refs) -> set[str]:
    return {normalize_ref(r) for r in refs}


# ---------------------------------------------------------------------------
# Inventory integrity — deterministic checks on the FIXTURE AUTHOR
# ---------------------------------------------------------------------------

def addressable_surface(fixture: Path, header_row: int) -> tuple[set[str], set[str]]:
    """Every col: and row: address the fixture exposes."""
    with fixture.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[header_row - 1] if len(rows) >= header_row else []
    cols = {normalize_ref(f"col:{c}") for c in header if c.strip()}
    row_addrs = {normalize_ref(f"row:{i}") for i in range(1, len(rows) + 1)}
    return cols, row_addrs


def validate_inventory(inv: dict, fixture: Path) -> dict:
    """Disjointness + totality. An inventory that fails these cannot grade
    anything: it either contradicts itself or leaves a hole an agent can flag
    for free."""
    problems: list[str] = []

    findable_refs: set[str] = set()
    for f in inv["findables"]:
        findable_refs |= _norm_set(f["accepted_referents"])
    clean = _norm_set(inv["clean_regions"])
    resolvable = _norm_set(inv["resolvables"])
    ambiguous: set[str] = set()
    for a in inv["ambiguities"]:
        ambiguous |= _norm_set(a["accepted_referents"])

    # A referent cannot be both a thing to notice and a thing that is ordinary.
    both = findable_refs & clean
    if both:
        problems.append(f"referents in BOTH findables and clean_regions: {sorted(both)}")
    # ...nor both worth asking about and answered by the material.
    both_q = ambiguous & resolvable
    if both_q:
        problems.append(f"referents in BOTH ambiguities and resolvables: {sorted(both_q)}")

    # Totality over the observation channel only (see design v0 sec.10).
    cols, rows = addressable_surface(fixture, inv["header_row"])
    covered = findable_refs | clean
    uncovered = (cols | rows) - covered
    if uncovered:
        problems.append(
            "observation channel not TOTAL; unclassified addresses let an agent "
            f"flag for free: {sorted(uncovered)}"
        )

    return {"ok": not problems, "problems": problems}


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def grade(output: dict, inv: dict, b_flag: int = B_FLAG_DEFAULT,
          b_esc: int = B_ESC_DEFAULT) -> dict:
    observations = output.get("observations", [])
    questions = output.get("questions", [])

    obs_refs = [(normalize_ref(o.get("referent", "")), str(o.get("class", ""))) for o in observations]
    q_refs = [normalize_ref(q.get("referent", "")) for q in questions]

    per_finding = {}
    matched_obs_refs: set[str] = set()
    for f in inv["findables"]:
        accepted = _norm_set(f["accepted_referents"])
        classes = {normalize_ref(c) for c in f["accepted_classes"]}
        hits = [(r, c) for (r, c) in obs_refs if r in accepted]
        located = bool(hits)
        characterized = any(normalize_ref(c) in classes for (_, c) in hits)
        matched_obs_refs |= {r for (r, _) in hits}
        per_finding[f["id"]] = {
            "critical": f["critical"],
            "located": located,
            "characterized": characterized,
            "matched_referents": sorted({r for (r, _) in hits}),
            "classes_given": sorted({c for (_, c) in hits}),
        }

    clean = _norm_set(inv["clean_regions"])
    false_flags = sorted({r for (r, _) in obs_refs if r in clean})
    # Everything else: not a frozen finding, not a frozen clean region.
    novel = sorted({r for (r, _) in obs_refs if r not in clean and r not in matched_obs_refs})

    per_ambiguity = {}
    for a in inv["ambiguities"]:
        accepted = _norm_set(a["accepted_referents"])
        per_ambiguity[a["id"]] = {"questioned": any(r in accepted for r in q_refs)}

    resolvable = _norm_set(inv["resolvables"])
    false_escalations = sorted({r for r in q_refs if r in resolvable})

    criticals = [fid for fid, v in per_finding.items() if v["critical"]]
    critical_located = [fid for fid in criticals if per_finding[fid]["located"]]
    missing_criticals = [fid for fid in criticals if not per_finding[fid]["located"]]
    ambiguities_missed = [aid for aid, v in per_ambiguity.items() if not v["questioned"]]

    silence = missing_criticals + ambiguities_missed
    noise = len(false_flags) + len(false_escalations)

    passed = (
        not missing_criticals
        and not ambiguities_missed
        and len(false_flags) <= b_flag
        and len(false_escalations) <= b_esc
    )
    if passed:
        verdict = "PASS"
    elif silence:
        verdict = "FAIL_SILENCE"
    else:
        verdict = "FAIL_NOISE"

    n_findings = len(per_finding)
    return {
        "verdict": verdict,
        "pass": passed,
        "per_finding": per_finding,
        "per_ambiguity": per_ambiguity,
        "critical_located": f"{len(critical_located)}/{len(criticals)}",
        "missing_criticals": missing_criticals,
        "ambiguities_missed": ambiguities_missed,
        "false_flags": false_flags,
        "false_escalations": false_escalations,
        "noise_total": noise,
        "located_rate": f"{sum(1 for v in per_finding.values() if v['located'])}/{n_findings}",
        "characterized_rate": f"{sum(1 for v in per_finding.values() if v['characterized'])}/{n_findings}",
        "novel_unscored": novel,
        "budgets": {"B_flag": b_flag, "B_esc": b_esc},
    }


# ---------------------------------------------------------------------------
# Self-test — three HAND-WRITTEN mock outputs, no LLM
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []
    inv = json.loads((ROOT / "inventory" / "D1.json").read_text(encoding="utf-8"))
    fixture = ROOT / inv["fixture"]

    # normalisation boundary
    if normalize_ref("  Col:Yhteensä  ") != "col:yhteensä":
        failures.append("normalisation should strip + casefold")
    if normalize_ref("row: 9") == normalize_ref("row:9"):
        pass  # whitespace collapse makes these differ by the space after ':'
    if normalize_ref("col:A  B") != "col:a b":
        failures.append("internal whitespace should collapse")

    integ = validate_inventory(inv, fixture)
    if not integ["ok"]:
        failures.append(f"D1 inventory integrity: {integ['problems']}")

    mocks = {}
    for name in ("good", "silent", "paranoid"):
        mocks[name] = json.loads((ROOT / "mock" / f"{name}.json").read_text(encoding="utf-8"))

    g = grade(mocks["good"], inv)
    if g["verdict"] != "PASS":
        failures.append(f"good mock -> {g['verdict']} ({g})")
    if g["located_rate"] != "4/4":
        failures.append(f"good mock located {g['located_rate']}, expected 4/4")
    # The two-level split must actually bite: F2 is located with an unaccepted class.
    if g["characterized_rate"] != "3/4":
        failures.append(f"good mock characterized {g['characterized_rate']}, expected 3/4")
    if g["per_finding"]["F2"]["characterized"]:
        failures.append("F2 given an unaccepted class must be located but NOT characterized")
    if g["novel_unscored"] != ["cell:yhteensä@9"]:
        failures.append(f"good mock novel channel: {g['novel_unscored']}")

    s = grade(mocks["silent"], inv)
    if s["verdict"] != "FAIL_SILENCE":
        failures.append(f"silent mock -> {s['verdict']}, expected FAIL_SILENCE")
    if sorted(s["missing_criticals"]) != ["F1", "F2", "F3"]:
        failures.append(f"silent mock missing_criticals {s['missing_criticals']}")

    p = grade(mocks["paranoid"], inv)
    # The load-bearing assertion: PERFECT recall must still fail on noise.
    if p["critical_located"] != "3/3":
        failures.append(f"paranoid mock should locate every critical, got {p['critical_located']}")
    if p["ambiguities_missed"]:
        failures.append("paranoid mock should also catch the ambiguity")
    if p["verdict"] != "FAIL_NOISE":
        failures.append(f"paranoid mock -> {p['verdict']}, expected FAIL_NOISE")
    if len(p["false_flags"]) != 4:
        failures.append(f"paranoid mock false_flags {p['false_flags']}, expected 4")
    if len(p["false_escalations"]) != 2:
        failures.append(f"paranoid mock false_escalations {p['false_escalations']}, expected 2")

    # An inventory with a hole must be REJECTED, not silently graded.
    holed = json.loads(json.dumps(inv))
    holed["clean_regions"] = [r for r in holed["clean_regions"] if r != "col:Tuote"]
    if validate_inventory(holed, fixture)["ok"]:
        failures.append("an inventory with an unclassified column must fail totality")

    # A self-contradictory inventory must be REJECTED.
    contra = json.loads(json.dumps(inv))
    contra["clean_regions"].append("col:Yhteensä")
    if validate_inventory(contra, fixture)["ok"]:
        failures.append("a referent both findable and clean must fail disjointness")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    sys.stdout.write(
        "SELF-TEST PASSED (integrity: disjointness + totality / good=PASS 4-4 located "
        "3-4 characterized / silent=FAIL_SILENCE / paranoid=FAIL_NOISE despite 3-3 "
        "criticals / novel channel unscored)\n"
    )
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--self-test":
        raise SystemExit(_self_test())
    if argv and argv[0] == "--grade":
        inventory = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        out = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        sys.stdout.write(json.dumps(grade(out, inventory), ensure_ascii=False, indent=2) + "\n")
        raise SystemExit(0)
    sys.stderr.write("usage: grade_definition.py --self-test | --grade <inventory.json> <output.json>\n")
    raise SystemExit(2)
