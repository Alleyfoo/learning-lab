# Experiment H — Reference-Vocabulary Header Location: Result

**PASS — `overall=True`.** The reference-location framing works, and the
counterfactual scan shows the whole line collapses to a deterministic recipe.
The LLM was correct in all four probes but necessary in none.

```text
H1   clean 12-month row          deterministic-first: row 4        (LLM not invoked)
H2   suffixed 'Tammi 2026'         LLM proposed row 4 -> gate 12/12  (accept)
H3a  frozen 3A A1 fixture (4/12)  LLM returned ask_human            (ask_human)
H3b  11/12 + 'Jakso A' interloper LLM returned ask_human            (ask_human)

h1h2_pass=True   h3_pass=True   overall=True
```

This is a deliberate change of framing from the 3A–3E programme. 3A–3E asked the
model to *infer* what months are and classify each cell, which invited the
closed-world lexical prior 3C located (`Jakso A` doesn't look like a month →
`not_month`). H supplies the 12-month reference vocabulary and asks the model
to *locate* the row containing it, tolerating harmless variation. Reference
knowledge is a lookup, not intelligence; the model's intelligence is spent on
finding how somebody represented known concepts in a messy file.

---

## The architecture (frozen)

```text
supplied reference vocabulary (12 Finnish month names)        -- the "world"
        |
        v
deterministic-first scan (exact_match: case-insensitive, trimmed, full-token)
        |   any row covers all 12?  -> YES: that row is the answer; LLM NOT invoked
        |                            -> NO: continue
        v
locator LLM (GLM-5.2, fresh isolated context): find the single row covering
        the reference set (harmless formatting variation allowed), or ask_human
        |
        v
DETERMINISTIC VERIFICATION GATE (code, not LLM; AUTHORITATIVE):
        tolerant-coverage of the claimed row (suffix-tolerant prefix match)
        coverage == 12 -> accept;  < 12 -> ask_human, REGARDLESS of the LLM
        (LLM ask_human / parse failure -> ask_human)
```

The gate is the **3E comparison-gate transposed**: the model claims a result;
code checks a verifiable property (reference coverage); an unsupported claim
cannot acquire authority. On H3b (11/12 interloper), a model that confidently
picks the row is overridden to `ask_human` — the same safety property 3E
established, applied to row-location.

## The non-scoring counterfactual scan — the key finding

After grading, the frozen `tolerant_match` coverage function was applied to
**every row** of every fixture (non-scoring). The result:

| Probe | Counterfactual: rows reaching 12/12 | max coverage |
| --- | --- | --- |
| H1 | row 4, **unique** | 12 |
| H2 | row 4, **unique** | 12 |
| H3a | none | 4 (row 4) |
| H3b | none | 11 (row 4) |

A tolerant deterministic locator — with no LLM — would correctly handle all
four cases:

```text
H1  row 4 unique 12/12 -> accept
H2  row 4 unique 12/12 -> accept (suffix absorbed by tolerant match)
H3a no row at 12 (max 4)  -> ask_human
H3b no row at 12 (max 11) -> ask_human (interloper not silently upgraded to 12)
```

So the **entire H line collapses to a deterministic recipe**:

> Find the row whose tolerant-coverage of the reference vocabulary == 12. If
> exactly one such row exists, accept it. If none exists, ask_human. (If
> several, the LLM adds the discriminatory value the deterministic locator
> lacks — not exercised by these four fixtures.)

The LLM was correct in all four probes but necessary in none. This is the
**"Excel macro saver"** outcome, fully realized:

```text
first weird provider file
  -> agent inspects
  -> discovers "this row is the monthly header"
  -> observable rule turns out to be: tolerant match against the known
     12-month vocabulary, coverage == 12
  -> save as deterministic provider logic
  -> future files use the saved rule (no intelligence paid)
```

The agent solves the unfamiliar instance once; the solution collapses into a
stable rule; we save the rule and stop paying intelligence for repetition. H
ran the agent on the four instances precisely to discover that the rule is
stable and the agent can be deleted from the runtime.

## The four findings

### 1. H1 — exact format is a deterministic macro

Row 4 uniquely covers all 12 references exactly. The deterministic-first path
solved it without invoking the LLM. This is the boring case: when the
spreadsheet literally contains the known strings, deterministic code wins and
no intelligence is owed.

