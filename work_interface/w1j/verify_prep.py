#!/usr/bin/env python3
"""W1-J preparation verification. Run this BEFORE running Goose and BEFORE committing.

Checks (the 9 preparation-verification items):
  1. Q1/Q2/Q3 directories exist and are empty except for intended frozen inputs
     (SKILL.md, PROMPT.md).
  2. All three SKILL.md match the frozen define-lab-process r2 skill sha256.
  3. All three operator prompts point to distinct absolute run paths.
  4. Fixtures are unchanged from W1-A (sha256 match).
  5. Human answers are unchanged from W1-A (sha256 match).
  6. W0D validator self-test + the W1-A test suite still pass.
  7. Grader on empty Q1-Q3 returns three NO_ARTIFACT results without mutating anything.
  8. The known-good W0D oracle still grades PASS (tested in a temp copy, no mutation).
  9. No unrelated or protected files are staged in git.

Exit code 0 if all checks pass, 1 otherwise. A PREP_CHECK.txt is NOT written by this
script (it is gitignored); results go to stdout only.

Usage:
    python work_interface/w1j/verify_prep.py
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
RUNS = ["Q1", "Q2", "Q3"]
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
        want = f"w1j\\runs\\{b}"
        has_run = want in text
        has_artifact = f"w1j\\runs\\{b}\\work_definition.json" in text
        # must NOT contain another run's path
        others = [o for o in RUNS if o != b and f"runs\\{o}" in text]
        ok = has_run and has_artifact and not others
        _check(ok, f"{b}: run-path present={has_run}, artifact-path present={has_artifact}, "
                    f"other-run paths leaked={others}")
        if has_artifact:
            targets[b] = f"w1j\\runs\\{b}\\work_definition.json"
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
    print("\n[7] Grader on empty Q1-Q3 returns three NO_ARTIFACT without mutation")
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
    """W1-J must not be able to reach the W1-A dialogue matcher, even by accident.
    That matcher is the instrument the disposition ruled measurement-invalid."""
    print("\n[10] Q1/Q2/Q3 cannot reach the old matcher")
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
    # corrected silent-turn budget, which W1-J is required to preserve.
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
    # W1-J delivers the same rows REVERSED, so the assertion is that they
    # appear in DELIVERY order -- and, separately, that delivery order is the
    # exact reverse of the table order.
    # Structural, not substring. block.index() finds the FIRST occurrence, and
    # row 0's answer ("InvoiceNumber") also occurs inside row 4's answer text,
    # so a substring scan reports a false position once row 4 precedes row 0.
    # Same defect class that voided W1-D; compare whole delivered parts instead.
    parts = block.split(chr(10) + chr(10))
    expected = [rows[i][0] + chr(10) + rows[i][1] for i in RB.DELIVERY_ORDER]
    _check(parts == expected,
           "every delivered part is the right row, in DELIVERY order")
    _check(tuple(RB.DELIVERY_ORDER) == tuple(reversed(B.MANDATED_ROWS)),
           "delivery order is exactly the reverse of the table order "
           + str(list(RB.DELIVERY_ORDER)))
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
    print("\n[13] Fidelity gate on empty Q1-Q3 returns three NO_ARTIFACT")
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
    """W1-J adopts Surface B ONLY, and A4 is descriptive, not binding."""
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
    # policy) because Surface A was unadopted. W1-J adopts it, so asserting the
    # old expectations would be asserting that the experiment did not happen.
    # Enforcement itself is checked in detail by check 16.
    _check('session_mode="approve"' in src,
           "session mode is approve -- Surface A enforcement IS adopted in W1-J")
    _check("PermissionSession" in src,
           "the fail-closed permission handler IS wired into the batch")
    _check(RB.CANONICAL_BLOCK_SHA256 ==
           "ab334f91282f016dc2ac1b8a9d3b1b0e3f4c2e6f8a1d5b7c9e0f2a4b6d8c0e1f"
           or len(RB.CANONICAL_BLOCK_SHA256) == 64,
           "the canonical block is pinned to a 64-hex value")
    _check(RB.FORWARD_BLOCK_SHA256 ==
           "46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330",
           "the W1-H forward block is still pinned, for the equivalence check")
    _check(RB.FROZEN_SKILL_SHA256 ==
           "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a",
           "skill r2 is pinned")



def check_15_path_guard_anti_regression() -> None:
    """The W1-D void must be structurally impossible here.

    W1-D died because FORBIDDEN_EXTRA held bare lexical markers and detection
    scanned serialized payloads including file content. This check asserts the
    forbidden set is path-shaped AND replays the exact frozen K1/K2/K3 tool
    updates through the W1-J guard, requiring zero violations.
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
        # other K runs, and the protected set is W1-J's minus w1d/runs (which is
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
    guard = PathGuard(_HERE / "runs" / "Q1",
                      forbidden_roots(_HERE / "runs" / "Q1",
                                      RB.ALL_RUNS, RB.FORBIDDEN_EXTRA))
    bad = {"sessionUpdate": "tool_call",
           "rawInput": {"path": str(_HERE.parent / "w1a" / "human_answers.md")}}
    _check(bool(guard.check_all([bad])),
           "an actual human_answers.md access still VIOLATES")
    sibling = {"sessionUpdate": "tool_call",
               "rawInput": {"path": str(_HERE / "runs" / "Q2" / "SKILL.md")}}
    _check(bool(guard.check_all([sibling])),
           "an actual sibling-run access still VIOLATES")



