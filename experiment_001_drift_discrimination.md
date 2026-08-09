# Experiment 1 — Drift Discrimination Harness

**Recommended as the single first experiment.** Build authorization for this experiment only;
the agentic modelling network remains unauthorized.

**Contains no LLM and no agents.** That is deliberate.

---

## 1. The question it answers

> Can a published task model's declared applicability predicates correctly discriminate
> "this source still matches" from "escalate", and does the *failing predicate* identify the
> *true drift class* — without falsely accepting semantically drifted input?

This is the one unanswered question that gates every other design decision. If declared
applicability cannot discriminate drift classes, no amount of agent sophistication helps,
because the work plane cannot tell when to call for help. The escalation trigger is upstream of
the escalation handler.

**It directly tests H1** (is `Template` rich enough?) **and H4** (are most changes resolvable
without human semantic input?), and it produces the measurements behind Q5 and Q6.

---

## 2. Why this and not something else

| Candidate first experiment | Rejected because |
| --- | --- |
| Build the modelling network and see if it produces good templates | Tests H2/H6, both already established; expensive; a positive result would not tell us when to reuse the output |
| Retrieval/fingerprint index over many providers | Depends on knowing which predicates discriminate — that is this experiment |
| LLM-based semantic interpretation of headers | Prior art is dense (Harmonia, Flatfile); low information yield |
| End-to-end pilot on one real provider | Confounds generation quality with applicability; a single success proves nothing (workorder §2) |

This experiment is days of work, not weeks; needs no new architecture; and its **negative
result is as informative as its positive one**.

---

## 3. Design

### 3.1 Amendments required first (minimal)

Extend the `Template` artifact with two declared blocks. No behaviour change to the existing
transform path.

```jsonc
{
  // ... existing Template v3 fields unchanged ...

  "applicability": {
    "L0_fingerprint": {
      "sheet_names": ["Myynti", "Tuotteet"],
      "sheet_count": 2,
      "filename_pattern": "^sales_\\d{4}_\\d{2}\\.xlsx$",
      "producing_application": "SAP NetWeaver"        // from workbook metadata
    },
    "L1_structural": {
      "sheet": "Myynti",
      "header_row": 3,
      "column_names": ["Tuotenro", "Nimi", "Kpl", "Summa"],   // multiset, order-insensitive
      "column_count": 4,
      "required_columns": ["Tuotenro", "Summa"]
    },
    "L2_typing": {
      "Tuotenro": { "dtype": "string",  "null_rate_max": 0.01, "cardinality_min": 50 },
      "Summa":    { "dtype": "float",   "null_rate_max": 0.02 },
      "Kpl":      { "dtype": "int",     "null_rate_max": 0.02 }
    },
    "L3_grain": {
      "key": ["Tuotenro", "report_date"],
      "key_must_be_unique": true,
      "row_count_band": [800, 2400]
    },
    // L4 = statistical evidence RELEVANT TO applicability.
    // It is not semantic validation. See non-claim N1 (amendment A2/A3).
    "L4_statistical_evidence": {
      "period_total_band_pct": 0.35,          // vs. trailing accepted periods
      "negative_row_share_band": [0.00, 0.06],
      "cross_field": [
        { "expr": "abs(Summa - Kpl * unit_price) / Summa", "max": 0.01, "coverage_min": 0.95 }
      ],
      "detection_floor": {                    // published property, amendment A3.1
        "period_total": { "min_detectable_shift_pct": 3.2, "confidence": 0.95 }
      },
      "baseline_provenance": {                // amendment A5.1
        "periods_in_baseline": 14,
        "highest_tier_in_baseline": "T2",
        "periods_since_independent_anchor": 6,
        "max_periods_since_anchor": 12        // exceed -> escalate for re-anchoring
      }
    },
    "L5_semantic_assertions": [
      { "claim": "Summa excludes freight",     "evidence": "provider email 2025-11-03", "confidence": "human_confirmed" },
      { "claim": "Summa excludes VAT",         "evidence": "reconciled to invoice totals 2025-12", "confidence": "derived" }
    ]
  },

  "invariants": {
    "row_count_nonzero": true,
    "no_all_null_measure_column": true,
    "period_coverage": "exactly_one_month"
  }
}
```

L0–L4 are machine-decidable. **L5 is deliberately not checkable** — it is carried so that a
detected L4 anomaly can be reported *against a stated assumption*, and so that an external
event (provider changes ERP → L0 `producing_application` changes) can invalidate it.

