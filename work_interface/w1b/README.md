# W1-B — the perfect-information ablation

**Authority: `../W1A_DISPOSITION.md`.** W1-A2–W1-A5 are closed as
measurement-invalid for skill-quality inference. The dialogue channel routed 37%
of worker questions correctly and **misrouted 17%** — answering *"For output
order: left_then_right or sorted_by_key?"* with **`InvoiceNumber`**. A channel
that both withholds and misdelivers cannot attribute PASS or FAIL to the skill.

W1-B removes the channel rather than repairing it, changing the question from

> "Can the worker interact correctly with our dialogue harness?"

to

> **"Can the worker perform the skill when all required human information is
> definitely available?"**

That capability baseline does not currently exist.

## Unchanged

```text
SKILL.md          byte-identical, 4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55
fixtures          byte-identical  d0cb95ab… / 284861d7…   (same fixture semantics)
human_answers.md  byte-identical  5fe99a5b…               (source of every block byte)
validator         unchanged       work_interface/work_definition.py
grader logic      unchanged apart from the run prefix
```

`w1a/`, `w1a2/`, `w1a3/`, `w1a4/` and `w1a5/` are closed evidence: not reused,
not re-run, not edited. F1/F2/F3 are fresh.

## The ablation property

After **every completed worker turn that did not produce the artifact**, the
harness sends one canonical block. The outgoing message is **unconditional** — it
does not depend on what the worker said, or whether it said anything at all.

**There is no lexical matching, no semantic matching, no synonyms, no routing and
no question classification anywhere in `harness/block_harness.py`.** There is
deliberately no `classify_turn`, no `intents_in`, no `segment_fragments`, and no
import of any W1-A harness. `verify_prep.py` check 10 proves this by AST — code,
not prose — and by asserting the imported module exposes none of those symbols.

Interrogative counting exists solely to log whether the worker keeps asking for
information it already holds. It selects nothing and gates nothing.

## The canonical block

693 bytes, sha256 `46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330`.

```text
Which field identifies the **same record / invoice** in both files?
InvoiceNumber

Should **Amount** be compared, and if so, how and with what tolerance?
Yes, compare Amount numerically, within 0.01.

Is **Currency** part of the reconciliation rule?
No. All sample amounts are GBP; Currency is not compared and is not part of the rule.

Which file is the **source of truth** for matching?
Neither — both are peer sources. Report what is missing from either side and
differences in the compared field.

Which fields should appear in the **report row**?
The match key (InvoiceNumber) and the compared field (Amount).

Which fields are **context** for the report?
Date, Supplier Name, and Status.
```

Every byte is verbatim from `w1a/human_answers.md` — the labels are the table's
own Intent cells, the answers its own canonical strings. **Nothing is authored
by the harness**, and there is no preamble or framing sentence, because any such
text would be invented here and could bias the worker.

### A boundary judgement, flagged for review

The five SKILL-mandated questions map to **six** table rows: S5 (*"Which fields
should appear in the report row, and which are context?"*) is one mandated
question whose frozen answer has two halves, rows 4 and 5. Both are included —
dropping row 5 would withhold half of a mandated answer. If you intended
strictly five rows, this is the line to change.

### Deliberately excluded

```text
rows 6, 7   duplicate-key and non-numeric policy. SKILL.md:124-125 assigns these
            to the worker via closed vocabularies (refuse_run / refuse_key).
            Supplying them would paper over the ownership inconsistency this
            ablation must leave standing.
row 8       the Notes field -- a specialisation beyond the five.
(no row)    left/right roles, classify labels, output order, purpose. SKILL.md
            assigns all four to the worker; the frozen table has no answer.
```

## Outcomes

```text
COMPLETED                                     artifact written; session terminated at once
CONTESTED: BLOCKED_WITH_COMPLETE_INFORMATION  no artifact within the turn limit although
                                              the complete mandated block was held --
                                              a meaningful WORKER-BEHAVIOUR result,
                                              not a harness fault
CONTESTED                                     timeout, forbidden path, mutated input
HARNESS_ERROR                                 infrastructure only

exit 0  batch executed correctly, CONTESTED included
exit 1  HARNESS_ERROR only          -> a correct batch always reaches grade.py
```

**Continued questioning after the block is supplied is logged separately and does
not itself fail the artifact.** `questions_after_block` counts question-bearing
lines in every turn after the first delivery. A worker that keeps asking and then
succeeds is a PASS with a behavioural note; a worker that blocks indefinitely
while holding the information is the CONTESTED case above.

## Preserved from W1-A5

First-artifact hard stop, controlled-input hashing before and after, forbidden-path
checks, complete append-only transcript capture (with one `lifecycle` record per
block delivery), and infrastructure-vs-experimental exit semantics.

## Frozen interpretation

```text
3/3 PASS   capability under complete information is established. The old failures
           were dominated by the measurement channel. RETIRE matcher repair.
FAIL       now interesting -- inspect skill under-specification, worker
           contradiction, or artifact-validation fidelity, because the
           answer-delivery confound is gone.
MIXED      causal analysis run by run FIRST. Do NOT increase N until we know what
           differs between the runs.
```

## Execution

```bash
python work_interface/w1b/harness/selftest.py && python work_interface/w1b/harness/block_harness.py --run all && python work_interface/w1b/grade.py
```

Inspect the block without running anything:

```bash
python work_interface/w1b/harness/block_harness.py --run all --show-block
```

## What this experiment deliberately does not test

Dialogue competence. Delivering all five answers unconditionally abandons "ask
only what you need" fidelity by design. That is the right first cut precisely
because the instrument that was supposed to measure dialogue competence is the
thing now shown to be broken. Structured dialogue with explicit question identity
is W1-C, and only if capability survives here.
