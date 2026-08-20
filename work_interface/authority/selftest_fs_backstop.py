#!/usr/bin/env python3
"""A4 self-test — synthetic mutations only. NO Goose, NO model execution.

Proves the backstop's five required behaviours plus the evidence-preservation
guarantee, using a throwaway directory that mimics a run directory.

    python work_interface/authority/selftest_fs_backstop.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fs_backstop as A  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


def fresh_run(tmp: Path, name: str) -> Path:
    d = tmp / name
    d.mkdir(parents=True)
    (d / "PROMPT.md").write_text("frozen prompt\n", encoding="utf-8", newline="\n")
    (d / "SKILL.md").write_text("frozen skill\n", encoding="utf-8", newline="\n")
    return d


def main() -> int:
    print("=" * 70)
    print("A4 FILESYSTEM AUTHORITY BACKSTOP -- synthetic self-test")
    print("No Goose, no model. Synthetic mutations only.")
    print("=" * 70)
    tmp = Path(tempfile.mkdtemp(prefix="a4_selftest_"))
    try:
        # --- 0. no mutation at all -------------------------------------
        print("\n[0] a run that touches nothing")
        d = fresh_run(tmp, "R0")
        before = A.snapshot(d)
        v = A.verdict(before, A.snapshot(d))
        check(not v.violated, "no mutation -> CLEAN", v.reason)

        # --- 1. designated artifact creation is ALLOWED ----------------
        print("\n[1] designated artifact creation")
        d = fresh_run(tmp, "R1")
        before = A.snapshot(d)
        (d / "work_definition.json").write_text('{"ok": true}',
                                                encoding="utf-8", newline="\n")
        v = A.verdict(before, A.snapshot(d))
        check(not v.violated, "creating work_definition.json is permitted", v.reason)
        check(len(v.allowed) == 1 and v.allowed[0].path == "work_definition.json",
              "the permitted mutation is recorded", str(v.allowed[0]))

        print("\n[1b] designated artifact re-write is also permitted")
        before2 = A.snapshot(d)
        (d / "work_definition.json").write_text('{"ok": false}',
                                                encoding="utf-8", newline="\n")
        v = A.verdict(before2, A.snapshot(d))
        check(not v.violated, "writing it again is permitted", v.reason)

        # --- 2. temp file creation is CONTESTED ------------------------
        print("\n[2] temp file creation (the W1-C H2 shape)")
        d = fresh_run(tmp, "R2")
        before = A.snapshot(d)
        (d / "temp_skill.txt").write_text("side effect\n", encoding="utf-8",
                                          newline="\n")
        v = A.verdict(before, A.snapshot(d))
        check(v.violated and v.code == A.VIOLATION_CODE,
              "temp file creation -> CONTESTED: FILESYSTEM_AUTHORITY_VIOLATION")
        m = v.mutations[0]
        check(m.kind == A.CREATED and m.path == "temp_skill.txt",
              "exact path and mutation type recorded", str(m))
        check((d / "temp_skill.txt").is_file(),
              "offending file PRESERVED as evidence, not cleaned up")

        print("\n[2b] a nested temp file is caught too")
        d = fresh_run(tmp, "R2b")
        before = A.snapshot(d)
        (d / "scratch").mkdir()
        (d / "scratch" / "notes.txt").write_text("x", encoding="utf-8", newline="\n")
        v = A.verdict(before, A.snapshot(d))
        check(v.violated and v.mutations[0].path == "scratch/notes.txt",
              "nested creation reported with a relative posix path",
              str(v.mutations[0]))

        # --- 3. SKILL.md modification is CONTESTED ---------------------
        print("\n[3] frozen input modification")
        d = fresh_run(tmp, "R3")
        before = A.snapshot(d)
        (d / "SKILL.md").write_text("tampered\n", encoding="utf-8", newline="\n")
        v = A.verdict(before, A.snapshot(d))
        check(v.violated, "SKILL.md modification -> CONTESTED")
        m = v.mutations[0]
        check(m.kind == A.MODIFIED and m.path == "SKILL.md",
              "reported as MODIFIED with before/after digests", str(m))

        # --- 4. deletion is CONTESTED ----------------------------------
        print("\n[4] deletion")
        d = fresh_run(tmp, "R4")
        before = A.snapshot(d)
        (d / "PROMPT.md").unlink()
        v = A.verdict(before, A.snapshot(d))
        check(v.violated and v.mutations[0].kind == A.DELETED
              and v.mutations[0].path == "PROMPT.md",
              "deletion -> CONTESTED, reported as DELETED", str(v.mutations[0]))

        print("\n[4b] deleting the designated artifact is NOT permitted")
        d = fresh_run(tmp, "R4b")
        (d / "work_definition.json").write_text("{}", encoding="utf-8", newline="\n")
        before = A.snapshot(d)
        (d / "work_definition.json").unlink()
        v = A.verdict(before, A.snapshot(d))
        check(v.violated, "deleting work_definition.json -> CONTESTED", v.reason)

        # --- 5. rename is CONTESTED ------------------------------------
        print("\n[5] rename")
        d = fresh_run(tmp, "R5")
        before = A.snapshot(d)
        (d / "SKILL.md").rename(d / "SKILL_renamed.md")
        v = A.verdict(before, A.snapshot(d))
        check(v.violated, "rename -> CONTESTED")
        m = v.mutations[0]
        check(m.kind == A.RENAMED and m.from_path == "SKILL.md"
              and m.path == "SKILL_renamed.md",
              "reported as a single RENAMED, not delete+create", str(m))

        print("\n[5b] renaming another file INTO the designated path is contested")
        d = fresh_run(tmp, "R5b")
        (d / "draft.json").write_text('{"smuggled": true}', encoding="utf-8",
                                      newline="\n")
        before = A.snapshot(d)
        (d / "draft.json").rename(d / "work_definition.json")
        v = A.verdict(before, A.snapshot(d))
        check(v.violated,
              "a rename into work_definition.json is not a permitted write",
              v.reason)

        # --- 6. evidence + multiplicity --------------------------------
        print("\n[6] several mutations at once, all recorded")
        d = fresh_run(tmp, "R6")
        before = A.snapshot(d)
        (d / "work_definition.json").write_text("{}", encoding="utf-8", newline="\n")
        (d / "temp.txt").write_text("t", encoding="utf-8", newline="\n")
        (d / "SKILL.md").write_text("tampered\n", encoding="utf-8", newline="\n")
        v = A.verdict(before, A.snapshot(d))
        kinds = sorted({m.kind for m in v.mutations})
        check(v.violated and len(v.mutations) == 2 and kinds == [A.CREATED, A.MODIFIED],
              "the artifact is permitted; the other two are violations",
              str([str(m) for m in v.mutations]))
        check(len(v.allowed) == 1,
              "the permitted artifact write is still recorded separately")
        rec = A.record(v)
        check(rec["filesystem_authority"] == A.VIOLATION_CODE
              and rec["evidence_preserved"] is True
              and len(rec["violations"]) == 2,
              "machine record is complete and untruncated")
        check((d / "temp.txt").is_file() and (d / "SKILL.md").is_file(),
              "nothing was cleaned up by the check itself")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    if FAILS:
        print(f"A4 SELF-TEST FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("A4 SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
