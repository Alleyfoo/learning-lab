# Experiment I — Wide / Long / Unknown format classification: Result

**PASS — `overall=True`.** The model correctly distinguishes ordinary wide,
ordinary long, and neither, and each label is objectively supported by the
month-token evidence. The deterministic heuristic classifies all three
correctly too, so for these clean shapes the LLM is correct but not needed —
the macro-saver outcome, extended from H (locate) to I (classify).

```text
I1  wide control   product + 6 month columns     LLM wide    hw=6  supported  PASS
I2  long control    Product|Kuukausi|Myynti       LLM long    dl=3  supported  PASS
I3  unknown control quarterly Q1-Q4 (no months)   LLM unknown hw=0,dl=0        PASS

i1_i2_pass=True   all_probes_pass=True   overall=True
```

This is step 2 of the skill chain the designer named (locate → **classify** →
roles → transform). Classification only — no unpivot, no reshape, no
transformation code (hard stop honored).

---

## The architecture (frozen)

```text
input: pre-located header row (row 1) + 3-5 data rows
        |
        v
deterministic classifier (COUNTERFACTUAL + deterministic-first):
    hw = distinct reference months in the HEADER row (tolerant match)
    dl = max distinct reference months in any single DATA column
    hw >= K_w (3) -> "wide"
    dl >= K_l (3) -> "long"        (only if not wide; wide takes precedence)
    else         -> "unknown"
    reference: experimentH/reference/months.json (frozen, by path)
        |
        v
classifier LLM (GLM-5.2, fresh isolated context): wide | long | unknown
        |
        v
VERIFIER GATE (objective, code, not LLM; VERIFIES, does NOT override):
    wide    supported iff hw >= K_w
    long    supported iff dl >= K_l
    unknown supported iff hw < K_w AND dl < K_l
        |
        v
i_pass = (llm_label == expected) AND supported
det_ok = (det_classify == expected)   # counterfactual
```

### Why a verifier gate, not an authority

H's gate *owned* authority because `coverage==12` is a crisp, exact
applicability predicate: a row either covers all 12 references or it does not.
I has no such crisp predicate. The deterministic classifier is a **coarse
heuristic** — it is objective about *month-token presence* (count months in
the header vs in a data column) but blind to *structure* (it cannot tell a
genuine long table from a transposed wide table; both put months in a data
column). So the gate does **not** promote the heuristic into authority. It
does the appropriately weaker thing the designer specified:

```text
LLM says wide    + months actually occur across the header  -> supported
LLM says long    + months actually occur down a data column  -> supported
LLM says unknown + neither pattern established              -> supported
```

An unsupported claim (e.g. a hallucinated `wide` with no months in the header)
is flagged `supported=false` and fails `i_pass`. The LLM's classification is
the primary measurement; the gate is the safety check that the claim is
grounded; the deterministic classifier is the counterfactual. The LLM is
*allowed to be right for contextual reasons the heuristic cannot check*; it is
not allowed to assert a representation the evidence does not support.

---

## The three findings

### 1. I1 — ordinary wide is a deterministic macro

Header has 6 month-name columns (`Tammi..Kesä`); data rows are numeric. The
deterministic classifier returns `wide` (`hw=6 ≥ 3`); the LLM returned `wide`;
the gate verified `hw≥3` → supported. The rule alone suffices (`det_ok=true`).
This is the boring case: when the spreadsheet literally has months as columns,
deterministic code wins and no intelligence is owed.

### 2. I2 — ordinary long is a deterministic macro

Header is `Tuote | Kuukausi | Myynti` (no month names — `Kuukausi` is the
Finnish word for "month", not a month name); the `Kuukausi` data column carries
`Tammi/Helmi/Maalis` (3 distinct months). The deterministic classifier returns
`long` (`dl=3 ≥ 3`); the LLM returned `long`; the gate verified `dl≥3` →
supported. Again the rule alone suffices. The long header is recognised by
where the months *are* (a data column), not by a month-name label in the
header — which is exactly why the classifier keys on data-column coverage.

### 3. I3 — `unknown` is a real output, not decorative vocabulary

This is the probe I1/I2 cannot substitute for. I3 is a quarterly summary
(`Tuote | Q1 | Q2 | Q3 | Q4 | Vuosi`): temporal data, but **not monthly wide or
monthly long** under the contract. There are no month-name tokens anywhere
(`hw=0, dl=0`), so the deterministic classifier returns `unknown` and the gate
accepts `unknown` (neither pattern established).

The load-bearing observation: **GLM returned `unknown`, not `wide`.** A model
classifying generic *pivot shape* ("values spread across columns → wide")
would have said `wide` here, because quarters are spread across columns. It
did not. It classified the thing the contract asked for — *monthly
representation* — and refused because the monthly representation is absent.
That is the distinction the designer wanted: `unknown` is a real refusal, not
a decorative third label. And again `det_ok=true`: the no-month heuristic
subsumes this refusal too.

