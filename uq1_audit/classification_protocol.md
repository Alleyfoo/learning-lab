# UQ-1 — Retrospective Archive Audit Protocol

**Question:** how often do the conditions Experiment 1 measured actually occur in real business
data?

Experiment 1 asked what the warrant machinery *can* distinguish. UQ-1 asks *how often it
matters*. The two are orthogonal and must stay that way — see the contamination rules below.

**This is manual classification, not software.** The only code here is a summariser that runs
once rows exist.

---

## 0. Contamination rules — read before opening any file

| # | Rule |
| --- | --- |
| **R1** | **Classify by what actually changed, never by what would have been detected.** Scoring an event by whether the harness would have caught it bakes the mechanism's blind spots into the prevalence estimate and makes the combination step circular |
| **R2** | Do not use anything observed here to tune Experiment 1, its floor, its corpus, or its generator. Experiment 1's artifacts are frozen at `exp1-runA-final` and `detection_floor_v2.json` |
| **R3** | Record the **archive-access date** in `register.csv` when the first file is opened. Any change to Experiment 1's generator or corpus spec committed after that date must justify itself on grounds independent of the archive |
| **R4** | If you cannot determine a classification, use `unknown`. An honest `unknown` rate is a finding. A guessed classification is contamination |

---

## 1. Unit of observation

**One row per transition per provider**: delivery *N−1* → delivery *N*.

Not one row per file. The question is about *change events*, and a provider sending 24 identical
files produces 23 `unchanged` transitions — which is exactly the information needed.

Minimum useful sample: **one provider × 12 transitions**. Target: 3–5 providers × 12–24
transitions. More providers beats more periods; the between-provider variance is the thing that
decides whether source families are real.

---

## 2. Classification categories

Assign exactly one. Where several apply, take the **highest** in this list — a structural change
that also renames a header is `structural`.

| Code | Category | Definition | Examples |
| --- | --- | --- | --- |
| `unchanged` | Unchanged | Byte-identical structure; same sheets, headers, layout, types, grain | Same export, new month |
| `cosmetic` | Cosmetic / syntactic | Representation changed; meaning, grain and measure definition unchanged | Header renamed, columns reordered, sheet renamed, date format, decimal separator, casing |
| `structural` | Structural | Shape or grain changed | Sheet split, wide↔long, grain change, new join required, returns separated, column added/removed |
| `possible_semantic` | Possible semantic | Suspicion that a definition moved, **without** external evidence | Unexplained level shift; a total that no longer reconciles; a field that "feels" different |
| `semantic_confirmed` | Semantic, externally evidenced | Definition change **confirmed** by evidence outside the file | Provider email, ERP migration notice, contract change, finance confirmation |
| `unknown` | Unknown | Cannot be determined from available material | Files missing, no prior delivery, undocumented gap |

### The `possible_semantic` / `semantic_confirmed` boundary matters most

This split is the whole point of the audit. `possible_semantic` counts events where the system
would have had **only** a statistical signal — precisely the region N1 says is undecidable.
`semantic_confirmed` counts events where external evidence existed and could have been used.

The ratio between them estimates how much of the semantic class is reachable at all.

---

## 3. Fields to record per transition

See [`register_template.csv`](register_template.csv). Columns:

| Column | Values | Notes |
| --- | --- | --- |
| `provider_id` | free | Pseudonymise if the archive is sensitive |
| `source_system` | free / `unknown` | ERP or accounting package, if known. Feeds the source-family question |
| `from_period`, `to_period` | `YYYY-MM` | The transition |
| `classification` | one of §2 | |
| `what_changed` | free text | **Required.** One sentence. What actually moved |
| `evidence_source` | `none` / `email` / `erp_notice` / `finance_confirmation` / `contract` / `other` | What established a `semantic_confirmed` |
| `measure_shift_pct` | number / blank | Period-total change vs prior period, if computable. **Record it; do not classify on it** (R1) |
| `anchor_available` | `yes` / `no` / `unknown` | Was an independent anchor available for this period? |
| `anchor_type` | `ledger_reconciliation` / `human_confirmed_definition` / `accepted_output` / `payment_settlement` / `none` | |
| `grain_declared_would_catch` | `yes` / `no` / `n/a` | **Fill in a SECOND pass only**, after classification is locked |
| `notes` | free | |

`grain_declared_would_catch` is a detectability field. It is deliberately last and deliberately
second-pass, so it cannot influence the classification (R1).

---

## 4. Procedure

1. Record the archive-access date in the register header comment. Commit that before classifying.
2. Sort each provider's deliveries chronologically.
3. For each consecutive pair, open both and classify per §2. Fill `what_changed` in every row —
   including `unchanged` rows, where it reads "no change".
4. Record `anchor_available` / `anchor_type` honestly. "We could have reconciled this if we'd
   thought to" is `no`.
5. **Only after all rows are classified and committed**, do a second pass for
   `grain_declared_would_catch`.
6. Run `python uq1_audit/summarize.py` for the distribution.

---

## 5. What the result decides

| If the archive looks like | Then |
| --- | --- |
| ~95% `unchanged` + `cosmetic`, near-zero semantic | The economically correct system is L0–L2 plus a synonym store. **Report that plainly and do not build the rest.** Impressive machinery solving a rare problem |
| Frequent `structural`, recurring `semantic_confirmed`, ERP changes, grain changes | The modelling network has a concrete reason to exist and the human gate is the product |
| High `possible_semantic` relative to `semantic_confirmed` | Most semantic change is *unreachable* — external evidence channels matter more than better detection |
| `anchor_available` mostly `no` | Reconciliation freshness is not implementable as designed. This would be the most consequential negative finding, because the whole self-certification guard depends on anchors existing |

**All four are acceptable results. The distribution is the deliverable, not a hurdle.**

---

## 6. Data required — not currently in this repository

Nothing here can run without archived provider deliveries. To proceed:

- 12–24 months of archived files from **at least one**, ideally 3–5, real providers.
- Any correspondence that would establish `semantic_confirmed` (emails, migration notices).
- Whatever external totals exist for `anchor_available` (ledger figures, settlement reports).

Handle according to whatever confidentiality applies; `provider_id` may be pseudonymised and
`what_changed` written without commercial detail. The classification does not require the values,
only the structure and the definitions.
