# Fidelity / traceability slice 1 — preregistration (CORRECTED, NOT YET IMPLEMENTED)

**Status: corrected per roundtable, and BLOCKED on two mechanical decisions
(§7).** No checker exists. No calibration has been run. Nothing in
`work_interface/w1b/` has been touched.

Authority: `work_interface/w1b/F1_ANALYSIS.md`, accepted at `dd9f7c6`.

## 1. What this slice measures

The structural validator checks shape, not faithfulness to what the human
actually supplied. W1-B produced three observations no refusal could see. This
slice asks, mechanically and without any model:

> **Can every Work Definition decision that a delivered human answer governs be
> traced back to that answer?**

## 2. Mechanism

A deterministic referent checker over two inputs: the **delivered block** (a
known row→canonical-string map, byte-identical and recorded per run in
`harness_result.json.block_sha256`) and the **artifact**. Every test is string
equality or declared-span containment against frozen bytes. **No semantic
judging, no LLM, no synonym list.**

## 3. Finding types

```text
FID-1  UNCITED_HUMAN_FACT      a decision slot that HAS v0 provenance machinery
                               (`basis` + `confirmation`) and whose governing
                               canonical answer was delivered, but whose basis is
                               not `human_confirmed`, or whose `confirmation` does
                               not resolve to a record carrying that canonical
                               string
FID-2  BUNDLED_CONFIRMATION    one human_confirmations[].answer carries TWO OR MORE
                               distinct delivered canonical answers
FID-3  PHANTOM_CONFIRMATION    a confirmation answer carrying ZERO delivered
                               canonical answers
FID-5  UNRECORDED_HUMAN_ANSWER a delivered canonical answer with no preserving
                               human_confirmations record anywhere in the artifact
FID-4  CONTRADICTED_DECISION   a slot value that contradicts its delivered
                               canonical answer
```

**FID-2 / FID-3 are exclusive**, per roundtable: each confirmation record is
classified by its canonical count — exactly one → normal, two or more → FID-2,
zero → FID-3. Every record receives exactly one classification.

### FID-1 is a PROPOSED invariant, not current law

**The requirement that a delivered governing answer must yield
`basis = "human_confirmed"` is a new fidelity invariant proposed by this slice.
The current structural validator does not require it and deliberately declines
to** — `work_definition.py:24-29`:

> *"It does not judge whether a `basis` label is the right epistemic label…
> Whether 'observed' is actually appropriate for a given decision stays with the
> human/modeller."*

An FID-1 finding is therefore a **measurement**, not a refusal, and must never be
reported as a validator violation.

## 4. Slot bindings — only where v0 has provenance machinery

```text
row 0  match key        -> body.match_on           basis + confirmation   FID-1 eligible
row 1  Amount/tolerance -> body.compare[Amount]    basis + confirmation   FID-1 eligible
row 2  currency         -> negative assertion: Currency absent from compare[]   FID-4 only
row 4  report row       -> output.reports_fields   NO basis/confirmation  FID-5 only
row 5  context          -> output.context_fields   NO basis/confirmation  FID-5 only
row 3  source of truth  -> NO v0 slot binding                             OUT OF SCOPE
rows 6,7 policies       -> not delivered in W1-B                          OUT OF SCOPE
```

`output.reports_fields` and `output.context_fields` carry **no `basis` and no
`confirmation`** in v0. FID-1 does not apply to them; FID-5 does. The schema has
no slot-level provenance there and this slice does not pretend otherwise.

**Row 3 is out of scope for slice 1**, per roundtable — it has no v0
decision-slot binding. Noted for the roundtable: row 3 *would* be FID-5-checkable
(does any confirmation preserve the source-of-truth canonical string?), and that
is deliberately deferred rather than silently dropped. F2 and F3 both produced a
`Q_source_of_truth` record, so slice 2 could measure it if wanted.

**Rows 6/7 stay out of slice 1.** `on_non_numeric` therefore remains an **observed
divergence**, reported non-refusing, and is *not* a mechanically judgeable
contradiction in this corpus: the block deliberately withheld the authoritative
answer, so there is nothing delivered to contradict.

## 5. Corpus and honesty constraint

Static, over already-frozen artifacts: **F1, F2, F3** primarily; D3/E2/E3
secondary. **No Goose. No new runs. N unchanged.**