### 2. H2 — harmless suffix variation is absorbed by the tolerant macro

The 12 months appear as `Tammi 2026`, `Helmi 2026`, … — exact match fails, so
the LLM was invoked and proposed row 4; the gate verified tolerant coverage
12/12 and accepted. H2 establishes that the LLM *can* propose the correct row
and the gate *can* authorize it. It does **not** establish the LLM was needed:
the counterfactual scan shows row 4 is uniquely 12/12 under the tolerant match,
so a tolerant deterministic locator would have found it too. The suffix case
is already within the macro's reach.

### 3. H3a — the 3A failure fixture escalates under the new framing

The frozen 3A A1 fixture (`Tuote | Tammi | Helmi | Jakso A | Huhti | Touko`)
covers only 4 of 12 references. The LLM returned `ask_human` itself; the
counterfactual confirms no row reaches 12 (max 4). The exact fixture where 3A
failed (silent omission of `Jakso A`, `ask_human=false`) now produces
`ask_human=true` — not because a fancy reviewer intervened, but because the
reference set is simply not covered. The whole escalation story collapses to
something beautifully boring: `coverage = 4/12 → recipe not applicable → HUMAN`.

### 4. H3b — an LLM proposal cannot bypass the applicability gate

A 12-slot row with `Jakso A` replacing `Maalis` looks like a full 12-month
header (11/12). The LLM returned `ask_human` itself — correctly calibrated —
but the load-bearing point is that it *didn't need to be*: had it confidently
proposed row 4, the gate would have counted 11/12 < 12 and overridden to
`ask_human`. The model is allowed to be optimistic without acquiring
authority. That is exactly the security property the 3E gate established,
transposed to row-location.

---

## Run identity

| | |
| --- | --- |
| Locator | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per LLM-invoked probe (H2, H3a, H3b); H1 deterministic, no LLM |
| Contract | header-row locator: given the 12-name reference + rendered source rows, identify the single row covering the reference set (harmless variation allowed), or ask_human; JSON output only |
| Gate | deterministic code (`harness/gate_H.py`); deterministic-first (exact) + tolerant-coverage verification; no LLM in the gate |
| Counterfactual | non-scoring all-row tolerant scan, recorded per probe |
| Sampling | one run per probe; no seed control over GLM-5.2 in the agent tool — cannot distinguish *always* from *once* |
| Fixtures | H1/H2/H3b authored + frozen for H; H3a = frozen 2B/3A A1 by path, unmodified |
| Freeze | preregistration + expected + reference + fixtures + harness at `3a19794`; amendment (counterfactual + H2 caveat) at `7df2b2a`; H1/H2 graded at `cec9288`; full graded at `2ad619a` |

## Decision rule — which branch fired

Preregistered decision table: `h1_h2 AND h3` → PASS. Fired exactly. No other
branch was close. `h2_ok` required `source==llm_accepted` (the LLM had to
propose and the gate had to authorize) — satisfied. The counterfactual scan is
non-scoring and recorded alongside; it did not change any pass flag.

## Hard stop — honored (scope ruling approved by designer)

H is month-reference-assisted row location only. No normalization (the locator
finds a row, does not output normalized values), no transformation code, no
country mappings (supplying month names is reference data, not a country
mapping), no numeric parsing, no multiple sheets, no joins, no procedure
synthesis, no production architecture. The broader "known countries/concepts"
generalization and any production system are out of scope. Designer approved
this ruling before the run.

## What this establishes

- **The reference-location framing dissolves the 3A failure mode.** The model
  is never asked what months *are*; the reference IS the world, so the
  closed-world lexical prior that generated `Jakso A → not_month` has no
  question to answer. The 3A failure fixture, under the new framing,
  escalates trivially (`4/12 → ask_human`).
- **The deterministic gate is the authority, and it transposes.** 3E's
  principle (deterministic code owns authority; an unsupported claim cannot
  acquire it) carries from cell-classification to row-location. H3b proves an
  optimistic LLM proposal cannot bypass the applicability gate.
- **For these four task shapes, the LLM is a discovery mechanism, not a
  runtime component.** The agent solved the instances; the observable rule
  (tolerant-coverage==12 → accept, else ask_human) is stable; the rule
  subsumes the agent for all four cases. This is the macro-saver outcome: the
  agent taught us how to delete the agent.

