# S15 — The Duplicate-Gate Guard (mandatory novelty check inside propose_rule)

> Frozen BEFORE any model call. S15 is a tiny, single-change A/B against S14:
> the same 6 cells, the same N=6, the same verbatim S13 canary texts and
> synthetic probes, with ONE machinery change — `propose_rule` now runs a
> MANDATORY novelty/duplicate check between the evidence gate and the conflict
> gate. S14 is FROZEN (read-only); S15 forks `s14/run.py` into `s15/run.py` and
> reuses the S14 cells/oracle verbatim texts for an exact comparison. No
> `supervisor/*`, `s13/*`, or `s14/*` file is edited. No rule is promoted to
> the real rulebook; ACTIVE remains S15-local.

## 1. The question (and what S14 left open)

S14 showed the supervisor routes improvement proposals to the correct
institutional mechanism **intelligently** — 5 of 6 cells perfect (6/6, zero
variance). The one failure was the enforcement-framed duplicate (re-confirm-after-
promotion, which restates R-CONFIRM-VERSION): it was misrouted to `propose_rule`
and reached ACTIVE in 3/6 reps. The cause was precise:

- The conflict gate **cannot** catch a duplicate — a restatement is *compatible*
  (it reinforces, not conflicts), so `propose_rule`'s conflict gate waved it
  through to proposed → ACTIVE every time.
- The duplicate detector (`check_duplicate_rule`) **worked 4/4 when invoked**,
  including on the enforcement-framed text (rep01, rep04). The gap was
  **invocation**: calling it was optional, and the 3 misrouted reps skipped it.

S15 tests the design principle this surfaces:

> **Some questions are too important to depend on the supervisor remembering to
> ask them.** The authority-bearing transition must run the check itself.

S15 does NOT test whether the LLM conflict classifier can be made deterministic.
The rep04 conflict-gate non-determinism (blocked, then compatible, on the same
text) is explicitly **out of scope**: the mandatory duplicate gate removes that
text from the conflict classifier *before* it ever reaches that ambiguous
question. Whatever instability remains on genuinely novel proposals is observed,
not fixed.

## 2. The single change (the lifecycle, modified)

S14's `propose_rule`:
```
evidence gate -> conflict gate -> proposed|blocked -> approve -> ACTIVE
```

S15's `propose_rule`:
```
propose_rule(text, evidence, rule_draft)
   |
   evidence gate  (refuses if evidence empty) -- unchanged
   |
   MANDATORY novelty/duplicate check  (check_duplicate_rule, reuses S14's
   DUPLICATE_RULE_PROMPT, against the 5 rules)
   |
   ├── restates an existing rule
   |       -> demote to DUPLICATE_RULE
   |       -> record in duplicate_register (named rule id)
   |       -> NO proposed_rules entry, NO conflict check, never ACTIVE
   |
   └── novel (restates None)
           |
           conflict gate  (rulebook.classify, unchanged)
           |
           ├── conflicts -> state=blocked (never ACTIVE)
           └── compatible -> state=proposed -> approve_rule -> ACTIVE
```

The model may still call `check_duplicate_rule()` beforehand for preliminary
reasoning. But the **write boundary** (`propose_rule`) does not trust that
somebody remembered — it runs the check itself. This is exactly analogous to
database validation: we are not forbidding intelligent preliminary reasoning; we
are saying the final write boundary does not trust that all prerequisites were
remembered.

Everything else in S14 is unchanged: the 4 routes (file_measurement /
file_skill / file_duplicate_rule / reject_conflict), the gate tools, the
warm-router prompt, the 5 rules, the registers, the no-auto-promotion canary,
the orchestrator-simulated approval. Only `propose_rule`'s internal pipeline
gains the mandatory check.

## 3. The cells (identical to S14 — exact A/B)

Same 6 cells × N=6 = 36 sessions, same canonical verbatim texts (the 4 S13
canary texts read byte-exact from the frozen S14 oracle, which read them from
the frozen S13 run.json files; the 2 synthetic probes). Same emergence counts
disclosed. Same routing prompt. The only difference is the machinery in
`propose_rule`. This makes the A/B exact: any change in the duplicate_rule cell
is attributable to the mandatory gate, not to a different text or prompt.

