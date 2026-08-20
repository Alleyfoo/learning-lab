# MCP model-wiring probe — `MCP_MODEL_WIRING_CONFIRMED`

One isolated coached probe, in a temporary directory outside every W1 pack.
**W1-F was not modified before or after** — its tree hashes identically
(`5d85d953e1ed564a`) either side of the probe, and `git status` over `w1f/` shows
no tracked change. N1/N2/N3 were not executed.

## Scope

**Availability and invocability only.** The instruction named the tool
explicitly, so this says **nothing about discoverability** — which is precisely
what W1-F measures.

## Configuration

Identical to W1-F: `goose acp`, shared Goose/Ollama config, `qwen3.5:9b`, session
mode `approve`, no client filesystem capability, the fail-closed policy with
`resource_ids`, and the authorized-reader MCP server attached via
`session/new`.

The server process was `mcp_tee.py`, which **delegates every message to the
frozen `authorized_reader.handle()`** and adds logging only, so the wire
behaviour is the frozen module's. That is how the MCP-side call log below was
captured; the real reader is never given a write capability. Frozen reader
sha256 `545f1bb94825f623…`, unchanged.

Coached instruction, verbatim:

```text
Call read_authorized_resource with resource_id "skill" and report whether the
call succeeded. Do not use any other tool.
```

## Result

```text
turn returned in 25s, stopReason end_turn
permission decisions: 1
tool calls made:      1
run dir afterwards:   ['SKILL.md']
```

## Criteria, all met

```text
PASS  Goose requested tools/list from the MCP server
PASS  exposed exactly ['read_authorized_resource']
PASS  the model issued that tool call
PASS  MCP received exactly one tools/call
PASS  arguments were exactly {"resource_id": "skill"}
PASS  returned text hashes to the frozen r2 skill  0230969ea7fd00ed…
PASS  exactly one permission decision -- the reader, ALLOWED
PASS  no shell tool call was made
PASS  no path-based filesystem tool call was made
PASS  no experiment directory was touched (w1f tree hash unchanged)
```

The MCP-side log shows the full round trip:

```text
in   initialize (protocolVersion 2025-11-25)
out  serverInfo authorized-reader/1, capabilities {tools:{}}
in   notifications/initialized
in   tools/list
out  tools: [read_authorized_resource]
in   tools/call  arguments {"resource_id": "skill"}
out  content [<11979 chars>]        (length only; text never logged)
```

The single permission decision, from the client side:

```text
ALLOW  READ  "authorized-reader: read authorized resource"
             reason: authorized reader, resource_id='skill'
```

## Verdict

**`MCP_MODEL_WIRING_CONFIRMED`.**

Goose exposes the tool to the model, routes the call to the MCP server, and
returns the exact frozen bytes. The declared unknown in `w1f/README.md` — whether
Goose surfaces the tool at prompt time — is closed. **No change was made to
W1-F.**

## What remains open, and is W1-F's actual question

Whether the worker **finds and chooses** the tool without being told it exists.
This probe deliberately told it. A W1-F run in which the tool is never called is
therefore a **worker/discoverability** finding, not a wiring finding — that
alternative explanation is now excluded.
