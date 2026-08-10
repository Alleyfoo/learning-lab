# Experiment 3D — Symmetric Reviewer: Result

**CLEAN WIN. `framing_was_the_problem + structure_establishes_month`.**

```text
Tammi    -> A   (control: real month established)
Tuote    -> B   (control: real non-month established)
Jakso A  -> C   (neither established)   <- the load-bearing prediction held
[TARGET] -> A   (month, from structure)
```

Symmetric framing solved the escalation. Under a symmetric A/B/C question with no
handed proposal, the reviewer returned `C` (neither established) for `Jakso A` —
the exact cell on which every prior probe (2B.3, 2B.5, 3A.G3, 3B.1, 3B.2) endorsed
`not_month` or omitted the column. The closed-world lexical default that 3C located
**did not fire** when there was no `not_month` proposition to confirm against. The
gate would receive `C` on the failure cell and escalate to HUMAN.

This is the first clean win in the escalation programme, and it is a *confirmed
preregistered prediction*: 3C isolated proposal framing as the contamination
variable, 3D removed that variable, and the predicted `Jakso A → C` appeared.

---

## Results

| Probe | Evidence | Target | Result | Expected | OK |
| --- | --- | --- | --- | --- | --- |
| **CTRL-MONTH** | Full A1 | col 2 `Tammi` | `A` | A | ✓ |
| **CTRL-NONMONTH** | Full A1 | col 1 `Tuote` | `B` | B | ✓ |
| **3D-FULL** | Full A1 | col 4 `Jakso A` | `C` | C | ✓ |
| **3D-MASKED** | Masked A1 (col 4 → `[TARGET]`) | col 4 `[TARGET]` | `A` | A | ✓ |

All four reviewer calls returned well-formed JSON; zero parse failures. A1 fixture
sha256 matched the frozen value. The reviewer model, evidence-burden standard,
fixture, and invocation mechanism were identical to 3C; **only the review framing
changed** — symmetric A/B/C instead of a handed proposition.

## Run identity

| | |
| --- | --- |
| Reviewer | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per probe, four run concurrently — structural independence |
| Contract | symmetric A/B/C, no handed proposal; evidence-burden standard carried from 3B.1/3C ("absence of evidence that the target is a month is not evidence that it is not a month"; neither established → C) |
| Sampling | one run per probe; no seed control over GLM-5.2 in the agent tool — cannot distinguish *always* from *once* |
| Fixtures | frozen A1 from Experiment 2B, referenced by path, unmodified |
| Freeze | preregistration + expected answers + harness committed at `4dd9b51` before any 3D probe ran |

---

## The 3C ↔ 3D contrast (the cleanest demonstration)

3C and 3D share the same model, the same fixture, the same evidence-burden clause.
The only difference is the review framing. On the same cell:

```text
                                         framing              result
3C  F1   Jakso A, handed "not_month?"    asymmetric proposition  supported (not_month endorsed)
3D  FULL Jakso A, "which: A/B/C?"        symmetric               C (neither established)
```

Same evidence, same standard, same model. The judgement flipped from
`not_month supported` to `neither established` **solely** by removing the handed
proposal. That is the isolated effect of proposal framing, measured cleanly.

And on the masked cell, the structural reading was **framing-robust**:

```text
3C  M2    [TARGET], handed "month?"      asymmetric proposition  supported (month endorsed)
3D  MASK  [TARGET], "which: A/B/C?"      symmetric               A (month established)
```

So symmetric framing fixed exactly the broken half (the lexical `not_month`
default on `Jakso A`) without breaking the working half (the structural month
reading on `[TARGET]`). That is the ideal outcome: the fix removes the failure
mode and preserves the correct behaviour.

## The three findings

### 1. Controls pass — the symmetric contract is calibrated

`Tammi → A` and `Tuote → B`. The symmetric framing does not make the reviewer
over-withhold: it establishes a real month and a real non-month when the evidence
supports them. This rules out "the symmetric contract just returns C to
everything," so the `Jakso A → C` result means what it appears to mean — genuine
withholding on an undecidable cell, not a blanket refusal.

