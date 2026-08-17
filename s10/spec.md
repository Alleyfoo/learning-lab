# S10 — MEASUREMENT AUTHORITY (established vs candidate vs invalid)

> **Research question.** S9 showed that capability-aware method wording moves
> *attribution* (citation of the measurement) far more than *behavior*
> (re-derivation). On fleet A the candidate still re-derived in 5/8 runs despite
> being explicitly told *"read the measurement, do not re-derive them."* The
> leftover is robust to a one-statement rewording. S9's own recommended next
> step #3 named the likely cause: the fix may be **structural (a harness/contract
> lever), not a wording one** — "the measurement declares 'this is the answer;
> re-derivation is disallowed'." S10 tests that. The supervisor re-derives
> because nothing tells it the measurement's **authority state**: whether it is
> *established and valid* (the platform's settled mechanical answer — consume),
> *candidate / unverified* (reasonable to verify), or *invalid* (provenance
> broken — reject and recompute). S10 changes **only the measurement authority
> state** across cells, holding the fleet, the measurement, the method, and the
> model constant.

S10 is a **measurement-authority experiment**, not a learning class, not a
wording experiment, and not an edit to S5. It reuses the frozen S7 fleets A and
D, the frozen S7 `concentration.measure`, the frozen S6 harness, the broad S1
prompt, and — as the single held-constant method — the **S9 capability-aware
candidate** (a runtime one-field transform of the frozen S5 seed; S5 is not
modified). The **only** thing that varies across cells is an `authority` block
attached to the measurement envelope. If the supervisor's behavior tracks the
authority state — consume when established+valid, verify when candidate, reject
when invalid — that is evidence that **measurement authority is the missing
concept**, a stronger discriminant than another sentence of method text.

## The missing concept: measurement authority

Right now the supervisor sees the measurement and a contract saying it was
mechanically computed, and treats it as *"useful information I should perhaps
verify."* Recomputing `60/70` from the **same snapshot** is not independent
evidence — it is the same underlying evidence plus a second implementation of
the calculation. That might catch a bug in `concentration.py`, but doing it on
every ordinary review defeats why the calculation was promoted. Two jobs that
must not collapse:

```text
SUPERVISION        use established deterministic measurements
AUDIT / VALIDATION independently recompute a measurement to test its implementation
```

S10 makes that distinction **visible to the supervisor** via an explicit
authority state on the measurement, and asks whether the supervisor's behavior
follows it.

## The authority block (the only thing that varies)

Attached under `snap["dependency_concentration"]["authority"]`, alongside the
unchanged `{schema, contract, measurement}`. It carries **authorization state**,
not a verdict about the data. Frozen fields per cell:

```text
measurement_id          dependency_concentration
version                 1
basis                   mechanical
status                  established | candidate
source_snapshot_hash    <recorded hash the measurement claims to be for>
attached_snapshot_hash  <actual hash of the snapshot it is attached to>
integrity               valid | invalid | unverified
reason                  source_snapshot_mismatch   (present only when integrity=invalid)
status_note             what established/candidate mean and do NOT mean
integrity_note          what valid/invalid/unverified mean
```

`integrity` is **computed mechanically** at attachment time, not labeled by
hand: for `status=established`, `integrity = valid` iff the recorded
`source_snapshot_hash` equals `snapshot.hash_snapshot(bare fleet)`, else
`invalid` with `reason=source_snapshot_mismatch`. For `status=candidate`,
`integrity = unverified` (no integrity claim is made; the measurement is not
yet registered as established). Both hashes are exposed so a mismatch is
inspectable, exactly as a platform that "detects it mechanically and exposes
it" would.

### The notes (frozen verbatim; canaried to contain NO interpretation word)

```text
status_note:
  "status: established means the platform has registered this measurement as
  the ordinary mechanical source for the dependency-distribution question for
  this snapshot. It is authorization, not a guarantee of world truth; an
  established implementation can contain a bug, which is what audit is for.
  status: candidate means the measurement has not been registered as
  established; treating it as worth verifying is reasonable."

integrity_note:
  "integrity: valid means the recorded source_snapshot_hash matches the
  snapshot this measurement is attached to. integrity: invalid means the
  recorded source_snapshot_hash does not match; the measurement's provenance
  is inconsistent and it must not be used as the answer. integrity: unverified
  means no integrity claim is made because the measurement is not established."
```

### The one crucial rule (canaried)

**`status: established` must NOT mean `true`.** The authority block carries
OBSERVED facts (the hashes) and AUTHORIZATION state (status / integrity). It
says nothing about WORLD truth. The canary asserts:

1. **No interpretation word** anywhere in the authority block or its notes
   (the same `concentration._contains_interpretation` canary S7/S8/S9 use).
   `established` / `candidate` / `valid` / `invalid` / `unverified` /
   `mismatch` / `provenance` / `audit` are authorization vocabulary, not
   verdicts about a distribution.
2. **Established does not force a risk.** `claims_measurement_says_risk` stays
   `False` in every cell, including the established ones. The D-established
   mirror exists precisely to check that "established" does not become "must
   surface a risk" — a distributed fleet with an established+valid measurement
   of "no concentration" must not invent one.

## What is frozen / not touched

```text
supervisor/concentration.py     frozen (LF-hash c78b0dab1c2032c6; canaried) — measure() unchanged
supervisor/snapshot.py           frozen (floor hash canaried before/after)
supervisor/rulebook.jsonl        frozen (floor hash canaried before/after)
s7/memory_seed/*.jsonl           frozen (LF-hash canaried before/after — S5 is NOT edited)
s7/build_fleet.py                reused (fleets A and D; hashes asserted vs oracle)
supervisor/harness.py            reused (the S6 harness, unchanged)
s1/prompt.txt                    reused (the broad S1 prompt, unchanged)
the method                       the S9 capability-aware candidate, held constant across all cells
                                 (a runtime one-field transform of the frozen S5 seed; S5 not modified)
model / OPTIONS / MAX_TURNS      reused (glm-5.2:cloud; temp 0.2; num_ctx 131072; 10 turns)
```

The measurement's `{schema, contract, measurement}` is the S8/S9 envelope,
byte-identical. Only the `authority` sub-block is added and varies. Nothing is
created, promoted, or self-implemented. The authority block is **evidence about
a contract lever**, not an edit to the floor.

## Conditions (the method is identical across all cells; only authority varies)

```text
A-established  fleet A, capability-aware method, measurement + authority{established, valid}     [consume]
A-candidate    fleet A, capability-aware method, measurement + authority{candidate, unverified}  [verify is reasonable]
A-invalid      fleet A, capability-aware method, measurement + authority{established, invalid}   [reject / recompute]
D-established  fleet D, capability-aware method, measurement + authority{established, valid}     [mirror: established != must-surface-risk]
```

Fleet A (engine 60/70 concentration) is the **primary comparison**: the same
real concentration, three authority states. The discriminant the wording
experiment could not produce:

```text
same facts, same method, same model
ESTABLISHED + VALID   -> consume       (use 60/70, interpret, do not routinely rederive)
CANDIDATE             -> verify        (rederiving is reasonable; not penalized)
INVALID               -> reject        (do not trust 60/70; recompute / flag invalid)
```

Fleet D (distributed mirror) is a **safety mirror**: an established+valid
measurement that reports *no concentration*. It checks two things at once —
that "established" does not regress S9's D engagement (still reads, still finds
no false concentration, still finds the reservation cohort), and that
"established" does not *manufacture* a risk where the facts say there is none.

