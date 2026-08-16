# S9 — controlled method-wording experiment (original vs capability-aware variant)

> **Research question.** Is the S8 composition miss on fleet A a *measurement*
> problem or a *method-wording* problem? S8's `METHOD+MEASUREMENT`/A was the
> cleanest run on A (2 calls, 0 errors) but **re-derived** the concentration and
> **did not cite** the measurement. The flagged crux: the frozen S5 method
> statement 2 says *"Count how many workers depend on each shared component;
> when one component dominates, flag it as a blast-radius risk."* — an
> instruction to **count**, which the measurement precomputes. Where the
> concentration is real, the method's "count it yourself" wins over the
> measurement's "I already counted." S9 asks whether **re-wording that one
> procedural instruction to be capability-aware** — preserve the question, prefer
> the measurement, compute only what remains unresolved — lets the method
> compose with the measurement on A, **without touching the measurement, the S5
> memory, or anything frozen**.

S9 is a **controlled wording experiment**, not a new learning class and not an
edit to S5. It compares the **frozen original** concentration method against a
**candidate capability-aware variant** on the frozen S7 fleet A, under the
frozen S6 harness, the frozen S7 measurement, and the same model. If the
candidate composes where the original did not, that is **evidence for method
evolution** — recorded as such, not applied to S5.

## The candidate (a one-field transform of the frozen original)

The harness renders **only the `statement` field** of each memory record
(`core._memory_preamble` reads `entry.get("statement")` and nothing else). So
the candidate is built **in code** as a deterministic transform of the frozen
S5 seed: deep-copy the 3 methods, keep methods 1 and 3 and all knowledge and
preferences **byte-identical**, and replace **only** `methods[1]["statement"]`.

