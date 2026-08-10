# Experiment I — Wide / Long / Unknown format classification: Preregistration

**STATUS: FROZEN before any run.** No LLM probes have been run. The harness
self-test passes on the frozen fixtures. Probes run only on explicit
designer authorization, as in H.

## Purpose

Step 2 of the little skill chain the designer named:

```text
1. Where is the header?            (Experiment H — locate via month vocabulary)
2. Is the data wide or long?        (Experiment I — this one)
3. Which columns carry the roles?   (later)
4. Only then consider transformation (out of scope here)
```

I is **classification, not transformation**. Given the already-located header
row plus 3–5 sample data rows, label the monthly-data representation as
`wide`, `long`, or `unknown`. No unpivot, no reshape, no code generation.

```text
WIDE:  Product | Jan | Feb | Mar  with one row per product, values in cells
LONG:  Product | Month | Sales    with one row per (product, month)
UNKNOWN: neither cleanly holds
```

## Architectural note (carried from H, made explicit here)

H as built is a **wide-header locator**: it finds a row whose cells cover the
12-month reference vocabulary. In a long table, the months live in a **data
column**, not the header — so H's recipe returns `ask_human` on a long table.
That is correct for H (H locates a *header*), and it is exactly why I exists
as a separate classification step: before you can locate-with-H, you may need
to know whether the file is wide (months in header → H applies) or long
(months in data → a different locator is needed). The chain ordering question
— *format-classification-first, then locate* vs *a general header-row
locator* — is left open. I does not require it resolved: I receives the
header + data as a pre-located extract and classifies the representation.

## Input and contract

Input per probe: a small UTF-8 CSV — header row (row 1) + 3–5 data rows.
(Pre-located: H-style title/metadata rows are absent; I isolates the
representation variable.)

LLM contract (one locator-style call per probe, fresh isolated context):

> Given the rendered rows below, determine whether the monthly data is
> represented in **wide**, **long**, or **unknown** format.
> Output ONLY JSON: {"format": "wide"} | {"format": "long"} | {"format": "unknown"}.

## Probes

| Probe | Fixture | Shape | Expected | Role |
| --- | --- | --- | --- | --- |
| I1 | `fixtures/I1.csv` | `Tuote | Tammi | Helmi | …` (6 months) + numeric rows | `wide` | positive wide control |
| I2 | `fixtures/I2.csv` | `Tuote | Kuukausi | Myynti` + one row per product-month | `long` | positive long control |
| I3 | `fixtures/I3.csv` | `Tuote | Q1 | Q2 | Q3 | Q4 | Vuosi` + numeric rows | `unknown` | refusal/odd control |

I3 is the "genuinely odd one" deferred from the design discussion (design now,
run later). It is a quarterly summary at a different time granularity — there
are no month-name tokens at all, so the monthly representation is neither
wide nor long: `unknown` is the correct refusal.

A more structurally-odd candidate was considered and **deferred**: a
*transposed wide* table (months as rows, products as columns). That case is
where the deterministic classifier is wrong (months in a data column → the
rule says `long`) and the LLM could add value. It is noted in the stated
limitations and reserved for a later probe; it is NOT I3, because I's first
run should establish the clean controls and the clean refusal before testing
a case where the rule itself fails.

## The three layers (frozen)

```text
deterministic classifier (counterfactual + deterministic-first):
    hw = distinct reference months in the HEADER row (tolerant match)
    dl = max distinct reference months in any single DATA column
    hw >= K_w (3) -> "wide"
    dl >= K_l (3) -> "long"        (only if not wide; wide takes precedence)
    else         -> "unknown"
    reference: experimentH/reference/months.json (frozen, by path)
    match: H's suffix-tolerant prefix match (verbatim)

verifier gate (objective, code, not LLM; VERIFIES, does not override):
    wide    supported iff hw >= K_w
    long    supported iff dl >= K_l
    unknown supported iff hw < K_w AND dl < K_l
    invalid label -> not supported
    records: supported, agreement with det_classify

grader (frozen in expected.json):
    i_pass   = (llm_label == expected) AND supported
    det_ok   = (det_classify == expected)   # counterfactual
    i1_i2    = I1.i_pass AND I2.i_pass
    overall  = I1 AND I2 AND I3 all i_pass
```

