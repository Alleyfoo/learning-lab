# S6 — Supervisor Harness Floor (frozen spec)

> **Research question.** Can the existing supervisor run behind a small explicit
> *harness contract* while preserving its demonstrated behaviour and authority
> boundaries?

S6 is a **refactor/proof round, not a new intelligence experiment.** S1–S5 ran
the supervisor through `core.review` — a home-grown agent loop that mixes prompt
assembly, model calls, tool dispatch and recording into one function. That was
fine for discovering what the supervisor can do, but every future result is now
partly a statement about the quirks of that loop (S4 and S5 both hit the same
fresh-Python-namespace `NameError`, and it was impossible to say whether that
was "the model misunderstood the tool" or "the harness never stated the tool's
semantics," because there was no explicit tool contract to point at).

S6 builds the smallest explicit **SupervisorHarness** boundary around what
already exists, then proves it does not change the supervisor's demonstrated
behaviour or widen its authority. It is the floor that lets the staircase
(S1 notice / S2 learn / S3 reason / S4 invent / S5 transfer) continue without
every future result being partly about the home-grown loop.

## What is built (and what is not)

A new module `supervisor/harness.py`:

- **Tool contract** — `Tool(name, description, input_schema, output_schema,
  authority_class, execute)`. Each tool is an explicit, inspectable contract,
  not an implicit convention. The built-in `python_analysis` tool wraps
  `bench.run`; its `description` **declares the fresh-namespace semantics up
  front** ("each call runs in a fresh namespace; bindings do not persist;
  re-bind what you need on every call"). The bench is **NOT** turned into a
  persistent kernel to eliminate the S4/S5 `NameError` — that would hide a real
  tool-semantics question. With the contract declared, a future `NameError` is
  "the model misunderstood a stated contract," separable from "the harness
  failed to state it."
- **Context providers** — `ContextProvider(name, authority_class, placement,
  provide)`. Existing code becomes providers, it is not rewritten:
  `snapshot.py`→`FleetContext` (the fleet as the primary user stimulus),
  `memory.py`→`MemoryContext` (knowledge/preferences/methods preamble, reusing
  `core._memory_preamble`), `rulebook.py`→`RulebookContext` (rules/improvement
  register preamble). `placement` is `"system"` or `"user"`.
- **Tool policy** — `Policy(allow, never)`. A closed vocabulary of authority
  classes. Every tool and context provider's `authority_class` is checked at
  registration; a `NEVER` class is refused, an unknown class is refused.
- **Append-only session record** — `EventLog` emitting `session_started`,
  `context_added`, `tools_declared`, `authority_declared`, `model_request`,
  `model_response`, `tool_call`, `tool_result`, `supervisor_output`,
  `session_finished`. Each event is stamped and sequenced.
- **SupervisorHarness.run(operator_prompt, *, max_turns)** — assembles the
  system message (operator prompt + system-placement context + tool contracts +
  authority statement) and the user message (fleet stimulus), then runs the
  model loop: a turn is a `model_request` → `model_response` → 0..N
  `tool_call`/`tool_result`; a turn with no ```python block is the final
  `supervisor_output` and ends the session. **Reuses `core._chat`** for the
  model round-trip and `bench.run` (via the tool) for analysis.

`core.review` is **untouched and remains the S1–S5 path.** The harness is a
parallel path through the same primitives. S1–S5 code is not rewritten around
the abstraction.

## The reconstructability invariant (the one DeepSeek-Harness idea we keep)

> **Anything model-visible must be reconstructable from the session record.**

Every context body, tool contract, authority statement, model request, model
response, tool call and tool result is an event. A `replay(events)` rebuilds
the exact per-turn message lists from events alone. The harness self-test
asserts `replay(events) == model_request.messages` — the session record is a
sufficient description of everything the model saw. We do **not** copy
DeepSeek's whole event system; we keep the one idea that matters for a research
instrument.

## Authority — preserve the floor, do not widen it

```
ALLOW  read_fleet, analyse_copied_data, read_memory, read_rulebook,
       write_session_log, write_improvement_proposals
NEVER   modify_workers, modify_models, promote_versions, execute_runtime,
        apply_effects, alter_customer_data, filesystem_unrestricted,
        shell, network
```

Harnessing the supervisor must not accidentally give it more power. The policy
refuses any tool/context whose authority class is `NEVER` or unknown. The
bench's restricted namespace (no `open`/shell/network; `deepcopy` of the
snapshot so the original is never mutated) is the enforcement behind
`analyse_copied_data`; the policy is the declarative layer that makes the bound
inspectable.

## Regression proof — frozen S4 through the harness

Run the frozen S4 fleet through the new harness and compare against the old S4
run (`s4/results/run.json`, run_id `20260816T182432Z`):

- **same stimulus:** rebuild the S4 fleet (deterministic) and assert the
  snapshot hash matches the oracle stamp `a38f6a5a1382ab03`.
- **same model/settings:** `glm-5.2:cloud`, `temperature=0.2`, `num_ctx=131072`,
  `max_turns=10`.
- **same broad S1 prompt** (`s1/prompt.txt`, unchanged), verbatim, as the
  operator prompt. The prompt must not encode expected answers.
- **no memory, no rulebook:** `contexts=[FleetContext(snap)]` only — no
  `MemoryContext`, no `RulebookContext`. This is the cold S4 condition.
- **same oracle** (`s4/oracle.json`) and the same `assess()` / `SIGNAL_TERMS`
  from `s4/run.py`, reused by import.
- **compare old vs harnessed S4 on:** tool use (python_used, call count),
  model turns, errors/recovery, the L1/L2/C1/C2/C3/C5/C6 scan verdicts, final
  supervisory usefulness, complete session reconstructability, authority
  boundary.
- **exact prose and exact tool calls need not match.** The harness rewrites the
  system message from contracts (not `core.py`'s prose), so the model sees a
  differently-worded but equivalent prompt. We compare *behaviour and
  usefulness*, not token-for-token reproduction.
- **preserve new misses and surprises.** If the harnessed run misses a signal
  the old run hit (or vice versa), that is recorded honestly, not hidden. The
  point is that the harness preserves the supervisor's *demonstrated
  capability*, not that it reproduces a specific transcript.

## Self-test (no model call)

`python supervisor/harness.py --self-test` must pass before any model run. It
asserts, without calling the model:

1. the policy refuses a `NEVER`-authority tool at registration (canary: a
   `apply_effects` tool is rejected);
2. the policy refuses an unknown-authority tool;
3. the `python_analysis` tool contract declares the fresh-namespace semantics
   and runs `bench.run` against the snapshot;
4. a stub-model session runs through the boundary (compute turn → answer turn),
   with the expected event types in the append-only log;
5. **RECONSTRUCTABILITY CANARY:** `replay(events) == model_request.messages`;
6. behind the harness, the bench still refuses `os` and `open` (authority not
   widened);
7. `core.review` is still importable (the S1–S5 path is intact).

## Success criteria (the stop condition)

S6 passes when **all** hold:

1. supervisor execution goes through one clear harness boundary
   (`SupervisorHarness.run`);
2. context, model calls and tools produce a reconstructable append-only session
   record (canary 5 above);
3. authority is explicitly bounded and the policy refuses `NEVER`/unknown
   classes (canaries 1–2, 6);
4. frozen S4 still demonstrates useful large-fleet supervision through the
   harness (the regression comparison — same hash, same model, same prompt,
   same oracle; usefulness preserved, misses preserved);
5. existing S1–S5 behaviour/code remains available rather than rewritten around
   the abstraction (`core.review` intact, providers wrap existing modules).

**Then stop.** No new intelligence claim, no S5 variance, no C3 method, no
memory extension, no rule promotion, no DeepSeek dependency.

## What this round does NOT do

- No new model, no new seed. GLM-5.2:cloud only (standing constraint).
- No S5 variance, no C3 cohort-rigor method, no method promotion into
  deterministic machinery, no memory extension (all deferred, per the user's
  S6 memo).
- No DeepSeek installation, vendoring, TypeScript rewrite, or dependency. The
  DeepSeek-Harness concepts are evaluated in a research note
  (`s6/notes/deepseek_harness.md`) only.
- No rewrite of S1–S5 code around the abstraction. `core.review` stays.
- No framework for its own sake. The harness is the smallest boundary that
  makes context/model/tools/authority explicit and reconstructable.