# S11 — OPERATING MODE: SUPERVISION vs AUDIT

> **Research question.** S10 found measurement authority is **real but
> asymmetric**: an explicit, mechanically-detected `integrity=invalid` state
> produces `reject` 8/8 (a stop-signal the supervisor honors), but
> `established+valid` is *cited 100% yet re-derived 8/8* — establishing a
> measurement does not stop re-derivation of a real 60/70 concentration. The
> supervisor enforces `established != true` *itself*: it re-derives because an
> established implementation can contain a bug, and re-deriving from the same
> snapshot is the cheap check that would catch one. That is the right epistemic
> instinct — and it is also why ordinary supervision still behaves like an audit
> on every review. The thing still missing is the **operating-mode separation**
> S10's handoff pointed at: ordinary SUPERVISION should *consume* an established
> measurement and not re-derive it; AUDIT should *independently recompute* it to
> test the implementation. S11 makes that an explicit, harness-enforced mode.

S11 is an **operating-mode experiment**. It holds frozen everything S10 held
frozen — fleet A, the `concentration` measurement, the `established+valid`
authority envelope, the S9 capability-aware method, the S6 harness, the broad
S1 prompt, the model/settings — and **changes only the operating mode**. The
mode is not a wording change: it is enforced through the **tool policy**, not
only prose. In SUPERVISION mode a `python_analysis` call that merely recomputes
`dependency_concentration` from worker records is **refused** with a transparent
`DUPLICATE_ESTABLISHED_MEASUREMENT` message; in AUDIT mode the same call is
permitted and expected. The refusal makes two things **separable** that S9/S10
could not separate:

```text
attempted re-derivation  =  model habit        (the model still tries to count)
executed re-derivation   =  policy failure     (the count actually ran)
```

S11 asks: does enforcing the mode through the tool policy convert the
supervisor's re-derivation *habit* (S9/S10: re-derives 8/8) into a *refused
attempt* followed by consume — while the same measurement, in AUDIT mode, is
independently recomputed and compared?

## The two modes (frozen verbatim; canaried to contain NO interpretation word)

```text
SUPERVISION
  This is an ordinary supervisory review. Established, integrity-valid
  deterministic measurements are the operational factual source for questions
  they cover. Do not independently re-derive those same facts during this
  review. Use tools only for questions the established measurements do not
  answer. If an established measurement is missing, stale, invalid or
  insufficient, investigate instead.

AUDIT
  This is a measurement audit. Independently recompute the
  dependency-concentration result from underlying records and compare it with
  the established measurement. Re-derivation is explicitly permitted and
  expected.
```

The mode is **authorization, not a verdict about the data**. The canary asserts
the mode prose (and the refusal message) contain no interpretation word —
`SUPERVISION` does not smuggle "safe"/"consume-trust-this" any more than S10's
`established` smuggled "true". `established != true` is preserved: an
established+valid measurement can still be *wrong* (the A-wrong fixture proves
it), which is exactly why AUDIT exists.

## The wrong-measurement audit fixture (why AUDIT exists)

A deliberately wrong but **integrity-valid** measurement, in an **audit-only**
frozen experimental fixture (not production state):

```text
measurement says        engine X = 59 / 70   (fleet_share 0.843)
underlying fleet        mechanically yields  60 / 70
source_snapshot_hash    still matches the fleet  -> integrity = valid
```

`integrity=valid` only means **provenance matches** — it does NOT mean the
content is correct. The fixture's `measurement` field is a hand-corrupted copy
of `concentration.measure(bare fleet)` (the engine count 60 is changed to 59
and the share recomputed); `concentration.py` itself is NOT modified (canaried:
the real `measure` still returns 60; the fixture is built in `run.py`, not in
the measurement module). The fixture is marked
`fixture: "wrong_measurement_audit_only"` so it is never confused with
production state.

This fixture is **AUDIT-only**. It is NOT run in SUPERVISION mode — doing so
would blur the experiment (SUPERVISION would consume the wrong 59/70, which is
the failure mode that motivates audit). The point is to show that **not auditing
every review does not mean abandoning audit**: the same supervisor that consumes
in SUPERVISION independently challenges in AUDIT and catches a defect that
provenance-validity alone cannot.

