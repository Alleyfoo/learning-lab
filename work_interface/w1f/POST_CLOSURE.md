# W1-F post-closure note — write-surface hypothesis confirmed

Additive. **No W1-F evidence is changed by this note**: `runs/`, `AUTHORITY.md`,
`RESULTS.md`, `FIDELITY.md` and `CLOSURE.md` are all untouched. W1-F is not
re-run and no artifact is repaired.

Reference: calibration `d511894`,
`work_interface/authority/tool_surface_probe/FINDINGS.md`.

## What was open

`CLOSURE.md` §2 recorded a **declared unknown**: the worker reported having no
write capability, and `write` was never attempted in any of N1/N2/N3, but ACP
exposes only tools *called* — never tools *offered* — so the evidence could not
distinguish tool suppression from tool-selection behaviour. It was labelled the
leading hypothesis, explicitly not a finding.

## What the calibration established

The paired coached probe read the `tools` array directly from the provider
request bodies, outside every W1 pack, with Goose unmodified:

```text
no MCP attached        18 tools offered, including builtin `write`
                       write invoked -> ALLOW WRITE -> work_definition.json written
reader MCP attached     1 tool offered: authorized-reader__read_authorized_resource
                       builtin `write` not offered at all
```

Attaching one MCP server does not add a tool — it **replaces the entire builtin
surface**.

## Consequence for W1-F

The previously unresolved write-surface hypothesis is **confirmed by direct
provider traffic**. W1-F's worker did not decline to use `write`; `write` was
never offered to it. The **artifact-producing layers are therefore
infrastructure-confounded**:

```text
COMPLETION / LIFECYCLE   infrastructure-confounded
STRUCTURAL               infrastructure-confounded
FIDELITY                 infrastructure-confounded
```

`CLOSURE.md` §2 already dispositioned these measurement-invalid. This note only
upgrades the stated reason from *leading hypothesis* to *confirmed cause*.

**`RESOURCE_CONSUMPTION` remains valid.** 3/3 unprompted discovery of the
authorized reader, and 3/3 consumption of all three resources, measured on a
reader the calibration independently confirms returns the frozen bytes exactly.
That finding is unaffected and still stands as W1-F's result.

Also settled in passing: W1-F's unconditional shell DENY was never load-bearing.
N3's `powershell` call carried `_meta.goose.toolCall.toolName = "powershell"`, a
name absent from every offered set (the builtin is `shell`) — the model invented
an execution route it did not have.

## Not a licence

This does not authorize editing W1-F, rerunning it, increasing N, or repairing
an artifact. The artifact-producing question moves to W1-G, which is built so
the worker's capability box contains exactly the verbs its role needs.
