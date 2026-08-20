# W1-A4 — closed as executed evidence

**Harness: 1 COMPLETED, 2 CONTESTED. Grader: 1/3 PASS.** The primary criterion
(3/3) was not met.

The batch executed correctly end to end: the self-test gated it, the harness
exited 0, and `grade.py` ran inside the preregistered chain — the W1-A3
exit-code defect is fixed and confirmed.

> **D1 and D2 are NOT attributable to `define-lab-process`.** One is a harness
> defect and one is an agent lifecycle behaviour. Neither is evidence about the
> skill.

## The three runs

### D1 — HARNESS-CONTESTED

Valid questions were present but were **not recognized as interrogative** because
their terminal `?` was wrapped in Markdown emphasis.

Turn 1 worked exactly as designed: intents `[0, 1, 2, 5]` recognized, four frozen
canonical answers delivered, three unmatched fragments recorded and left
unanswered. Turn 2 then asked two clear questions:

```text
**Q5: Should `InvoiceNumber` also appear in the report (since it's the match key), or should it be excluded?**
**Q6: Where do `Date` and `SupplierName` belong — context_fields or compare()?**
```

Both lines end with `**`, not `?`. `segment_fragments()` required a trailing `?`,
returned `[]`, and the turn scored NO_MATCH on a turn that plainly asked. The
skill produced good dialogue; the harness could not see it.

### D2 — AGENT-QUIESCENT

Goose's reasoning stated an intention to ask the human, but the **completed turn
contained zero `agent_message_chunk`**, no artifact, and therefore no actionable
question.

```text
agent_message_chunk   0        <- no user-visible content at all
agent_thought_chunk   393
tool_call             4        read SKILL.md, type both fixtures
artifact              absent
infrastructure        no failure; stopReason was reached
```

Its reasoning ends *"Let me ask the human to clarify the load-bearing
questions"* — and the turn ended without saying anything. This is an agent
behaviour, not a capture failure: no message was ever emitted to capture. The
harness had no lifecycle state for "the turn completed and the agent simply did
not speak", so it fell through to CONTESTED.

### D3 — PASS

**The first complete, structurally valid Work Definition produced through the
automated ACP dialogue path.** No human operator at any point.

```text
turns          3
match_on       InvoiceNumber <-> InvoiceNumber, basis human_confirmed
compare        Amount, "within", tolerance "0.01", basis human_confirmed
confirmations  4
authority      requested_authority null, no override keys
sha256         6e419d2d7f88…
```

Turn 1 recognized intent `[1]`; turn 2 recognized `[0, 1, 3, 4]` and delivered
four frozen answers; turn 3 wrote the artifact and the session was terminated
immediately.

## What W1-A4 established

- **The corrected turn-level matcher works.** Frozen canonical answers reached
  Goose for the first time in this experiment line. Every emitted string was
  verbatim from the frozen table; no unmatched fragment received an invented
  response; no turn was invalidated by an unmatched fragment. The W1-A3 failure
  mode did not recur in any run.
- **The full automated path can produce a valid artifact** — D3 is the existence
  proof.
- **Controlled-input integrity held**: 15/15 hashes verified against the
  committed preregistered blobs, `before == after` in all three runs, no
  forbidden path touched anywhere.

## What it did not establish

Whether the skill *reliably* elicits a valid Work Definition. One success out of
three attempts, with the other two lost to harness and lifecycle causes, does not
measure reliability.

## Two defects recorded, both addressed in W1-A5

1. **Question detection was presentation-sensitive** (D1).
2. **No lifecycle state for a silent completed turn** (D2).

`SKILL.md`, the fixtures, `human_answers.md`, the validator, the intent table and
the answer rendering are unchanged and carry no question IDs. W1-A5 changes the
harness lifecycle only.

`w1a4/` is closed evidence: not reused, not re-run, not edited. D1's exact failing
turn and D2's exact silent-turn state are carried into
`w1a5/harness/fixtures/regression/` as captured fixtures — real output, not
invented examples.
