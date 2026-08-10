# Experiment H — Reference-Vocabulary Header Location: Preregistration

**Frozen before any run.** Expected answers in `experimentH/expected.json` (hidden
from the locator LLM). Reference vocabulary in `experimentH/reference/months.json`.
Fixtures frozen in `experimentH/fixtures/` (H1, H2, H3b) and reused by path (H3a =
the frozen 2B/3A A1 fixture, unmodified).

## The question

> Given a known reference vocabulary (the 12 Finnish month names), can a locator
> agent find the row containing that vocabulary in a source, tolerating harmless
> formatting variation — with a deterministic gate that escalates to HUMAN when no
> row covers the reference set?

This is a deliberate change of framing from the 3A–3E programme. 3A–3E asked the
model to *infer* what months are and then *classify* each cell, which invited a
closed-world lexical prior (`Jakso A` doesn't look like a month → `not_month`).
H asks the model to *locate* a supplied vocabulary, which removes the inference.
The reference IS the world; the model's intelligence is spent on finding how
somebody represented the known concepts in a messy file, not on rediscovering
January.

## The architectural realization

> **Reference knowledge doesn't need to be intelligence.** We already know what
> the months are. The intelligent part is finding how somebody represented them
> in Tuesday's horrible Excel file.

Division of labour (frozen):

```text
REFERENCE DATA  (known months / known concepts)        -- supplied, not inferred
        |
        v
AGENT          (find where/how those concepts appear  -- the LLM earns its keep
                 despite harmless representation differences)
        |
        v
DETERMINISTIC CODE (use the identified row/columns    -- mechanical
                    mechanically; verify coverage)
```

## What is frozen, what is new

- **Frozen (new, authored for H):** the reference vocabulary (12 names), the H1/H2/H3b
  fixtures, the deterministic gate logic, the match functions, the success criteria.
- **Frozen (reused by path, unmodified):** the A1 fixture from Experiment 2B
  (used as the H3a safety case). sha256 `64356f..`, header row 4.
- **New:** the locator contract (find-the-row, not classify-the-cell); the
  deterministic-first routing; the tolerant-coverage verification gate.

## Architecture as run

```text
supplied reference vocabulary (12 Finnish month names)        -- the "world"
        |
        v
deterministic-first scan (exact_match, case-insensitive, trimmed, full-token)
        |   any row covers all 12?  --> YES: that row is the answer; LLM NOT invoked
        |                           --> NO: continue
        v
locator LLM (GLM-5.2, fresh isolated context):
   "find the single row whose cells cover the supplied reference set, allowing
    harmless formatting variation; if no such row can be identified, ask_human."
        |
        v
LLM returns {"header_row": r} or {"ask_human": true}
        |
        v
DETERMINISTIC VERIFICATION GATE (code, not LLM; AUTHORITATIVE):
   tolerant-coverage of the claimed row r (count references present under
   tolerant_match; suffix-tolerant prefix + non-letter boundary)
        |   coverage == 12 --> accept row r
        |   coverage < 12  --> ask_human, REGARDLESS of what the LLM said
        |   (LLM ask_human / parse failure --> ask_human)
        v
final gated output: {"header_row": r, "source": ...} or {"ask_human": true}
```

No LLM participates in the deterministic-first scan or the verification gate.
The gate is ordinary code in `harness/gate_H.py`.

## Non-scoring diagnostic — counterfactual all-row tolerant scan

> If the deterministic tolerant-coverage gate can compute "12/12" for an
> arbitrary row, it could presumably scan every row itself.

After grading each fixture, apply the frozen `tolerant_match` coverage function
to **every row** and record:

- the rows reaching 12/12
- whether the max-coverage row is unique

This diagnostic **does not affect the H result.** It answers a separate
question: *could a tolerant deterministic locator have found the row without the
LLM?* Two outcomes, both useful:

- If the scan uniquely reaches 12/12 on the accepted row → the LLM was
  **correct, but not needed**. The engineering conclusion is to automate the
  provider with the tolerant deterministic locator. The LLM still had to
  *propose* the row for the gate to authorize it, so the run is not wasted — it
  taught us the task is already deterministic.
- If the scan produces several candidate rows (or none) while the LLM correctly
  identifies the header → the LLM adds genuine discriminatory value that the
  deterministic locator lacks.

Either result is informative. The diagnostic is recorded per probe in
`results/H.json` under `counterfactual_tolerant_scan`. It never changes `h*_ok`
or the pass flags.

## What H2 does and does not establish (stated before the run)

H2 requires `source == llm_accepted` for `h2_ok` — the LLM must **propose** the
row and the gate must **authorize** it. That establishes:

> The LLM can propose the correct row, and deterministic evidence can authorize
> that proposal.

It does **not** establish:

> The LLM was needed to find the row.

Whether the LLM was needed is decided by the counterfactual scan above. If H2's
accepted row is uniquely 12/12 under the tolerant scan, the honest reading is:
the LLM works, but the provider's monthly workflow can be automated with the
tolerant deterministic locator. That is a successful outcome of the experiment,
not a failure — the agent helped discover that the task is already
deterministic.

## Why deterministic-first is a positive control, not an aside

If a row contains all 12 reference strings exactly, we do not need the LLM. The
deterministic-first path is the realistic production path: it handles the boring
case (and trivial casing/spacing variation) without an LLM call. The LLM is
invoked only on the genuinely dirty case (H2). H1 therefore tests that the
deterministic path *solves the clean case and does not invoke the LLM*; H2 tests
that the LLM earns its keep when exact match fails. `source` in the gate output
records which path won.

## The deterministic gate (frozen logic)

```text
# step 1 — deterministic-first (exact_match: case-insensitive, trimmed, full-token)
for each row:
    if count(reference months present via exact_match) == 12:
        return that row; LLM not invoked

# step 2 — LLM invoked (only when no exact 12/12 row)
if LLM says ask_human:        -> ask_human (reason: llm_asked)
r = LLM.header_row
if r invalid:                  -> ask_human (reason: llm_parse_failure)

# step 3 — verification (tolerant_match: suffix-tolerant prefix + non-letter boundary)
cov = count(reference months present in row r via tolerant_match)
if cov == 12:                 -> accept row r (source: llm_accepted)
else:                         -> ask_human (reason: gate_coverage_short, coverage: cov)
```

This gate is the **3E comparison-gate transposed**. In 3E the gate compared the
specialist's classification to the reviewer's verdict; here it verifies a
checkable property (reference coverage) of the LLM's claimed row. The principle
is identical: **deterministic code owns authority; an unsupported claim cannot
acquire it.** On H3b (11/12 interloper), a model that confidently picks the row is
overridden to `ask_human` — the same safety property 3E established, applied to
row-location instead of cell-classification.

## The probes (four, frozen)

| ID | Fixture | Description | Expected final |
| --- | --- | --- | --- |
| **H1** | `fixtures/H1.csv` | clean: all 12 reference months appear exactly, row 4 | `header_row=4, source=deterministic, llm_invoked=false` |
| **H2** | `fixtures/H2.csv` | realistic: 12 months suffixed (`Tammi 2026`, …), row 4; exact match fails | `header_row=4, source=llm_accepted, coverage=12` |
| **H3a** | `../experiment2b/fixtures/A1.csv` (frozen, by path) | partial-coverage: the 3A failure fixture; row 4 has 4/12 + interlopers | `ask_human=true, coverage=4` |
| **H3b** | `fixtures/H3b.csv` | interloper: 12 month-slots but `Jakso A` replaces Maalis, row 4; 11/12 | `ask_human=true, coverage=11` |

### Why these four

- **H1 + H2** are the clean/dirty pair. Same fixture layout, same header row,
  same 12 concepts; the **only** difference is representation (exact vs suffixed).
  Isolate-one-variable, per programme discipline. H1 should be solved
  deterministically (no LLM); H2 should require the LLM and be accepted via the
  gate. This is the existence test: can the locator + gate handle the realistic
  dirty case the deterministic path cannot.
- **H3a** is the frozen 3A failure fixture, repurposed. Under the reference-location
  framing with a 12-name reference, A1 row 4 covers only 4/12 → `ask_human`. The
  exact fixture where 3A failed now escalates. This closes the loop: the disease
  3A–3E fought (silent omission / over-assertion) is, in the new framing, caught
  by the coverage gate.
- **H3b** is the direct transpose of the 3A `Jakso A` failure: a row that *looks*
  like a full 12-month header but one slot is an interloper (`Jakso A`) and one
  month (`Maalis`) is absent → 11/12. A confident model may pick row 4; the gate
  counts 11/12 < 12 and overrides to `ask_human`. This is the load-bearing safety
  test — the one that proves the gate, not the model, owns authority.

H3a and H3b are **designed in this freeze but run after H1/H2** (per the designer's
"tiny first" ordering). Their design, expected answers, and decision-table rows
are frozen now so the safety test is not designed post-hoc in light of H1/H2
results.

### Why suffix variation for H2 (not casing/spacing)

The designer named casing/spacing/suffixes/abbreviations as the "harmless
variation" axis and chose "controlled first, mess later." This freeze varies
**one** kind: suffixes (`Tammi 2026`). Rationale: casing and spacing are so
trivial that a realistic deterministic-first path (case-insensitive, trimmed)
solves them without the LLM — so they don't test where the LLM earns its keep.
Suffixes defeat exact match (no cell *equals* `Tammi`), genuinely require the
LLM to locate, and have a crisp tolerant-verification rule (reference is a prefix
followed by a non-letter). Abbreviations (`Heinä`/`Heinäkuu`) are messier and
two-directional — deferred to H2b.

### Distractor rows

H1/H2/H3b each include a partial-month distractor row (`Q1,Tammi,Helmi,Maalis`,
3/12) at a different row than the header, so "find the row" requires
discriminating the full-coverage row from a partial one — and so the gate can
demonstrate overriding a wrong partial pick (self-test case `H2-wrong-partial`:
model picks the 3/12 row → gate → `ask_human`).

## Success criterion (frozen)

> `H1 final header_row==4 AND H2 final header_row==4 AND H2 source==llm_accepted`
> AND `H3a ask_human==true AND H3b ask_human==true`.

The `H2 source==llm_accepted` clause is load-bearing: if the deterministic-first
path solved H2, the fixture is too easy (or `exact_match` is too loose) and the
LLM never earned its keep — that is a `FAIL_h2_deterministic_solved`, not a pass.

## Decision table — declared before running

| Outcome | Reading |
| --- | --- |
| `h1_h2 AND h3` | **PASS.** Locator + deterministic gate handle clean, dirty, and partial/interloper cases. Reference-knowledge-as-lookup + LLM-as-locator + deterministic-authority works. |
| H1/H2 pass, H3 fails | **FAIL — safety gate did not transpose.** The gate does not catch short coverage; the 3E principle did not carry over. Inspect match function / threshold. |
| H3 passes, H1/H2 fail | **FAIL — locator broken.** Safety gate works but the LLM cannot find clean/dirty rows, or deterministic-first routing is wrong. |
| H2 `source==deterministic` | **FAIL — H2 too easy.** Deterministic-first solved the suffix case; LLM never invoked; fixture or `exact_match` too loose. |
| nothing | **FAIL — architecture mis-designed.** Inspect per-probe gate outputs. |

The counterfactual tolerant scan is recorded alongside every probe and is
**non-scoring**. A PASS with H2's accepted row uniquely 12/12 under the tolerant
scan reads as: the locator+gate works, *and* the provider can likely be
automated deterministically (delete the LLM). A PASS with the tolerant scan
ambiguous (multiple candidate rows) reads as: the LLM adds genuine
discriminatory value. Both are useful; the scan decides which.

## Hard stop — scope ruling for the H line (carried from 3A–3E, with a ruling)

The carried hard stop forbade: normalization; Python transformation generation;
country mappings; numeric parsing; multiple sheets; joins; reusable procedure
synthesis.

**Ruling (stated for review; correctable at freeze review):** H1/H2/H3 as
designed stay *within* the carried hard stop:
- Supplying a month reference list is **not** "country mappings" (it is input to
  a probe, not a production country-normalization system).
- The locator is asked to **find a row**, not to output normalized values, so it
  is **not** "normalization" in the forbidden sense.
- No transformation code, no numeric parsing, no multiple sheets, no joins, no
  procedure synthesis is built.
- The deterministic gate is verification code (count references), not a
  transformation generator.

The broader "known countries, known concepts" generalization and any production
architecture are **out of scope** for this freeze and would revisit the hard stop
separately. The H line is a probe of the reference-location framing on one
concept class (months) with four fixtures — not a production system.

If this ruling is wrong, redirect at freeze review; nothing has been run.

## Model / invocation (frozen)

- Locator: GLM-5.2 (the session model), fresh isolated agent calls
  (general-purpose), one per probe, four run — structural independence.
- Contract: "Given the supplied reference month names and the source rows below,
  identify the single row whose cells cover the reference set, allowing harmless
  formatting variation (e.g. suffixes, casing). Output JSON: `{\"header_row\": <int>}`
  or `{\"ask_human\": true}`. If no row covers the reference set, return ask_human."
- No handed *classification*; the model is handed a *vocabulary* and a *location task*.
- The reference list and the rendered source rows are the only inputs per probe.

## Stated limitations (declared before running)

- **One run per probe, one model (GLM-5.2), no seed control.** Cannot distinguish
  *always* from *once*. Existence test, not reliability.
- **Single variation kind (suffixes).** Casing/spacing/abbreviation are later H2b.
- **Accept threshold is full coverage (12/12).** A real table that legitimately
  drops a month would escalate. Graduated thresholds are a later H probe.
- **`tolerant_match` is suffix-specific** (prefix + non-letter boundary). Other
  variation kinds need their own tolerant_match.
- **The locator sees the reference list**, so "locating" partly reduces to
  substring matching; the interesting part is the LLM tolerating the suffix while
  discriminating the full row from the partial distractor.
- **H3a (old A1) is a different table shape** (6 cols, 4 months), not a 12-month
  table missing months; escalating it is correct but is "reference set mostly
  absent," not "one interloper among twelve." H3b is the sharper interloper test.
- **The gate is new code**, simple and deterministic, auditable in
  `harness/gate_H.py`; its logic was dry-run-verified over seven input
  combinations before the real run.