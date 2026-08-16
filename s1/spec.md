# S1 — "What's worth telling me?"

> **Research question.** If we give an LLM explicit read-only knowledge of the
> fleet plus a Python scratchpad, does it naturally perform useful supervision —
> and what does it choose to do?

The first question we need evidence for. The implementation is the smallest
supervisor vertical slice that can answer it: a read-only snapshot adapter, a
UI-free `review()` core, an optional restricted Python bench, and four frozen
fleet conditions. No memory, rulebook, improvement register, scheduling,
personality, or fixed output schema — those are hypotheses waiting for this
evidence.

## What is frozen

- **The prompt** (`s1/prompt.txt`) is deliberately broad. It does NOT name effect
  failures, healthy refusals, repeated confirmations, or any expected answer.
  Those live here, in the spec, never in the prompt.
- **The four conditions** (`s1/fixtures/{A,B,C,D}/`) are committed fixture fleets
  derived from the inherited fleet by `s1/build_conditions.py`, which asserts
  each fixture actually exhibits its intended condition.
- **The model** is local Ollama `glm-5.2:cloud`, the same model the operator
  console already uses. Settings: `temperature=0.2`, `max_turns=6`.

## The tool

`run_python` — a fenced ```python block executed against a `deepcopy` of the
snapshot in a restricted namespace (analysis modules + pandas; no file/shell/
network). **Python is optional and never prompted for.** Whether and why the
supervisor reaches for it is itself evidence.

## Conditions, predictions, and what we preserve

For every run we preserve: snapshot hash, prompt, model/settings, every python
call (code + stdout + error), final response, the frozen expectation below, and a
post-run assessment (filled from the evidence, not from imagination).

### S1-A — BORING

A single healthy worker (`fazerish-invoicing`): ordinary runs, no exceptions, no
refusals, no confirmations, no investigation, no inbox.

**Expectation.** A useful supervisor should not manufacture concern merely
because it was asked to review something. "Nothing needs attention" is a
legitimate answer. We do not require literal silence.

### S1-B — EFFECT FAILURE

`room-reservation`, frozen at the moment an accepted decision's committing effect
did not land (`ok=false`, `effect_applied=false`, a `PermissionError`), before the
retry. The failed item sits in the inbox exception queue. No open investigation —
an effect failure is an inbox exception awaiting retry, not a drift
investigation, so the supervisor must notice it from run outcomes and inbox
state, not from a `pending_exceptions` flag.

**Expectation.** This is operator-relevant and should be surfaced prominently —
the strongest case. We watch whether it points at the failed effect and the
queued exception specifically, rather than a generic "something is wrong."

### S1-C — NOISY BUT HEALTHY

`orders-enrichment`: four healthy runs, each refusing two rows under declared
policy (`MISSING_PRODUCT`, `NON_NUMERIC_OPERAND`). No exception, no failed
effect.

**Expectation.** The supervisor should distinguish healthy policy refusals from
system failure. We do not yet demand it ignore them entirely — maybe it correctly
thinks the volume is worth mentioning. Preserve what it does.

### S1-D — NOTHING BROKEN, SOMETHING INTERESTING

Two independent workers (`supplier-outstanding`, `training-room`), each carrying
a version-bound human confirmation about a world-fact the machinery cannot
re-prove (invoices are unpaid; there is exactly one training room). No active
exception, no failed effect, no noisy refusals.

**Expectation.** There is a plausible system-improvement observation available
(the fleet repeatedly depends on human-held facts that vanish on version change),
but nothing operationally broken. This is the first hint at whether a "Reflector"
mode emerges naturally from supervision. We do not require it; we observe.

## What we are looking for across all four

1. Does it surface B prominently and stay quiet on A? (calibration)
2. Does it distinguish healthy refusals (C) from failure (B)? (semantics)
3. Does it reach for Python at all, and what does it try to calculate? Anything
   it computes repeatedly is a candidate for a deterministic platform primitive.
4. Does any "improvement" observation emerge unprompted on D? (the Reflector
   hypothesis)

## Explicitly deferred

memory/journal · operator preference learning · rulebook · improvement register ·
scheduled wake-ups · event triggers · personality/roleplay · fixed report schema ·
self-modification · automatic actions · production-grade sandbox

The goal of this round is not a pretty supervisor UI. It is to come back with
four preserved model runs and be able to say: **here is what the LLM actually did
when given a fleet to supervise.** Then S2 is designed from its failures and
surprises, not from our imagination.