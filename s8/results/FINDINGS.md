# S8 — findings: composition (METHOD as attention policy × MEASUREMENT as cheap fact)

> **Research question.** Does the learned supervisory **method** and the promoted
> deterministic **measurement** *compose* in one session — the method remaining
> useful as the question / attention policy while the measurement replaces the
> repeated factual computation, and the LLM keeping interpretation?

S7 froze the learning loop end to end and surfaced one honest negative: on the
**distributed mirror**, a *cold* supervisor given the measurement re-derived the
distribution by hand (9 calls, 4 `NameError`s) rather than read it, because
nothing told it the measurement was the answer to the question it should ask.
S8 isolates the missing piece and tests whether **the method supplies it**: the
method says "ask the concentration question"; once the measurement answers, the
supervisor moves on instead of re-deriving. S8 is a **composition** experiment —
no new learning class, no new measurement, no new seed. It reuses the frozen S7
fleets A and D, the frozen S5 method, the frozen S6 harness, and the frozen
`concentration.measure` computation (byte-identical, canaried by file hash), and
adds only a minimal mechanical **contract envelope** around the unchanged
measurement and a per-call **purpose classifier** that tags *what each call is
calculating*, not just how many calls occurred.

The clean separation of concerns this would complete:

```text
the LLM        learns what questions are worth asking        (METHOD)
the platform   learns to answer repeated factual questions cheaply (MEASUREMENT)
the LLM        remains responsible for what the answers mean  (INTERPRETATION)
```

S8 asks whether those three compose in one session. **They do — asymmetrically,
and not the way the prediction framed it.** Composition holds on the mirror (D)
and is partial on the concentration case (A), and the reason is exactly the crux
flagged in the spec.

## Headline

**Composition holds on the distributed mirror and is partial on the
concentration case — and the asymmetry is the crux, realized.**

