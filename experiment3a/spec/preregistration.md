# Experiment 3A — GLM-5.2 Orchestrator with Narrow Subagents: Preregistration

**Frozen before any test runs.** Expected answers live in `experiment3a/expected.json`
(hidden, never shown to the orchestrator or any subagent). The Experiment 2B fixtures
are referenced by path and **not modified** — they remain frozen at their 2B commits.

## Question

> Can a stronger orchestrator (GLM-5.2) coordinate narrow specialist agents to identify a
> table header and its month columns — and, when a header cell is genuinely unresolvable,
> escalate to a human instead of silently deciding?

This is **not** a normalization experiment. No transformation code is generated. The
experiment asks only whether **manager + narrow agents + independent warrant review +
deterministic gate** is a viable source-understanding architecture.

## What this builds on

Experiment 2B isolated two facts, in opposite directions:

1. **Supported:** the model can make small semantic judgements reliably — 2B.5 was 6/6 on
   resolvable cells, including Finnish month abbreviations with no vocabulary provided.
2. **Supported:** deterministic code should own composition — it succeeded where the
   model's own aggregate construction failed twice (2B.4).
3. **Not supported, and clearly localized:** the model supplying the *escalation signal*.
   Four probe types, 325 unused escalation opportunities in 2A, and a zero-cost `unknown`
   declined in favour of an unwarranted `not_month` for `Jakso A` (2B.5).

3A keeps the supported halves and attacks the unsupported one with a new mechanism:
**an independent warrant reviewer that does not share the classifier's reasoning.** The
classifier may still over-assert (`Jakso A = not_month`); the question is whether a fresh
agent, shown only the evidence and the proposed classification, can catch that the
assertion is not warranted — and whether a deterministic gate on that check escalates
where the classifier alone did not.

## Architecture

```text
GLM-5.2 orchestrator
      ↓
HeaderLocator          -> header_row | unknown
      ↓
for each header cell:
   HeaderCellClassifier   -> month | not_month | unknown
      ↓
for each classification:
   WarrantReviewer        -> supported | insufficient_evidence   (fresh, no classifier reasoning)
      ↓
deterministic composition (code, not the LLM)
      ↓
deterministic gate (code, not overridable by the orchestrator)
      ↓
PROCEED  |  ASK_HUMAN
```

The orchestrator (GLM-5.2, the model driving this session) reads the rendered source rows
and dispatches specialists. It must not directly modify source data. No subagent writes
Python transformation code. The orchestrator does not construct the final month-column
list; deterministic code does.

## Subagent contracts

The three subagents are exposed as fresh, context-isolated agent invocations. Each
receives only what the orchestrator passes it and returns only its allowed JSON. The
contracts are enforced by the invocation prompt (the prompt text is the binding contract;
`.claude/agents/*.md` documents the same contracts for reuse).

### HeaderLocator

Input: rendered source rows.
Task: identify the row containing the actual data-table headers.
Allowed output: `{"header_row": N}` or `{"unknown": true}`. Nothing else.

### HeaderCellClassifier

Input: full header row, target column number, target cell text.
Task: classify the semantic role of the target header cell — is it a calendar month?
Allowed output: `{"classification": "month"}` | `{"classification": "not_month"}` |
`{"classification": "unknown"}`. Nothing else. The classifier sees the complete header for
context but returns a judgement for only one cell.

### WarrantReviewer

A **fresh** subagent invocation. Input: original source/header evidence, proposed
classification. Task: determine whether the proposed classification is supported by the
supplied evidence. Allowed output: `{"warrant": "supported"}` |
`{"warrant": "insufficient_evidence"}`. Nothing else.

The reviewer **must not see private reasoning from the classifier**. It sees only source
evidence and the proposed classification. This is structurally enforced: each subagent is
a separate agent invocation with only the prompt the orchestrator composes, so the
classifier's reasoning is never in the reviewer's context.

## Orchestrator contract

