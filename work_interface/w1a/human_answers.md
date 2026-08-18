# W1-A frozen human-answer script

This is the **controlled variable** for the W1-A experiment. Every desktop Goose
session (A1–A5) must receive the same human input, so that any difference in the
produced `work_definition.json` is attributable to the skill/model, not to the human.

The operator runs each session by following this script verbatim. The answers are
derived from the W0B corrected candidate (`work_interface/cases/W0B_corrected.json`)
so that a clean run reproduces the known-good oracle. **The operator does not invent
answers, does not correct the agent, and does not repair the artifact.**

## Session setup (identical for A1–A5)

1. Confirm the live skill is byte-identical to the frozen revision (sha256 in
   `skill/PROVENANCE.md`). If it differs, stop — the run is contaminated.
2. Copy the two frozen fixtures into the run directory so the agent can inspect them:
   ```
   work_interface/w1a/fixtures/supplier-statement.txt  ->  work_interface/w1a/runs/A<i>/
   work_interface/w1a/fixtures/ledger-book.txt         ->  work_interface/w1a/runs/A<i>/
   ```
   Do not edit the copies; they are for the agent to read. The grader cross-checks
   against the originals in `w1a/fixtures/`, so an accidental edit of a copy does not
   change the grade.
3. Start the Goose session with the working directory set to the run directory
   `work_interface/w1a/runs/A<i>`.
4. Send Goose the **opening prompt** (below), then `load_skill("define-lab-process")`,
   then answer its questions from the table below.

## Opening prompt (send verbatim to Goose)

> I have two files in this folder — a supplier statement and an internal ledger.
> Show which supplier items do not match our ledger. Use the define-lab-process skill
> and produce a work_definition.json for Learning Lab to validate.

## Answers to Goose's questions

Goose may phrase or order its questions differently. Match by **intent**, not by
wording, and give the canonical answer verbatim. If Goose asks a question this script
does not cover, answer honestly and minimally, but record what you said in the run
notes — an unscripted answer is a protocol deviation, not a repair.

| Intent Goose is asking about | Canonical answer (say this verbatim) |
|---|---|
| Which field identifies the **same record / invoice** in both files? | `InvoiceNumber` |
| Should **Amount** be compared, and if so, how and with what tolerance? | Yes, compare Amount numerically, within 0.01. |
| Is **Currency** part of the reconciliation rule? | No. All sample amounts are GBP; Currency is not compared and is not part of the rule. |
| Which file is the **source of truth** for matching? | Neither — both are peer sources. Report what is missing from either side and differences in the compared field. |
| Which fields should appear in the **report row**? | The match key (InvoiceNumber) and the compared field (Amount). |
| Which fields are **context** for the report? | Date, Supplier Name, and Status. |
| What should happen if the same key appears **more than once** in a source? | Refuse the run — do not silently pick or merge. |
| What should happen if a compared value is **not a number**? | Refuse the run — do not coerce. |
| Anything about the **Notes** field in the ledger? | It is not load-bearing for now; leave it as an open, non-load-bearing question. Do not make it part of the rule. |

## What the operator must NOT do

- Do not tell Goose the field names are "Supplier Name" / "InvoiceNumber" etc. unless
  it asks — Goose must read those from the fixture headers itself. If Goose misreads a
  header (e.g. writes `SupplierName`), **do not correct it**. A misread header is
  exactly the kind of defect the validator is meant to catch; correcting it would
  falsify the experiment.
- Do not tell Goose the answers to the structural contract (vocabularies, basis
  rules). The skill teaches those. Answer only the business decisions above.
- Do not edit, rename, or "fix" the produced `work_definition.json` for any reason.
  The grader records what Goose actually produced.
- If Goose asks whether the artifact is "approved" or "established" or tries to set
  authority, answer: "No — it is a non-authoritative proposal for validation.
  `requested_authority` is null." Do not let it self-authorize.

## After the session

1. Confirm `work_interface/w1a/runs/A<i>/work_definition.json` exists. If Goose wrote
   it elsewhere, that is a defect (wrong output location) — record it, do not move
   the file. The grader reports `no_artifact` for the run dir, which is the honest
   result.
2. Optionally write a one-line `operator_notes.md` in the run dir noting any protocol
   deviations (unscripted questions, Goose confusion, timeouts). Do not put notes
   inside `work_definition.json`.
3. Run the grader: `python work_interface/w1a/grade.py` (grades all five run dirs).