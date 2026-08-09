# Build Notes — Reuse Assessment

Recorded per instruction: inspect the old code first, copy only what saves real
implementation or testing effort, otherwise write fresh. **No compatibility with the old
repositories is preserved.** Compatibility is plumbing tax and nothing here needs it.

Inspected: `Alleyfoo/Data-tool` @ `ab10b8c`.

---

## Copied

| Piece | Source | Why |
| --- | --- | --- |
| **Synonym vocabulary** (5 canonical fields) | `src/config.yaml` `synonyms:` | Genuine domain data, not machinery. Hard-won real-world header vocabulary including Finnish/Swedish/German terms. Using it as the rename vocabulary for cosmetic variants means the self-heal test runs against terms a real provider might actually send, rather than terms I invented to be easy. Copied as **data only**, into [`spec/rename_vocabulary.json`](spec/rename_vocabulary.json) |

That is the entire list.

All five of the baseline's columns map cleanly onto that vocabulary
(`article_sku`, `report_period`→`report_date`, `quantity`→`sales_qty`,
`amount`→`sales_amount`, `unit_price`), so no invention was needed.

---

## Deliberately not copied

| Piece | Source | Reason |
| --- | --- | --- |
| `auto_map_columns` | `src/core.py:253` | ~30 lines, but greedy and dict-order-dependent: `used_targets` plus a `break` on first substring hit means "Total units sold" resolves by whichever of `sales_amount`/`sales_qty` iterates first. More importantly it matches on **name only**. The experiment requires three-way corroboration (name + type profile + value overlap) before accepting a rename, which Data-tool does not do at all. A fresh 25-line implementation is smaller than the port-plus-fix |
| `filter_and_rename` | `src/templates.py:484` | Carries defect **D1** — renames by positional index when `headers` is populated. That is the exact false-apply generator the experiment exists to measure. Porting it would be importing the bug under test |
| `normalize_excel_headers` | `src/templates.py:406` | openpyxl merged-cell expansion. There is no Excel in this experiment; the corpus is CSV/DataFrame-level. Zero applicability |
| `guess_header_row` | `src/services/header_detection.py:16` | Header *detection*. The warranted procedure **declares** `header_row` in its L1 contract; the harness never infers it. Detection is a modelling-plane concern and there is no modelling plane here |
| `warn_on_schema_diff` | `src/api/v1/engine.py:94` | Computes missing/extra column sets at runtime and logs a warning. `engine._check_l1` already does this contract-driven and returns structured failures instead of log lines. Fewer lines, and the result is machine-readable |
| `_coerce_field_types` | `src/api/v1/engine.py:18` | Coercion with failure counts. `engine._check_l2` is contract-driven and only needs to *detect*, not coerce — the harness must never repair the data it is judging |
| `schema_candidates.*` | `src/services/schema_candidates.py` | Numeric-block detection, month-token normalisation, candidate ranking. All of it *infers* structure. Contracts here declare structure. Excellent code, wrong layer |
| `samples/generate_samples.py` | `samples/` | Hardcoded 2-row fixtures, not parameterised mutation. The corpus needs variants whose magnitude is a function of the committed detection floor. Nothing reusable beyond the variant *catalogue* — offset header, merged header, split year/month, multi-sheet — which is already reflected in the preregistered corpus list |
| `Template` / `.df-template.json` | `src/templates.py` | A reader configuration with a different lifetime and no applicability, grain, evidence or provenance. The warranted procedure is a different artifact. Bridging the two would be pure plumbing tax with no measurement value |
| pandera `OutputSchema` | `src/schema.py` | Four optional columns with `strict=False`; cannot fail on a wrong-but-well-formed table. The L1–L3 checks are stricter and are the thing under test |

---

## Idea taken, code not

`samples/expected.json` pairs each `file::sheet` with `expected_headers` and, for the offset
case, `expected_header_row`. That is the same shape as an L1 predicate and is quiet
confirmation that the applicability idea was already latent in the old repo. The L1 contract
supersedes it; nothing was copied.

---

## Net effect

One JSON file of vocabulary, ~60 lines of data. Everything else is written fresh against the
warrant model. The harness has no import from, and no format compatibility with, any of the
four existing repositories.