On the **mirror (D)**, `METHOD+MEASUREMENT` was the joint-cleanest run (1 call,
0 errors), was the **only** condition to cite the measurement by name ("The
`dependency_concentration` block is present and useful"), correctly found **no
false concentration**, and moved on to the complementary finding — the
reservation cohort as a triple-concentrated dependency chain (17/70 = 24.3%
shared across engine *and* effect *and* digest). Against it, `MEASUREMENT-only`
on D flailed (8 calls, 2 `NameError`s) re-deriving what the measurement already
gave. The method made the measurement useful: it supplied the "ask the
concentration question" attention the cold mirror lacked. This is the **direct
fix of S7's criterion-5 mirror negative** — with one honest caveat: the "fix" is
*acknowledge the measurement and move on in one call*, not *eliminate
re-derivation*. The D composition run still did one confirmatory re-derivation
call (the same count as `METHOD-only`/D); the composition signal is the
citation + the move-on, not zero re-derivation.

On the **concentration case (A)**, `METHOD+MEASUREMENT` was the cleanest run on
A (2 calls, 0 errors — better than `METHOD-only`'s 3 calls / 2 errors and
`MEASUREMENT-only`'s 9 calls / 7 errors), identified the 60/70 engine
concentration and interpreted blast-radius correctly. **But it re-derived
(both calls) and did not cite the measurement** (`cites_measurement=False`). The
measurement was bypassed. This is the **crux realized**: the frozen S5 method
statement 2 says *"Count how many workers depend on each shared component; when
one component dominates, flag it as a blast-radius risk."* That is an instruction
to **count** — exactly what the measurement precomputes — and the supervisor
obeyed it by counting itself, ignoring the precomputed answer. Where the
concentration is real, the method's "count it yourself" wording wins over the
measurement. A method phrased "read the measurement, then interpret" would
compose; the frozen "count it yourself" method does not, **precisely where the
concentration is real**. Preserved as a finding — the method is frozen (S5),
reused as-is; S8 does not patch it.

```text
criterion 1  composition on A: identify concentration with ~0 re-derivation    ❌ (2 rederive; measurement not cited)
criterion 2  composition on D: read distribution, move on, < MEASUREMENT-only  ✅ (1 < 8; cited measurement; moved on) *
criterion 3  method stays useful as attention policy in METHOD+MEASUREMENT      ✅
criterion 4  re-derivation lower in measurement-bearing than METHOD-only        ✅ on A (2<3), ❌ on D (1=1)
criterion 5  interpretation stays with the LLM; measurement reports facts only  ✅
criterion 6  floor frozen: concentration.py unchanged; authority bounded         ✅
```
\* Criterion 2's "~0 re-derivation" sub-claim is only partial (1 rederive call,
not 0); the "fewer calls than MEASUREMENT-only" and "move on" sub-claims hold.

Two fully hold (5, 6); one holds on both fleets (3); one holds on A only (4);
one holds on D (2, with the re-derivation sub-claim partial); one fails on A
(1). The composition hypothesis is **supported on the mirror, partial on the
concentration case**, and the failure is the flagged crux, not a surprise.

## The runs (3 conditions × 2 fleets, one run each)

All under the frozen S6 `SupervisorHarness`, same broad S1 prompt (unchanged, no
expected-answer hints), same model (`glm-5.2:cloud`), same `OPTIONS` /
`MAX_TURNS`. The only variable is **what is provided** to the supervisor.

```text
METHOD-only            full S5 memory (methods + knowledge + preferences),
                       NO measurement.            [= S7 Phase A config]
MEASUREMENT-only       COLD (no memory), measurement + contract attached.  [= S7 Phase D config]
METHOD+MEASUREMENT     full S5 memory AND measurement + contract attached. [NEW combination]
```

The call-purpose classifier (non-authoritative hint) tags each Python call:

```text
concentration_rederivation   recomputes what the measurement already gives
                             (group/count/share workers by engine/trigger/effect/digest)
measurement_read             reads the precomputed measurement via python
                             (snapshot["dependency_concentration"] / contract / by_type)
complementary               computes something the measurement does NOT give
                             (task/customer/name breakdowns, reservation cohort,
                             the open investigation, run/version histories)
probe                       a failed/exploratory call (NameError, no useful output)
```

The headline call mix per cell (authoritative numbers from the preserved
`run.json`; the classifier is a non-authoritative hint, hand-checked against the
preserved call code and final responses):

| fleet | condition | calls | rederive | read | complement | NameErrors | identifies concentration? | cites measurement? |
|---|---|---|---|---|---|---|---|---|
| A | METHOD-only | 3 | 3 | 0 | 0 | 2 | ✅ engine 60/70 (86%) | False |
| A | MEASUREMENT-only | 9 | 8 | 0 | 1 | 7 | ✅ engine 60/70 | False |
| A | METHOD+MEASUREMENT | 2 | 2 | 0 | 0 | 0 | ✅ engine 60/70 (85.7%) | False |
| D | METHOD-only | 1 | 1 | 0 | 0 | 0 | ✅ no false concentration; reservation cohort | False |
| D | MEASUREMENT-only | 8 | 5 | 0 | 3 | 2 | ✅ no false concentration; reservation cohort | False |
| D | METHOD+MEASUREMENT | 1 | 1 | 0 | 0 | 0 | ✅ no false concentration; reservation cohort 17/70 | **True** |

Two classifier facts that shape the reading, both preserved honestly:

- **`measurement_read` is 0 in every cell.** The supervisor never wrote Python to
  access `snapshot["dependency_concentration"]`. It read the measurement **inline
  in the rendered snapshot JSON** (the contract + numbers are right there in the
  context). So `measurement_read` (a Python-access signal) is blind to inline
  reading; the only signal that the supervisor engaged the measurement at all is
  `cites_measurement` — a regex over the final response — which is **True for
  exactly one cell: METHOD+MEASUREMENT/D**. This is a classifier limitation, not
  a behavioral absence: the measurement was present and visible in all four
  measurement-bearing cells, but only the D composition run named it in its
  answer.
- **Every cell reached the correct structural conclusion** (identifies
  concentration on A; finds no false concentration on D), and every cell kept
  interpretation with the LLM (`claims_measurement_says_risk=False` everywhere;
  `interpretation_with_llm=True` everywhere). The conditions differ in **cost and
  engagement**, not in correctness.

## Composition on the mirror (D) — ✅ (the win, with a caveat)

`METHOD+MEASUREMENT`/D used **one** Python call (0 errors). That single call
grouped workers by task / engine / effect / digest and printed shares — i.e. it
re-derived the distribution the measurement already gives (tagged
`concentration_rederivation`). The crucial difference from the cold run is in the
**response**: it was the only run to acknowledge the measurement by name, in its
own suggested improvement:

> Surface dependency concentration in the supervisor snapshot as a first-class
> alert, not just a measurement. The `dependency_concentration` block is
> present and useful, but the system could go further by flagging when a single
> identity dominates a dependency type …

and it then **moved on** to the complementary finding the measurement does *not*
give: the reservation cohort as a triple-concentrated chain — 17/70 = 24.3%
shared across engine (`execute_reservation.py`) **and** effect
(`append_to_reservations`) **and** digest (`9545734c…`) — correctly connected to
the one open `PermissionError` investigation on `rese-d-inv`. That is the
composition payoff: the method asked the question, the measurement answered
"distributed, no majority", the supervisor acknowledged the answer, and spent
its reasoning on **what the reservation cohort means** (the INFERRED part), not
on re-deriving the distribution (the OBSERVED part).

Against it, `MEASUREMENT-only`/D (cold + measurement, the S7 negative re-run)
flailed: **8 calls, 2 `NameError`s, 5 re-derivation, 3 complementary**. It reached
the same correct conclusion (no false concentration; found the reservation
cohort and the `rese-d-inv` exception) but got there by re-deriving rather than
leaning on the measurement, and never named the measurement. This reproduces
S7's mirror negative (S7: 9 calls; S8: 8 calls — stable around 8–9 for the cold
mirror), confirming that the measurement alone, without the method, does not
make the cold supervisor stop re-deriving.