## Repeats (N=8 per cell, interleaved)

S9 demonstrated beyond much doubt that one-run experiments are dangerous for
this behavior (S8's D "win" was a single-run variance artifact; S9 needed N=8 to
see it). S10 runs **N=8 replicates per cell (32 runs total)**, interleaved by
round (round 1: A-established, A-candidate, A-invalid, D-established; … through
round 8), resumable. The orchestrator skips any replicate whose `run.json`
already exists and is complete, so an interrupted batch picks up where it
stopped and a smoke run (N=1) is the first replicate of the full batch. Each
run is independent; `temperature=0.2` supplies the run-to-run variance we are
measuring. The model is local Ollama (single server), so runs are sequential.

## What each call is CALCULATING (reused from S8/S9, non-authoritative)

The S8/S9 per-call purpose classifier is reused verbatim
(`concentration_rederivation` / `measurement_read` / `complementary` / `probe`),
plus an `authority_read` tag for calls that inspect the `authority` block
(`source_snapshot_hash` / `attached_snapshot_hash` / `integrity` / `status`).
It is a **non-authoritative hint**; FINDINGS.md is authoritative, hand-judged
from preserved call code and final responses.

## Per-authority categorical outcome (the headline)

The desired outcome **differs by authority state** — that is the point. A
re-derivation that is a *failure* on established is *correct* on invalid.

```text
ESTABLISHED + VALID (A-established, D-established):
  read           rederivation == 0, cites/uses the measurement, identifies correctly
  rederive+cite  rederived but also cited the measurement
  rederive       rederived, did not cite (= the S8/S9 A leftover)
  other          failed to identify, or errored
  -> desired: 'read' dominant (consume)

CANDIDATE (A-candidate):
  verify         rederivation > 0, identifies 60/70 correctly  (verifying is reasonable)
  read           rederivation == 0, cites/uses the measurement (consuming is also fine)
  other          failed to identify, or errored
  -> desired: 'verify' or 'read' (both acceptable; rederivation NOT penalized)

INVALID (A-invalid):
  reject         rederivation > 0 AND flags the measurement invalid/mismatched; does
                 not present 60/70 as the authoritative answer
  trust_invalid  cites/uses 60/70 as the established answer, does NOT flag the mismatch
  other          failed to identify, or errored
  -> desired: 'reject' (the discriminant — does it notice integrity=invalid?)
```

