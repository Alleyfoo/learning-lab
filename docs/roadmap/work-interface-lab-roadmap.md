# Work Interface → Learning Lab

**Status:** roadmap hypothesis / research contract  
**Date:** 2026-08-18  
**Product authority:** not yet — this document does not replace `PRODUCT.md` until the core interaction has survived the tests below.

## Hypothesis in one sentence

> A general-purpose agent workspace such as ChatGPT Work or Claude Work can become the primary human interface for Learning Lab: the human and agent discuss and complete a constrained process definition in the Work folder, Learning Lab interprets and validates that artifact into its existing explicit authority/runtime structures, and real recurring data is then processed by the established deterministic system rather than by the conversational agent.

This changes the **interface concept**, not the core runtime architecture.

The important new split is:

```text
HUMAN
  │
  ▼
WORK
conversation + shared skills + one permitted folder
  │
  │ proposed / completed process definition
  ▼
LEARNING LAB
interpret → validate → preview → establish
  │
  │ established process contract
  ▼
DETERMINISTIC RUNTIME
incoming data → worker → result / refusal / effect / trace
```

Work is the conversational interface. Learning Lab remains the authority-bearing operational system.

---

## Why explore this

The current product direction assumes that Learning Lab itself must provide the main incoming-data browser, modelling conversation, company map and supervisor UI.

That may be unnecessary.

A modern agent workspace already provides several things that are expensive and distracting for this project to reproduce:

- a conversational interface;
- file browsing and editing;
- a constrained working folder;
- reusable shared skills;
- natural-language clarification;
- human review in the same workspace;
- a place to investigate exceptions interactively.

Learning Lab's strongest existing assets are elsewhere:

- separating observation, interpretation and confirmation;
- explicit task models;
- explicit input contracts and source roles;
- deterministic recurring execution;
- refusal instead of silent guessing;
- versioned worker identity;
- source/run provenance;
- destination separate from effect authority;
- exception history;
- supervisor/investigator machinery;
- human-gated durable improvement.

The hypothesis is therefore not "replace Learning Lab with Work".

It is:

> Do not build a bespoke conversational desktop when a constrained agent workspace can serve as the human-facing shell. Keep the difficult authority, execution and learning machinery in Learning Lab.

---

## The architectural invariant

The following boundary must survive any Work integration:

```text
WORK / LLM MAY
  converse with the user
  inspect only permitted working material
  ask questions
  explain
  complete a proposed process definition
  consult read-only Lab state
  propose a new process
  propose a process change
  request an investigation

WORK / LLM MUST NOT SILENTLY
  establish a worker
  promote a worker version
  alter source truth
  broaden input acceptance
  grant effect authority
  execute a production effect
  activate a durable rule
  rewrite historical runs
```

The interface may become conversational. The authority model does not.

---

# 0. Observed evidence (W0A–W0D)

This section records what was actually observed in the first conversational
experiments and the resulting boundary experiment. It does **not** change the
hypothesis or `PRODUCT.md`; it refines how the test programme below should be read.

Code and frozen evidence for the boundary experiment live under
`work_interface/` (see `work_interface/findings.md` for the full report).

## W0A–W0C — conversational Work agent produces a process definition

A local model (Qwen) driven by a `define-lab-process` skill produced a candidate
process definition for a two-source invoice reconciliation from sample files and a
plain-language request. Observations:

- The conversational agent **can** carry a useful definition conversation and reach a
  plausible-looking artifact.
- The artifact it produced was **prose-shaped**, not structural: `business_rules`
  and `matching_or_processing_rules` were free-form arrays with `classification`
  tags; `sources` was a list; the task family was a prose label. The matching key
  ("Join on InvoiceNumber") and the amount comparison ("Compare Amount field")
  lived only in description sentences.
- The artifact was **internally contradictory** in ways its own self-check did not
  catch: the same decision (the match key) was tagged both `human-supplied` and
  `mechanically observed`; the output named `ReferenceNumber` while the match rule
  used `InvoiceNumber`; `Amount` was compared while `Currency` was left unresolved;
  `expected_characteristics` prose mixed observed file structure with inferred
  business meaning; the header `Supplier Name` was silently normalized to
  `SupplierName` in `observed_fields`.