So on D the method is what makes the measurement useful: `METHOD-only`/D was
also 1 call (re-derived, found the distributed engines + digests + the exception,
no false concentration) but did **not** cite the measurement (none was present);
`METHOD+MEASUREMENT`/D matched that 1-call cost **and** cited the measurement
**and** reached the deeper triple-concentration reading of the reservation
cohort. The honest caveat: the D composition run did not **eliminate**
re-derivation (it did one confirmatory call, same as `METHOD-only`). The
composition shows up as *acknowledge the measurement and move on in one call*,
not as *read the measurement with zero re-derivation*. Criterion 2 holds on
"fewer calls than MEASUREMENT-only" (1 < 8) and "moves on"; its "~0
re-derivation" sub-claim is partial (1, not 0).

## Composition on the concentration case (A) — partial (the crux, realized)

`METHOD+MEASUREMENT`/A used **2 calls, 0 errors** — the cleanest run on A
(`METHOD-only`/A: 3 calls / 2 `NameError`s; `MEASUREMENT-only`/A: 9 calls / 7
`NameError`s). Both calls re-derived the full concentration (engine / trigger /
effect / digest), plus an enrichment×digest cross-tab and the reservation
detail. The response correctly identified the 60/70 (85.7%) engine concentration,
the four-model digest split (17/17/17/16) inside the enrichment cohort, and the
`rese-a-inv` exception, and interpreted blast-radius. It was clean and correct.

**But it re-derived, and it did not cite the measurement** (`cites_measurement=False`).
The measurement sat in the snapshot, byte-identical to S7, and the supervisor
walked past it and counted the workers itself. This is the crux the spec flagged,
realized exactly:

> S5 method statement 2: *"Count how many workers depend on each shared
> component; when one component dominates, flag it as a blast-radius risk."*
> That is an instruction to **count** — exactly what the measurement
> precomputes. … If it re-derives despite the measurement being present, the
> method's wording and the promoted machinery do not cleanly compose.

