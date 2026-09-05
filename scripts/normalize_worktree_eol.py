#!/usr/bin/env python3
"""Bring an EXISTING checkout into line with `.gitattributes`, safely.

Why this exists
---------------
`.gitattributes` governs what Git writes when it checks a file out. It does not
rewrite files that are already sitting in a working tree. A clone made before
the attributes file existed therefore keeps its CRLF working copy, and the
byte-exact guards inside frozen experiment harnesses keep reporting VOID on
artifacts that never changed:

    scripts/check_surfaced.py
      -> experimentL/harness/execute_recipe.py
        -> experimentJ/harness/macro_v2.py   verify_v1_source() at import time
          -> experimentI/harness/gate_I.py   hashed byte-exactly

Every file in that chain is frozen evidence or a historical harness, so the
only lawful repair is to make the working tree reproduce the committed bytes.
That is all this script does.

What it will and will not touch
-------------------------------
It rewrites a tracked file ONLY when the working copy differs from the
committed blob by line endings ALONE -- that is, when

    disk.replace(CRLF, LF) == blob

Anything else is a genuine local edit and is never touched. If any tracked file
has a substantive difference, the script REFUSES to apply and names the files,
because a bulk `git checkout -- .` or `git reset --hard` would silently discard
that work. Untracked files are never read or written.

Rewriting a file to its own committed bytes is the opposite of altering frozen
evidence: it restores the checkout to what the repository actually contains. No
hash is recorded, edited or re-frozen here.

Usage
-----
    python scripts/normalize_worktree_eol.py             # dry run: report only
    python scripts/normalize_worktree_eol.py --apply     # rewrite the EOL-only files
    python scripts/normalize_worktree_eol.py --self-test # exercise the safety rules

Exit codes: 0 nothing to do or applied cleanly; 1 refused, or dry run found work.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
CRLF = bytes([13, 10])
LF = bytes([10])


def _git(args: list[str], cwd: Path = LAB) -> bytes:
    out = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: "
                           f"{out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout


def tracked_files(root: Path = LAB) -> list[str]:
    raw = _git(["ls-files", "-z"], root)
    return [p.decode("utf-8") for p in raw.split(bytes([0])) if p]


def blob_bytes(rel: str, root: Path = LAB) -> bytes | None:
    """The committed bytes of `rel` at HEAD, or None if it is not in HEAD."""
    try:
        return _git(["show", f"HEAD:{rel}"], root)
    except RuntimeError:
        return None


def classify(root: Path = LAB) -> tuple[list[str], list[str]]:
    """(eol_only, substantive) tracked paths whose working copy differs from HEAD."""
    eol_only: list[str] = []
    substantive: list[str] = []
    for rel in tracked_files(root):
        path = root / rel
        if not path.is_file():
            continue
        blob = blob_bytes(rel, root)
        if blob is None:
            continue
        disk = path.read_bytes()
        if disk == blob:
            continue
        if disk.replace(CRLF, LF) == blob:
            eol_only.append(rel)
        else:
            substantive.append(rel)
    return eol_only, substantive


def apply(root: Path = LAB) -> int:
    eol_only, substantive = classify(root)
    if substantive:
        print("REFUSED: these tracked files differ from HEAD by more than line "
              "endings. They look like real local work, and this script will not "
              "overwrite them:")
        for rel in substantive:
            print(f"  {rel}")
        print("\nCommit, stash or revert them, then run this again.")
        return 1
    for rel in eol_only:
        (root / rel).write_bytes(blob_bytes(rel, root) or b"")
    print(f"normalized {len(eol_only)} file(s) to their committed bytes")
    return 0


def report(root: Path = LAB) -> int:
    eol_only, substantive = classify(root)
    if substantive:
        print(f"{len(substantive)} tracked file(s) differ substantively from HEAD "
              f"(these would BLOCK --apply):")
        for rel in substantive:
            print(f"  {rel}")
    if not eol_only:
        print("nothing to normalize: every tracked file already matches its "
              "committed bytes")
        return 0 if not substantive else 1
    print(f"{len(eol_only)} tracked file(s) differ from HEAD by line endings only:")
    for rel in eol_only[:20]:
        print(f"  {rel}")
    if len(eol_only) > 20:
        print(f"  ... and {len(eol_only) - 20} more")
    print("\nRun with --apply to rewrite them to their committed bytes.")
    return 1


# ---------------------------------------------------------------------------
# self-test -- builds throwaway repositories; never touches this one
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, why: str) -> None:
        if not cond:
            failures.append(why)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        _git(["init", "-q"], root)
        _git(["config", "user.email", "t@t"], root)
        _git(["config", "user.name", "t"], root)
        _git(["config", "core.autocrlf", "false"], root)

        (root / "text.txt").write_bytes(b"alpha" + LF + b"beta" + LF)
        (root / "keep.txt").write_bytes(b"one" + LF)
        (root / "bin.dat").write_bytes(bytes([0xFF, 0xFE]) + CRLF + bytes([0x80]))
        _git(["add", "-A"], root)
        _git(["commit", "-qm", "seed"], root)

        # a pre-existing CRLF checkout of a file whose blob is LF
        (root / "text.txt").write_bytes(b"alpha" + CRLF + b"beta" + CRLF)
        eol_only, substantive = classify(root)
        check(eol_only == ["text.txt"],
              f"an EOL-only difference must be detected: {eol_only}")
        check(substantive == [],
              f"nothing substantive should be reported yet: {substantive}")

        # a genuine local edit must BLOCK the whole apply, and survive it
        (root / "keep.txt").write_bytes(b"one" + LF + b"my unsaved work" + LF)
        eol_only, substantive = classify(root)
        check(substantive == ["keep.txt"],
              f"a real edit must be classified substantive: {substantive}")
        rc = apply(root)
        check(rc == 1, "apply must refuse while a real edit is present")
        check((root / "keep.txt").read_bytes() == b"one" + LF + b"my unsaved work" + LF,
              "CANARY: a genuine local edit must survive a refused apply")
        check((root / "text.txt").read_bytes() == b"alpha" + CRLF + b"beta" + CRLF,
              "CANARY: a refused apply must change nothing at all")

        # with the edit resolved, apply normalizes exactly the EOL-only file
        (root / "keep.txt").write_bytes(b"one" + LF)
        rc = apply(root)
        check(rc == 0, "apply must succeed once no substantive diff remains")
        check((root / "text.txt").read_bytes() == b"alpha" + LF + b"beta" + LF,
              "the EOL-only file must now equal its committed bytes")
        check((root / "bin.dat").read_bytes() == bytes([0xFF, 0xFE]) + CRLF + bytes([0x80]),
              "CANARY: a binary carrying CRLF payload must not be rewritten")
        check(classify(root) == ([], []), "the tree must be clean afterwards")

        # untracked files are never considered
        (root / "scratch.tmp").write_bytes(b"x" + CRLF)
        check(classify(root) == ([], []),
              "CANARY: an untracked file must never enter the candidate set")

    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        return 1
    print("OK  self-test: 10 checks -- EOL-only diffs are found and normalized to "
          "the committed bytes; a genuine local edit blocks the apply and survives "
          "it untouched; binary payload and untracked files are never rewritten")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--apply" in argv:
        return apply()
    return report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
