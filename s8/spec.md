# S8 — composition: METHOD (attention policy) × MEASUREMENT (cheap fact)

> **Research question.** Does the learned supervisory **method** and the promoted
> deterministic **measurement** *compose*? That is: does the method remain useful as
> the question/attention policy ("ask what the fleet shares, and how concentrated
> that is") while the promoted measurement replaces the repeated factual
> computation (group / count / share) the method used to make the supervisor do by
> hand — with interpretation still owned by the LLM?

S7 froze the loop end-to-end (method → repeated utility → proposal → conflict
check → human approval → OBSERVED-only measurement → cheaper cold supervision).
S7's honest negative was criterion 5 on the **distributed mirror**: a *cold*
supervisor with the measurement re-derived the distribution by hand (9 calls, 4
`NameError`s) rather than read the measurement, because nothing told it the
measurement was the answer to the question it should be asking. S8 tests the
hypothesis that the **method supplies the missing piece**: it is the attention
policy that says "ask the concentration question", and once the measurement
answers it, the supervisor moves on instead of re-deriving.

S8 is a **composition** experiment, not another learning class. No new memory
class, no new seed, no new measurement. It reuses frozen S7 fleets A and D and
the frozen S5 method, and compares three conditions under the frozen S6 harness.

## The clean separation of concerns this would complete

```text
the LLM        learns what questions are worth asking        (METHOD)
the platform   learns to answer repeated factual questions cheaply (MEASUREMENT)
the LLM        remains responsible for what the answers mean  (INTERPRETATION)
```

S8 asks whether those three compose in one session.

## Conditions (one run each; 2 fleets × 3 conditions = 6 runs)

All under the S6 `SupervisorHarness`, same broad S1 prompt (unchanged, no
expected-answer hints), same model (`glm-5.2:cloud`), same `OPTIONS`, same
`MAX_TURNS`. The only variables are **what is provided** to the supervisor.

```text
METHOD-only            full S5 memory (methods + knowledge + preferences),
                       NO measurement attached.            [= S7 Phase A config]
MEASUREMENT-only       COLD (no memory), measurement attached WITH contract.  [= S7 Phase D config]
METHOD+MEASUREMENT     full S5 memory AND measurement attached WITH contract. [NEW combination]
```

`METHOD-only` and `MEASUREMENT-only` reuse S7's exact configs (full memory vs
cold) so S8 also yields a cross-experiment variance signal on those two cells;
`METHOD+MEASUREMENT` is the new combination that isolates composition.

## Fleets (reused, frozen)

```text
A   engine concentration   60/70 on execute_enrichment.py   (the case the measurement was built for)
D   distributed mirror     no majority concentration;        (S7's criterion-5 negative)
                          engines 18/18/17/17, real reservation cohort 17/70, 1 open investigation
```

Fleets are loaded via `s7.build_fleet.build_all()` (a pure function; the frozen
`s7/oracle.json` is NOT rewritten by importing it). Snapshot hashes are asserted
against the S7 oracle before any model call, so a regenerated fleet that drifted
would fail loudly.

## The measurement's explicit mechanical contract / provenance

S7 attached `concentration.measure(snap)` directly as `snap["dependency_concentration"]`.
S8 attaches an **envelope** that carries a minimal mechanical contract + provenance
around the **unchanged** `measure()` output:

```json
"dependency_concentration": {
  "schema": "supervisor.dependency_concentration/v1",
  "contract": {
    "nature": "mechanically computed from snapshot records; no interpretation; no thresholds",
    "computes": "for each dependency type {engine, trigger, effect, digest}: workers per identity, and each identity's share of the whole fleet",
    "source_fields": "worker.engine, worker.trigger, worker.effect, current-version digest from version_history",
    "share": "worker_count / total worker_count of the whole fleet",
    "ordering": "sorted by worker_count descending (an ordering of facts, not a judgement)",
    "is_not": "does not label or threshold any distribution; whether it matters is for the supervisor to decide",
    "provenance": "computed by supervisor.concentration.measure (a pure function; the snapshot is not mutated)"
  },
  "measurement": { ...the frozen measure(snap) output, byte-identical to S7... }
}
```

The contract is an **S8 layer**; `supervisor/concentration.py` is NOT modified
(canaried by file hash vs the S7 `a56e180` state, and by a frozen reference
output). The contract describes the frozen computation's mechanics; it carries
no interpretation and no thresholds (canaried with `concentration._contains_interpretation`).
The supervisor sees the contract inline in the rendered snapshot JSON — it does
not need Python to read it.

## The new instrument: what each call is CALCULATING, not just how many

S7 measured Python-call *count*. S8 adds a per-call **purpose classifier** over
the preserved call code (non-authoritative hint; FINDINGS.md is authoritative,
hand-judged from the preserved code and final responses):

```text
concentration_rederivation   recomputes what the measurement already gives:
                             grouping/counting/sharing workers by engine/trigger/
                             effect/digest. This is the "repeated factual
                             computation" the measurement is meant to replace.
measurement_read             reads the precomputed measurement (snapshot
                             ["dependency_concentration"] / its contract / by_type)
                             instead of re-counting workers. The "cheap" path.
complementary               computes something the measurement does NOT give:
                             task/customer/name breakdowns, the reservation cohort,
                             the open investigation, run/version/confirmation
                             histories.
probe                       a failed or exploratory call (NameError, recompute,
                             no useful output) -- overhead, not signal.
```

Each call gets a primary purpose tag + the evidence that triggered it. The
**call mix** per condition is the headline, not the count alone.