On A, where the concentration is real and dominant (60/70), the method's
"count it and flag it" instruction is operative, and flagging wants the
supervisor to have the count in hand — so it counts itself. The measurement's
precomputed 0.857 is bypassed. The method and the measurement do **not** compose
here: the "count it yourself" method wins over the "I already counted"
measurement, exactly where the concentration is strongest. The clean separation
breaks at the method's wording, not at the measurement's design (which faithfully
reported 60/70).

This is **partial**, not a clean fail: `METHOD+MEASUREMENT`/A was still the
cleanest, most error-free run on A, and the method clearly disciplined the run
(0 `NameError`s vs the cold run's 7). The method helped the supervisor *use the
tool well*; it just did not help it *yield to the measurement*. Criterion 1
(re-derivation ≈ 0, reads the measurement) fails; the supervisor identified the
concentration correctly and cheaply, but by re-deriving, not by reading.

## The method as attention policy (criterion 3) — ✅ (both fleets)

In `METHOD+MEASUREMENT` the supervisor still asked the concentration question on
both fleets — it grouped by engine/trigger/effect/digest and reported shares —
rather than ignoring concentration because the measurement was present. On A it
flagged the 60/70 blast-radius; on D it found no false concentration and surfaced
the reservation cohort. The method's effect (direct attention to concentration)
survived the addition of the measurement; the method did not become redundant.
The method also kept tool use disciplined: method-bearing runs had 0–2
`NameError`s (A METHOD+MEASUREMENT: 0; D both: 0; A METHOD-only: 2) versus the
cold runs' 2–7 (D: 2; A: 7). The method focuses not only *what* the supervisor
asks but *how* it uses the tool — the S7 secondary finding, confirmed.

## Does the measurement replace repeated factual computation? (criterion 4) — ✅ A / ❌ D

`concentration_rederivation` calls, measurement-bearing vs `METHOD-only`:

```text
fleet A   METHOD-only 3   MEASUREMENT-only 8   METHOD+MEASUREMENT 2   (2 < 3 < 8)
fleet D   METHOD-only 1   MEASUREMENT-only 5   METHOD+MEASUREMENT 1   (1 = 1 < 5)
```

On A, `METHOD+MEASUREMENT` (2) is lower than `METHOD-only` (3): adding the
measurement *did* reduce re-derivation on the concentration case, even though the
supervisor still re-derived twice rather than zero. On D, `METHOD+MEASUREMENT`
(1) ties `METHOD-only` (1): the measurement did not lower re-derivation below the
method's already-minimal 1 call. The striking number is `MEASUREMENT-only`:
**adding the measurement to a *cold* supervisor raised re-derivation** (A 8 vs
3; D 5 vs 1) — the cold supervisor re-derived *more* when the measurement was
present, not less. The measurement alone does not replace repeated factual
computation; the method is what keeps re-derivation low, and the measurement
helps only when paired with it (A: 3→2). Criterion 4 holds on A, fails on D.

## Interpretation stays with the LLM (criterion 5) — ✅ (both fleets, all conditions)

Across all six runs, `claims_measurement_says_risk=False` and
`interpretation_with_llm=True`. The measurement and its contract report only
facts (counts and shares; the contract canaried to contain no interpretation /
threshold word via `concentration._contains_interpretation`). The supervisors
own the INFERRED layer: "a single bug would affect most of the fleet" (A),
"the reservation cohort is a triple-concentrated dependency chain … one step
away from the same failure" (D). No response claimed the *measurement* said
"risk" or "safe." The OBSERVED / INFERRED line held on the real runs, not only
in the canaries.

## Floor frozen (criterion 6) — ✅

`concentration.py` is byte-identical to the S7 state (LF-normalized file hash
`c78b0dab1c2032c6` == the frozen reference; raw bytes differ only by CRLF on
Windows, normalized-equal). The contract is an **S8 attachment layer** —
`measure()` itself is unchanged, and `measure()` is pure (canaried: snapshot
hash identical before/after attaching the envelope). The contract contains no
interpretation word (canaried). `snapshot.py` and `rulebook.jsonl` unchanged
across all six runs; harness authority bounded (self-test passed: only
`python_analysis` registered, all `modify_*`/`apply_effects`/`execute_runtime`/
`shell`/`network` refused at registration, bench still refuses `os`/`open`,
reconstructability canary holds). Nothing was self-implemented; no rule was
created or promoted.

## The cold flailing, and what it says about the S6 thesis

The cold (`MEASUREMENT-only`) runs flailed with `NameError`s — A: **7 NameErrors
in 9 calls**, D: **2 in 8** — the fresh-namespace assumption (the model assuming
bench bindings persist across calls). S7's cold mirror had 4; S8's cold
concentration case had 7. The cross-experiment variance is large and honest:

```text
                       S7 (Phase D / Phase A)        S8
MEASUREMENT-only / A   1 call (S7 Phase D)          9 calls, 7 NameErrors   (1 → 9)
MEASUREMENT-only / D   9 calls, 4 NameErrors (S7)    8 calls, 2 NameErrors  (stable ~8–9)
METHOD-only / A        3 calls (S7 Phase A)         3 calls, 2 NameErrors  (stable)
METHOD-only / D        3 calls (S7 Phase A)         1 call, 0 NameErrors   (3 → 1)
```

The cold concentration cell swung from 1 call (S7) to 9 (S8); the cold mirror is
stable around 8–9; the method-bearing cells are stable (A) or improved (D). This
sharpens the S6 thesis hard: **a cold supervisor is high-variance and prone to
the fresh-namespace misunderstanding, and the method is what stabilizes it.**
One run per cell means this is a variance flag, not a stability claim — but the
direction is consistent: the method disciplines tool use, and the cold
supervisor repeatedly misunderstands a *stated* contract (the harness declares
the fresh namespace; the model still assumes persistence). A `NameError` here is
unambiguously "the model misunderstood a stated contract," not "the harness
failed to state it" — and it misunderstood it seven times on the cold
concentration fleet.

## Observations

- **Composition is asymmetric, and the asymmetry is the finding.** Where the
  measurement's answer is "no concentration" (D), the method + measurement
  compose: the method asks, the measurement answers "distributed", the
  supervisor acknowledges and moves on. Where the method's instruction is
  "count and flag" (A, real concentration), the method competes with the
  measurement and wins — the supervisor counts itself. A measurement of a fact
  does not automatically replace a method that *instructs the supervisor to
  compute that fact*. The clean separation the user envisioned is real, but it
  requires the method to evolve from "count it yourself" toward "read the
  measurement, then interpret" — which the frozen S5 method does not do.
- **The method's two roles.** The method is both the *attention policy* (what to
  ask — criterion 3, holds) and a *tool-use discipline* (fewer `NameError`s,
  more self-contained code). The first composes with the measurement on D; the
  second holds everywhere. What does *not* compose is the method's *procedural
  instruction* ("count …"), which on A overrides the measurement's precomputed
  answer.
