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
It rewrites a tracked file ONLY when BOTH of these hold:

    disk.replace(CRLF, LF) == blob                  the difference is EOL-shaped
    restorable_text(disk) and restorable_text(blob)  and both sides are text

The second condition is not decoration. The byte test alone is satisfied by a
NON-text local edit -- committed payload `... LF ...` changed to `... CRLF ...`
is a content change wearing a line ending's clothes, and rewriting it would
destroy the operator's work.

`restorable_text` is deliberately NOT `verify_frozen.is_text`; see its docstring.
The strict integrity predicate rejects valid-UTF-8 files carrying ANSI escapes,
three of which are tracked here, and using it made the migration refuse to run
at all.

A tracked path the operator has DELETED counts as substantive and blocks the
run. Skipping it because it is not a regular file would let `--apply` reach the
index refresh, where `git add --renormalize .` can stage the deletion.

Anything else is a genuine local edit and is never touched. If any tracked file
has a substantive difference, the script REFUSES to apply -- before writing
anything at all -- and names the files, because a bulk `git checkout -- .` or
`git reset --hard` would silently discard that work. Untracked files are never
read or written.

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



def restorable_text(data: bytes) -> bool:
    """Positive text test for EOL RESTORATION. Deliberately not the integrity one.

    The two answer different questions, and the difference is load-bearing:

    `verify_frozen.is_text` asks *may I forgive this artifact's line-ending
    representation when checking its hash?* A false positive there lets a
    corrupted binary verify, so it is strict: valid UTF-8 AND no C0 control byte
    but tab, LF, CR.

    This asks *is this a file Git itself would have EOL-converted on checkout,
    such that restoring the committed bytes gives back what was committed?* Using
    the strict predicate here misclassifies real repository content:
    `experimentR/results/probe{1,2,3}_raw.txt` are raw terminal captures holding
    ANSI escape sequences (byte 27). They are valid UTF-8, Git converted them on
    checkout, and the strict test calls them non-text -- which made `--apply`
    refuse outright and the migration impossible to run at all.

    So this test drops only the control-byte arm and keeps the two that carry the
    safety property:

        no NUL          Git's own binary heuristic, and
        valid UTF-8     which arbitrary binary payload is not

    A non-text payload edited into an EOL shape is still refused, because such
    payload is not valid UTF-8 -- that is the canary in the self-test, and it is
    why this stays a positive classification rather than a byte-shape guess.

    The residual risk is narrow and named: a byte stream that is genuinely not
    text, yet decodes as UTF-8, given a local edit that is exactly EOL-shaped,
    would be restored. Nothing in this repository is such a file.
    """
    if bytes([0]) in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


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
    """(eol_only, substantive) tracked paths whose working copy differs from HEAD.

    Only a difference PROVEN to be textual line-ending representation may land in
    `eol_only`; everything else is substantive and blocks the migration.

    Two traps this guards, both of which let real local work be overwritten:

    * `disk.replace(CRLF, LF) == blob` is not on its own evidence of a line-ending
      difference. Committed non-text bytes holding `... LF ...`, locally edited to
      `... CRLF ...`, satisfy it exactly -- and that edit is payload, not
      representation. Both sides must be proven text first, by the same positive
      predicate the integrity checker uses.
    * A tracked path the user has DELETED is real local state. Skipping it because
      it is not a regular file would let `--apply` proceed to the index refresh,
      where `git add --renormalize .` can stage the deletion. A missing tracked
      path is therefore substantive, and blocks before anything is written.
    """
    eol_only: list[str] = []
    substantive: list[str] = []
    readable: list[str] = []
    for rel in tracked_files(root):
        path = root / rel
        if not path.exists():
            # locally deleted (or a broken symlink): real local state, never ours
            substantive.append(rel)
        elif path.is_file():
            readable.append(rel)
        # anything else -- a directory or a special file where a blob is tracked --
        # is left alone rather than guessed at.

    blobs = read_blobs(readable, root)
    for rel in readable:
        blob = blobs.get(rel)
        if blob is None:
            continue
        disk = (root / rel).read_bytes()
        if disk == blob:
            continue
        if (disk.replace(CRLF, LF) == blob
                and restorable_text(disk) and restorable_text(blob)):
            eol_only.append(rel)
        else:
            substantive.append(rel)
    return sorted(eol_only), sorted(substantive)


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
    # imported HERE, only so the self-test can assert the two predicates really
    # do differ on the case that blocked the migration. Production code in this
    # module deliberately does not use it -- see `restorable_text`.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verify_frozen import is_text as is_text_strict
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

        # (A) CANARY: a NON-TEXT tracked blob given an EOL-SHAPED local byte edit.
        # `disk.replace(CRLF, LF) == blob` is satisfied exactly, so the predicate
        # this script shipped with would have called it eol_only and overwritten
        # the operator's edit with the committed bytes. Positive text proof is
        # what stops it. The payload carries NO NUL, so the weaker "NUL means
        # binary" test would not have saved it either.
        payload_blob = bytes([0xFF, 0xFE]) + b"PK" + LF + bytes([0x80, 0x81])
        (root / "payload.bin").write_bytes(payload_blob)
        _git(["add", "-A"], root)
        _git(["commit", "-qm", "payload"], root)
        edited = bytes([0xFF, 0xFE]) + b"PK" + CRLF + bytes([0x80, 0x81])
        (root / "payload.bin").write_bytes(edited)
        check(edited.replace(CRLF, LF) == payload_blob,
              "the canary edit must satisfy the OLD predicate, or it proves nothing")
        check(bytes([0]) not in edited,
              "the canary payload must contain NO NUL, or it only tests the old test")
        eol_only, substantive = classify(root)
        check("payload.bin" not in eol_only,
              "CANARY: a non-text local edit must NEVER be classified eol_only")
        check("payload.bin" in substantive,
              "a non-text local edit must be classified substantive")
        check(apply(root) == 1, "apply must refuse while that edit is present")
        check((root / "payload.bin").read_bytes() == edited,
              "CANARY: the non-text local edit must survive the refused apply "
              "byte for byte")
        (root / "payload.bin").write_bytes(payload_blob)     # restore for later checks

        # (A2) CANARY: real repository content -- a raw terminal capture holding
        # ANSI escape bytes -- is valid UTF-8 and Git converts it on checkout, so
        # it MUST stay eligible. The strict integrity predicate calls byte 27
        # non-text; using it here made --apply refuse outright on three tracked
        # experimentR probe files and the migration could not run at all.
        esc_blob = b"Thinking..." + LF + b"out" + bytes([27]) + b"[4D" + LF
        (root / "ansi_raw.txt").write_bytes(esc_blob)
        _git(["add", "-A"], root)
        _git(["commit", "-qm", "ansi"], root)
        (root / "ansi_raw.txt").write_bytes(esc_blob.replace(LF, CRLF))
        check(bytes([27]) in esc_blob, "the ANSI fixture must carry an escape byte")
        check(not is_text_strict(esc_blob),
              "the fixture must be one the STRICT integrity predicate rejects, "
              "or it does not reproduce the blocking case")
        check(restorable_text(esc_blob),
              "CANARY: valid-UTF-8 text with ANSI escapes must be restorable")
        eol_only, substantive = classify(root)
        check("ansi_raw.txt" in eol_only,
              "CANARY: an ANSI-carrying text file must be eligible, not blocking")
        check(apply(root) == 0, "apply must succeed with only such files present")
        check((root / "ansi_raw.txt").read_bytes() == esc_blob,
              "the ANSI file must be restored to its committed bytes")

        # (B) CANARY: a tracked path the operator has DELETED locally. Skipping it
        # because it is not a regular file would let --apply reach the index
        # refresh, where `git add --renormalize .` can stage the deletion.
        (root / "keep.txt").unlink()
        eol_only, substantive = classify(root)
        check("keep.txt" in substantive,
              "CANARY: a locally deleted tracked path must be substantive")
        check(apply(root) == 1, "apply must refuse while a tracked file is deleted")
        check(not (root / "keep.txt").exists(),
              "CANARY: the deletion must remain a working-tree deletion")
        staged = _git(["diff", "--cached", "--name-only", "HEAD"], root).strip()
        check(staged == b"",
              f"CANARY: the migration must stage nothing while refusing: {staged!r}")
        _git(["checkout", "--", "keep.txt"], root)           # restore for later checks

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
    print("OK  self-test: 31 checks -- EOL-only diffs are found and normalized to "
          "the committed bytes; a genuine local edit blocks the apply and survives "
          "it untouched; binary payload and untracked files are never rewritten; a batch far larger than a pipe buffer returns instead of deadlocking; a NON-TEXT edit shaped like an EOL change, and a tracked deletion, both refuse and survive untouched; valid-UTF-8 text carrying ANSI escapes stays eligible")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--apply" in argv:
        return apply()
    return report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
