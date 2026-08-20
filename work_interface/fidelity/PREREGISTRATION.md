# Fidelity / traceability slice 1 — preregistration (REVISED, frozen before implementation)

> ## THIS IS A CALIBRATION, NOT A BLIND WORKER EXPERIMENT
>
> The corpus is F1/F2/F3 — three artifacts **already inspected in detail** during
> the W1-B analysis. The expectations in §5 were **hand-derived from the frozen
> bytes before the checker was written**. The run therefore falsifies **the
> instrument**, not the workers. It cannot tell us anything new about
> `define-lab-process`, and no fidelity claim about worker quality may be drawn
> from it. A blind application requires a corpus not yet inspected.

Authority: `work_interface/w1b/F1_ANALYSIS.md` (accepted `dd9f7c6`) and the
roundtable decisions recorded in `work_interface/W1A_DISPOSITION.md` lineage.
No Goose or model execution at any point.

---

## 1. Operation 1 — deterministic attribution

Which frozen canonical row(s) a confirmation derives from. **No semantic
matching, no LLM, no synonyms.**

```text
normalization (ATTRIBUTION ONLY -- never used to judge byte-exactness)
    collapse all whitespace runs to a single space; strip ends
    remove terminal sentence punctuation  [.!?]  from the canonical and the answer

complete attribution
    for each canonical, LONGEST NORMALIZED FORM FIRST:
        find its first occurrence in the normalized answer that does not overlap
        an already-claimed span
        on success: claim that span, attribute the row
    a span once claimed cannot be claimed again by a nested shorter canonical

partial attribution -- ONLY when zero complete rows were attributed
    if the normalized answer is a STRICT PREFIX of exactly one normalized
    canonical -> attribute that row (partial)
    if it is a strict prefix of two or more -> UNATTRIBUTED (ambiguous)
```

The longest-first + span-claiming rule exists for one observed reason: row 0's
entire canonical is the string `InvoiceNumber`, which is nested inside row 4's
canonical. Without it, row 4's text spuriously attributes to row 0.

## 2. Operation 2 — exclusive fidelity classification

Every confirmation record receives **exactly one** classification:

```text
0 attributable rows                              -> FID-3 PHANTOM_CONFIRMATION
>= 2 attributable rows                           -> FID-2 BUNDLED_CONFIRMATION
exactly 1 + answer byte-exact to that canonical  -> normal
exactly 1 + answer NOT byte-exact                -> FID-6 NONVERBATIM_CONFIRMATION
```

Byte-exactness is tested on **raw bytes**, never on the normalized form.

`FID-6` carries a deterministic subreason from a closed set:

```text
TRUNCATED_PREFIX   the answer is a strict prefix of the canonical (content lost)
TRAILING_CONTENT   the canonical is a strict prefix of the answer (content added)
EMBEDDED           the canonical appears complete, with text on both sides
ALTERED            attributed only partially, or present only after normalization
```

`FID-3` means *invented human speech*. Truncation is **not** invention: a
truncated answer attributes via the strict-prefix rule and lands in FID-6 with
`TRUNCATED_PREFIX`. This is the correction that removes the mislabel.

## 3. Findings

```text
FID-1  UNCITED_HUMAN_FACT       a decision slot WITH v0 provenance machinery
                                (`basis` + `confirmation`) whose governing canonical
                                row was delivered, but whose basis is not
                                `human_confirmed`, or whose `confirmation` does not
                                resolve to a confirmation attributing EXCLUSIVELY and
                                BYTE-EXACTLY to that governing row.
                                A BUNDLED or NONVERBATIM confirmation is NOT
                                sufficient provenance.
FID-2  BUNDLED_CONFIRMATION     see §2
FID-3  PHANTOM_CONFIRMATION     see §2
FID-4  CONTRADICTED_DECISION    a slot value contradicting its delivered canonical
FID-5  UNRECORDED_HUMAN_ANSWER  a delivered row whose v0 decision has NO provenance
                                slot, and which no confirmation attributes to
                                anywhere in the artifact. It asks whether the
                                canonical authority was RECORDED at all -- not
                                whether an output slot cites it, because v0 gives
                                those slots nothing to cite with.
FID-6  NONVERBATIM_CONFIRMATION see §2
```