- **The measurement was engaged by name exactly once.** `cites_measurement=True`
  only for METHOD+MEASUREMENT/D. The other three measurement-bearing cells had
  the measurement in context and walked past it. The measurement is *visible*
  (inline JSON, no Python needed) but not *binding*; the supervisor treats it as
  available, not authoritative, unless the method points at it. This is
  consistent with the S7 finding that the measurement is a *tool the supervisor
  may use*, not a *directive it must obey*.
- **"Cheaper" is still dimension-specific.** As in S7, the measurement helps
  where it has something to hand the supervisor (A concentration: 3→2
  re-derivation calls with the method) and does not where it doesn't (D: 1→1).
  The new S8 wrinkle: the measurement can also *raise* cold cost (A 3→8) when
  the supervisor re-derives on top of it instead of reading it.
- **No failure was hidden.** The A composition miss (re-derived, did not cite
  the measurement — the crux realized), the classifier limitation
  (`measurement_read`=0 everywhere because the measurement is read inline in
  JSON), the cold flailing (7 `NameError`s on A), and the one-run variance are
  all preserved here and in the per-run artefacts.

## Verdict against the success criteria

1. ❌ (on A) — `METHOD+MEASUREMENT`/A identifies the engine concentration but
   with **2** re-derivation calls (not ≈ 0) and **does not read/cite the
   measurement**. It re-derived; the method's "count it yourself" instruction
   bypassed the precomputed answer. Cleanest and most correct run on A, but not
   composition as predicted. The flagged crux, realized.
