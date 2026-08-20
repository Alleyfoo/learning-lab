#!/usr/bin/env python3
"""Surface B self-test — offline lifecycle regressions. NO Goose, NO model.

Driven by a scripted fake ACP transport, so every lifecycle property is provable
during preparation.

    python work_interface/harness/selftest_single_block.py
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import single_block_harness as H  # noqa: E402

BLOCK = ("Which field identifies the **same record / invoice** in both files?\n"
         "InvoiceNumber\n\nShould **Amount** be compared, and if so, how and with "
         "what tolerance?\nYes, compare Amount numerically, within 0.01.")

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(label)


class FakeSession:
    """Scripted transport. Records every outgoing session/prompt verbatim."""
    FILLER = "(scripted transport: no further content)"

    def __init__(self, turns, artifact_path: Path | None = None,
                 artifact_at: int | None = None):
        self.turns = list(turns)
        self.sent: list[str] = []
        self.lifecycle: list[dict] = []
        self.tool_payloads: list[str] = []
        self.unoffered_requests: list = []
        self._i = 0
        self.artifact_path = artifact_path
        self.artifact_at = artifact_at

    def request(self, method, params, timeout=120):
        if method == "initialize":
            return {"result": {"protocolVersion": 1}}
        if method == "session/new":
            return {"result": {"sessionId": "fake"}}
        if method == "session/set_mode":
            return {"result": {}}
        if method == "session/prompt":
            self.sent.append(params["prompt"][0]["text"])
            self._i += 1
            if self.artifact_at is not None and self._i == self.artifact_at:
                self.artifact_path.write_text('{"ok": true}', encoding="utf-8",
                                              newline="\n")
            return {"result": {"stopReason": "end_turn"}}
        return {"result": {}}

    def drain_agent_text(self):
        i = self._i - 1
        return self.turns[i] if 0 <= i < len(self.turns) else self.FILLER

    def record_lifecycle(self, obj):
        self.lifecycle.append(obj)

    def close(self):
        pass


def make_run(tmp: Path, name: str) -> Path:
    d = tmp / "runs" / name
    d.mkdir(parents=True)
    (d / "PROMPT.md").write_text("RUN PROMPT TEXT\n", encoding="utf-8", newline="\n")
    (d / "SKILL.md").write_text("# frozen skill\n", encoding="utf-8", newline="\n")
    return d


def drive(tmp: Path, name: str, turns, artifact_at=None):
    d = make_run(tmp, name)
    art = d / "work_definition.json"
    s = FakeSession(turns, artifact_path=art, artifact_at=artifact_at)
    res = H.run_one(name, d, BLOCK, lambda: s,
                    controlled={"PROMPT.md": d / "PROMPT.md",
                                "SKILL.md": d / "SKILL.md"})
    return res, s, d


def main() -> int:
    print("=" * 72)
    print("SURFACE B -- single-block lifecycle self-test (no Goose, no model)")
    print("=" * 72)
    tmp = Path(tempfile.mkdtemp(prefix="b_selftest_"))
    try:
        # ---------------- R1: the H1 reproduction ----------------------
        print("\n[R1] H1 reproduction: questions, silent, query, query, artifact")
        res, s, d = drive(tmp, "R1",
                          ["I have questions: which field is the key?",
                           "",
                           "Which output_order should I use?",
                           "And on_duplicate_key? on_non_numeric?",
                           "writing now"],
                          artifact_at=5)
        kinds = [e["sent"] for e in res.turn_log]
        print(f"        turns={res.turns} sent={kinds} "
              f"blocks={res.blocks_delivered} continuations={res.continuations_sent}")
        check(res.outcome == H.COMPLETED, "R1 -> COMPLETED", res.reason)
        check(res.turns == 5, "terminated on the artifact turn", str(res.turns))
        check(kinds == [H.SENT_BLOCK, H.SENT_CONTINUATION,
                        H.SENT_CONTINUATION, H.SENT_CONTINUATION],
              "block once, then three continuations", str(kinds))
        check(res.blocks_delivered == 1, "THE BLOCK WAS EMITTED EXACTLY ONCE",
              str(res.blocks_delivered))
        after = s.sent[2:]
        check(all(m == H.CONTINUATION for m in after),
              "every activation after the block is byte-identical 'Continue.'")
        check(len(set(after)) == 1 and after[0] == "Continue.",
              "exactly one distinct activation string", repr(set(after)))
        check(s.sent[0].startswith("RUN PROMPT"), "turn 1 sent the run prompt")
        check(s.sent[1] == BLOCK, "turn 2 sent the canonical block verbatim")
        check(BLOCK not in "".join(after),
              "the block never appears again in any later message")
        texts = [e["agent_turn_text"] for e in res.turn_log]
        check(texts[2] == "Which output_order should I use?"
              and texts[3].startswith("And on_duplicate_key?"),
              "post-block question text recorded VERBATIM")

        # ---------------- R2: artifact before the block ----------------
        print("\n[R2] immediate artifact on turn 1 -- block never sent")
        res, s, d = drive(tmp, "R2", ["done"], artifact_at=1)
        check(res.outcome == H.COMPLETED, "R2 -> COMPLETED", res.reason)
        check(res.blocks_delivered == 0, "no block was delivered",
              str(res.blocks_delivered))
        check(len(s.sent) == 1 and s.sent[0].startswith("RUN PROMPT"),
              "only the run prompt was ever sent", str(len(s.sent)))

        # ---------------- R3: artifact immediately after the block -----
        print("\n[R3] artifact on turn 2, immediately after the block")
        res, s, d = drive(tmp, "R3", ["questions?", "writing"], artifact_at=2)
        check(res.outcome == H.COMPLETED, "R3 -> COMPLETED", res.reason)
        check(res.blocks_delivered == 1 and res.continuations_sent == 0,
              "exactly one block, zero continuations",
              f"{res.blocks_delivered}/{res.continuations_sent}")
        check(s.sent[1] == BLOCK, "the block was the second and last message")

        # ---------------- R4: silent turns reach the retry limit -------
        print("\n[R4] repeated silent turns reach the retry limit")
        res, s, d = drive(tmp, "R4", ["", "", "", "", ""])
        check(res.outcome == H.CONTESTED, "R4 -> CONTESTED", res.outcome)
        check("QUIESCENT_RETRY_LIMIT" in res.reason,
              "labelled QUIESCENT_RETRY_LIMIT", res.reason[:70])
        check(res.silent_turns == 3, "three silent turns before the stop",
              str(res.silent_turns))
        check(res.blocks_delivered == 1,
              "the first silent turn still earned the block exactly once",
              str(res.blocks_delivered))
        check(res.continuations_sent == 1,
              "then exactly one continuation before the limit",
              str(res.continuations_sent))

        # ---------------- R5: visible content resets the streak --------
        print("\n[R5] visible content resets the silent streak")
        res, s, d = drive(tmp, "R5",
                          ["q?", "", "", "I am still here", "", "", "done"],
                          artifact_at=7)
        check(res.outcome == H.COMPLETED,
              "two silences, visible content, two more silences -> survives",
              res.reason)
        streaks = [e["silent_streak"] for e in res.turn_log]
        print(f"        silent_streak per turn: {streaks}")
        check(streaks[3] == 0, "visible content reset the streak to 0", str(streaks))
        check(res.blocks_delivered == 1, "still exactly one block",
              str(res.blocks_delivered))

        print("\n[R5b] a visible POST-BLOCK QUESTION resets the streak but earns only 'Continue.'")
        res, s, d = drive(tmp, "R5b",
                          ["q?", "", "", "But what about output_order?", "", "", "x"],
                          artifact_at=7)
        streaks = [e["silent_streak"] for e in res.turn_log]
        check(streaks[3] == 0, "the question reset the streak", str(streaks))
        check(res.turn_log[3]["sent"] == H.SENT_CONTINUATION,
              "and it received a continuation, not information")
        check(s.sent[4] == H.CONTINUATION, "the message sent was exactly 'Continue.'",
              repr(s.sent[4]))

        # ---------------- R6: questions never cause delivery -----------
        print("\n[R6] post-block questions NEVER cause information delivery")
        res, s, d = drive(tmp, "R6",
                          ["first?",
                           "Which field identifies the same record in both files?",
                           "Should Amount be compared, and with what tolerance?",
                           "Please just resend the answers.",
                           "ok"],
                          artifact_at=5)
        check(res.blocks_delivered == 1,
              "four question turns, still exactly one block",
              str(res.blocks_delivered))
        later = s.sent[2:]
        check(all(m == H.CONTINUATION for m in later),
              "every reply to a question was 'Continue.'", repr(set(later)))
        check(sum(1 for m in s.sent if m == BLOCK) == 1,
              "the block string appears exactly once across the whole session")

        # ---------------- invariants -----------------------------------
        print("\n[INV] lifecycle invariants")
        check(H.CONTINUATION == "Continue.", "the activation is exactly 'Continue.'",
              repr(H.CONTINUATION))
        check(H.MAX_CONSECUTIVE_SILENT == 2, "at most two consecutive re-entries")
        check(H.next_silent_action(0) == ("CONTINUE", 1)
              and H.next_silent_action(1) == ("CONTINUE", 2)
              and H.next_silent_action(2)[0] == "QUIESCENT_RETRY_LIMIT",
              "silent budget: continue, continue, limit")
        import inspect
        check(list(inspect.signature(H.next_silent_action).parameters)
              == ["silent_streak"],
              "tool activity has no path to reset the streak")
        check(H.next_message(False, BLOCK) == (BLOCK, H.SENT_BLOCK)
              and H.next_message(True, BLOCK) == (H.CONTINUATION,
                                                  H.SENT_CONTINUATION),
              "next_message depends ONLY on whether the block was already sent")
        check(list(inspect.signature(H.next_message).parameters)
              == ["block_sent", "block"],
              "next_message cannot see the agent's text at all",
              str(list(inspect.signature(H.next_message).parameters)))

        # ---------------- A4 remains independent -----------------------
        print("\n[A4] the filesystem backstop still contests, independently")
        res, s, d = drive(tmp, "A4", ["q?", "writing"], artifact_at=2)
        check(res.outcome == H.COMPLETED, "clean run completes", res.reason)
        check(res.fs_authority["filesystem_authority"] == "CLEAN",
              "and reports CLEAN filesystem authority")
        d2 = make_run(tmp, "A4b")
        art = d2 / "work_definition.json"
        s2 = FakeSession(["q?", "writing"], artifact_path=art, artifact_at=2)
        orig = s2.request

        def sneaky(method, params, timeout=120):
            out = orig(method, params, timeout)
            if method == "session/prompt" and s2._i == 1:
                (d2 / "temp_skill.txt").write_text("side effect\n",
                                                   encoding="utf-8", newline="\n")
            return out
        s2.request = sneaky
        res2 = H.run_one("A4b", d2, BLOCK, lambda: s2,
                         controlled={"PROMPT.md": d2 / "PROMPT.md",
                                     "SKILL.md": d2 / "SKILL.md"})
        check(res2.outcome == H.CONTESTED,
              "a stray write contests the run even though the lifecycle succeeded",
              res2.reason[:90])
        check("temp_skill.txt" in res2.reason, "the exact offending path is named")
        check((d2 / "temp_skill.txt").is_file(), "offending file preserved")

        print("\n[A4-shadow] fs_enforcing=False cannot influence the run")
        d3 = make_run(tmp, "A4c")
        art3 = d3 / "work_definition.json"
        s3 = FakeSession(["q?", "writing"], artifact_path=art3, artifact_at=2)
        orig3 = s3.request

        def sneaky3(method, params, timeout=120):
            out = orig3(method, params, timeout)
            if method == "session/prompt" and s3._i == 1:
                (d3 / "temp_skill.txt").write_text("side effect\n",
                                                   encoding="utf-8", newline="\n")
            return out
        s3.request = sneaky3
        res3 = H.run_one("A4c", d3, BLOCK, lambda: s3,
                         controlled={"PROMPT.md": d3 / "PROMPT.md",
                                     "SKILL.md": d3 / "SKILL.md"},
                         fs_enforcing=False)
        check(res3.outcome == H.COMPLETED,
              "the identical stray write does NOT contest in shadow mode",
              res3.reason)
        check(res3.fs_authority.get("filesystem_authority") == "SHADOW_DEFERRED",
              "no verdict is computed in-run; it is deferred to the audit",
              str(res3.fs_authority))
        check(res3.fs_snapshot_before and "PROMPT.md" in res3.fs_snapshot_before,
              "the pre-run snapshot is still recorded as data for the audit")
        check((d3 / "temp_skill.txt").is_file(),
              "and the offending file is still preserved, unaltered")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 72)
    if FAILS:
        print(f"SURFACE B SELF-TEST FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("SURFACE B SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