### 2. `Jakso A → C` — framing was the problem

The load-bearing prediction. Under the symmetric question, the reviewer did not
select `B` (not_month) for `Jakso A`. The closed-world lexical default — "the
token doesn't look like a month name, so it's not a month" — required a handed
`not_month` proposition to confirm against (3C F1). Forced to choose symmetrically
between A, B, and C, the reviewer concluded that the evidence establishes neither
month nor not_month, and returned C. The evidence-burden clause that 3B.1/3C could
not enforce under asymmetric framing reached the cell under symmetric framing.

The mechanism 3C located is confirmed, and the fix 3C pointed at works:
**the reviewer never inherits the claim's direction, so the default has nothing to
confirm.**

### 3. `[TARGET] → A` — structure establishes month, framing-robust

Consistent with 3C M2. Without the lexical token and without a handed proposal, the
reviewer independently concluded `month` from the structural surroundings (position
between `Helmi` and `Huhti`, numeric data column like the months). This was not an
artifact of proposition framing — it survived the switch to symmetric review. So
the structural month-reading is robust, and the only framing-dependent behaviour
was the lexical `not_month` default on the visible `Jakso A` token.

---

## What this establishes

### The escalation signal can be produced — by changing the question, not the model

Across 2B.3 → 2B.5 → 3A.G3 → 3B.1 → 3B.2, the `Jakso A` cell never produced an
escalation signal under any model or contract tested, because all of them reviewed
a *handed proposition*. 3D produced the signal (`C`) on the first try, on the same
model that failed in 3A/3B.1, by removing the handed proposition. The fix was
architectural (change the review framing), not a bigger model or a stricter
contract.

### The closed-world lexical default requires a proposal to confirm against

3C showed the default fires under asymmetric framing. 3D shows it does not fire
under symmetric framing. The default is not a free-standing classification — it is
a *confirmation bias* that needs a proposition to confirm. Without one, "the token
doesn't look like a month" is correctly read as "month is not established" (not
"not_month is established"), and the symmetric C option catches it.

### The architectural change is justified by measurement

3C isolated the variable; 3D removed it and the predicted outcome appeared. The
move from "review the specialist's claim" to "independently classify, then
deterministically compare" is now grounded in a confirmed prediction, not a prompt
hunch:

```text
specialist proposes classification
        ↓
reviewer independently asks: what does the evidence establish?
        ↓
MONTH (A) / NOT_MONTH (B) / NEITHER (C)
        ↓
deterministic comparison
        ↓
specialist = not_month, reviewer = C  ->  disagreement / insufficient warrant  ->  HUMAN
```

The reviewer never inherits the claim's direction, so the closed-world default has
nothing to confirm. On the 3A G3 failure cell, this would have produced
`specialist=not_month, reviewer=C → HUMAN` — the escalation that never happened in
3A.

## What this does NOT establish

- **One run, one model, no seed control.** The clean win is a single sample on
  GLM-5.2. It is a *confirmed preregistered prediction* (stronger than a post-hoc
  observation), but reliability — *always* vs *once* — is unmeasured. The
  `Jakso A → C` could be run-unstable; 3C's F1 reproduced 3B.1's `supported` across
  two runs, which is mild evidence the behaviour is stable, but 3D has no such
  replication yet.
- **Only GLM-5.2 tested.** Whether symmetric framing solves the same cell on other
  model families (qwen, llama, gemma, etc.) is not tested. The wider model sweep
  remains parked. Symmetric framing is a *framing* fix; whether it is
  model-universal is an open question.
- **The symmetric contract still lists B as an option.** Listing `B` (not_month)
  does not hand the reviewer a *direction* the way a proposal does, but B is not
  absent from view. The test shows B must *compete* with C symmetrically rather
  than be *confirmed* — which is the architecturally relevant distinction — but a
  contract that omitted B entirely would be a different design, untested.
