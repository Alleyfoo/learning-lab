#!/usr/bin/env python3
"""Regressions for backlog B-1 and B-2. Offline; no model, no network.

Each check reproduces a defect this lab actually shipped, then proves the new
infrastructure catches it.

```text
B-1  a prep verifier regenerated reporter outputs over frozen evidence
     (W1-B/W1-C, W1-F, W1-I twice)
B-2  a reporter constant naming an input was cloned instead of derived
     (W1-F worker_verdict, W1-I markers, W1-I + W1-K skill_match pins)
     and a run set taken from a directory glob can change denominators
```
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pack_manifest as PM  # noqa: E402
import prep_guard as PG  # noqa: E402

WI = HERE.parent
FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}"
          + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def make_pack(tmp: Path, runs, executed=()) -> Path:
    """A minimal pack with a manifest, optionally holding evidence."""
    pack = tmp / "w1x"
    (pack / "runs").mkdir(parents=True)
    skill = (WI / "skill" / "r2" / "skill.md").read_bytes()
    import hashlib
    sha = hashlib.sha256(skill).hexdigest()
    for r in runs:
        d = pack / "runs" / r
        d.mkdir()
        (d / "SKILL.md").write_bytes(skill)
        (d / "PROMPT.md").write_text("task", encoding="utf-8")
        if r in executed:
            (d / "work_definition.json").write_text("{}", encoding="utf-8")
            (d / "harness_result.json").write_text("{}", encoding="utf-8")
    manifest = {
        "pack": "w1x",
        "runs": list(runs),
        "arms": {"baseline": list(runs)},
        "skills": {"baseline": {"revision": "r2", "sha256": sha}},
        "validator": {"name": "v0", "module": "work_definition"},
        "fixtures": {"dir": "w1a/fixtures",
                     "roles": {"supplier_statement": "supplier-statement.txt",
                               "ledger_book": "ledger-book.txt"}},
        "answers": {"path": "w1a/human_answers.md",
                    "sha256": hashlib.sha256(
                        (WI / "w1a" / "human_answers.md").read_bytes()
                    ).hexdigest()},
        "block": {"order": [0, 1, 2, 3, 4, 5], "sha256": "0" * 64},
        "artifact": "work_definition.json",
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                        encoding="utf-8")
    return pack


def main() -> int:
    print("[1] B-1: a verifier REFUSES a pack that already holds evidence")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b1_"))
    try:
        pack = make_pack(tmp, ["R01", "R02"], executed=["R01"])
        m = PM.load(pack)
        try:
            PG.refuse_if_executed(pack, m.runs)
            check(False, "must refuse an executed pack")
        except PG.PackAlreadyExecuted as e:
            check("already been executed" in str(e),
                  "refuses, and says which runs hold evidence", str(e)[:60])
        check(PG.executed_runs(pack, m.runs) == ["R01"],
              "and identifies exactly the executed run")

        pack2 = make_pack(tmp / "clean", ["R01", "R02"])
        m2 = PM.load(pack2)
        PG.refuse_if_executed(pack2, m2.runs)
        check(True, "an unexecuted pack passes the guard")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[2] B-1: reporter work runs in a COPY; the pack is untouched")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b1b_"))
    try:
        pack = make_pack(tmp, ["R01"])
        before = PG.fingerprint(pack)
        with PG.observational_copy(pack) as copy:
            # simulate exactly what a reporter does: write outputs
            (copy / "RESULTS.md").write_text("regenerated", encoding="utf-8")
            (copy / "runs" / "R01" / "work_definition.json").write_text(
                "{}", encoding="utf-8")
            check((copy / "RESULTS.md").is_file(),
                  "the copy is writable, so checks still work")
        after = PG.fingerprint(pack)
        muts = PG.assert_unchanged(before, after)
        check(not muts, "the ORIGINAL pack is byte-unchanged",
              str(muts[:2]) if muts else "no mutations")
        check(not (pack / "RESULTS.md").exists(),
              "and the reporter output never reached it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[3] B-1: the mutation detector actually detects mutation")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b1c_"))
    try:
        pack = make_pack(tmp, ["R01"])
        before = PG.fingerprint(pack)
        (pack / "RESULTS.md").write_text("oops", encoding="utf-8")
        muts = PG.assert_unchanged(before, PG.fingerprint(pack))
        check(any(x.startswith("CREATED RESULTS.md") for x in muts),
              "a written reporter output is reported as CREATED", str(muts))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[4] B-2: consumption markers are DERIVED, not cloned")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b2_"))
    try:
        pack = make_pack(tmp, ["R01"])
        m = PM.load(pack)
        markers = m.consumption_markers()
        for role in m.fixture_roles:
            body = m.fixture_path(role).read_text(encoding="utf-8")
            check(markers[role] in body,
                  f"the {role} marker occurs in its own fixture",
                  repr(markers[role])[:52])
        # the W1-I defect: a marker from a DIFFERENT pack's fixtures
        stale = "Supplier Statement File"
        alt = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        alt["fixtures"] = {"dir": "w1i/fixtures",
                           "roles": {"supplier_statement":
                                     "vendor-charge-summary.txt",
                                     "ledger_book":
                                     "internal-charge-ledger.txt"}}
        (pack / "manifest.json").write_text(json.dumps(alt), encoding="utf-8")
        m3 = PM.load(pack)
        markers3 = m3.consumption_markers()
        check(stale not in markers3.values(),
              "switching fixtures switches the markers -- the W1-I defect "
              "cannot recur")
        check(all(markers3[r] in m3.fixture_path(r).read_text(encoding="utf-8")
                  for r in m3.fixture_roles),
              "and the new markers occur in the NEW fixtures")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[5] B-2: every declared revision is accepted (the skill_match pin)")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b2b_"))
    try:
        import hashlib
        pack = make_pack(tmp, ["A1", "B1"])
        r2c = WI / "skill" / "r2c" / "skill.md"
        data = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        data["arms"] = {"control": ["A1"], "treatment": ["B1"]}
        data["skills"] = {
            "control": data["skills"]["baseline"],
            "treatment": {"revision": "r2c",
                          "sha256": hashlib.sha256(
                              r2c.read_bytes()).hexdigest()}}
        (pack / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        (pack / "runs" / "B1" / "SKILL.md").write_bytes(r2c.read_bytes())
        m = PM.load(pack)
        check(m.skill_revision("A1") == "r2" and m.skill_revision("B1") == "r2c",
              "each run resolves to ITS arm's revision")
        check(not m.verify(),
              "a correctly declared two-arm pack verifies clean",
              str(m.verify()[:1]))
        check(len(m.declared_revisions()) == 2,
              "both revisions are declared, so no arm is a false mismatch")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[6] B-2: the run set is AUTHORITATIVE, not a directory glob")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b2c_"))
    try:
        pack = make_pack(tmp, ["R01", "R02"])
        # a stray debug directory appears, exactly the silent-denominator risk
        stray = pack / "runs" / "R99_debug"
        stray.mkdir()
        (stray / "SKILL.md").write_text("scratch", encoding="utf-8")
        m = PM.load(pack)
        check(m.runs == ["R01", "R02"],
              "the manifest run set ignores the stray directory", str(m.runs))
        check(m.denominators()["runs"] == 2,
              "so the denominator is unchanged at 2")
        check(m.undeclared_run_dirs() == ["R99_debug"],
              "but the stray directory is REPORTED, never silently ignored")
        problems = m.verify()
        check(any("undeclared" in p for p in problems),
              "and verification names it as a problem", str(problems[:1]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[7] B-2: a mis-declared skill hash is caught")
    tmp = Path(tempfile.mkdtemp(prefix="infra_b2d_"))
    try:
        pack = make_pack(tmp, ["R01"])
        data = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        data["skills"]["baseline"]["sha256"] = "f" * 64
        (pack / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        problems = PM.load(pack).verify()
        check(any("!= declared" in p for p in problems),
              "declaration and bytes disagreeing is a named problem",
              str(problems[:1]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    if FAILS:
        print(f"PACK INFRA REGRESSIONS FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("PACK INFRA REGRESSIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
