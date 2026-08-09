# Unanswered Questions

Questions the research could not settle from published sources or repository inspection.
Ranked by how much each one changes the architecture if answered.

Legend — **Blocks:** what cannot be decided until this is answered.
**Answerable by:** the cheapest instrument that would settle it.

---

## Tier 1 — Answer before any modelling plane is built

### UQ-1. What is the drift-class distribution for real providers?

What fraction of real source changes are cosmetic, structural, or semantic, over 12–24 months
of real deliveries?

- **Why it dominates:** this single distribution determines whether the architecture pays for
  itself. If 90% of changes are cosmetic, a synonym store plus fuzzy matching handles the
  business and the modelling plane is over-engineering. If 20% are semantic, the human gate is
  the product and everything else is plumbing.
- **Blocks:** H4; the escalation cost model; whether L4 statistical baselining is worth building.
- **Answerable by:** a retrospective audit of archived provider files. No system required —
  just the historical files and a classification pass. **This is a data-collection task, not a
  research task, and it should start immediately and in parallel with everything else.**
- **Not answerable from literature.** No surveyed system reports it.

### UQ-2. How stationary are ERP/bookkeeping exports, really?

The recommendation to prefer agent-independent artifacts rests on the claim that spreadsheet
exports are more stationary than web UIs (which is why AWM's agent-dependent design should not
be imported).

- **Blocks:** H2's applicability to our domain; the entire "reduce future use of intelligence" premise.
- **Answerable by:** the same retrospective audit as UQ-1 — measure inter-delivery structural
  change rate per provider.

### UQ-3. What is the false-apply rate of name-set applicability across a source family?

Adjacent providers within one source family (e.g. three companies on the same ERP, same export
template) look nearly identical structurally. How often would a name-set-based predicate accept
provider B's file under provider A's model?

- **Why it matters:** this is the dangerous failure. A wrong adapter that runs successfully and
  produces plausible wrong numbers is invisible. It is also the failure mode that *grows* with
  scale, exactly as the reuse benefit does.
- **Blocks:** Q10; whether structural fingerprinting alone can gate publication (the report
  argues it cannot, on reasoning, not measurement).
- **Answerable by:** Experiment 1, extended with cross-provider files.

---

## Tier 2 — Answer during Experiment 1

### UQ-4. Can grain change be detected without a declared key?

If no key is declared, is grain change detectable at all — e.g. from row-count ratios,
duplicate-fraction shifts, or aggregate multiplication? Or is a declared key strictly required?

- **Blocks:** whether grain declaration is mandatory in every task model (expensive, needs human
  input) or only recommended.
- **Answerable by:** Experiment 1's structural-drift variants.

### UQ-5. Does schema-reuse behaviour transfer from relational schemas to workbooks?

Corpus-based matching and meta-mappings are established over relational schemas. Workbook
structure adds header offsets, metadata blocks, merged cells, multi-sheet layouts and
non-tabular regions.

- **Blocks:** the design of the retrieval key (fingerprint) and the adapter-inheritance model.
- **Answerable by:** literature is silent; requires our own measurement once a corpus exists.
- **Partially answerable now:** the Meta-Mappings PVLDB PDF could not be text-extracted during
  this study. **It should be read properly before adapter inheritance is designed.**

### UQ-6. What is L4's detection floor, and what false-escalation rate does it cost?

Reframed by [amendment A2/A3](workorder_amendment_001.md). L4 produces *statistical evidence
relevant to applicability*; it is not semantic validation, and per non-claim **N1** it cannot
be. Two quantities are needed per provider and measure:

- **Detection floor** — the smallest definitional shift L4 separates from normal variation at
  95% confidence. This becomes a published property of the applicability contract.
- **False-escalation rate** at that floor, on real historical data. L4 cannot distinguish
  "definition changed" from "genuinely good month," so the floor and the alarm rate trade off
  directly.

- **Blocks:** whether gate trigger #5 (statistical discontinuity with no structural explanation)
  is usable or must be dropped.
- **Answerable by:** replaying L4 bands over archived historical deliveries.

### UQ-7. Is `Template`'s positional mapping salvageable?