**The expectations in §6 were derived from inspection already performed during
the W1-B analysis.** The first execution is therefore a **calibration of the
instrument against hand-derived expectations — not a blind prediction.** It
falsifies the checker, not the workers. A blind application requires a corpus not
yet inspected.

## 6. Frozen expectations (pending §7 resolution)

```text
F1  FID-1  body.match_on            basis "observed", confirmation null, row 0 delivered
F1  FID-5  row 4                    no confirmation preserves it
F1  FID-5  row 5                    no confirmation preserves it
F1  normal Q_compare_amount         carries exactly row 1
F2  FID-2  Q_compare_rule           carries rows 1,2,3,4,5 -- five decisions, one record
F2  normal Q_match_key              carries exactly row 0
F2  no FID-1 on match_on            basis human_confirmed, confirmation resolves to row 0
F3  normal Q_match_key              carries exactly row 0
F3  normal Q_source_of_truth        carries exactly row 3
all no FID-4                        no slot contradicts a delivered answer
pass criterion: the checker reproduces this table exactly. Missed and surplus
                findings cost the same, as in every prior gate.
```

## 7. BLOCKING — two premises that do not survive contact with the bytes

Implementation must not begin until the roundtable settles these.

### 7.1 The stated canary is factually wrong for F3

The correction asked to *"preserve the longest-first/non-overlapping-span canary
so F3 `Q_report_fields` resolves to row 4 only."* It cannot, under exact
full-string matching:

```text
row 4 canonical : 'The match key (InvoiceNumber) and the compared field (Amount).'
row 5 canonical : 'Date, Supplier Name, and Status.'
F3 answer       : 'The match key (InvoiceNumber) and the compared field (Amount) in
                   report rows. Date, Supplier Name, and Status as context.'

row 4 present in full?  False   <- terminal "." replaced by " in report rows."
row 5 present in full?  False   <- terminal "." replaced by " as context."
row 0 present in full?  True    <- "InvoiceNumber", nested inside row 4's phrasing
```

F3 spliced text over both terminal periods. Two candidate normalizations, with
what each yields:

```text
(a) exact full-string        -> {row 0} only. Semantically wrong: the record
                                actually carries spliced rows 4 and 5, and the
                                row-0 hit is the nesting artifact the canary
                                exists to suppress. Classified "normal".
(b) terminal-punctuation-    -> {row 4, row 5} after longest-first span claiming;
    tolerant                    row 0 falls inside row 4's claimed span and is
                                discounted. Classified FID-2.
```

**(b) satisfies the canary's intent** — row 0 must not spuriously win — but the
outcome is rows 4 **and** 5, not "row 4 only". The preregistration cannot be
frozen until one normalization is chosen and the expected value corrected.

### 7.2 Exclusive classification mislabels a truncated answer

```text
row 3 canonical : 'Neither — both are peer sources. Report what is missing from
                   either side and differences in the compared field.'
F2 Q_source_of_truth.answer : 'Neither — both are peer sources.'
row 3 present in full? False
```

F2 **truncated** the canonical answer, dropping the half that specifies what to
report. Under §3's exclusive rule this scores zero canonicals →
`FID-3 PHANTOM_CONFIRMATION`, i.e. *invented human speech* — which mislabels the
defect. Truncation is not invention, and the distinction matters: one fabricates
authority, the other loses instruction.

Options for the roundtable: accept the mislabel; add a distinct truncation
finding; or define a prefix rule. **Not decided here.**

## 8. Explicitly out of scope for slice 1

- Any judgement of whether a `basis` label is epistemically *right*
  (`work_definition.py:24-29` places that with the human).
- Row 3, rows 6/7 (§4).
- Paraphrase detection. F3's `Q_compare_policy` carries row 1 verbatim and a
  **paraphrase** of row 2 (*"No, Currency is…"* against canonical *"No. All sample
  amounts are GBP; …"*). Exact matching sees one canonical and scores it normal.
  **Paraphrased answers are invisible to this instrument**, and that limit is
  declared rather than patched — closing it would require semantic judging, which
  this slice forbids.

## 9. What slice 1 cannot conclude

That a clean result means high fidelity. It measures only whether delivered
canonical strings are traceable into the artifact's provenance machinery, over
four rows, on three artifacts, with paraphrase invisible.
