# W1-A2 — result and postmortem evidence

**Result: 2/3 PASS. The primary success criterion (3/3) FAILED.**

Graded 2026-08-20 13:10:38 by `grade.py`. Read-only analysis; no artifact, frozen
input, or grader output was repaired, revised, or moved. The skill is **not**
revised. No fix is proposed in this document.

```text
B1   PASS      skill_match yes   sha 6c6b53c0934b
B2   REFUSED   skill_match yes   observed_field_not_in_source   sha ccf91d4ae84c
B3   PASS      skill_match yes   sha fad66688bd50
```

B2's refusal, verbatim from `RESULTS.md`:

> `observed_field_not_in_source` @ `<work_definition>:sources.statement` —
> `' Supplier Name '` claimed observed but not in fixture header
> `['Date', 'Supplier Name', 'InvoiceNumber', 'Amount', 'Currency', 'Status']`

## FINDING 0 — a frozen input was destroyed during the B2 session

**This is recorded first because it bounds every other conclusion below.**

`runs/B2/PROMPT.md` is **modified in the working tree**: truncated from 1934
bytes / 38 lines to 22 bytes / 1 line. The surviving content is the single line
`This is W1-A2 run B2.`

```text
committed blob   fa2a49de3262134756bd10f7476fd177f51e35a0f828fb1bf52f4266f8ced523
on disk          66010fd393906873a3493159dca8edc2a05652e44a2baafb205ee6a17be7f039
git diff         1 file changed, 37 deletions(-)
```

Timeline from filesystem mtimes:

```text
13:01:11   B1/work_definition.json written
13:03:57   B2/PROMPT.md truncated          <- during the B2 session
13:05:23   B2/work_definition.json written
13:09:38   B3/work_definition.json written
13:10:38   RESULTS.md / RESULTS.json written
```

B1's and B3's prompts are byte-intact (1934 bytes each). The 37 deleted lines
carried: the fixture absolute paths, the Windows-safe read commands, the
artifact write path, the prohibition on inspecting the validator / oracle /
other runs, and the instruction *"Do not modify `SKILL.md`, the fixtures,
repository code, tests, the roadmap, `PRODUCT.md`, or any existing evidence."*

**Consequence:** B2 is the one run whose controlled inputs are known not to have
been held constant, and it is the run that failed. Any statement of the form
"the skill caused B2's refusal" is not currently supported.

`SKILL.md` is intact in all three runs (`4ff939d4…`, frozen hash, exact), so
skill *delivery* was uncompromised in all three.

## FINDING 1 — where `' Supplier Name '` appears

It appears **only inside B2's artifact**, in exactly two places:

```text
.sources.statement.observed_fields[1]   ' Supplier Name '
.output.context_fields[2]               ' SupplierName '
```

These are the only two whitespace-padded strings in the entire artifact.

## FINDING 2 — it is absent from every frozen input

Literal byte search for `" Supplier Name "` and `" SupplierName "` (both with
leading and trailing space) across:

```text
w1a/fixtures/supplier-statement.txt      not present
w1a/fixtures/ledger-book.txt             not present
w1a/human_answers.md                     not present
w1a2/runs/B2/SKILL.md                    not present
w1a2/runs/B2/PROMPT.md (committed blob)  not present
```

**The padded value was introduced by the B2 session.** It did not come from the
fixture, the prompt, the frozen human answers, or the skill.

## FINDING 3 — it is not a naive-parse artifact either

The fixture header line is:

```text
Header: Date, Supplier Name, InvoiceNumber, Amount, Currency, Status
```

Columns are separated by `,` followed by a space, so a naive `split(",")` yields
a **leading** space only:

```text
naive split(',')   ' Date'  ' Supplier Name'  ' InvoiceNumber'  ' Amount'  …
validator (strip)  'Date'   'Supplier Name'   'InvoiceNumber'   'Amount'   …
' Supplier Name ' producible by naive split?   False
```

Two facts rule out a systematic parsing failure:

1. The **trailing** space is not derivable from the header bytes by any
   straightforward comma split.
