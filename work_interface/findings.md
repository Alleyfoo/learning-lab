# Work Definition v0 — boundary experiment findings

**Status:** experiment complete (boundary demonstrated). Research output only — no
product integration. Does not change `PRODUCT.md`.
**Date:** 2026-08-18
**Scope:** W0A–W0D Goose/local-model interface evidence → the smallest explicit Work
Definition contract Learning Lab can validate deterministically without reading prose.

This document answers the eight requested outputs. It is paired with code under
`work_interface/` and frozen evidence under `work_interface/evidence/`.

---

## 1. Reuse / boundary assessment

The repo already contains the discipline this experiment needs. The right move was
to **reuse, not invent a universal schema**.

### 1.1 What directly discharges Work Definition fields

| Work Definition concern | Existing concept | Where | Reused how |
|---|---|---|---|
| envelope + closed refusal vocabulary + "refuse by name, not traceback" | `task_model` envelope | `taskmodel/task_model.py` | `Problem`/`Report` imported verbatim; `malformed_sources` pattern copied; `assert_refusal` discipline mirrored (codes are closed) |
| matching key (explicit, not prose) | `match_on.left_field/right_field` | `reconciliation/harness/reconciliation_model.py` | Work Definition body *is* the reconciliation body; the key is structural |
| compare fields (explicit, with kind + tolerance) | `compare: [{field, comparison, tolerance?}]` | reconciliation body | reused as-is |
| output semantics tied to declared comparisons | `classify` + `constructs()` referent inventory | reconciliation `constructs()` + `modeller/manifest.py:check()` | the gate enforces `classify_split_mismatch` (both directions) and `output_field_not_declared` so output refers only to declared fields |
| closed comparison/policy vocabularies | `COMPARISONS`, `NUMERIC_COMPARISONS`, `DUPLICATE_POLICIES`, `OUTPUT_ORDERS`, `NON_NUMERIC_POLICIES` | reconciliation body | imported by name so the proposal cannot drift from what the executor honours |
| observed vs human-confirmed vs proposed | `status ∈ {OBSERVED, CONFIRMED, INFERRED, UNKNOWN}` + `basis` | `inspector/observe.py`, `fleet/confirmations.py`, `modeller/pipeline.py` boundary ("the LLM structurally cannot emit OBSERVED or CONFIRMED") | generalized into the Work Definition `basis ∈ {observed, human_confirmed, proposed, unresolved}` with the same rule: executable choices require authority-bearing basis |
| unresolved load-bearing facts | `CANNOT_ESTABLISH` block + `established/ambiguous/unsupported` verdicts | `modeller/pipeline.py` | `open_questions[].load_bearing` + `load_bearing_unresolved` refusal |
| version-bound human confirmation | `confirmations.jsonl` (`status=CONFIRMED`, `basis=human_confirmation`, version-bound, never `OBSERVED`) | `fleet/confirmations.py` | `human_confirmations[]` referenced by `confirmation` refs; `confirmation_missing` when a `human_confirmed` basis has no record |
| destination ≠ effect authority | `Worker.committing` (only reservation commits) + `destination` on `worker.json` identity | `fleet/fleet.py`, `supervisor/define.py` | `requested_destination`/`requested_delivery` are intent only; `requested_authority` must be null |
| "approve is a human step; you cannot approve" | routing refusal of self-approval | `supervisor/routing.py:329` | `OVERRIDE_KEYS` scan + `prose_override_attempt` |
| malformed external producer shape must refuse not crash | `malformed_sources` (added after Experiment R) | `taskmodel/task_model.py:68-73` | same pattern; `malformed_work_definition` for non-object input |

### 1.2 What is task-specific and stays task-specific

The **body** is task-family-specific. v0 supports exactly one family —
`reconciliation` — because that is the only family with W0B evidence. The envelope
owns identity, source roles, evidence/authority basis, unresolved questions, and the
closed refusal vocabulary; the body owns `left/right/match_on/compare/classify/
output_order/on_duplicate_key/on_non_numeric` exactly as the reconciliation family
already does. This mirrors `task_model`'s discipline: the envelope is an envelope,
not a task language; `reservation`'s `rules` and `enrichment`'s `lookup` were never
unioned into one shape, and the Work Definition does not union them either. Adding
enrichment/reservation/aggregation means registering a family here and giving it a
body-structure check — it does **not** mean inventing a universal Work language.