### Why a verifier gate, not an authority

H's gate owned authority because coverage==12 is an **objective, exact**
property: a row either covers all 12 references or it does not. Here the
"deterministic classifier" is a **heuristic** (count month tokens in header
vs in a data column). It is objective about *token presence* but coarse about
*structure*: it cannot distinguish a genuine long table from a transposed wide
table (both put months in a data column). So the gate **verifies** the LLM's
claim is objectively supported — it does not substitute its own answer as
authority. The LLM's classification is the primary measurement; the gate is
the safety check that the claim is grounded; the deterministic classifier is
the counterfactual.

### Deterministic-first (production rule, recorded not enforced)

The production optimisation — skip the LLM when the deterministic classifier is
confident (`wide`/`long`) — is recorded as a derived recommendation. The
experiment invokes the LLM on **all** probes, because I's purpose is to
*measure whether the model can identify the representation*. The counterfactual
(`det_ok`) answers whether the LLM was needed. This differs from H, where H1
short-circuited and was not LLM-tested; there the purpose was "does the
deterministic path solve the clean case", here it is "can the model classify".

## Counterfactual (non-scoring, recorded per probe)

For each probe, `det_classify` is computed and compared to the expected label.
If `det_ok` holds on all probes, the rule alone suffices and the LLM was
correct-but-unnecessary (the H macro-saver outcome). If `det_ok` fails somewhere
while `i_pass` holds, the LLM added value the rule lacked — that is the
interesting case and points to a new macro to extract. I's clean controls are
expected to show `det_ok` everywhere; the deferred transposed-wide probe is
where `det_ok` would fail.

## Decision rules (frozen, not relaxed after the fact)

| Branch | Condition | Outcome |
| --- | --- | --- |
| I1 & I2 pass, I3 not run | `i1_i2` | `i1_i2 PASS`; I3 deferred |
| All three pass | `overall` | PASS |
| Any control fails | — | FAIL (recorded as-is, criteria not relaxed) |

Stage-aware grading, as in H: probes present in `judgements/I.json` are graded;
`i1_i2` requires I1 AND I2 present and passing; `overall` requires all three.

## Hard stop — scope ruling for I (carried, requested)

I is a **classification label**, not a transformation. Producing a label is
within the carried hard stop (no transformation code, no unpivot, no reshape).
Explicitly out of scope, even if I1–I3 all pass:

- normalization, numeric parsing, country mappings
- Python transformation / unpivot / reshape generation
- multiple sheets, joins, reusable procedure synthesis
- the full production architecture (locate → classify → role → transform)
- the transposed-wide probe (deferred, not I3)

The next skill step (3: which columns carry the roles) and any transformation
are **not** authorized by running I. Running I authorizes only the
classification measurement on the frozen fixtures.

## What I establishes (if it passes)

- The LLM can correctly label wide, long, and unknown representations on the
  clean controls, with each label objectively supported by the token evidence.
- The deterministic month-token heuristic classifies the same controls
  correctly (counterfactual), so for these shapes the LLM is a discovery
  mechanism, not a runtime component — the macro-saver outcome, extended from
  H (locate) to I (classify).
- The verifier gate flags an unsupported claim (a hallucinated `wide` with no
  months in the header would be `supported=False`). Safety without authority.

## What I does NOT establish

- The heuristic is coarse and is wrong on transposed wide (deferred). Passing
  the clean controls says nothing about structures the heuristic misreads.
- n=1 on GLM-5.2, no seed control: existence, not reliability.
- Classification only; no transformation is produced or validated.
- The chain-ordering question (classify-first vs general locator) is open.

## Run identity (to be filled at run time)

- Model: GLM-5.2 (session model), fresh isolated agent calls (general-purpose),
  one per probe.
