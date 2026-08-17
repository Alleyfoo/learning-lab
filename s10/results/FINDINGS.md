# S10 — findings: measurement authority (established / candidate / invalid)

> **Research question.** S9 showed that capability-aware method wording moves
> *attribution* (citation of the measurement) far more than *behaviour*
> (re-derivation): the candidate still re-derived in 5/8 runs on A despite being
> explicitly told *"read the measurement, do not re-derive them."* S9's own
> recommended next step #3 named the likely cause: the fix is **structural (a
> harness/contract lever), not a wording one** — the measurement should declare
> its *authority state*. S10 makes that state explicit and asks whether the
> supervisor's behaviour tracks it. The **only** variable across cells is an
> `authority` block on the measurement envelope (`status` × `integrity`,
> `integrity` computed mechanically via `source_snapshot_hash`). The fleet, the
> frozen `concentration.measure`, the S9 capability-aware method (held constant),
> the harness, the prompt, and the model are all unchanged. **N=8 per cell,
> 32 runs**, interleaved — the variance discipline S9 established.

S10 is a **measurement-authority experiment**, not a learning class and not an
edit to S5. The method is the S9 capability-aware candidate in every cell (a
runtime one-field transform of the frozen S5 seed; `s7/memory_seed` is not
modified, canaried). The authority block carries **OBSERVED facts** (the two
hashes) and **AUTHORIZATION state** (`status` / `integrity`) — never a verdict
about the data (canaried: no interpretation word anywhere in the block or its
notes; `status: established` is never made to mean `true`).

## The authority block (the only thing that varies)

```text
A-established   fleet A, authority{established, valid}     -> consume        (predicted)
A-candidate     fleet A, authority{candidate,  unverified} -> verify is reasonable
A-invalid       fleet A, authority{established, invalid}   -> reject / recompute
D-established   fleet D, authority{established, valid}     -> mirror: established != risk
```

`integrity` is **detected mechanically**, not labelled by hand: for
`status=established`, `integrity = valid` iff the recorded `source_snapshot_hash`
equals `snapshot.hash_snapshot` of the bare fleet, else `invalid` with
`reason=source_snapshot_mismatch`; for `status=candidate`, `integrity=unverified`.
For A-invalid the recorded hash is `0000000000000000` (all zeros) against the real
`6cb2c1ffaa1d4d77`, so the mismatch is genuine and inspectable — exactly as a
platform that "detects it mechanically and exposes it" would. Canaried before any
model call: established→valid, candidate→unverified, invalid→invalid+reason, all
three detected from the hashes.

## Headline

**The hypothesis is partially supported — with a sharp asymmetry that refines
the "missing concept." Authority awareness is real and robustly detectable, but
only as a NEGATIVE / stop signal. The POSITIVE / consume signal does not work.**

- **The integrity axis is the strong discriminant (criterion 3 — ✅).** Same
  `status: established`, same fleet, same method, same model — only `integrity`
  differs (valid vs invalid). Behaviour changes dramatically: A-established
  re-derives 1.5/run and flags invalid 0/8; **A-invalid re-derives 2.875/run,
  flags invalid 8/8, reads the authority block via Python 1.375/run, and is
  `reject` 8/8.** Every A-invalid run names `integrity: invalid`,
  `source_snapshot_mismatch`, "the recorded `source_snapshot_hash` is all zeros
  and does not match," and refuses to rely on the measurement — even the two
  1-call runs. This is authority-awareness, and it is the behaviour S9's wording
  could not produce.