- **Not** that the symmetric reviewer is calibrated in general. It is calibrated on
  two controls (Tammi, Tuote) and one ambiguous cell (Jakso A) on one run. A
  wider calibration over many cells/fixtures is not done.
- **Not** a production architecture. 3D tested the framing on one frozen cell plus
  controls. Building the symmetric-reviewer + deterministic-comparison system,
  validating it end-to-end on the 3A G3 chain, and measuring its reliability are
  future work, not done here.
- **The masked result `[TARGET] → A` is itself a single sample.** 3C M2 → 3D MASK
  consistency is two samples (one per framing) of the same structural reading, but
  neither is replicated.

---

## Capability boundary after 3D

```text
2B.1  locate header              PASS
2B.2  identify month columns     PASS   (aggregate, binary contract)
2B.3  refuse when unresolved     FAIL   (silent omission)
2B.4  aggregate + uncertainty    INCONCLUSIVE (control failed)
2B.5  atomic classification      6/7    (composition solved; warrant not)
3A.G1 orchestrate easy           PASS
3A.G2 orchestrate Finnish        PASS   (incl. warrant reviewer calibrated)
3A.G3 escalate via warrant       FAIL   (reviewer endorsed over-assertion)
3B.1  evidence-burden reviewer   FAIL   (still_overconfident; controls pass)
3B.2  model-diversity reviewer   FAIL   (target supported; C1 control broken)
3C    direction x evidence       DIAGNOSTIC — mechanism located (closed-world lexical default)
3D    symmetric reviewer         PASS   — clean win; Jakso A -> C (neither)
```

Composition solved twice (2B.5, 3A). Escalation failed six times across six
mechanisms, then 3C diagnosed the mechanism, then 3D produced the signal. The
programme arc: *observe the failure → isolate the variable (3C) → remove it (3D) →
the signal appears.* For the first time, the gate that has been waiting since 2B.3
for an `insufficient_evidence`/`neither` signal receives one on the failure cell.

## Decision rule — which branch fired

Preregistered: `controls_pass AND 3D-FULL=C AND 3D-MASKED=A` → the clean win
(`framing_was_the_problem + structure_establishes_month`). Fired exactly. The
partial-pass branch (`3D-FULL=C, 3D-MASKED=C`) did not fire; the masked structural
confidence survived the framing change.

## Hard stop — honored

No normalization, no transformation code, no country mappings, no numeric parsing,
no multiple sheets, no joins, no procedure synthesis, and no symmetric-reviewer
production architecture were built. 3D tested whether symmetric review framing
lets the escalation signal appear on the one frozen cell (plus controls). It did.
The experiment ended there.

## Where this points (not a commitment, not authorization)

The framing fix is measured, not yet validated as a system. The informative next
moves, none authorized:

1. **3E — end-to-end replay of 3A G3 with the symmetric reviewer.** Freeze the 3A
   G3 classifier outputs (still allowed to say `not_month` for `Jakso A`), run the
   symmetric reviewer on all six columns, and feed both into a deterministic
   comparison gate: `specialist=not_month, reviewer=C → HUMAN`. This is the
   direct demonstration that the production architecture would have escalated 3A
   G3. Reuses 3A's frozen classifier judgements and 3D's symmetric framing; only
   the reviewer + gate change.
2. **Reliability of the 3D win** — repeat the four 3D probes across several runs
   (and seeds, where controllable) to move from "did once" toward "reliable."
   Cheap; the design is frozen.
3. **Symmetric framing on other model families** — run the 3D four-probe design on
   the parked local models. Tests whether the framing fix is model-universal or
   GLM-specific. Lower priority now that the win is measured on GLM-5.2, but it
   determines whether the architectural change is safe to recommend generally.

The honest summary: the gate was waiting for a signal that no judgement mechanism
would produce under asymmetric proposition review. 3C showed *why* — a closed-world
lexical default invited by the handed proposal. 3D shows that removing the
proposal lets the evidence-burden standard reach the cell, and the signal appears.
The remaining question is no longer "can the signal be produced?" but "is the 3D
win reliable and model-universal enough to build on?"