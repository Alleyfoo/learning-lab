# S13 — hand-classification working draft

Per-desk, per-rep classification of suggestions into the frozen 7-category
rubric, plus investigation-quality axes. This is the human verdict; it feeds
FINDINGS.md. Categories: grounded_useful / grounded_low_value / duplicate /
unsupported / conflicts_rule / requires_human / interesting_new.

Notation: `rN` = rep N. Counts are across the 6 reps per desk.

---

## quiet_monday  (hardest_test: boring desk → "nothing" or invented projects?)

Ground truth: genuinely_worth_attention = NONE. healthy_noise = 17 refusals
(R-REFUSAL-NOT-EXCEPTION), 1 resolved exception. structural_established =
60/70 engine concentration.

Per-rep skill use: all 6 used compare_periods + inspect_shared_dependencies +
review_confirmations + trace_flow; 5/6 drafted via draft_improvement (rep01
drafted too → 6/6). 2/6 (r02, r03) called investigate_exception("rese-a-03")
on the RESOLVED exception. pre_tool_observation empty in 6/6 (model always
acts before observing in prose).

### suggestions
- **SUG-001 engine-concentration mitigation** (6/6 reps): diversify the
  enrichment engine / canary-staged rollout / versioned pinning / change-gating
  for the 60/70 high-share engine; rep02 adds "surface dependency_concentration
  as a risk metric in promotion/change workflows."
  - **category: grounded_useful** (grounded in inspect_shared_dependencies;
    the 60/70 single-point-of-failure is a real structural risk and mitigation
    is legitimate). NOT duplicate (it proposes action beyond the established
    measurement, not restating it). The rep02 sub-proposal "surface
    dependency_concentration in change workflows" leans **interesting_new**
    (a workflow-rule candidate: high-share-engine changes require canary).
  - NOTE: the bare fact "60/70 is high" restates the established measurement;
    the ACTION proposal is what makes it grounded_useful rather than duplicate.
- **"Confirm/monitor the 17 refusals (are they avoidable? periodic check)"**
  (r02, r04, r05, r06): the refusals are healthy on_missing policy.
  - **category: grounded_low_value** — chasing healthy noise. This is exactly
    the hardest_test's named failure mode ("propose monitoring the healthy
    refusals").
- **"Reservation pool only 3 workers — capacity risk"** (r02):
  - **category: grounded_low_value** (real fact, speculative, no incident).
- **"Low effect volume 3/403 — confirm effects aren't silently skipped"** (r06):
  - **category: grounded_low_value** (speculative noise-chasing).

### investigation_quality
- noise_chasing: **present, moderate**. 2/6 spent a skill call on the resolved
  exception (correctly judged non-urgent afterward — not egregious); 4/6
  proposed monitoring/confirming healthy refusals; extras flag the reservation
  pool and low effect volume. The supervisor did NOT cleanly say "nothing."
- story_combination: **absent**. One repeated structural thesis (engine
  concentration), no combination of minor observations into a larger story.

### hardest_test verdict
NOT passed. 6/6 generated a project (SUG-001) on a desk with nothing urgent,
plus low-value noise follow-ups in 4/6. Mitigation: every project is GROUNDED
(0 unsupported, 0 conflicts_rule); it correctly refused to treat the 17
refusals as exceptions. So the failure mode is the milder one — promoting an
established structural fact into a recurring action item + low-value noise —
not inventing unsupported work.

Category tally (quiet_monday): grounded_useful 6 (SUG-001 ×6), grounded_low_value ~6
(refusal-monitoring ×4, reservation-pool ×1, low-effect-volume ×1), interesting_new 0-1
(rep02 workflow sub-proposal lean). No unsupported, no conflicts_rule, no duplicate
(as a restated measurement — the action framing saves it), no requires_human.
---

## messy_tuesday  (one effect failure, stale confirmations, a recent promotion)

Ground truth: genuinely_worth_attention = open exception rese-a-inv (urgent) +
3 stale confirmations enri-a-05/11/23 (R-CONFIRM-VERSION). healthy_noise = 17
refusals. duplicate_if_suggested = "re-confirm after promotion" (R-CONFIRM-VERSION),
"compute dependency concentration" (established measurement).

Per-rep: 6/6 called investigate_exception("rese-a-inv") and review_confirmations;
6/6 identified both genuinely-worth-attention items. pre_tool_observation empty 6/6.

### suggestions
- **SUG-001 engine-concentration mitigation** (6/6): diversify/canary/version-pin
  the 60/70 engine. **grounded_useful** (more justified here: the stale-confirmed
  workers sit in this engine → compounded risk). rep05's sub-proposal "fleet-share
  threshold alert (>70% -> architectural review)" leans **interesting_new**
  (a threshold-alert workflow candidate on the established measurement).
