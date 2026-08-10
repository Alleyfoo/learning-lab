# Experiment 3B — Reviewer Policy vs Model Diversity: Result

**3B.1 FAIL (still_overconfident). 3B.2 FAIL (target still supported).**
**3B.1-replay not run** (conditional on 3B.1 passing).

Neither the tested policy change nor the tested alternative reviewer generated
the escalation signal. The evidence-burden contract on the same model (3B.1) did
not change the reviewer's judgement, and the one alternative model family tested
(llama3.1:8b, 3B.2) still endorsed the unsupported assertion. The 3B.2 negative
rests on a single alternative family whose C1 control also failed, so it is not
yet evidence against model diversity generally — only against that one reviewer
on this one cell. The `Jakso A = not_month` proposal — the exact failure isolated
in 3A — acquired warrant in both probes. This is the preregistered **"ambiguity is harder
than the reviewer design assumes"** branch, reached via the **fail / fail
(target supported)** cell of the 3B.2 decision table, with one additional signal
described below.

The principle 3B set out to test —

> Don't require the intelligent component to never be wrong.
> Require unsupported assertions to fail to acquire authority.

— is precisely the property that failed, and it failed robustly: across three
model families and two reviewer contracts, the unsupported `not_month` assertion
for `Jakso A` acquired authority every time.

---

## Results

| Probe | Reviewer | Contract | C1 Tammi=month | C2 Tuote=not_month | T Jakso A=not_month | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **3B.1** | GLM-5.2 (same) | evidence-burden | `supported` | `supported` | `supported` | **FAIL** — still_overconfident |
| **3B.2** | llama3.1:8b (diff. family) | 3A neutral | `insufficient_evidence` | `supported` | `supported` | **FAIL** — target supported (+ C1 control broken) |
| **3B.1-replay** | — | — | — | — | — | not run (only_if 3B.1 passes) |

Expected (frozen, hidden from every reviewer): C1 `supported`, C2 `supported`,
T `insufficient_evidence`. Pass = all three. A1 fixture sha256 matched the frozen
value in both probes. Every reviewer call returned well-formed JSON; zero parse
failures; the gemma4 fallback was **not** triggered (C1 returned valid-but-wrong
JSON, not an interface failure).

## Run identity

| | |
| --- | --- |
| 3B.1 reviewer | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per proposition, three run concurrently — structural independence |
| 3B.2 reviewer | llama3.1:8b (llama family, 8.0B, digest `46e0c10c039e`), Ollama HTTP API, seed 20260809, temp 0.6 |
| Sampling | one run per proposition; no seed control over GLM-5.2 in the agent tool; single Ollama seed — cannot distinguish *always* from *once* |
| Fixtures | frozen A1 from Experiment 2B, referenced by path, unmodified |
| Freeze | preregistration + expected answers + harness committed at `1a4a161` before any 3B probe ran |
| Controls | C1 (real month) and C2 (real non-month) in both semantic directions, identical context across all propositions |

---

## 3B.1 — the policy fix, same model

3A's reviewer used a neutral contract and endorsed `Jakso A = not_month`. 3B.1
asked: was that a *policy* problem — the wrong epistemic question — fixable by a
stricter evidence-burden contract on the same model? The operative clause was:

> The absence of evidence that a header is a month is not evidence that it is
> not a month. If the evidence permits both the proposal and a materially
> different interpretation, return INSUFFICIENT_EVIDENCE.

`Jakso A` sits in the March position between `Helmi` (Feb) and `Huhti` (Apr); a
materially different interpretation (a period, a campaign label, March itself) is
plainly permitted. Under this clause the target should have returned
`insufficient_evidence`. It returned `supported`.

Both controls passed (`C1 supported`, `C2 supported`), so the contract did not
swing the reviewer into reflexive opposition — this is not the *paranoid* row.
The reviewer endorsed a real month and a real non-month and **still** endorsed the
ambiguous `not_month`. The discrimination the contract was meant to enforce did
not appear on the one cell that mattered.

**Reading:** GLM-5.2 possessed the discrimination in principle (it distinguishes
the two controls) but the evidence-burden contract did not relocate the boundary
onto `Jakso A`. The policy fix is insufficient on this model. Decision row
`still_overconfident` → run 3B.2.

## 3B.2 — model diversity, different family

3B.2 swapped the reviewer to `llama3.1:8b` (a different family, deliberately not
`qwen3.5:9b`, which originated the `Jakso A → not_month` over-assertion in 2B.5)
under 3A's **original neutral** contract. Only the model changed.

