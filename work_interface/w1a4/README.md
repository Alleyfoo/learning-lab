# W1-A4 — the skill trial, with the dialogue adapter corrected

W1-A3 ended 3/3 CONTESTED and 0/3 NO_ARTIFACT, and **that result is not
attributable to `define-lab-process`** — every run was killed by the harness
matcher on turn 1, before any frozen canonical answer was supplied. See
`../w1a3/CLOSURE.md`.

**W1-A4 changes the harness and nothing else.**

```text
SKILL.md          byte-identical, 4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55
fixtures          byte-identical  d0cb95ab… / 284861d7…
human_answers.md  byte-identical  5fe99a5b…   -- and NO question IDs were added
```

`w1a/`, `w1a2/` and `w1a3/` are closed evidence: not reused, not re-run, not
edited. D1/D2/D3 are fresh.

## Matcher contract

The matcher classifies a **completed assistant turn**, not a punctuation-delimited
fragment.

```text
produce a SET of recognized intents from the whole turn
repeated or alternative formulations of one intent collapse to that one intent
several distinct intents are allowed, answered once each, in FROZEN TABLE ORDER
unmatched conversational fragments are RECORDED, receive no invented response,
   and do NOT invalidate a turn in which at least one intent was recognized
zero recognized intents            -> CONTESTED: NO_MATCH
only exact frozen canonical answers may ever be emitted
```

Intents are still derived mechanically from `w1a/human_answers.md`: each row's
`**bold**` spans are its term groups, `/` inside a span is the author's own
alternation, and every group must be satisfied. No model is involved anywhere in
the matcher.

Fragments still exist, but only as **reporting units** — they localise which part
of a turn was recognised and which was not. They are no longer verdict units.
Only interrogative text is scanned, so narration cannot pull an answer out of the
harness for a question that was never asked.

### Response format

One answer per line, in frozen table order, each verbatim. A single answer is sent
bare. Nothing is invented, combined, paraphrased or supplemented.

## Regression fixtures

`harness/fixtures/regression/C{1,2,3}_first_turn.txt` are the **exact** first-turn
messages that killed W1-A3, captured verbatim from its transcripts. They are real
output, not invented examples, and may not be edited to make a test pass.

The self-test requires all three to be RECOGNIZED **and to include intent 0**:

```text
C1  intents [0, 1, 3, 5]   unmatched fragments 3
C2  intents [0, 1, 4, 5]   unmatched fragments 4
C3  intents [0, 1, 2, 3, 8] unmatched fragments 5
```

## Outcomes and exit codes

```text
COMPLETED      artifact written; session terminated immediately
CONTESTED      an experimental outcome -- zero recognized intents, a mutated
               controlled input, a forbidden path, a turn timeout, or the
               clarification turn limit
HARNESS_ERROR  infrastructure only -- Goose missing, ACP handshake failure,
               subprocess death, a client-bound request for a capability we never
               offered, or a run directory that was not fresh

exit 0   the batch executed correctly, CONTESTED runs included
exit 1   HARNESS_ERROR only
```

This is what guarantees a correctly executed batch always reaches `grade.py`. In
W1-A3 a contested batch returned 1, `&&` short-circuited, and the grader never ran.

## Evidence

Complete reasons and the full per-turn matcher log — recognized intents, answers
sent, unmatched fragments, every fragment's verdict, and the agent's turn text —
are written to `runs/D*/harness_result.json` **without truncation**. Truncation
happens only in the printed summary. Nothing under `w1a4/` is gitignored.

## Execution

```bash
python work_interface/w1a4/harness/selftest.py && python work_interface/w1a4/harness/acp_harness.py --run all && python work_interface/w1a4/grade.py
```

Success criterion: **3/3 PASS** with the frozen skill hash intact in all three run
directories.

A CONTESTED run is **not** a skill failure and must not be graded as one. Do not
repair an artifact, revise the skill, or edit a prompt. A bad run is the
measurement.

## Declared limitation

Term matching is literal. A question whose wording avoids an intent's frozen terms
may be attributed to a different intent that its wording does happen to contain —
for example "the amount is non-numeric?" carries the token `amount` and so is read
as the Amount-comparison intent rather than the non-numeric one. The consequence
is bounded: every emitted string is still an exact frozen canonical answer to an
intent the turn genuinely raised, and the mis-read intent simply goes unanswered
that turn. This is recorded here rather than patched with a hand-written synonym
list, which would put un-preregistered interpretation into the matcher.