- Gate: deterministic code (`harness/gate_I.py`); no LLM in the gate.
- Counterfactual: `det_classify` per probe, recorded.
- Sampling: one run per probe; no seed control over GLM-5.2 in the agent tool.

---

# AMENDMENT — I4 (transposed monthly table), added before the I4 run

**Status: FROZEN before the I4 run.** I1/I2/I3 were run and PASSED at `f3c3a9a`
(3-probe result frozen; not retroactively changed by this amendment — verified
by re-grading). I4 is the probe the designer named as "the first probe where
the saved macro should be allowed to be wrong."

## The probe

```text
Kuukausi | ART-001 | ART-002 | ART-003
Tammi    | 10      | 7       | 5
Helmi    | 12      | 9       | 7
Maalis   | 8       | 11      | 6
... (12 months down rows; products across columns)
```

This is a **transposed wide** representation: months run down a column and
products run across the header, with values in cells. It is **not** the
canonical long form (`Product | Month | Sales`, one row per product-month).
Calling it `long` just because months run downward would confuse **month
orientation** with **table grain/shape**.

## Frozen expectations — the macro is knowingly wrong

```text
det_classify(I4) = long       (FROZEN, WRONG, left unchanged -- do not "fix" it)
expected(I4)     = unknown
```

The deterministic classifier is left **unchanged**. It will say `long` because
`dl = 12 ≥ 3` (months down a data column). That wrong prediction is the whole
value of I4: the first case where a saved deterministic macro encounters a
representation outside its applicability and makes the wrong classification.

## Grader for I4 — the oracle, not the verifier

For I1/I2/I3 the grader is the verifier: `i_pass = (llm_label == expected) AND
gate.supported`. **For I4 the verifier is SUSPENDED.** The frozen fixture
expectation is the grader:

```text
LLM label == unknown  -> I4 PASS
LLM label != unknown  -> I4 FAIL
det_classify == long  -> recorded counterfactual MISS (not a fail of I4; the point)
```

Why the verifier is suspended: `dl = 12` would make `gate.supported(long) =
true` and `gate.supported(unknown) = false`. If we let that gate I4, we would
quietly solve I4 deterministically in order to verify the LLM — and the LLM's
correct `unknown` would be marked unsupported. So for I4 the verifier's
support values are **recorded as evidence** but do **not** gate `i_pass`:

```text
hw = 0          (recorded)
dl = 12         (recorded)
supported(long)    = true   (recorded; NOT interpreted as support for long here)
supported(unknown) = false  (recorded; the evidence rule I4 falsifies)
```

I4 exists specifically to demonstrate that **"month tokens down one column" is
not sufficient evidence for long format.** If GLM says `unknown`, that
falsifies the `dl≥3 → long` evidence rule as a general long-test — which is a
good thing to learn. The verifier design is *not* retroactively changed for
I1/I2/I3 (they keep the verifier grader, frozen); I4 simply uses the oracle
because the verifier is known-wrong on this structure.

## What I4 tests

> Can GLM notice the structural difference — months down rows with several
> product/value columns is not canonical long — and return `unknown`, while
> the saved macro confidently (and wrongly) says `long`?

