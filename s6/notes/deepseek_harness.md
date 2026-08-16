# DeepSeek Harness — concept evaluation against the S6 contract

> Research note only. S6 does **not** install, vendor, rewrite in TypeScript, or
> make a dependency of DeepSeek Harness. This file evaluates which of its
> concepts we need now, which are later, and which are not relevant — so the
> choice to keep or defer each one is explicit and on the record.

## What "DeepSeek Harness" is, for our purposes

DeepSeek's agent harness work (the durable-session / tool-scoping ideas behind
their agent runtime) is one recent example of the broader pattern of giving an
LLM agent an explicit, inspectable execution substrate: durable sessions with a
turn/step lifecycle, scoped tools with explicit contracts, a tool policy that
bounds authority, a sandbox for tool execution, structured context injection,
and higher-level orchestration primitives (jobs, plugin/profile systems, a web
UI). The pattern is not unique to DeepSeek; it is the same direction the
agent-runtime field has converged on. We evaluate it as a *source of concepts*,
not a piece of software to adopt.

The S6 contract is narrow: build the smallest explicit boundary around the
supervisor we already have, prove it preserves behaviour and authority, and
stop. So the test for each concept is: **does S6 need it to make
context/model/tools/authority explicit and reconstructable, now?**

## Concept-by-concept

### Durable sessions — NEED NOW (the part we keep)

A session is a durable, append-only record of everything that happened: context
given, model requests, model responses, tool calls, tool results, the final
output. This is exactly the S6 reconstructability invariant — "anything
model-visible must be reconstructable from the session record." We keep this
idea in its smallest form: an `EventLog` of typed, sequenced, stamped events,
and a `replay(events)` that rebuilds the per-turn message lists from the log
alone. The self-test asserts `replay(events) == model_request.messages`.

What we do **not** take from "durable sessions": persistence across processes,
session resumption, distributed session stores. Our sessions are single-run,
in-process, written to a `.jsonl` artefact. Durability-for-replay is the need;
durability-across-restarts is not.

**Verdict: NEED NOW** — but only the append-only/replayable transcript, not the
full session-lifecycle infrastructure.

### Turn / step lifecycle — NEED NOW (minimal)

A session is a sequence of turns; a turn is one model request plus the tool
steps it triggers; a turn with no tool call is the final answer. We need this
boundary to make "where did the model stop?" and "which turn produced which
tool calls?" inspectable — the S4/S5 analysis is turn-structured (calls per
turn, stop_reason). The harness models it directly: `model_request`/`model_response`
carry a `turn` index; `tool_call`/`tool_result` are grouped under a turn;
`stop_reason` is `final` (a no-tool turn) or `max_turns`.

What we do **not** take: a formal step state machine with named transitions,
retry/branch primitives, or step-level checkpointing. Our lifecycle is the
smallest one that makes the turn structure inspectable and replayable.

**Verdict: NEED NOW** — in its minimal turn-indexed form.

### Scoped tools with explicit contracts — NEED NOW

A tool has a name, a description, input/output schemas, an authority class, and
an execute. This is the S6 Tool dataclass, and it is the direct answer to the
S4/S5 `NameError` ambiguity: the `python_analysis` tool's description *states*
the fresh-namespace semantics, so "the model assumed bindings persist" is now
"the model misunderstood a stated contract" rather than "the harness never said."
The contract is also what makes tools inspectable and the policy enforceable.

**Verdict: NEED NOW** — this is the core of the boundary.

### Tool policy — NEED NOW

A declarative bound on what tools may do, checked before execution, separable
from the tool's implementation. This is the S6 `Policy(allow, never)`: a closed
authority vocabulary, validated at registration, refusing `NEVER` and unknown
classes. It is the layer that makes "harnessing must not widen power" inspectable
— the bench's restricted namespace is the *enforcement*, the policy is the
*declaration*. Without it, the authority boundary is implicit in bench's code
and invisible to a reader of the session.

**Verdict: NEED NOW** — the explicit authority bound is a stated S6 requirement.

### Sandbox — NEED NOW (already have it)

Tool execution happens in a restricted namespace: no `open`/shell/network, a
`deepcopy` of the snapshot so the original is never mutated, a bounded timeout
and call count. We already have this in `bench.py`; the harness does not
rebuild it, it wraps it behind the `analyse_copied_data` authority class. The
self-test confirms the bench still refuses `os` and `open` *behind the harness*
— i.e., wrapping did not widen the sandbox.

