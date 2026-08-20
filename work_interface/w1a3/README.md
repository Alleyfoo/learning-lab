# W1-A3 — the skill trial, run under a corrected operator protocol

W1-A2 produced 2/3 PASS but **was not executed according to its frozen interaction
protocol**. W1-A3 re-runs the same trial with the operator side fixed.

**Nothing about the stimulus changed.** Same frozen skill
(`4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55`), same frozen
fixtures, same canonical human-answer table, same validator, same grader logic.
The C prompts are byte-identical to the W1-A2 B template apart from the run
identifier, the run's own paths, and the list of forbidden sibling runs.

**W1-A2 is evidence and stays frozen.** `w1a/` and `w1a2/` are not reused, not
edited, and not re-run. B1/B2/B3 remain exactly as they are, including B2's
truncated `PROMPT.md`.

## Why W1-A3 exists

From the W1-A2 transcripts:

```text
B2   INVALID.  Goose failed to read PROMPT.md, used the `edit` tool on it as if it
     were a reader, deleted its content, stated it had done so, and overwrote the
     file with the stub "This is W1-A2 run B2." Having lost its instructions it
     opened B1's prompt to reconstruct its task -- crossing the boundary B1's own
     prompt forbids -- and later said it understood B2 "based on examining runs
     B1 and B3." Protocol-invalid; cannot score the skill.

B3   NOT PROTOCOL-PURE.  Given the path to `human_answers.md` rather than the
     matching canonical answer, so it ingested the whole answer script. Also
     edited `work_definition.json` after writing it, past the designated stop.

B1   UNKNOWN.  Needs its transcript checked for the same answer-delivery
     deviation before it can be called clean.
```

Two operator-side defects caused this, and both are closed by the protocol below:
Goose was handed **paths instead of contents**, and it was handed **the answer
key** instead of one answer at a time.

## Operator protocol — follow exactly, three times

1. **Fresh Goose session** for each run. Never reuse a session.
2. **Paste the *contents* of `runs/C<i>/PROMPT.md` into the chat.** Do not give
   Goose the filename or path of the prompt. It must never need to read it.
3. Let Goose read its own `SKILL.md` and the two fixtures from the absolute paths
   the prompt gives. That part is unchanged from W1-A2 and is the one thing W1-A2
   established works.
4. **When Goose asks a business question**, you open
   `work_interface/w1a/human_answers.md`, match the question by intent, and paste
   **only the matching canonical answer**, verbatim — e.g.
   `Yes, compare Amount numerically, within 0.01.`
5. **Never give Goose the path to `human_answers.md`**, never paste the table, and
   never paste an answer it did not ask for.
6. **The instant `work_definition.json` is written, end the session.** Do not let
   it review, re-read, or correct the artifact. Closing the session is the
   operator's act — do not rely on Goose obeying the stop instruction, because
   B3 did not.
7. Do not correct Goose, do not repair its artifact, and do not edit the skill
   between runs. **A bad run is the measurement.**

Then, once all three are done and not before:

```bash
python work_interface/w1a3/grade.py
```

## Success criterion

**3/3 PASS**, with the frozen skill hash intact in all three run dirs.

Below 3/3, preserve every output and refusal code unchanged. Do not revise the
skill on the strength of this run — W1-A2 already showed that a failed run is
more likely to be a protocol defect than a skill defect, and that question is
exactly what W1-A3 exists to separate.

## A residual risk this pack does NOT close

Step 2 removes the prompt file from Goose's reach, which is what wrecked B2. It
does **not** remove `SKILL.md`, which Goose still reads from disk with the same
file reader that failed on B2's markdown. If a C run mangles its own `SKILL.md`,
`grade.py` reports it CONTESTED via the frozen hash and the run is invalid —
detected, not silent.

Adding an explicit "never open a file with an edit or write tool" clause to the
prompt would close that too, but it would change the stimulus and break
comparability with W1-A2. It was deliberately left out. Reconsider only if a C
run is lost the same way.

## Layout

```text
w1a3/
  README.md            this file
  grade.py             read-only grader (W0D validator; never repairs an artifact)
  verify_prep.py       9 preparation checks; run before C1
  runs/C1|C2|C3/
    PROMPT.md          frozen; pasted as TEXT, never given as a path
    SKILL.md           frozen W1-A skill, byte-identical across all three
```

Fixtures and the answer table are **referenced, not copied**:
`work_interface/w1a/fixtures/` and `work_interface/w1a/human_answers.md`.

---

## Execution: the ACP harness (supersedes the manual protocol above)

The manual operator protocol is retained as the specification of intent. In
practice W1-A3 is executed by `harness/acp_harness.py`, which removes the human
operator entirely — the defect W1-A2 actually died of.

```bash
python work_interface/w1a3/harness/selftest.py          # must pass first
python work_interface/w1a3/harness/acp_harness.py --run all
python work_interface/w1a3/grade.py
```

One fresh `goose.exe acp` subprocess per run, same shared Goose/Ollama config and
`qwen3.5:9b` as the desktop sessions.

### What the harness enforces structurally

```text
prompt as TEXT          PROMPT.md is read by the harness and its contents sent via
                        session/prompt. Goose never receives the path, so B2's
                        edit-the-prompt-as-a-reader failure cannot recur.
no client fs capability initialize declares fs.readTextFile/writeTextFile = false,
                        so Goose's own `developer` extension does all file I/O --
                        the same stimulus as the desktop runs.
cwd = the run directory session/new is created with the run dir as cwd.
mode = auto             tool calls are auto-approved; no human in the loop.
turn-synchronous        the next message is sent only after the previous
                        session/prompt returns a stopReason. Steering is never used.
stop at first artifact  the artifact is checked after every tool update and at every
                        turn end. The instant it exists the session is terminated --
                        no further model turn, review, repair or edit. B3's
                        post-write self-correction cannot recur.
append-only transcript  every ACP message, in and out, lands in the run's
                        acp_transcript.jsonl as it arrives.
```

### CONTESTED conditions

A run is CONTESTED, never rescued, if any of these hold:

```text
a controlled input's sha256 changes across the run
   (PROMPT.md, SKILL.md, both fixtures, human_answers.md -- hashed before and after)
a tool call names another run directory, human_answers.md, the validator,
   the oracle cases, prior W1-A/W1-A2 outputs, or the grader results
a question does not resolve to exactly one frozen intent
the clarification turn limit or the turn timeout is reached
the agent sends a client-bound request we never offered a capability for
```

### The matcher

Closed and deterministic; no model is involved. The frozen intents are derived
mechanically from `w1a/human_answers.md`: each row's `**bold**` spans are its
discriminating term groups, and a `/` inside a span is the author's own
alternation. An intent matches only if every group is satisfied.

```text
UNIQUE_MATCH      send exactly the frozen canonical answer
NO_MATCH          stop the run as CONTESTED
MULTIPLE_MATCHES  stop the run as CONTESTED
```

Several questions in one assistant message are supported: the message is split
into question units and each is matched independently, so distinct frozen intents
are each answered with their own canonical string. Two units resolving to the
same intent is itself ambiguity and stops the run. Answers are never invented,
combined, paraphrased or supplemented — one answer is sent bare; several are sent
in the frozen numbered format, one per line, in the order asked.

The frozen skill is not modified to carry question IDs. W1-A3 still tests the
existing skill.