### FID-1 is a PROPOSED invariant, not current law

The structural validator does not require `basis = "human_confirmed"` when a
human answer was delivered, and deliberately declines to —
`work_definition.py:24-29`:

> *"It does not judge whether a `basis` label is the right epistemic label…
> Whether 'observed' is actually appropriate for a given decision stays with the
> human/modeller."*

FID-1 is a **measurement**, never a validator violation.

## 4. Slot bindings

```text
row 0  match key        -> body.match_on          basis+confirmation   FID-1 eligible
row 1  Amount/tolerance -> body.compare[Amount]   basis+confirmation   FID-1 eligible
row 2  currency         -> negative assertion: Currency absent from compare[]  FID-4
row 4  report row       -> output.reports_fields  no provenance slot   FID-5 only
row 5  context          -> output.context_fields  no provenance slot   FID-5 only
row 3  source of truth  -> NO bound v0 decision slot        OUT of slot-level FID-1
rows 6,7  policies      -> not delivered in W1-B            OUT of scope entirely
```

**Row 3 stays out of slot-level FID-1** because v0 has no bound decision slot for
it. It still participates in *attribution* — a confirmation may attribute to row
3 and be classified — it simply has no slot whose provenance could be checked.

**Rows 6/7 stay out.** `on_non_numeric` therefore remains an **observed
divergence**, reported non-refusing: the block withheld the authoritative answer,
so there is nothing delivered to contradict.

## 5. Frozen expectations — hand-derived from the bytes, before implementation

### Confirmation classification

```text
F1  Q_compare_amount    rows {1}        byte-exact              normal
F2  Q_match_key         rows {0}        byte-exact              normal
F2  Q_compare_rule      rows {1,2,3,4,5}                        FID-2 BUNDLED
F2  Q_source_of_truth   rows {3} partial, strict prefix         FID-6 TRUNCATED_PREFIX
F3  Q_match_key         rows {0}        byte-exact              normal
F3  Q_compare_policy    rows {1}        canonical is a prefix   FID-6 TRAILING_CONTENT
F3  Q_source_of_truth   rows {3}        byte-exact              normal
F3  Q_report_fields     rows {4,5}                              FID-2 BUNDLED
```

Two corrections against the previous draft, both forced by the actual bytes:

- **F3 `Q_report_fields` attributes to rows 4+5, not row 0.** F3 spliced text
  over both terminal periods (`…(Amount) in report rows.`, `…and Status as
  context.`), so the rows attach only after terminal-punctuation normalization,
  and row 0 is discounted as nested inside row 4's claimed span. → FID-2.
- **F2 `Q_source_of_truth` attributes to row 3 and is FID-6, not FID-3.**
  `"Neither — both are peer sources."` is a strict prefix of row 3's canonical.

### Slot-level findings

```text
F1  FID-1  body.match_on          basis "observed" (not human_confirmed)
F1  FID-5  row 4                  no confirmation attributes to it
F1  FID-5  row 5                  no confirmation attributes to it
F2  FID-1  body.compare[Amount]   cites Q_compare_rule, which is BUNDLED
F3  FID-1  body.compare[Amount]   cites Q_compare_policy, which is NONVERBATIM
no FID-1 on F2/F3 body.match_on   both cite an exclusive byte-exact confirmation
no FID-5 on F2 or F3              rows 4 and 5 are attributed somewhere in both
no FID-4 anywhere                 no slot contradicts a delivered canonical
```

**Pass criterion:** the checker reproduces this table exactly. Missed and surplus
findings cost the same, as in every prior gate.

## 6. Declared limits

- **Paraphrase is invisible.** F3's `Q_compare_policy` also carries a paraphrase
  of row 2 (*"No, Currency is not part of the reconciliation rule."* against
  canonical *"No. All sample amounts are GBP; …"*). Attribution sees one row, not
  two. Closing this would require semantic judging, which this slice forbids.
- The checker never judges whether a `basis` label is epistemically right (§3).
- Rows 3, 6, 7 per §4.
- A clean result would mean only that delivered canonical strings are traceable
  into v0's provenance machinery over four rows on three already-inspected
  artifacts.