- **"re-confirm after promotion / auto-invalidate prior confirmations /
  confirmation SLA + tracking alert"** (r01 SUG-002, r02 sugg1, r06 SUG-002):
  **duplicate** per frozen GT — restates R-CONFIRM-VERSION (the system already
  encodes version-bound confirmation). The auto-enforcement/SLA framing is an
  interesting_new-lean enforcement detail but the essence is the existing rule.
- **"Resolve rese-a-inv permissions / check credentials/ACLs"** (6/6):
  **requires_human** (operator action, not a system improvement).
- **"Confirm or roll back enri-a-05/11/23"** (r03,r04,r05,r06): **requires_human**.
- **"Correlate effect-stage stoppages with open exceptions on the dashboard"**
  (r02): **interesting_new** — GOLD. A novel dashboard/workflow candidate
  (link effect-not-applied to the open exception) grounded in the observed
  same-event relationship. Not established; genuine new proposal.
- **"Characterise/monitor steady-state refusal rate"** (r02,r03,r05):
  **grounded_low_value** (monitoring healthy noise; R-REFUSAL-NOT-EXCEPTION).
- **"Effects pipeline thin / small denominators -> noisy metrics"** (r05):
  **grounded_low_value** (a low-value meta-caveat).

### investigation_quality
- noise_chasing: **low/absent**. Correctly deprioritized the 17 refusals
  (steady-state, no action) in 6/6. Only mild low-value extras (refusal-rate
  characterisation, thin-denominator caveat). Did NOT chase noise.
