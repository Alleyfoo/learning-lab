#!/usr/bin/env python3
"""W1-L preparation verification — OBSERVATIONAL by construction.

Backlog B-1. Earlier packs' verifiers ran the pack's own reporters in place, so
on a completed pack the verification command rewrote the evidence it was
verifying (W1-B/W1-C, W1-F, W1-I twice). This one cannot:

```text
1  it REFUSES outright if any declared run already holds evidence
2  any check needing a reporter runs it against a temporary COPY
3  it fingerprints the pack before and after itself and FAILS if a single
   byte moved -- the verifier proves its own innocence
```

Backlog B-2. Nothing here is a cloned literal. Run set, fixtures, revisions,
markers and denominators all come from `manifest.json`, and the run set is
authoritative rather than globbed.

    python work_interface/w1l/verify_prep.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WI = _HERE.parent
sys.path.insert(0, str(_WI / "harness"))
sys.path.insert(0, str(_WI / "w1b" / "harness"))
sys.path.insert(0, str(_WI / "authority"))
sys.path.insert(0, str(_WI))
import pack_manifest as PM  # noqa: E402
import prep_guard as PG  # noqa: E402
import block_harness as B  # noqa: E402
import work_definition as wd  # noqa: E402

FAILS: list[str] = []
MANIFEST = PM.load(_HERE)


def _check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(label)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------

def check_0_observational() -> None:
    """The guard that would have prevented every prior occurrence."""
    print("\n[0] this verifier may not touch an executed pack")
    used = PG.executed_runs(_HERE, MANIFEST.runs)
    _check(not used,
           "no declared run holds evidence yet",
           f"executed: {used}" if used else "pack is unrun")
    if used:
        raise PG.PackAlreadyExecuted(
            f"{', '.join(used)} already hold evidence; refusing to verify a "
            f"completed pack. See BACKLOG.md B-1.")
    _check(callable(PG.refuse_if_executed) and callable(PG.observational_copy),
           "the observational guard is wired in")


def check_1_manifest() -> None:
    print("\n[1] the manifest declares this pack, and matches the bytes")
    problems = MANIFEST.verify()
    _check(not problems, "manifest verifies against the filesystem",
           str(problems[:2]) if problems else "no problems")
    _check(MANIFEST.pack == "w1l", f"pack is {MANIFEST.pack!r}")
    _check(MANIFEST.data.get("treatment") is None,
           "treatment is explicitly NONE -- this is a baseline")
    _check(len(MANIFEST.runs) == 12,
           f"{len(MANIFEST.runs)} runs declared", str(MANIFEST.runs[:3]) + "...")
    _check(MANIFEST.undeclared_run_dirs() == [],
           "no undeclared run directories",
           str(MANIFEST.undeclared_run_dirs()))


def check_2_runs() -> None:
    print("\n[2] every declared run holds exactly the frozen inputs")
    for run in MANIFEST.runs:
        d = MANIFEST.run_dir(run)
        entries = sorted(p.name for p in d.iterdir()) if d.is_dir() else []
        _check(entries == ["PROMPT.md", "SKILL.md"],
               f"{run}: {entries}")


def check_3_skill() -> None:
    print("\n[3] every SKILL.md is the declared revision (r2), byte-identical")
    seen = set()
    for run in MANIFEST.runs:
        got = _sha(MANIFEST.run_dir(run) / "SKILL.md")
        seen.add(got)
        _check(got == MANIFEST.skill_sha256(run),
               f"{run}: {MANIFEST.skill_revision(run)} {got[:16]}")
    _check(len(seen) == 1, "all runs share ONE revision -- no arms here",
           f"{len(seen)} distinct")
    _check(next(iter(seen)) == _sha(_WI / "skill" / "r2" / "skill.md"),
           "and it is the frozen r2 on disk")


def check_4_no_treatment() -> None:
    """The defining property: nothing from any later line is present."""
    print("\n[4] NO treatment: no r2c, r3, Surface C, or reordering")
    body = (MANIFEST.run_dir(MANIFEST.runs[0]) / "SKILL.md").read_text(
        encoding="utf-8")
    _check("separator syntax" not in body.lower(),
           "the skill carries no r3 tokenization amendment")
    # r2 has a TOP-LEVEL "provenance" block (producer/skill/produced_at);
    # only output.provenance is the r2c surface. Test the output block itself.
    out_block = body.split('"output": {', 1)[-1].split("},", 1)[0]
    _check('"provenance"' not in out_block,
           "the skill's output block carries no provenance surface")
    _check("reports_fields" in out_block and "context_fields" in out_block,
           "and it is the plain v0 output block")
    _check(tuple(MANIFEST.block_order) == tuple(B.MANDATED_ROWS),
           f"delivery order is canonical {list(MANIFEST.block_order)}")
    _check(MANIFEST.data["validator"]["name"] == "v0",
           "the validator is plain v0, not v0+C")
    src = (_HERE / "harness" / "run_batch.py").read_text(encoding="utf-8")
    for banned in ("r2c", "work_definition_c", "DELIVERY_ORDER = tuple(reversed"):
        _check(banned not in src, f"the runner does not reference {banned!r}")


def check_5_prompts() -> None:
    print("\n[5] prompts are per-run and leak nothing about the design")
    targets = set()
    for run in MANIFEST.runs:
        text = (MANIFEST.run_dir(run) / "PROMPT.md").read_text(encoding="utf-8")
        want = f"w1l\\runs\\{run}"
        _check(want in text, f"{run}: names its own run directory")
        others = [o for o in MANIFEST.runs
                  if o != run and f"w1l\\runs\\{o}\\work" in text]
        _check(not others, f"{run}: no other run's artifact path leaks",
               str(others[:2]))
        targets.add(f"w1l\\runs\\{run}\\{MANIFEST.artifact}")
        for banned in ("baseline", "repeatability", "variability", "twelve",
                       "provenance", "read_authorized_resource",
                       "write_work_definition", "resource_id", "mcp"):
            _check(banned not in text.lower(),
                   f"{run}: does not mention {banned!r}")
    _check(len(targets) == len(MANIFEST.runs),
           "every run has a distinct artifact target")


def check_6_inputs() -> None:
    print("\n[6] fixtures, answers and block are the declared frozen inputs")
    for role in MANIFEST.fixture_roles:
        p = MANIFEST.fixture_path(role)
        _check(p.is_file(), f"fixture {role}: {p.name}")
    _check(_sha(MANIFEST.answers_path) == MANIFEST.answers_sha256,
           "answer table matches its declared sha256")
    sys.path.insert(0, str(_HERE / "harness"))
    import run_batch as RB
    block = RB.canonical_block()
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    _check(digest == MANIFEST.block_sha256,
           f"canonical block {len(block)} bytes {digest[:16]}")
    _check(digest == "46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330",
           "and it is the same block W1-H/W1-K delivered")
    rows = B.load_table_rows(MANIFEST.answers_path)
    parts = block.split("\n\n")
    expected = [rows[i][0] + "\n" + rows[i][1] for i in MANIFEST.block_order]
    _check(parts == expected, "every delivered part is the right row, in order")


def check_7_derived_constants() -> None:
    """Backlog B-2: no reporter may carry a cloned literal."""
    print("\n[7] reporter constants are DERIVED, and denominators are too")
    markers = MANIFEST.consumption_markers()
    for role in MANIFEST.fixture_roles:
        body = MANIFEST.fixture_path(role).read_text(encoding="utf-8")
        _check(markers[role] in body,
               f"the {role} marker occurs in its own fixture",
               repr(markers[role])[:46])
    D = MANIFEST.denominators()
    _check(D["runs"] == len(MANIFEST.runs) == 12, f"runs denominator {D['runs']}")
    _check(D["rows"] == 6, f"rows denominator {D['rows']}")
    rsrc = (_HERE / "baseline_report.py").read_text(encoding="utf-8")
    _check("MANIFEST.runs" in rsrc,
           "the reporter takes its run set from the manifest")
    for bad in ("/3", "/6 runs", "glob("):
        _check(bad not in rsrc.replace("x{c}", ""),
               f"the reporter hard-codes no {bad!r}")
    _check("rglob" not in rsrc and "iterdir" not in rsrc,
           "and never enumerates runs/ directly")


def check_8_measures() -> None:
    print("\n[8] both primary fingerprints, and they classify correctly")
    sys.path.insert(0, str(_HERE))
    import baseline_report as R
    canon = ["Date", "Supplier Name", "InvoiceNumber", "Amount", "Currency",
             "Status"]
    cases = {
        "EXACT": canon,
        "SINGLE_FIELD_PAD": ["Date", " Supplier Name", "InvoiceNumber",
                             "Amount", "Currency", "Status"],
        "SYSTEMATIC_PAD": ["Date", " Supplier Name", " InvoiceNumber",
                           " Amount", " Currency", " Status"],
        "UNSPLIT_HEADER": ["Date, Supplier Name, InvoiceNumber, Amount, "
                           "Currency, Status"],
        "COLLAPSED": ["Date", "SupplierName", "InvoiceNumber", "Amount",
                      "Currency", "Status"],
        "OTHER": ["Date", "Bogus", "InvoiceNumber", "Amount", "Currency",
                  "Status"],
    }
    for want, declared in cases.items():
        got = R.classify_source(declared, canon)
        _check(got["class"] == want, f"classifies {want}", got["class"])
        if want != "EXACT":
            _check(bool(got["offenders"]),
                   f"{want} preserves the offending token(s)",
                   repr(got["offenders"][0]["declared"])[:40])

    # the fingerprints reproduce known historical results
    tbl = B.load_table_rows(MANIFEST.answers_path)
    cmap = {i: tbl[i][1] for i in MANIFEST.block_order}
    known = {("w1h", "P1"): ("EEEEEE", "EXACT"),
             ("w1h", "P2"): ("EE----", "EXACT"),
             ("w1k", "A1"): ("E-----", "UNSPLIT_HEADER")}
    for (pack, run), (fp, tok) in known.items():
        p = _WI / pack / "runs" / run / MANIFEST.artifact
        if not p.is_file():
            continue
        art = json.loads(p.read_text(encoding="utf-8"))
        _check(R.preservation(art, cmap)["fingerprint"] == fp,
               f"{pack}/{run} preservation reproduces {fp}")
        _check(R.tokenization(art)["class"] == tok,
               f"{pack}/{run} tokenization reproduces {tok}")


def check_9_reporters_observational() -> None:
    """Reporter behaviour is exercised in a COPY, never in the pack."""
    print("\n[9] reporters run against a temp COPY, not the pack")
    before = PG.fingerprint(_HERE)
    with PG.observational_copy(_HERE) as copy:
        # The copy lives outside work_interface, so the reporter's relative
        # sibling imports cannot resolve. Point PYTHONPATH at the real
        # instruments; pack_manifest resolves fixtures from its own location,
        # so the copy still reads the pack's OWN manifest.
        import os as _os
        env = dict(_os.environ)
        env["PYTHONPATH"] = _os.pathsep.join(
            str(x) for x in (_WI / "harness", _WI / "fidelity",
                             _WI / "w1b" / "harness", _WI / "authority", _WI))
        r = subprocess.run([sys.executable, str(copy / "baseline_report.py")],
                           capture_output=True, text=True, timeout=300,
                           env=env)
        _check(r.returncode == 0, f"baseline_report runs (exit {r.returncode})",
               (r.stderr or "").strip().splitlines()[-1][:70] if r.stderr else "")
        _check((copy / "BASELINE.md").is_file(),
               "and writes its report INTO THE COPY")
        body = (copy / "BASELINE.md").read_text(encoding="utf-8")
        _check("artifacts graded  0/12" in body,
               "reports 0/12 graded on an unrun pack -- denominator derived")
    after = PG.fingerprint(_HERE)
    muts = PG.assert_unchanged(before, after)
    _check(not muts, "the PACK itself is byte-unchanged by this check",
           str(muts[:2]) if muts else "no mutations")
    _check(not (_HERE / "BASELINE.md").exists(),
           "no reporter output leaked into the pack")


def check_10_validator_and_infra() -> None:
    print("\n[10] frozen instruments intact; infra regressions pass")
    r = subprocess.run([sys.executable, "work_definition.py", "--self-test"],
                       cwd=str(_WI), capture_output=True, text=True)
    _check(r.returncode == 0, f"v0 self-test exit={r.returncode}")
    r2 = subprocess.run([sys.executable,
                         str(_WI / "harness" / "selftest_pack_infra.py")],
                        capture_output=True, text=True)
    _check(r2.returncode == 0,
           f"B-1/B-2 pack-infra regressions exit={r2.returncode}")
    fid = _WI / "fidelity" / "fidelity_check.py"
    _check(_sha(fid) ==
           "11984c096b8fd74f40549d17f9300dc732f3dbe1d4e1112f3dc0f412036b41d4",
           "frozen fidelity checker is pinned and intact")
    caps = (_WI / "authority" / "authorized_capabilities.py").read_text(
        encoding="utf-8")
    _check("sys.stdin.reconfigure" in caps and 'encoding="utf-8"' in caps,
           "the corrected UTF-8 capability server is in place")


def main() -> int:
    print("=" * 70)
    print("W1-L preparation verification (observational)")
    print("=" * 70)
    self_before = PG.fingerprint(_HERE)

    check_0_observational()
    check_1_manifest()
    check_2_runs()
    check_3_skill()
    check_4_no_treatment()
    check_5_prompts()
    check_6_inputs()
    check_7_derived_constants()
    check_8_measures()
    check_9_reporters_observational()
    check_10_validator_and_infra()

    # the verifier proves its own innocence
    print("\n[11] the verifier mutated nothing")
    muts = PG.assert_unchanged(self_before, PG.fingerprint(_HERE))
    _check(not muts, "the pack is byte-identical to before this run",
           str(muts[:3]) if muts else "no mutations")

    print("\n" + "=" * 70)
    if FAILS:
        print(f"PREP VERIFICATION FAILED: {len(FAILS)} check(s) failed")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("PREP VERIFICATION PASSED (all 12 checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