### 3.2 The drift corpus

Start from one real provider layout (or `Data-tool`'s existing
`data/archive/multi_sheet_jan.xlsx`, `offset_header.xlsx`, `consistent_schema_feb.xlsx` if no
real file can be used). Generate variants programmatically so ground truth is exact.

| Class | Variants (minimum) |
| --- | --- |
| **Control** | Unchanged file; same file, next period |
| **Cosmetic** | Header renamed (`Summa`→`Myynti EUR`); columns reordered; sheet renamed; date format `31.01.2026`→`2026-01-31`; decimal comma→point; extra whitespace/casing |
| **Structural** | One sheet split into two; wide monthly → long; **an extra column inserted before a mapped column** (the D1 trap); grain change (per-invoice-line instead of per-article-month); returns moved to a separate sheet; header row moved by 2 |
| **Semantic** — see §3.2.1, **both detectability cases are mandatory** | **S-obvious**: `Summa` redefined to include freight where freight ≈ 8% of revenue; **S-invisible**: same redefinition where freight ≈ 0.4% — below the noise floor; **S-creep**: the 0.4% redefinition sustained over 6 periods; `Kpl` changed from units to cases (÷12); date changed from invoice date to posting date (values shift only across month boundaries) |
| **Adjacent-provider** | A *different* provider's file from the same source family (tests UQ-3 false-apply) |

Target ≈ 25–35 variants. Every variant carries a ground-truth label: `(applies | drifted)` and
`drift_class ∈ {none, cosmetic, structural, semantic}`.

### 3.2.1 The semantic variants must span both detectability cases

Amendment A7. Without this, the experiment risks "solving" semantic drift by constructing only
convenient examples.

| Variant | Construction | Expected result |
| --- | --- | --- |
| **S-obvious** | Freight ≈ 8% of revenue — well above period-to-period variation | L4 escalates. Establishes L4 has non-zero power |
| **S-invisible** | Freight ≈ 0.4% — below the noise floor | **L4 does not escalate. This is a correct result and must be reported as a success of the experiment design, not a failure of the method** |
| **S-creep** | The 0.4% redefinition sustained across 6 periods | Tests whether reconciliation freshness (A5.1) catches cumulative divergence from an external anchor that per-period L4 never sees |

S-invisible is the variant that **measures** non-claim N1 rather than assuming it, and it is
what calibrates the published detection floor. S-creep tests the one mechanism that might
recover ground lost to N1 without external supervision every period.

### 3.3 The harness

Pure Python, deterministic, no LLM:

```
for each variant file:
    for each level in [L0, L1, L2, L3, L4]:
        evaluate predicates -> pass / fail(predicate_id, observed, expected)
    verdict   = APPLIES if all levels pass else ESCALATE
    predicted_class = classify(first failing level)
        L0/L1 -> structural-or-cosmetic (disambiguate via name/type/value-overlap agreement)
        L2    -> cosmetic (format) or structural
        L3    -> structural (grain)
        L4    -> semantic-suspect
    emit escalation object {variant, verdict, failing_predicates, observed vs expected, trace}
```

The escalation object is the second deliverable of the experiment: it is the concrete proposal
for the modelling plane's input contract, produced from evidence rather than from design
intuition. `Data-tool`'s existing `_build_validation_report` (`src/pipeline.py:87-117`) and
quarantine writer are the starting point.

---

## 4. Measurements

**Primary — the one the experiment exists for:**

| Metric | Definition | Prediction |
| --- | --- | --- |
| **False-apply rate on semantic variants** | semantic variants judged `APPLIES` ÷ semantic variants | **100% with L0–L3 only.** With L4: **S-obvious caught, S-invisible not caught** |
| **Published detection floor** | smallest definitional shift L4 separates from normal variation at 95% confidence, per measure | A number, e.g. ±3.2% of period total. This is the deliverable that makes N1 usable |
| **S-creep recovery** | does reconciliation freshness escalate S-creep before period 6? | Unknown — this is the genuinely open sub-question |

Two things are being measured here, and only one of them is a capability.

The predicted 100% false-apply under L0–L3 converts "structural predicates cannot see semantic
change" from an architectural argument into a measurement, and establishes the marginal value of
L4 — the most expensive layer to build and the only one requiring retained history.

