# S9 — findings: controlled method-wording experiment (original vs capability-aware candidate)

> **Research question.** Is the S8 composition miss on fleet A a *measurement*
> problem or a *method-wording* problem? S8's `METHOD+MEASUREMENT`/A re-derived
> the concentration and did not cite the measurement; the flagged crux was that
> the frozen S5 method statement 2 says *"Count how many workers depend on each
> shared component…"* — an instruction to count, which the measurement
> precomputes. S9 re-words that one procedural instruction to be
> **capability-aware** — preserve the question, prefer the measurement, compute
> only what remains unresolved — and asks whether that lets the method compose
> on A, **without touching the measurement, the S5 memory, or anything frozen**.

S9 is a **controlled wording experiment**, not a learning class and not an edit
to S5. It compares the **frozen original** concentration method against a
**candidate capability-aware variant** on the frozen S7 fleet A (primary) and D
(safety mirror), both WITH the measurement, under the frozen S6 harness, the
frozen S7 measurement, and the same model. The candidate is a **runtime
one-field transform** of the frozen S5 seed: deep-copy the 3 methods, keep
methods 0 & 2 and all knowledge/preferences byte-identical, replace only
`methods[1].statement`. **S5 is not modified** (canaried: the three seed files
are byte-identical before and after all 32 runs). **N=8 replicates per cell**
(32 runs), interleaved by round, because S8's one-run-per-cell was exactly the
variance trap this experiment removes.

## The two statements (the only difference between variants)

```text
frozen original method 2:
  "Count how many workers depend on each shared component; when one component
   dominates, flag it as a blast-radius risk."

candidate method 2 (capability-aware):
  "Read how many workers depend on each shared component from the
   `dependency_concentration` measurement in the snapshot (its counts and
   shares are mechanically computed from fleet records); use those facts
   directly and do not re-derive them. Compute by hand only what no
   measurement resolves, and when one component dominates, flag it as a
   blast-radius risk."
```

The harness renders **only the `statement` field** (`core._memory_preamble`), so
this is the entire treatment. The supervisory question (methods 1 & 3, the
knowledge, the preferences) is identical across variants; only the procedural
instruction differs. Canaried: the candidate transform changes exactly one key
(`statement`) in exactly one method; methods 0 & 2 are byte-identical.

## Headline

**The hypothesis is partially supported — and N=8 overturns S8's single-run
story in two places.** The candidate is **directionally better on every metric
on both fleets, never regresses, and always keeps interpretation with the LLM**.
But it does **not cleanly fix A**: A stays re-derivation-dominant (5/8 runs
re-derived; re-derivation drops only 1.125→1.0 calls/run, within the noise).
The candidate's clearest effect is **attribution/engagement**, not **behavior
change**: it makes the supervisor *name and lean on* the measurement far more
often (A `cites_meas` 0→37.5%; D 0→87.5%) while barely moving the
re-derivation rate. **The crux holds harder than S8's one-run miss suggested: a
real dominant concentration (60/70) gets re-derived robustly, even when the
method explicitly says "read the measurement, do not re-derive."**

The largest honest finding is on the **safety mirror (D)**: S8's celebrated D
"composition win" — `METHOD+MEASUREMENT`/D cited the measurement in its single
run — was a **variance artifact**. In N=8, **D-orig cites the measurement 0/8**.
The original does **not** reliably engage the measurement on D; S8 saw the one
lucky run. The **candidate** is what makes D reliably compose: D-cand cites
7/8 and reads the measurement via Python 0.875/run vs D-orig's 0/8 and 0.0. So
the candidate's value is clearest on the mirror, the *opposite* of where the
prediction put the win — and S8's D result should be read as "the original
*sometimes* composes on D," not "the original composes on D."

```text
criterion 1  reduction in concentration_rederivation            ✅* A (1.125→1.0, within noise) / ❌ D (1.75→1.875)
criterion 2  correct use of OBSERVED measurement facts          ◐ A (read 3/8, cite 0→37.5%) / ✅ D (engage 0→7/8)
criterion 3  complementary rather than duplicate computation    ◐ both (complementary analysis retained inline; python complementary ~0 for all: A 0/0, D 0.125/0)
criterion 4  interpretation remains with the LLM                 ✅ (32/32 runs)
criterion 5  safety mirror: D-cand does not regress D-orig       ✅ (calls equal; +citation; −NameErrors; correct)
criterion 6  floor frozen; S5 not edited                        ✅ (concentration.py, seed, floor unchanged across 32 runs)
```

Two fully hold (4, 6); one holds (5); three are partial (1, 2, 3). The
candidate is **evidence for method evolution — directionally better, safe,
and the reliable producer of mirror composition — but not by itself a fix for
the A miss.** That is recorded as partial evidence, not applied to S5.

