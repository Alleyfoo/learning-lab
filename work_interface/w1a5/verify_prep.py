#!/usr/bin/env python3
"""W1-A5 preparation verification. Run this BEFORE running Goose and BEFORE committing.

Checks (the 9 preparation-verification items):
  1. E1/E2/E3 directories exist and are empty except for intended frozen inputs
     (SKILL.md, PROMPT.md).
  2. All three SKILL.md match the frozen W1-A skill sha256.
  3. All three operator prompts point to distinct absolute run paths.
  4. Fixtures are unchanged from W1-A (sha256 match).
  5. Human answers are unchanged from W1-A (sha256 match).
  6. W0D validator self-test + the W1-A test suite still pass.
  7. Grader on empty E1-E3 returns three NO_ARTIFACT results without mutating anything.
  8. The known-good W0D oracle still grades PASS (tested in a temp copy, no mutation).
  9. No unrelated or protected files are staged in git.

Exit code 0 if all checks pass, 1 otherwise. A PREP_CHECK.txt is NOT written by this
script (it is gitignored); results go to stdout only.

Usage:
    python work_interface/w1a5/verify_prep.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_W1A = _HERE.parent / "w1a"
_LAB = _HERE.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB / "taskmodel"))
sys.path.insert(0, str(_HERE.parent))

import work_definition as wd  # noqa: E402

FROZEN_SKILL_SHA256 = "4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55"
FIXTURE_SHA = {
    "supplier-statement.txt": "d0cb95ab5755bef320390f11899c53034548a60678e27430882e556ce1a45feb",
    "ledger-book.txt": "284861d7d948dd6f0cd3a5e7826a6794d15db0ce2aafe108dafa37752c36f25e",
}
HUMAN_ANSWERS_SHA = "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd"
PROTECTED = [
    ".github/workflows/ci-full.yml",
    "scripts/ci_build_smoke.py",
    "scripts/smoke/ci_gui_smoke.py",
    "scripts/checks/check_update_correctness_signatures.py",
]
RUNS = ["E1", "E2", "E3"]
ALLOWED_RUN_ENTRIES = {"SKILL.md", "PROMPT.md"}

failures: list[str] = []


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(ok: bool, msg: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        failures.append(msg)


def check_1_dirs() -> None:
    print("\n[1] Run directories exist and contain only frozen inputs")
    for b in RUNS:
        d = _HERE / "runs" / b
        if not d.is_dir():
            _check(False, f"{b}: run dir missing at {d}")
            continue
        entries = sorted(p.name for p in d.iterdir())
        extra = [e for e in entries if e not in ALLOWED_RUN_ENTRIES]
        missing = [e for e in ALLOWED_RUN_ENTRIES if e not in entries]
        ok = not extra and not missing
        _check(ok, f"{b}: entries={entries} (expected {sorted(ALLOWED_RUN_ENTRIES)})")
        if extra:
            print(f"      unexpected: {extra}")
        if missing:
            print(f"      missing: {missing}")


def check_2_skill() -> None:
    print("\n[2] All three SKILL.md match the frozen W1-A skill sha256")
    for b in RUNS:
        p = _HERE / "runs" / b / "SKILL.md"
        if not p.is_file():
            _check(False, f"{b}: SKILL.md missing")
            continue
        d = _sha(p)
        _check(d == FROZEN_SKILL_SHA256, f"{b}: SKILL.md sha256={d} (frozen={FROZEN_SKILL_SHA256})")


def check_3_prompts() -> None:
    print("\n[3] Operator prompts point to distinct absolute run paths")
    targets: dict[str, str] = {}
    for b in RUNS:
        p = _HERE / "runs" / b / "PROMPT.md"
        if not p.is_file():
            _check(False, f"{b}: PROMPT.md missing")
            continue
        text = p.read_text(encoding="utf-8")
        # the run-path line and the artifact write path must both name this run's dir
        want = f"w1a5\\runs\\{b}"
        has_run = want in text
        has_artifact = f"w1a5\\runs\\{b}\\work_definition.json" in text
        # must NOT contain another run's path
        others = [o for o in RUNS if o != b and f"runs\\{o}" in text]
        ok = has_run and has_artifact and not others
        _check(ok, f"{b}: run-path present={has_run}, artifact-path present={has_artifact}, "
                    f"other-run paths leaked={others}")
        if has_artifact:
            targets[b] = f"w1a5\\runs\\{b}\\work_definition.json"
    distinct = len(set(targets.values())) == len(targets) and len(targets) == len(RUNS)
    _check(distinct, f"distinct artifact targets: {sorted(targets.values())}")


def check_4_fixtures() -> None:
    print("\n[4] Fixtures unchanged from W1-A (sha256 match)")
    for name, want in FIXTURE_SHA.items():
        p = _W1A / "fixtures" / name
        if not p.is_file():
            _check(False, f"fixture missing: {p}")
            continue
        d = _sha(p)
        _check(d == want, f"{name}: sha256={d} (expected {want})")


def check_5_answers() -> None:
    print("\n[5] Human answers unchanged from W1-A (sha256 match)")
    p = _W1A / "human_answers.md"
    if not p.is_file():
        _check(False, f"human_answers.md missing: {p}")
        return
    d = _sha(p)
    _check(d == HUMAN_ANSWERS_SHA, f"human_answers.md sha256={d} (expected {HUMAN_ANSWERS_SHA})")


def check_6_tests() -> None:
    print("\n[6] W0D validator self-test + W1-A test suite still pass")
    # self-test
    r = subprocess.run([sys.executable, "work_definition.py", "--self-test"],
                       cwd=str(_HERE.parent), capture_output=True, text=True)
    ok1 = r.returncode == 0
    _check(ok1, f"work_definition.py --self-test exit={r.returncode} "
                f"({r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()})")
    # pytest suite
    r2 = subprocess.run([sys.executable, "-m", "pytest", "test_work_definition.py", "-q"],
                        cwd=str(_HERE.parent), capture_output=True, text=True)
    ok2 = r2.returncode == 0
    tail = r2.stdout.strip().splitlines()[-1] if r2.stdout.strip() else r2.stderr.strip()
    _check(ok2, f"pytest test_work_definition.py exit={r2.returncode} ({tail})")


def check_7_grader_empty() -> None:
    print("\n[7] Grader on empty E1-E3 returns three NO_ARTIFACT without mutation")
    # snapshot run dir contents (names + mtimes + hashes of frozen inputs)
    before: dict[str, dict] = {}
    for b in RUNS:
        d = _HERE / "runs" / b
        before[b] = {p.name: (p.stat().st_mtime_ns, _sha(p)) for p in d.iterdir()}
    r = subprocess.run([sys.executable, str(_HERE / "grade.py")],
                       capture_output=True, text=True)
    ok_run = r.returncode == 0
    # parse RESULTS.json
    res = json.loads((_HERE / "RESULTS.json").read_text(encoding="utf-8"))
    statuses = {x["run"]: x["status"] for x in res["runs"]}
    all_noart = all(statuses.get(b) == "NO_ARTIFACT" for b in RUNS)
    # mutation check: frozen inputs unchanged, no new tracked files appeared in run dirs
    mutated = []
    for b in RUNS:
        d = _HERE / "runs" / b
        after = {p.name: (p.stat().st_mtime_ns, _sha(p)) for p in d.iterdir()}
        if after != before[b]:
            mutated.append(b)
    _check(ok_run and all_noart and not mutated,
           f"grader exit={r.returncode}, statuses={statuses}, mutated={mutated}")


def check_8_oracle() -> None:
    print("\n[8] Known-good W0D oracle still grades PASS (temp copy, no mutation)")
    oracle_path = _HERE.parent / "cases" / "W0B_corrected.json"
    if not oracle_path.is_file():
        _check(False, f"oracle missing: {oracle_path}")
        return
    with tempfile.TemporaryDirectory() as td:
        # copy fixtures + oracle into temp so the original paths are untouched
        tdp = Path(td)
        shutil.copy(_W1A / "fixtures" / "supplier-statement.txt", tdp)
        shutil.copy(_W1A / "fixtures" / "ledger-book.txt", tdp)
        artifact = json.loads(oracle_path.read_text(encoding="utf-8"))
        rep = wd.validate(artifact, evidence_dir=tdp)
        _check(rep.valid and not rep.codes(),
               f"oracle valid={rep.valid} codes={sorted(rep.codes())}")


def check_9_git() -> None:
    print("\n[9] No unrelated or protected files staged in git")
    r = subprocess.run(["git", "status", "--porcelain"], cwd=str(_LAB),
                       capture_output=True, text=True)
    staged_protected = []
    for line in r.stdout.splitlines():
        # staged = status in first two columns starts with a letter (M/A/R/C) not ' ' or '?'
        if not line:
            continue
        xy, _, path = line[:2], "", line[3:]
        if xy[0] in ("M", "A", "R", "C", "T"):
            for prot in PROTECTED:
                if path == prot or path.startswith(prot):
                    staged_protected.append(path)
    _check(not staged_protected, f"protected files staged: {staged_protected}")
    # also flag if any protected file shows as modified in the worktree (warn only)
    r2 = subprocess.run(["git", "status", "--porcelain"], cwd=str(_LAB),
                        capture_output=True, text=True)
    wt_protected = [line[3:] for line in r2.stdout.splitlines() if line
                    and any(line[3:] == prot for prot in PROTECTED)]
    if wt_protected:
        print(f"      (worktree-modified protected files present: {wt_protected} -- "
              "ensure they are NOT staged)")


def main() -> int:
    print("=" * 70)
    print("W1-A5 preparation verification")
    print("=" * 70)
    check_1_dirs()
    check_2_skill()
    check_3_prompts()
    check_4_fixtures()
    check_5_answers()
    check_6_tests()
    check_7_grader_empty()
    check_8_oracle()
    check_9_git()
    print("\n" + "=" * 70)
    if failures:
        print(f"PREP VERIFICATION FAILED: {len(failures)} check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PREP VERIFICATION PASSED (all 9 checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())