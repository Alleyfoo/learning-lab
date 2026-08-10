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

---

# AMENDMENT — I4 result (transposed monthly table): FAIL

**I4 FAILS as run.** GLM did not catch the structural difference. This is the
first probe where the saved macro was allowed to be wrong — and on this single
sample the agent did not rescue it.

```text
                     macro (v1)     GLM          expected
I4 transposed wide    long (WRONG)   wide (WRONG)  unknown
```

The frozen predictions held exactly: `det_classify(I4) = long` (wrong,
unchanged on purpose), `expected = unknown`. GLM returned `{"format": "wide"}`,
not `unknown`.

## What happened

- **The saved macro said `long`** — wrong, as frozen-predicted. `dl = 12`
  (months down the `Kuukausi` data column) triggers `dl≥3 → long`. This is the
  macro's known blind spot: it confuses *month orientation* (months down a
  column) with *table grain/shape* (canonical long is `Product | Month | Sales`,
  one row per product-month — not months down a label column with several
  product columns across).
- **GLM said `wide`** — also wrong, and wrong *differently*. It reverted to
  generic pivot-shape classification ("values spread across columns → wide").
  This is precisely the failure mode GLM *avoided* on I3, where it correctly
  returned `unknown` on a quarterly table with products across columns. On I4
  it did not hold the line: it saw products across columns and said `wide`,
  even though the months are not across the header (`hw = 0`).
- **Neither said `unknown`.** The macro-saver lifecycle did **not** get its
  happy example on this sample: the agent did not catch the case the saved
  macro cannot handle. No candidate rule v2 emerges from a run where the agent
  was also wrong.

## The verifier, and what I4 falsifies

GLM's `wide` claim is `supported = false` under the verifier (`hw = 0 < 3` —
no months in the header). So GLM's answer fails **both** graders: the oracle
(`wide ≠ unknown`) *and* the verifier (`wide` unsupported). It is not a case of
the LLM being right for contextual reasons the heuristic cannot check; it is a
case of the LLM being wrong, and ungrounded.

The frozen `dl≥3 → long` evidence rule is **falsified as a general long-test**:
`dl = 12` here, yet the correct label is `unknown`, not `long`. "Month tokens
down one column" is not sufficient evidence for long format. This was the
explicit purpose of I4, and the falsification is now demonstrated — by the
macro being wrong, not by the LLM being right.

## Grader (frozen, oracle for I4)

```text
i_pass(I4) = (llm_label == unknown)             # oracle; verifier suspended
           = (wide == unknown) = false           # FAIL
det_ok(I4) = (det_classify == unknown) = false   # counterfactual MISS (the point)
supported(I4, wide)    = (hw >= 3) = false       # GLM's claim ungrounded
supported(I4, long)    = (dl >= 3) = true        # recorded; NOT gating; the falsified rule
supported(I4, unknown) = (hw<3 and dl<3) = false  # the verifier would reject the RIGHT answer
```

The verifier is suspended for I4 exactly because `supported(unknown) = false`
here: the coarse evidence rule would reject the correct answer. Letting it
gate would mark the LLM's correct `unknown` (had it given one) as unsupported.
The oracle grader is what makes I4 fair.

## What this establishes

- **The saved macro v1 is wrong on transposed wide** (says `long`), as
  frozen-predicted. `dl≥3 → long` is insufficient: month orientation ≠ table
  grain. This is now demonstrated, not just asserted.
- **On this single sample, GLM did not catch it.** It said `wide`, reverting to
  generic pivot-shape classification — the failure mode it avoided on I3. So
  GLM does not *reliably* distinguish transposed wide from wide/long on n=1.
- **I4 is an informative FAIL**, recorded as-is. Pass criteria were not
  relaxed. The 3-probe I1/I2/I3 PASS (`f3c3a9a`) is **not** retroactively
  changed — I4 is graded separately (stage `i4`, `judgements/I4.json`).

## What this does NOT establish

- **n=1, no seed control.** GLM said `wide` once. It may say `unknown` on
  another sample; reliability is unmeasured. This is a single existence sample
  of the failure, not a frequency.