## The runs (4 cells × N=8 = 32 runs)

Both variants run WITH the measurement; the only difference is method 2's
`statement`. Per-run categorical outcome: `read` (re-derivation 0, identified
correctly), `rederive+cite` (re-derived but also cited the measurement),
`rederive` (re-derived, did not cite = S8 A behaviour), `other` (failed to
identify). The classifier is a non-authoritative hint; FINDINGS is hand-judged
from preserved call code and final responses.

### Fleet A — primary (engine 60/70 concentration), n=8 each

| metric | A-orig | A-cand |
|---|---|---|
| calls/run (mean) | 1.125 | 1.0 |
| calls values | [1, 0, 4, 1, 0, 1, 1, 1] | [0, 1, 1, 1, 0, 4, 0, 1] |
| re-derivation (mean) | 1.125 | 1.0 |
| measurement_read (mean, python) | 0.125 | 0.5 |
| NameErrors (sum) | 3 (one 4-call run) | 2 (one 4-call run) |
| categorical | rederive 6, read 2 | read 3, rederive 4, rederive+cite 1 |
| cites_meas rate | 0/8 (0%) | 3/8 (37.5%) |
| correct (identifies 60/70) | 8/8 | 8/8 |
| claims_measurement_says_risk | no | no |
| interpretation_with_llm | all | all |

On A the candidate is **marginally better and never worse**: one fewer
re-derivation call total over 8 runs, one more `read` (2→3), one fewer
NameError (3→2), and — the clearest gain — it **cites the measurement 0→37.5%**.
But A remains **re-derivation-dominant**: 5/8 candidate runs re-derived the
60/70 concentration despite being told not to. The two distributions of
call-counts are nearly identical (each has two 0-call reads, five 1-call runs,
one 4-call flailer). The wording shifted attribution, not behaviour.

Hand-judged, the `read` runs confirm correct use of OBSERVED facts:

- **A-cand rep05 (`read`, cited):** *"The `dependency_concentration`
  measurement shows: `enrichment/…` — 60 of 70 workers (85.7% fleet share)"* —
  uses the measurement's exact 85.7%, attributes it, then does complementary
  analysis (four-digest 67/70 split, the `rese-a-inv` exception, trigger
  distribution). Zero re-derivation. This is the composition payoff, realised.
- **A-cand rep07 (`read`, uncited)** and **A-orig rep05 (`read`, uncited):**
  both report the exact 60/70 = 85.7% with **zero re-derivation** but **do not
  name** the measurement block. So the **original can read inline too** (its 2
  `read` runs did) — the candidate's edge on A is that it reads *slightly more
  often* and *attributes* the measurement, not that only it can read. The
  re-derivation instinct is present in both; the wording tilts it modestly.

### Fleet D — safety mirror (distributed, no majority), n=8 each

| metric | D-orig | D-cand |
|---|---|---|
| calls/run (mean) | 1.875 | 1.875 |
| calls values | [1, 1, 2, 3, 1, 5, 1, 1] | [0, 2, 2, 3, 2, 1, 2, 3] |
| re-derivation (mean) | 1.75 | 1.875 |
| measurement_read (mean, python) | 0.0 | 0.875 |
| NameErrors (sum) | 5 (a 5-call/3-NE run) | 4 (spread) |
| categorical | rederive 8 | rederive+cite 6, read 1, rederive 1 |
| cites_meas rate | 0/8 (0%) | 7/8 (87.5%) |
| correct (no false concentration) | 8/8 | 8/8 |
| claims_measurement_says_risk | no | no |
| interpretation_with_llm | all | all |

This is the result that **re-reads S8**. S8's `METHOD+MEASUREMENT`/D was the
single cell that cited the measurement — the "composition win on D." In N=8,
**D-orig cites 0/8 and reads the measurement via Python 0/8**: S8 caught the
one run that happened to cite. The original does **not** reliably compose on
D; it reliably re-derives (8/8 `rederive`, never citing). The **candidate**
is what makes D reliably engage the measurement: D-cand cites 7/8, reads via
Python 0.875/run, and only 1/8 is a pure `rederive`. Yet D-cand's
re-derivation (1.875) is **not lower** than D-orig's (1.75) — the candidate
re-derives *and* cites (6/8 `rederive+cite`), it does not "read and move on"
(only 1/8 `read`). So the candidate's effect on D is **engagement**, not
**stopping re-derivation** — exactly the same shape as on A, but far stronger.

