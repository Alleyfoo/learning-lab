#!/usr/bin/env python3
"""W1-D batch runner — Surface B lifecycle ONLY.

Drives K1/K2/K3 through harness revision r2
(`work_interface/harness/single_block_harness.py`).

**Worker capability environment is identical to W1-C**, deliberately: same
`goose acp`, same shared Goose/Ollama config, `qwen3.5:9b`, session mode `auto`,
no client filesystem capability so the `developer` extension does all file I/O,
and NO fail-closed permission policy. Surface A is not adopted here; it becomes
W1-E only after W1-D is closed.

**Lifecycle is the only intentional stimulus change relative to W1-C.**

A4 runs in SHADOW mode (`fs_enforcing=False`): the pre-run filesystem snapshot is
recorded as data, no verdict is computed in-run, and the filesystem state cannot
terminate, alter, rescue or otherwise influence a run. The descriptive audit is
`a4_shadow.py`, run after the complete batch.

    python work_interface/w1d/harness/run_batch.py --run all
    python work_interface/w1d/harness/run_batch.py --run all --dry-run
    python work_interface/w1d/harness/run_batch.py --show-block
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W1D = HERE.parent
WI = W1D.parent
sys.path.insert(0, str(WI / "harness"))
sys.path.insert(0, str(WI / "w1b" / "harness"))      # frozen canonical-block reader
import single_block_harness as L                      # noqa: E402
from acp_session import ACPSession, GOOSE_EXE         # noqa: E402
import block_harness as BLOCKSRC                      # noqa: E402

RUNS_DIR = W1D / "runs"
ALL_RUNS = ["K1", "K2", "K3"]
ARTIFACT = "work_definition.json"

FROZEN_SKILL_SHA256 = (
    "0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a")   # r2
CANONICAL_BLOCK_SHA256 = (
    "46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330")
W1A = WI / "w1a"
HUMAN_ANSWERS = W1A / "human_answers.md"
HUMAN_ANSWERS_SHA256 = (
    "5fe99a5bb41a3f3698e7f821c0355c5bfd4812c266883b77bef0e09da5d1b1bd")

FORBIDDEN_EXTRA = ["human_answers", "work_definition.py", "census", "authority",
                   "fidelity", "RESULTS.json", "RESULTS.md", "FIDELITY.json",
                   "FIDELITY.md", "POSTMORTEM", "CLOSURE", "DISPOSITION",
                   "ANALYSIS", "w1a/runs", "w1a2/runs", "w1a3/runs",
                   "w1a4/runs", "w1a5/runs", "w1b/runs", "w1c/runs",
                   "work_interface/cases"]


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
    ap = argparse.ArgumentParser(description="W1-D batch (Surface B only)")
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
    print("lifecycle      : r2 single-block; A4 in SHADOW mode (non-binding)")

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
        res = L.run_one(run, d, block,
                        lambda: ACPSession(d, transcript),
                        artifact_name=ARTIFACT,
                        controlled=controlled(d),
                        all_runs=ALL_RUNS,
                        forbidden_extra=FORBIDDEN_EXTRA,
                        fs_enforcing=False)          # SHADOW, non-binding
        print(f"  outcome            : {res.outcome}")
        print(f"  reason             : {res.reason[:400]}")
        print(f"  turns              : {res.turns}")
        print(f"  blocks delivered   : {res.blocks_delivered}")
        print(f"  continuations sent : {res.continuations_sent}")
        print(f"  silent turns       : {res.silent_turns}")
        print(f"  artifact           : {res.artifact}")
        (d / "harness_result.json").write_text(
            json.dumps({"run": res.run, "outcome": res.outcome,
                        "reason": res.reason, "turns": res.turns,
                        "artifact": res.artifact,
                        "blocks_delivered": res.blocks_delivered,
                        "continuations_sent": res.continuations_sent,
                        "silent_turns": res.silent_turns,
                        "block_sha256": digest,
                        "lifecycle_revision": "r2_single_block",
                        "fs_authority_mode": "SHADOW_DEFERRED",
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
