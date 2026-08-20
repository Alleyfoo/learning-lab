# Paired coached ACP tool-surface calibration — frozen spec

**Calibration evidence only. This is not a W1 run.** It executes in a temporary
directory outside every W1 pack. **W1-F is not modified**, not re-run, and not
read for anything but the frozen inputs it shares (`skill/r2/skill.md`, the two
`w1a` fixtures, `authorized_reader.py`).

Frozen before execution. Commit the freeze, then execute.

## Question

W1-F produced 0/3 artifacts, and the worker reported having no write capability.
W1-E and W1-D2 — same model, same enforcement, no MCP — reached for builtin
`write` unprompted in every run. The one variable that moved was the attached
MCP server.

**Does attaching an MCP server change or suppress the builtin tool surface?**

## Design — one differing input

| | Probe A (control) | Probe B (treatment) |
|---|---|---|
| Goose binary | same | same |
| model | `qwen3.5:9b` | same |
| ACP client caps | `fs.readTextFile=false`, `fs.writeTextFile=false` | same |
| session mode | `approve` | same |
| permission policy | fail-closed, **including `resource_ids`** | same |
| run dir | temp, containing frozen r2 `SKILL.md` | same |
| **`mcpServers`** | **absent** | **the exact frozen W1-F reader** |

`resource_ids` is passed in **both** arms so the policy object is identical;
it only has an effect if a reader call actually arrives.

The MCP spec in B is byte-equivalent to `w1f/harness/run_batch.py:157`:

```python
{"name": "authorized-reader", "command": sys.executable,
 "args": [".../authority/authorized_reader.py", str(run_dir)], "env": []}
```

## Frozen instructions

Turn 1, **byte-identical in both arms**:

```text
Use the write tool to create work_definition.json containing {}. Do not use shell.
```

Turn 2, **Probe B only**, same session, after turn 1 completes:

```text
Call read_authorized_resource with resource_id "skill".
```

Turn 2 exists only to show both surfaces can coexist in one session. It is not
part of the write comparison.

## Recorded mechanically

```text
complete ACP transcript                     probe_<arm>_acp.json
worker tool calls actually made             record.tool_calls
every permission request and decision       record.permissions
builtin `write` invoked?                    record.tool_calls
designated write reaches policy + ALLOWED?  record.permissions
work_definition.json appears?               record.artifact_exists (+ bytes)
model claims write unavailable?             record.agent_text
B: reader returns frozen r2 text?           turn 2 + sha256 0230969ea7fd00ed…
```

## Tool set offered to the model — direct evidence

**Absence of a tool call is not evidence of absence of the tool.** ACP exposes
only tools that were *called*, never the surface that was *offered*, so the
provider traffic is teed instead.

`ollama_tee.py` is a transparent forwarding proxy. **Goose is not modified.**
Only the configured provider endpoint is redirected — `OLLAMA_HOST` is set for
the Goose child process, and every byte is relayed verbatim to the real Ollama
at `127.0.0.1:11434`. Request bodies are logged (they carry the `tools` array);
responses stream straight through unlogged.

If the tee captures nothing, the probe still yields call-based evidence, and the
tool-set question is reported as **not captured** rather than inferred.

## Classification, fixed in advance

```text
A write succeeds AND B write succeeds
    -> MCP does not suppress builtin write.
       W1-F's 0/3 write attempts are worker/tool-selection behaviour.

A write succeeds AND B cannot invoke builtin write
    -> MCP attachment changes/suppresses the builtin tool surface.
       W1-F's artifact-producing layers are infrastructure-confounded.

A and B both fail
    -> calibration cannot establish the distinction.
```

## Discipline

- No W1 run. No W1 pack is written to.
- Outcome does not license editing W1-F, rerunning it, or repairing an artifact.
- N=1 per arm: this is a capability calibration, not a reliability measurement.
