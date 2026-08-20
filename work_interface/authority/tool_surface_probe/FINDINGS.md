# Paired tool-surface calibration — `MCP_ATTACHMENT_SUPPRESSES_BUILTIN_TOOLS`

Executed from the probe frozen at `dfa0929`, in temp directories outside every
W1 pack. **W1-F was not modified, not re-run, and not read for anything but the
frozen inputs it shares.** Round 1's void arm is preserved under `round1_void/`.

## Classification

```text
A write succeeds  AND  B cannot invoke builtin write
    -> MCP attachment changes/suppresses the builtin tool surface.
       W1-F's artifact-producing layers are INFRASTRUCTURE-CONFOUNDED.
```

This is the pre-registered branch from `PROBE_SPEC.md`, reached on direct
evidence of the offered tool set — not inferred from a missing call.

## The measurement

| | Probe A (no MCP) | Probe B (reader MCP) |
|---|---|---|
| tools **offered to the model** | **18** | **1** |
| builtin `write` offered | **yes** | **no** |
| `write` invoked | yes | impossible |
| write reached the policy | **ALLOW WRITE** | never arrived |
| `work_definition.json` | **created, bytes `{}`** | absent |
| model claims no write tool | none | **yes** |

Same binary, model, client capabilities, `approve` mode and fail-closed policy.
The single differing input was `session/new`'s `mcpServers`.

Arm A's offered set, verbatim from the provider request:

```text
analyze, apps__create_app, apps__delete_app, apps__iterate_app,
apps__list_apps, delegate, edit, extensionmanager__list_resources,
extensionmanager__manage_extensions, extensionmanager__read_resource,
extensionmanager__search_available_extensions, load, load_skill, read_image,
shell, todo__todo_write, tree, write
```

Arm B's offered set, same instruction, same turn position:

```text
authorized-reader__read_authorized_resource
```

Attaching one MCP server did not *add* a tool. It **replaced the entire builtin
surface** — all 18 tools, including `write`, `edit` and `shell` — with only the
attached server's tool.

Arm A wrote the file on the first attempt:

```text
tool call   write · work_definition.json
permission  ALLOW WRITE — structured write of the designated artifact
result      work_definition.json exists, contents {}
```

Arm B could not, and said so — reproducing W1-F's language:

> I apologize, but I don't have access to a file-writing tool in my current
> function set.

## Both surfaces coexist — the reader is not the problem

Arm B turn 2, same session, after the write turn: the reader was called three
times, every call ALLOWED, every payload verifying against frozen bytes.

```text
skill               11979 chars   sha256 0230969ea7fd00ed…   == frozen r2
supplier_statement    541 chars   sha256 d0cb95ab5755bef3…   == frozen fixture
ledger_book           753 chars   sha256 284861d7d948dd6f…   == frozen fixture
```

The reader works perfectly. It is the *presence of an attached MCP server* that
removes the builtins, not any defect in the reader.

## Provider capture — how the offered set was obtained

ACP reports only tools *called*, never tools *offered*, so absence of a call was
never treated as absence of a tool. `ollama_tee.py` is a transparent forwarding
proxy; **Goose was not modified**, only its configured `OLLAMA_HOST` redirected,
with every byte relayed verbatim to Ollama at `127.0.0.1:11434`. The `tools`
array was read from the actual `/v1/chat/completions` request bodies.

## Resolving the W1-F N3 anomaly

W1-F N3 made a `powershell` call, which looked inconsistent with a one-tool
surface. It is not. Goose recorded:

```text
_meta.goose.toolCall.toolName = "powershell"
```

`powershell` appears in **neither** arm's offered set — arm A's builtin is named
`shell`. N3 called a tool that did not exist in any configuration. That is a
model inventing an execution route it had been left without, and it strengthens
rather than weakens the finding. It also means W1-F's unconditional shell DENY
was never load-bearing: no shell tool was ever on offer to deny.

## What this settles, and what it does not

**Settles** the declared unknown in `w1f/CLOSURE.md` §2. The leading hypothesis
is now confirmed by direct evidence: W1-F's worker did not decline to use
`write` — `write` was never offered to it. W1-F's 0/3 artifact result is
infrastructure-confounded and carries no information about tool-selection
behaviour, and none about `define-lab-process`.

**Does not settle:**

- Why Goose replaces rather than merges the surfaces, or whether a setting
  changes it. Not investigated — that is an implementation question, and no
  change was made to Goose.
- Whether this holds beyond this Goose build, this ACP path, and `qwen3.5:9b`.
- Anything about reliability. **N=1 per arm.** This is a capability
  calibration: it establishes what was *possible*, not what happens *usually*.

## Consequences

W1-F's `RESOURCE_CONSUMPTION` layer is **unaffected and still stands** — 3/3
unprompted discovery, the finding that closed the W1-E interface gap. It was
measured on the reader, which this calibration shows working exactly as frozen.

W1-F's COMPLETION / STRUCTURAL / FIDELITY layers were already dispositioned
measurement-invalid in `w1f/CLOSURE.md` §2. This upgrades the reason for that
disposition from *leading hypothesis* to *confirmed cause*. **W1-F is left
exactly as it is** — not edited, not re-run, not repaired.

Any future pack that needs both an authorized reader and artifact production
must first solve the coexistence problem, because in this configuration
attaching the reader removes the write route. That is a W1-G design input, not
a licence to alter W1-F.