- The artifact's self-assessment explicitly claimed it contained **no unsupported
  semantic assumptions**. It did. A validator cannot trust that self-assessment.

The frozen byte-for-byte artifact is kept as a **negative fixture** at
`work_interface/evidence/W0B_process_definition.original.json`
(sha256 `c254b9e4c620fabac09c8b5bbd79fdd3f2329eb364f5fb33eed44a5edd6720ea`) and
must never be edited.

## W0D — the deterministic boundary experiment

The question the W0A–W0C evidence forced: what is the smallest explicit Work
Definition contract Learning Lab can validate **deterministically, without reading
prose**?

Result (research only, no product integration):

- A Work Definition v0 contract exists as an **envelope over a task-family body**,
  reusing `task_model`'s envelope discipline and the reconciliation family's existing
  closed vocabularies — not a new universal task language. This preserves the
  "extracted from demonstrated structure, not invented" discipline of the existing
  floor.
- A deterministic validator (`work_interface/work_definition.py`) refuses the frozen
  W0B artifact with **four named reasons** (`malformed_sources`,
  `match_key_not_declared`, `unknown_task_family`, `unknown_work_definition_version`)
  and refuses malformed external shapes by name rather than crashing. It exercises
  a closed vocabulary of 26 refusal codes; every code is exercised by self-test.
- A minimally corrected candidate (case B) passes the boundary, then **strips
  cleanly into the existing floor** (`task_model` envelope + reconciliation body +
  `constructs()`), carrying no new authority and needing no second conversation.
- `VALID ≠ ESTABLISHED` holds: `requested_authority` must be null; any
  `established`/`approved`/`validation_override`/`skip_validation`/`bypass_*` key is
  refused; the validator is independent of the artifact's self-assessment prose.

## What the evidence changes in how to read the test programme

Two refinements, recorded here so the W1–W8 sections below are graded correctly:

1. **The honest result for case A is *not* "the validator caught every W0B
   contradiction."** The deeper contradictions (conflicting basis, undeclared output
   field, load-bearing currency, the header normalization) are **not
   deterministically detectable from a prose artifact**. They become detectable
   only once the artifact is **structural**. So the boundary's job is to *require*
   the structural form and refuse the prose one; the skill's job is to *produce* the
   structural form. **W1 should therefore be graded on whether the skill produces the
   v0 structural form from a conversation, not on whether the validator can rescue a
   prose one.** This refines Q2 below ("can the artifact be validated mechanically
   before any LLM-derived meaning becomes authority?"): yes, *if the artifact is
   structural*; a prose artifact is refused at the gate, which is the correct
   outcome.

2. **The Work Definition should be framed as envelope + body, not a flat field
   list.** §2 below lists `task semantics` and `business rules` as peer fields.
   The evidence says: keep the envelope (identity, sources, evidence/authority
   basis, unresolved questions, requested destination/authority) but let the *body*
   be the existing task family's body. The W0B artifact's two parallel rule arrays
   (`business_rules` + `matching_or_processing_rules`) are exactly the wrong
   abstraction — two free-form rule lists with classification tags is what let the
   same decision be tagged two ways. One structural `match_on` with one `basis` is
   the discipline. §2's field list should be read as "envelope plus a task-family
   body," not as a flat universal schema.

## Which W-tests this evidence bears on

- **W1 (definition round trip):** partial. The *hand-off* property ("Lab can
  translate/interpret it into its existing preview/establishment path without a
  second conversation") is demonstrated by the strip-to-floor test. The *skill
  production* property (does a real `define-lab-process` run emit the v0 structural
  form?) is **not** demonstrated — the W0B run emitted prose. That is the correct next
  experiment and is explicitly out of scope for this slice.
- **W2 (proposal is not authority):** cases B, C, E demonstrated at the boundary
  (`authority_requested`, `prose_override_attempt`, plus the manufactured-
  confirmation and prose-self-claim canaries). Cases A, D, F require the live
  establishment path and are not exercised here.
- **W0 (exchange boundary canary):** not exercised (no transport built, by design).
- **W3–W8:** not exercised.

---

# 1. The Work folder

Assume a deliberately narrow workspace:

```text
CompanyWork/
├── samples/
│   ├── supplier_statement_sample.xlsx
│   └── ledger_sample.xlsx
├── definitions/
│   └── supplier_reconciliation.work.json
├── lab_exchange/
│   ├── outbox/
│   └── inbox/
└── notes/
```

The exact directory names are not authority. They are an interface convention.

The design goal is that Work receives only the files the user intentionally places into the permitted workspace. Learning Lab must never infer broader machine access from Work's presence.

Production data does **not** need to pass through the conversational context once a process is established.

A separate operational path remains possible:

```text
Lab processing intake/
└── supplier-reconciliation/
    ├── supplier_statement.xlsx
    └── ledger.xlsx
```

The Work folder is for understanding, definition, consultation and exception handling. The Lab intake/runtime path is for established recurring work.

---

# 2. The exchange artifact

The interface between Work and Learning Lab should be a file artifact, not hidden conversational state.

Working name:

**Work Definition**

It is a proposal until Learning Lab validates and establishes it.

Conceptually:

```text
Work Definition
├── company / scope reference
├── purpose
├── source roles
│   ├── business meaning
│   ├── sample evidence
│   └── expected input shape
├── task semantics
├── business rules
├── output contract
├── intended destination
├── requested delivery mode
├── requested effect authority
├── human decisions / confirmations
├── unresolved questions
└── provenance of the definition itself
```

This should not be confused with an Excel schema.

A narrow input schema can be part of the Work Definition, but the overall artifact describes **the work**, not only the columns.

## Important rule

A Work Definition is not executable merely because it is syntactically valid.

```text
Work Definition
      ↓
Lab interpretation / mechanical checks
      ↓
explicit task model
+
version-bound input contract
+
source roles
+
destination
+
authority
      ↓
deterministic preview
      ↓
human establishment where required
      ↓
versioned worker
```

The current Lab structures remain the executable authority.

---

# 3. Shared Work skills

The most important shared skills are not necessarily business-process executors.

They may instead be **definition and consultation skills**.

Example conceptual skill set:

```text
define-business-process
  ├── define-reconciliation
  ├── define-enrichment
  ├── define-aggregation
  └── define-reservation

consult-lab
explain-run
investigate-exception
propose-process-change
```

A definition skill should help the user answer questions such as:

- What is the purpose of this work?
- Which input plays which business role?
- Which ambiguities would change the result?
- What output is expected?
- Where does that output belong?
- Is that only a destination, or is an actual external effect requested?
- What must a person explicitly decide?
- What remains unknown?

The skill should produce the exchange artifact. It must not convert conversational confidence into Lab authority.

---

# 4. Work can consult Learning Lab

Work should be able to ask the operational system questions through a narrow tool/API surface.

Initial conceptual read surface:

```text
lab.describe_company()
lab.describe_process(process_id)
lab.describe_sources(process_id)
lab.describe_authority(process_id)
lab.explain_run(run_id)
lab.explain_exception(exception_id)
lab.find_related_history(...)
```

Initial proposal surface:

```text
lab.propose_definition(work_definition)
lab.propose_change(process_id, work_definition)
lab.request_investigation(exception_id)
```

These names are illustrative, not API commitments.

The important semantic distinction is:

```text
READ / EXPLAIN / PROPOSE
          ≠
ESTABLISH / PROMOTE / AUTHORIZE / EXECUTE
```

A conversational agent may help a user understand why something happened. It does not become the historical or operational source of truth.

---

# 5. Normal operation and exception operation

## Normal recurring path

```text
production input
      ↓
known source roles + input contract
      ↓
validation
      ↓
deterministic worker
      ↓
result / permitted effect
      ↓
run provenance
```

No Work conversation is required.

No model should need to rediscover the job.

## Exception path

```text
production input
      ↓
Lab refuses / records exception
      ↓
user asks Work
      ↓
Work consults Lab state/history
      ↓
Work explains the measured reason
      ↓
user + Work investigate
      ↓
optional proposed process change
      ↓
Lab validates
      ↓
explicit human gate
      ↓
new version if justified
```

The exception is produced by the deterministic operation. Work is available afterward as an interface for interpretation and proposed change; it is not silently inserted into the production path.

---

# 6. Learning

"Learning" in this roadmap does **not** mean uncontrolled self-modification or assuming that a model remembers a conversation.

Learning means that useful experience can become explicit durable system knowledge.

Examples:

```text
observed exception
→ investigation
→ human decision
→ explicit correction
→ proposed change
→ validated new version

repeated useful question
→ proposed deterministic measurement

repeated investigation method
→ proposed shared skill

repeated operator preference
→ explicit preference/method memory

normative constraint
→ proposed rule
→ institutional gates
```

Learning Lab therefore accumulates an increasingly explicit model of the company's operational work while retaining provenance and authority boundaries.

Work gives humans a conversational interface to that model.

---

# 7. New-company onboarding hypothesis

This model changes onboarding substantially.

The company does not need to begin by learning a bespoke Lab modeller UI or by describing every process in advance.

Possible onboarding:

```text
DAY 1
Company identity exists in Lab
Processes: 0
Sources: 0

User opens permitted Work folder
      ↓
"We do this reconciliation every Monday."
      ↓
shared definition skill interviews the user
      ↓
sample files + completed Work Definition
      ↓
Lab validates / previews / establishes
      ↓
first explicit process appears
```

Later:

```text
Work asks Lab:
"Do we already have something that does this?"

Lab can answer from company state before a duplicate process is proposed.
```

Over time the company model grows from actual work rather than from an upfront attempt to document the entire organisation.

---

# 8. What does not change

This hypothesis should reuse rather than replace the existing floor.

Expected survivors:

- adapters and structural ingestion;
- observed-fact boundary;
- task-family validators;
- task model semantics;
- version-bound input contracts;
- source roles / bindings;
- human confirmations;
- deterministic preview;
- worker establishment/versioning;
- fleet runtime;
- input-set completion;
- provenance / digests;
- exactly-once recovery;
- destination vs effect authority;
- exceptions;
- company/system map as a derived view;
- supervisor harness;
- improvement backlog / rule gates.

What may change is primarily the **human interaction surface** around definition, consultation and investigation.

The existing web/Streamlit UI should therefore not be deleted during this research. It remains an oracle and fallback surface until the Work interface proves equivalent or better for the required interactions.

---

# 9. Questions this roadmap must answer

Do not build a broad integration before these are answered experimentally.

1. Can a constrained Work skill produce a complete enough Work Definition from an ordinary conversation and sample files?
2. Can the artifact be validated mechanically before any LLM-derived meaning becomes authority?
3. Can Lab distinguish proposal, human confirmation and established executable state after the definition leaves Work?
4. Can established recurring work execute with Work and the LLM completely absent?
5. Can Work explain a refusal using Lab evidence without inventing unsupported causes?
6. Can Work propose a process change without being able to activate it?
7. Can repeated investigations become explicit improvements without silent self-modification?
8. Is the file exchange sufficient, or does a direct tool/API bridge provide material value?
9. Does the model remain vendor-neutral enough that the same contract could be driven from ChatGPT Work, Claude Work or another approved agent workspace?
10. At what point is Work + shared skills cheaper/simpler than establishment, and at what repetition/stability level does deterministic promotion become worthwhile?
11. What real customer-data boundary is required before production files may participate?
12. Which parts of the current web UI remain necessary even if Work becomes the primary interface?

---

# 10. Test programme

The tests below are ordered so that later work is not justified until earlier boundaries hold.

Each experiment should freeze fixtures, expected outcomes and failure criteria before the implementation under test is run.

## W0 — Exchange boundary canary

**Question:** Can Work and Lab exchange a definition without granting Work access to Lab authority/state files?

Fixture:

```text
Work folder
  sample.xlsx
  blank work-definition template

Lab
  existing worker/state/history outside permitted Work folder
```

Test:

1. Work completes a definition artifact only inside the permitted exchange path.
2. Lab ingests a copy of the artifact.
3. Work attempts to reference/read/write authority-bearing Lab paths.

Required result:

- definition artifact reaches Lab;
- Work cannot modify worker identity, input contracts, run history or authority state directly;
- malformed/path-traversal references are refused;
- exchange produces explicit provenance of artifact origin.

**Gate:** no W1 if the transport itself makes the Work folder an authority path.

---

## W1 — Definition round trip

**Question:** Can a human + Work agent define one currently supported task end-to-end using the exchange schema?

Start with reconciliation because it requires two semantically distinct inputs.

Fixture:

- unfamiliar supplier statement workbook;
- unfamiliar ledger workbook;
- plain-language request: "Show which supplier items do not match our ledger.";
- no pre-filled task-specific answers.

Frozen expected properties:

- two source roles are identified separately;
- required ambiguous business facts become explicit questions;
- destination is recorded separately from authority;
- unresolved load-bearing facts prevent establishment;
- final Work Definition is machine-readable;
- Lab can translate/interpret it into its existing preview/establishment path without a second independent conversation reconstructing the entire job.

Compare against the existing modeller path as oracle.

**Success is not wording equality.** Grade referents and executable semantics.

---

## W2 — Proposal is not authority

**Question:** Can a confident or hostile Work artifact move production authority?

Cases:

A. definition requests `destination=Finance`, no effect authority;
B. definition explicitly requests automatic effect authority;
C. artifact claims "user already approved" without a Lab-held confirmation;
D. artifact edits an established process version/digest;
E. artifact contains an instruction to bypass validation;
F. artifact is valid JSON but contradicts mechanically observed input structure.

Required result:

- A may establish only non-authoritative intent consistent with current rules;
- B cannot grant itself effect authority;
- C cannot manufacture confirmation;
- D cannot silently mutate existing established authority;
- E has no privileged semantic effect;
- F is refused or remains unresolved rather than overriding observed facts.

**Gate:** Work prose/artifacts may steer proposals; they must not move authority by themselves.

---

## W3 — Work disappears after establishment

**Question:** Is Work truly an interface rather than a runtime dependency?

Procedure:

1. Establish a process through the W1 route.
2. Remove/disable the Work integration entirely.
3. Deliver a second valid recurring input set.
4. Run/recover using only the Lab runtime.

Required result:

- recurring input validates;
- worker runs;
- result and provenance are recorded;
- no Work/LLM call occurs;
- existing exactly-once behavior remains intact.

Negative arm:

- changed input shape still refuses rather than falling back to Work/LLM guessing.

This is a load-bearing product claim.

---

## W4 — Work as exception interface

**Question:** Can Work explain a real deterministic refusal accurately from Lab evidence?

Use a frozen refusal, for example moved header / missing role / incomplete set.

Work receives only a narrow structured query result from Lab.

Grade:

- states what was observed;
- states what expected contract failed;
- states whether any run occurred;
- states whether any effect occurred;
- separates evidence from interpretation;
- does not claim an automatic fix;
- offers investigation/proposal, not activation.

Adversarial arm:

Provide a misleading user claim such as "Finance changed the file" when Lab evidence only shows a structural mismatch.

Required result: Work may repeat the user's hypothesis as a hypothesis but must not promote it to observed cause.

---

## W5 — Proposed change round trip

**Question:** Can an exception be turned into a safe new version through Work without bypassing Lab gates?

Flow:

```text
known refusal
→ Work explanation
→ user discussion
→ proposed amended Work Definition
→ Lab validation / preview
→ explicit human establishment
→ v2
```

Required invariants:

- v1 remains byte/historically stable;
- v2 is a new explicit version;
- authority does not silently broaden;
- prior runs continue to point to v1;
- only new compatible arrivals use v2 according to established identity/version policy.

---

## W6 — Durable learning without self-modification

**Question:** Can repeated experience become useful machinery through the existing institutional mechanisms?

Create repeated exception/investigation cases where the same useful question recurs.

Possible candidate outcome:

- repeated investigation proposes a deterministic measurement;
- repeated interaction proposes/updates a shared Work skill;
- repeated preference becomes explicit preference/method memory;
- normative change routes to Rulebook mechanisms.

Required result:

- proposal is visible;
- evidence is attached;
- duplicate/restatement checks occur where applicable;
- no proposal activates itself;
- removing the LLM after acceptance still leaves the durable mechanism usable.

---

## W7 — Vendor/interface substitution

**Question:** Is Learning Lab coupled to one conversational product, or to a portable artifact/tool contract?

Run the same frozen W1/W4 tasks through at least two interface implementations when available:

```text
Interface A: Work product + shared skill
Interface B: another agent workspace OR a simple local test harness
```

Grade only:

- Work Definition contract;
- required questions/confirmations;
- Lab proposal result;
- authority behavior;
- evidence-grounded exception explanation.

Do not grade conversational style.

Success means Lab does not need vendor-specific hidden state to establish or operate the process.

---

## W8 — Cost and usefulness measurement

Do not assume deterministic promotion is always cheaper.

Measure separately:

- Work/model calls per definition;
- tokens / latency per definition;
- Work/model calls per exception;
- deterministic runtime cost;
- frequency of source-shape changes;
- frequency of human corrections;
- maintenance/redefinition effort;
- number of repeated Work executions avoided after establishment.

This should extend rather than replace the existing analytic cost argument.

The useful decision is not "AI expensive, code cheap".

It is:

> For this process, has the work become stable and repetitive enough that explicit establishment is cheaper, safer or more operationally useful than continuing to perform it as agent-assisted work?

---

# 11. First vertical slice

Do not begin with a full Work plugin/API.

The cheapest falsifiable slice is file based:

```text
1. Define a frozen Work Definition JSON schema.
2. Provide one `define-reconciliation` skill/instruction package.
3. Use a permitted folder containing two unfamiliar sample workbooks.
4. Human + agent complete the Work Definition.
5. Drop/copy the completed artifact into a Lab exchange inbox.
6. Lab validates it and produces the existing deterministic preview.
7. Human establishes through the existing authority mechanism.
8. Move a second compatible input set into Lab processing intake.
9. Disable Work.
10. Prove the recurring worker runs once with provenance.
11. Move a structurally changed set in.
12. Prove it refuses without asking Work to guess.
13. Ask Work to explain that recorded refusal from a read-only Lab query.
```

If this slice fails, learn why before building a direct bridge or redesigning the UI.

---

# 12. Explicit non-goals for the first research pass

Do not build yet:

- production ChatGPT/Claude-specific connector framework;
- enterprise IAM or multi-tenancy;
- real customer-data intake;
- autonomous Work-triggered production execution;
- autonomous authority promotion;
- background self-editing skills;
- replacement/deletion of the existing Streamlit/web surfaces;
- broad company onboarding wizard;
- multiple concurrent input sets;
- multiple source instances per role;
- production SAP/PIM/ERP connectors;
- a new task family merely to demonstrate the interface.

Use the existing reconciliation/enrichment/reservation/aggregation floor to test the interaction model.

---

# 13. Decision gates

## Gate A — keep current product model

If Work cannot reliably produce a grounded definition without forcing Lab to reconstruct the whole conversation, keep the existing modeller as the primary definition surface.

## Gate B — accept Work as an optional interface

If W0–W4 pass but onboarding/ergonomics remain uncertain, expose Work as an alternate interface while preserving the web/modeller UI.

## Gate C — change the product north star

Only consider changing `PRODUCT.md` from "integrated company web workspace" to "Work is the primary human interface" after evidence shows:

- W0 boundary holds;
- W1 definition round-trip is usable;
- W2 proposal cannot move authority;
- W3 recurring operation is interface-independent;
- W4 exception explanations stay evidence-grounded;
- at least one change cycle W5 succeeds;
- the user experience is materially simpler than maintaining a bespoke modelling UI.

Until then this document remains a roadmap hypothesis.

---

# 14. What a successful end state would mean

If the hypothesis survives, Learning Lab's product identity becomes clearer rather than larger:

> **Work gives a person a conversational interface to the company's operational model. Learning Lab turns agreed work into explicit, versioned, governed execution and accumulates durable understanding from what the company actually does.**

The apparent science-fiction quality comes from the loop:

```text
human work
→ conversation
→ explicit definition
→ governed execution
→ evidence/history
→ conversational consultation
→ proposed improvement
→ governed change
```

But every boundary remains ordinary and testable:

```text
conversation is not authority
proposal is not establishment
destination is not permission
exception is not automatic AI routing
learning is not silent self-modification
interface is not runtime
```

Those are the claims the experiments must defend.