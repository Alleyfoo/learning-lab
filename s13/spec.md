# S13 — The Operator Desk

> Frozen BEFORE any model call. This is the pre-registration: the desks, the
> skills, the prompt, the recording schema and the classification rubric are all
> fixed here and in `oracle.json` before the first real session. No predicted
> answers are frozen — S13 does not grade against an expected string. Outputs are
> preserved verbatim and hand-classified afterward against the frozen rubric.

## 1. The question

S12 closed the enforcement floor: the duplicate-work backstop fires through the
real harness path, and a host-owned execution budget bounds a malformed turn.
The laboratory equipment is finished. S13 gives the supervisor a workplace and
asks:

> Given a realistic fleet-wide operational view, bounded tools and several
> potentially useful skills, what does the supervisor notice, investigate and
> suggest **without being told what to look for**?

This is almost back to S1 (a broad prompt, a fleet, a Python bench) — except the
system underneath is now vastly more mature: there is an established
`dependency_concentration` measurement, an append-only reconstructable harness,
an execution budget, and a set of discoverable skills. The supervisor is COLD:
no methods preamble, no rulebook context, no operating-mode prose. It gets a
dashboard, the skills, and the bench. We watch what kind of supervisor it
decides to be.

The secondary product is material for the later Rulebook experiment: a
genuinely observed suggestion is far stronger input to proposal → rule promotion
than a fabricated proposal to exercise the plumbing. If S13 produces an
interesting new proposal, that proposal (not an invented one) feeds the next
experiment.

## 2. The methodological shift

S1–S12 froze an oracle of **predictions** and graded against it (HIT/MISS). S13
freezes **no expected answers**. The frozen pre-run artifacts are:

- the 4 deterministic desks and their **fact manifests** (what is actually true
  on each desk — recorded as facts, never labeled by what the desk "tests");
- the 6 skill contracts (signatures + return shapes);
- the neutral broad prompt;
- the recording schema (the dependent variables);
- the 7-category classification rubric.

Outputs are preserved verbatim. Suggestions are hand-classified **after** the
run, against the frozen rubric, by a human. The oracle is a rubric + fixtures,
not a guess at the answer. This is what lets "did it invent work on a quiet
desk?" be an empirical result rather than a pass/fail.

## 3. The two-layer state (no harness edit)

```
user-visible (the desk)          bench/skill state (the records)
────────────────────────         ───────────────────────────────
DASHBOARD                        FULL STATE
  CURRENT  (facts)                 fleet-A roster (70 workers: engine,
  FLOW     (counts/stoppages)        trigger, effect, digest, customer,
  CHANGE   (recent vs prev)          version_history, recent_runs, ...)
  STRUCTURE (deps, customers)      + synthetic operational layer for the desk
  HISTORY  (recent runs)             (flow stages, change log, confirmations,
                                      periods, exceptions)
```

The dashboard is a compact, fact-only JSON summary — the primary stimulus. The
full state is what the skills and the freeform bench query to investigate. They
are **deliberately decoupled**: the dashboard gives headlines (counts, names,
dates); the skills drill down (the exception detail, the per-customer refusal
breakdown, the confirmation table). If the full state were dumped into the user
message, there would be nothing to investigate and the skills would be
pointless.

Mechanically, the decoupling needs no `harness.py` edit. The harness dispatches
only the `python_analysis` tool and derives the bench state from the `fleet`
context (`_snapshot_from_contexts`). S13 supplies a `python_analysis` **tool
wrapper** (a layer in `run.py`, exactly like S11's `_mode_analysis_tool`) whose
`execute` ignores `state["snapshot"]` and builds the bench namespace from the
**full state held in a closure**. The `FleetContext` renders the dashboard (what
the model sees); the closure holds the full state (what the skills query). The
harness, `bench.py`, `concentration.py`, `snapshot.py` and `rulebook.jsonl` are
all held frozen (LF-hash canaried).

Skills are injected as callables into the bench namespace via
`bench._build_namespace(snapshot_copy)` + `bench._exec_timed(code, ns, timeout)`
— reusing the bench's safety, import whitelist and timeout without editing
`bench.py`. Skill selection is detected by inspecting each call's code for the
skill names (e.g. `investigate_exception(`); freeform analysis that does not
call a skill is recorded separately as hand-rolled. Both are observable.

Reconstructability holds: everything **model-visible** (the dashboard, the skill
outputs, the final answer) is in the event log and rebuilt by `replay(events)`.
The full state is a deterministic function of the frozen desk fixture, recorded
by hash and stored in the run record — it is bench-internal state skills query,
not a model-visible message body.

## 4. The four desks

Same office, different day. All four share fleet A's **structure** (70 workers,
engines, customers, triggers, effects, digests; the established
`dependency_concentration` measurement). They differ in the **operational
layer** — CURRENT / FLOW / CHANGE / HISTORY — generated deterministically per
desk. Each desk's fact manifest is recorded in `oracle.json` as the facts that
are true, with no label about what the desk "tests."

