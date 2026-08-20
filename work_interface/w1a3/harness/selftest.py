#!/usr/bin/env python3
"""Harmless self-test for the W1-A3 ACP harness.

Part A exercises the deterministic matcher with no model at all.
Part B drives one real Goose ACP session in a TEMPORARY directory with a throwaway
task, proving session control, artifact detection, immediate termination, transcript
capture and controlled-input hashing.

Touches no W1-A3 run directory. C1/C2/C3 are never opened for writing, and no
Learning Lab file is modified.

    python work_interface/w1a3/harness/selftest.py            # A + B
    python work_interface/w1a3/harness/selftest.py --matcher  # A only
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acp_harness as H  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(label)


def part_a() -> None:
    print("\n[A] deterministic matcher (no model)")
    intents = H.load_answer_table()
    check(len(intents) == 9, "answer table parses 9 intents", f"got {len(intents)}")
    check(H.sha256_file(H.HUMAN_ANSWERS) == H.HUMAN_ANSWERS_SHA256,
          "human_answers.md matches the frozen hash")

    r = H.match_message("Which field identifies the same record in both files?", intents)
    check(r["status"] == H.UNIQUE_MATCH and r["answers"] == ["InvoiceNumber"],
          "single question -> UNIQUE_MATCH, canonical answer", str(r["answers"]))

    multi = ("1. Should Amount be compared, and with what tolerance?\n"
             "2. Is Currency part of the reconciliation rule?")
    r = H.match_message(multi, intents)
    check(r["status"] == H.UNIQUE_MATCH and len(r["answers"]) == 2,
          "two distinct intents in one message -> both canonical answers",
          str(r["answers"]))
    check(r["answers"][0].startswith("Yes, compare Amount")
          and r["answers"][1].startswith("No. All sample amounts"),
          "the two answers are the frozen strings, in question order")

    r = H.match_message("What is your favourite colour?", intents)
    check(r["status"] == H.NO_MATCH, "unknown question -> NO_MATCH")

    r = H.match_message("Should Amount be compared and is Currency part of the rule?",
                        intents)
    check(r["status"] == H.MULTIPLE_MATCHES,
          "one question spanning two intents -> MULTIPLE_MATCHES")

    r = H.match_message("I have read both files and will now build the definition.",
                        intents)
    check(r["status"] == H.NO_MATCH, "turn with no question -> NO_MATCH")

    check(H.render_answers(["InvoiceNumber"]) == "InvoiceNumber",
          "one answer is sent bare, with nothing added")
    check(H.render_answers(["A", "B"]) == "1. A\n2. B",
          "several answers use the frozen numbered format")

    canon = {i.canonical for i in intents}
    check(all(a in canon for a in ["InvoiceNumber",
                                   "Yes, compare Amount numerically, within 0.01."]),
          "canonical strings are taken verbatim from the frozen table")


def part_b() -> None:
    print("\n[B] live ACP session in a temporary directory")
    if not H.GOOSE_EXE.is_file():
        check(False, "goose CLI present", str(H.GOOSE_EXE))
        return
    tmp = Path(tempfile.mkdtemp(prefix="w1a3_selftest_"))
    try:
        runs = tmp / "runs"
        d = runs / "T1"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# throwaway skill (self-test only)\n",
                                    encoding="utf-8", newline="\n")
        (d / "PROMPT.md").write_text(
            "This is a harness self-test.\n\n"
            "Write a file named work_definition.json in your current directory whose "
            'entire contents are exactly: {"selftest": true}\n\n'
            "Stop immediately after the file has been written.\n",
            encoding="utf-8", newline="\n")
        print(f"  temp run dir: {d}")

        res = H.run_one("T1", runs_dir=runs, check_skill=False)
        print(f"  outcome={res.outcome} turns={res.turns} artifact={res.artifact}")
        print(f"  reason={res.reason}")

        check(res.outcome == "COMPLETED", "session reached COMPLETED", res.reason)
        check(res.artifact and (d / "work_definition.json").is_file(),
              "artifact detected and present on disk")
        t = d / "acp_transcript.jsonl"
        lines = t.read_text(encoding="utf-8").splitlines() if t.is_file() else []
        check(len(lines) > 5, "append-only transcript captured", f"{len(lines)} messages")
        sent = [l for l in lines if '"dir": "out"' in l and "session/prompt" in l]
        check(any("harness self-test" in l for l in sent),
              "the prompt was sent as TEXT, not as a filepath")
        check(not any("PROMPT.md" in l for l in sent),
              "no session/prompt message names PROMPT.md")
        check(res.hashes_before == res.hashes_after,
              "controlled inputs unchanged across the run")
        check(H.sha256_file(H.HUMAN_ANSWERS) == H.HUMAN_ANSWERS_SHA256,
              "frozen answer source untouched by the run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matcher", action="store_true", help="run part A only")
    args = ap.parse_args(argv)

    print("W1-A3 harness self-test")
    part_a()
    if not args.matcher:
        part_b()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"SELF-TEST FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
