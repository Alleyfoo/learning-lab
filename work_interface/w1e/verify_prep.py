#!/usr/bin/env python3
"""W1-E preparation verification. Run this BEFORE running Goose and BEFORE committing.

Checks (the 9 preparation-verification items):
  1. M1/M2/M3 directories exist and are empty except for intended frozen inputs
     (SKILL.md, PROMPT.md).
  2. All three SKILL.md match the frozen define-lab-process r2 skill sha256.
  3. All three operator prompts point to distinct absolute run paths.
  4. Fixtures are unchanged from W1-A (sha256 match).
  5. Human answers are unchanged from W1-A (sha256 match).
  6. W0D validator self-test + the W1-A test suite still pass.
  7. Grader on empty M1-M3 returns three NO_ARTIFACT results without mutating anything.
  8. The known-good W0D oracle still grades PASS (tested in a temp copy, no mutation).
  9. No unrelated or protected files are staged in git.

Exit code 0 if all checks pass, 1 otherwise. A PREP_CHECK.txt is NOT written by this
script (it is gitignored); results go to stdout only.

Usage:
    python work_interface/w1e/verify_prep.py
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

FROZEN_SKILL_SHA256 = "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a"
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
RUNS = ["M1", "M2", "M3"]
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
    print("\n[2] All three SKILL.md match the frozen define-lab-process r2 skill sha256")
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
        want = f"w1e\\runs\\{b}"
        has_run = want in text
        has_artifact = f"w1e\\runs\\{b}\\work_definition.json" in text
        # must NOT contain another run's path
        others = [o for o in RUNS if o != b and f"runs\\{o}" in text]
        ok = has_run and has_artifact and not others
        _check(ok, f"{b}: run-path present={has_run}, artifact-path present={has_artifact}, "
                    f"other-run paths leaked={others}")
        if has_artifact:
            targets[b] = f"w1e\\runs\\{b}\\work_definition.json"
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
    print("\n[7] Grader on empty M1-M3 returns three NO_ARTIFACT without mutation")
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



def check_10_no_matcher() -> None:
    """W1-E must not be able to reach the W1-A dialogue matcher, even by accident.
    That matcher is the instrument the disposition ruled measurement-invalid."""
    print("\n[10] M1/M2/M3 cannot reach the old matcher")
    import ast
    src_path = _HERE.parent / "harness" / "single_block_harness.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    # Defined names: functions, classes, module-level assignments.
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    defined.add(tgt.id)
    # Referenced names, i.e. anything actually called or read as code.
    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    referenced |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}

    # Imported modules.
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)

    # NOTE: `next_silent_action` is deliberately NOT banned here. In W1-C it was
    # inherited from the W1-A matcher lineage; in the r2 lifecycle it IS the
    # corrected silent-turn budget, which W1-E is required to preserve.
    for sym in ("classify_turn", "intents_in", "segment_fragments", "match_message",
                "UNIQUE_MATCH", "MULTIPLE_MATCHES", "load_answer_table"):
        _check(sym not in defined and sym not in referenced,
               "no code defines or calls " + repr(sym) + " (docstrings may mention it)")
    bad_imports = [m for m in imported
                   if "acp_harness" in m or m.startswith("w1a") or ".w1a" in m]
    _check(not bad_imports, "imports no W1-A harness module " + str(sorted(imported)))

    sys.path.insert(0, str(_HERE.parent / "harness"))
    import single_block_harness as B
    for sym in ("classify_turn", "intents_in", "segment_fragments",
                "match_message", "load_answer_table"):
        _check(not hasattr(B, sym), "imported module exposes no " + sym + "()")
    mods = [m for m in sys.modules if "acp_harness" in m]
    _check(not mods, "no W1-A harness module is loaded (" + str(mods) + ")")


def check_11_block() -> None:
    """The canonical block is exactly the five SKILL-mandated answers, verbatim,
    and nothing excluded leaks into it."""
    print("\n[11] Canonical block integrity")
    sys.path.insert(0, str(_HERE / "harness"))
    import run_batch as RB
    import block_harness as B
    rows = B.load_table_rows()
    _check(len(rows) == 9, "frozen table reads 9 rows (got " + str(len(rows)) + ")")
    block = RB.canonical_block()
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    print("      block: " + str(len(block)) + " bytes, sha256=" + digest)
    _check(B.MANDATED_ROWS == (0, 1, 2, 3, 4, 5),
           "mandated rows are " + str(B.MANDATED_ROWS))
    for i in B.MANDATED_ROWS:
        cell, ans = rows[i]
        _check(cell in block and ans in block,
               "row " + str(i) + ": question and answer present verbatim")
    pos = [block.index(rows[i][1]) for i in B.MANDATED_ROWS]
    _check(pos == sorted(pos), "answers in frozen table order " + str(pos))
    for i in B.EXCLUDED_ROWS:
        _check(rows[i][1] not in block,
               "excluded row " + str(i) + " does not leak into the block")
    low = block.lower()
    for banned in ("refuse_run", "refuse_key", "left_then_right", "sorted_by_key",
                   "output_order", "both_same", "only_left", "classify", "purpose"):
        _check(banned not in low,
               "worker-owned term " + repr(banned) + " absent from the block")
    answers_src = B.HUMAN_ANSWERS.read_text(encoding="utf-8")
    stray = [l for l in block.splitlines() if l.strip() and l not in answers_src]
    _check(not stray, "every block line is verbatim from human_answers.md "
           + str(stray[:1]))



def check_12_fidelity_instrument() -> None:
    """The fidelity verdict is only meaningful against a DECLARED instrument."""
    print("\n[12] Frozen fidelity checker is pinned and intact")
    gate = _HERE / "fidelity_gate.py"
    _check(gate.is_file(), "fidelity_gate.py present")
    checker = _HERE.parent / "fidelity" / "fidelity_check.py"
    _check(checker.is_file(), "frozen fidelity_check.py present")
    if not (gate.is_file() and checker.is_file()):
        return
    import re as _re
    m = _re.search(r'FROZEN_FIDELITY_CHECK_SHA256 = \(\s*"([0-9a-f]{64})"',
                   gate.read_text(encoding="utf-8"))
    _check(bool(m), "fidelity_gate.py pins a checker sha256")
    if not m:
        return
    got = _sha(checker)
    _check(got == m.group(1),
           "frozen checker matches the pin: " + got[:16] + " vs " + m.group(1)[:16])

    # the gate must not be able to reach a question matcher either
    import ast
    tree = ast.parse(checker.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    bad = [m2 for m2 in imported if "acp_harness" in m2]
    _check(not bad, "frozen checker imports no dialogue harness " + str(sorted(imported)))


def check_13_fidelity_gate_empty() -> None:
    """On fresh run dirs the gate reports NO_ARTIFACT three times, mutating nothing."""
    print("\n[13] Fidelity gate on empty M1-M3 returns three NO_ARTIFACT")
    before = {p2: _sha(p2) for p2 in sorted(_HERE.rglob("*"))
              if p2.is_file() and "FIDELITY" not in p2.name}
    r = subprocess.run([sys.executable, str(_HERE / "fidelity_gate.py")],
                       capture_output=True, text=True, cwd=str(_LAB))
    _check(r.returncode == 0, "fidelity_gate exit=" + str(r.returncode))
    import json as _json
    fj = _HERE / "FIDELITY.json"
    if fj.is_file():
        data = _json.loads(fj.read_text(encoding="utf-8"))
        statuses = {x["run"]: x["status"] for x in data["runs"]}
        _check(all(v == "NO_ARTIFACT" for v in statuses.values()),
               "statuses=" + str(statuses))
    else:
        _check(False, "FIDELITY.json not written")
    after = {p2: _sha(p2) for p2 in sorted(_HERE.rglob("*"))
             if p2.is_file() and "FIDELITY" not in p2.name}
    mutated = [str(k.name) for k in before if before[k] != after.get(k)]
    _check(not mutated, "gate mutated nothing: " + str(mutated))



def check_14_lifecycle_and_shadow() -> None:
    """W1-E adopts Surface B ONLY, and A4 is descriptive, not binding."""
    print("\n[14] Surface-B lifecycle adopted; A4 shadow is non-binding")
    import inspect
    sys.path.insert(0, str(_HERE.parent / "harness"))
    sys.path.insert(0, str(_HERE / "harness"))
    import single_block_harness as L
    import run_batch as RB

    _check(L.CONTINUATION == "Continue.",
           "the activation is exactly 'Continue.' " + repr(L.CONTINUATION))
    _check(list(inspect.signature(L.next_message).parameters)
           == ["block_sent", "block"],
           "next_message cannot see the agent text")
    _check(L.next_message(False, "B") == ("B", L.SENT_BLOCK)
           and L.next_message(True, "B") == (L.CONTINUATION, L.SENT_CONTINUATION),
           "block once, then continuations")
    _check(list(inspect.signature(L.next_silent_action).parameters)
           == ["silent_streak"],
           "tool activity cannot reset the silent streak")
    _check(L.MAX_CONSECUTIVE_SILENT == 2, "silent budget is two")

    src = (_HERE / "harness" / "run_batch.py").read_text(encoding="utf-8")
    _check("fs_enforcing=False" in src,
           "the batch runs A4 in SHADOW mode (fs_enforcing=False)")
    # These two assertions are INVERTED relative to W1-D/W1-D2, deliberately.
    # There they asserted a permissive environment (mode auto, no permission
    # policy) because Surface A was unadopted. W1-E adopts it, so asserting the
    # old expectations would be asserting that the experiment did not happen.
    # Enforcement itself is checked in detail by check 16.
    _check('session_mode="approve"' in src,
           "session mode is approve -- Surface A enforcement IS adopted in W1-E")
    _check("PermissionSession" in src,
           "the fail-closed permission handler IS wired into the batch")
    _check(RB.CANONICAL_BLOCK_SHA256 ==
           "46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330",
           "the canonical block is pinned to the W1-B/W1-C value")
    _check(RB.FROZEN_SKILL_SHA256 ==
           "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a",
           "skill r2 is pinned")



def check_15_path_guard_anti_regression() -> None:
    """The W1-D void must be structurally impossible here.

    W1-D died because FORBIDDEN_EXTRA held bare lexical markers and detection
    scanned serialized payloads including file content. This check asserts the
    forbidden set is path-shaped AND replays the exact frozen K1/K2/K3 tool
    updates through the W1-E guard, requiring zero violations.
    """
    print("\n[15] W1-D void anti-regression: structured path detection")
    import json as _json
    sys.path.insert(0, str(_HERE / "harness"))
    sys.path.insert(0, str(_HERE.parent / "harness"))
    import run_batch as RB
    from path_guard import PathGuard
    from single_block_harness import forbidden_roots

    # every declared forbidden entry must be path-shaped and must EXIST
    bare = [str(x) for x in RB.FORBIDDEN_EXTRA
            if ("/" not in str(x) and "\\" not in str(x))]
    _check(not bare, "no bare lexical markers in FORBIDDEN_EXTRA " + str(bare))
    missing = [str(x) for x in RB.FORBIDDEN_EXTRA if not Path(x).exists()]
    _check(not missing,
           "every forbidden entry anchors to a real resource " + str(missing[:3]))

    # replay the frozen W1-D evidence that caused the void
    w1d_runs = _HERE.parent / "w1d" / "runs"
    total = 0
    for run in ("K1", "K2", "K3"):
        tr = w1d_runs / run / "acp_transcript.jsonl"
        if not tr.is_file():
            _check(False, "frozen W1-D evidence present for " + run)
            continue
        ups = []
        for line in tr.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            m = _json.loads(line)
            if m.get("dir") != "in":
                continue
            u = (m.get("msg") or {}).get("params", {}).get("update") or {}
            if u.get("sessionUpdate") in ("tool_call", "tool_call_update"):
                ups.append(u)
        total += len(ups)
        # Judge them in THEIR OWN context: cwd is the K run dir, siblings are the
        # other K runs, and the protected set is W1-E's minus w1d/runs (which is
        # the tree those updates legitimately live in). Staging this from an L run
        # would make K's own authorized SKILL.md reads look like forbidden-tree
        # access -- correct guard behaviour, wrong test.
        protected = [x for x in RB.FORBIDDEN_EXTRA
                     if Path(x) != _HERE.parent / "w1d" / "runs"]
        k_dir = w1d_runs / run
        guard = PathGuard(k_dir,
                          forbidden_roots(k_dir, ["K1", "K2", "K3"], protected))
        viol = guard.check_all(ups)
        _check(not viol,
               run + ": " + str(len(ups)) + " frozen tool updates -> no violation "
               + "; ".join(str(v) for v in viol)[:120])
    _check(total > 40, "replayed a meaningful number of updates: " + str(total))

    # and a real forbidden access still violates
    guard = PathGuard(_HERE / "runs" / "M1",
                      forbidden_roots(_HERE / "runs" / "M1",
                                      RB.ALL_RUNS, RB.FORBIDDEN_EXTRA))
    bad = {"sessionUpdate": "tool_call",
           "rawInput": {"path": str(_HERE.parent / "w1a" / "human_answers.md")}}
    _check(bool(guard.check_all([bad])),
           "an actual human_answers.md access still VIOLATES")
    sibling = {"sessionUpdate": "tool_call",
               "rawInput": {"path": str(_HERE / "runs" / "M2" / "SKILL.md")}}
    _check(bool(guard.check_all([sibling])),
           "an actual sibling-run access still VIOLATES")



def check_16_authority_enforced() -> None:
    """W1-E adopts Surface A. Enforcement must be real, and must teach nothing."""
    print("\n[16] Surface A enforced: approve mode + fail-closed policy")
    import inspect
    sys.path.insert(0, str(_HERE / "harness"))
    sys.path.insert(0, str(_HERE.parent / "harness"))
    sys.path.insert(0, str(_HERE.parent / "authority"))
    import run_batch as RB
    from permission_policy import PermissionPolicy, ALLOW, DENY

    src = (_HERE / "harness" / "run_batch.py").read_text(encoding="utf-8")
    _check('session_mode="approve"' in src, "the batch requests approve mode")
    _check("PermissionSession" in src, "the batch uses the permission session")
    _check("fs_watch=True" in src, "A4 runs as an independent post-turn watch")
    _check("fs_enforcing=False" in src,
           "A4 does not flip the lifecycle outcome; AUTHORITY is its own layer")

    run_dir = _HERE / "runs" / "M1"
    pol = PermissionPolicy(run_dir,
                           readable=[run_dir / "SKILL.md",
                                     _HERE.parent / "w1a" / "fixtures" / "supplier-statement.txt",
                                     _HERE.parent / "w1a" / "fixtures" / "ledger-book.txt"],
                           writable=[run_dir / "work_definition.json"])

    def rq(raw):
        return {"params": {"toolCall": {"rawInput": raw},
                           "options": [{"optionId": "allow_once", "kind": "allow_once"},
                                       {"optionId": "reject_once", "kind": "reject_once"}]}}

    _check(pol.decide(rq({"path": str(run_dir / "SKILL.md")})).verdict == ALLOW,
           "authorized SKILL.md read is ALLOWED")
    _check(pol.decide(rq({"path": str(run_dir / "work_definition.json"),
                          "content": "{}"})).verdict == ALLOW,
           "designated artifact write is ALLOWED")
    _check(pol.decide(rq({"command": "type SKILL.md"})).verdict == DENY,
           "shell is DENIED even for an authorized file")
    _check(pol.decide(rq({"path": str(run_dir / "todo.md"),
                          "content": "x"})).verdict == DENY,
           "an arbitrary write is DENIED")
    _check(pol.decide(rq({"path": str(_HERE.parent / "w1a" / "human_answers.md")})).verdict == DENY,
           "an undeclared read is DENIED")
    _check(pol.decide({"params": {}}).verdict == DENY,
           "an unparseable request is DENIED")

    # the prompt must not have been edited to route around the observed failure
    prompt = (run_dir / "PROMPT.md").read_text(encoding="utf-8")
    for banned in ("read_image", "text_editor", "use the tool", "instead of shell"):
        _check(banned not in prompt.lower(),
               "the prompt names no tool or route (" + banned + ")")
    _check("Windows-safe" in prompt,
           "the W1-D2 shell hint is still present -- the prompt was NOT edited "
           "to compensate for the enforcement")


def main() -> int:
    print("=" * 70)
    print("W1-E preparation verification")
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
    check_10_no_matcher()
    check_11_block()
    check_12_fidelity_instrument()
    check_13_fidelity_gate_empty()
    check_14_lifecycle_and_shadow()
    check_15_path_guard_anti_regression()
    check_16_authority_enforced()
    print("\n" + "=" * 70)
    if failures:
        print(f"PREP VERIFICATION FAILED: {len(failures)} check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PREP VERIFICATION PASSED (all 16 checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())