#!/usr/bin/env python3
"""Verify every frozen artifact in the lab still hashes to its recorded value.

Why this exists
---------------
On 2026-08-14, regenerating one Experiment K fixture silently rewrote six
already-frozen ones: `openpyxl` embeds timestamps in the `.xlsx` zip, so
generator output is NOT byte-reproducible. K's hash checks would have reported
VOID on the next run, but only if someone ran them. Two specs also carried the
false claim that regeneration was byte-identical.

The corrections were prose. `operating_procedure.md` §2.1 is explicit that a
rule is only worth stating if it is checkable, so this is the check.

Design
------
The per-experiment `expected.json` files stay AUTHORITATIVE -- this script does
not copy their hashes, it reads them. Duplicating a frozen hash into a second
file would create two sources of truth and guarantee they eventually disagree.

Three hash layouts are in use across the programme, all collected:

    sibling   {"fixture": "fixtures/I1.csv", "sha256": "…"}
    prefixed  {"months_json": "…/months.json", "months_json_sha256": "…"}
    manifest  frozen_manifest.json -- artifacts no expected.json covers
              (the grammar's W1 workbook, the I/J fixture sets, …)

Usage
-----
    python scripts/verify_frozen.py            # verify; exit 1 on any mismatch
    python scripts/verify_frozen.py --list     # show what is covered
    python scripts/verify_frozen.py --adopt    # write current hashes into the
                                               # manifest for NEW artifacts only
                                               # (never overwrites a recorded one)
    python scripts/verify_frozen.py --self-test  # exercise the integrity rule

Checkout invariance
-------------------
A frozen hash is a claim about an artifact, not about the machine holding it.
Text can be checked out as LF or CRLF; that representation must not change the
verdict, and `renderings()` is where that is decided. Binary artifacts keep
exact-byte semantics -- they are never EOL-folded.

`.gitattributes` pins the checkout to LF so that the byte-exact guards inside
frozen experiment harnesses (which cannot be edited) also see what was
committed. The two mechanisms answer different halves: the attributes file
fixes what lands on disk, `renderings()` forgives hashes that were recorded
from a CRLF checkout before that file existed. Neither edits a recorded hash.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
MANIFEST = LAB / "frozen_manifest.json"

PATH_KEYS = ("fixture", "workbook", "path", "file", "source", "input")
_HEX = set("0123456789abcdef")


CRLF = bytes([13, 10])
LF = bytes([10])


def sha256(path: Path) -> str:
    """The artifact's exact bytes -- what a hash was, and still is, recorded from."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_binary(data: bytes) -> bool:
    """A NUL byte means the artifact is not text and must never be EOL-folded.

    Every binary artifact in the frozen estate is an xlsx (a zip), and all 38 of
    them carry NULs. The heuristic is deliberately conservative: anything that
    might be text is treated as text, and text is the only thing whose
    line-ending representation is forgiven.
    """
    return bytes([0]) in data


def renderings(data: bytes) -> set:
    """Every hash this artifact could legitimately have been recorded under.

    Binary: exactly one -- its bytes. Exact-byte integrity is unchanged.

    Text: the same content in either line-ending representation. A checkout is
    free to store text as LF or CRLF; that is a property of the machine, not of
    the artifact, and a corruption verifier must test the artifact. Any change
    to the content itself alters every rendering, so mutation detection is not
    weakened -- only the representation is forgiven.

    The raw bytes are included too, so a file with mixed endings that matches
    its record exactly still passes.
    """
    if is_binary(data):
        return {hashlib.sha256(data).hexdigest()}
    lf = data.replace(CRLF, LF)
    crlf = lf.replace(LF, CRLF)
    return {hashlib.sha256(b).hexdigest() for b in (data, lf, crlf)}


def integrity(path: Path, expected: str) -> tuple:
    """(matches, only_via_other_eol) for one artifact against its frozen hash.

    `only_via_other_eol` is true when the artifact is intact but this checkout
    stores it in the other line-ending representation from the one the hash was
    recorded under. Worth reporting; not a failure.
    """
    data = path.read_bytes()
    exact = hashlib.sha256(data).hexdigest() == expected
    matches = expected in renderings(data)
    return matches, (matches and not exact)