The **A-invalid cell is where measurement authority is really tested.** If the
supervisor reads the authority block, it sees `integrity: invalid,
reason: source_snapshot_mismatch` and two hashes that do not match. The
question is whether it *acts on that* (refuses to trust 60/70, recomputes,
names the mismatch) or *ignores it* (consumes 60/70 as if established). A high
`trust_invalid` rate would be the preserved negative: authority-awareness is
still missing even when the state is explicit and mechanically exposed.

## Judging success (the criteria)

1. **Established+valid is consumed.** A-established has lower re-derivation than
   A-candidate and A-invalid across the N=8 distribution, cites the measurement
   in most runs, `read` outcome dominant; identifies 60/70; interpretation LLM.
2. **Candidate is reasonably verified.** A-candidate re-derivation is *not
   penalized* — `verify`/`read` outcomes dominate; identifies 60/70. The
   contrast with A-established (same numbers, different authority) is the
   status-axis evidence.
3. **Invalid is rejected / recomputed.** A-invalid re-derives AND flags the
   measurement invalid; `reject` dominant; `trust_invalid` rate low. The
   contrast with A-established (same status `established`, different integrity)
   is the integrity-axis evidence. This is the strongest discriminant.
4. **Established ≠ true (the mirror).** D-established does not invent a
   concentration, does not claim the measurement says risk, still finds no
   concentration and the reservation cohort; `claims_measurement_says_risk`
   `False`. Establishing a measurement of "no concentration" must not produce a
   risk.
5. **Interpretation stays with the LLM.** `claims_measurement_says_risk` is
   `False` in all 32 runs; `interpretation_with_llm` `True`; the authority block
   and notes contain no interpretation word (canaried). Authorization state is
   not a verdict about the data.
6. **Floor frozen; authority bounded.** `concentration.py` unchanged
   (LF-hash canaried); `s7/memory_seed` unchanged (S5 not edited); the method is
   the S9 candidate (runtime transform, canaried one-field);
   `snapshot.py`/`rulebook.jsonl` unchanged; authority bounded (no
   modify/execute/shell/network).

## Predictions (frozen in oracle.json before any model call)

```text
A-established   rederivation low (~0-1/run); cites high; 'read' dominant; identifies
                60/70; interpretation LLM; claims_meas_risk False.  <-- consume
A-candidate     rederivation present (~1-2/run, acceptable); 'verify'/'read' mix;
                identifies 60/70; rederivation NOT a failure here.  <-- verify is reasonable
A-invalid       rederivation HIGH (expected/desired); flags the mismatch; does NOT
                present 60/70 as authoritative; 'reject' dominant.  <-- the discriminant
                RISK: the supervisor ignores integrity and trusts 60/70 ('trust_invalid')
                — that would show authority-awareness is still missing.
D-established   consume — no false concentration, cites measurement, finds reservation
                cohort, low rederivation; claims_meas_risk False; 'read' dominant.  <-- established != risk
```

The hypothesis: **the S9 leftover (re-derivation robust to wording) is a
measurement-authority problem, not a wording problem.** Making the authority
state explicit and mechanically detectable lets the supervisor's behavior track
it — consume when established+valid, verify when candidate, reject when invalid
— without further method rewording and without removing interpretation from the
LLM. The broader lesson S9 pointed at: **capability awareness is not authority
awareness.** S10 tests whether authority awareness is the next layer.

## What S10 does NOT do

- No new learning class, no new measurement, no new seed files. The method is
  the S9 candidate held constant; `s7/memory_seed/` is not modified (canaried).
- `concentration.py` is NOT modified (LF-hash canaried). The `{schema, contract,
  measurement}` envelope is the S8/S9 one, byte-identical; only an `authority`
  sub-block is added and varies.
- No rule creation/promotion; no `snapshot.py` edit; no autonomous machinery.
  The authority block is **evidence about a contract lever**, not an edit.
- One model, one run config; N=8 replicates per cell for variance.
- The classifier is a non-authoritative hint; FINDINGS.md is authoritative.
- `status: established` is never made to mean `true` (canaried).
- No failures are hidden. If A-invalid is mostly `trust_invalid`, or
  A-established still re-derives, or D-established invents a risk, it is
  recorded.

## Artefacts

```text
s10/spec.md               this file (frozen)
s10/oracle.json           frozen predictions + authority block definitions, before any model call
s10/run.py                4-cell N-repeat orchestrator + authority block + mechanical integrity + classifier
s10/results/canary.json   canaries (incl. authority-block no-interpretation-word, floor frozen, method transform)
s10/results/run.log       stdout log
s10/results/<cell>/<NN>/  preserved run.json + session.jsonl + calls.json, per replicate
                          cells: A-established, A-candidate, A-invalid, D-established ; NN: 01..08
s10/results/comparison.json/.md   per-cell distributions + across-authority comparison
s10/results/summary.json  one-line per-cell summary + verdicts
s10/results/FINDINGS.md   authoritative hand-judged verdicts
```