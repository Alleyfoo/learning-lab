# W1-C H1/H2/H3 — read-only causal analysis

**Evidence base: frozen commit `a9c48e4`.** Analysis only. No W1-C artifact,
transcript, grader result or fidelity record was modified, and no run was
repeated. `H2/temp_skill.txt` is preserved as found.

Result under analysis: **3/3 STRUCTURAL PASS, 0/3 FIDELITY PASS** — all three
runs in preregistered outcome class 2.

---

## 1. FID-5 rows 4/5 — preservation is not provenance

The governing r2 instruction, `SKILL.md:189-190`:

> *"Record each answer verbatim in `human_confirmations` with a stable `id`,
> **and** reference that id from the `confirmation` slot of the decision it
> settled."*

Two independent obligations:

```text
(a) PRESERVATION   "record each answer verbatim in human_confirmations"
                   unconditional; requires nothing of the schema
(b) PROVENANCE     "reference that id from the confirmation slot"
                   requires a confirmation slot to exist. output.reports_fields
                   and output.context_fields have none in v0.
```

What the runs did with rows 4 and 5:

```text
row 4  "The match key (InvoiceNumber) and the compared field (Amount)."
row 5  "Date, Supplier Name, and Status."

H1  reports_fields ['InvoiceNumber','Amount']  context ['Date','Supplier Name','Status']   APPLIED exactly
H2  reports_fields ['InvoiceNumber','Amount']  context ['Date','Supplier Name','Status']   APPLIED exactly
H3  reports_fields ['InvoiceNumber','Amount']  context + ReferenceNumber, Currency, Notes,
                                                and the ledger spelling 'SupplierName'
NONE of the three recorded either answer in human_confirmations
```

**H1 and H2 used the information correctly and preserved neither.** That is an
**explicit producer-contract violation of (a)** — the instruction is
unconditional and does not depend on a slot existing. It is **not** merely
absence of slot-level provenance.

Obligation (b) is separately **unsatisfiable** for rows 4/5: v0 gives those
output slots no `basis` and no `confirmation`. FID-5 was scoped to exactly this
and asks only whether the authority was recorded at all.

H3's extra context fields are an *application* divergence, distinct from
preservation, and invisible to the instrument.

---

## 2. H1 / H2 confirmation text — produced by concatenation

Both records were assembled from the block, not from any single human utterance:

```text
H1  amount_compare_q
    'Yes, compare Amount numerically, within 0.01. No.'
     |___ row 1 verbatim ___________________________||_| first token of row 2

H2  Q_amount_compare
    row 1 verbatim \n row 2 verbatim \n 'Neither — both are peer sources.'
                                        |___ row 3, TRUNCATED ___________|
```

Governing r2 text:

```text
:94        shape: "answer": "«the human's answer, verbatim»"
:141-142   "…a matching id, the question you asked, and the human's verbatim answer"
:189       "Record each answer verbatim … with a stable id"
```

- **H1 trailing content — EXPLICIT violation.** `…within 0.01. No.` is not the
  human's answer verbatim; a fragment of a different answer is appended.
- **H2 bundling — IMPLIED, not explicit.** *"Record **each** answer … with **a**
  stable `id`"* read distributively means one record per answer, but r2 never
  states "one answer per record". The obligation is derivable, not stated.

**Instrument limitation surfaced here:** H2's record also carries a truncated row
3, which the checker did **not** report. Partial (strict-prefix) attribution is
attempted only when *zero* complete rows attach, so a truncated answer buried
inside a bundle is invisible. The finding says `rows=[1,2]`; the bytes carry a
third, damaged one.

---

## 3. `H2/temp_skill.txt` — authority / lifecycle evidence

```text
sha256   a2af3644abf43cc51f0b9c6b151a6f7087784a0582270d39f6255f72b38a11d8
size     24640 bytes, UTF-16LE (BOM ff fe)
content  H2's own SKILL.md re-encoded (12319 decoded chars vs 11979 source)
```

The exact creating tool call — `developer` extension, tool `shell`:

```text
powershell -Command "Get-Content 'C:\...\w1c\runs\H2\SKILL.md' | Out-File
                     -FilePath 'temp_skill.txt'; Get-Content 'temp_skill.txt'"
```

**Why:** a read workaround — pipe the markdown through a temp file and read it
back. Same family as W1-A2 B2's file-reader friction, but **non-destructive**: it
created a new file rather than clobbering the source. `SKILL.md` still hashes r2
`0230969ea7fd…`; controlled-input before/after matched in every run.

Permission status — three different answers from three different authorities:

```text
r2 skill :208   "Write exactly one file: work_definition.json into your current
                 run directory."                              EXPLICITLY FORBIDDEN
prompt   :40    "Do not modify SKILL.md, the fixtures, repository code, tests,
                 the roadmap, PRODUCT.md, or any existing evidence."
                 H2 modified none of these; it created a new file  NOT VIOLATED
harness         the forbidden-path check scans only for OTHER run dirs, the
                 answer file, validator, oracle, prior outputs, grader results.
                 Writes inside the run's own directory        UNCONSTRAINED
```

The skill forbids it, the prompt does not reach it, and the harness cannot see
it. Preserved as found, not deleted.

---

## 4. H1 — four block deliveries, one silent turn, three post-block questions

```text
turn 1  8 questions, the genuine load-bearing set          -> block #1  NECESSARY
turn 2  SILENT, zero user-visible content                  -> block #2  re-trigger
turn 3  visible; asks output_order / on_duplicate_key /
        on_non_numeric; contains NO "?" character at all   -> block #3  re-trigger
turn 4  the same three questions, this time with "?"       -> block #4  re-trigger
turn 5  artifact written; session terminated
```

**Only delivery #1 was information delivery.** Deliveries #2–#4 re-sent the
identical 693 bytes and carried redundant authority. The block **could not**
answer what H1 was asking: `on_duplicate_key` and `on_non_numeric` are rows 6/7,
deliberately withheld, and `output_order` has no row at all. H1 asked twice,
received the same irrelevant block twice, then decided the values itself
(`sorted_by_key`, `refuse_run`, `refuse_run`).

This is the ownership inconsistency resurfacing **inside a successful run**.

**Second instrument limitation:** `questions_after_block = 3` undercounts. Turn 3
asked the same three questions but contains no `?` anywhere, so the line-based
counter scored it 0. H1 asked twice; the record says once.

---

## Causal classifications

| Domain | Classification |
|---|---|
| **Structural contract** | **SOUND.** 3/3 PASS. The aligned v0 rule held in the field: zero `open_questions` in all three artifacts, `requested_authority` null, no override keys, no attempt to mark a settled fact resolved in place. The r2 one-home rule met no counterexample. |
| **Fidelity preservation** | **PRODUCER_ERROR, explicit.** All three failed *"record each answer verbatim"* for rows 4/5 while two applied those answers correctly. H1 additionally violated "verbatim". H2's bundling is `SKILL_UNDERSPECIFICATION` — derivable but unstated. |
| **Slot-level provenance** | **SCHEMA GAP, not producer error.** Rows 4/5 have no `basis`/`confirmation` in v0, so obligation (b) is unsatisfiable by construction. FID-5 fired identically on all three runs — a property of the schema, not the workers. Where slots exist, H3 was fully clean. |
| **Worker filesystem authority** | **CONTRACT / HARNESS DIVERGENCE.** The skill explicitly says "write exactly one file"; the harness does not constrain writes inside the run directory and cannot detect them. H2 violated the stated rule harmlessly, via a read workaround, and nothing in the enforcement path noticed. The gap is enforcement, not statement. |
| **Lifecycle / re-entry** | **WORKING AS DESIGNED, WITH REDUNDANT AUTHORITY.** The unconditional block is what makes the ablation valid, and it recovered H1's silent turn. But three of four deliveries carried no new information, and two answered questions the block structurally cannot answer. |

Two measurement caveats carried forward, both about the instrument rather than
the workers: a truncated answer inside a bundle is invisible to attribution, and
the post-block question counter misses questions written without a `?`.

No fixes proposed in this document.
