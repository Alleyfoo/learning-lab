#!/usr/bin/env python3
"""W1-B grader: validate each F run's work_definition.json with the existing W0D
deterministic validator, and record PASS / refusal codes.

Read-only with respect to agent output. It never edits, repairs, renames, or moves a
run's `work_definition.json` (or its `SKILL.md`). It only reads and records. If a run
is bad, the result summary says so -- that is the experiment's signal, not something
to fix. If Goose writes to the wrong location, the run dir has no artifact and the
grader reports NO_ARTIFACT -- an honest end-to-end failure, not repaired.

W1-B isolates the skill-content question. The frozen W1-A skill is delivered to each
run as a local `SKILL.md` (byte-identical to the frozen revision), removing Goose
`load_skill` discovery from the experiment. The grader marks the run CONTESTED if its
`SKILL.md` differs from the frozen hash.

Usage:
    python work_interface/w1b/grade.py
        # grades work_interface/w1b/runs/F1..F3 against the frozen W1-A fixtures
        # (work_interface/w1a/fixtures)

    python work_interface/w1b/grade.py --runs DIR --fixtures DIR
        # grade an alternate set of run dirs / fixtures

Output:
    work_interface/w1b/RESULTS.md      -- human-readable summary table
    work_interface/w1b/RESULTS.json    -- machine-readable record
    also prints the summary to stdout

Per run the summary records:
  - status:  PASS | REFUSED | NO_ARTIFACT | UNPARSEABLE_JSON
  - skill_match: whether this run's SKILL.md matches the frozen W1-A sha256
  - for REFUSED: the sorted refusal codes and per-problem details
  - the sha256 of the agent's work_definition.json (provenance; detects later edits)
  - requested_authority (must be null) and any override/authority keys present

A run is PASS only if the W0D validator returns Report.valid with zero problems AND
its SKILL.md matches the frozen hash AND requested_authority is null with no override
keys. PASS means "valid Work Definition -- safe to enter the existing modelling/preview
path", NOT "established".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Repo-root import bootstrap, same convention as work_definition.py and the W1-A grader.
_HERE = Path(__file__).resolve().parent
_LAB = _HERE.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB / "taskmodel"))
sys.path.insert(0, str(_HERE.parent))  # so `import work_definition` resolves

import work_definition as wd  # noqa: E402

RUNS_DEFAULT = _HERE / "runs"
# Reuse the frozen W1-A fixtures unchanged (do not duplicate, do not alter).
FIXTURES_DEFAULT = _HERE.parent / "w1a" / "fixtures"
FROZEN_SKILL_SHA256 = "4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55"
RESULTS_MD = _HERE / "RESULTS.md"
RESULTS_JSON = _HERE / "RESULTS.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grade_run(run_dir: Path, fixtures: Path) -> dict:
    """Read one B run's work_definition.json and SKILL.md (read-only) and grade them.
    Never writes into the run directory."""
    record: dict = {"run": run_dir.name, "run_path": str(run_dir)}

    # --- skill delivery check -------------------------------------------------
    skill_path = run_dir / "SKILL.md"
    if not skill_path.is_file():
        record["skill_present"] = False
        record["skill_match"] = False
        record["skill_sha256"] = None
        record["status"] = "CONTESTED_SKILL"
        record["note"] = "SKILL.md missing from run dir -- delivery failed"
        return record
    skill_digest = _sha256(skill_path)
    record["skill_present"] = True
    record["skill_sha256"] = skill_digest
    record["skill_match"] = (skill_digest == FROZEN_SKILL_SHA256)

    # --- artifact grading -----------------------------------------------------
    artifact_path = run_dir / "work_definition.json"
    record["artifact"] = str(artifact_path)
    if not artifact_path.is_file():
        record["status"] = "NO_ARTIFACT"
        record["note"] = ("no work_definition.json in the run directory "
                          "(Goose wrote elsewhere or stopped early)")
        return record

    record["sha256"] = _sha256(artifact_path)
    raw_text = artifact_path.read_text(encoding="utf-8")
    try:
        artifact = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        record["status"] = "UNPARSEABLE_JSON"
        record["note"] = f"agent produced invalid JSON: {exc}"
        record["raw_first_line"] = raw_text.splitlines()[0] if raw_text.strip() else ""
        return record

    report = wd.validate(artifact, evidence_dir=fixtures)  # never raises
    codes = sorted(report.codes())
    record["status"] = "PASS" if report.valid else "REFUSED"
    record["codes"] = codes
    record["problems"] = [{"code": p.code, "where": p.where, "detail": p.detail}
                          for p in report.problems]
    if isinstance(artifact, dict):
        record["requested_authority"] = artifact.get("requested_authority")
        override_hits = [k for k in wd.OVERRIDE_KEYS if artifact.get(k)]
        record["override_keys_present"] = override_hits
        record["work_definition_version"] = artifact.get("work_definition_version")
        record["task_family"] = artifact.get("task_family")
    return record


def _render_md(runs: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# W1-B grading results")
    lines.append("")
    lines.append("Generated by `work_interface/w1b/grade.py`. The grader is read-only:")
    lines.append("it never edits, repairs, renames, or moves an agent's")
    lines.append("`work_definition.json` or `SKILL.md`. PASS means *valid Work Definition --")
    lines.append("safe to enter the existing modelling/preview path*, NOT *established*.")
    lines.append("")
    lines.append("## Skill delivery")
    lines.append("")
    lines.append(f"- frozen W1-A skill sha256: `{FROZEN_SKILL_SHA256}`")
    lines.append("")
    lines.append("## Per-run results")
    lines.append("")
    lines.append("| run | status | skill_match | codes (if refused) | authority | override keys | sha256 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in runs:
        run = r["run"]
        status = r["status"]
        sm = r.get("skill_match")
        sm_s = "yes" if sm is True else ("no" if sm is False else "-")
        codes = ", ".join(r["codes"]) if r.get("codes") else ""
        auth = r.get("requested_authority", "")
        ov = ", ".join(r.get("override_keys_present", [])) or ""
        sha = r.get("sha256", "")[:12] or "-"
        lines.append(f"| {run} | **{status}** | {sm_s} | {codes} | {auth!r} | {ov} | `{sha}` |")
    lines.append("")
    # contested skill note
    contested = [r for r in runs if r.get("status") == "CONTESTED_SKILL"]
    if contested:
        lines.append("> ⚠ CONTESTED: one or more run `SKILL.md` files differ from the frozen")
        lines.append("> W1-A revision (or are missing). A contested run did not use the pinned")
        lines.append("> skill content; discard it, do not repair it.")
        lines.append("")
    # detail blocks
    detail_needed = [r for r in runs
                     if r["status"] in ("REFUSED", "UNPARSEABLE_JSON", "NO_ARTIFACT",
                                        "CONTESTED_SKILL")]
    if detail_needed:
        lines.append("## Detail")
        lines.append("")
        for r in detail_needed:
            lines.append(f"### {r['run']} -- {r['status']}")
            lines.append("")
            if r["status"] == "CONTESTED_SKILL":
                lines.append(f"- {r.get('note','')}")
                if r.get("skill_sha256"):
                    lines.append(f"- SKILL.md sha256: `{r['skill_sha256']}`")
            elif r["status"] == "NO_ARTIFACT":
                lines.append(r.get("note", ""))
            elif r["status"] == "UNPARSEABLE_JSON":
                lines.append(f"- note: {r.get('note')}")
                lines.append(f"- first line: `{r.get('raw_first_line', '')}`")
            else:  # REFUSED
                for p in r.get("problems", []):
                    lines.append(f"- `{p['code']}` @ `{p['where']}` -- {p['detail']}")
            lines.append("")
    # pass-rate summary
    n = len(runs)
    npass = sum(1 for r in runs if r["status"] == "PASS")
    lines.append("## Pass rate")
    lines.append("")
    lines.append(f"**{npass}/{n} PASS** (primary W1-B success criterion: 3/3).")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Grade W1-B runs with the W0D validator.")
    ap.add_argument("--runs", default=str(RUNS_DEFAULT),
                    help="directory containing F1..F3 run subdirs")
    ap.add_argument("--fixtures", default=str(FIXTURES_DEFAULT),
                    help="frozen fixture directory (evidence_dir for the validator); "
                         "defaults to the frozen W1-A fixtures")
    args = ap.parse_args(argv)

    runs_dir = Path(args.runs).resolve()
    fixtures = Path(args.fixtures).resolve()
    if not fixtures.is_dir():
        print(f"Fixtures directory not found: {fixtures}", file=sys.stderr)
        return 2

    run_dirs = sorted([d for d in runs_dir.iterdir()
                       if d.is_dir() and d.name.startswith("F")]
                      if runs_dir.is_dir() else [])
    if not run_dirs:
        print(f"No F* run directories found under {runs_dir}", file=sys.stderr)
        return 2

    runs = [_grade_run(d, fixtures) for d in run_dirs]

    md = _render_md(runs)
    RESULTS_MD.write_text(md, encoding="utf-8")
    RESULTS_JSON.write_text(
        json.dumps({"frozen_skill_sha256": FROZEN_SKILL_SHA256, "runs": runs}, indent=2),
        encoding="utf-8")

    print(md)
    print("\n" + "-" * 60)
    print(f"Wrote {RESULTS_MD} and {RESULTS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())