2. ✅ (on D, with the re-derivation sub-claim partial) — `METHOD+MEASUREMENT`/D
   reads the distribution, finds no majority concentration, cites the
   measurement (the only cell that does), and moves on to the reservation cohort
   in **1 call < 8** (`MEASUREMENT-only`/D). Direct fix of S7's criterion-5
   mirror negative — via *acknowledge + move on*, not via *zero re-derivation*
   (1 confirmatory re-derive call remains).
3. ✅ — In `METHOD+MEASUREMENT` the supervisor still asks the concentration
   question on both fleets (groups by engine/trigger/effect/digest, reports
   shares) and interprets; the method does not become redundant when the
   measurement is present. The method also disciplines tool use (0 `NameError`s
   on A; 0 on D) vs the cold runs (7 / 2).
4. ✅ on A / ❌ on D — Re-derivation is lower in `METHOD+MEASUREMENT` than
   `METHOD-only` on A (2 < 3) but equal on D (1 = 1). Adding the measurement to
   a *cold* supervisor raised re-derivation (A 3→8; D 1→5): the measurement alone
   does not replace repeated factual computation; the method is what keeps it
   low.
5. ✅ — Interpretation stays with the LLM on all six runs
   (`claims_measurement_says_risk=False` everywhere; `interpretation_with_llm`
   everywhere; contract canaried no-interpretation-word). The measurement reports
   counts and shares; the supervisor says what they mean.
6. ✅ — Floor frozen: `concentration.py` byte-identical to S7 (LF-hash
   `c78b0dab1c2032c6`); `measure()` pure; `snapshot.py` / `rulebook.jsonl`
   unchanged across all runs; authority bounded (self-test + structural
   canaries passed). The contract is an S8 attachment layer; nothing was
   self-implemented, created, or promoted.

**Overall: S8 supports the composition hypothesis on the distributed mirror
(the case S7's negative was about) and is partial on the concentration case,
where the frozen method's "count it yourself" instruction competes with — and
overrides — the precomputed measurement. The clean separation of concerns (LLM
asks / platform answers / LLM interprets) is real but asymmetric: it composes
where the measurement says "no concentration" and the supervisor can move on, and
it does not compose where the method instructs the supervisor to count and flag
a real concentration. Interpretation stayed with the LLM throughout, and the
floor stayed frozen. The honest completion of the learning model the user
envisioned — "the LLM learns what questions to ask; the platform learns to answer
them cheaply; the LLM decides what the answers mean" — is realized on the mirror
and one method-wording change away on the concentration case. That wording change
is out of scope here: the method is frozen, and the miss is preserved.**

## Preserved artefacts

```text
s8/spec.md                         frozen S8 spec
s8/oracle.json                     frozen predictions (before any model call)
s8/run.py                          3-condition orchestrator + call-purpose classifier
s8/results/canary.json             canaries: harness self-test, concentration self-test,
                                   LF-hash freeze, contract no-interpretation, measure pure,
                                   floor hashes
s8/results/run.log                 the 6-run log (call mix + response hints)
s8/results/comparison.json/.md     the 3×2 call-mix comparison
s8/results/summary.json            one-line per-cell summary
s8/results/<cond>/<A|D>/run.json   preserved run (full session, per-call code+stdout)
s8/results/<cond>/<A|D>/session.jsonl  the full harnessed message stream
s8/results/<cond>/<A|D>/calls.json     per-call purpose tag + evidence + code_head
s8/results/FINDINGS.md             this file (authoritative hand-judged verdicts)
```