**The S-invisible result is not a capability measurement. It is a boundary measurement.**
It should come out negative, and reporting it as a failure would be a misreading. Its purpose is
to calibrate the detection floor, so that every published contract can state what magnitude of
definitional change it is blind to. That number is what lets a human be asked the right question
at the right time, instead of being asked everything or nothing.

**Secondary:**

| Metric | Definition |
| --- | --- |
| Detection rate per drift class | escalated ÷ total, per class |
| Class-attribution accuracy | predicted class == true class, given escalation |
| False-escalation rate | control + cosmetic variants escalated when they should self-heal |
| Predicate attribution precision | does the *first failing* predicate name the actual change |
| Cross-provider false-apply | adjacent-provider files judged `APPLIES` (UQ-3) |
| Cosmetic self-heal rate | cosmetic variants resolvable by synonym + type + value-overlap agreement, without escalation — using the existing `config.yaml` synonym store |
| **D1 confirmation** | does the inserted-column variant currently succeed and produce shifted output under `Template` v3? |

---

## 5. Decision rules set in advance

Committing to these before running the experiment, so the result cannot be reinterpreted after
the fact:

| Outcome | Interpretation | Next action |
| --- | --- | --- |
| Cosmetic + structural detection ≥ 90%, class attribution ≥ 80%, cosmetic self-heal ≥ 50% | Declared applicability works. The work plane can decide when to escalate | Proceed to design the escalation contract and modelling plane |
| Structural detection high but grain change missed | L3 needs a declared key and it cannot be optional | Make grain declaration mandatory; revisit the human-gate cost |
| L4 catches **S-obvious** at a tolerable false-escalation rate (< ~15% on controls) | Statistical evidence is worth its cost, within its floor | Build history retention; publish the detection floor on every contract |
| L4 misses **S-invisible** | **Expected. N1 confirmed empirically** | Report the detection floor as a contract property; route sub-floor questions to external evidence. Not a failure |
| L4 *catches* S-invisible | **N1 challenged** — investigate before believing it; most likely an artefact of corpus construction | Re-examine whether the variant was genuinely sub-floor before claiming anything |
| L4 false-escalation rate is intolerable | Trigger #5 is unusable; semantic change needs external evidence only | Redesign the human gate around source-system change events; **this materially weakens the whole programme and must be reported as such** |
| Reconciliation freshness escalates **S-creep** before period 6 | Cumulative divergence recovers some of what per-period L4 cannot see | Make `periods_since_independent_anchor` mandatory in every contract |
| S-creep never escalates | Sustained sub-floor drift is undetectable without periodic external anchoring | Independent re-anchoring becomes a **scheduled obligation**, not a trigger — a recurring cost the business must accept |
| Cross-provider false-apply is non-trivial | Structural fingerprinting cannot gate publication at scale | Publication must depend on L3+L4, not L1. Revisit Q10 before any multi-provider work |
| Detection is poor across the board | Declared applicability over `Template` is not viable | **STOP.** Reconsider the artifact from scratch before building any agent |

---

## 6. Scope boundaries

**In scope:** the applicability/invariant blocks, the drift corpus generator, the deterministic
harness, the escalation object, the measurements above.

**Explicitly out of scope:** any LLM or agent; the retrieval/fingerprint index; adapter
inheritance; multi-provider onboarding; modifying `Data-tool`, `Data-agents`,
`Pipe-transformation` or `data-frame-tool`; any production integration; the Streamlit UI.

Fix defect **D1** (positional mapping, `src/templates.py:484-500`) inside the lab copy only —
the inserted-column variant exists specifically to demonstrate why, and the fix must not be
pushed to `Data-tool` under this authorization.

---

## 7. Deliverables of Experiment 1

1. `applicability_schema.md` — the amended artifact specification, as validated or corrected by results.
2. Drift corpus generator + the corpus itself (checked in; deterministic seed).
3. The harness and its results table.
4. `escalation_object.md` — the modelling plane's input contract, derived from observed failures.
5. A short results memo answering §5's decision rules, and updating
   [falsification_ledger.md](falsification_ledger.md) H1 and H4 with measured evidence.

Only after (5) should a build workorder for the modelling plane be considered.

---

## 8. Parallel non-experiment task

**Start the UQ-1 retrospective audit now, alongside this experiment.** Classify 12–24 months of
archived provider deliveries into cosmetic / structural / semantic change events. It requires no
software, it is the highest-value unknown in the whole study
([unanswered_questions.md](unanswered_questions.md) UQ-1), and Experiment 1's L4 design will be
much better informed if even a partial distribution exists when the results are read.
