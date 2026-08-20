#!/usr/bin/env python3
"""W1-C batch exit-semantics proof. SYNTHETIC / OFFLINE ONLY.

Proves, before the experiment is executed:

  1. grade.py exits 0 after a correctly completed grading operation whatever the
     structural result -- 3/3, 2/3, 1/3, 0/3, and with NO_ARTIFACT present.
  2. structural REFUSED / NO_ARTIFACT are DATA, not process errors.
  3. fidelity_gate.py exits 0 when it successfully evaluates artifacts, including
     when it reports FID-1..FID-6 findings.
  4. nonzero from either tool is reserved for inability to perform the declared
     evaluation: instrument drift, malformed invocation, missing inputs.
  5. therefore the preregistered `&&` chain always reaches the fidelity gate
     after a correctly executed three-run batch.

Everything runs against a TEMPORARY MIRROR of the tools. H1/H2/H3 are never read
or written, and `w1c/RESULTS.*` and `w1c/FIDELITY.*` are never touched -- both
tools write results relative to their own directory, so the mirror absorbs them.

NO Goose. NO model. No experiment execution.

    python work_interface/w1c/exit_semantics_check.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WI = HERE.parent
LAB = WI.parent

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def build_mirror(tmp: Path) -> Path:
    """Copy the dependency closure the two tools need, and nothing else."""
    shutil.copytree(LAB / "taskmodel", tmp / "taskmodel")
    wi = tmp / "work_interface"
    (wi / "w1a").mkdir(parents=True)
    shutil.copytree(WI / "w1a" / "fixtures", wi / "w1a" / "fixtures")
    shutil.copyfile(WI / "w1a" / "human_answers.md", wi / "w1a" / "human_answers.md")
    (wi / "w1b" / "harness").mkdir(parents=True)
    shutil.copyfile(WI / "w1b" / "harness" / "block_harness.py",
                    wi / "w1b" / "harness" / "block_harness.py")
    (wi / "fidelity").mkdir(parents=True)
    shutil.copyfile(WI / "fidelity" / "fidelity_check.py",
                    wi / "fidelity" / "fidelity_check.py")
    shutil.copyfile(WI / "work_definition.py", wi / "work_definition.py")
    (wi / "w1c").mkdir(parents=True)
    for f in ("grade.py", "fidelity_gate.py"):
        shutil.copyfile(HERE / f, wi / "w1c" / f)
    return wi / "w1c"


def canon_rows():
    sys.path.insert(0, str(WI / "w1b" / "harness"))
    import block_harness as B
    rows = B.load_table_rows()
    return {i: rows[i][1] for i in B.MANDATED_ROWS}


def valid_artifact() -> dict:
    return json.loads((WI / "cases" / "W0B_corrected.json").read_text(encoding="utf-8"))


def refused_artifact() -> dict:
    """Synthetic REFUSED: a load-bearing open question (the aligned v0 rule)."""
    a = valid_artifact()
    a["open_questions"] = [{"id": "Q_synth", "question": "synthetic?",
                            "load_bearing": True, "status": "unresolved"}]
    return a


def fidelity_clean_artifact(canon) -> dict:
    """Synthetic artifact designed to yield ZERO fidelity findings."""
    a = valid_artifact()
    a["human_confirmations"] = [
        {"id": "C0", "question": "match key?", "answer": canon[0],
         "basis": "human_confirmed"},
        {"id": "C1", "question": "amount?", "answer": canon[1],
         "basis": "human_confirmed"},
        {"id": "C4", "question": "report row?", "answer": canon[4],
         "basis": "human_confirmed"},
        {"id": "C5", "question": "context?", "answer": canon[5],
         "basis": "human_confirmed"},
    ]
    a["body"]["match_on"]["basis"] = "human_confirmed"
    a["body"]["match_on"]["confirmation"] = "C0"
    for c in a["body"].get("compare") or []:
        if c.get("field") == "Amount":
            c["basis"] = "human_confirmed"
            c["confirmation"] = "C1"
    return a


def fidelity_findings_artifact() -> dict:
    """Synthetic artifact guaranteed to yield findings (basis 'observed')."""
    a = valid_artifact()
    a["human_confirmations"] = []
    a["body"]["match_on"]["basis"] = "observed"
    a["body"]["match_on"]["confirmation"] = None
    return a


def write_runs(pack: Path, arts: dict[str, dict | None]) -> None:
    runs = pack / "runs"
    if runs.exists():
        shutil.rmtree(runs)
    for name, art in arts.items():
        d = runs / name
        d.mkdir(parents=True)
        shutil.copyfile(WI / "skill" / "r2" / "skill.md", d / "SKILL.md")
        if art is not None:
            (d / "work_definition.json").write_text(
                json.dumps(art, indent=2), encoding="utf-8", newline="\n")


def run(tool: Path, *args) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(tool), *args],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    print("=" * 74)
    print("W1-C BATCH EXIT SEMANTICS -- synthetic/offline proof")
    print("H1/H2/H3 are never read or written. No Goose, no model.")
    print("=" * 74)

    canon = canon_rows()
    tmp = Path(tempfile.mkdtemp(prefix="w1c_exit_"))
    try:
        pack = build_mirror(tmp)
        grade, gate = pack / "grade.py", pack / "fidelity_gate.py"
        V, R = valid_artifact(), refused_artifact()

        print("\n[1] grade.py exits 0 for every structural rate")
        for label, arts, expect in [
            ("3/3", {"H1": V, "H2": V, "H3": V}, "3/3 PASS"),
            ("2/3", {"H1": V, "H2": V, "H3": R}, "2/3 PASS"),
            ("1/3", {"H1": V, "H2": R, "H3": R}, "1/3 PASS"),
            ("0/3", {"H1": R, "H2": R, "H3": R}, "0/3 PASS"),
        ]:
            write_runs(pack, arts)
            rc, out = run(grade)
            check(rc == 0, f"structural {label} -> exit 0", f"exit={rc}")
            check(expect in out, f"structural {label} reported as {expect}")

        print("\n[2] REFUSED / NO_ARTIFACT are data, not process errors")
        write_runs(pack, {"H1": V, "H2": R, "H3": None})
        rc, out = run(grade)
        check(rc == 0, "mixed PASS/REFUSED/NO_ARTIFACT -> exit 0", f"exit={rc}")
        check("REFUSED" in out and "NO_ARTIFACT" in out,
              "both outcomes appear in the report as data")

        print("\n[3] fidelity_gate.py exits 0 when it evaluates successfully")
        write_runs(pack, {"H1": fidelity_findings_artifact(),
                          "H2": fidelity_findings_artifact(),
                          "H3": fidelity_findings_artifact()})
        rc, out = run(gate)
        check(rc == 0, "gate reporting FINDINGS -> exit 0", f"exit={rc}")
        check("FIDELITY FINDINGS" in out, "findings were actually reported")
        fj = json.loads((pack / "FIDELITY.json").read_text(encoding="utf-8"))
        n = sum(len(r["findings"]) for r in fj["runs"])
        check(n > 0, "at least one FID finding recorded", f"{n} findings")

        write_runs(pack, {"H1": fidelity_clean_artifact(canon),
                          "H2": fidelity_clean_artifact(canon),
                          "H3": fidelity_clean_artifact(canon)})
        rc, out = run(gate)
        check(rc == 0, "gate reporting PASS -> exit 0", f"exit={rc}")
        check("3/3 FIDELITY PASS" in out, "clean artifacts report 3/3 FIDELITY PASS")

        write_runs(pack, {"H1": None, "H2": None, "H3": None})
        rc, out = run(gate)
        check(rc == 0, "gate with no artifacts -> exit 0 (NO_ARTIFACT is data)",
              f"exit={rc}")

        print("\n[4] nonzero is reserved for inability to evaluate")
        write_runs(pack, {"H1": V, "H2": V, "H3": V})
        rc, _ = run(grade, "--fixtures", str(tmp / "does_not_exist"))
        check(rc != 0, "grade.py: missing fixtures dir -> nonzero", f"exit={rc}")
        empty = tmp / "empty_runs"
        empty.mkdir(exist_ok=True)
        rc, _ = run(grade, "--runs", str(empty))
        check(rc != 0, "grade.py: no run directories -> nonzero", f"exit={rc}")

        checker = pack.parent / "fidelity" / "fidelity_check.py"
        original = checker.read_bytes()
        checker.write_bytes(original + b"\n# drift\n")
        rc, out = run(gate)
        check(rc != 0, "fidelity_gate: instrument drift -> nonzero", f"exit={rc}")
        check("drifted" in out.lower(), "drift is named in the error")
        checker.write_bytes(original)
        rc, _ = run(gate)
        check(rc == 0, "gate recovers once the pin is restored", f"exit={rc}")

        print("\n[5] the preregistered && chain reaches the fidelity gate")
        write_runs(pack, {"H1": R, "H2": R, "H3": R})   # worst case: 0/3 structural
        r = subprocess.run(
            f'"{sys.executable}" "{grade}" && "{sys.executable}" "{gate}"',
            shell=True, capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        check(r.returncode == 0, "0/3 structural && gate -> chain exit 0",
              f"exit={r.returncode}")
        check("0/3 PASS" in out, "the structural half ran and reported 0/3")
        check("fidelity" in out.lower() and "FIDELITY" in out,
              "the fidelity gate RAN despite 0/3 structural")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 74)
    if FAILS:
        print(f"EXIT-SEMANTICS CHECK FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("EXIT-SEMANTICS CHECK PASSED -- semantics already correct; nothing changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