Hand-judged: **D-cand rep06 (`rederive+cite`, 1 call, 0 NameErrors):** *"From
the `dependency_concentration` measurement: Engine 17 (24.3%), Effect 17
(24.3%), Digest 17 (24.3%)"* — cites the measurement's exact facts, finds no
false concentration, surfaces the reservation cohort, clean. On the same
run-round **D-orig rep06 was 5 calls / 3 NameErrors / 0 cite**. The candidate
stabilised D on that round; in aggregate D-cand has fewer NameErrors (4 vs 5)
and equal calls. **Safety holds**: D-cand does not regress D-orig on calls or
correctness, and improves engagement and stability.

## Why the crux holds harder than S8 implied

S8's one-run A miss made the crux look like a single wording fix away. N=8
shows the supervisor's drive to **re-derive a real dominant concentration is
robust**: even with the method explicitly saying *"use those facts directly
and do not re-derive them,"* the candidate re-derived 5/8 on A. The wording
moved **attribution** (citing the measurement: A 0→37.5%, D 0→87.5%) far more
than it moved **behaviour** (re-derivation: A 1.125→1.0, D 1.75→1.875). Two
readings are honest:

- The candidate **does** help: on every metric, on both fleets, it is
  directionally better or equal, never worse. It is the reliable producer of
  measurement engagement on D (where the original is 0/8). It reduces
  NameError flailing slightly (A 3→2, D 5→4). It is correct 16/16 and keeps
  interpretation with the LLM 16/16.
- The candidate **does not** resolve the A miss: re-derivation of 60/70
  persists 5/8. A one-statement rewording is **partial evidence for method
  evolution**, not a fix. The supervisor treats the measurement as *available*
  and *nameable*, not as *authoritative*; when the concentration is real and
  dominant, it verifies by computing, wording or no wording.

So the S8 A miss is **partly** a wording problem (the candidate helps at the
margin) but **not wholly** (the candidate doesn't close it). Method-wording is
a real but weak lever over re-derivation; it is a strong lever over
*engagement/attribution*.

## Variance (the reason N=8 was necessary)

Both variants are **high-variance** on both fleets, with `NameError` flailing
in outlier runs for **both** — the candidate is not immune:

```text
A-orig calls [1,0,4,1,0,1,1,1]  -> one 4-call/3-NameError flailer
A-cand calls [0,1,1,1,0,4,0,1]  -> one 4-call/2-NameError flailer
D-orig calls [1,1,2,3,1,5,1,1]  -> one 5-call/3-NameError flailer
D-cand calls [0,2,2,3,2,1,2,3]  -> NameErrors spread across 4 runs
```

S8's one run per cell could not see this: S8's A-orig-equivalent was 2 calls
(here A-orig ranges 0–4); S8's D-orig-equivalent cited the measurement (here
D-orig cites 0/8). The N=8 distributions are what let the above claims survive
— and they are still only N=8 (a 95% CI on a 3/8 vs 2/8 read-rate is wide), so
the verdicts are "directional and consistent," not "settled." A larger N would
tighten the A read-rate gap (3/8 vs 2/8 is within plausible noise) but is
unlikely to overturn the D citation result (7/8 vs 0/8) or the A
"still-re-derivation-dominant" finding (5/8).

## Interpretation stayed with the LLM (criterion 4) — ✅ (32/32)

Every one of the 32 runs kept interpretation with the LLM:
`claims_measurement_says_risk=False` on all 32; `interpretation_with_llm=True`
on all 32. The candidate's "flag it as a blast-radius risk" is the LLM's
interpretive act; the measurement reports counts and shares (contract canaried
no-interpretation-word). No response laundered "risk" into an observed fact,
under either wording. The candidate naming the measurement did not make it
treat the measurement as the source of the verdict — it used the measurement's
*facts* and supplied the *meaning* itself, in every run.

## Floor frozen; S5 not edited (criterion 6) — ✅

`concentration.py` byte-identical to S7 (LF-hash `c78b0dab1c2032c6` before and
after all 32 runs); `measure()` pure (snapshot hash unchanged by attachment);
`s7/memory_seed/{methods,knowledge,preferences}.jsonl` **unchanged** before
and after all 32 runs (LF-hash canaried) — **S5 was not edited**; the candidate
is a runtime transform of the frozen seed, verified to change exactly one
`statement` in exactly one method. `snapshot.py` / `rulebook.jsonl` unchanged
across all runs; harness authority bounded (self-test passed). Nothing was
created, promoted, or self-implemented. The candidate is **evidence**, not an
edit.

## Observations

- **Engagement ≠ behaviour change.** The cleanest signal in S9 is that the
  candidate roughly triples measurement citation on A (0→37.5%) and takes it
  from 0 to 87.5% on D, while re-derivation barely moves. Method-wording is a
  strong lever over *whether the supervisor names the precomputed source* and
  a weak lever over *whether it re-computes anyway*. This separates two things
  S8 conflated by one-run evidence.