## Enforcement — the tool policy (the interesting part)

Not "tell the model don't rederive." The harness already has explicit
authority/policy (S6: ALLOW/NEVER per tool, checked at registration). S11
**extends that idea with mode-specific tool policy**, implemented as a
mode-aware `python_analysis` tool wrapper supplied at harness construction.
**The S6 `harness.py` file itself is NOT modified** (LF-hash canaried); the
policy is a layer in `s11/run.py`, exactly as S10's authority block was a layer
on the measurement envelope without touching `concentration.py`.

```text
SUPERVISION:
  established_answer_exists(question Q)
  -> duplicate derivation of Q refused

AUDIT:
  duplicate derivation permitted
```

**Kept narrow to `dependency_concentration` for S11.** This is NOT a universal
semantic duplicate-computation detector (deliberately deferred). The detector
refuses a `python_analysis` call when it computes a per-`dependency`-field
distribution from worker records — i.e. the thing `concentration.measure`
already provides. Narrow rule (all three must hold, with one guard):

```text
accesses_workers      the code references the workers collection
concentration_field   the code names a concentration field as a grouping key
                      (engine | trigger | effect | digest) -- quoted ("engine")
                      or attribute (w.engine) form
aggregates            the code aggregates (Counter / groupby / value_counts /
                      len / sum / for-in counting / .count / .size / defaultdict)
NOT complementary     the code does NOT also group by a non-concentration field
                      (customer | task | name | exceptions | runs | ...) -- if it
                      does, it is a CORRELATION the measurement does not cover,
                      not a duplicate, and is ALLOWED.
```

A pure `Counter(w["engine"] for w in workers)` is refused (marginal duplicate).
A `Counter((w["engine"], w["customer"]) for w in workers)` is **allowed**
(joint distribution / correlation, not in the measurement). Customer
breakdowns, exception histories, affected-worker-identity lists, and reading
the measurement's own `by_type` are all allowed. **Known narrow boundaries**
(hand-judged, preserved): a joint distribution that happens to include a
concentration field is allowed (may under-refuse a cleverly-worded duplicate);
a single call mixing a pure duplicate and an unrelated complementary read may
leak. The detector is a non-authoritative policy layer; FINDINGS.md is
authoritative.

The refusal is **transparent**:

```text
DUPLICATE_ESTABLISHED_MEASUREMENT
dependency_concentration already provides the mechanical distribution for this
snapshot in SUPERVISION mode. Re-deriving it from worker records is duplicate
established work and is refused. Use the measurement's by_type counts/shares
directly. You may compute other things the measurement does not cover (customer
breakdown, exception history, affected worker identities, correlations).
```

So if the model still tries to count, we learn something useful:
`attempted_re-derivation` = model habit; `executed_re-derivation` = policy
failure. **Those are now separable** — the central methodological advance of S11
over S9/S10, which could only see executed re-derivation.

## Conditions (the method, fleet, measurement, authority, harness, prompt,
## model are identical across all cells; only the mode + fixture differ)

```text
A-supervision    fleet A, established+valid, SUPERVISION mode, normal measurement (60/70)  [consume]
A-audit          fleet A, established+valid, AUDIT mode,       normal measurement (60/70)  [recompute, agree]
A-wrong-audit    fleet A, established+valid, AUDIT mode,       WRONG measurement (claims 59/70, fleet yields 60/70, hash matches)  [recompute, detect defect]
```

The **primary contrast** is A-supervision vs A-audit: same measurement, same
`established+valid` authority block, only the **mode** differs. S10's
A-established re-derived 8/8 because nothing told it re-derivation was
disallowed. S11's A-supervision is told — and the telling is **enforced** by the
tool refusing the duplicate. If A-supervision consumes (executed re-derivation
~0, identifies 60/70 from the measurement) while A-audit recomputes and agrees,
the difference comes from **explicit operating authority**, not from pretending
established means true.

A-wrong-audit is the **why-audit-exists** proof: the same AUDIT mode that agrees
on the normal fixture detects the 59/70-vs-60/70 disagreement on the wrong
fixture and surfaces a measurement defect — a defect `integrity=valid` cannot
catch, because integrity is about provenance, not content.