def _looks_like_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= _HEX


def _resolve(rel: str, base: Path) -> Path:
    """Paths in an expected.json are relative to the experiment dir OR to the
    lab root -- both conventions are in use. Try the experiment first."""
    candidate = (base / rel).resolve()
    if candidate.exists():
        return candidate
    alternative = (LAB / rel).resolve()
    return alternative if alternative.exists() else candidate


def _collect_from_obj(obj: object, base: Path, out: list[tuple[str, Path, str]],
                      origin: str) -> None:
    """Walk a JSON tree pulling out (path, hash) pairs in either layout."""
    if isinstance(obj, dict):
        # sibling layout: a path-ish key alongside "sha256"
        if _looks_like_hash(obj.get("sha256")):
            for key in PATH_KEYS:
                value = obj.get(key)
                if isinstance(value, str) and value:
                    out.append((origin, _resolve(value, base), obj["sha256"]))
                    break
        # prefixed layout: "<name>" and "<name>_sha256"
        for key, value in obj.items():
            if key.endswith("_sha256") and _looks_like_hash(value):
                target = obj.get(key[: -len("_sha256")])
                if isinstance(target, str) and target and "/" in target.replace("\\", "/"):
                    out.append((origin, _resolve(target, base), value))
        for value in obj.values():
            _collect_from_obj(value, base, out, origin)
    elif isinstance(obj, list):
        for value in obj:
            _collect_from_obj(value, base, out, origin)