- **GLM says `unknown`** → I4 PASS. The macro-saver lifecycle gets its first
  really interesting example: the agent catches a case the saved macro cannot
  handle, and its successful judgement becomes material for improving the
  macro (candidate rule v2: distinguish "months down a single label column
  with one value column" = long, from "months down a label column with
  *several* entity columns" = transposed wide / unknown).
- **GLM says `long` (or `wide`)** → I4 FAIL. GLM did not catch the structural
  difference; it followed the same coarse signal as the macro.

Either outcome is informative and is recorded as-is; pass criteria are not
relaxed after the fact.

## No fourth label

`transposed_wide` is **not** added as a fourth label. Adding it would change
the classification problem instead of testing whether the existing three-way
contract correctly rejects an out-of-contract representation. I4's expected
label is `unknown` under the frozen wide/long/unknown contract.

## Hard stop — still honored

I4 is still classification only. No unpivot/reshape/transformation, no
production architecture, no macro-v2 implementation (a candidate v2 rule may
be *noted* in the result as material, but it is not built or run). The
deterministic classifier is left unchanged on purpose.

---

# AMENDMENT 2 — I5 (contrastive prototypes), added before the I5 run

**Status: FROZEN before the I5 run.** I4 ran and FAILED (`cd91bd4`): the macro
said `long` (wrong, frozen), GLM said `wide` (also wrong) — neither said
`unknown`. I5 is the designer's contrastive probe to isolate *why* GLM failed:
**contract underspecification** vs **genuine contextual-classification limit**.

## The probe — only the contract changes

I5 uses the **same frozen I4 fixture** (`fixtures/I4.csv`, unchanged), the
**same three labels** (`wide`/`long`/`unknown`), and the **same expected
label** (`unknown`). The deterministic classifier is **unchanged** — it still
says `long` on this fixture (`det_classify=long`, wrong). The grader is the
same oracle (verifier suspended; `dl=12` is evidence, not long-support).

The **only** change from I4 is the LLM contract: instead of word definitions,
the prompt first shows two category prototypes, then the target, then asks for
the label with "Use unknown if it matches neither supplied representation."

```text
WIDE example
Product | Jan | Feb | Mar
A       | 10  | 12  | 8
B       | 7   | 9   | 11

LONG example
Product | Month | Sales
A       | Jan   | 10
A       | Feb   | 12
B       | Jan   | 7

[then the unchanged I4 fixture, in its standard ROW N rendering]

Classify the monthly representation as: wide / long / unknown.
Use unknown if it matches neither supplied representation.
Output ONLY {"format": ...}.
```

Crucially: do **not** name "transposed wide," and do **not** give a rule like
"long requires one row per product-month." Let the examples establish the
distinction. That is the whole point — testing whether canonical examples
carry the category boundary that three words did not.

## Frozen expectations

```text
det_classify(I5) = long    (UNCHANGED, WRONG; same fixture as I4)
expected(I5)     = unknown
grader           = oracle  (i_pass = llm_label == unknown; verifier suspended)
```

## The clean branch

```text
I4 (word contract)        -> wide     (observed, cd91bd4)
I5 (prototype contract)   -> ?        (this run)
```

- **I5 → `unknown`**: GLM *can* distinguish canonical long from transposed-wide
  structure when given prototypes. The I4 failure was **contract
  underspecification**, not a capability limit. Practical upshot for the skill
  idea: the skill may need a couple of canonical examples, not pages of
  instructions. (Caveat: the prototypes are English, the target is Finnish —
  see limitations — so a fully clean follow-up would use matched-language
  prototypes.)
- **I5 → `wide` (or `long`)**: even with prototypes GLM does not distinguish.
  Stronger evidence of a **genuine contextual-classification limitation**
  rather than mere contract ambiguity.

Either outcome is informative and recorded as-is; pass criteria are not
relaxed.

## What I5 does NOT establish

- **n=1, no seed control.** A single I5 sample. If I5→`unknown`, it is one
  sample of the prototypes working; reliability unmeasured.
- **The I3-mechanism hypothesis stays a hypothesis.** I4 made "I3's `unknown`
  was token-absence-driven" plausible (I3 had no month tokens; I4 had them
  down a column and GLM said `wide`). But one run on each, no controlled
  contrast (unlike 3C's 2×2) — not isolated. I5 bears on it indirectly but does
  not isolate it.
- **Cross-language caveat.** Prototypes are English (`Product/Month/Sales`,
  `Jan/Feb/Mar`); the target is Finnish (`Kuukausi`, `Tammi..`). Deliberate:
  the prototypes are generic category illustrations and the cross-language
  match tests structural (not lexical) generalization. But it is a stated
  caveat on the inference; a matched-language follow-up would be cleaner.

## Hard stop — still honored

I5 is classification only. No transformation, no macro-v2 implementation, no
fourth label. The deterministic classifier is left unchanged on purpose.