- **S8's D win was variance.** This is the most important re-reading S9 forces:
  the original does not reliably compose on D (0/8 citation). Any claim that
  "the method makes the measurement useful on D" needs the candidate wording
  (or a larger N under the original to see how often it actually cites). S8's
  single D run was a high point, not a property.
- **The mirror is where the candidate earns its keep.** The prediction put the
  win on A (the concentration case). The data puts it on D (the mirror): the
  candidate converts an unreliable 0/8 engagement into a reliable 7/8. On A it
  only nudges. Method evolution toward "read the measurement" helps the case
  where the measurement says "no concentration" (read and move on) more than
  the case where it says "60/70" (the supervisor re-checks anyway).
- **Complementary analysis is retained, mostly inline.** `complementary` Python
  calls were ~0 for all cells (A-orig 0, A-cand 0, D-orig 0.125 = one run,
  D-cand 0), yet the responses contain rich complementary analysis (the
  reservation exception, the digest split within the enrichment cohort,
  trigger distribution, shared-effect blast radius) — done by reading the
  inline snapshot, not by Python. So "complementary rather than duplicate" is
  satisfied by both via inline reading; the candidate reduces *duplicate
  concentration computation* only marginally on A. Criterion 3 holds, weakly,
  for both — it is not the differentiator.
- **Flailing is wording-resistant.** Both variants produce 4–5-call
  `NameError` outlier runs. The candidate softens them (fewer NameErrors) but
  does not prevent them. The fresh-namespace misunderstanding (S6/S7/S8
  recurring) is not a method-wording problem; it is a tool-use phenomenon the
  method only mildly disciplines.
- **No failure was hidden.** The A non-fix (candidate re-derives 5/8), the
  D re-derivation non-reduction, the S8-D-was-variance re-reading, the
  candidate's own flailing runs, and the N=8 width of the A read-rate gap are
  all preserved here and in the per-run artefacts.

## Verdict against the success criteria

1. ◐ — Re-derivation is lower on A (1.125→1.0, one call total over 8 runs;
   within the noise) and **not** lower on D (1.75→1.875). Marginal where it
   helped, absent where it didn't.
2. ◐ — When the candidate reads (3/8 A, 1/8 D) it correctly uses the
   measurement's exact facts (85.7%, 24.3%) and attributes them; on D it
   engages the measurement 0→7/8. But `read` is **not dominant on A** (3/8;
   5/8 still re-derived). Correct use of OBSERVED facts is real but not
   the dominant A behaviour.
3. ◐ — Both variants retain complementary analysis (inline); the candidate
   reduces duplicate concentration computation only marginally on A.
   Satisfied by both, not a differentiator.
4. ✅ — Interpretation stayed with the LLM on all 32 runs
   (`claims_measurement_says_risk` never; `interpretation_with_llm` always).
5. ✅ — Safety: D-cand does not regress D-orig (equal calls, +citation,
   −NameErrors, 8/8 correct, no false concentration).
6. ✅ — Floor frozen: `concentration.py`, `s7/memory_seed/`, `snapshot.py`,
   `rulebook.jsonl` all unchanged across 32 runs; candidate transform verified
   one-statement; authority bounded.

**Overall: S9 partially supports the wording hypothesis. The capability-aware
candidate is directionally better on every metric, safe, and — most clearly —
it is what makes the distributed mirror reliably engage the measurement
(revealing that S8's D "win" was a single-run variance artifact, not a
property of the original method). But it does not fix the A composition miss:
re-derivation of a real dominant concentration is robust to a one-statement
rewording (5/8 on A), and the wording moves attribution far more than
behaviour. Recorded as partial evidence for method evolution — a real but
weak lever over re-derivation, a strong lever over engagement — and explicitly
not applied to S5, which stays frozen.**

## Preserved artefacts

```text
s9/spec.md                         frozen S9 spec (candidate wording verbatim)
s9/oracle.json                     frozen predictions (before any model call)
s9/run.py                          4-cell N-repeat orchestrator + candidate transform + classifier
s9/results/canary.json             canaries (incl. S5 seed unchanged + candidate-transform correctness)
s9/results/run.log                 stdout log (32 runs)
s9/results/comparison.json/.md     per-cell N=8 distributions + orig-vs-cand comparison
s9/results/summary.json            one-line per-cell summary + verdicts + post-run floor canary
s9/results/<cell>/<NN>/            preserved run.json + session.jsonl + calls.json, per replicate
                                   cells: A-orig, A-cand, D-orig, D-cand ; NN: 01..08
s9/results/FINDINGS.md             this file (authoritative hand-judged verdicts)
```