### 1.3 What in the W0B artifact is prose that cannot safely be validated

- `sources[].expected_characteristics` — "comma-delimited text file containing
  invoice records with external supplier statement data" mixes observed structure
  with inferred business meaning. **Not mechanically separable.** The v0 contract
  drops it; `role_label` is descriptive and non-load-bearing.
- `business_rules[]` and `matching_or_processing_rules[]` — the matching key and the
  amount comparison live only in `description` sentences. **Recoverable only by
  reading prose.** Refused as `match_key_not_declared` / `compare_not_declared`.
- `output.discrepancy_report` prose — names `ReferenceNumber` in missing-record
  semantics. As prose it is not mechanically checkable; as a structural
  `output.reports_fields` list it is (`output_field_not_declared`).
- `human_confirmations[].answer_provided` prose — the answer's *meaning* is prose;
  only the existence of a confirmation record with an id is mechanical.
- `evidence_notes[].observed_content` — narrative. Dropped (the structural
  `observed_fields` cross-checked against the fixture is what is mechanical).

### 1.4 Minimal additional explicit structure that makes the W0B contradictions mechanically detectable

Each W0B contradiction maps to one structural requirement:

| W0B defect | Minimal structure that exposes it | Refusal code |
|---|---|---|
| #1 match key tagged both `human-supplied` (B2) and `mechanically observed` (M1) | one `match_on` declaration with a single scalar `basis` | `conflicting_basis` (list of distinct bases) / `basis_not_scalar` |
| #2 output names `ReferenceNumber` but the match rule uses `InvoiceNumber` | `output.reports_fields[]` + `context_fields[]`, each checked against {match key ∪ compare ∪ declared context} | `output_field_not_declared` |
| #3 `Amount` compared while `Currency` unresolved | executable `compare:Amount` requires authority basis; `open_questions[].load_bearing` that blocks it must be `resolved` | `load_bearing_unresolved` |
| #4 `expected_characteristics` mixes observed + inferred | `observed_fields[]` cross-checked against the fixture header (no prose) | `observed_field_not_in_source` (the W0B artifact normalizes "Supplier Name" → "SupplierName") |
| #5 Work artifact output vs business-process output not separated | envelope `requested_delivery` (Work artifact) distinct from `body.classify` (business output) | structural, not a refusal |
| #6 fresh session inferred "case-sensitive" | `comparison` must be a closed-vocab value (`exact` vs `casefold`), not inferred from "exactly as written" | `unknown_comparison` if absent; declared, not inferred, if present |

### 1.5 Where this boundary belongs in the current architecture

It sits **in front of** `task_model`, as a pre-envelope for proposals arriving from
outside the repo (a Work agent). The flow:

```text
Work agent (Goose/Qwen)  →  process_definition artifact (prose or v0)
   ↓
Work Definition v0 gate        ← this experiment (work_interface/work_definition.py)
   ↓ VALID (no establishment authority)
to_task_model() strips the evidence/authority envelope
   ↓
task_model.parse + validate    ← existing floor, unchanged
+ reconciliation validate_body  ← existing family validator, reused as oracle
   ↓
deterministic preview (existing builder.preview)
   ↓
human establishment (existing fleet/confirmations.establish)   ← authority still human
```

The gate adds only the evidence/authority layer `task_model` deliberately does not
own (task_model assumes the model is already authoritative). It is read-only with
respect to the existing floor: it imports `Problem`/`Report` and the reconciliation
vocabularies, and its `to_task_model()` produces a dict the existing floor accepts
unchanged. No existing file was modified.

---

## 2. Frozen W0B evidence location

- **Artifact (byte-preserved, negative fixture):**
  `work_interface/evidence/W0B_process_definition.original.json`
  - sha256 `c254b9e4c620fabac09c8b5bbd79fdd3f2329eb364f5fb33eed44a5edd6720ea`, 5058 bytes.
  - Source: `tmp/w0b_goose_skill/process_definition.json` (Qwen via `define-lab-process`).
  - **Never edited.** Corrected candidates are separate files.
- **Fixtures (frozen, so observed claims are checkable against the real bytes):**
  `work_interface/evidence/W0B_fixtures/{supplier-statement.txt,ledger-book.txt}`
- **Provenance + discipline:** `work_interface/evidence/PROVENANCE.md`

