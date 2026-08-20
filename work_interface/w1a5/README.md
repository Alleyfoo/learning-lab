# W1-A5 — the skill trial, with two lifecycle corrections

W1-A4 ended 1/3 PASS. D3 was the first structurally valid Work Definition
produced through the automated path; D1 and D2 were lost to causes that say
nothing about `define-lab-process`. See `../w1a4/CLOSURE.md`.

**W1-A5 makes exactly two changes, both in the harness.**

```text
SKILL.md          byte-identical, 4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55
fixtures          byte-identical  d0cb95ab… / 284861d7…
human_answers.md  byte-identical  5fe99a5b…   -- no question IDs added
validator         unchanged
intent table      unchanged (same **bold**-span derivation, same term matching)
answer rendering  unchanged
```

`w1a/`, `w1a2/`, `w1a3/` and `w1a4/` are closed evidence: not reused, not
re-run, not edited. E1/E2/E3 are fresh.

## Change 1 — question presentation normalization

Presentation-only wrappers are stripped before deciding whether a fragment is
interrogative: Markdown emphasis (`*`, `_`), backticks, tildes and surrounding
whitespace. **A question ending `?**` is recognized equivalently to one ending
`?`.** A `?` followed by closing emphasis no longer swallows the next sentence
on the same line.

This is presentation only. **No synonyms, no semantic interpretation, no LLM
matcher.** The term groups, the matching rule and the canonical strings are
untouched, and normalization cannot make a statement interrogative.

D1's exact failing turn is a frozen regression fixture; its two markdown-wrapped
questions must be detected before E1–E3 may be frozen.

## Change 2 — silent-turn re-entry

When `session/prompt` reaches `stopReason` with **no artifact, zero user-visible
assistant content, and no infrastructure failure**, the state is classified
`QUIESCENT` — not immediately `CONTESTED` — and exactly this is sent into the
same session:

```text
Continue.
```

That string carries no business or task information. It is a lifecycle trigger
only, and it is not a canonical answer.

```text
at most 2 CONSECUTIVE silent continuations
the counter RESETS ONLY when the agent emits non-empty user-visible content
tool calls DO NOT reset it -- activity is not a mechanically established
    completion or dialogue advance
budget exhausted -> CONTESTED: QUIESCENT_RETRY_LIMIT
```

So a sequence of silent turns containing tool calls stays consecutive:

```text
silent + tool calls        -> Continue. #1
silent + different tools   -> Continue. #2
silent + more tools        -> CONTESTED: QUIESCENT_RETRY_LIMIT
```

Artifact existence still terminates immediately as COMPLETED, before any of this
is reached. Tool-call counts are still recorded per turn as observation, and the
record carries `streak_reset_by_tool_calls: false` so the rule is visible in the
evidence itself. `next_silent_action()` takes only the streak — there is no
parameter through which activity could reset it.

Every silent re-entry is recorded explicitly in `harness_result.json` **and** in
the ACP transcript as a `lifecycle` record, so a reader can see exactly why a
`Continue.` was sent.

D2's captured silent-turn state is a frozen regression fixture. It carries the
real recorded state — `agent_message_chunks: 0`, empty visible text, 393 thought
chunks, 4 tool calls — and **no assistant message was fabricated for it.**

## Lifecycle state machine

Evaluated after every `session/prompt` returns, in this order:

```text
1  artifact exists on disk                    -> COMPLETED, terminate at once
2  tool call touched a forbidden path         -> CONTESTED
3  client-bound request never offered         -> HARNESS_ERROR
4  no stopReason within the turn timeout      -> CONTESTED
5  session/prompt returned an error           -> HARNESS_ERROR
6  clarification turn limit reached           -> CONTESTED
7  classify_lifecycle(visible, artifact, infra):
     QUIESCENT   next_silent_action(streak)        <- streak only; tools ignored
                   CONTINUE               -> send "Continue.", streak += 1, loop
                   QUIESCENT_RETRY_LIMIT  -> CONTESTED
     DIALOGUE    classify_turn(text)               <- the ONLY streak reset
                   NO_MATCH               -> CONTESTED
                   RECOGNIZED             -> send frozen answers, reset streak
```

Step 1 is checked before everything else, so the first-artifact hard stop is
preserved exactly: no review turn, no repair, no edit.

## Outcomes and exit codes (unchanged)

```text
COMPLETED      artifact written; session terminated immediately
CONTESTED      experimental -- NO_MATCH, QUIESCENT_RETRY_LIMIT, mutated
               controlled input, forbidden path, timeout, turn limit
HARNESS_ERROR  infrastructure only

exit 0   the batch executed correctly, CONTESTED runs included
exit 1   HARNESS_ERROR only
```

A correctly executed batch therefore always reaches `grade.py`.

## Execution

```bash
python work_interface/w1a5/harness/selftest.py && python work_interface/w1a5/harness/acp_harness.py --run all && python work_interface/w1a5/grade.py
```

Success criterion: **3/3 PASS** with the frozen skill hash intact in all three
run directories.

A CONTESTED run is **not** a skill failure and must not be graded as one. Do not
repair an artifact, revise the skill, or edit a prompt. A bad run is the
measurement.

## Declared limitation (carried forward, unchanged)

Term matching is literal. A question whose wording avoids an intent's frozen
terms may be attributed to a different intent its wording does contain — "the
amount is non-numeric?" carries `amount` and reads as the Amount-comparison
intent. Every emitted string is still an exact frozen answer to an intent the
turn genuinely raised; the mis-read intent simply goes unanswered. Recorded
rather than patched, because a hand-written synonym list would put
un-preregistered interpretation into the matcher.
