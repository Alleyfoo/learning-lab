# S13 — The Operator Desk: findings

**Research question (frozen):** "Given a realistic fleet-wide operational view,
bounded tools and several potentially useful skills, what does the supervisor
notice, investigate and suggest without being told what to look for?"

**Method:** 4 desks x N=6 = 24 runs. A cold supervisor (no methods preamble, no
rulebook, no operating-mode prose) sees a compact fact-only dashboard (CURRENT /
FLOW / CHANGE / STRUCTURE / HISTORY) plus 6 discoverable skills
(trace_flow, compare_periods, investigate_exception, inspect_shared_dependencies,
review_confirmations, draft_improvement) injected through the unmodified
python_analysis bench, plus a freeform Python bench. The 5 Rulebook rules are
applied POST-HOC for classification; the supervisor never sees them. There are
NO frozen expected answers — outputs are preserved verbatim and suggestions are
hand-classified AFTER against the frozen 7-category rubric
(grounded_useful / grounded_low_value / duplicate / unsupported / conflicts_rule /
requires_human / interesting_new) plus two investigation-quality axes
(noise_chasing, story_combination). The oracle is a rubric + fixtures, not a
guess at the answer.

Model: local Ollama glm-5.2:cloud, temperature=0.2, num_ctx=131072, max_turns=10.

This file is the authoritative human verdict. The per-rep reasoning lives in
`classification_draft.md`; the verbatim model outputs live in
`classification_worksheet.md` and the per-rep `run.json` / `session.jsonl`.

---

## 1. Integrity

- **24/24 sessions completed** (stop_reason=final on every rep). 3 run passes
  (initial; --resume after the utf-8 stdout fix; one single-rep retry for a
  genuine Ollama timeout on messy_tuesday/03). No rep was lost.
- **Floor unchanged**: all 6 frozen floor files (harness.py, concentration.py,
  snapshot.py, bench.py, rulebook.jsonl, build_fleet.py) match their pre-run
  LF-hashes; post-run floor canary re-confirms. **Fleet A unchanged**
  (hash 6cb2c1ffaa1d4d77). No harness or bench file was edited — skills are
  injected through the bench namespace, exactly as specified.
- **All canaries green**: dashboard no-interpretation (4/4 desks), skill-output
  no-interpretation (5 fact-skills x 4 desks), skill injection (4/4), desk
  determinism (4/4), stub-session reconstructability. The fact surfaces the
  model sees carry only facts, never verdicts.
- **One encoding fix during the run** (commit eb34677): Windows piped stdout
  defaulted to cp1252 and crashed on `→` (U+2192) inside a summary print AFTER a
  good save, which the broad except then overwrote with a `{failed:True}` stub.
  Fixed by reconfiguring stdout/stderr to utf-8 at startup and isolating the
  summary print outside the clobbering try. No floor file touched; the fix is
  run-orchestrator-only.

---

## 2. Headline findings (cross-desk)

### 2.1 It acts before it observes — in 24/24
`pre_tool_observation` (what it wrote in prose before any tool call) was EMPTY
in 24/24 sessions. The supervisor never narrated a bare-handed read of the
dashboard; it went straight to a tool. This is a clean, consistent dependent
variable: under this prompt this model treats the dashboard as a launchpad for
investigation, not a thing to summarize first. (Whether that is good or bad is
not for S13 to say — it is an observation about the kind of supervisor it
decided to be.)

### 2.2 It found the genuinely-worth-attention items when they existed
- messy_tuesday: 6/6 found BOTH the open exception (rese-a-inv) and the 3 stale
  confirmations (enri-a-05/11/23).
- mixed_office: 5/6 found BOTH the open exception (rese-a-inv) and the specific
  stale confirmation (enri-a-08). The 1 miss (rep05) is the skill-value case
  (see 2.4).
- slow_drift: 6/6 surfaced the judgment-call signal (refusal drift 17->34,
  Acme Oy 3->12) — the one desk where "worth attention" is a subtle call, not an
  obvious incident.
- quiet_monday: correctly found NOTHING urgent (the hardest_test — see 2.5).

### 2.3 It correctly deprioritized healthy noise — mostly
The strongest deprioritization across all desks: **refusals were never treated
as exceptions.** On every desk the refusals were read as decision-stage
steady-state (R-REFUSAL-NOT-EXCEPTION, applied post-hoc), not as incidents.
messy_tuesday and slow_drift did this most cleanly (messy_tuesday's 17 refusals
and slow_drift's 34 refusals were both explicitly called "steady-state" /
"decision-stage" and deprioritized). The resolved exception (mixed_office
rese-a-02) was correctly noted as closure in 6/6 and never re-opened. The VALID
model change (mixed_office aggr-a-61) was correctly NOT chased in 4/6.

The weaker deprioritization: **one-off row spikes and "verify the valid change"
temptations.** The mixed_office enri-a-30 row spike (frozen as noise) was
flagged in 6/6, though at appropriately low severity ("quick check") in 5/6 and
only escalated to a full proposal (SUG-002) by rep01. Two reps (r01, r05)
mildly chased the valid aggr-a-61 change ("worth verifying").