The W0B artifact is a **negative fixture by intent**: a capable local Work agent
produced a useful but internally imperfect proposal while its own self-check claimed
no unsupported semantic assumptions. The validator is independent of that
self-assessment — it ignores `requested_authority: null` and the `authority_status`
prose and verifies structurally.

---

## 3. Proposed Work Definition v0 contract

Located in `work_interface/work_definition.py`. Shape (reconciliation family):

```json
{
  "work_definition_version": 0,
  "task_family": "reconciliation",
  "model_id": "...",
  "provenance": {"producer": "...", "skill": "...", "produced_at": "..."},
  "purpose": "...",
  "sources": {
    "<role>": {
      "role_label": "...",
      "fixture": "<sample file, for observed-field cross-check>",
      "path": "<materialized json, for the stripped model>",
      "collection": "<collection key>",
      "observed_fields": ["..."],
      "basis": "observed"
    }
  },
  "body": {
    "left": "<role>", "right": "<role>",
    "match_on": {"left_field": "...", "right_field": "...",
                 "basis": "human_confirmed", "confirmation": "Q_id"},
    "compare": [{"field": "...", "comparison": "within", "tolerance": "0.01",
                 "basis": "human_confirmed", "confirmation": "Q_id"}],
    "classify": {"both_same": "...", "both_different": "...",
                 "only_left": "...", "only_right": "..."},
    "output_order": "left_then_right",
    "on_duplicate_key": "refuse_run",
    "on_non_numeric": "refuse_run"
  },
  "output": {"reports_fields": ["..."], "context_fields": ["..."]},
  "human_confirmations": [{"id": "Q_id", "question": "...", "answer": "...",
                           "basis": "human_confirmed"}],
  "open_questions": [{"id": "...", "question": "...",
                      "load_bearing": false, "status": "unresolved"}],
  "requested_destination": "review_only",
  "requested_delivery": {"format": "..."},
  "requested_authority": null
}
```

**Authority invariant.** The strongest success state is:

```text
VALID WORK DEFINITION  →  SAFE TO ENTER EXISTING MODELLING / PREVIEW PATH
```

Not `ESTABLISHED`. `requested_authority` must be null; any truthy
`established`/`approved`/`validation_override`/`skip_validation`/`bypass_*` key is
refused. A valid Work Definition strips (via `to_task_model`) to a `task_model` that
the existing floor validates — carrying no Work-Definition authority of its own.
Establishment remains the existing human-gated `fleet/confirmations.establish`.

**Evidence/authority invariant.** Each load-bearing decision carries one `basis` in
`{observed, human_confirmed, proposed, unresolved}`. Executable choices
(`match_on`, `compare`) require `observed` or `human_confirmed` — `proposed` and
`unresolved` are not authority. `human_confirmed` must point at a recorded
confirmation. `observed` source-field claims are cross-checked against the fixture
header. One decision with multiple bases is refused.

---

## 4. Deterministic validator / refusal vocabulary