## Hypothesis and predictions (frozen in oracle.json before any model call)

> The learned method remains useful as the **question/attention policy** while
> the promoted deterministic machinery **replaces the repeated factual
> computation**; interpretation stays with the LLM. On the distributed mirror,
> METHOD+MEASUREMENT inspects the mechanical distribution and **moves on**
> rather than re-derive it.

```text
fleet A (engine 60/70 concentration):
  METHOD-only            asks the question; RE-DERIVES engine 60/70 by hand.
                         call mix: concentration_rederivation present.
                         identifies concentration; interprets (blast-radius) with LLM.
  MEASUREMENT-only       measurement present, cold. identifies engine concentration.
                         may read the measurement or do a small re-derivation.
                         call mix: measurement_read OR some concentration_rederivation.
  METHOD+MEASUREMENT     method asks; measurement answers. NO re-derivation needed.
                         call mix: concentration_rederivation ~0; measurement_read +
                         complementary. identifies engine 60/70 citing the
                         measurement; interprets with the LLM.
                         <-- the composition win on A

fleet D (distributed mirror):
  METHOD-only            asks the question; looks; re-derives to confirm NO
                         majority concentration; finds the real reservation cohort
                         17/70 + the open investigation. call mix:
                         concentration_rederivation + complementary. does NOT
                         invent a concentration.
  MEASUREMENT-only       cold + measurement. S7 re-derived by hand (9 calls, 4
                         NameErrors), did not cite the measurement. Prediction:
                         similar -- may or may not lean on the measurement.
  METHOD+MEASUREMENT     method asks; measurement says "distributed, no majority";
                         supervisor READS the mechanical distribution and MOVES ON
                         to complementary work (reservation cohort, investigation)
                         WITHOUT re-deriving. call mix: concentration_rederivation
                         ~0; measurement_read + complementary; FEW total calls.
                         <-- the composition win on D, and the direct fix of S7's
                             criterion-5 mirror negative
```

The **sharpest contrast** is on D: `MEASUREMENT-only` (re-derives, many calls)
vs `METHOD+MEASUREMENT` (reads, moves on, few calls). The method's role is not
just "what to ask" but "when the measurement has answered, stop and move on."

## The crux / the honest risk

The frozen S5 **method statement 2** literally says: *"Count how many workers
depend on each shared component; when one component dominates, flag it as a
blast-radius risk."* That is an instruction to **count** — exactly what the
measurement precomputes. So METHOD+MEASUREMENT has a genuine, testable tension:
does the supervisor obey the method's "count" instruction and re-derive anyway,
or recognise that the measurement has already counted and **read** it?

- If it reads the measurement and moves on: composition works; the method
  functions as attention policy, the measurement as cheap factual answer.
- If it re-derives despite the measurement being present: the method's wording
  and the promoted machinery do not cleanly compose, and the honest finding is
  that a method phrased as "count it yourself" does not automatically yield to a
  precomputed answer. **The method is frozen (S5, reused as-is); any such
  failure is preserved, not patched.**

S8 does not change the method to say "read the measurement." It tests whether the
method as frozen composes with the measurement as built.

## Success criteria

1. **Composition on A:** METHOD+MEASUREMENT identifies the engine concentration
   with `concentration_rederivation` calls ≈ 0 (reads the measurement), and
   spends its calls on complementary + interpretation.
2. **Composition on D (the mirror):** METHOD+MEASUREMENT reads the mechanical
   distribution, finds no majority concentration, and moves on with fewer total
   calls and ≈ 0 `concentration_rederivation` calls than MEASUREMENT-only — the
   direct fix of S7's criterion-5 mirror negative.
3. **Method stays useful as attention policy:** in METHOD+MEASUREMENT the
   supervisor still asks the concentration question (the method's effect),
   rather than ignoring concentration because the measurement is present.
4. **Measurement replaces repeated factual computation:** `concentration_
   rederivation` calls are lower in MEASUREMENT-bearing conditions than in
   METHOD-only, especially on D.
5. **Interpretation stays with the LLM:** the measurement (and its contract)
   report facts only; the supervisor's responses carry the interpretation
   (blast-radius, "would affect most of the fleet"). No response claims the
   *measurement* said risk/safe.
6. **Floor frozen:** `concentration.py` unchanged; `snapshot.py` /
   `rulebook.jsonl` unchanged across all runs; harness authority bounded.

## What S8 does NOT do

- No new learning class, no new memory seed, no new method, no new measurement.
- `concentration.py` is NOT modified (the computation is frozen; the contract is
  an S8 attachment layer).
- No rule creation/promotion; no snapshot.py edit; no autonomous machinery.
- One run per condition per fleet (variance is a separate future task).
- The classifier is a non-authoritative hint; FINDINGS.md is authoritative.
- No failures are hidden. If METHOD+MEASUREMENT does not compose as predicted
  (e.g., re-derives anyway per the method's "count" wording, or NameErrors
  recur), it is recorded.

## Artefacts

```text
s8/spec.md               this file (frozen)
s8/oracle.json           frozen predictions, stamped before any model call
s8/run.py                3-condition orchestrator + call-purpose classifier
s8/results/<cond>/<A|D>/  preserved run.json + session.jsonl + calls.json (per-call purpose)
s8/results/comparison.json/.md   the 3x2 call-mix comparison
s8/results/summary.json  one-line per-cell summary
s8/results/FINDINGS.md   authoritative hand-judged verdicts
```