def collect() -> list[tuple[str, Path, str]]:
    """Every (origin, path, expected_hash) the lab has frozen."""
    out: list[tuple[str, Path, str]] = []

    for spec in sorted(LAB.glob("experiment*/expected*.json")):
        try:
            data = json.loads(spec.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - corrupt freeze
            out.append((str(spec.relative_to(LAB)), spec, f"UNREADABLE: {exc}"))
            continue
        _collect_from_obj(data, spec.parent, out, str(spec.relative_to(LAB)))

    if MANIFEST.exists():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in data.get("artifacts", []):
            out.append(("frozen_manifest.json", (LAB / entry["path"]).resolve(),
                        entry["sha256"]))

    # De-duplicate: the same artifact is legitimately frozen by several
    # experiments (K's C1 is referenced by both K and the C3-fix replay).
    seen: dict[tuple[Path, str], str] = {}
    unique: list[tuple[str, Path, str]] = []
    for origin, path, digest in out:
        key = (path, digest)
        if key in seen:
            continue
        seen[key] = origin
        unique.append((origin, path, digest))
    return unique


def verify() -> tuple:
    problems: list[str] = []
    missing: list[str] = []
    eol_folded: list[str] = []
    checked = 0
    conflicts: dict[Path, set[str]] = {}

    for origin, path, expected in collect():
        rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
        if not path.exists():
            missing.append(f"{rel}  (frozen by {origin}) -- FILE MISSING")
            continue
        matches, via_other_eol = integrity(path, expected)
        actual = sha256(path)
        checked += 1
        conflicts.setdefault(path, set()).add(expected)
        if via_other_eol:
            eol_folded.append(f"{rel}  (frozen by {origin})")
        if not matches:
            problems.append(f"{rel}\n      frozen by {origin}\n"
                            f"      expected {expected}\n      actual   {actual}")

    # Two experiments freezing the SAME file at DIFFERENT hashes means one of
    # them is already broken, even if the file matches one of them.
    for path, digests in conflicts.items():
        if len(digests) > 1:
            rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
            problems.append(f"{rel}\n      CONFLICT: frozen at {len(digests)} "
                            f"different hashes by different experiments")
    return problems, missing, checked, eol_folded


def adopt() -> int:
    """Record hashes for artifacts not yet covered. Never overwrites."""
    covered = {p for _, p, _ in collect()}
    data = (json.loads(MANIFEST.read_text(encoding="utf-8"))
            if MANIFEST.exists() else {"artifacts": []})
    known = {e["path"] for e in data["artifacts"]}

    candidates = sorted(
        p for pattern in ("definition_phase/fixtures/*.xlsx",
                          "definition_phase/recipes/*.json",
                          "definition_phase/recipes/broken/*.json",
                          "experimentH/reference/*.json",
                          "experimentI/fixtures/*.csv",
                          "experimentJ/fixtures/*.csv",
                          "experiment2b/fixtures/*.csv",
                          # Agent definitions are inputs to the 3A-3E runs in the
                          # same sense a fixture is: editing one moves the
                          # boundary two runs are compared across. See
                          # scripts/agent_binding.py.
                          ".claude/agents/*.md",
                          # The authority path, frozen 2026-08-15 as
                          # `authority-path-v1`. Pinned so it stays answerable
                          # LATER which guarantees existed WHEN -- the stated
                          # reason for freezing at this boundary. A change here
                          # is a re-freeze, not a hash edit. See
                          # definition_phase/design/authority_path_freeze_v1.md.
                          "definition_phase/design/authority_path_freeze_v1.md",
                          "definition_phase/design/observable_error_v1.md",
                          # The implementation, not only the prose. A freeze that
                          # pins what the guarantees SAY while the code providing
                          # them drifts silently is the staleness this repo keeps
                          # finding -- Experiment M's record drifted for several
                          # commits with nothing noticing.
                          "experimentL/harness/execute_recipe.py",
                          "definition_phase/harness/approval.py",
                          "scripts/check_surfaced.py",
                          # The task-model floor, pinned 2026-08-15 before
                          # Experiment R2 so that experiment's instrument is
                          # fixed. Malformed external proposals are refused by
                          # name here rather than crashing; R2 depends on that.
                          "taskmodel/task_model.py")
        for p in LAB.glob(pattern))

    # Stamped with the day the hash was actually taken. It was hardcoded, which
    # would have back-dated every later adoption to the day this script was
    # written -- a false provenance claim in the one file whose job is provenance.
    stamp = datetime.date.today().isoformat()

    added = 0
    for path in candidates:
        rel = str(path.relative_to(LAB)).replace("\\", "/")
        if path.resolve() in covered or rel in known:
            continue
        data["artifacts"].append({"path": rel, "sha256": sha256(path),
                                  "note": f"adopted {stamp}"})
        added += 1
    data["artifacts"].sort(key=lambda e: e["path"])
    data.setdefault("_note",
                    "Frozen artifacts NOT covered by any experiment's expected.json. "
                    "Per-experiment expected.json files remain authoritative for what "
                    "they cover; this file never duplicates them. Do not edit a hash "
                    "to make a check pass -- if an artifact legitimately changed, that "
                    "is a re-freeze and belongs in a commit that says so.")
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"adopted {added} new artifact(s); manifest now has {len(data['artifacts'])}")
    return 0


