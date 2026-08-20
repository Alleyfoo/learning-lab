# Round 1 — Probe A VOID (client defect), Probe B valid

Preserved unaltered. Round 1 does **not** classify the pair.

## Probe A — VOID

`session/new` was rejected before any turn ran:

```text
{"error": {"code": -32602, "message": "Invalid params",
           "data": {"error": "invalid type: null..."}}}
sessionId: None    tool calls: []    permissions: []    provider traffic: none
```

Cause is a defect in **my probe client**, not in Goose and not a finding: arm A
omitted the `mcpServers` key from `session/new` entirely. The real harness always
sends the key, empty when nothing is attached — `single_block_harness.py:199`:

```python
"mcpServers": list(mcp_servers or [])
```

So arm A never reached the control condition it was supposed to establish. Its
`provider_A.jsonl` contains only `proxy_start`, which independently confirms no
session and no model turn ever happened.

**A VOID means the pair cannot be classified from round 1.** Probe B alone
cannot distinguish suppression from tool-selection behaviour — that is exactly
what the control arm exists to settle.

## Probe B — valid, and preserved as evidence

Ran normally and is consistent with round 2. Kept for completeness.

```text
session 20260820_49
turn 1 (write instruction)  43s, end_turn, no tool calls, no artifact
turn 2 (reader instruction) reader called, ALLOWED
tools offered to the model  ['authorized-reader__read_authorized_resource']
builtin write offered       False
```

## Disposition

Fix the client to always send `mcpServers`, re-freeze, and re-run **both** arms
so the pair shares one client version. Round 1 is retained; nothing here is
edited or rerun in place.