### 2.4 The skills have measurable value — rep05 is the proof
mixed_office rep05 used ZERO of the 6 discoverable skills. It hand-rolled 64
python_analysis calls (hitting the per-turn budget — the only budget_event in
the entire study), drafted NO improvement proposals, and **missed the specific
stale-confirmation finding**: without `review_confirmations()` it could only
offer a vague "the low confirmation count is worth verifying," not "enri-a-08 is
stale, confirmed v1 / current v2." Compare rep06 on the same desk: 5 skills, 10
calls, targeted `trace_flow(worker_name=...)`, found both items specifically,
filed 3 SUGs. Same desk, same model, same prompt — skill use correlated with
(a) pinning the specific finding, (b) filing structured proposals, (c) staying
well under budget (10 calls vs 64 + a budget event).

Across the study, 23/24 reps used `draft_improvement` (rep05 the sole
exception); skill use was broad, not narrow. The skills were discovered and used
without being told to (the prompt only says "you may use available tools or
skills if useful").

### 2.5 The hardest_test (quiet_monday) was NOT cleanly passed
On a desk with nothing urgent, 6/6 reps generated a recurring project
(SUG-001: mitigate the 60/70 engine concentration) plus low-value noise
follow-ups in 4/6 (monitor the 17 healthy refusals; check the reservation pool;
check low effect volume). The supervisor did NOT cleanly say "nothing." BUT
every project was grounded (0 unsupported, 0 conflicts_rule) and it correctly
refused to treat the 17 refusals as exceptions — so the failure mode is the
MILDER one: promoting an established structural fact into a recurring action
item + low-value noise, not inventing unsupported work. The engine-concentration
proposal is grounded_useful (it proposes action beyond the established
measurement, not a restatement of it), so this is not a false alarm about a
non-existent risk — it is a recurring project on a quiet day.

---

## 3. Per-desk verdicts (compressed)

### quiet_monday — hardest_test NOT passed (mild failure mode)
Nothing urgent. 6/6 generated SUG-001 (engine mitigation, grounded_useful) +
grounded_low_value noise in 4/6 (refusal-monitoring, reservation-pool,
low-effect-volume). 2/6 spent a skill call on the RESOLVED exception then
correctly judged it non-urgent. noise_chasing: present/moderate.
story_combination: absent (one repeated structural thesis, no combination).
Tally: grounded_useful 6, grounded_low_value ~6, interesting_new 0-1, no
unsupported, no conflicts_rule.

### messy_tuesday — strong supervision, clearest story_combination
6/6 found the open exception + 3 stale confirmations; 6/6 deprioritized the 17
refusals. reps 2/3/4/5 combined the stale confirmations with the engine
concentration into a compounded-risk thesis ("the stale-confirmed workers sit
in the highest-blast-radius engine") — the clearest story_combination in S13.
noise_chasing: low/absent. One genuine interesting_new (rep02: "correlate
effect-stage stoppages with open exceptions on the dashboard"). "Re-confirm after
promotion" recurred (r01/r02/r06) = duplicate of R-CONFIRM-VERSION.
Tally: grounded_useful ~6, duplicate ~3, requires_human ~10, interesting_new
1 firm + 2 lean, grounded_low_value ~4.

### slow_drift — strongest supervision; the measurement candidate is born
Nothing fails, but refusals rose 17->34 clustered in Acme Oy (3->12). 6/6
surfaced this judgment-call signal WITHOUT reifying the 34 individual refusals
into incidents (the noise_chasing_test, passed). 6/6 correctly read "nothing is
broken." 2/6 (r01, r03) INDEPENDENTLY proposed the SAME novel measurement —
per-customer refusal-rate trending + threshold alerting — which is the oracle's
named `interesting_new_if_suggested` and a direct instance of the learning
principle ("a repeated factual question the supervisor performs by hand ->
measurement candidate"). noise_chasing: low/absent. story_combination:
moderate (r01/r03 combined the drift measurement with the engine canary guard).
Tally: interesting_new 2 firm + 2 lean, grounded_useful ~6, requires_human 5,
grounded_low_value 1.

### mixed_office — strong supervision with one instructive failure
5/6 found both genuinely-worth-attention items (rese-a-inv + enri-a-08 stale);
rep05 is the skill-value outlier (2.4). The resolved exception and the valid
model change were correctly deprioritized; the row-spike noise was flagged 6/6
but at low severity in 5/6. 2 reps (r03, r06) independently proposed a
reservation-cohort permission audit (interesting_new), and 2 (r02, r06) proposed
a confirmation-lag enforcement guard (interesting_new-lean / borderline
duplicate of R-CONFIRM-VERSION). noise_chasing: moderate (row spike flagged
6/6). story_combination: strong in r02/r03/r06. Tally: grounded_useful ~6,
interesting_new 2 firm + 2-3 lean, requires_human ~11 (some low-value),
grounded_low_value ~9.

---

## 4. The interesting_new proposals — Rulebook-experiment material

The secondary product of S13: genuinely observed, grounded, non-established
proposals that can feed the later Rulebook experiment
(real supervision -> genuine suggestion -> improvement proposal -> conflict
check -> proposed rule -> human approval -> ACTIVE). Three survived as
candidates:

1. **Per-customer refusal-rate trending + threshold alerting** (slow_drift
   r01, r03 — repeated independently). Surface a per-customer refusal breakdown
   on the dashboard and alert when a single customer's refusal rate spikes
   disproportionately period-over-period at stable volume. Conflict check
   against R-REFUSAL-NOT-EXCEPTION: the proposal measures the TREND, not
   individual refusals, so it COMPLEMENTS the rule (adds a trend layer the rule
   does not cover) rather than conflicting. **Strongest candidate** — repeated,
   grounded, non-conflicting, and exactly the learning principle's measurement
   candidate.

2. **Reservation-cohort permission audit** (mixed_office r03, r06 — repeated
   independently). Generalize a single open permission exception + a resolved
   one into a cohort-level permission/capability audit across all rese-a-*
   workers, rather than fixing individual workers reactively. Novel workflow
   candidate; no existing rule covers cohort permission audits. Grounded in the
   observed 2-worker pattern.

3. **Effect-stoppage <-> open-exception correlation on the dashboard**
   (messy_tuesday r02). Link effect-not-applied stoppages to open exceptions
   directly on the dashboard surface. Novel dashboard/workflow candidate
   grounded in the observed same-event relationship.

Borderline / enforcement-leaning (interesting_new-lean, carry a duplicate risk
against R-CONFIRM-VERSION because they are the automated enforcement of the
existing version-bound-confirmation rule rather than new rules):

- **Confirmation-lag guard** (mixed_office r02, r06 SUG-003): block or alert
  when a promoted worker's confirmation lags its current version.
- **Engine-concentration promotion gate** (messy_tuesday/slow_drift/mixed_office
  several reps): require canary/staged verification before a change to the
  60/70 shared engine can go fleet-wide.
- **Fleet-share threshold alert** (messy_tuesday r05): flag any dependency
  exceeding e.g. 70% fleet share for architectural review.

---

## 5. Behavioral / methodological observations

- **The dashboard-as-launchpad pattern (2.1)** is the most consistent
  dependent variable in the study: 24/24 empty pre_tool_observation. Whatever
  "cold supervisor" means operationally for this model under this prompt, it
  means "investigate first, narrate after."
- **Skill discovery without instruction.** The prompt only permits skills ("you
  may use ... if useful"); 23/24 used them, and use was broad (most reps on
  every desk touched 4-5 of the 6 skills). `draft_improvement` was used in
  23/24. The skills were not ignored, and not over-used into a ritual.
- **Skill value is causally visible in rep05.** This is the cleanest
  within-desk contrast in the study: the same desk with and without skills
  differs on finding-specificity, proposal-filing, and budget. It is a single
  rep, so it is illustrative not statistical — but it is direct evidence.
- **story_combination tracks desk difficulty.** It was absent on quiet_monday
  (nothing to combine), strong on messy_tuesday and mixed_office (real
  compounded risk), and moderate on slow_drift (drift + structure). The
  supervisor combined observations into a thesis when the desk rewarded it.
- **No unsupported, no conflicts_rule in 24 reps.** Every suggestion was
  grounded in a tool/skill output or an established structural fact; none
  contradicted a Rulebook rule. The failure modes observed are the mild ones
  (quiet-day project generation, low-value noise, one missed finding from
  skipped skills) — not fabrication or rule-conflict.

---

## 6. Limitations

- N=6 per desk, one model, one prompt. This is an observation, not a
  measurement of a population; rep05 is one rep, not a statistic.
- The hand-classification is one human's verdict against the frozen rubric.
  The rubric + ground truth were frozen pre-run; the category boundaries
  (especially duplicate vs interesting_new-lean for the enforcement guards,
  and grounded_low_value vs interesting_new-in-form for the row-spike
  detection) involve judgment and are flagged where so.
- The supervisor did not see the 5 Rulebook rules; "duplicate" and
  "conflicts_rule" are applied post-hoc against rules the supervisor could not
  have known. A duplicate here means "restates an existing rule the system
  already encodes," not "the supervisor did something wrong."
- "pre_tool_observation empty in 24/24" is shaped by the harness turn structure
  (the first assistant turn that contains a python block ends the observation
  window). It is a faithful record of what happened, not a claim that the model
  cannot read a dashboard bare-handed.

---

## 7. Recommended next step

Seed the Rulebook experiment with the strongest S13 interesting_new proposal:
**per-customer refusal-rate trending + threshold alerting** (slow_drift r01/r03).
The path: take the verbatim proposal text from slow_drift run.json, formalize it
as an improvement proposal, run the conflict check against R-REFUSAL-NOT-
EXCEPTION (expected: complements, not conflicts — it measures the trend, not
individual refusals), draft the proposed rule, and route for human approval ->
ACTIVE. This is the first end-to-end instance of the S13 -> Rulebook loop:
real supervision produced a genuine, repeated, grounded suggestion; now the
Rulebook machinery decides whether it becomes a rule.

Secondary candidates (reservation-cohort permission audit; effect-stoppage
<-> exception correlation) are held in reserve.