# ---------------------------------------------------------------------------
# self-test -- exercises the integrity rule against temporary fixtures.
# It never reads, mutates or restores a real frozen artifact.
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, why: str) -> None:
        if not cond:
            failures.append(why)

    text = "alpha" + LF.decode() + "beta" + LF.decode() + "gamma" + LF.decode()
    lf_bytes = text.encode("utf-8")
    crlf_bytes = lf_bytes.replace(LF, CRLF)
    lf_hash = hashlib.sha256(lf_bytes).hexdigest()
    crlf_hash = hashlib.sha256(crlf_bytes).hexdigest()
    check(lf_hash != crlf_hash,
          "the fixture must actually differ between renderings, or it proves nothing")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def write(name: str, data: bytes) -> Path:
            q = root / name
            q.write_bytes(data)
            return q

        # (1) unchanged text artifact, LF on disk, hash recorded from LF
        lf_file = write("a_lf.txt", lf_bytes)
        check(integrity(lf_file, lf_hash) == (True, False),
              "an LF artifact must match an LF-recorded hash exactly")

        # (2) the SAME artifact checked out as CRLF still matches
        crlf_file = write("a_crlf.txt", crlf_bytes)
        check(integrity(crlf_file, lf_hash)[0],
              "a CRLF checkout of an LF-recorded artifact must still verify")
        check(integrity(crlf_file, lf_hash)[1],
              "that match must be reported as reached via the other rendering")

        # and the mirror: a hash recorded from a CRLF checkout (11 of the real
        # manifest's hashes are like this) must verify on an LF checkout
        check(integrity(lf_file, crlf_hash)[0],
              "an LF checkout of a CRLF-recorded artifact must still verify")

        # (3) a non-EOL content mutation must still FAIL, in both renderings
        mutated = write("mutated.txt", lf_bytes.replace(b"beta", b"BETA"))
        check(integrity(mutated, lf_hash)[0] is False,
              "a real text mutation must fail")
        check(integrity(mutated, crlf_hash)[0] is False,
              "a real text mutation must fail against a CRLF-recorded hash too")
        # a mutation that only ADDS a line is still a mutation
        extra = write("extra.txt", lf_bytes + b"delta" + LF)
        check(integrity(extra, lf_hash)[0] is False,
              "appended content must fail")

        # (4) binary artifacts keep EXACT-byte semantics and are never folded.
        # This payload deliberately contains CRLF next to a NUL: if binaries were
        # EOL-folded, the LF form below would wrongly verify.
        blob = bytes([0]) + b"PK" + CRLF + b"payload" + CRLF + bytes([0, 255])
        bin_file = write("thing.xlsx", blob)
        blob_hash = hashlib.sha256(blob).hexdigest()
        check(is_binary(blob), "the binary fixture must be detected as binary")
        check(integrity(bin_file, blob_hash) == (True, False),
              "an unchanged binary must verify on its exact bytes")
        check(len(renderings(blob)) == 1,
              "a binary must have exactly one legitimate rendering")
        folded = write("folded.xlsx", blob.replace(CRLF, LF))
        check(integrity(folded, blob_hash)[0] is False,
              "CANARY: changing CRLF to LF inside a BINARY must fail -- binary "
              "integrity is exact-byte and must not inherit the text rule")
        one_byte = write("bitflip.xlsx", blob[:-1] + bytes([254]))
        check(integrity(one_byte, blob_hash)[0] is False,
              "a single changed byte in a binary must fail")

        # (5) the text rule must not quietly accept an empty or truncated file
        truncated = write("trunc.txt", lf_bytes[: len(lf_bytes) // 2])
        check(integrity(truncated, lf_hash)[0] is False,
              "a truncated text artifact must fail")

    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        return 1
    print("OK  self-test: 13 checks -- LF and CRLF renderings of intact text both "
          "verify; text mutation, appended text and truncation fail; binaries stay "
          "exact-byte and are NOT EOL-folded")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--self-test":
        return _self_test()
    if argv and argv[0] == "--adopt":
        return adopt()
    if argv and argv[0] == "--list":
        for origin, path, digest in collect():
            rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
            print(f"{digest[:12]}  {str(rel):58}  <- {origin}")
        return 0

    problems, missing, checked, eol_folded = verify()
    for line in missing:
        print(f"MISSING  {line}")
    if eol_folded:
        print(f"NOTE  {len(eol_folded)} textual artifact(s) match their frozen hash "
              f"under the other line-ending rendering. Intact -- this checkout "
              f"simply stores them the other way round. Not a mismatch.")
    if problems:
        print("\nFROZEN ARTIFACT MISMATCH:")
        for line in problems:
            print(f"  {line}")
        print(f"\n{len(problems)} mismatch(es) across {checked} checked artifacts.")
        print("An artifact was modified after being frozen. If a generator was "
              "re-run, restore from git (`git checkout -- <path>`) rather than "
              "editing the recorded hash.")
        return 1
    print(f"OK: {checked} frozen artifacts verified"
          + (f"; {len(missing)} missing" if missing else ""))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
