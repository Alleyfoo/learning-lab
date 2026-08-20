# ACP capability-probe evidence

Raw JSON-RPC transcripts from the read-only capability probe that established the
Goose interface the W1-A3 harness is built on. Both were captured in throwaway
temporary directories; neither touched Learning Lab.

They are kept because two harness design decisions are **empirical**, not
stylistic, and would otherwise look arbitrary to the next reader.

## The interface as measured

```text
binary   F:\download\google\Goose-win32-x64\dist-windows\resources\bin\goose.exe
         bundled with the desktop app; NOT on PATH
version  goose 1.46.0, ACP protocolVersion 1
config   %APPDATA%\Block\goose\config\config.yaml -- shared with the desktop app
         active_provider: ollama, model qwen3.5:9b, OLLAMA_HOST localhost:11434
modes    auto | approve | smart_approve | chat   ("auto" auto-approves tool calls)
```

## `acp_probe_A_fs_capability_deadlock.json` — the negative result

44 messages. The client advertised
`clientCapabilities.fs = {readTextFile: true, writeTextFile: true}`.

Goose planned the write, emitted the `tool_call`, and then sent a **client-bound
request** — `fs/write_text_file` — delegating the actual write back to the client.
The probe never answered it, so the turn blocked for the full 400 s timeout and
`probe.txt` was never created.

The second `session/prompt` into the same session was then rejected outright:

```json
{"code": -32602, "message": "Invalid params",
 "data": "session already has active run `run_3ef4710d-...`; use _goose/unstable/session/steer"}
```

**Two facts, both load-bearing for the harness:**

1. Advertising `fs` capabilities moves file I/O out of Goose and into the client.
   For W1-A3 that would be fatal twice over — it changes the stimulus away from
   the desktop runs, and it would make the *harness* the thing that writes
   `work_definition.json`. Hence `fs.readTextFile/writeTextFile = false`, so
   Goose's own `developer` extension does the work.
2. One active run per session. A turn must reach `stopReason` before the next
   message is sent. This is why the harness is strictly turn-synchronous and why
   `session/steer` is never used.

## `acp_probe_B_multiturn_success.json` — the positive control

166 messages, same probe with `fs` capabilities declined.

```text
turn 1   "create probe.txt containing OK"      77 s
         tool_call todo -> completed
         tool_call write · probe.txt -> completed   (extension: developer)
         stopReason end_turn, usage 5381 tokens
         probe.txt present on disk
turn 2   "what filename did you just create?"   2 s
         "probe.txt"                            <- same session, context retained
         stopReason end_turn
```

This is the whole clarification loop the Work-interface experiment needs —
programmatic session start, tool use, turn completion, a second user message into
the same session, and a full transcript — with no human at a terminal.

## What these transcripts do NOT establish

They were run against a trivial task in a temp directory. They say nothing about
whether the frozen skill elicits a valid Work Definition; that is what W1-A3 is
for. They also predate the harness itself — the harness's own live proof is
`selftest.py` part B.