- **The consume prediction failed (criterion 1 — ❌).** A-established is
  **8/8 `rederive+cite`, 0/8 `read`**. The supervisor *cites* the established
  measurement every time ("The `dependency_concentration` measurement shows 60 of
  70 workers (85.7%)") but **re-derives it every time anyway.** Establishing the
  measurement does not stop re-derivation of a real 60/70 concentration. The S9
  leftover is robust even to an explicit `established+valid` authority block.
- **The status axis shows no behavioural difference (criterion 2 — ◐).**
  A-established vs A-candidate (same numbers, only `status` differs, both
  provenance-fine): re-derivation 1.5 vs 1.375, citation 1.0 vs 1.0. The
  supervisor does **not** distinguish "established" from "candidate" when the
  numbers are right and the provenance is fine. "Status: established" as a label
  does not change behaviour.

So the S9 leftover is **partly** a measurement-authority problem. Authority
solves the **invalid** case (reject, 8/8) but **not** the **consume** case
(established does not stop re-derivation). The missing concept is real but
**asymmetric**: it is *integrity / provenance authority* — a mechanically
checkable **stop signal** ("this measurement's provenance is broken right now") —
not *status authority* — a **consume permission** ("you may skip verifying this").

```text
criterion 1  established+valid is consumed (rederive < cand/invalid; read dominant)  ❌  A-established 8/8 rederive+cite, 0/8 read; rederive 1.5 ≈ A-candidate 1.375
criterion 2  candidate reasonably verified (rederive not penalised)                  ✅  8/8 verify, correct — but no contrast with established
criterion 3  invalid rejected / recomputed (reject dominant; trust_invalid low)      ✅  8/8 reject; flags_invalid 8/8; trust_invalid 0/8; rederive up (1.5→2.875) -- the discriminant
criterion 4  established != true (mirror: no false concentration, no meas-says-risk) ✅  D-established correct 8/8, no false concentration, no flags_invalid (one claims_risk regex hit is a hand-judged false positive)
criterion 5  interpretation stays with the LLM                                       ✅  hand-judged 32/32; authority block + notes canaried no-interpretation-word
criterion 6  floor frozen; authority bounded                                          ✅  concentration.py / S5 seed / snapshot.py / rulebook.jsonl unchanged; method = S9 one-field transform
```

Two strong (3, 6), three hold (2, 4, 5), one fails (1). The headline is the
**integrity-axis contrast**: same established status, only integrity differs →
consume vs reject. That is the stronger discriminant the user asked for —
"another sentence of prompt text" (S9) could not produce it; an explicit,
mechanically-detected authority state did.

## The runs (4 cells × N=8 = 32 runs)

The method is identical in every cell; only the `authority` block differs.
Per-run categorical outcome **differs by authority state** — a re-derivation
that is a *failure* on `established` is *correct* on `invalid`:

```text
established -> read (consume) / rederive+cite / rederive
candidate   -> verify (rederive, correct -- not penalised) / read
invalid     -> reject (rederives AND flags integrity=invalid; does not present 60/70 as authoritative) / trust_invalid
```

### Fleet A — primary (engine 60/70 concentration), n=8 each

| metric | A-established | A-candidate | A-invalid |
|---|---|---|---|
| calls/run (mean) | 1.5 | 1.375 | 2.875 |
| calls values | [1,1,2,1,1,3,1,2] | [1,2,1,2,1,2,1,1] | [1,1,6,3,1,3,3,5] |
| re-derivation (mean) | 1.5 | 1.375 | 2.875 |
| measurement_read (python, mean) | 1.375 | 0.875 | 1.5 |
| authority_read (python, mean) | 0.0 | 0.0 | 1.375 |
| NameErrors (sum) | 1 | 1 | 6 |
| categorical | rederive+cite 8 | verify 8 | reject 8 |
| cites_meas rate | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) |
| flags_invalid rate | 0/8 | 0/8 | 8/8 (100%) |
| treats_authoritative rate | 0/8 | 4/8 (50%) | 5/8 (62.5%) |
| correct (identifies 60/70) | 8/8 | 8/8 | 8/8 |
| claims_measurement_says_risk | no | no | no |
| interpretation_with_llm | all | all | all |

**A-established (consume prediction — FAILED).** 8/8 `rederive+cite`, 0/8 `read`.
The supervisor cites the established measurement in every run — *"The
`dependency_concentration` measurement shows that 60 of 70 workers (85.7%) all
run through the same engine"* — and then re-derives it (1–3 calls). It treats
`established+valid` as *correct and citable* but **not as a reason to skip
verification**. Establishing the measurement moved attribution (citation 100%,
vs S9 A-cand 37.5%) but did **not** move re-derivation (1.5/run, vs S9 A-cand
1.0). The S9 leftover — re-deriving a real dominant concentration — is robust
even to an explicit authority block saying this is the platform's settled
mechanical answer.

**A-candidate (verify — HOLDS, but no contrast).** 8/8 `verify`, correct 8/8.
Re-deriving is the reasonable act for an unverified candidate, and the supervisor
does it cleanly (1–2 calls, 1 NameError total). But behaviourally A-candidate is
**nearly identical to A-established** (rederive 1.375 vs 1.5; cites 1.0 vs 1.0):
the `status` label (established vs candidate) does not change behaviour when the
provenance is fine in both. The predicted consume-vs-verify contrast on the
status axis did not appear.

