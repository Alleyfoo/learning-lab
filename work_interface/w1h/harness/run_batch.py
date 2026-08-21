#!/usr/bin/env python3
"""W1-H batch runner — the two-verb capability box.

Drives P1/P2/P3 through harness revision r2
(`work_interface/harness/single_block_harness.py`).

**The only intentional change relative to W1-F is one added MCP capability.**

W1-F proved the purpose-built reader is discovered unprompted (3/3) but produced
no artifact, because attaching an MCP server REPLACES Goose's builtin tool
surface rather than extending it — confirmed from provider traffic in
calibration `d511894`. W1-H stops fighting that and uses it: the worker is not
given a general-purpose computer with a policy bolted on, it is given exactly
the verbs its role needs.

```text
READ AUTHORITY   read_authorized_resource(skill|supplier_statement|ledger_book)
WRITE AUTHORITY  write_work_definition(content)
everything else  DENY
```

No shell, no generic filesystem, no path-bearing write, no directory listing.

The permission layer stays **fail-closed regardless**. It does not depend on
Goose continuing to suppress the builtins: if a future build offers `shell`
again, the policy still denies it.

A4 runs in SHADOW mode (`fs_enforcing=False`): the pre-run filesystem snapshot is
recorded as data, no verdict is computed in-run, and the filesystem state cannot
terminate, alter, rescue or otherwise influence a run.

    python work_interface/w1h/harness/run_batch.py --run all
    python work_interface/w1h/harness/run_batch.py --run all --dry-run
    python work_interface/w1h/harness/run_batch.py --show-block
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W1H = HERE.parent
WI = W1H.parent
sys.path.insert(0, str(WI / "harness"))
sys.path.insert(0, str(WI / "w1b" / "harness"))      # frozen canonical-block reader
import single_block_harness as L                      # noqa: E402
from permission_session import PermissionSession, GOOSE_EXE  # noqa: E402
sys.path.insert(0, str(WI / "authority"))
from permission_policy import PermissionPolicy        # noqa: E402
import authorized_capabilities as CAPS                 # noqa: E402
import block_harness as BLOCKSRC                      # noqa: E402

RUNS_DIR = W1H / "runs"
ALL_RUNS = ["P1", "P2", "P3"]
ARTIFACT = "work_definition.json"

FROZEN_SKILL_SHA256 = (
    "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a")   # r2
CANONICAL_BLOCK_SHA256 = (
    "46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330")
W1A = WI / "w1a"
HUMAN_ANSWERS = W1A / "human_answers.md"
HUMAN_ANSWERS_SHA256 = (
    "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd")

# PATH-SHAPED protected resources, anchored to real files and directories.
#
# NEVER bare words. W1-D was voided because this list held lexical markers such
# as "authority", and the detector scanned serialized payloads including file
# CONTENT -- so a worker reading its own authorized SKILL.md, which uses the word
# "authority" eleven times, tripped the boundary on turn 1
# (`work_interface/w1d/CLOSURE.md`). Detection is now structured path extraction
# (`work_interface/harness/path_guard.py`).
FORBIDDEN_EXTRA = [
    W1A / "human_answers.md",
    WI / "work_definition.py",
    WI / "cases",
    WI / "census",
    WI / "fidelity",
    WI / "authority",
    WI / "w1a" / "runs",
    WI / "w1a2" / "runs",
    WI / "w1a3" / "runs",
    WI / "w1a4" / "runs",
    WI / "w1a5" / "runs",
    WI / "w1b" / "runs",
    WI / "w1c" / "runs",
    WI / "w1d" / "runs",
    WI / "w1d2" / "runs",
    WI / "w1e" / "runs",
    WI / "w1f" / "runs",
    WI / "w1g" / "runs",
]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def controlled(run_dir: Path) -> dict[str, Path]:
    return {"PROMPT.md": run_dir / "PROMPT.md",
            "SKILL.md": run_dir / "SKILL.md",
            "supplier-statement.txt": W1A / "fixtures" / "supplier-statement.txt",
            "ledger-book.txt": W1A / "fixtures" / "ledger-book.txt",
            "human_answers.md": HUMAN_ANSWERS}


def canonical_block() -> str:
    """The 693-byte W1-B/W1-C block, rebuilt from the same frozen table."""
    return BLOCKSRC.build_block()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W1-H batch (capability box)")
    ap.add_argument("--run", choices=ALL_RUNS + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-block", action="store_true")
    args = ap.parse_args(argv)

    block = canonical_block()
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    if args.show_block:
        print(block)
        return 0
    if digest != CANONICAL_BLOCK_SHA256:
        print(f"HARNESS ERROR: canonical block drifted\n  expected "
              f"{CANONICAL_BLOCK_SHA256}\n  got      {digest}", file=sys.stderr)
        return 1
    print(f"canonical block: {len(block)} bytes, sha256 {digest[:16]} "
          f"(pinned, identical to W1-B/W1-C)")
    print(f"answer source  : {HUMAN_ANSWERS.name} {sha256_file(HUMAN_ANSWERS)[:12]}")
    print("lifecycle      : r2 single-block")
    print("authority      : ENFORCED -- approve mode, fail-closed policy;"
          " A4 independent post-turn watch")
    print("capability box : " + ", ".join(t["name"] for t in CAPS.TOOLS))
    print("  read         : " + str(list(CAPS.RESOURCE_IDS)))
    print("  write        : single-shot, destination fixed, no path argument")

    if not GOOSE_EXE.is_file():
        print(f"HARNESS ERROR: Goose CLI not found: {GOOSE_EXE}", file=sys.stderr)
        return 1

    runs = ALL_RUNS if (args.run == "all" or not args.run) else [args.run]
    if args.dry_run:
        for r in runs:
            d = RUNS_DIR / r
            print(f"{r}: prompt={(d / 'PROMPT.md').is_file()} "
                  f"skill_r2={sha256_file(d / 'SKILL.md') == FROZEN_SKILL_SHA256} "
                  f"artifact_absent={not (d / ARTIFACT).exists()}")
        return 0

    infra = False
    for run in runs:
        d = (RUNS_DIR / run).resolve()
        print(f"\n=== {run} ===")
        if sha256_file(d / "SKILL.md") != FROZEN_SKILL_SHA256:
            print("  CONTESTED: SKILL.md does not match frozen r2")
            continue
        if sha256_file(HUMAN_ANSWERS) != HUMAN_ANSWERS_SHA256:
            print("  CONTESTED: human_answers.md does not match its frozen hash")
            continue
        transcript = d / "acp_transcript.jsonl"
        policy = PermissionPolicy(
            d,
            readable=[d / "SKILL.md",
                      W1A / "fixtures" / "supplier-statement.txt",
                      W1A / "fixtures" / "ledger-book.txt"],
            writable=[d / ARTIFACT],
            resource_ids=CAPS.RESOURCE_IDS,
            writer_capability=True)
        session = PermissionSession(d, transcript, policy)
        mcp = [{"name": "authorized-capabilities",
                "command": sys.executable,
                "args": [str(WI / "authority" / "authorized_capabilities.py"),
                         str(d)],
                "env": []}]
        res = L.run_one(run, d, block,
                        lambda: session,
                        artifact_name=ARTIFACT,
                        controlled=controlled(d),
                        all_runs=ALL_RUNS,
                        forbidden_extra=FORBIDDEN_EXTRA,
                        fs_enforcing=False,   # AUTHORITY is its own layer
                        session_mode="approve",
                        fs_watch=True,
                        mcp_servers=mcp)
        print(f"  outcome            : {res.outcome}")
        print(f"  reason             : {res.reason[:400]}")
        print(f"  turns              : {res.turns}")
        print(f"  blocks delivered   : {res.blocks_delivered}")
        print(f"  continuations sent : {res.continuations_sent}")
        print(f"  silent turns       : {res.silent_turns}")
        print(f"  artifact           : {res.artifact}")
        allow = sum(1 for e in session.permission_log if e["verdict"] == "ALLOW")
        deny = sum(1 for e in session.permission_log if e["verdict"] == "DENY")
        print(f"  permission requests: {len(session.permission_log)} "
              f"(ALLOW {allow} / DENY {deny})")
        print(f"  shell attempts     : {session.shell_attempts}")
        (d / "harness_result.json").write_text(
            json.dumps({"run": res.run, "outcome": res.outcome,
                        "reason": res.reason, "turns": res.turns,
                        "artifact": res.artifact,
                        "blocks_delivered": res.blocks_delivered,
                        "continuations_sent": res.continuations_sent,
                        "silent_turns": res.silent_turns,
                        "block_sha256": digest,
                        "lifecycle_revision": "r2_single_block",
                        "fs_authority_mode": "WATCH_INDEPENDENT",
                        "session_mode": "approve",
                        "permission_log": session.permission_log,
                        "shell_attempts": session.shell_attempts,
                        "authorized_reader_ids": list(CAPS.RESOURCE_IDS),
                        "capability_box": [x["name"] for x in CAPS.TOOLS],
                        "fs_snapshot_before": res.fs_snapshot_before,
                        "turn_log": res.turn_log,
                        "hashes_before": res.hashes_before,
                        "hashes_after": res.hashes_after},
                       indent=2, ensure_ascii=False),
            encoding="utf-8")
        if res.outcome == L.HARNESS_ERROR:
            infra = True
    return 1 if infra else 0


if __name__ == "__main__":
    raise SystemExit(main())
