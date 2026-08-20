#!/usr/bin/env python3
"""Self-test for the W1-B ablation harness. NO Goose, NO model execution.

The turn loop is driven by a scripted fake ACP transport, so every property can
be proven offline during preparation:

  A  the canonical block is exactly the five SKILL-mandated answers, verbatim
  B  nothing excluded leaks into it
  C  THE ABLATION PROPERTY -- the outgoing message is byte-identical regardless
     of what the worker said, or whether it said anything
  D  the first-artifact hard stop still terminates at once
  E  continued questioning after the block is logged and does NOT fail the run
  F  never producing an artifact while holding the block ends the run
     CONTESTED: BLOCKED_WITH_COMPLETE_INFORMATION

    python work_interface/w1b/harness/selftest.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import block_harness as B  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{('  -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(label)


class FakeSession:
    """Scripted ACP transport. Records every outgoing session/prompt so the
    ablation property can be asserted. Runs no subprocess."""

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
        self.closed = False

    def request(self, method, params, timeout=120):
        if method == "initialize":
            return {"result": {"protocolVersion": 1}}
        if method == "session/new":
            return {"result": {"sessionId": "fake-1"}}
        if method == "session/set_mode":
            return {"result": {}}
        if method == "session/prompt":
            self.sent.append(params["prompt"][0]["text"])
            self._i += 1
            if self.artifact_at is not None and self._i == self.artifact_at:
                self.artifact_path.write_text('{"selftest": true}',
                                              encoding="utf-8", newline="\n")
            return {"result": {"stopReason": "end_turn"}}
        return {"result": {}}

    FILLER = "(scripted transport: no further content)"

    def drain_agent_text(self):
        idx = self._i - 1
        if 0 <= idx < len(self.turns):
            return self.turns[idx]
        # Non-empty filler: an exhausted script must not masquerade as the
        # worker falling silent, or silent-turn counts become a test artifact.
        return self.FILLER

    def record_lifecycle(self, obj):
        self.lifecycle.append(obj)

    def close(self):
        self.closed = True


def make_run(tmp: Path, name: str = "F1") -> Path:
    d = tmp / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("# throwaway skill (self-test only)\n",
                                encoding="utf-8", newline="\n")
    (d / "PROMPT.md").write_text("This is a W1-B self-test prompt.\n",
                                 encoding="utf-8", newline="\n")
    return d


def part_ab() -> str:
    print("\n[A/B] the canonical block")
    rows = B.load_table_rows()
    check(len(rows) == 9, "frozen table reads 9 rows", f"got {len(rows)}")
    check(B.sha256_file(B.HUMAN_ANSWERS) == B.HUMAN_ANSWERS_SHA256,
          "human_answers.md matches the frozen hash")

    block = B.build_block()
    check(B.MANDATED_ROWS == (0, 1, 2, 3, 4, 5), "mandated rows are 0-5",
          str(B.MANDATED_ROWS))
    check(B.EXCLUDED_ROWS == (6, 7, 8), "excluded rows are 6-8", str(B.EXCLUDED_ROWS))

    for i in B.MANDATED_ROWS:
        cell, ans = rows[i]
        check(cell in block and ans in block,
              f"row {i} question and answer both present verbatim")

    # frozen order
    positions = [block.index(rows[i][1]) for i in B.MANDATED_ROWS]
    check(positions == sorted(positions), "answers appear in FROZEN TABLE ORDER",
          str(positions))

    for i in B.EXCLUDED_ROWS:
        cell, ans = rows[i]
        check(ans not in block, f"excluded row {i} answer does NOT leak into the block",
              ans[:40])
    check("Refuse the run" not in block,
          "no duplicate-key / non-numeric policy in the block")
    low = block.lower()
    for banned in ("left_then_right", "sorted_by_key", "output order", "output_order",
                   "both_same", "only_left", "classify", "purpose",
                   "refuse_run", "refuse_key", "notes"):
        check(banned not in low, f"worker-owned term {banned!r} absent from the block")

    # nothing authored here: every line of the block comes from the frozen file
    src = B.HUMAN_ANSWERS.read_text(encoding="utf-8")
    stray = [l for l in block.splitlines() if l.strip() and l not in src]
    check(not stray, "every block line is verbatim from human_answers.md", str(stray[:2]))
    print(f"        block: {len(block)} bytes, sha256 "
          f"{hashlib.sha256(block.encode()).hexdigest()[:16]}")
    return block


def part_c(block: str) -> None:
    print("\n[C] the ablation property -- delivery is unconditional")
    tmp = Path(tempfile.mkdtemp(prefix="w1b_selftest_"))
    try:
        d = make_run(tmp)
        turns = [
            "",                                              # silent
            "Which field identifies the same record?",        # a routable question
            "Duplicate key policy: refuse_run or refuse_key?",  # W1-A would misroute
            "I have read both files and will now build it.",  # a statement
            "```json\n{\"on_duplicate_key\": \"????\"}\n```",  # unrepresentable
            "¡Qué campo identifica el mismo registro?",  # not English
        ]
        s = FakeSession(turns)
        res = B.run_one("F1", runs_dir=tmp / "runs", check_skill=False,
                        session_factory=lambda: s, block=block)
        after_first = s.sent[1:]
        check(len(after_first) >= len(turns) - 1,
              "a message was sent after every non-artifact turn",
              f"{len(after_first)} sends")
        check(all(m == block for m in after_first),
              "EVERY message after the prompt is the identical canonical block")
        check(len(set(after_first)) == 1,
              "exactly one distinct outgoing message across all worker inputs",
              f"{len(set(after_first))} distinct")
        check(s.sent[0].startswith("This is a W1-B self-test prompt"),
              "turn 1 sends the prompt text, not the block")
        digests = {e["block_sha256"] for e in s.lifecycle}
        check(len(digests) == 1 and digests.pop() ==
              hashlib.sha256(block.encode()).hexdigest(),
              "every lifecycle record carries the same block digest")
        check(res.silent_turns == 1, "the silent turn is recorded as behaviour",
              str(res.silent_turns))
        # no matcher exists to have been consulted
        for banned in ("classify_turn", "intents_in", "segment_fragments",
                       "match_message", "load_answer_table"):
            check(not hasattr(B, banned), f"harness has no {banned}()")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_def(block: str) -> None:
    print("\n[D/E/F] stop rule, continued questioning, blocking")
    tmp = Path(tempfile.mkdtemp(prefix="w1b_selftest_"))
    try:
        d = make_run(tmp, "F2")
        art = d / "work_definition.json"
        s = FakeSession(["Which field identifies the same record?",
                         "Thanks. Writing the artifact now.",
                         "this turn must never happen"],
                        artifact_path=art, artifact_at=3)
        res = B.run_one("F2", runs_dir=tmp / "runs", check_skill=False,
                        session_factory=lambda: s, block=block)
        check(res.outcome == B.COMPLETED, "artifact run reaches COMPLETED", res.reason)
        check(res.turns == 3 and art.is_file(),
              "terminates on the turn the artifact appears", f"turns={res.turns}")
        check(len(s.sent) == 3, "no further prompt after the artifact exists",
              f"{len(s.sent)} sends")
        check(res.blocks_delivered == 2, "block delivered once per applicable turn",
              str(res.blocks_delivered))

        # E: keeps asking after the block, still completes
        d3 = make_run(tmp, "F3")
        art3 = d3 / "work_definition.json"
        s3 = FakeSession(["First question?",
                          "Still asking? And another?\nAnd a third?",
                          "ok"],
                         artifact_path=art3, artifact_at=3)
        r3 = B.run_one("F3", runs_dir=tmp / "runs", check_skill=False,
                       session_factory=lambda: s3, block=block)
        check(r3.outcome == B.COMPLETED,
              "asking again after the block does NOT fail the run", r3.reason)
        # turn 2 carries two question-bearing LINES; count_interrogatives is
        # line-based, so 2 is the correct count, not 3 question marks.
        check(r3.questions_after_block == 2,
              "question-bearing lines after the block are counted separately",
              str(r3.questions_after_block))

        # F: never writes an artifact
        d4 = make_run(tmp, "F1")
        s4 = FakeSession(["Question?"] * (B.MAX_TURNS + 2))
        r4 = B.run_one("F1", runs_dir=tmp / "runs", check_skill=False,
                       session_factory=lambda: s4, block=block)
        check(r4.outcome == B.CONTESTED, "never-writing run ends CONTESTED", r4.outcome)
        check("BLOCKED_WITH_COMPLETE_INFORMATION" in r4.reason,
              "and is labelled BLOCKED_WITH_COMPLETE_INFORMATION", r4.reason[:80])
        check(r4.blocks_delivered >= 1 and r4.questions_after_block > 0,
              "the block was demonstrably held while it blocked",
              f"blocks={r4.blocks_delivered} q_after={r4.questions_after_block}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("W1-B harness self-test (no Goose, no model execution)")
    block = part_ab()
    part_c(block)
    part_def(block)
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