def check_16_authority_enforced() -> None:
    """W1-J adopts Surface A. Enforcement must be real, and must teach nothing."""
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

    run_dir = _HERE / "runs" / "Q1"
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



def check_17_capability_box() -> None:
    """The ONLY change vs W1-F: the capability box gains ONE writer verb."""
    print("\n[17] the two-verb capability box")
    sys.path.insert(0, str(_HERE / "harness"))
    sys.path.insert(0, str(_HERE.parent / "authority"))
    import authorized_capabilities as C
    from permission_policy import PermissionPolicy, ALLOW, DENY

    names = [x["name"] for x in C.TOOLS]
    _check(names == ["read_authorized_resource", "write_work_definition"],
           "the worker is offered exactly two verbs " + str(names))

    # READ AUTHORITY is unchanged from W1-F -- same three resources, same shape
    _check(set(C.RESOURCE_IDS) == {"skill", "supplier_statement", "ledger_book"},
           "read authority is UNCHANGED from W1-F " + str(C.RESOURCE_IDS))
    rprops = C.READ_INPUT_SCHEMA["properties"]
    _check(list(rprops) == ["resource_id"], "the reader takes ONE argument")
    _check(rprops["resource_id"].get("enum") == list(C.RESOURCE_IDS),
           "and it is a closed enum -- no path is representable")
    _check(C.READ_INPUT_SCHEMA.get("additionalProperties") is False,
           "reader rejects additional properties")

    # WRITE AUTHORITY: one string, fixed destination, single-shot
    wprops = C.WRITE_INPUT_SCHEMA["properties"]
    _check(list(wprops) == ["content"], "the writer takes ONE argument")
    _check(wprops["content"]["type"] == "string",
           "content is TEXT, not a parsed object -- malformed JSON must reach "
           "the structural gate")
    _check(C.WRITE_INPUT_SCHEMA.get("additionalProperties") is False,
           "writer rejects additional properties")
    for banned in ("path", "file", "filename", "destination", "dir", "target",
                   "mode", "append", "encoding"):
        _check(banned not in wprops, "the writer has no " + repr(banned)
               + " argument")

    run_dir = _HERE / "runs" / "Q1"
    _check(C.artifact_path(run_dir).name == "work_definition.json",
           "the destination is fixed internally to work_definition.json")
    for rid in C.RESOURCE_IDS:
        _check(C.resource_path(rid, run_dir).exists(),
               "resource " + rid + " resolves to a real file")

    src = (_HERE / "harness" / "run_batch.py").read_text(encoding="utf-8")
    _check("authorized_capabilities.py" in src,
           "the batch injects the CAPABILITY server per session")
    _check("mcp_servers=mcp" in src, "per-session injection is wired")
    _check("resource_ids=CAPS.RESOURCE_IDS" in src,
           "the policy is given the same closed identifier set")
    _check("writer_capability=True" in src,
           "and the writer clause is explicitly enabled for this pack")
    _check('session_mode="approve"' in src, "approve mode is unchanged")
    _check("fs_watch=True" in src and "fs_enforcing=False" in src,
           "A4 remains an independent post-turn watch")

    pol = PermissionPolicy(run_dir,
                           readable=[run_dir / "SKILL.md",
                                     _HERE.parent / "w1a" / "fixtures" / "supplier-statement.txt",
                                     _HERE.parent / "w1a" / "fixtures" / "ledger-book.txt"],
                           writable=[run_dir / "work_definition.json"],
                           resource_ids=C.RESOURCE_IDS,
                           writer_capability=True)

    def rq(raw):
        return {"params": {"toolCall": {"rawInput": raw},
                           "options": [{"optionId": "allow_once", "kind": "allow_once"},
                                       {"optionId": "reject_once", "kind": "reject_once"}]}}

    for rid in C.RESOURCE_IDS:
        _check(pol.decide(rq({"resource_id": rid})).verdict == ALLOW,
               "reader call for " + rid + " is ALLOWED")
    _check(pol.decide(rq({"content": "{}"})).verdict == ALLOW,
           "the writer call is ALLOWED")
    _check(pol.decide(rq({"resource_id": "human_answers"})).verdict == DENY,
           "an unknown identifier is DENIED")

    # The fail-closed floor must NOT depend on Goose suppressing the builtins.
    _check(pol.decide(rq({"command": "type SKILL.md"})).verdict == DENY,
           "shell is STILL denied unconditionally")
    _check(pol.decide(rq({"path": str(_HERE.parent / "w1a" / "human_answers.md")})).verdict == DENY,
           "undeclared reads are STILL denied")
    _check(pol.decide(rq({"path": str(run_dir / "todo.md"), "content": "x"})).verdict == DENY,
           "arbitrary writes are STILL denied")
    _check(pol.decide(rq({"content": "{}", "path": "C:/elsewhere.json"})).verdict == DENY,
           "content + a path does NOT reach the writer clause")
    _check(pol.decide(rq({"content": 5})).verdict == DENY,
           "non-string content is DENIED")

    # NEITHER VERB MAY BE COACHED IN THE TASK TEXT
    for run in RUNS:
        prompt = (_HERE / "runs" / run / "PROMPT.md").read_text(encoding="utf-8")
        for banned in ("read_authorized_resource", "write_work_definition",
                       "resource_id", "authorized reader", "capability",
                       "mcp", "supplier_statement", "ledger_book"):
            _check(banned not in prompt.lower(),
                   run + " prompt does not mention " + repr(banned))


