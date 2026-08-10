# Experiment 3E — Architectural Replay with Symmetric Review: Result

**PASS — `failure_blocked`. The 3D fix blocks the 3A G3 failure end-to-end,
with the original bad specialist judgement frozen in place.**

```text
col 1 Tuote    specialist=not_month  reviewer=B  ->  accept_not_month
col 2 Tammi    specialist=month      reviewer=A  ->  accept_month
col 3 Helmi    specialist=month      reviewer=A  ->  accept_month
col 4 Jakso A  specialist=not_month  reviewer=C  ->  HUMAN (insufficient_warrant)
col 5 Huhti    specialist=month      reviewer=A  ->  accept_month
col 6 Touko    specialist=month      reviewer=A  ->  accept_month

gate: month_columns=[2,3,5,6]  human_columns=[4]  ask_human=true
```

This is the experiment the whole programme was building toward. 3A observed the
failure (`Jakso A` silently classified `not_month`, warrant endorsed it,
`ask_human=false`). 3B tried two simple reviewer fixes and both failed. 3C
isolated the mechanism (a closed-world lexical default invited by the handed
proposition). 3D removed the proposition and the signal appeared (`Jakso A → C`).
3E now takes that signal back into the architecture it was meant to protect —
the 3A G3 chain — and asks: does it block the failure?

It does. The frozen specialist still says `not_month` for `Jakso A`. The
classifier was NOT re-run, NOT fixed, NOT improved. The symmetric reviewer says
`C` (neither established) on that same cell. The deterministic comparison gate
sees `specialist=not_month, reviewer=C` and routes the cell to HUMAN. The five
resolvable cells (Tuote, Tammi, Helmi, Huhti, Touko) all accept correctly. The
gate emits `ask_human=true` — exactly the output 3A G3 failed to produce.

---

## The frozen inputs (what did NOT change)

```text
frozen specialist (experiment3a/judgements/G3.json, verbatim, classifier NOT re-run):
  col 1 Tuote   -> not_month
  col 2 Tammi   -> month
  col 3 Helmi   -> month
  col 4 Jakso A -> not_month     # the over-assertion, unchanged
  col 5 Huhti   -> month
  col 6 Touko   -> month

frozen fixture: A1 from Experiment 2B (sha256 64356f..), header row 4
frozen contract: symmetric A/B/C (3D framing), evidence-burden standard
frozen gate logic: deterministic comparison (code, not LLM)
```