- **The I3-vs-I4 contrast is an observation, not an isolated mechanism.** GLM
  said `unknown` on I3 (no month tokens anywhere) and `wide` on I4 (month
  tokens present, down a column). That contrast is *consistent with* the
  hypothesis that I3's `unknown` was token-absence-driven rather than
  structure-driven — but with one run on each probe and no controlled contrast
  (unlike 3C's 2×2), the mechanism is **not established**. I4 makes the
  hypothesis plausible; it does not isolate it. I5 (contrastive prototypes)
  bears on this: if prototypes flip I4 to `unknown`, the original contract
  was underspecified; if not, a contextual-classification limitation is more
  likely. Either way the token-absence reading stays a hypothesis until a
  controlled probe isolates it.
- **No candidate rule v2 is extracted.** The macro-saver lifecycle's
  interesting example requires the *agent* to solve the instance the macro
  cannot; here the agent also failed, so there is no successful judgement to
  distil into a v2 rule. A v2 rule (distinguish "months down a single label
  column with one value column" = long, from "months down a label column with
  several entity columns" = transposed wide / unknown) can be *designed* from
  the structural definition, but it is not *discovered* from this run.
- **Not** a production architecture; classification only; hard stop honored.

## Where this points (not a commitment, not authorization)

The macro-discovery question is now sharper. I4 showed the macro v1 is wrong
on transposed wide — but the agent did not, on this single sample, provide the
correct judgement to learn from. Candidate next probes (each needs its own
freeze):

1. **Re-run I4 across samples / seeds** — does GLM ever say `unknown` here?
   n=1 so far; reliability of the contextual judgement is the open question.
2. **A prompted/contextual I4 variant** — give the agent the canonical long
   definition explicitly contrasted with transposed wide, and see whether it
   then returns `unknown`. This tests whether the failure is a capability gap
   or a contract-clarity gap.
3. **Design macro v2 by hand** (not discovered) — encode "months down a label
   column with several entity columns → unknown", and verify it classifies
   I1–I4 correctly. This would be the deterministic-first path catching up to
   the structural distinction, by design rather than discovery.

The honest summary: I4 is the first probe where the saved macro is wrong, and
on this single run the agent was wrong too — so the macro was not improved by
the agent this time. The `dl≥3 → long` rule is falsified; what is *not*
established is that the agent can reliably supply the judgement the macro
lacks. That is the reliability question, now foregrounded.

---

# AMENDMENT 3 — I5 result (contrastive prototypes): FAIL

**I5 FAILS as run.** GLM said `wide` — the same label it gave on I4 — even with
the two canonical prototypes shown first. The contrastive probe did **not**
isolate a contract-underspecification fix.

```text
                        contract              GLM          expected
I4  word definitions     (no prototypes)       wide          unknown   (FAIL)
I5  two prototypes       (WIDE + LONG)         wide          unknown   (FAIL)
```

I5 used the **same frozen I4 fixture**, the **same labels**, the **same
expected `unknown`**, and the **same oracle grader**. The only change was the
contract: word definitions → two canonical prototypes, then "Use unknown if it
matches neither supplied representation." The deterministic classifier was left
unchanged (`det_classify = long`, wrong, on both).

## The branch resolved — toward a contextual-classification limitation

Per the frozen decision table, `I5 → wide` is the branch for **stronger
evidence of a genuine contextual-classification limitation** rather than mere
contract ambiguity. GLM did not match the target against the prototypes and
refuse; it again classified generic pivot shape ("products across columns →
`wide`"), ignoring that in the WIDE prototype the columns are *months*, not
products.

A useful contrast in error direction: the macro and GLM are wrong in
**different ways**.

```text
macro v1:  months DOWN a column      -> long   (keys on month orientation)
GLM:       products ACROSS columns   -> wide   (keys on column spread)
expected:  neither prototype matches -> unknown (keys on canonical structure)
```

Neither keys on the canonical-structure match the prototypes were meant to
establish. So on this single sample, examples did not carry the category
boundary that words did not.

## What this establishes

- **Prototypes did not fix it.** I4→`wide` and I5→`wide` on the same fixture.
  The I4 failure was not solved by supplying canonical examples — so it is not
  *merely* contract underspecification (on n=1, with the cross-language caveat).
- **The failure is structural, not lexical.** GLM is not following the
  macro's "months down → long" cue; it is following a "values across columns →
  wide" cue. Both are surface-shape heuristics; neither is the canonical-structure
  judgement the contract asks for.
- **I5 is an informative FAIL**, recorded as-is. Pass criteria not relaxed.
  I1/I2/I3 frozen PASS and I4 FAIL are unchanged; I5 is graded separately
  (stage `i5`).

## What this does NOT establish

- **n=1, no seed control.** GLM said `wide` once with prototypes. It may say
  `unknown` on another sample; reliability is unmeasured. This is one sample
  of the prototypes *not* working, not a frequency.
- **Cross-language caveat.** Prototypes are English (`Product/Month/Sales`,
  `Jan/Feb/Mar`); the target is Finnish (`Kuukausi`, `Tammi..`). The
  cross-language match was deliberate (tests structural, not lexical,
  generalization) but is a stated caveat: a matched-language I5 could in
  principle flip the result, and would be the cleaner isolation. GLM is
  multilingual and the structure is language-independent, so the language
  difference is a secondary explanation, not the primary one — but it is not
  ruled out.
- **The I3-mechanism hypothesis stays a hypothesis.** I5 does not isolate
  whether I3's `unknown` was token-absence-driven; that needs a controlled
  contrast (a 3C-style 2×2), not these single samples.
- **Not** a production architecture; classification only; hard stop honored.

## Where this points (not a commitment, not authorization)

I5 operationalized the I4 "candidate #2" (contract-clarity vs capability gap)
in the designer's chosen form — prototypes, no rule-naming. The answer on this
single sample: prototypes did not fix it. The candidate next probes (each needs
its own freeze):

1. **Matched-language I5** — Finnish prototypes (same vocabulary as the target)
   to remove the cross-language caveat and re-test. Cheapest way to tighten
   the inference.
2. **Re-run I4/I5 across samples / seeds** — does GLM *ever* say `unknown`
   here? n=1 so far; reliability is the open question.
3. **A rule-naming variant** — explicitly contrast canonical long with
   transposed wide by *rule* ("long requires one row per product-month;
   months down a label column with several entity columns is not long"). This
   crosses the line the designer held (let examples, not rules, establish the
   distinction), so it is a different test — but it would separate "no amount
   of contract helps" from "rules help where examples didn't."
4. **Hand-design macro v2** (not discovered) — encode "months down a label
   column with several entity columns → unknown" and verify it classifies
   I1–I5 correctly. The deterministic-first path catching up by design. The
   designer's stated preference: only design v2 *after* finding out whether a
   compact skill can teach the agent the distinction — I5 suggests, on n=1,
   that two examples alone do not.

The honest summary: I4 and I5 together show that, on this single sample, GLM
classifies the transposed monthly table as `wide` whether or not it is given
canonical prototypes. The macro is wrong (`long`); the agent is wrong (`wide`);
neither produces the `unknown` the contract expects. The `dl≥3 → long` rule
is falsified, and the agent did not supply the judgement to replace it. The
reliability question — and whether a matched-language or rule-naming contract
changes this — remains open.