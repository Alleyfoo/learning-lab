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