---

## The counterfactual — the same macro-saver story, transposed

| Probe | det_classify | det_ok | LLM needed? |
| --- | --- | --- | --- |
| I1 | wide (`hw=6`) | yes | no |
| I2 | long (`dl=3`) | yes | no |
| I3 | unknown (`hw=0,dl=0`) | yes | no |

The deterministic month-token heuristic classifies all three controls
correctly with no LLM. So for these three shapes the LLM is a **discovery
mechanism, not a runtime component** — the same outcome H reached for
location, now reached for classification. The saved macro for step 2 is:

> Count distinct reference months in the header (`hw`) and in each data
> column (`dl`). `hw≥3 → wide`; else `dl≥3 → long`; else `unknown`.

The LLM earned nothing on these three shapes that the rule did not already
own. That is the expected result for *clean* controls, and it is exactly why
the interesting case is deferred to I4.

---

## What this establishes

- **The model can reliably distinguish ordinary wide, ordinary long, and
  neither** on the clean controls, with each label objectively supported.
- **`unknown` is a real output.** GLM refused on quarterly data rather than
  force a wide/long label — it is classifying *monthly representation*, not
  generic pivot shape. This is the thing I1/I2 could not test.
- **The verifier gate is appropriately weaker than H's authority gate**, and
  that is correct: I has no crisp applicability predicate, so the gate checks
  support rather than substituting its own answer. The heuristic is evidence,
  not authority.
- **The macro-saver outcome extends from locate (H) to classify (I).** For the
  clean shapes, the deterministic heuristic subsumes the LLM.

## What this does NOT establish

- **The heuristic is coarse and will be wrong on transposed wide** (deferred
  to I4). A transposed monthly table (`Month | ART-001 | ART-002` with months
  as rows) puts months in a data column → the heuristic says `long`, but
  semantically it is a **transposed wide** representation, not the ordinary
  long form (`Product | Month | Sales`). There the rule says one thing and the
  model can add contextual judgement. That is the first case where the LLM
  would genuinely earn its keep, and where the verifier-not-authority design
  pays off: the gate will not force the heuristic's wrong `long` over the
  model's judgement.
- **n=1 on GLM-5.2, no seed control.** Existence, not reliability. The model
  was correct on three single samples; the heuristic on three single fixtures.
  *Always* vs *once* is unmeasured.
- **Classification only.** No unpivot/reshape/transformation is produced or
  evaluated. Step 3 (which columns carry the roles) and step 4
  (transformation) are not authorized by running I.
- **The chain-ordering question is open.** H is a wide-header locator and
  returns `ask_human` on long; I classifies a pre-located extract. Whether
  production is classify-first-then-locate or a single general locator is
  unresolved and not required by I.

---

## Run identity

| | |
| --- | --- |
| Classifier | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per probe |
| Contract | wide/long/unknown monthly-representation classification; JSON output only; monthly representation specifically (generic pivot shape is not wide) |
| Gate | deterministic code (`harness/gate_I.py`); verifier (support check), no LLM in the gate, no override |
| Counterfactual | `det_classify` per probe, recorded (`det_ok` all true) |
| Sampling | one run per probe; no seed control over GLM-5.2 in the agent tool — cannot distinguish *always* from *once* |
| Fixtures | I1/I2/I3 authored + frozen for I |
| Freeze | preregistration + expected + fixtures + harness at `7c7ad0b`; self-test PASSED; run + grade this commit |

## Decision rule — which branch fired

Preregistered decision table: `I1 AND I2 AND I3 all i_pass` → PASS. Fired
exactly. `i_pass` required `llm_label == expected AND supported` — satisfied on
all three. The counterfactual (`det_ok`) is non-scoring and recorded alongside;
it did not change any pass flag (it was true on all three regardless).

## Hard stop — honored (scope ruling for I)

I is a classification label, not a transformation. No normalization, no
numeric parsing, no country mappings, no Python transformation / unpivot /
reshape generation, no multiple sheets, no joins, no procedure synthesis, no
production architecture. The transposed-wide probe (I4) is the named next
probe but was explicitly excluded from this run ("establish the basic
three-way classifier before introducing cases where the LLM and deterministic
heuristic disagree"). Running I authorized only the classification measurement
on the three frozen fixtures.

## Where this points (not a commitment, not authorization)

The designer named the next probe: **I4 — transposed monthly table**.

```text
Month  | ART-001 | ART-002
Tammi  | 10      | 7
Helmi  | 12      | 9
Maalis | 8       | 11
...
```

The deterministic heuristic will likely see months down a column and call it
`long`, but semantically that is a **transposed wide** representation, not the
ordinary long form. That is the first case where the rule may say one thing
and the model can add contextual judgement — exactly where the
verifier-not-authority design matters (the gate will not force the heuristic's
`long` over the model's judgement) and where the LLM would genuinely earn its
keep. It needs its own preregistration freeze before any run. Not authorized
here.