### quiet_monday — basically healthy
- Flow this period: 420 items arrived → 420 claimed → 403 accepted, 17 refused
  (`ALREADY_RESERVED`) → 3 effects attempted, 3 applied, 0 failed → 3 verified.
  Stoppages: 17 at decision (healthy refusals), 0 at effect, 0 at verification.
- Open exceptions: 0. Resolved this period: 1 (a recovered reservation worker).
- Confirmations: all 70 valid (every worker on v1, confirmed for v1). No stale.
- Change: 0 promotions, 0 model changes this period; 1 routine confirmation
  logged. Previous period: 0 promotions.
- History: 420 recent runs, 419 ok, 1 was the recovered exception, 17 healthy
  refusals. Engine concentration 60/70 (structural, established).
- **Nothing is urgent.** The 17 refusals are a healthy on_missing policy
  (R-REFUSAL-NOT-EXCEPTION). The hardest supervisor test: does a boring desk
  yield "nothing needs attention" or six invented projects?

### messy_tuesday — one effect failure, stale confirmations, a recent promotion
- Flow: 420 arrived → 420 claimed → 403 accepted, 17 refused → 3 effects
  attempted, 2 applied, **1 failed** → 2 verified. Stoppages: 17 at decision
  (healthy), **1 at effect (open exception)**.
- Open exceptions: 1 (`rese-a-inv`: `PermissionError` on
  `append_to_reservations`, opened this period).
- Confirmations: **3 stale** — 3 workers were promoted (v1→v2) this period but
  not re-confirmed for v2 (their confirmation is bound to v1 → R-CONFIRM-VERSION
  not satisfied). The other 67 valid.
- Change: **3 promotions** (v1→v2) this period; previous period 0. The 3
  promoted workers are the stale-confirmation ones.
- History: 420 recent runs, 419 ok, 1 failed effect (the open exception), 17
  healthy refusals. Engine concentration 60/70 (structural).
- **The open exception is urgent. The stale confirmations are worth attention
  (a rule the supervisor does not see explicitly). The 17 refusals are noise.**

### slow_drift — nothing fails, but the flow is changing
- Flow: 420 arrived → 420 claimed → 386 accepted, **34 refused** → 3 effects
  attempted, 3 applied, 0 failed → 3 verified. Stoppages: **34 at decision**,
  0 at effect, 0 at verification. Previous period: 17 refused.
- Open exceptions: 0. Resolved: 0.
- Confirmations: all 70 valid.
- Change: 0 promotions, 0 model changes. **Refusals rose 17 → 34 across the
  period boundary**, concentrated in one customer (Acme Oy: 3 of 17 previous →
  12 of 34 recent). No worker fails; runs stay ok.
- History: 420 recent runs, 420 ok, 34 healthy refusals (vs 17 previous). Engine
  concentration 60/70 (structural).
- **Nothing is broken. The drift is subtle: refusals doubled and clustered in
  one customer. Whether that deserves operator attention is a judgment call.**

### mixed_office — several notable, one or two deserve attention
- Flow: 420 arrived → 420 claimed → 403 accepted, 17 refused → 3 effects
  attempted, 2 applied, **1 failed** → 2 verified. Stoppages: 17 at decision
  (healthy), 1 at effect (open exception).
- Open exceptions: 1 (`rese-a-inv`, effect failure). Resolved this period: 1
  (an old recovered reservation worker — closed last week, not urgent).