**A-invalid (reject — the discriminant, STRONG).** 8/8 `reject`, flags_invalid
8/8, `trust_invalid` 0/8. Every run reads the authority block (authority_read
1.375/run vs 0.0 in the other A cells), names the invalid state, and refuses to
rely on the measurement. Two anchors, hand-judged from the preserved responses:

- **A-invalid rep01 (1 call, `reject`):** a dedicated section *"Integrity note on
  the `dependency_concentration` measurement"* — *"The measurement's `integrity`
  field is `invalid` with reason `source_snapshot_mismatch` — the recorded
  `source_snapshot_hash` (all zeros) does not match the snapshot it's attached
  to… the measurement's provenance metadata is inconsistent."* It recomputed the
  counts once to verify, flagged the mismatch, and did not present 60/70 as the
  platform's settled answer.
- **A-invalid rep05 (1 call, `reject`):** *"reports `integrity: invalid` with
  reason `source_snapshot_mismatch` — the recorded `source_snapshot_hash` is all
  zeros and does not match the attached snapshot hash… a provenance
  inconsistency. This is worth raising with whoever [owns the measurement]."*

Same `status: established` as A-established — only `integrity` differs. The
supervisor consumes one and rejects the other. That is the measurement-authority
discriminant, and it required the structural lever S9's wording could not supply.

### Fleet D — safety mirror (distributed, no majority), n=8

| metric | D-established |
|---|---|
| calls/run (mean) | 1.375 |
| calls values | [1,4,1,1,1,1,1,1] |
| re-derivation (mean) | 1.375 |
| NameErrors (sum) | 2 (one 4-call flailer, rep02) |
| categorical | rederive+cite 4, rederive 4 |
| cites_meas rate | 4/8 (50%) |
| flags_invalid rate | 0/8 |
| correct (no false concentration) | 8/8 |
| claims_measurement_says_risk | regex True on 1 run (hand-judged false positive) |
| interpretation_with_llm | all |

**D-established (mirror — established ≠ risk, HOLDS).** No run invented a false
majority concentration (`correct 8/8`); no run flagged the measurement invalid
(`flags_invalid 0/8`). The supervisor re-derives the distribution, finds no
60/70-style concentration, and surfaces the **real** reservation cohort (17/70
across engine + effect + digest) — the same real finding S7/S8/S9 surfaced. The
one `claims_measurement_says_risk` regex hit (rep08) is a **hand-judged false
positive**: the response says *"Per the `dependency_concentration` measurement,
the reservation cohort represents a concentrated structural risk"* — the LLM is
interpreting a real 17/70 cohort as a risk, citing the measurement as the source
of the *facts*; it is not saying the measurement declares risk. Interpretation
stayed with the LLM. `established` did not manufacture a risk where the facts say
there is none — the central mirror claim holds.

D-established is, like A-established, **not** pure-`read` (0/8 read; 4
rederive+cite, 4 rederive). The established authority did not push the mirror to
"read and move on" either — the same asymmetry as A: established is heard as
*citable*, not as *skip-verification*. This is consistent across both fleets.

## Why the consume prediction failed — and why that is honest

The user's framing predicted `ESTABLISHED+VALID → consume`. The data says
established+valid is **cited and re-derived**, not consumed. Two readings are
honest, and the second is the interesting one:

1. **Authority as a consume-permission is a weak lever** — weaker than the
   invalid stop-signal. The supervisor does not treat "you may rely on this" as
   "you must not verify this."
2. **The supervisor is enforcing `established ≠ true` itself.** The authority
   block's own `status_note` says *"an established implementation can contain a
   bug, which is what audit is for."* The supervisor behaves accordingly: it
   re-derives because an established measurement *can* be buggy, and re-deriving
   from the same snapshot is the cheap check that would catch a `concentration.py`
   bug. That is the user's "AUDIT / VALIDATION" job happening on every ordinary
   review — exactly the conflation the user wanted to separate — but it is not
   irrational: the supervisor agrees established is not true.

So S10 sharpens the user's distinction. The two jobs that must not collapse —

```text
SUPERVISION        use established deterministic measurements
AUDIT / VALIDATION independently recompute a measurement to test its implementation
```

