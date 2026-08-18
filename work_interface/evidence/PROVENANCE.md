# Work-interface evidence — provenance

This directory holds frozen, byte-for-byte research evidence from the
Goose / local-model Work-agent interface experiments (W0A–W0D). Nothing here
is to be repaired in place. Corrected candidates are written elsewhere as
*new* files; the originals stay verbatim.

## W0B — `W0B_process_definition.original.json`

- **Source**: produced by a Goose session running the local Qwen model via the
  `define-lab-process` skill, originally written to
  `tmp/w0b_goose_skill/process_definition.json`.
- **sha256 (content)**: `c254b9e4c620fabac09c8b5bbd79fdd3f2329eb364f5fb33eed44a5edd6720ea`
- **Size**: 5058 bytes.
- **Status**: **negative fixture.** It must NOT pass cleanly into authoritative
  modelling. It is preserved exactly because the historical observation matters:
  a capable local Work agent produced a useful but internally imperfect proposal
  while its own self-check claimed there were no unsupported semantic assumptions.
  The validator built against it must be independent of that self-assessment.
- **Fixtures**: the two synthetic sources the artifact references are frozen
  alongside it under `W0B_fixtures/` (`supplier-statement.txt`,
  `ledger-book.txt`), so the artifact's claims about observed structure can be
  checked against the bytes that were actually present.

## Discipline

- Never edit the `.original.` files. To show a corrected candidate, write a new
  file (e.g. `W0B_process_definition.corrected.json`) and cite the original.
- Any contradiction between the artifact and the fixtures is a finding about the
  artifact, not a reason to edit the fixtures.