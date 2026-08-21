#!/usr/bin/env python3
"""v0+C — the v0 Work Definition envelope plus the output provenance surface.

**Additive wrapper. `work_definition.py` is imported, never modified.** Every v0
rule, code and behaviour applies unchanged; v0+C only adds the requirement that
`output.reports_fields` and `output.context_fields` carry the same provenance
surface `body.match_on` and `body.compare[]` already have.

```json
"output": {
  "reports_fields": [...],
  "context_fields": [...],
  "provenance": {
    "reports_fields": {"basis": "human_confirmed", "confirmation": "<id>"},
    "context_fields": {"basis": "human_confirmed", "confirmation": "<id>"}
  }
}
```

This is the W1-K **treatment** schema. Arm A validates against plain v0, arm B
against v0+C. The two differ in exactly this surface and nothing else.

Design constraints carried from the v0 envelope:

```text
one scalar basis per decision      never a list, mirroring _check_basis
the confirmation id must EXIST     a dangling citation is not provenance
no new vocabulary                  basis reuses the v0 evidence vocabulary
additive only                      no v0 rule is relaxed, renamed or removed
```

    python work_definition_c.py --self-test
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import work_definition as v0  # noqa: E402
from task_model import Problem, Report  # noqa: E402

# The codes v0+C adds. Named, like every other refusal in this lab.
OUTPUT_PROVENANCE_CODES = (
    "output_provenance_missing",
    "output_provenance_entry_missing",
    "output_provenance_basis_invalid",
    "output_provenance_confirmation_missing",
    "output_provenance_confirmation_unknown",
)

REQUIRED_ENTRIES = ("reports_fields", "context_fields")

# Pinned so the self-test can prove the frozen validator was not touched.
V0_SHA256 = (
    "9e686bae2881e3afaef2850d77ce12e57326c8b2a16f0ccd86ee1e821f035a5a")


def _confirmation_ids(raw: dict) -> set[str]:
    out: set[str] = set()
    confs = raw.get("human_confirmations")
    if isinstance(confs, list):
        for c in confs:
            if isinstance(c, dict) and isinstance(c.get("id"), str):
                out.add(c["id"])
    elif isinstance(confs, dict):
        out.update(k for k in confs if isinstance(k, str))
    return out


def check_output_provenance(raw: Any) -> list[Problem]:
    """The ONLY thing v0+C adds. Structural, and named on failure."""
    problems: list[Problem] = []
    if not isinstance(raw, dict):
        return problems
    where = "<work_definition>:output.provenance"

    output = raw.get("output")
    if not isinstance(output, dict):
        # v0 already reports a malformed/missing output; do not double-report.
        return problems

    prov = output.get("provenance")
    if not isinstance(prov, dict):
        problems.append(Problem(
            "output_provenance_missing", where,
            "output.provenance is required and must be an object with one "
            f"entry for each of {list(REQUIRED_ENTRIES)}"))
        return problems

    known = _confirmation_ids(raw)
    for key in REQUIRED_ENTRIES:
        entry = prov.get(key)
        if not isinstance(entry, dict):
            problems.append(Problem(
                "output_provenance_entry_missing", f"{where}.{key}",
                f"output.provenance.{key} is required and must be an object "
                f"with a scalar 'basis' and a 'confirmation' id"))
            continue

        basis = entry.get("basis")
        if not isinstance(basis, str) or basis not in v0.BASIS_VOCABULARY:
            problems.append(Problem(
                "output_provenance_basis_invalid", f"{where}.{key}.basis",
                f"basis must be a single scalar string from "
                f"{list(v0.BASIS_VOCABULARY)}, got {basis!r}"))

        cid = entry.get("confirmation")
        if not isinstance(cid, str) or not cid:
            problems.append(Problem(
                "output_provenance_confirmation_missing",
                f"{where}.{key}.confirmation",
                "a confirmation id is required; a provenance slot with no "
                "citation records nothing"))
        elif known and cid not in known:
            problems.append(Problem(
                "output_provenance_confirmation_unknown",
                f"{where}.{key}.confirmation",
                f"{cid!r} is cited but is not an id in human_confirmations "
                f"{sorted(known)}"))
    return problems


def validate(artifact: Any, evidence_dir: Optional[Path] = None) -> Report:
    """v0, unchanged, plus the output provenance surface."""
    report = v0.validate(artifact, evidence_dir=evidence_dir)
    extra = check_output_provenance(v0.parse(artifact))
    if not extra:
        return report
    return Report(problems=list(report.problems) + extra)


# ---------------------------------------------------------------------------

def _self_test() -> int:
    fails: list[str] = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}"
              + (f"  -- {detail}" if detail else ""))
        if not ok:
            fails.append(label)

    fixtures = HERE.parent / "w1a" / "fixtures"
    oracle_path = HERE.parent / "cases" / "W0B_corrected.json"
    import json
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))

    print("[1] v0 is unchanged by this module")
    r = v0.validate(oracle, evidence_dir=fixtures)
    check(r.valid, "the known-good oracle still passes plain v0",
          str(sorted(r.codes()))[:70])

    print("\n[2] the same artifact FAILS v0+C until it declares provenance")
    rc = validate(oracle, evidence_dir=fixtures)
    check(not rc.valid, "v0+C refuses it")
    check("output_provenance_missing" in rc.codes(),
          "and names the missing surface", str(sorted(rc.codes())))

    print("\n[3] a correctly declared provenance surface passes")
    good = json.loads(json.dumps(oracle))
    cid = None
    confs = good.get("human_confirmations")
    if isinstance(confs, list) and confs:
        cid = confs[0].get("id")
    elif isinstance(confs, dict) and confs:
        cid = sorted(confs)[0]
    good["output"]["provenance"] = {
        "reports_fields": {"basis": "human_confirmed", "confirmation": cid},
        "context_fields": {"basis": "human_confirmed", "confirmation": cid}}
    rg = validate(good, evidence_dir=fixtures)
    check(rg.valid, "v0+C accepts it", str(sorted(rg.codes()))[:70])

    print("\n[4] each failure mode is named separately")
    cases = {
        "output_provenance_entry_missing":
            {"reports_fields": {"basis": "human_confirmed",
                                "confirmation": cid}},
        "output_provenance_basis_invalid":
            {"reports_fields": {"basis": ["human_confirmed"],
                                "confirmation": cid},
             "context_fields": {"basis": "human_confirmed",
                                "confirmation": cid}},
        "output_provenance_confirmation_missing":
            {"reports_fields": {"basis": "human_confirmed"},
             "context_fields": {"basis": "human_confirmed",
                                "confirmation": cid}},
        "output_provenance_confirmation_unknown":
            {"reports_fields": {"basis": "human_confirmed",
                                "confirmation": "Q_nonexistent"},
             "context_fields": {"basis": "human_confirmed",
                                "confirmation": cid}},
    }
    for code, prov in cases.items():
        bad = json.loads(json.dumps(good))
        bad["output"]["provenance"] = prov
        rb = validate(bad, evidence_dir=fixtures)
        check(code in rb.codes(), f"{code} is reported",
              str(sorted(rb.codes()))[:80])

    print("\n[5] v0+C is strictly additive")
    check(all(c in v0.WORK_DEFINITION_PROBLEM_CODES or c in OUTPUT_PROVENANCE_CODES
              for c in rc.codes()),
          "every code is either a v0 code or one of the five new ones")
    check(len(OUTPUT_PROVENANCE_CODES) == 5, "five new codes, all named")
    # The real property, not a text scan: this module performs no writes at
    # all, so it cannot modify the frozen validator or anything else.
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check("open" not in called, "the module never calls open()")
    attrs = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    for w in ("write_text", "write_bytes", "unlink", "rename", "mkdir"):
        check(w not in attrs, f"the module never calls {w}()")
    v0_path = HERE.parent / "work_definition.py"
    import hashlib as _h
    check(_h.sha256(v0_path.read_bytes()).hexdigest()
          == V0_SHA256, "the frozen v0 validator is byte-unchanged")

    print("\n" + "=" * 70)
    if fails:
        print(f"v0+C SELF-TEST FAILED: {len(fails)} check(s)")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("v0+C SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        raise SystemExit(_self_test())
    print(__doc__)