## Repeats (N=8 per cell, interleaved)

S8/S9/S10 variance discipline: N=8 replicates per cell (24 runs total),
interleaved by round, resumable. The wrong-measurement audit is also N=8 — the
user permits smaller if deterministic, but N=8 preserves the variance honesty
S8's single-run artifact exposed, and 24 runs is cheaper than S10's 32. Each run
independent; `temperature=0.2` supplies run-to-run variance. Local Ollama,
sequential.

## Per-mode categorical outcome (the headline)

The desired outcome **differs by mode** — a re-derivation that is a *failure*
in SUPERVISION is *correct* in AUDIT:

```text
SUPERVISION (A-supervision):
  consume            executed re-derivation == 0, identifies 60/70, cites/uses
                     the measurement  (the win -- habit refused or absent, then consume)
  policy_leak        executed re-derivation > 0  (the policy FAILED to refuse a
                     real duplicate -- the separable failure mode)
  other              did not identify 60/70
  -> desired: 'consume' dominant; executed re-derivation mean ~ 0
     (attempted re-derivation may be > 0 -- habit -- and is tracked separately)

AUDIT (A-audit, normal):
  audit_agree        executed re-derivation > 0, identifies 60/70, notes
                     agreement with the measurement
  audit_rederive     executed re-derivation > 0, identifies 60/70 (no explicit
                     agree/disagree statement)
  other              did not identify 60/70
  -> desired: recompute 60/70, agree with the established measurement

AUDIT (A-wrong-audit, wrong fixture):
  audit_detect_defect   executed re-derivation > 0, recomputes 60/70, flags the
                        disagreement with the measurement's 59 (measurement
                        defect surfaced)  -- the why-audit-exists win
  audit_miss_defect     executed re-derivation > 0, recomputes 60/70 but does NOT
                        flag the 59 disagreement
  trust_wrong           did NOT re-derive; consumed the measurement's 59/70 as
                        the answer  (the failure mode SUPERVISION would hit)
  other                 did not identify the concentration
  -> desired: 'audit_detect_defect' dominant
```

## Judging success (the criteria)

1. **SUPERVISION consumes.** A-supervision: `consume` dominant; **executed**
   re-derivation mean ~ 0 across N=8 (attempted may be > 0 and is tracked);
   identifies 60/70; cites/uses the measurement; interpretation LLM. The
   contrast with A-audit (same measurement, only mode differs) is the evidence.
2. **AUDIT recomputes and agrees.** A-audit: `audit_agree`/`audit_rederive`
   dominant; executed re-derivation > 0 in most runs; identifies 60/70; notes
   agreement with the established measurement where stated.
3. **AUDIT catches the defect (why audit exists).** A-wrong-audit:
   `audit_detect_defect` dominant; recomputes 60/70; flags the disagreement with
   the measurement's 59; surfaces a measurement defect. `trust_wrong` low. This
   is the proof that not auditing every review does not mean abandoning audit.
4. **Mode is authority, not truth.** `claims_measurement_says_risk` False in all
   runs; mode prose + refusal message + authority block contain no
   interpretation word (canaried); `established != true` preserved (A-wrong-audit
   proves an established+valid measurement can be wrong).
5. **Interpretation stays with the LLM.** `interpretation_with_llm` True; the
   mode tells the supervisor *whether to recompute*, not *what the answer means*.
6. **Floor frozen; mode is a layer.** `harness.py` unchanged (LF-hash canaried --
   the mode policy is a tool wrapper in `run.py`, not a harness edit);
   `concentration.py` unchanged (LF-hash canaried; real `measure` still returns
   60; the wrong fixture is built in `run.py`); `s7/memory_seed` unchanged (S5
   not edited; method = S9 candidate one-field transform, canaried);
   `snapshot.py`/`rulebook.jsonl` unchanged; authority bounded; wrong fixture
   marked experimental and audit-only.

## Predictions (frozen in oracle.json before any model call)

