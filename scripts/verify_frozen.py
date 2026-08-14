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
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
MANIFEST = LAB / "frozen_manifest.json"

PATH_KEYS = ("fixture", "workbook", "path", "file", "source", "input")
_HEX = set("0123456789abcdef")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def verify() -> tuple[list[str], list[str], int]:
    problems: list[str] = []
    missing: list[str] = []
    checked = 0
    conflicts: dict[Path, set[str]] = {}

    for origin, path, expected in collect():
        rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
        if not path.exists():
            missing.append(f"{rel}  (frozen by {origin}) -- FILE MISSING")
            continue
        actual = sha256(path)
        checked += 1
        conflicts.setdefault(path, set()).add(expected)
        if actual != expected:
            problems.append(f"{rel}\n      frozen by {origin}\n"
                            f"      expected {expected}\n      actual   {actual}")

    # Two experiments freezing the SAME file at DIFFERENT hashes means one of
    # them is already broken, even if the file matches one of them.
    for path, digests in conflicts.items():
        if len(digests) > 1:
            rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
            problems.append(f"{rel}\n      CONFLICT: frozen at {len(digests)} "
                            f"different hashes by different experiments")
    return problems, missing, checked


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
                          "experiment2b/fixtures/*.csv")
        for p in LAB.glob(pattern))

    added = 0
    for path in candidates:
        rel = str(path.relative_to(LAB)).replace("\\", "/")
        if path.resolve() in covered or rel in known:
            continue
        data["artifacts"].append({"path": rel, "sha256": sha256(path),
                                  "note": "adopted 2026-08-14"})
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


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--adopt":
        return adopt()
    if argv and argv[0] == "--list":
        for origin, path, digest in collect():
            rel = path.relative_to(LAB) if path.is_relative_to(LAB) else path
            print(f"{digest[:12]}  {str(rel):58}  <- {origin}")
        return 0

    problems, missing, checked = verify()
    for line in missing:
        print(f"MISSING  {line}")
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