Closed vocabulary of 27 codes (`WORK_DEFINITION_PROBLEM_CODES`), every one exercised
by the self-test (mirroring `task_model`'s "no declared-but-unexercised code" rule):

**Envelope / shape:** `malformed_work_definition`, `unknown_work_definition_version`,
`unknown_task_family`, `malformed_sources`.

**Sources / evidence:** `missing_source_fixture`, `observed_field_not_in_source`.

**Body structure (reconciliation, vocabulary imported):** `match_key_not_declared`,
`compare_not_declared`, `classify_split_mismatch`, `unknown_comparison`,
`comparison_tolerance_mismatch`, `malformed_tolerance`, `unknown_policy`,
`unknown_source`, `unknown_output_order`, `missing_on_non_numeric`.

**Evidence / authority:** `basis_not_known`, `basis_not_scalar`, `conflicting_basis`,
`executable_field_unresolved`, `executable_field_proposed_only`, `confirmation_missing`.

**Output / unresolved:** `output_field_not_declared`, `load_bearing_unresolved`.

**Authority invariant:** `authority_requested`, `prose_override_attempt`.

The validator **never raises** on a malformed external shape (the `task_model`
Experiment-R discipline): a non-object input, a list of source specs, a bad basis
value, etc. all return a named `Problem` so the producer (the Work agent) can be told
what was wrong. It does **not** LLM-read or regex prose for meaning.

---

## 5. Tests and their results

Two runnable suites, both green:

```
python work_interface/work_definition.py --self-test
  -> SELF-TEST PASSED (all 27 Work-Definition codes exercised ...)

python work_interface/test_work_definition.py --self-test
  -> WORK DEFINITION TESTS PASSED (14 tests)
```

### Case A — the byte-preserved W0B artifact

`work_interface/evidence/W0B_process_definition.original.json` → `validate(...)`:

```text
valid? False
codes: ['malformed_sources', 'match_key_not_declared', 'unknown_task_family', 'unknown_work_definition_version']
  - unknown_work_definition_version: None
  - unknown_task_family: 'Invoice-to-Invoice Reconciliation'; supported: ['reconciliation']
  - malformed_sources: expected an object keyed by source role, got list
  - match_key_not_declared: body missing; task semantics are not declared
```

**Result: does not pass cleanly into authoritative modelling, for concrete named
reasons.** The deeper W0B contradictions (conflicting basis, ReferenceNumber in
output, load-bearing currency, the `SupplierName` normalization) are **not** claimed
here — they are not honestly derivable from the prose shape. The validator refuses at
the structural gate (no `body`, sources as a list, prose task label). That split is
the finding the prompt asked for: *which defects are deterministically detectable*
(those, in the v0 shape) *and which still require modeller/human interpretation*
(the prose mixing of observed and inferred meaning; whether "observed" is the right
epistemic label for a given decision).

### Case B — minimally corrected candidate

`work_interface/cases/W0B_corrected.json` → `validate(...)`:

```text
valid? True   (passes Work Definition validation only; requested_authority = null)
```

**Hand-off to the existing floor** (`test_case_B_strips_into_existing_floor`):
`to_task_model(B)` → `task_model.parse` → `task_model.validate` (envelope) +
reconciliation `validate_body` (field presence, classify/compare pairing, closed
vocab) → **passes**; `constructs()` reports `match_binding`, `compare:Amount`,
`difference_classification`, `peer_presence_classification`. The corrected candidate
enters the existing modelling/preview path with no new authority and no second
conversation — the roadmap W1 property.

### Canaries (each maps to a real W0B defect or a roadmap W2 case)

| Canary | Refusal code | Source |
|---|---|---|
| same decision marked observed + human_confirmed | `conflicting_basis` | W0B #1 |
| `ReferenceNumber` named in output, not declared | `output_field_not_declared` | W0B #2 |
| classify reports differences, no compare | `compare_not_declared` | W0B #3 form |
| load-bearing currency unresolved | `load_bearing_unresolved` | W0B #3 |
| `body.left` names a role not in sources | `unknown_source` | unknown source role |
| `requested_authority = "effect"` | `authority_requested` | roadmap W2-B |
| `"established": true` | `prose_override_attempt` | roadmap W2-C |
| `"validation_override": true` | `prose_override_attempt` | roadmap W2-E |
| `match_on.basis = "proposed"` | `executable_field_proposed_only` | executable-on-non-authority |
| `match_on.basis = "unresolved"` | `executable_field_unresolved` | executable-on-unresolved |
| `basis = "guess"` | `basis_not_known` | unknown basis value |
| `human_confirmed` with no confirmation record | `confirmation_missing` | manufactured confirmation |
| `tolerance = "lots"` | `malformed_tolerance` | bad tolerance |
| `comparison = "fuzzy"` | `unknown_comparison` | unknown comparison kind |
| `on_duplicate_key = "drop"` | `unknown_policy` | unknown policy |
| missing `output_order` | `unknown_output_order` | body completeness |
| numeric compare, missing `on_non_numeric` | `missing_on_non_numeric` | body completeness |
| `on_duplicate_key`/classify split pairings | `classify_split_mismatch` | reuse reconciliation |
| malformed external shapes (string/list/int/None/`{"sources":"x"}`) | `malformed_work_definition` / `malformed_sources` | refuse not crash (task_model R) |
| prose `authority_status` self-claim on an otherwise-valid B | **passes** (prose is not authority) | W2-C negative arm |

---

## 6. What the validator deliberately does NOT attempt to decide

- **Whether a `basis` label is the right epistemic label.** "Is `observed` actually
  appropriate for the match-key *decision*?" is a judgment for the human/modeller.
  The validator only checks the label is in the closed set, is singular, and that
  executable choices carry an authority-bearing one. (W0B #4 lives here — the prose
  mixing of observed structure with inferred business meaning is not mechanically
  separable, so the contract drops the prose field rather than parse it.)
- **Whether the W0B prose's `expected_characteristics` describes the file
  correctly.** Dropped entirely; only the structural `observed_fields` cross-check
  against the fixture is mechanical.
- **The business meaning of the `purpose`/`role_label` prose.** Non-load-bearing;
  no basis required; never gates execution.
- **Whether an open question *should* be load-bearing.** The artifact declares
  `load_bearing`; the validator enforces the consequence (an unresolved
  load-bearing question blocks entry), not the classification.
- **Whether the proposed task is a good idea, correctly scoped, or the right family
  for the data.** That is the modeller/operator's job after the boundary.
- **Establishment, effect authority, version promotion, or any production
  movement.** Out of scope by design.

---

## 7. Does the experiment support continuing toward a Work/Goose interface?

**Yes — for the boundary specifically, and conditionally.**

The boundary the prompt asked for is demonstrated:

- A conversational Work agent's plausible mistakes (conflicting authority tags,
  undeclared fields in output, load-bearing unknowns treated as resolved, claimed
  self-approval, effect requests) are **proposals** at this gate, not authority.
  Each is refused with a named code; none can move production authority.
