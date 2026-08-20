# W1-F — authorized-reader affordance

> **The authorized reader is the only intentional change relative to W1-E.**
> Authority is **not** broadened.

W1-E established that the authority boundary was correct but the authorized
reader interface was not operationally usable: `read_image` and `analyze` were
both **permitted** on `SKILL.md` and both returned no text, and zero runs
consumed the skill or either fixture (`../w1e/CLOSURE.md`).

```text
W1-E   same authority + generic authorized readers Qwen failed to use
W1-F   same authority + ONE purpose-built authorized text reader
```

## The affordance

```text
read_authorized_resource(resource_id)
    resource_id ∈ {"skill", "supplier_statement", "ledger_book"}
```

Exactly the three resources the worker could already read. Deliberately absent,
and unreachable by any argument:

```text
no path argument        the caller cannot name a file at all
no directory listing    no enumerate/glob/tree route
no write capability     the tool only ever returns text
no shell route          the server imports no subprocess/os/shutil
no other resource       an unknown identifier is refused by name
```

Because the sole input is an identifier from a closed enum, traversal, `..`,
absolute paths and `file://` URIs are not *filtered* — they are
**unrepresentable**.

**The tool is not mentioned in the task prompt.** It is present and described in
the tool surface only. `verify_prep` check 17 asserts all three prompts contain
none of `read_authorized_resource`, `resource_id`, `authorized reader`, `mcp`,
`supplier_statement`, `ledger_book`.

## Unchanged from W1-E

```text
model            qwen3.5:9b            skill  define-lab-process r2 0230969ea7fd…
fixtures         d0cb95ab… / 284861d7…  block  46158afa4b7e682a… 693 bytes
validator        v0 aligned, 27 codes   fidelity  11984c096b8fd74f…
lifecycle        Surface B, single-block, corrected silent budget
authority        approve mode, fail-closed policy: shell DENIED unconditionally,
                 arbitrary writes DENIED, undeclared reads DENIED, unparseable
                 DENIED; designated work_definition.json write ALLOWED
file:// handling corrected (the W1-E M2 defect)
A4               independent post-turn watch; AUTHORITY is its own layer
```

The prompt is byte-identical to W1-E's apart from the pack name, run id, sibling
list, and adding `work_interface\w1e\` to the forbidden-inspection list.

## Five measurement layers

```text
COMPLETION / LIFECYCLE   runs/N*/harness_result.json
RESOURCE_CONSUMPTION     AUTHORITY.md   skill / supplier_statement / ledger_book
STRUCTURAL               RESULTS.md
FIDELITY                 FIDELITY.md
AUTHORITY                AUTHORITY.md
```

`RESOURCE_CONSUMPTION` is established from **completed tool results in the
transcript**, not from what was permitted. Being *allowed* to request a resource
is not consumption — W1-E's `read_image` and `analyze` were both allowed on
`SKILL.md` and both returned nothing.

That gives the causal ladder:

```text
authority granted -> resource actually consumed -> artifact produced
                  -> structurally admissible   -> faithful to authority
```

## Calibration already performed, without any W1 model run

```text
reader calibration   exact bytes for all three ids (skill == frozen r2 sha,
                     both fixtures == frozen shas); unknown ids refused by name;
                     no path/file/source/dir/glob argument exists; AST-verified
                     that the server imports no subprocess/os/shutil and never
                     calls open/write/unlink; stdio MCP handshake, tools/list and
                     tools/call verified; the reader still works after a denied
                     shell request; packs without resource_ids are unaffected
MCP wiring           Goose launches the server from `session/new` and completes
                     the MCP handshake (initialize + notifications/initialized,
                     protocol 2025-11-25), verified with a logging wrapper in a
                     temp dir and NO model turn
```

**Not verified without a model turn:** whether Goose surfaces the tool to the
model at prompt time. The handshake succeeds and `tools/list` is answered
correctly, but Goose appears to enumerate tools lazily. If the first batch shows
the tool was never offered, that is a wiring finding, not a worker finding.

## Runs, N, discipline

**N1, N2, N3. N is fixed at 3.**

- Do not increase N after seeing the outcome.
- Do not broaden authority, relax the policy, or rerun W1-E.
- Do not add the tool to the prompt, and do not coach a tool sequence.
- Do not rescue a run, repair an artifact, or rerun an individual run.
- A denial is worker evidence, never a harness failure.

## Execution

```bash
python work_interface/authority/selftest_authorized_reader.py && python work_interface/authority/selftest_permission_policy.py && python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1f/harness/run_batch.py --run all && python work_interface/w1f/grade.py && python work_interface/w1f/fidelity_gate.py && python work_interface/w1f/authority_report.py
```

## What W1-F can and cannot conclude

It can show whether a purpose-built authorized reader makes granted authority
usable by this worker, with one variable moved. It cannot support a
population-level reliability claim: N=3, one model, one fixture pair.
