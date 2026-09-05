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
    return read_blobs([rel], root).get(rel)


def read_blobs(rels: list[str], root: Path = LAB) -> dict:
    """Committed bytes for many paths in ONE `git cat-file --batch` process.

    A `git show` per path costs a process spawn per file; this repository tracks
    thousands, which made the naive version unusable at repo scale. The batch
    protocol is: send `HEAD:<path>` per line, read back either
    `<oid> <type> <size>` followed by that many bytes and a newline, or a line
    ending in `missing`.
    """
    if not rels:
        return {}
    # The query goes through a temp FILE rather than a pipe. Writing all of it to
    # stdin before reading stdout deadlocks on any real repository: git fills the
    # ~64KB stdout pipe buffer and blocks, while this process is still blocked
    # writing stdin. A file as stdin lets git stream output while we read it.
    import tempfile
    with tempfile.TemporaryDirectory() as qdir:
        qfile = Path(qdir) / "batch-query"
        qfile.write_bytes(bytes().join(
            (f"HEAD:{r}".encode("utf-8") + LF) for r in rels))
        with qfile.open("rb") as stdin_handle:
            proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=str(root),
                                    stdin=stdin_handle, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
            out = _drain(proc, rels)
    return out


def _drain(proc, rels: list[str]) -> dict:
    """Read one `--batch` response per requested path."""
    out: dict = {}
    for rel in rels:
        header = proc.stdout.readline()
        if not header:
            break
        parts = header.split()
        if len(parts) < 3 or parts[-1] not in (b"blob", b"tree", b"commit", b"tag"):
            if header.rstrip().endswith(b"missing"):
                out[rel] = None
                continue
            # `<oid> blob <size>` is the normal shape; anything else is not a blob
            if len(parts) != 3:
                out[rel] = None
                continue
        size = int(parts[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)                    # the trailing newline
        out[rel] = data if parts[1] == b"blob" else None
    proc.stdout.close()
    proc.wait()
    return out


def classify(root: Path = LAB) -> tuple[list[str], list[str]]:
    """(eol_only, substantive) tracked paths whose working copy differs from HEAD."""
    eol_only: list[str] = []
    substantive: list[str] = []
    rels = [r for r in tracked_files(root) if (root / r).is_file()]
    blobs = read_blobs(rels, root)
    for rel in rels:
        path = root / rel
        blob = blobs.get(rel)
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
    blobs = read_blobs(eol_only, root)
    for rel in eol_only:
        data = blobs.get(rel)
        if data is not None:
            (root / rel).write_bytes(data)
    print(f"normalized {len(eol_only)} file(s) to their committed bytes")
    return refresh_index(root)


def refresh_index(root: Path = LAB) -> int:
    """Update the index's cached stat data, and PROVE no content was staged.

    Without this the migration leaves `git status` reporting thousands of
    modified files that `git diff` says are identical: the index still caches the
    old (CRLF) size, and `git update-index --refresh` does not clear it. A
    repository that looks massively modified when nothing changed is its own
    hazard -- the next worker cannot see a real edit in that noise.

    `git add --renormalize .` rewrites the stat data. Under this repository's
    `* -text` it must stage NOTHING, because the working tree already holds the
    committed bytes. That is asserted rather than assumed: if anything did get
    staged, the content changed, which must never happen here, and the operator
    is told to inspect it rather than trust this script.
    """
    _git(["add", "--renormalize", "."], root)
    staged = [p for p in _git(["diff", "--cached", "--name-only", "HEAD"],
                              root).decode("utf-8").split() if p]
    if staged:
        print("")
        print(f"WARNING: refreshing the index staged {len(staged)} content "
              f"change(s), which normalizing to committed bytes must never do:")
        for rel in staged[:20]:
            print(f"  {rel}")
        print("Inspect with `git diff --cached` and unstage with `git reset` "
              "before trusting this run.")
        return 1
    print("index stat data refreshed; nothing staged, so no content changed")
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
        check(_git(["diff", "--cached", "--name-only", "HEAD"], root).strip() == b"",
              "CANARY: the index refresh must stage NO content change")
        check(_git(["status", "--porcelain"], root).strip() == b"",
              "git status must be clean after a successful apply, not full of "
              "phantom modifications")

        # untracked files are never considered
        (root / "scratch.tmp").write_bytes(b"x" + CRLF)
        check(classify(root) == ([], []),
              "CANARY: an untracked file must never enter the candidate set")

        # CANARY for the pipe deadlock this script shipped with once: the first
        # batched version wrote every query to git's stdin BEFORE reading stdout,
        # so on a real repository git filled the ~64KB stdout pipe and blocked
        # while this process was still blocked writing stdin. Three fixture files
        # never came close to the buffer, so the self-test passed and a real run
        # hung. This fixture deliberately exceeds it in both directions.
        bulk = root / "bulk"
        bulk.mkdir()
        payload = (b"x" * 400) + LF
        for i in range(300):
            (bulk / f"f{i:03d}.txt").write_bytes(payload)
        _git(["add", "-A"], root)
        _git(["commit", "-qm", "bulk"], root)
        rels = [f"bulk/f{i:03d}.txt" for i in range(300)]
        total = len(rels) * len(payload)
        check(total > 64 * 1024,
              f"the bulk fixture must exceed a pipe buffer to prove anything: {total}")
        blobs = read_blobs(rels, root)
        check(len(blobs) == 300 and all(blobs[r] == payload for r in rels),
              "CANARY: reading many blobs at once must return them all, not hang")

    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        return 1
    print("OK  self-test: 15 checks -- EOL-only diffs are found and normalized to "
          "the committed bytes; a genuine local edit blocks the apply and survives "
          "it untouched; binary payload and untracked files are never rewritten; a batch far larger than a pipe buffer returns instead of deadlocking")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--apply" in argv:
        return apply()
    return report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