## 4. The falsifiable prediction

| cell | S14 result | S15 prediction |
|---|---|---|
| measurement | 6/6 MEASUREMENT | unchanged (6/6 MEASUREMENT; never enters propose_rule) |
| skill_workflow | 6/6 SKILL_WORKFLOW | unchanged (6/6; never enters propose_rule) |
| **duplicate_rule** | **3/6 wrongly ACTIVE** (3/6 DUPLICATE_RULE) | **0/6 ACTIVE, 6/6 DUPLICATE_RULE** — the mandatory gate catches the restatement before the conflict gate |
| new_rule (genuine) | 6/6 → ACTIVE | **6/6 still proceeds** to ACTIVE (the engine rule is novel, so the duplicate check returns None and the lifecycle continues) |
| conflicting_probe | 6/6 REJECT_CONFLICT (never active) | unchanged |
| compatible_mirror_probe | 6/6 DUPLICATE_RULE | unchanged (the model files duplicate directly; if it ever calls propose_rule, the mandatory gate also catches it) |

If this holds, the demonstration is:

> **The supervisor chooses institutional mechanisms intelligently, but critical
> governance checks belong inside the institutional mechanism, not in the
> supervisor's discretionary workflow.**

And the genuine S13 loop completion is preserved: real supervisor observation →
repeated suggestion → correct rule routing → evidence → conflict check →
human-controlled approval → ACTIVE — now with the guarantee that a restatement
cannot sneak through the conflict gate's "compatible."

## 5. What is NOT in S15 (scope discipline)

- No fix for LLM conflict-classifier non-determinism. The enforcement-framed
  duplicate text is removed from the conflict classifier by the mandatory
  duplicate gate; remaining instability on genuinely novel proposals is
  observed, not engineered away.
- No framing-variation probe (paraphrasing the duplicate as bare restatement
  vs enforcement). Held in reserve; out of scope.
- No new cells, no change to N, no change to the prompt, no change to the 5
  rules, no real-rulebook mutation. One machinery change only.

## 6. Floor canaries (held frozen; no floor file is edited)

- `supervisor/{harness,concentration,snapshot,bench,rulebook,core}.py`,
  `rulebook.jsonl`, `improvements.jsonl`, `build_fleet.py` — unchanged (LF-hash
  canaried). S15 imports them, never edits.
- **`s14/**` read-only** — S14 is frozen; S15 reuses its oracle's verbatim texts
  and DUPLICATE_RULE_PROMPT, never writes `s14/**`.
- **`s13/**` read-only** — unchanged.
- **No-auto-promotion** — no record reaches ACTIVE unless the orchestrator
  called `approve_rule`; the model never calls `approve_rule`.
- **Mandatory-gate canary (new)** — every `propose_rule` call that passes the
  evidence gate is followed by a duplicate-check call recorded in
  `tool_invocations`; a restatement never produces a `proposed_rules` entry.
- **Evidence gate** — refuses empty evidence (unchanged).
- **Reconstructability** + **no-interpretation** + **stub-first** — unchanged
  from S14.

## 7. Run plan

- 6 cells × N=6 = 36 real sessions, sequential, resumable.
- Model: local Ollama `glm-5.2:cloud`, temp=0.2 (routing), 0.1 (gates),
  num_ctx=131072, max_turns=6, request timeout 900s, bench timeout 10s.
- ~2-3 Ollama calls per new_rule/duplicate_rule rep (routing + the mandatory
  duplicate check + possibly the conflict check); fewer for the other cells.
  Resumable; batched for the Ollama cloud rate-limit.
- `FINDINGS.md` is authoritative; the auto-extracted `route_chosen` + the
  new `mandatory_gate_caught` field are hints; the hand-classification is the
  verdict.

## 8. What S15 does NOT establish

- It does not make the LLM conflict classifier deterministic (out of scope; §5).
- It does not promote any rule to the real `rulebook.jsonl` (ACTIVE is S15-local).
- It does not test paraphrase/framing robustness (one canonical text per cell).
- It does not change routing intelligence — the model's route *choice* is
  unchanged from S14; S15 only changes what `propose_rule` does once called.