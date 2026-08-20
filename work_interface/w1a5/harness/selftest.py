#!/usr/bin/env python3
"""Self-test for the W1-A5 ACP harness.

  Part A   turn-level matcher semantics (unchanged from W1-A4), no model
  Part B   CHANGE 1 -- question presentation normalization
  Part C   CHANGE 2 -- the lifecycle state machine
  Part D   regression against captured fixtures:
             C1/C2/C3 first turns  (W1-A3, must stay RECOGNIZED incl. intent 0)
             D1 failing turn       (W1-A4, its two markdown-wrapped questions
                                    must now be DETECTED)
             D2 silent turn        (W1-A4, must classify QUIESCENT -- the fixture
                                    carries the real empty visible text and no
                                    fabricated assistant message)
  Part E   one live Goose ACP session in a TEMPORARY directory

Touches no W1-A5 run directory. E1/E2/E3 are never opened for writing.

    python work_interface/w1a5/harness/selftest.py
    python work_interface/w1a5/harness/selftest.py --matcher   # A-D only
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acp_harness as H  # noqa: E402

REG = Path(__file__).resolve().parent / "fixtures" / "regression"
FAILS: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(label)


def part_a() -> None:
    print("\n[A] turn-level matcher (unchanged semantics)")
    I = H.load_answer_table()
    check(len(I) == 9, "answer table parses 9 intents", f"got {len(I)}")
    check(H.sha256_file(H.HUMAN_ANSWERS) == H.HUMAN_ANSWERS_SHA256,
          "human_answers.md matches the frozen hash")

    c = H.classify_turn("Which field identifies the same record in both files?", I)
    check(c["intents"] == [0] and c["answers"] == ["InvoiceNumber"],
          "single question -> RECOGNIZED {0}")

    c = H.classify_turn("Should we match records by `InvoiceNumber`? "
                        "Any other field is a better candidate?", I)
    check(c["status"] == H.RECOGNIZED and c["intents"] == [0]
          and c["unmatched"] == ["Any other field is a better candidate?"],
          "trailing conversational fragment recorded, not fatal")

    c = H.classify_turn("Is Currency part of the rule?\n"
                        "Which field identifies the same record?", I)
    check(c["intents"] == [0, 2] and c["answers"][0] == "InvoiceNumber",
          "answers emitted in FROZEN TABLE ORDER")

    c = H.classify_turn("What is your favourite colour?", I)
    check(c["status"] == H.NO_MATCH, "zero recognized intents -> NO_MATCH")

    check(H.render_answers(["InvoiceNumber"]) == "InvoiceNumber",
          "single answer sent bare (rendering unchanged)")
    check(H.render_answers(["A", "B"]) == "1. A\n2. B",
          "multiple answers use the frozen numbered format (unchanged)")


def part_b() -> None:
    print("\n[B] CHANGE 1 -- question presentation normalization")
    plain = "Should Amount be compared, and with what tolerance?"
    variants = {
        "bold-wrapped   `?**`": f"**{plain}**",
        "italic-wrapped `?*`": f"*{plain}*",
        "backticked": f"`{plain}`",
        "trailing whitespace": f"{plain}   ",
        "bold + numbered": f"3. **{plain}**",
    }
    for label, v in variants.items():
        check(H.is_interrogative(v), f"{label} is interrogative")
        check(H.segment_fragments(v) != [], f"{label} yields a fragment")

    I = H.load_answer_table()
    a = H.classify_turn(plain, I)
    b = H.classify_turn(f"**{plain}**", I)
    check(a["intents"] == b["intents"] == [1],
          "`?**` and `?` classify identically", f"{a['intents']} vs {b['intents']}")

    two = f"**Q5: Is Currency part of the rule?** And separately:\n**Q6: {plain}**"
    c = H.classify_turn(two, I)
    check(sorted(c["intents"]) == [1, 2],
          "emphasis mid-line does not swallow the next question", str(c["intents"]))

    check(not H.is_interrogative("I have read both files."),
          "normalization does not make a statement interrogative")
    check(H.classify_turn("The Amount column is numeric.", I)["status"] == H.NO_MATCH,
          "narration still yields no answer")


def part_c() -> None:
    print("\n[C] CHANGE 2 -- lifecycle state machine")
    check(H.classify_lifecycle("", False, False) == H.QUIESCENT,
          "no visible content, no artifact, no infra failure -> QUIESCENT")
    check(H.classify_lifecycle("   \n\t ", False, False) == H.QUIESCENT,
          "whitespace-only content -> QUIESCENT")
    check(H.classify_lifecycle("Which field?", False, False) == H.DIALOGUE,
          "visible content -> DIALOGUE")
    check(H.classify_lifecycle("", True, False) == H.COMPLETED,
          "artifact present wins over silence -> COMPLETED")
    check(H.classify_lifecycle("", False, True) == H.HARNESS_ERROR,
          "infrastructure failure wins -> HARNESS_ERROR")

    check(H.CONTINUATION == "Continue.",
          "the continuation is exactly `Continue.`", repr(H.CONTINUATION))
    check(H.MAX_CONSECUTIVE_SILENT == 2, "at most two consecutive continuations")

    check(H.next_silent_action(0) == ("CONTINUE", 1), "first silent turn -> continue")
    check(H.next_silent_action(1) == ("CONTINUE", 2), "second silent turn -> continue")
    a, _ = H.next_silent_action(2)
    check(a == "QUIESCENT_RETRY_LIMIT", "third consecutive silent turn -> limit")

    # Tool calls must NOT reset the streak: activity is not dialogue advance.
    import inspect
    sig = list(inspect.signature(H.next_silent_action).parameters)
    check(sig == ["silent_streak"],
          "next_silent_action takes ONLY the streak; no progress/tool-call input",
          str(sig))
    check(H.classify_lifecycle("", False, False) == H.QUIESCENT,
          "a turn with tool calls but no visible text is still QUIESCENT")

    canon = {i.canonical for i in H.load_answer_table()}
    check(H.CONTINUATION not in canon and "?" not in H.CONTINUATION,
          "the continuation carries no business/task content")


def part_d() -> None:
    print("\n[D] regression against captured fixtures")
    I = H.load_answer_table()

    for run in ("C1", "C2", "C3"):
        f = REG / f"{run}_first_turn.txt"
        c = H.classify_turn(f.read_text(encoding="utf-8"), I)
        check(c["status"] == H.RECOGNIZED and 0 in c["intents"],
              f"W1-A3 {run} still RECOGNIZED incl. intent 0", f"intents={c['intents']}")

    f = REG / "D1_failing_turn.txt"
    check(f.is_file(), "D1 failing-turn fixture present")
    text = f.read_text(encoding="utf-8")
    frags = H.segment_fragments(text)
    print(f"        D1 detected fragments ({len(frags)}):")
    for x in frags:
        print(f"          - {x[:100]}")
    check(len(frags) == 2,
          "D1's TWO markdown-wrapped questions are detected", f"got {len(frags)}")
    check(all(x.endswith("?") for x in frags),
          "both detected fragments normalize to a terminal '?'")
    c = H.classify_turn(text, I)
    check(c["status"] == H.RECOGNIZED,
          "D1's failing turn no longer scores NO_MATCH", f"intents={c['intents']}")
    check(all(a in {i.canonical for i in I} for a in c["answers"]),
          "D1 emits only frozen canonical answers")

    p = REG / "D2_silent_turn.json"
    check(p.is_file(), "D2 silent-turn fixture present")
    st = json.loads(p.read_text(encoding="utf-8"))
    check(st["agent_message_chunks"] == 0 and st["agent_visible_text"] == "",
          "fixture carries the REAL silent state; no assistant message fabricated")
    state = H.classify_lifecycle(st["agent_visible_text"], st["artifact_present"],
                                 st["infrastructure_failure"])
    check(state == H.QUIESCENT,
          "D2's captured turn classifies QUIESCENT, not CONTESTED", state)
    action, streak = H.next_silent_action(0)
    check(action == "CONTINUE",
          "D2 would receive a continuation rather than terminating the run",
          f"tool_calls={st['tool_calls']} -> streak={streak}")

    # --- the corrected budget, end to end -------------------------------
    # silent + tool calls -> Continue #1 -> silent + DIFFERENT tool calls ->
    # Continue #2 -> silent + MORE tool calls -> QUIESCENT_RETRY_LIMIT.
    # Each step reuses D2's real silent state (empty visible text); only the
    # tool-call counts vary, and they must not rescue the run.
    print("        tool-calling silent sequence (tool calls must not reset):")
    streak, continuations, tool_totals, final = 0, 0, [4, 7, 9], None
    for step, tools_total in enumerate(tool_totals, 1):
        state = H.classify_lifecycle(st["agent_visible_text"], False, False)
        if state != H.QUIESCENT:
            final = f"unexpected lifecycle state {state}"
            break
        action, streak = H.next_silent_action(streak)
        print(f"          step {step}: tool_calls_total={tools_total} "
              f"-> {action} (streak={streak})")
        if action == "CONTINUE":
            continuations += 1
        else:
            final = action
            break
    check(continuations == 2,
          "exactly two `Continue.` re-entries are permitted", f"got {continuations}")
    check(final == "QUIESCENT_RETRY_LIMIT",
          "third silent turn WITH tool calls hits QUIESCENT_RETRY_LIMIT", str(final))


def part_e() -> None:
    print("\n[E] live ACP session in a temporary directory")
    if not H.GOOSE_EXE.is_file():
        check(False, "goose CLI present", str(H.GOOSE_EXE))
        return
    tmp = Path(tempfile.mkdtemp(prefix="w1a5_selftest_"))
    try:
        runs = tmp / "runs"
        d = runs / "E1"
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

        res = H.run_one("E1", runs_dir=runs, check_skill=False)
        print(f"  outcome={res.outcome} turns={res.turns} artifact={res.artifact} "
              f"silent_continuations={res.silent_continuations}")

        check(res.outcome == H.COMPLETED, "session reached COMPLETED", res.reason)
        check(res.artifact and (d / "work_definition.json").is_file(),
              "artifact detected; first-artifact hard stop preserved")
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
    ap.add_argument("--matcher", action="store_true", help="parts A-D only")
    args = ap.parse_args(argv)

    print("W1-A5 harness self-test")
    part_a()
    part_b()
    part_c()
    part_d()
    if not args.matcher:
        part_e()

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
