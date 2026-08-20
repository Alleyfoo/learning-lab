#!/usr/bin/env python3
"""Self-test for the W1-A4 ACP harness.

  Part A  turn-level matcher semantics, no model
  Part B  REGRESSION: the exact C1/C2/C3 first-turn messages that W1-A3 died on.
          Each must now be RECOGNIZED and must include intent 0 (the match key).
          These are frozen post-W1-A3 fixtures; they are real captured output, not
          invented examples, and they may not be edited to make the test pass.
  Part C  one live Goose ACP session in a TEMPORARY directory

Touches no W1-A4 run directory. D1/D2/D3 are never opened for writing.

    python work_interface/w1a4/harness/selftest.py
    python work_interface/w1a4/harness/selftest.py --matcher   # A + B only
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acp_harness as H  # noqa: E402

REGRESSION = Path(__file__).resolve().parent / "fixtures" / "regression"
FAILS: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(label)


def part_a() -> None:
    print("\n[A] turn-level matcher (no model)")
    I = H.load_answer_table()
    check(len(I) == 9, "answer table parses 9 intents", f"got {len(I)}")
    check(H.sha256_file(H.HUMAN_ANSWERS) == H.HUMAN_ANSWERS_SHA256,
          "human_answers.md matches the frozen hash")

    c = H.classify_turn("Which field identifies the same record in both files?", I)
    check(c["status"] == H.RECOGNIZED and c["intents"] == [0]
          and c["answers"] == ["InvoiceNumber"],
          "single question -> RECOGNIZED {0}", str(c["answers"]))

    c = H.classify_turn("1. Should Amount be compared, and with what tolerance?\n"
                        "2. Is Currency part of the reconciliation rule?", I)
    check(c["intents"] == [1, 2] and len(c["answers"]) == 2,
          "two distinct intents -> both, once each", str(c["intents"]))

    # the exact shape that killed W1-A3
    c = H.classify_turn("Should we match records by `InvoiceNumber`? "
                        "Any other field is a better candidate?", I)
    check(c["status"] == H.RECOGNIZED and c["intents"] == [0],
          "load-bearing question + trailing conversational fragment -> RECOGNIZED")
    check(c["unmatched"] == ["Any other field is a better candidate?"],
          "the trailing fragment is RECORDED as unmatched", str(c["unmatched"]))
    check(c["answers"] == ["InvoiceNumber"],
          "the unmatched fragment receives no invented response")

    c = H.classify_turn("Which field identifies the same record?\n"
                        "Or is some other invoice field the key?", I)
    check(c["intents"] == [0] and len(c["answers"]) == 1,
          "two formulations of one intent collapse to one intent+answer")

    c = H.classify_turn("Should Amount be compared and is Currency part of the rule?", I)
    check(sorted(c["intents"]) == [1, 2],
          "one fragment spanning two intents recognizes both", str(c["intents"]))

    c = H.classify_turn("Is Currency part of the rule?\n"
                        "Which field identifies the same record?", I)
    check(c["intents"] == [0, 2] and c["answers"][0] == "InvoiceNumber",
          "answers are emitted in FROZEN TABLE ORDER, not question order")

    c = H.classify_turn("What is your favourite colour?", I)
    check(c["status"] == H.NO_MATCH and c["answers"] == [],
          "zero recognized intents -> NO_MATCH")

    c = H.classify_turn("I have read both files and will now build the definition.", I)
    check(c["status"] == H.NO_MATCH, "turn with no question -> NO_MATCH")

    check(H.render_answers(["InvoiceNumber"]) == "InvoiceNumber",
          "a single answer is sent bare")
    check(H.render_answers(["A", "B"]) == "1. A\n2. B",
          "several answers use the frozen numbered format")

    canon = {i.canonical for i in I}
    for c2 in [H.classify_turn(t, I) for t in
               ["Which field identifies the same record?",
                "Should Amount be compared? Is Currency in the rule?"]]:
        check(all(a in canon for a in c2["answers"]),
              "every emitted answer is verbatim from the frozen table")


def part_b() -> None:
    print("\n[B] regression: the exact turns W1-A3 died on")
    I = H.load_answer_table()
    for run in ("C1", "C2", "C3"):
        f = REGRESSION / f"{run}_first_turn.txt"
        if not f.is_file():
            check(False, f"{run} regression fixture present", str(f))
            continue
        c = H.classify_turn(f.read_text(encoding="utf-8"), I)
        check(c["status"] == H.RECOGNIZED, f"{run} first turn -> RECOGNIZED",
              f"status={c['status']}")
        check(0 in c["intents"], f"{run} resolves the match key to intent 0",
              f"intents={c['intents']}")
        print(f"        {run}: intents={c['intents']}  "
              f"unmatched_fragments={len(c['unmatched'])}")
        check(all(a in {i.canonical for i in I} for a in c["answers"]),
              f"{run} emits only frozen canonical answers")


def part_c() -> None:
    print("\n[C] live ACP session in a temporary directory")
    if not H.GOOSE_EXE.is_file():
        check(False, "goose CLI present", str(H.GOOSE_EXE))
        return
    tmp = Path(tempfile.mkdtemp(prefix="w1a4_selftest_"))
    try:
        runs = tmp / "runs"
        d = runs / "D1"
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

        res = H.run_one("D1", runs_dir=runs, check_skill=False)
        print(f"  outcome={res.outcome} turns={res.turns} artifact={res.artifact}")
        print(f"  reason={res.reason}")

        check(res.outcome == H.COMPLETED, "session reached COMPLETED", res.reason)
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matcher", action="store_true", help="parts A and B only")
    args = ap.parse_args(argv)

    print("W1-A4 harness self-test")
    part_a()
    part_b()
    if not args.matcher:
        part_c()

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