2. Padding is **sporadic, not uniform**. Under a naive split all six statement
   columns would be padded; in B2 only `observed_fields[1]` is. `Date`,
   `InvoiceNumber`, `Amount`, `Currency`, `Status` are all clean, B2's **entire
   `ledger` source is clean**, and `output.context_fields[1]` contains the same
   header token in trimmed form (`'Supplier Name'`) alongside the padded
   `' SupplierName '`. B2 is internally inconsistent with itself.

## FINDING 4 — what the refused field is supposed to refer to

`sources.<role>.observed_fields` is the field the validator cross-checks against
the real fixture. `work_definition.py:192` parses the header as:

```python
[c.strip() for c in line[len("header:"):].split(",") if c.strip()]
```

so the validator's canonical header is the **trimmed** form, and any padded
variant fails `observed_field_not_in_source`.

The second padded value did **not** raise anything. `output.context_fields` is
only read at `work_definition.py:453-455`, where it *populates* the `declared`
set; it is never cross-checked against a source header. So
`' SupplierName '` — a string that matches no header in either fixture — passed
unflagged. **The cross-check is asymmetric: `observed_fields` is verified
against source evidence, `context_fields` is not.**

## FINDING 5 — B1 and B3 met the same header and trimmed it

Same fixtures, same frozen skill, same human answers:

```text
B1  statement.observed_fields  ['Date','Supplier Name','InvoiceNumber','Amount','Currency','Status']
B2  statement.observed_fields  ['Date',' Supplier Name ','InvoiceNumber','Amount','Currency','Status']
B3  statement.observed_fields  ['Date','Supplier Name','InvoiceNumber','Amount','Currency','Status']

all three  ledger.observed_fields  ['Date','ReferenceNumber','SupplierName','InvoiceNumber','Amount','Status','Notes']
```

Five of six source field-lists across the three runs are trimmed and correct.

## FINDING 6 — the skill does not settle whitespace

The frozen skill is explicit about **spelling** and silent about **padding**:

```text
line 130  "`observed_fields` must be the EXACT strings from the fixture's
           `Header:` line, in order." … "`Supplier Name` and `SupplierName` are
           different fields" … "copy each column name verbatim"
line 163  "find the `Header:` line, and record the column names verbatim"
line 210  "Do not normalize or 'fix' field names. Copy header strings verbatim."
```

Every example it gives distinguishes *spelling* variants. It never states
whether the delimiter's trailing space belongs to the token, never uses the
words trim / strip / whitespace, and its standing instruction is *not* to
normalize — while the validator silently normalizes by trimming. **The contract
is under-specified at exactly the point B2 failed**, in a direction that mildly
discourages the behaviour the validator requires.

This does not by itself explain B2: the padded value is not what a
verbatim-and-do-not-normalize reading of the header produces either (FINDING 3).

## FINDING 7 — other differences, and one that PASS did not catch

Nothing else in B2 bears on the refusal; `observed_field_not_in_source` was the
only code raised. But the three artifacts are not equivalent:

```text
        confirmations   compare                             open_qs   authority
B1      2               Amount, comparison "exact"           0        None
B2      8               Amount, "within", tolerance 0.01     1        None
B3      9               Amount, "within", tolerance 0.01     1        None
```

The frozen human answer table states: *"Yes, compare Amount numerically, within
0.01."* **B1 PASSED while recording `comparison: "exact"` with no tolerance** —
contradicting the controlled human input — and captured 2 of the 11 answer rows.
B2, the refused run, captured 8 and got the comparison semantics right.

This repeats W1-A's A4/A5 observation on the other side of the pass line:
**structural validity is not fidelity to the human script, and the validator
does not measure fidelity.**

## What is preserved

Byte-for-byte, unmodified: `runs/B1|B2|B3/work_definition.json`,
`runs/B1|B2|B3/SKILL.md`, `RESULTS.md`, `RESULTS.json`,
`w1a/fixtures/*.txt`, `w1a/human_answers.md`. `runs/B2/PROMPT.md` is preserved
**in its truncated state** — it is evidence of FINDING 0 and was deliberately
not restored.