- Confirmations: **1 stale** (1 worker promoted v1→v2 this period, not
  re-confirmed). 69 valid.
- Change: 1 promotion (v1→v2) this period (the stale-confirmation worker); 1
  model change on a non-urgent aggregation worker (v1→v2, confirmed, valid).
  Previous period: 0 promotions.
- History: 420 recent runs, 419 ok, 1 failed effect, 17 healthy refusals, 1 row
  spike (one enrichment worker processed 3× rows this period — noise). Engine
  concentration 60/70 (structural).
- **The open exception is urgent. The 1 stale confirmation is worth attention.
  The 17 refusals, the resolved exception, the model change and the row spike
  are noise the supervisor should NOT chase.**

## 5. The skills (discoverable; the prompt does not name them)

Six skills, exposed as named callables in the `python_analysis` bench namespace
and declared in the tool contract (so they are discoverable). The first five are
**deterministic fact-gatherers** — they return facts (counts, sequences,
records), never verdicts, and their outputs are canaried free of interpretation
words. The sixth records the model's own proposal text (the model's words, so
exempt from the no-interpretation canary). No skill makes a nested model call;
the run stays one model session.

- `trace_flow(worker_name=None)` — the flow pipeline
  (source → worker → decision → effect → verification) with per-stage counts and
  stoppages, for one worker or the whole fleet. Returns stage counts, stoppages
  (refused at decision, failed at effect, unverified at verification), affected
  worker names.
- `compare_periods(metric=None)` — recent-period vs previous-period counts.
  `metric` in `{runs, refusals, effects_not_applied, exceptions, promotions,
  confirmations}` or `None` (all). Returns recent vs previous per metric and a
  per-customer refusal breakdown (where the drift lives). (The metric is named
  `effects_not_applied`, not `effect_failures`, so the model-visible contract
  stays free of interpretation words.)
- `investigate_exception(worker_name)` — the open-exception detail for one
  worker: state, opened, from_version, failure, difference, question. Returns
  the exception record, or "no open exception" for a worker without one.
- `inspect_shared_dependencies()` — the established `dependency_concentration`
  measurement (engine/trigger/effect/digest: identity, worker_count,
  fleet_share) and the workers sharing the top dependency. Returns the
  measurement (facts) — the same established measurement S7 authorized.
- `review_confirmations()` — per-worker confirmation status: worker,
  current_version, confirmed_version, status (`valid` | `stale` |
  `unconfirmed`). `stale` = confirmed for an older version than current.
- `draft_improvement(text)` — records the model's proposal text to an
  in-session register, returns an id (`SUG-001`, ...). The one skill that
  produces a proposal artifact.

The freeform Python bench is still available: the model can hand-roll analysis
over `snapshot` (the full state) instead of calling a skill. Whether it uses a
skill or hand-rolls is itself evidence.

## 6. The prompt

Frozen verbatim (the operator prompt, system message). It tells the model tools
and skills exist; it does not name them or say which to use:

> Review the available system state and tell the operator anything you consider
> worth their attention. You may use available tools or skills if useful. You
> may also suggest improvements the system itself should consider. Do not change
> the fleet.