— the supervisor defaults to AUDIT on every review, and only a **positive signal
that the measurement is broken** (integrity=invalid) overrides it toward "do not
trust." The signal that did **not** override it is "this is established and
valid" — because that is a *permission to rely on*, not a *prohibition on
verifying*, and the supervisor's verify-instinct for a real 60/70 concentration
(S9) is robust to permissions. **Making "established+valid" mean "consume, do not
re-derive" would require an explicit mode/permission — "re-derivation is
disallowed for ordinary supervision; audit is a separate mode" — which is the
next structural lever**, the one the user's architecture sketch points at
(MEASUREMENT REGISTRY → ESTABLISHED MEASUREMENT → consume; AUDIT → occasionally
challenge). S10 tested making the state *visible*; the state is heard when it is
a stop-signal, not when it is a consume-permission.

## Interpretation stayed with the LLM (criterion 5) — ✅ (32/32, hand-judged)

`interpretation_with_llm=True` on all 32 runs. `claims_measurement_says_risk` is
hand-judged **False on all 32**: the only regex hit (D-established rep08) is a
false positive — the LLM interpreting the real reservation cohort, not the
measurement declaring risk. No response laundered "risk" into an observed fact.
The authority block and both notes contain **no interpretation word** (canaried
per cell, and on all three authority states); `status: established` was not
smuggled into meaning `true` — the supervisor's own re-derivation is the proof,
and the D mirror did not manufacture a risk. The block carries OBSERVED facts
(the hashes) and AUTHORIZATION state (status/integrity); the LLM supplies the
meaning in every run.

## Floor frozen; S5 not edited; authority bounded (criterion 6) — ✅

`concentration.py` byte-identical to S7 (LF-hash `c78b0dab1c2032c6` before and
after all 32 runs); `measure()` pure (snapshot hash unchanged by attachment);
`s7/memory_seed/{methods,knowledge,preferences}.jsonl` **unchanged** before and
after all 32 runs (LF-hash canaried) — **S5 was not edited**; the method is the
S9 candidate, a runtime one-field transform verified to change exactly one
`statement` in exactly one method, identical across all four cells.
`snapshot.py` / `rulebook.jsonl` unchanged across all runs; harness authority
bounded (self-test passed). The authority block is **evidence about a contract
lever**, not an edit to the floor. Mechanical integrity canaried before any model
call: established→valid, candidate→unverified, invalid→invalid+reason, all
detected from the hashes.

## Variance

A-invalid carries the most computation and the most flailing: two runs are
outliers — **rep03 (6 calls, 5 NameErrors)** and **rep08 (5 calls, 1
NameError)**; the other six are clean 1–3-call rejects. The flailing is the
S6/S7/S8/S9 recurring fresh-namespace `NameError` phenomenon (more recompute =
more chances to misunderstand the stated contract), not an authority phenomenon —
both flailing runs still ended `reject`. D-established has one flailer (rep02, 4
calls / 2 NameErrors); A-established one (rep06, 3 calls / 1 NameError);
A-candidate one (rep02, 2 calls / 1 NameError). NameError totals: A-invalid 6,
D-established 2, A-established 1, A-candidate 1. The invalid cell's higher
recompute load is the *desired* behaviour (recompute because the measurement is
broken); its higher flailing is a tool-use side-effect, preserved honestly.

## Observations

- **Authority is a stop-signal, not a consume-permission.** The cleanest signal
  in S10 is the asymmetry: `integrity=invalid` changes behaviour 8/8 (reject,
  recompute, flag the mismatch); `status=established` changes behaviour 0/8
  (still re-derives). The supervisor hears "this specific measurement is broken
  right now" and acts; it does not hear "you may skip verifying this one." This
  refines S9's "capability awareness is not authority awareness" — authority
  awareness is real but **directional**: strong as a negative signal, weak as a
  positive one.
- **The integrity axis, not the status axis, is where authority lives.** The
  predicted consume-vs-verify contrast on `status` (established vs candidate) did
  not appear — the two cells are behaviourally identical. The contrast that did
  appear is on `integrity` (valid vs invalid), holding `status` fixed. The
  operationally meaningful authority question is *"is this measurement's
  provenance valid for this snapshot?"* — a mechanically checkable fact — not
  *"is this measurement established?"* — a label.
- **The supervisor enforces `established ≠ true` itself.** A-established re-derives
  because an established implementation can contain a bug. That is the epistemic
  rule the user wanted preserved, and the supervisor is honouring it — at the
  cost of behaving like a test suite on every invocation. The user's
  SUPERVISION-vs-AUDIT separation is the thing still missing: ordinary
  supervision should not audit on every review, but the supervisor currently
  does, because nothing tells it that re-deriving an established+valid
  measurement is *disallowed* (only that trusting an invalid one is).