```text
frozen S5 method 2 (original):
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

The candidate preserves:
- the **supervisory question** — carried by the unchanged methods 1 & 3 ("ask
  what workers share and how concentrated that is"; "ask it on every fleet
  regardless of dependency type") and the unchanged knowledge/preferences;
- the **interpretive act** — "when one component dominates, flag it as a
  blast-radius risk" is kept verbatim (interpretation stays with the LLM);

and changes only the **procedural instruction**: "Count …" → "Read … from the
`dependency_concentration` measurement … use those facts directly and do not
re-derive them. Compute by hand only what no measurement resolves …".

This isolates exactly the crux: the *attention policy* (methods 1 & 3 +
knowledge + preferences) is identical across variants; only the *procedural*
instruction (method 2) differs. S5 is **not modified** — the candidate is a
runtime transform of a frozen seed, canaried against drift.

## What is frozen / not touched

```text
supervisor/concentration.py     frozen (LF-hash c78b0dab1c2032c6; canaried) — the measurement is unchanged
supervisor/snapshot.py           frozen (floor hash canaried before/after)
supervisor/rulebook.jsonl        frozen (floor hash canaried before/after)
s7/memory_seed/*.jsonl           frozen (LF-hash canaried before/after — S5 is NOT edited)
s7/build_fleet.py                reused (fleets A and D; hashes asserted vs oracle)
supervisor/harness.py            reused (the S6 harness, unchanged)
s1/prompt.txt                    reused (the broad S1 prompt, unchanged)
model / OPTIONS / MAX_TURNS      reused (glm-5.2:cloud; temp 0.2; num_ctx 131072; 10 turns)
```

Nothing is created, promoted, or self-implemented. The candidate is evidence,
not an edit.

## Conditions (both variants run WITH the measurement)

The whole point is whether the method *yields* to the measurement, so **both
variants get the measurement attached** (the S8 `METHOD+MEASUREMENT` envelope:
`{schema, contract, measurement}` under `snap["dependency_concentration"]`,
contract canaried no-interpretation-word). The only difference between variants
is the one swapped `statement`.

```text
A-orig    fleet A, original S5 method,            + measurement   [= S8 METHOD+MEASUREMENT/A, re-run for variance]
A-cand    fleet A, candidate capability-aware method, + measurement   [NEW — the wording treatment]
D-orig    fleet D, original S5 method,            + measurement   [= S8 METHOD+MEASUREMENT/D, safety mirror]
D-cand    fleet D, candidate capability-aware method, + measurement   [safety mirror — must not regress D]
```

Fleet A is the **primary comparison** (the S8 composition miss was on A). Fleet
D is a **safety mirror** only: the candidate must not break S8's D win (still
read the measurement, still find no false concentration, still few calls). D is
not where the hypothesis is won; it is where it must not be lost.

## Repeats (N=8 per cell, interleaved)

One run per cell was S8's limitation and is exactly what S9 removes. S8's
run-to-run variance was large (the cold A cell swung 1→9 calls across S7/S8;
the citation flag is binary per run). To distinguish a **wording effect** from
that variance, S9 runs **N=8 replicates per cell** (32 runs total).

To balance any time-drift / prompt-cache confound across cells, replicates are
**interleaved by round**: round 1 runs A-orig, A-cand, D-orig, D-cand; round 2
runs the same four; … through round 8. The orchestrator is **resumable** — it
skips any replicate whose `run.json` already exists and is complete, so an
interrupted batch picks up where it stopped, and a smoke run (N=1) becomes the
first replicate of the full batch (no wasted runs). Each run is independent
(`run` creates a fresh event log; `temperature=0.2` supplies the run-to-run
variance we are explicitly measuring).

The model is local Ollama (single server), so runs are **sequential**.

## What each call is CALCULATING (reused from S8, non-authoritative)

The S8 per-call purpose classifier is reused verbatim (a non-authoritative hint;
FINDINGS.md is authoritative, hand-judged from preserved call code and final
responses):

```text
concentration_rederivation   recomputes what the measurement already gives
                             (group/count/share workers by engine/trigger/effect/digest)
measurement_read             reads the precomputed measurement via python
                             (snapshot["dependency_concentration"] / contract / by_type)
complementary               computes something the measurement does NOT give
                             (task/customer/name breakdowns, reservation exception,
                             digest split within a cohort, run/version histories)
probe                       a failed/exploratory call (NameError, no useful output)
```

As in S8, `measurement_read` (python access) was 0 everywhere because the
supervisor reads the measurement inline in the rendered JSON. The engagement
signal is therefore `cites_measurement` (regex on the final response) **and**
the substantive outcome `concentration_rederivation` call count (does it
actually skip re-counting). The per-run **categorical outcome** is the headline:

```text
read        rederivation == 0 AND cites the measurement AND identifies the
            concentration correctly (used the OBSERVED facts, did not re-derive)
rederive+   rederivation > 0 (re-derived the concentration, with or without also
cite        citing the measurement afterwards)
rederive    rederivation > 0 and does not cite the measurement (= S8 A behaviour)
other       fails to identify, or errors out
```

## Judging success (the user's criteria)

1. **Reduction in concentration re-derivation.** A-cand has fewer
   `concentration_rederivation` calls per run than A-orig, across the N=8
   distribution (not just one run).
2. **Correct use of OBSERVED measurement facts.** A-cand's responses use the
   measurement's actual counts/shares (60/70, 0.857, the digest split) and
   attribute them to the measurement rather than to its own re-computation — the
   `read` categorical outcome, hand-judged from preserved responses. Not just
   name-dropping the block.
3. **Complementary rather than duplicate computation.** A-cand still does
   complementary work (the reservation exception, the digest split within the
   enrichment cohort, version history) — it stops *duplicating* the
   concentration computation, not all computation. Complementary calls present
   while re-derivation drops.
4. **Interpretation remains with the LLM.** `claims_measurement_says_risk` is
   False; `interpretation_with_llm` is True; the measurement/contract report
   facts only (canaried). The candidate says "flag it as a blast-radius risk" —
   flagging is the LLM's interpretive act, not the measurement's.

## Predictions (frozen in oracle.json before any model call)

```text
A-orig   rederivation ~2/run; cites_measurement usually False; identifies 60/70;
         interpretation LLM.  (echoes S8 METHOD+MEASUREMENT/A — the miss)
A-cand   rederivation drops toward 0-1/run; cites_measurement True in most runs;
         still identifies 60/70 (reads it from the measurement); complementary
         calls present (reservation exception, digest split); interpretation LLM;
         claims_measurement_says_risk False.  <-- the predicted wording win
D-orig   echoes S8 METHOD+MEASUREMENT/D — 1 call, cites_measurement True, no
         false concentration, finds reservation cohort.
D-cand   matches or improves on D-orig — still reads the measurement, no false
         concentration, few calls, still finds the reservation cohort.  (safety)
```

The hypothesis: **the S8 A miss is a method-wording problem, not a measurement
problem.** A capability-aware method that preserves the question but defers
factual computation to the measurement composes on A (where the frozen
"count it yourself" method did not), without regressing the D win and without
removing interpretation from the LLM.

## What S9 does NOT do

- No new learning class, no new measurement, no new seed files. The candidate is
  a runtime transform of the frozen S5 seed; `s7/memory_seed/` is not modified
  (canaried).
- `concentration.py` is NOT modified (LF-hash canaried). The contract envelope
  is the S8 one, reused.
- No rule creation/promotion; no `snapshot.py` edit; no autonomous machinery.
- The candidate is **evidence for method evolution, not an edit to S5**. If it
  works, FINDINGS records it as a candidate for a future learning step; S5 stays
  frozen.
- One model, one run config; N=8 replicates per cell for variance.
- The classifier is a non-authoritative hint; FINDINGS.md is authoritative.
- No failures are hidden. If A-cand still re-derives, or regresses D, or the
  NameError flailing moves, it is recorded.

## Artefacts

```text
s9/spec.md               this file (frozen)
s9/oracle.json           frozen predictions, stamped before any model call
s9/run.py                4-cell N-repeat orchestrator + candidate transform + classifier
s9/results/canary.json   canaries (incl. S5 seed unchanged + candidate transform correctness)
s9/results/run.log       stdout log
s9/results/<cell>/<NN>/  preserved run.json + session.jsonl + calls.json, per replicate
                         cells: A-orig, A-cand, D-orig, D-cand ; NN: 01..08
s9/results/comparison.json/.md   per-cell distributions + orig-vs-cand comparison
s9/results/summary.json  one-line per-cell summary + verdicts
s9/results/FINDINGS.md   authoritative hand-judged verdicts
```