**Verdict: NEED NOW** — and already satisfied by reusing `bench.run` unchanged.

### Context injection — NEED NOW (as providers)

The model's context is not one magic prompt; it is assembled from named,
authority-classed, placement-tagged sources (fleet stimulus as the user
message; memory/rulebook preambles as system blocks; tool contracts and the
authority statement as system blocks). This is the S6 `ContextProvider`. It is
what makes "what did the model actually see?" reconstructable — each provider's
full text is a `context_added` event. It is also what lets existing code become
a provider rather than be rewritten (`FleetContext`/`MemoryContext`/`RulebookContext`
wrap `snapshot`/`memory`/`rulebook`).

**Verdict: NEED NOW** — in the provider form.

### Jobs — MAYBE LATER

A "job" is a higher-level orchestration unit: a named, multi-step task with its
own lifecycle, schedulable and resumable independently of a single chat
session. S6 has no use for this: every run is one session, one operator prompt,
one fleet, synchronous. Jobs become relevant if the supervisor ever needs to
run *recurring* reviews (a watch loop), *multi-fleet* sweeps, or *deferred*
follow-ups ("investigate this later"). Those are real future experiments
(variance runs, the watch loop the staircase points toward), but they are not
S6, and adding a job abstraction now would be framework-for-its-own-sake.

**Verdict: MAYBE LATER** — defer until a concrete experiment needs recurring or
multi-session orchestration.

### Plugins / profiles — MAYBE LATER

A plugin/profile system lets a harness load different tool sets and context
providers per scenario from configuration, without code changes. S6 has a
fixed, small tool set (one tool, `python_analysis`) and a fixed set of
providers, assembled in `s6/run.py` directly. There is no second configuration
surface to justify a plugin layer yet. The *seeds* of this exist in our design
— tools and contexts are already dataclasses registered with the harness, so a
profile is a future thin wrapper around "which tools/contexts to register" —
but building the wrapper now is premature. When we have distinct supervisor
configurations (e.g. a "cold review" profile vs a "with-memory-and-rulebook"
profile vs a "watch loop" profile), a profile loader earns its place.

**Verdict: MAYBE LATER** — the dataclass design leaves room; do not build the
loader until ≥2 real profiles exist.

### Web UI — NOT RELEVANT (MAYBE much later)

A web UI for inspecting sessions, stepping through turns, and viewing tool
results. For a research instrument whose artefacts are `.jsonl` session logs
and hand-judged `FINDINGS.md`, a web UI is not relevant to S6's proof. It could
become useful much later if the session record becomes a thing humans browse
regularly (e.g. an operator-facing supervisor dashboard) — but that is a
product direction, not a research one, and is far outside the staircase. The
reconstructable `.jsonl` is the substrate a future UI would render; we build
the substrate, not the UI.

**Verdict: NOT RELEVANT** to S6; MAYBE much later, only if the project turns
toward an operator-facing product.

## Summary

| concept | verdict | S6 form |
|---|---|---|
| durable sessions | **NEED NOW** | `EventLog` + `replay()` (transcript only, no cross-process persistence) |
| turn/step lifecycle | **NEED NOW** | turn-indexed events, `stop_reason` (no formal state machine) |
| scoped tools + contracts | **NEED NOW** | `Tool` dataclass; `python_analysis` declares fresh namespace |
| tool policy | **NEED NOW** | `Policy(allow, never)`; refuses `NEVER`/unknown at registration |
| sandbox | **NEED NOW** | reuse `bench.run` unchanged behind `analyse_copied_data` |
| context injection | **NEED NOW** | `ContextProvider` (placement system/user) |
| jobs | MAYBE LATER | defer until recurring/multi-session orchestration is needed |
| plugins/profiles | MAYBE LATER | dataclasses leave room; no loader until ≥2 real profiles |
| web UI | NOT RELEVANT | build the `.jsonl` substrate, not the UI |

## The one-line takeaway

DeepSeek Harness confirms the direction — make context, tools, model calls and
authority explicit and reconstructable — but S6 needs only the **transcript
layer** (durable sessions + turn lifecycle + scoped tools + policy + sandbox +
context injection). The **orchestration and product layers** (jobs, profiles,
web UI) are real concepts that belong to future experiments, not to this floor.
We keep the idea, not the system.