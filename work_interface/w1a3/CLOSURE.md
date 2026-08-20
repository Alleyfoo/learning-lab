# W1-A3 — closed. The result says nothing about `define-lab-process`.

**Harness: 3/3 CONTESTED. Grader: 0/3 PASS, three NO_ARTIFACT.**

> **This result is NOT attributable to the `define-lab-process` skill.**
> All three runs were terminated by the harness dialogue matcher on turn 1,
> **before a single frozen canonical answer was ever supplied.** The skill was
> never given the inputs it needs to be judged on. W1-A3 measured the harness.

## What actually happened

Each run reached exactly one completed assistant turn. In every case Goose read
both fixtures, reported the observed headers, and asked its load-bearing business
questions — including the match-key question, which the matcher **did** resolve
cleanly to frozen intent 0. The run was then killed anyway, because the matcher
required *every* punctuation-delimited fragment in the turn to resolve uniquely,
and each turn also carried a trailing conversational alternative:

```text
C1  "Should we match records by `InvoiceNumber` (identical string in both files)?"
                                                        -> UNIQUE_MATCH intent 0
    "Any other field is a better candidate?"            -> NO_MATCH -> run killed

C2  "Which field(s) identify the *same record* in both files?"
                                                        -> UNIQUE_MATCH intent 0
    "Or something else you observe?"                    -> NO_MATCH -> run killed

C3  "Should I use `InvoiceNumber` as the matching key?"  -> UNIQUE_MATCH intent 0
    "Or do you want to match on `Date + InvoiceNumber` combination?"
                                                        -> UNIQUE_MATCH intent 0
    "The ledger also has a unique `ReferenceNumber` — …" -> NO_MATCH -> run killed
```

The defect is the matcher's **shape**, not its strictness. A conversational
"or…?" appended to a correctly recognised question is normal dialogue, not
ambiguity, and treating each fragment as an independent verdict unit made the
turn-level result hostage to the least structured clause in it.

## What W1-A3 does and does not establish

**Establishes:**

- The ACP harness drives Goose without a human operator. Sessions started, the
  prompt was delivered as text, `developer`-extension tool calls ran, transcripts
  were captured, and every run terminated deterministically.
- Controlled-input integrity held perfectly: **15/15 hashes verified against the
  committed preregistered blobs**, `before == after` in all three runs. No
  forbidden path was touched in any run.
- No run was rescued, rerun or repaired, and no artifact was hand-written.

**Establishes nothing about:**

- whether the frozen skill elicits a valid Work Definition — the trial never got
  past the first clarification;
- whether the whitespace ambiguity from W1-A2 recurs;
- any property of the validator.

## Two harness defects recorded, both fixed in W1-A4

1. **Fragment-level verdicts** (the cause above).
2. **Exit code conflated experiment with infrastructure.** The harness returned 1
   for a batch of CONTESTED runs, so the preregistered `&&` chain short-circuited
   and `grade.py` never ran; it had to be invoked separately afterwards. CONTESTED
   is an experimental outcome, not a process failure.

A third, smaller one: C3's stored `reason` was truncated at 400 characters by the
harness's own display limit, so machine evidence lost information that survived
only in the transcript.

## Frozen

`w1a3/` is closed evidence and is not reused. The three first-turn messages are
copied verbatim into `w1a4/harness/fixtures/regression/` as post-W1-A3 regression
fixtures — real captured output, not invented examples — and the W1-A4 self-test
requires all three to resolve mechanically, including intent 0, before W1-A4 may
be frozen.

`SKILL.md`, the fixtures and `human_answers.md` are unchanged and carry no
question IDs. W1-A4 corrects the harness only.