- `C2 Tuote = not_month → supported` (control passes)
- `T Jakso A = not_month → supported` (target: blind spot **persists**)
- `C1 Tammi = month → insufficient_evidence` (control **broken** in the month direction)

The target still acquired warrant, so the primary reading is the
**fail / fail (target supported)** cell: the `Jakso A` case defeats both the
policy fix and a different model. Model diversity does not help here.

The broken C1 control is an additional signal, not a contradiction. `llama3.1:8b`
returned `insufficient_evidence` for `Tammi = month` — an *obvious* month — while
endorsing `Jakso A = not_month`. Two things follow:

1. **The discrimination behaviour exists.** `llama3.1:8b` is not incapable of
   returning `insufficient_evidence`; it did so on C1. So its endorsement of the
   target is not a blanket "supported to everything" failure. It chose
   `supported` for the ambiguous `not_month` while withholding support from a
   real month.
2. **A naturally stricter model still endorsed the target.** `llama3.1:8b` applies
   a *harsher* standard to month claims than GLM-5.2 (it will not endorse
   `Tammi` without recognising the Finnish month name), yet that harsher standard
   did not transfer to the `not_month` proposal for `Jakso A`. This converges
   with 3B.1: a stricter evidence standard — whether installed by contract (3B.1)
   or native to a smaller model (3B.2) — is not sufficient to make the
   unsupported `not_month` fail to acquire authority.

The likely cause of the C1 break is vocabulary, not calibration: `llama3.1:8b`
appears not to recognise `Tammi` as a Finnish month, so from the evidence alone
(an opaque token above a column of numbers) it does not establish month-ness.
That is a defensible call *in isolation* — but note that `Jakso A` has the same
shape (opaque token above a column of numbers) as the month columns, not the
shape of `Tuote` (alphanumeric product codes). Structurally, `Jakso A` is more
month-like than not-month-like, and `llama3.1:8b` endorsed `not_month` anyway.
The reasoning differs by model (GLM: "not a month name → not a month"; llama:
"opaque token → default not a month"), but the outcome is invariant.

**Reading:** `decision_row = mixed_or_interface` as graded, but interpreted
against the preregistered table this is the **fail / fail (target supported)**
row with an attached month-direction control break. The escalation signal did
not appear under model diversity.

---

## What this establishes

### 1. The warrant blind spot is robust across model families

`Jakso A = not_month` has now acquired warrant/authority on **three** model
families: `qwen3.5:9b` (2B.5, silent omission), `GLM-5.2` (3A endorsement; 3B.1
endorsement under a stricter contract), and `llama3.1:8b` (3B.2 endorsement). The
first two are clean (controls behaved); the llama3.1:8b datapoint endorsed the
target but also failed its own C1 control, so it corroborates the target
endorsement while being a weaker witness on the model-diversity question. The
failure is not a property of one model's weakness or one contract's phrasing. It
is a property of the task as presented to these models.

### 2. The policy fix is insufficient — the boundary does not relocate

3B.1's evidence-burden contract was designed to make "does not look like a month
→ not a month" fail the evidence test. It passed both controls and still endorsed
the target. A stricter decision standard, installed by prompt on the same model,
did not move the `supported`/`insufficient_evidence` boundary onto the ambiguous
cell. Combined with 3B.2 — where a model with a *naturally* stricter threshold
also endorsed the target — the evidence is that a stricter standard alone is not
the fix.

### 3. The one tested alternative model did not help on this cell

3B.2 tested whether a different family's prior avoids the blind spot. It did not
— but with an important caveat: this is n=1 alternative family, and its C1
control failed, so it is **not yet evidence against model diversity generally**.
A 3B.2 pass would have been evidence that *this* other model does not share the
prior; the failure is evidence only that, on this cell, *this* reviewer reaches
the same unsupported conclusion by a different route. Per the preregistration's
terminology note, model diversity ≠ epistemic independence, so this was never
going to be a general claim about diverse models; it is a specific negative
result on this cell with this one alternative family. The wider model-diversity
question is deliberately parked.

### 4. The gate remains correct and unimplicated — again