The only things new in 3E are the review path (symmetric A/B/C on all six
columns instead of 3A's same-model warrant review) and the composition (a
deterministic comparison gate instead of 3A's warrant gate). The bad
classification is preserved exactly as 3A produced it.

## The symmetric reviewer verdicts (six fresh independent calls, GLM-5.2)

| col | cell | specialist (frozen) | reviewer | expected reviewer | OK |
| --- | --- | --- | --- | --- | --- |
| 1 | Tuote | not_month | **B** | B | ✓ |
| 2 | Tammi | month | **A** | A | ✓ |
| 3 | Helmi | month | **A** | A (predicted) | ✓ |
| 4 | Jakso A | not_month | **C** | C | ✓ |
| 5 | Huhti | month | **A** | A (predicted) | ✓ |
| 6 | Touko | month | **A** | A (predicted) | ✓ |

All six verdicts match the frozen expected. The three predicted cells (Helmi,
Huhti, Touko — obvious Finnish months, by analogy to Tammi) returned A as
predicted, so the fix did not turn paranoid on the easy months. The
load-bearing cell `Jakso A → C` reproduced the 3D result in the six-column
replay. Zero parse failures; all six calls returned well-formed JSON.

## The deterministic comparison gate (authoritative)

The gate is ordinary code in `harness/compose_3e.py`, auditable, no LLM
participates:

```text
reviewer == C                              -> HUMAN  (insufficient warrant)
specialist == month     AND reviewer == A  -> ACCEPT month
specialist == not_month AND reviewer == B  -> ACCEPT not_month
otherwise                                 -> HUMAN  (disagreement / parse failure)
```

Applied per column:

| col | specialist | reviewer | gate disposition | reason |
| --- | --- | --- | --- | --- |
| 1 | not_month | B | accept_not_month | agree_not_month |
| 2 | month | A | accept_month | agree_month |
| 3 | month | A | accept_month | agree_month |
| 4 | not_month | C | **human** | **insufficient_warrant** |
| 5 | month | A | accept_month | agree_month |
| 6 | month | A | accept_month | agree_month |

Aggregate: `month_columns=[2,3,5,6]`, `human_columns=[4]`, `ask_human=true`.

This matches the frozen expected gate output exactly. The `ask_human=true` is
the output 3A G3 failed to produce — 3A's warrant gate endorsed all six and
emitted `ask_human=false` (the silent-omission failure). The same specialist
judgements, a different review path and gate, produce the escalation.

## Run identity

| | |
| --- | --- |
| Specialist | frozen 3A G3 classifier outputs (`experiment3a/judgements/G3.json`), NOT re-run |
| Reviewer | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per column, six run — structural independence; symmetric A/B/C (3D framing) |
| Gate | deterministic code (`harness/compose_3e.py`), no LLM; authoritative |
| Orchestrator (secondary) | GLM-5.2, one fresh isolated call seeing the six specialist+reviewer pairs + full A1; non-authoritative |
| Sampling | one run per reviewer cell; no seed control over GLM-5.2 in the agent tool — cannot distinguish *always* from *once* |
| Fixtures | frozen A1 from Experiment 2B, referenced by path, unmodified |
| Freeze | preregistration + expected answers + harness committed at `cb4e71c` before any 3E probe ran; graded result at `c259c9c` |

---

## The causal chain closes

```text
3A   failure observed          Jakso A -> not_month, warrant endorsed, ask_human=false
3B   simple reviewer fixes fail evidence-burden contract (3B.1) and a tested
                                alternative model (3B.2) both still endorsed the cell
3C   mechanism isolated         closed-world lexical default, invited by the handed
                                proposition; directional_prior + lexical_origin
3D   framing produces signal    symmetric A/B/C, no handed proposal -> Jakso A -> C
3E   signal blocks the failure  frozen bad specialist + symmetric reviewer + gate
                                -> Jakso A -> HUMAN, ask_human=true   PASS
```

This is not "we found a prompt that works." It is
*failure → diagnosis → controlled intervention → architectural replay*. 3C told
us which variable to remove (the handed proposal). 3D removed it and the
predicted signal appeared. 3E proves the signal, fed into a deterministic gate
alongside the *original bad judgement*, blocks the original failure path. The
fix works with the specialist still wrong — which was the load-bearing
constraint: the gate must not depend on the classifier being correct.

## The secondary measurement — the reasoning layer agreed too

One non-authoritative orchestrator-disposition call (GLM-5.2, fresh context)
saw the six `(cell, specialist classification, reviewer verdict with meaning)`
pairs plus the full A1 evidence, and was asked for a disposition. It returned:

```json
{"month_columns": [2, 3, 5, 6], "ask_human": true}
```

This **agrees with the gate** (`ask_human=true`, `month_columns=[2,3,5,6]`).
So the reasoning layer, on seeing `Jakso A → C` (neither established), also
requested HUMAN — it did not try to re-introduce the failure.

This was **not required for success.** The deterministic gate owns authority;
the orchestrator could have said `proceed` and the gate would still escalate.
The measurement tells us that the reasoning layer *understood* the situation,
not just that the gate *forced* the right answer. (Caveat: the orchestrator
saw the reviewer verdicts, so its `ask_human=true` is partly deferring to `C`
rather than independently re-deriving the escalation — stated as such in the
preregistration. The gate is what makes the outcome safe; the orchestrator
agreement is a weaker, informative datapoint.)

## Why this is stronger than 3D alone

3D showed the signal can be produced on the one cell, in isolation. A skeptic
could ask: "maybe the signal appears in the clean four-probe setup but not when
the reviewer is run six times in the full pipeline, or maybe the gate
composition mis-routes something, or maybe the fix turns the whole pipeline
paranoid on the easy months." 3E answers all three:

1. **The signal survived the six-column replay.** `Jakso A → C` reproduced with
   five other columns in the same run, not just in the isolated 3D probe.
2. **The gate composed correctly.** `not_month + C → HUMAN` fired exactly as
   designed; the five agreements accepted; no parse failures.
3. **The fix is not paranoid.** All five resolvable cells (Tuote, Tammi, Helmi,
   Huhti, Touko) accepted correctly. The fix escalates exactly the one cell it
   should and nothing else.

And it did this with the specialist judgement frozen to the *original wrong
value*. The architecture does not need the classifier to be fixed. That is the
architecturally important result: the review+gate layer catches the
over-assertion even when the classifier produces it.

## What this does NOT establish

- **One run, one model, no seed control.** 3E is n=1 on each of six reviewer
  cells and n=1 on the orchestrator-disposition call, all on GLM-5.2. The PASS
  is a *confirmed preregistered prediction* (the expected gate output was
  frozen before any 3E probe ran), which is stronger than a post-hoc
  observation, but reliability — *always* vs *once* — is unmeasured. The
  `Jakso A → C` could be run-unstable. 3D's single `Jakso A → C` plus 3E's
  single `Jakso A → C` is two samples (different contexts: isolated probe vs
  six-column replay), mild evidence of stability, but not a replication study.
- **Only GLM-5.2 tested.** Whether symmetric framing + the comparison gate
  blocks the same failure on other model families is not tested. The wider
  model sweep remains parked.
- **The frozen specialist is one run's output.** A different specialist run
  might classify `Jakso A` differently (e.g., `month`, or refuse). 3E holds the
  specialist fixed by design — the fix must work *with the specialist still
  wrong* — so this is a feature, not a gap, but it means 3E proves the
  review+gate layer against one specific bad judgement, not against the space
  of possible bad judgements.
- **The comparison gate is new code.** It is simple and deterministic and
  auditable in `harness/compose_3e.py`, but it is not the 3A warrant gate. Its
  correctness was checked by a dry run over all six input combinations before
  the real judgements were recorded.
- **The orchestrator agreement is partly deferential.** The orchestrator saw
  the reviewer verdicts; its `ask_human=true` is not independent re-derivation.
  The gate is what guarantees the outcome; the orchestrator measurement is
  weaker and informative only.
- **Not** a production architecture. 3E replayed one frozen chain. Building,
  validating end-to-end on many fixtures, and measuring reliability of the
  symmetric-reviewer + deterministic-comparison system are future work.

---

## Capability boundary after 3E

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
3E    architectural replay       PASS   — failure blocked end-to-end; ask_human=true
```

The programme arc is complete: *observe the failure (3A) → simple fixes fail
(3B) → diagnose the mechanism (3C) → remove the variable (3D) → the signal
appears → replay the original failure with the fix (3E) → the failure is
blocked.* For the first time, the gate that has been waiting since 2B.3 for an
escalation signal receives one on the failure cell, in the architecture it was
meant to protect, with the original bad judgement still in place.

## Decision rule — which branch fired

Preregistered decision table:

| Gate output | Reading | Fired? |
| --- | --- | --- |
| `ask_human=true, month_columns=[2,3,5,6], human_columns=[4]`, cols {1,2,3,5,6} ACCEPT | **PASS — failure blocked end-to-end** | **✓** |
| `ask_human=false` | FAIL — fix did not block | |
| `ask_human=true` but a resolvable cell also escalated | FAIL — paranoid | |
| `ask_human=true`, Jakso A escalated, but `month_columns` wrong | FAIL — partial | |

The `PASS_failure_blocked` branch fired exactly. No other branch was close:
`ask_human=true`, all five resolvable cells accepted, `month_columns` exactly
`[2,3,5,6]`, `human_columns` exactly `[4]`.

## Hard stop — honored

No normalization, no transformation code, no country mappings, no numeric
parsing, no multiple sheets, no joins, no procedure synthesis, no production
system, no wider model sweep, no replication study. 3E replayed the 3A G3 chain
with the symmetric reviewer + deterministic comparison gate and ended at "did
the measured fix block the original failure end-to-end?" It did.

## Where this points (not a commitment, not authorization)

The designer's stated ordering: *"After 3E, I would then worry about
replication. Not before. First prove that the intervention actually closes the
original failure path in the architecture it was meant to protect."* That is
now proved. The informative next moves, none authorized:

1. **Reliability of the 3D/3E win** — repeat the symmetric-reviewer probes
   across several runs (and seeds, where controllable) to move from "did once"
   toward "reliable." The design is frozen; the harness is deterministic; this
   is the cheapest informative move and the one the designer named next.
2. **Symmetric framing on other model families** — run the 3D/3E design on the
   parked local models. Tests whether the framing fix + gate is model-universal
   or GLM-specific. Determines whether the architectural change is safe to
   recommend generally.
3. **More bad-judgement cases** — 3E proves the gate against one specific
   over-assertion (`Jakso A → not_month`). Other failure shapes (e.g.,
   specialist says `month` on a genuinely ambiguous cell, reviewer says `C` →
   disagreement → HUMAN) are covered by the gate logic but not yet exercised on
   real fixtures.

The honest summary: the gate was waiting for a signal that no judgement
mechanism would produce under asymmetric proposition review. 3C showed why. 3D
produced the signal by changing the question. 3E proves the signal, fed into a
deterministic gate alongside the original bad judgement, blocks the original
failure. The remaining question is no longer "can the signal block the
failure?" but "is the win reliable and model-universal enough to build on?"