Defect D1 (position-based rename and integer `usecols`) can be fixed by mapping strictly by
name, or by keeping position as a *fallback* with an evidence check. Which is correct depends
on how often real files have genuinely ambiguous or duplicate header names.

- **Blocks:** the amendment design for object B.
- **Answerable by:** inspecting real provider files for duplicate/blank header names.

---

## Tier 3 — Answer before scaling beyond ~50 providers

### UQ-8. Does adapter inheritance keep memory sublinear in provider count?

Does a family adapter + per-provider delta actually compress, or do real providers diverge
enough that every one needs a near-complete adapter?

### UQ-9. What does an escalation cost, and what does a new source family cost?

Needed for the cost-bounded escalation policy. No surveyed system reports escalation cost;
DeepPrep reports only that it achieves comparable accuracy at 15× lower inference cost than a
strong closed-source baseline, which is a per-task figure, not a per-escalation policy.

### UQ-10. ~~Can historical replay serve as ground truth without circularity?~~ — **PROMOTED to design constraint**

Resolved in principle by [amendment A5](workorder_amendment_001.md): baselines are tiered by
provenance (T0 procedure-generated → T3 human-confirmed), the tiers are **not one ranking**
(T2 is strong on aggregate correctness and blind to meaning; T3 is strong on meaning and blind
to coverage), and `periods_since_independent_anchor` is carried on every contract so a
self-generated baseline cannot masquerade as evidence.

**What remains open, and it is now a quantity rather than a question:**

- What is a tolerable `max_periods_since_anchor`? Too short and re-anchoring becomes a standing
  tax; too long and the self-certification loop reopens.
- Which external artifacts are actually available per provider to serve as T2 anchors — stated
  period totals, ERP control totals, settlement or payment figures? Availability varies by
  provider and is the practical constraint on the whole scheme.
- Does S-creep (Experiment 1) escalate before the anchor expires? If not, independent
  re-anchoring becomes a **scheduled obligation** rather than a triggered one — a recurring cost
  the business has to accept knowingly.

### UQ-11. Do humans give consistent semantic answers?

The human gate assumes a human can authoritatively answer "does this measure include freight."
Inter-rater agreement on measure definitions within one organisation is unmeasured and, in
practice, often poor. If two humans disagree, the gate produces inconsistent history.

---

## Questions closed by this study (recorded so they are not reopened)

| Question | Answer | Source |
| --- | --- | --- |
| Does `data-frame-tool` contain concepts lost in the evolution to `Data-tool`? | **No.** Zero unique definitions; strict file subset; merge conflict markers committed in 7 files | Direct inspection, [repo_reuse_map.md](repo_reuse_map.md) §4 |
| Do our repos already use an LLM anywhere? | **No.** Not in any of the four | Repository-wide search |
| Can an executable artifact replace the agent for repeated work? | **Yes**, established prior art in 5 systems | [falsification_ledger.md](falsification_ledger.md) H2 |
| Do prior schemas help with new sources? | **Yes**, established since 2005 | H3 |
| Does `Data-agents` have cross-run memory? | **No.** All artifacts are run-scoped; `adapter_schema_spec.json` must be placed by hand | `runtime/excel_flow.py` |
| Is applicability represented in any surveyed system? | **Essentially no.** Closest is query-side sufficiency gating in Executable Schema Contracts, and `expected_headers` in our own `Pipe-transformation` | Comparative table, Panel 3 |

---

## Sources that could not be fully read

Two PDFs failed text extraction during this study and are flagged so the gaps are not mistaken
for negative findings:

- **Meta-Mappings for Schema Mapping Reuse** (PVLDB 12(5), Atzeni, Bellomarini, Papotti,
  Torlone). Only the abstract-level claims were established. Its generalization/instantiation
  procedure is the closest formal prior art to adapter inheritance and **should be read before
  UQ-5 or UQ-8 is addressed.**
- **SheetEncoder / SpreadsheetLLM EMNLP camera-ready.** Module descriptions were recovered from
  a secondary review rather than the paper itself; the numbers cited (78.9 F1, ~25× compression,
  +25.6% ICL) come from the arXiv abstract and are reliable.