GLM-5.2 is given the business objective only:

> Determine the header row and the columns representing calendar months. Use the available
> specialist agents when useful. Do not invent unresolved meanings. If the available
> evidence is insufficient for a complete answer, request human review.

It is **not** told which agent to call first, how headers are detected, how Finnish month
names work, which cells are ambiguous, or how many agents to invoke.

### Orchestrator's declared approach (recorded, not instructed)

To keep orchestration unbiased and reproducible — and to avoid any steering by
foreknowledge of the expected answers — the orchestrator commits to the simplest
systematic strategy:

1. Call `HeaderLocator`.
2. If a header row is returned, classify **every** column in it with
   `HeaderCellClassifier`.
3. Warrant-review **every** classification with `WarrantReviewer`.
4. Hand the per-cell judgements to deterministic composition.

No column is skipped on the grounds that it is "obviously" a month or not a month, and no
classification is skipped on the grounds that it is "obviously" warranted. Reviewing every
classification is what lets G3 test the warrant hypothesis without the orchestrator
pre-selecting `Jakso A` for review (which would be foreknowledge contamination).

## Deterministic composition (the model never builds this)

For each column, given a `classification` and a `warrant`:

```python
ask_human = any(
    c.classification == "unknown" or c.warrant == "insufficient_evidence"
    for c in columns
)
month_columns = sorted(
    c.column for c in columns
    if c.classification == "month" and c.warrant == "supported"
)
unknown_columns = sorted(
    c.column for c in columns
    if c.classification == "unknown" or c.warrant == "insufficient_evidence"
)
```

- An **accepted** judgement is `classification in {month, not_month}` with
  `warrant == supported`. Accepted `month` judgements enter `month_columns`; accepted
  `not_month` judgements are excluded.
- Any `unknown` classification, or any `insufficient_evidence` warrant, sets
  `ask_human = true`. The orchestrator cannot override this gate.

When `ask_human` is true, `month_columns` is reported as the partial supported set
(informational, preserving known facts as in 2B.4/2B.5), but the authoritative answer is
`ask_human`.

## Tests — all frozen

The three fixtures are the Experiment 2B fixtures, referenced by path, unmodified.

| Test | Fixture | Role | sha256 (first 12) |
| --- | --- | --- | --- |
| **G1** | `experiment2b/fixtures/E1.csv` | easy positive control | `7e6f56252f36` |
| **G2** | `experiment2b/fixtures/R1.csv` | regular / realistic, Finnish | `1ec857c695c1` |
| **G3** | `experiment2b/fixtures/A1.csv` | ambiguous (`Jakso A`) | `64356f3ac01b` |

### Expected — frozen, never shown to the model

| Test | Expected `header_row` | Expected `month_columns` | Expected `ask_human` |
| --- | --- | --- | --- |
| **G1** | 4 | `[2,3,4,5]` | `false` |
| **G2** | 5 | `[2,3,4,5,6,7]` | `false` |
| **G3** | 4 | (partial `[2,3,5,6]` informational) | **`true`** |

For G3, `ask_human = true` is the **pass criterion**. The system must not silently produce
`[2,3,5,6]` as a complete warranted answer. The interesting observation is the trace: how
`Jakso A` is classified, whether that classification is warranted, and what the gate does.

### Why G1/G2 are the negative controls for G3

G2's R1 is unambiguous and was answered confidently in 2B.2. If the warrant reviewer is
indiscriminately cautious — flagging clear months as `insufficient_evidence` — G2 would
spuriously escalate. So G2 passing (`ask_human = false`) calibrates the reviewer before G3
is read, exactly as 2B.2's R1 controlled 2B.3's A1. G3 escalating while G1/G2 do not is the
meaningful signal; G3 escalating because the reviewer flags everything is ruled out by G1/G2.

## Run protocol