## What this does NOT establish

- **One run per probe, one model (GLM-5.2), no seed control.** Existence, not
  reliability. The LLM was correct on four single samples; the recipe was
  correct on four single fixtures. *Always* vs *once* is unmeasured.
- **The four fixtures are all subsumed by the deterministic recipe.** This is
  strong for these shapes (exact, suffix) but says nothing about shapes the
  tolerant matcher *cannot* resolve — abbreviations (`Heinä`/`Heinäkuu`),
  sources where several rows partially match and only context disambiguates,
  or genuinely novel representations. There the LLM would add value the
  deterministic locator lacks. That is the deferred H2b and the open question.
- **The tolerant matcher is suffix-specific** (prefix + non-letter boundary).
  Other variation kinds need their own matcher; the recipe is not universal.
- **12/12 full-coverage is the accept threshold (frozen).** A real table that
  legitimately drops a month would escalate. Graduated thresholds ("one known
  alias missing") are a later probe; H3b's value is precisely that it proves
  11/12 is not silently upgraded to certainty.
- **The LLM refused on H3a/H3b on its own.** So the gate did not have to
  override on this run. The safety property does not depend on that — the gate
  owns authority and would override an optimistic pick — but the single sample
  does not test the override path on a real confident-pick. The self-test
  verified the override logic on mock confident picks (`H2-wrong-partial`,
  `H3b` with `header_row:4` → `gate_coverage_short` → ask_human).
- **Not** a production architecture. H tested the framing on four frozen
  fixtures. Building, validating, and measuring reliability of the
  macro-saver system are future work.

---

## Capability boundary after H

```text
2B.1  locate header              PASS
2B.2  identify month columns     PASS
2B.3  refuse when unresolved     FAIL   (silent omission)
2B.4  aggregate + uncertainty    INCONCLUSIVE
2B.5  atomic classification      6/7
3A.G1 orchestrate easy           PASS
3A.G2 orchestrate Finnish        PASS
3A.G3 escalate via warrant       FAIL   -> 3D/3E fix
3B    reviewer policy/diversity  FAIL/FAIL
3C    mechanism                  DIAGNOSTIC (closed-world lexical default)
3D    symmetric reviewer         PASS   (Jakso A -> C)
3E    architectural replay       PASS   (failure blocked end-to-end)
H     reference-vocabulary location  PASS  (4/4; collapses to deterministic recipe)
```

The programme now has two complementary results:
1. **3A→3E:** when the task genuinely requires a judgement (is this cell a
   month?), the fix is symmetric independent review + a deterministic
   comparison gate — and it blocks the original failure end-to-end.
2. **H:** when the task is "find where the known vocabulary appears," the
   intelligence is in *discovery*, not *runtime* — the agent solves the
   instance, the rule collapses, and the runtime is deterministic.

## Where this points (not a commitment, not authorization)

The designer named the actual next project: the **macro-discovery question**.

> When the agent solves a new provider file successfully, can we extract a
> compact repeatable rule from its observable actions and replay that rule
> without the agent?

H showed the *outcome* of macro-discovery for one concept class (the rule
"tolerant-coverage==12" was found to be stable and the agent deleted from the
runtime). The next experiment would test the *process*: given a new provider
file the deterministic recipe does *not* yet cover, can the agent solve it, can
we observe and extract the rule it used, and can that rule then be replayed
deterministically on similar files — with the same applicability gate refusing
when the rule does not establish coverage? That is where the LLM would
genuinely earn its keep: solving the instance the macro does not yet cover, and
being saved as a new macro once the rule is stable.

Informative, none authorized:
1. **Macro-discovery probe** — a new provider representation the current recipe
   cannot resolve (e.g. abbreviation, or a source where multiple rows
   partially match). Agent solves it; extract the rule; replay deterministically.
2. **Reliability** — repeat the H probes (and 3D/3E) across runs/seeds; n=1 so far.
3. **Other model families** — whether the framing + gate is model-universal.

The honest summary: the gate that 3E built (deterministic code owns authority)
transposes cleanly to the location task, and the reference-vocabulary framing
collapses the monthly-header problem to a deterministic macro the agent helped
us discover. The remaining question is no longer "can the agent locate the
row?" (yes) or "is the gate safe?" (yes) but "can we extract the rule the agent
used and replay it without the agent?" — the macro-discovery question.