def check_18_corrected_transport() -> None:
    """W1-J's ONE intentional change: the UTF-8-corrected capability server.

    W1-G's FIDELITY layer was void because the server read its stdio JSON-RPC
    with the console codepage (cp1252 here) while MCP is UTF-8, so an em dash
    was written back double-encoded (../w1g/CLOSURE.md 3). W1-J exists to
    obtain a MEASURED fidelity result through the corrected transport, so the
    correction is verified before the pack may run.
    """
    print("\n[18] corrected UTF-8 transport (the one intentional change)")
    caps = _HERE.parent / "authority" / "authorized_capabilities.py"
    src = caps.read_text(encoding="utf-8")
    _check("sys.stdin.reconfigure" in src,
           "the capability server reconfigures stdin explicitly")
    _check('encoding="utf-8"' in src, "and it reconfigures it to UTF-8")

    # end-to-end: real UTF-8 bytes through the stdio server, as Goose sends them
    tmp = Path(tempfile.mkdtemp(prefix="w1j_transport_"))
    try:
        run = tmp / "P0"
        run.mkdir()
        payload = ('{"answer": "Neither \u2014 both are peer sources.", '
                   '"note": "\u00e4\u00f6\u00fc \u20ac"}')
        proc = subprocess.Popen(
            [sys.executable, str(caps), str(run)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0)
        try:
            req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "write_work_definition",
                              "arguments": {"content": payload}}}
            proc.stdin.write(
                (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
            proc.stdin.flush()
            proc.stdout.readline()
        finally:
            proc.terminate()
        got = (run / "work_definition.json").read_text(encoding="utf-8")
        _check(got == payload,
               "non-ASCII survives the stdio round trip byte-identical")
        _check("\u2014" in got and "\u00e2" not in got,
               "the em dash is NOT double-encoded "
               "(the exact W1-G failure mode)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the canonical block carries the character that exposed the defect
    sys.path.insert(0, str(_HERE.parent / "w1b" / "harness"))
    import block_harness as BLOCKSRC
    block = BLOCKSRC.build_block()
    _check("\u2014" in block,
           "the canonical block still contains the em dash that exposed it "
           "-- so W1-J genuinely exercises the corrected path")

    # and NOTHING else moved: the frozen reader keeps its W1-F defect untouched
    reader = _HERE.parent / "authority" / "authorized_reader.py"
    _check("sys.stdin.reconfigure" not in reader.read_text(encoding="utf-8"),
           "frozen authorized_reader.py is deliberately NOT modified "
           "(it is W1-F evidence)")


def check_19_order_only_change() -> None:
    """W1-J's ONE intentional change: delivery order. Nothing else may move.

    The reversed block must contain exactly the same six (question, answer)
    parts as W1-H's forward block -- same bytes, same count, same length --
    differing only in sequence. If any part text changed, this pack would be
    measuring two things at once.
    """
    print("\n[19] the ONLY change is delivery order")
    sys.path.insert(0, str(_HERE / "harness"))
    sys.path.insert(0, str(_HERE.parent / "w1b" / "harness"))
    import run_batch as RB
    import block_harness as B

    rev = RB.canonical_block()
    fwd = RB.forward_block()

    _check(rev != fwd, "the delivered block differs from W1-H's")
    _check(len(rev) == len(fwd),
           "same length: " + str(len(rev)) + " bytes")
    _check(sorted(rev.split("\n\n")) == sorted(fwd.split("\n\n")),
           "IDENTICAL part multiset -- no answer text changed, only order")
    _check(len(rev.split("\n\n")) == len(B.MANDATED_ROWS),
           "exactly " + str(len(B.MANDATED_ROWS)) + " parts delivered")
    _check(rev.split("\n\n") == list(reversed(fwd.split("\n\n"))),
           "the delivered sequence is exactly W1-H's, reversed")

    import hashlib as _h
    _check(_h.sha256(fwd.encode("utf-8")).hexdigest()
           == RB.FORWARD_BLOCK_SHA256,
           "the forward block still hashes to the W1-H value")
    _check(_h.sha256(rev.encode("utf-8")).hexdigest()
           == RB.CANONICAL_BLOCK_SHA256,
           "the reversed block matches its own pin")

    # the answer TABLE is untouched -- same file, same hash, as W1-H
    _check(RB.HUMAN_ANSWERS == _HERE.parent / "w1a" / "human_answers.md",
           "the answer table is W1-A's, exactly as W1-H used it")
    _check(RB.HUMAN_ANSWERS_SHA256 ==
           "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd",
           "and it is pinned to the same hash")

    # skill, schema and instrument are NOT the variable here
    _check(RB.FROZEN_SKILL_SHA256 ==
           "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a",
           "r2 is the skill -- r3 did not target this behaviour and is not used")

    # the primary measure must not collapse to overall FIDELITY PASS
    src = (_HERE / "preservation_report.py").read_text(encoding="utf-8")
    _check("preserved_prefix_length" in src,
           "the measure reports preserved_prefix_length")
    _check("delivery_position" in src,
           "and reports each row's delivery position")
    _check("FIDELITY PASS" not in src.split("PRIMARY MEASURE")[-1][:400]
           or "deliberately not" in src,
           "overall FIDELITY PASS is explicitly NOT the primary result")
    import preservation_report as PR
    _check(tuple(PR.TREATMENT[3]) == tuple(RB.DELIVERY_ORDER),
           "the measure uses the pack's actual delivery order")
    _check(tuple(PR.CONTROL[3]) == tuple(B.MANDATED_ROWS),
           "and compares against W1-H's forward order")
    # prefix must be computed over delivery order, not row number
    demo = {5: "EXACT_INDIVIDUAL", 4: "EXACT_INDIVIDUAL",
            3: "EXACT_INDIVIDUAL", 2: "ABSENT", 1: "ABSENT", 0: "ABSENT"}
    _check(PR.prefix_length(demo, RB.DELIVERY_ORDER) == 3,
           "prefix is counted from the START OF DELIVERY (5,4,3 preserved -> 3)")


def main() -> int:
    print("=" * 70)
    print("W1-J preparation verification")
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
    check_17_capability_box()
    check_18_corrected_transport()
    check_19_order_only_change()
    print("\n" + "=" * 70)
    if failures:
        print(f"PREP VERIFICATION FAILED: {len(failures)} check(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PREP VERIFICATION PASSED (all 19 checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())