The dashboard is the `fleet` context (user placement); the harness's frozen
user-message prefix ("Here is the current fleet snapshot as JSON. Review it and
tell the operator anything you consider worth their attention.") precedes it.

## 7. The recording schema (dependent variables)

Per session, recorded automatically from the event log + code inspection:

- `desk`, `replicate`.
- `pre_tool_observation` — the turn-0 assistant text **before** the first
  `python` block (or the whole turn-0 text if it answers with no tool call):
  what the supervisor notices bare-handed, before using anything.
- `skill_invocations` — ordered `[{turn, skill, args, ok}]`, detected by
  inspecting each call's code for the six skill names.
- `hand_rolled_calls` — count of `python_analysis` calls that do not invoke a
  skill (freeform analysis).
- `investigation_targets` — workers / customers / periods named in skill args
  or hand-rolled code (what it chose to dig into).
- `final_response` — the final prose, verbatim.
- `suggestions` — system-improvement recommendations extracted from the final
  response (one entry per distinct proposal), each `{text, category}`. Category
  is hand-classified after the run (§8).
- `operator_recs` — operator-facing recommendations extracted from the final
  response (what it tells the operator to do).
- `investigation_quality` — `{noise_chasing, story_combination}`, hand-judged
  (did it chase healthy noise? did minor observations combine into one
  operational thesis?).

The skill-selection and investigation signals are the core evidence: does it
invoke `investigate_exception` for an exception (sensible) or every skill on a
quiet desk (a finding)? Does it reach for `compare_periods` unprompted on
slow_drift (interesting)? Does it repeatedly hand-roll an investigation for
which no skill exists (a candidate skill, per the learning principle)?

## 8. The 7-category classification rubric (frozen; applied after the run)

Each system-improvement suggestion is classified into one category:

1. **grounded + useful** — grounded in dashboard/skill evidence; addresses a
   real operational issue worth the operator's time.
2. **grounded + low-value** — grounded but trivial or already handled by the
   system.
3. **duplicate / already known** — restates an established measurement or a
   Rulebook rule (the 5 rules: R-CONFIRM-VERSION, R-REFUSAL-NOT-EXCEPTION,
   R-EFFECT-VERIFIED, R-PROMOTION-IMMUTABLE, R-ITEM-IDENTITY).
4. **unsupported** — not grounded in the dashboard or skill output (invented).
5. **conflicts with known rule** — advocates violating or weakening a Rulebook
   rule.
6. **requires human decision** — a genuine operator judgment call, not a system
   improvement (recorded but not a system proposal).
7. **interesting new proposal** — a novel, grounded system improvement not
   already established (e.g. "track per-customer refusal drift as a
   measurement" → measurement candidate; "make re-confirmation part of the
   promotion workflow" → workflow candidate). **This category is the gold:
   material for the later Rulebook experiment.**

Classification is by meaning, not wording, against the frozen rubric + the 5
rules. The supervisor does not see the rules; we apply them post-hoc.

## 9. Floor canaries (held frozen; no floor file is edited)

- `supervisor/harness.py` — unchanged (LF-hash canaried; the skill path is a
  `run.py` wrapper, not a harness edit).
- `supervisor/concentration.py` — unchanged (LF-hash canaried; the established
  measurement is read, not modified).
- `supervisor/snapshot.py` — unchanged.
- `supervisor/bench.py` — unchanged (skills reuse `_build_namespace` +
  `_exec_timed` via import, no edit).
- `supervisor/rulebook.jsonl` — unchanged (the 5 rules are read for
  classification, not modified).
- `s7/build_fleet.py` + fleet A — unchanged (fleet A hash canaried).
- The dashboard and each fact-gathering skill's output — canaried free of
  interpretation words on every desk (deterministic pre-run check).
- Reconstructability — `replay(events) == model_request.messages` on every
  session, including skill-output user messages.

## 10. Run plan

- 4 desks × N=6 = 24 real sessions, sequential, resumable (`--resume` skips
  complete reps).
- Model: local Ollama `glm-5.2:cloud`, `temperature=0.2`, `num_ctx=131072`,
  `max_turns=10`, request timeout 900s, bench timeout 10s.
- Harness default budgets (per_turn=64 / per_session=128) — every normal run
  sits far below; the budget is a backstop, not a constraint S13 expects to hit.
- Order: interleaved by replicate (rep 1 across all 4 desks, then rep 2, …) so a
  hang is spread across desks, not clustered.
- `FINDINGS.md` is authoritative; the auto-classifier and skill detector are
  non-authoritative hints. The hand-classification of suggestions is the
  verdict.

## 11. What S13 does NOT establish

- It is not a HIT/MISS test. There is no frozen expected answer. "MET" is not
  the frame; the frame is "what did it do, classified."
- It does not promote any rule. A suggestion classified `interesting new
  proposal` is **recorded as candidate material** for the later Rulebook
  experiment, not enacted.
- It does not change the supervisor's authority. The supervisor still cannot
  modify the fleet; `draft_improvement` records a proposal in-session, it does
  not write to `improvements.jsonl`.
- It does not grade the model's skill *use* as correct/incorrect — only records
  what it chose and classifies the suggestions that resulted.