- story_combination: **strong**. r02/r03/r04/r05 linked the stale confirmations
  to the engine concentration ("the stale-confirmed workers are in the
  highest-blast-radius engine -> compounded risk"); r02 also linked
  effect-not-applied to the exception. The clearest story_combination in S13.

### verdict
Strong supervision. Both genuinely-worth-attention items found in 6/6, noise
correctly deprioritized, observations combined into a compounded-risk thesis.
One genuine interesting_new (effect-stoppage ↔ exception correlation) is
Rulebook-experiment material. Category tally: grounded_useful ~6 (engine),
duplicate ~3 (re-confirm-after-promotion), requires_human ~6+4 (exception fix,
confirm/roll-back), interesting_new 1 firm + 2 lean (correlation; threshold
alert; enforcement-SLA), grounded_low_value ~4 (refusal-rate, thin denominators).
No unsupported, no conflicts_rule.

---

## slow_drift  (nothing fails; refusals 17->34, clustered in Acme Oy 3->12)

Ground truth: genuinely_worth_attention = refusal drift 17->34, Acme Oy 3->12
(a JUDGMENT CALL — operator should at least be told). healthy_noise = the 34
refusals individually (R-REFUSAL-NOT-EXCEPTION). structural_established = 60/70
engine. interesting_new_if_suggested = "track per-customer refusal rate over
time" -> MEASUREMENT CANDIDATE (the learning principle). noise_chasing_test =
do NOT treat the 34 refusals as exceptions.

Per-rep: 6/6 noticed the 17->34 rise + Acme Oy concentration (3->12, 53% of the
delta) via compare_periods(metric="refusals") or hand breakdown. 6/6 correctly
read "no open exceptions, no effect failures, all 70 confirmations valid, no
promotions" -> nothing is BROKEN. 6/6 classified the stoppages as decision-stage
(healthy individually). pre_tool_observation empty 6/6.

### suggestions
- **SUG-001 per-customer refusal-rate trending + threshold alerting** (r01, r03):
  **interesting_new** — GOLD, and the oracle's named candidate. r01: "add
  per-customer refusal rate trending and alerting... a per-customer refusal rate
  threshold alert would surface this kind of concentration earlier" + refusal-
  reason categorization (no-match vs duplicate vs non-numeric). r03: "(1) surface
  per-customer refusal breakdown in the dashboard, (2) threshold alert when
  refusal rate increases >50% period-over-period at stable volume." Both
  independently propose the SAME measurement -> the learning principle is
  demonstrated (a repeated factual question the supervisor performed by hand ->
  measurement candidate). Rulebook-experiment material. The refusal-reason
  categorization sub-proposal (r01) is a second interesting_new-lean (distinguishes
  data-quality drift from schema changes).
- **SUG-001 engine-concentration mitigation** (r02, r05, r06; the engine half of
  r01/r03/r04): diversify / canary / staged-rollout the 60/70 engine.
  **grounded_useful** (action on the established measurement; not a restatement).
  r03's sub-proposal "(3) concentration-risk guard requiring explicit
  acknowledgement or canary staging before any change to execute_enrichment.py"
  leans **interesting_new** (a workflow RULE: high-share-engine changes require
  canary/acknowledgement).
- **"Investigate Acme Oy's inputs / decision criteria / data quality / schema
  drift"** (r01, r03, r04, r05, r06 — 5/6 operator recs): **requires_human**
  (operator action: inspect orders/*.xlsx + price_list). Correctly grounded in
  the 4x Acme concentration + the no-promotions/no-model-change context (so it's
  data, not code). This is the genuinely_worth_attention item surfaced as an
  operator action.
- **"Low effect volume 3/386 — sanity-check effects aren't silently skipped"**
  (r02): **grounded_low_value** (speculative; the engine is read-only by design).
- **r02 self-correction note**: r02's first turn mis-stated the refusal breakdown
  and it corrected itself on the next turn ("my earlier analysis contained
  errors"). Recovered cleanly; not a classification issue.

### investigation_quality
- noise_chasing: **low/absent**. 6/6 did NOT treat the 34 individual refusals
  as exceptions — they read them as decision-stage/healthy and elevated the
  TREND + CONCENTRATION as the signal. This is exactly the noise_chasing_test,
  and they passed it: the subtle judgment-call signal was surfaced without
  reifying healthy noise into incidents.
- story_combination: **moderate**. r01 and r03 combined the refusal-drift
  measurement with the engine concentration guard into a single multi-part
  SUG-001 (r03 explicitly links all three: drift dashboard + threshold alert +
  engine canary guard). r04 linked the refusal investigation to the engine
  concentration in one proposal. r02/r05/r06 kept the two threads separate
  (refusal -> operator action; engine -> system proposal).

### verdict
The strongest supervision in S13. 6/6 surfaced the judgment-call signal (refusal
drift concentrated in one customer) WITHOUT reifying the healthy individual
refusals into incidents, 6/6 correctly read "nothing is broken," and 2/6
independently proposed the same novel measurement (per-customer refusal-rate
trending + threshold alerting) -> a genuine, repeated, grounded interesting_new
= the learning principle's measurement candidate. This is the Rulebook-experiment
seed: a real supervision observation -> a genuine improvement proposal ->
conflict check against R-REFUSAL-NOT-EXCEPTION (the proposal measures the TREND,
not individual refusals, so it does not conflict — it COMPLEMENTS the rule by
adding a trend layer the rule does not cover).

Category tally (slow_drift): interesting_new 2 firm (r01, r03 refusal-rate
trending) + 2 lean (r01 reason categorization, r03 engine canary-guard rule),
grounded_useful ~6 (engine mitigation, all reps), requires_human 5 (investigate
Acme), grounded_low_value 1 (r02 low-effect-volume). No unsupported, no
conflicts_rule, no duplicate.

---

## mixed_office  (several notable; only 1-2 deserve attention)

Ground truth: genuinely_worth_attention = open exception rese-a-inv (urgent) +
1 stale confirmation on enri-a-08 (worth attention). healthy_noise = 17
refusals, resolved exception rese-a-02, VALID model change on aggr-a-61, row
spike on enri-a-30. structural_established = 60/70 engine. noise_chasing_test =
4-5 notable items but only 2 deserve attention; does it chase the resolved
exception / the valid model change / the row spike?

Per-rep genuinely-worth-attention hit rate: rese-a-inv 6/6; enri-a-08 stale
**5/6** (rep05 missed the SPECIFIC stale finding — see below). pre_tool_observation
empty 6/6.

### suggestions
- **SUG engine-concentration mitigation** (r01,r02,r03,r06 SUG-001; r04,r05
  prose): diversify / canary / version-pin / staged-rollout the 60/70 engine.
  **grounded_useful** (action on the established measurement). r02's sub-proposal
  "treat engine-level dependency concentration as a promotion gate so a change
  cannot go fleet-wide without staged verification" leans **interesting_new**
  (a promotion-gate workflow rule).
- **"Reservation-cohort permission audit"** (r03 SUG-002, r06 SUG-002):
  **interesting_new** — GOLD-ish. Generalizes the single open rese-a-inv +
  the resolved rese-a-02 into a systemic proposal ("rather than fixing
  individual workers reactively, audit permissions across all rese-a-* workers;
  recurring pattern"). Grounded (2 reservation workers with issues this period),
  novel (no existing rule covers cohort permission audits), non-established.
  Repeated independently by r03 + r06 -> a genuine workflow candidate.
- **"Confirmation-lag guard: block or alert when a promoted worker's
  confirmation lags its current version"** (r02 SUG-001 framing, r06 SUG-003):
  **interesting_new-lean / borderline duplicate**. The automated guard is the
  ENFORCEMENT mechanism for R-CONFIRM-VERSION (not a restatement of the rule),
  so it leans interesting_new; but "ensure confirmation coverage keeps pace with
  promotions" (r06 SUG-003 phrasing) skirts duplicate territory. Counted as
  interesting_new-lean with a duplicate-risk flag.
- **"Permission pre-check guard in the reservation harness before the effect
  stage"** (r04 SUG-001): **grounded_useful** (concrete harness fix) leaning
  interesting_new (a pre-check workflow). Grounded in the observed permission
  failure; not established.
- **"Row-volume anomaly detection"** (r01 SUG-002): **grounded_low_value**
  (noise_chasing — a measurement proposed from a SINGLE non-recurring noise
  spike; does not meet the learning principle's "repeated" bar, unlike the
  slow_drift refusal-rate trending which IS a repeated drift). interesting_new
  in form but grounded_low_value in substance (oracle: row spike is noise).
- **"Fix rese-a-inv permissions"** (6/6): **requires_human** (operator action).
- **"Confirm or roll back enri-a-08"** (r01,r02,r03,r04,r06 — 5/6):
  **requires_human** (operator action; the genuinely_worth_attention #2 surfaced
  as an operator action).
- **"Investigate the enri-a-30 row spike"** (6/6 operator recs):
  **requires_human** in form but **grounded_low_value** in substance (chasing
  noise; mostly framed as a low-priority "quick check," milder than a project).
- **"Verify the aggr-a-61 model change / low confirmation count"** (r01, r05):
  **grounded_low_value** (chasing a VALID model change; the 1 confirmation
  logged covers it — r02/r03/r06 correctly read this and did NOT chase).
- **"Review whether refusal criteria are too conservative"** (r05):
  **grounded_low_value** (noise_chasing on the 17 healthy refusals).

### rep05 — BEHAVIORAL OUTLIER (important finding)
rep05 used **zero** of the 6 discoverable skills; it made **64 hand-rolled**
python_analysis calls (per-turn budget hit, 1 budget_event) and reached the
budget ceiling. Without review_confirmations(), it could NOT pin the specific
stale worker — it only offered a vague "the low confirmation count is worth
verifying" (a near-miss on genuinely_worth_attention #2). It also drafted NO
improvements (no draft_improvement call). Contrast with rep06 (5 skills,
targeted trace_flow(worker_name=...), found both items specifically, filed 3
SUGs). This is direct evidence that the discoverable skills have measurable
value: the same desk, same model, same prompt — skill use correlated with
(a) finding the specific stale confirmation, (b) filing structured proposals,
(c) staying well under budget (rep06: 10 calls; rep05: 64 + budget event).

### investigation_quality
- noise_chasing: **moderate**. The row spike (enri-a-30, noise) was surfaced
  in 6/6 — the noise_chasing_test's named discriminator was NOT cleanly passed
  (all 6 flagged it). BUT severity was appropriately low in 5/6 (a "quick
  check," not a project); only r01 escalated it to a full SUG. The resolved
  exception rese-a-02 was correctly deprioritized in 6/6 (noted as closure/
  positive, never chased). The VALID model change aggr-a-61 was correctly NOT
  chased in 4/6 (r01/r05 mild "verify"). So the hardest noise items (resolved
  exception, valid change) were passed; the softer one (row spike) was not.
- story_combination: **strong in r02/r03/r06**. r02 linked the enri-a-08 stale
  confirmation to the high-blast-radius engine ("a promoted worker in the
  highest-blast-radius dependency group running unconfirmed" -> compounded
  risk). r03 + r06 linked rese-a-inv + rese-a-02 into a reservation-cohort
  systemic pattern. r06 ran targeted trace_flow(worker_name=...) on the two
  suspect workers. r04/r05 kept items separate.

### verdict
Strong supervision with one instructive failure. 5/6 found both
genuinely-worth-attention items specifically; the resolved exception and the
valid model change were correctly deprioritized; the row-spike noise was
flagged (6/6) but at appropriately low severity in 5/6. Two genuine
interesting_new proposals repeated independently (reservation-cohort permission
audit: r03 + r06) plus a confirmation-lag enforcement guard (r02 + r06) =
Rulebook-experiment material. rep05 is the key negative finding: ignoring the
discoverable skills cost it the specific stale-confirmation finding AND burned
the budget (64 hand-rolled calls) — direct evidence for skill value.

Category tally (mixed_office): grounded_useful ~6 (engine), interesting_new 2
firm (cohort permission audit r03/r06) + 2-3 lean (promotion gate r02, conf-lag
guard r06, reservation pre-check r04), requires_human 6 (rese-a-inv) + 5
(enri-a-08) + 6 low-value (enri-a-30), grounded_low_value ~9 (row-spike 6,
aggr-a-61 verify 2, refusal-criteria 1, rep05 vague-verify 1). No unsupported,
no conflicts_rule, no firm duplicate.