- **Attribution vs behaviour, again.** As in S9, the authority block moved
  *attribution* (citation: A-established 100% vs S9 A-cand 37.5%) more than
  *behaviour* (re-derivation: A-established 1.5 vs S9 A-cand 1.0). The structural
  lever strengthened attribution substantially and **did** unlock one new
  behaviour the wording lever could not (reject on invalid). It did not unlock
  the other (consume on established). Two levers, two directions, one worked.
- **No failure was hidden.** The consume failure (A-established 0/8 read), the
  status-axis non-contrast (established ≈ candidate), the A-invalid flailing
  (2/8 outlier runs), the D-established claims_risk regex false positive
  (hand-judged clean), and the "established is cited not consumed" finding on the
  mirror are all preserved here and in the per-run artefacts.

## Verdict against the success criteria

1. ❌ — Established+valid is **not** consumed: A-established is 8/8
   `rederive+cite`, 0/8 `read`; re-derivation 1.5/run is **not** below A-candidate
   (1.375). The consume prediction failed. Establishing the measurement moved
   attribution, not re-derivation.
2. ✅ — Candidate is reasonably verified: A-candidate 8/8 `verify`, correct 8/8,
   re-derivation not penalised. (But behaviourally indistinguishable from
   established — so this holds without producing the predicted status-axis
   contrast.)
3. ✅ — **Invalid is rejected / recomputed: A-invalid 8/8 `reject`,
   `flags_invalid` 8/8, `trust_invalid` 0/8, re-derivation up (1.5→2.875),
   authority_read 0→1.375. The strongest discriminant — the behaviour S9's wording
   could not produce, produced by an explicit mechanically-detected authority
   state.**
4. ✅ — Established ≠ true (mirror): D-established no false concentration (8/8
   correct), no `flags_invalid`; the one `claims_measurement_says_risk` regex hit
   is a hand-judged false positive (LLM interpreting the real 17/70 cohort).
5. ✅ — Interpretation stayed with the LLM on all 32 runs (hand-judged
   `claims_measurement_says_risk` never true; `interpretation_with_llm` always
   true; authority block + notes canaried no-interpretation-word).
6. ✅ — Floor frozen: `concentration.py`, `s7/memory_seed/`, `snapshot.py`,
   `rulebook.jsonl` all unchanged across 32 runs; method = S9 one-field transform
   (canaried); mechanical integrity canaried; authority bounded.

**Overall: S10 partially supports the measurement-authority hypothesis, with a
sharp asymmetry. Authority awareness is real and robustly detectable — the
`integrity=invalid` state produces `reject` 8/8, the behaviour S9's wording could
not produce, holding fleet/measurement/method/model constant. But authority is a
stop-signal, not a consume-permission: `established+valid` is cited 100% yet
re-derived 8/8, and `established` vs `candidate` (both provenance-fine) show no
behavioural difference. The missing concept is *integrity/provenance authority*
(a mechanically checkable "this measurement is broken right now") rather than
*status authority* (a "you may rely on this" label). The supervisor enforces
`established ≠ true` itself — re-deriving because an established implementation
can contain a bug — which is the epistemic rule the user wanted preserved, and is
also why ordinary supervision still behaves like an audit on every review.
Separating SUPERVISION from AUDIT (an explicit "re-derivation is disallowed for
ordinary supervision; audit is a separate mode") is the next structural lever —
the one the user's MEASUREMENT-REGISTRY → ESTABLISHED-MEASUREMENT → consume
architecture sketch points at. S10 is evidence about that lever, not an edit to
the floor.**

## Preserved artefacts

```text
s10/spec.md                         frozen S10 spec (authority block verbatim)
s10/oracle.json                     frozen predictions + authority block definitions (before any model call)
s10/run.py                          4-cell N-repeat orchestrator + authority block + mechanical integrity + classifier
s10/results/canary.json             canaries (authority-block no-interpretation-word; mechanical integrity; floor + S5 seed frozen)
s10/results/run.log                 stdout log (32 runs)
s10/results/comparison.json/.md     per-cell N=8 distributions + across-authority contrasts (status axis, integrity axis, mirror)
s10/results/summary.json            per-cell summary + verdicts + post-run floor canary
s10/results/<cell>/<NN>/            preserved run.json + session.jsonl + calls.json, per replicate
                                    cells: A-established, A-candidate, A-invalid, D-established ; NN: 01..08
s10/results/FINDINGS.md             this file (authoritative hand-judged verdicts)
```