- A valid proposal strips cleanly into the existing floor with no new authority and
  no second conversation. `VALID ≠ ESTABLISHED` holds.
- The validator is independent of the agent's self-assessment (it ignores the
  `requested_authority: null` / `authority_status` prose and checks structurally),
  which was the load-bearing concern given the W0B self-check claim.

This is evidence for roadmap **W1** (definition round-trip) at the *boundary* level
and **W2** (proposal is not authority) cases B/C/E. It is **not** evidence for W0
(transport), W3 (Work disappears after establishment — not exercised), W4
(exception explanation), W5 (change round-trip), or the onboarding ergonomics.

**The condition:** the W0B evidence also shows the Work agent does not reliably
produce the structural form unaided — its artifact was prose-shaped and internally
contradictory. The boundary works *because it refuses the prose shape*. So the
remaining dependency for W1 is: can the `define-lab-process` skill (or a revised
one) reliably produce the **v0 structural form** from a conversation, rather than
the free-form prose the W0B Qwen run produced? That is a W1 skill question, not a
boundary question, and it is the correct next experiment — but it is explicitly
out of scope for this slice and not started here.

---

## 8. Findings that change the roadmap hypothesis

Three, recorded here; the roadmap document is updated separately (below).

1. **The Work Definition is an envelope over a task-family body, not a new task
   language.** Roadmap §2 sketches the Work Definition as a flat list of fields
   (purpose, source roles, task semantics, business rules, output contract, …).
   The evidence says: keep the *envelope* (identity, sources, evidence/authority
   basis, unresolved questions, requested destination/authority) but let the *body*
   be the existing task family's body. The W0B artifact's `business_rules` +
   `matching_or_processing_rules` arrays are exactly the wrong abstraction — two
   parallel rule lists with free `classification` tags is what let the same decision
   be tagged two ways. One structural `match_on` with one `basis` is the
   discipline. The roadmap's §2 field list should be reframed as envelope + body.

2. **The boundary is "refuse the prose shape," not "interpret the prose."** The
   honest result for case A is that the deeper W0B contradictions are *not*
   deterministically detectable from the prose artifact — they become detectable
   only once the artifact is structural. So the boundary's job is to **require**
   the structural form; the skill's job is to **produce** it. This refines roadmap
   Q2 ("can the artifact be validated mechanically before any LLM-derived meaning
   becomes authority?"): yes, *if the artifact is structural*; a prose artifact is
   refused at the gate, which is the correct outcome. The roadmap should state this
   precondition explicitly so W1 is graded on whether the skill produces the
   structural form, not on whether the validator can rescue a prose one.

3. **`requested_destination`/`requested_delivery` are intent; `requested_authority`
   is the authority switch.** The W0B artifact already separates `destination`
   ("Review-only output; no external write authority granted") from
   `requested_authority: null`. The v0 contract confirms this is the right split and
   makes it mechanical: destination/delivery prose is never read for authority;
   only `requested_authority` (and the closed override-key scan) is. This validates
   the existing fleet split (`Worker.committing` vs `destination` on identity) and
   is the W2-A/B discriminator.

---

## Run

```
python work_interface/work_definition.py --self-test      # 27 codes exercised
python work_interface/test_work_definition.py --self-test # A / B / canaries
```

No existing file was modified. The experiment is self-contained under
`work_interface/` and the frozen `work_interface/evidence/`.