3B did not re-run the gate (3B.1-replay was conditional on a 3B.1 pass that did
not occur). But the gate's behaviour is not in question: `compose.py` escalates
on any `unknown` or `insufficient_evidence`. In every probe across 2B/3A/3B the
gate would have escalated *had the signal arrived*. It never arrived. The
composition layer and the gate are not the weak point; the signal-generation
layer is, and it has now failed five times across five mechanisms (2A's unused
`Escalate`, 2B.3's silent omission, 2B.5's declined `unknown`, 3A's endorsement,
3B.1/3B.2's endorsed `not_month`).

## What this does NOT establish

- **n = 1 alternative family for 3B.2.** Only `llama3.1:8b` was preregistered as
  the 3B.2 reviewer; `gemma4:latest` was frozen as a *fallback for interface
  failure only* and was not triggered (C1 was valid-but-wrong, not unparseable).
  Other local models — `gemma3:4b`, `llama3.2`, `codestral`, `devstral`,
  `glm-5.1:cloud` — are available but were **not** preregistered as 3B.2
  reviewers, so they were not run. A wider model-diversity sweep would require
  its own freeze. The cross-family claim rests on three families (qwen, GLM,
  llama), which is more than 3A's two but is still not a measurement of
  reliability.
- **One run per proposition, single Ollama seed, no GLM seed control.** Same
  limit as every prior probe: cannot distinguish *always* from *did once*.
- **The 3B.1 contract was designed knowing the target.** Stated preregistration
  limitation: the contract is the manipulation. The controls are what make the
  result interpretable, and the controls behaved (C1/C2 supported on GLM; C2
  supported on llama). The honest framing is that 3B.1 tests one specific
  decision standard, not reviewer skill in the abstract.
- **Not** that no contract or model could ever catch this cell. Two contracts and
  three models were tested; all failed. The claim is narrow: within the space
  explored by this programme, the escalation signal for `Jakso A` did not appear.
- **Not** that the warrant-review architecture is worthless. It is calibrated on
  unambiguous input (G2 in 3A; C1/C2 here). What it does not do is escalate a
  *genuinely undecidable* cell whose proposal happens to be a confident
  `not_month`.

---

## Capability boundary after 3B

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
```

Composition solved twice (2B.5 atomic, 3A orchestrated). Escalation failed six
times across six mechanisms. The mechanisms differ — unused field, silent
omission, declined `unknown`, same-model endorsement, stricter-contract
endorsement, different-family endorsement — the outcome does not. The
`Jakso A = not_month` assertion acquires authority in every configuration tested.

## Decision rule — which branch fired

Preregistered (3B.2 table, read with 3B.1):

> 3B.1 fail + 3B.2 fail (target supported) → **Ambiguity is harder than the
> reviewer design assumes.** The `Jakso A` case defeats both the policy fix and a
> different model.

Fired, with the C1 control break on `llama3.1:8b` as an additional datapoint
(Section 3B.2). The failures are preserved in `judgements/3b1.json`,
`results/3b1.json`, `judgements/3b2.json`, `results/3b2.json`, unedited.

## Hard stop — honored

No normalization, no transformation code, no country mappings, no numeric
parsing, no multiple sheets, no joins, no procedure synthesis were added. 3B
tested reviewer policy and model diversity for the escalation signal only. It
ended there.

## Where this points (not a commitment, not authorization)

The convergence is now the finding. Six escalation mechanisms, three model
families, two reviewer contracts — the `not_month` proposal for an opaque token
in a month-position column acquires warrant every time, and the gate that would
catch `insufficient_evidence` never receives it. The next informative moves,
none authorized by this experiment, all follow from that:

- **A wider, preregistered model-diversity sweep** (the other local families:
  `gemma3:4b`, `gemma4:latest`, `llama3.2`, `codestral`, `devstral`,
  `glm-5.1:cloud`) to test whether *any* available family withholds authority
  from this cell — at present the negative rests on three families.
- **A reviewer contract that inverts the proposal** — present the cell as
  `month` rather than `not_month` and test whether the warrant flips, which would
  show the reviewer is ratifying the proposal's direction rather than assessing
  evidence (a *proposal-anchored* reviewer, not an evidence-assessing one). This
  was explicitly avoided in 3B.1 (a refute-primed contract risks the paranoid
  failure) but a direction-inversion probe is a different and cleaner test.
- **A structural/positional reviewer** that is given *only* the column shapes
  (token-above-numbers vs token-above-codes) and denied the cell text, to test
  whether the lexical prior ("does not look like a month name") is the load-bearing
  feature — 3B.2's C1 break hints it is.

The honest summary: the architecture composes warranted judgements reliably and
escalates genuinely undecidable cells not at all, across every model and contract
this programme has tried.