```text
A-supervision (normal, SUPERVISION):
  identifies 60/70 (from the measurement); measurement cited/used;
  executed concentration re-derivation ~ 0 (attempted may be > 0 -- habit -- and
  is refused); complementary analysis still allowed; interpretation LLM;
  claims_meas_risk False.  <-- consume, enforced

A-audit (normal, AUDIT):
  re-derives 60/70 from records; compares; agrees with the established
  measurement; executed re-derivation > 0; interpretation LLM.  <-- recompute, agree

A-wrong-audit (wrong fixture, AUDIT):
  re-derives 60/70 from records; detects disagreement with the measurement's 59;
  surfaces a measurement defect; trust_wrong low; interpretation LLM.  <-- why audit exists

RISK (preserved): A-supervision still executes a re-derivation ('policy_leak') --
  the detector misses the duplicate, or the model evades the narrow detector. That
  would show tool-policy enforcement is leakier than prose suggests, separable from
  the model's habit. A-wrong-audit 'trust_wrong' (consumes 59 without recomputing)
  would show AUDIT mode does not actually trigger recomputation.
```

The hypothesis: **the S10 leftover (established+valid re-derived 8/8) is an
operating-mode problem, not an authority-label problem.** S10 made the authority
state visible and the supervisor honored the *negative* signal (invalid→reject)
but not the *positive* one (established→consume), because "you may rely on this"
is a permission and the supervisor's verify-instinct is robust to permissions.
S11 turns the positive signal into a **prohibition enforced by the tool policy**
— in SUPERVISION, re-deriving is not merely discouraged, it is *refused* — and
separates the mode where re-derivation is disallowed (SUPERVISION) from the mode
where it is the job (AUDIT). If A-supervision consumes while A-audit recomputes
and A-wrong-audit catches the defect, the operating-mode layer is the missing
concept above authority. The broader lesson: **authority says whether a
measurement is settled; mode says whether this review consumes it or tests it.**
S11 tests whether mode is the next layer.

## What S11 does NOT do

- No new learning class, no new measurement, no new seed files. The method is
  the S9 candidate held constant; `s7/memory_seed/` is not modified (canaried).
- `concentration.py` is NOT modified (LF-hash canaried; real `measure` returns
  60). The wrong fixture is a hand-corrupted copy built in `run.py`, marked
  experimental, audit-only.
- `harness.py` is NOT modified (LF-hash canaried). The mode policy is a
  `python_analysis` tool wrapper supplied at construction — a layer in `run.py`,
  not a harness edit. The S6 boundary (FleetContext, fresh-namespace contract,
  bench refusal of os/open, ALLOW/NEVER policy) is reused unchanged.
- No universal duplicate-computation detector. The detector is narrow to
  `dependency_concentration` (the user's explicit scope); its boundaries are
  documented and hand-judged.
- No rule creation/promotion; no `snapshot.py` edit; no autonomous machinery.
  The mode is **evidence about an operating-authority lever**, not an edit.
- The wrong-measurement fixture is NOT run in SUPERVISION (would blur the
  experiment).
- `established` is never made to mean `true` (canaried; A-wrong-audit proves it).
- No failures hidden. `policy_leak`, `trust_wrong`, `audit_miss_defect`, and the
  detector's narrow boundaries are all preserved.

## Artefacts

```text
s11/spec.md               this file (frozen)
s11/oracle.json           frozen predictions + mode/fixture definitions, before any model call
s11/run.py                3-cell N-repeat orchestrator + mode tool wrapper + duplicate detector
                          + wrong-measurement fixture + classifier (attempted/executed/refused)
s11/results/canary.json   canaries (harness.py + concentration.py unchanged; wrong fixture
                          59-vs-60 with matching hash; detector battery; mode prose clean; floor)
s11/results/run.log       stdout log
s11/results/<cell>/<NN>/  preserved run.json + session.jsonl + calls.json, per replicate
                          cells: A-supervision, A-audit, A-wrong-audit ; NN: 01..08
s11/results/comparison.json/.md   per-cell distributions + mode contrast + wrong-fixture verdict
s11/results/summary.json  one-line per-cell summary + verdicts + post-run floor canary
s11/results/FINDINGS.md   authoritative hand-judged verdicts
```