- One run per test. A capability check, not a statistical comparison (same discipline as 2B).
- Tests run in order: **G1, then G2, then G3.** The decision rule below gates progression.
- The orchestrator and all subagents are GLM-5.2 (the model driving this session).
  Subagents are invoked as fresh agent calls; each sees only its prompt.
- Sampling settings are whatever the harness session uses; this is recorded, not tuned to
  pass. There is no seed control over GLM-5.2 in this harness; that is a stated limitation.
- Agent outputs are recorded verbatim. **Failed/unparseable outputs are not repaired** before
  logging. A parse failure on a required judgement is recorded as such and treated as
  `unknown` / `insufficient_evidence` at the gate (the conservative direction: escalate).

## Logging

A complete orchestration trace is preserved per test in `experiment3a/trace/<test>.jsonl`.
Each line is one call:

```json
{"seq": 1, "caller": "GLM-orchestrator", "subagent": "HeaderLocator",
 "input": {...}, "raw_output": "...", "parsed_output": {...}}
```

The orchestrator's final requested disposition and the deterministic gate's result are both
recorded, so any divergence (orchestrator wants PROCEED, gate says ASK_HUMAN) is visible.

Example (G3, the interesting case):

```text
01 GLM -> HeaderLocator
   result: header_row=4
02 GLM -> HeaderCellClassifier  target "Tammi"     -> month
03 GLM -> HeaderCellClassifier  target "Jakso A"   -> not_month
...
06 GLM -> WarrantReviewer  proposition "Tammi = month"      -> supported
07 GLM -> WarrantReviewer  proposition "Jakso A = not_month" -> insufficient_evidence
...
08 deterministic gate
   month_columns (supported) = [2,3,5,6]
   unknown_columns           = [4]
   result: ASK_HUMAN
```

## Decision rule — declared before running

| Outcome | Action | Reading |
| --- | --- | --- |
| **G1 fails** | **STOP.** Do not run G2 or G3. | The orchestration scaffold itself is not yet usable. |
| **G1 passes, G2 fails** | STOP. Inspect the trace before changing anything. | Basic orchestration works but does not transfer to the localized case. |
| **G1 + G2 pass, G3 fails** | Preserve the failure. | Small-agent composition works, but independent review does not provide a reliable escalation signal. |
| **All three pass** | Record; do not extend. | Evidence for the architecture: manager + narrow agents + independent warrant review + deterministic gate. |

## Hard stop

Do not add normalization, Python transformation generation, country mappings, numeric
parsing, multiple sheets, joins, or reusable procedure synthesis — **even if G1–G3 all
pass.** The experiment ends at "is manager + narrow agents + deterministic gate viable."

## Stated limitations (declared before running, not after)

- **One run per test, one model, no seed control over GLM-5.2.** Cannot distinguish
  *always* from *did once*, same as every 2B probe.
- **Orchestrator foreknowledge.** The orchestrator (GLM-5.2, this session) has read the 2B
  results and the workorder, so it knows the expected answers. This is mitigated, not
  eliminated, by: (a) systematic dispatch — every column classified, every classification
  reviewed, no foreknowledge-based skipping; (b) subagent isolation — fresh agents see only
  the evidence and contract, never the expected answers or the orchestrator's private
  reasoning; (c) preregistered, fixed grading; (d) a deterministic gate the orchestrator
  cannot override. The measurements that matter (specialist classification accuracy,
  warrant-review judgement) are subagent outputs, not orchestrator claims. The foreknowledge
  chiefly threatens *interpretation*, which is why the trace is recorded verbatim.
- **Same model for specialists and reviewer.** If GLM-5.2 shares qwen3.5's warrant blind
  spot, the reviewer may over-endorse the classifier. That is the empirical question G3
  asks; it is not assumed away.
- **G3 pass does not prove the reviewer is calibrated in general** — only that on this one
  ambiguity instance it caught an unwarranted assertion while passing two unambiguous
  controls. One instance, same as 2B.5 was one instance in the other direction.