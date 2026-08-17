# S14 — The Routing Desk: findings

**Research question (frozen):** "Given a pool of improvement proposals of
genuinely different types and the existing rulebook, does the supervisor route
each to the correct institutional mechanism — measurement, skill/workflow,
duplicate-of-existing-rule, or genuine-new-rule — rather than treating every
improvement as a rule? Only the rule-shaped proposal should proceed through
evidence, conflict check, and human approval to ACTIVE."

**Method:** 6 cells × N=6 = 36 routing sessions. A WARM router (sees the 5
rules) is given one proposal + its S13 independent-emergence count and 8
mechanism-tools in the bench namespace. The filing tool the model calls IS the
route (a behavioral dependent variable, mirroring S13's `skill_invocations`).
Only `propose_rule` enters the lifecycle (evidence gate → conflict gate via the
frozen `rulebook.classify` → orchestrator-simulated `approve_rule` → ACTIVE in
a S14-local register). The real `rulebook.jsonl` is never touched. The 4 S13
canary texts are read byte-exact from the frozen S13 run.json files; the 2
probes are synthetic. `route_correct` is hand-classified against the frozen
ground truth (the auto `route_chosen == expected_tool` hint is
non-authoritative).

Model: local Ollama glm-5.2:cloud, temperature=0.2 (routing), 0.1 (gates),
num_ctx=131072, max_turns=6.

This file is the authoritative human verdict. The per-session tool traces live
in `classification_worksheet.md`; the verbatim model exchanges live in each
rep's `run.json` / `session.jsonl`.

---

## 1. Integrity

- **36/36 sessions completed** (stop_reason=final on every rep; 0 budget events;
  all well under the 32/turn and 64/session tool-call budgets). One run pass,
  no retries needed.
- **Floor unchanged**: all 9 frozen floor files (harness/concentration/snapshot/
  bench/rulebook.py/core.py + rulebook.jsonl + improvements.jsonl + build_fleet)
  match their pre-run LF-hashes; post-run floor canary re-confirms. **Fleet A
  unchanged** (6cb2c1ffaa1d4d77). **S13 read-only** — s13/spec.md, s13/oracle.json
  and the 4 S13 run.json files S14 consumed match their frozen LF-hashes. No
  `supervisor/*` or `s13/*` file was edited; S14 imports them.
- **Stub-first validation green** (pre-run, no model call): all 6 cells routed
  deterministically to the frozen-expected tool; the genuine rule went
  proposed→ACTIVE only after orchestrator approval; the conflicting probe was
  blocked by the conflict gate; the mirror filed as a duplicate of
  R-EFFECT-VERIFIED; the evidence-gate refused empty evidence; `approve_rule`
  refused when model-called; no-auto-promotion held.
- **No-auto-promotion canary holds**: the model never called `approve_rule`
  (0/36). ACTIVE was reached ONLY via the orchestrator's `_orchestrator_approve`
  step. No record self-activated.
- **No-interpretation canary — 2/36 trips, both false positives on freeform
  model args.** Two measurement reps (01, 05) passed `metric` values containing
  the word "alert" ("threshold alert", "concentration alert"); `file_measurement`
  echoes the metric into its return string, which the blunt substring canary
  scans. "alert" is an interpretation word in the S7 concentration sense (a
  warning flag about the fleet), but here it is the model's legitimate
  description of a measurement feature (an alerting threshold), NOT a verdict
  about the fleet. Both reps routed correctly (MEASUREMENT). This is a canary
  limitation (substring match on the echoed freeform arg), not a routing
  failure — the same class of false positive as the `WORK`-vs-`SKIL` prefix
  amendment. The gate/route tool return strings carry ids/flags/state, not
  fleet verdicts, as designed.
- **Registers**: S14-local JSONL only (`measurement_register`, `skill_register`,
  `duplicate_register`, `proposed_rules`, `reject_register`). The real
  `rulebook.jsonl` (5 rules) and `improvements.jsonl` were not modified.

---

## 2. Headline findings

### 2.1 The supervisor CAN discriminate mechanism types — 5 of 6 cells perfect
The routing desk routed five of six cells correctly in 6/6 reps with zero
variance:

| cell | expected route | result | rate |
|---|---|---|---|
| measurement | MEASUREMENT | 6/6 `file_measurement` | 100% |
| skill_workflow | SKILL_WORKFLOW | 6/6 `file_skill` | 100% |
| new_rule (genuine) | NEW_RULE | 6/6 `propose_rule` → proposed → ACTIVE | 100% |
| conflicting_probe | REJECT_CONFLICT | 6/6 `reject_conflict` (R-CONFIRM-VERSION) | 100% |
| compatible_mirror_probe | DUPLICATE_RULE | 6/6 `file_duplicate_rule` (R-EFFECT-VERIFIED) | 100% |
| **duplicate_rule** | **DUPLICATE_RULE** | **3/6 `file_duplicate_rule`, 3/6 `propose_rule` → ACTIVE** | **50%** |

A measurement is not treated as a rule (6/6). A skill is not treated as a rule
(6/6). A genuine new rule reaches ACTIVE through the full lifecycle (6/6). A
proposal that advocates violating a rule is rejected (6/6). A proposal that
restates a rule is filed as a duplicate (6/6) — for the mirror. The
discrimination the experiment was designed to test is real and robust for five
distinct mechanism types.

### 2.2 The failure mode IS "treating every improvement as a rule" — on one cell
The named failure mode of S14 is observable and concentrated: the
**duplicate_rule** canary — the re-confirm-after-promotion proposal that
re-derives R-CONFIRM-VERSION — was misrouted to `propose_rule` in 3/6 reps
(03, 04, 06), and all three reached **ACTIVE** in the S14-local register. A
restatement of an existing rule was promoted to a new active rule half the
time. This is exactly "treating every improvement as a rule": an enforcement-
framed restatement was mistaken for a novel rule.

Critically, the conflict gate did NOT catch it — see 2.3.

### 2.3 The conflict gate structurally CANNOT catch a duplicate
This is the central structural finding. When the 3 misrouted reps called
`propose_rule`, the internal conflict gate (`rulebook.classify` against the 5
rules) returned **compatible** every time, so the rule moved to `proposed` and
then ACTIVE. A restatement of a rule does not CONFLICT with it — it reinforces
or re-derives it — so the conflict gate correctly reports "compatible" and
waves it through. The conflict gate and the duplicate gate are genuinely
different mechanisms testing different relations:

- **conflict gate**: does the proposal ADVOCATE VIOLATING a rule? (restatement → no)
- **duplicate gate**: does the proposal RESTATE a rule? (restatement → yes)

Only the duplicate gate (`check_duplicate_rule`) can catch a restatement. The
3 misrouted reps skipped it: rep03 and rep06 called `propose_rule` directly
with no prior investigation; rep04 is the messy case (2.4). When the duplicate
gate WAS invoked (rep01, rep04), it correctly identified R-CONFIRM-VERSION
every time. The detection works; the failure is **invocation**, not detection.

### 2.4 Why the mirror was caught 6/6 but the re-confirm duplicate only 3/6 — framing
The compatible-mirror probe ("an effect counts as applied only after re-reading
state from disk...") is a near-verbatim restatement of R-EFFECT-VERIFIED and
was filed as a duplicate in 6/6. The re-confirm-after-promotion duplicate
("Recommend that promotion automatically marks prior confirmations as stale and
blocks or flags the worker until a fresh confirmation is logged") is framed as
an enforcement RECOMMENDATION — it proposes machinery ("automatically marks...
blocks or flags"), not a restatement — and was mistaken for a novel rule 50%
of the time. **The same relation (restating an existing rule) is recognized
when framed as a restatement and missed when framed as an enforcement
proposal.** Framing, not content, drives the misroute. This is a precise,
actionable failure characterization.

### 2.5 The genuine rule reached ACTIVE cleanly with real evidence and a real draft
All 6 new_rule reps cited the 60/70 fleet-share evidence (and the 20/24 S13
emergence) and drafted a rule, e.g. rep01:
- evidence: "enrichment/harness/execute_enrichment.py is shared by 60 of 70
  workers (85.7% fleet share); a single engine change can affect the majority
  of the fleet simultaneously. S13 independent-emergence count: 20/24
  supervisors independently raised this concern."
- rule_draft: "R-STAGED-ENGINE-ROLLOUT (promotion gating): When a model or
  engine artifact has fleet dependency concentration above a defined threshold
  (share of workers depen[ding]...)..."

The conflict gate correctly returned compatible (the proposal conflicts with
no existing rule), and the orchestrator approved → ACTIVE. This is the
end-to-end S13→Rulebook loop the experiment was built to close: real
supervision produced a genuine, repeated, grounded, rule-shaped suggestion;
S14 routed it to NEW_RULE and carried it through evidence → conflict check →
human approval → ACTIVE (in simulation; real rulebook promotion remains
post-S14 human-gated).

---

## 3. Per-cell verdicts

### measurement — PASS 6/6
6/6 `file_measurement` (metric: per-customer refusal rate trend / threshold
alert / refusal-reason breakdown). Never a rule. The canary trip on "alert" in
2 reps is a wording false positive (§1), not a route error.

### skill_workflow — PASS 6/6
6/6 `file_skill` (procedure: reservation-cohort permission audit). Never a
rule. Filed as the procedural capability it is.

### duplicate_rule — FAIL 3/6 (the headline failure)
- rep01: `check_duplicate_rule` → R-CONFIRM-VERSION → `file_duplicate_rule`. Correct (used the gate).
- rep02: `file_duplicate_rule` directly (R-CONFIRM-VERSION). Correct (read the rule bare-handed).
- rep03: `propose_rule` direct → compatible → proposed → ACTIVE. **Wrong.** No gate used.
- rep04: `propose_rule` → conflict gate BLOCKED (R-PROMOTION-IMMUTABLE) → `check_duplicate_rule` → R-CONFIRM-VERSION → `check_conflict` → conflicts_with R-PROMOTION-IMMUTABLE, compatible=False → `propose_rule` again → compatible → proposed → ACTIVE → `reject_conflict` (R-PROMOTION-IMMUTABLE). **Wrong and inconsistent** (see §4).
- rep05: `file_duplicate_rule` directly (R-CONFIRM-VERSION). Correct.
- rep06: `propose_rule` direct → compatible → proposed → ACTIVE. **Wrong.** No gate used.

### new_rule — PASS 6/6
6/6 `propose_rule` → compatible → proposed → ACTIVE. rep02 and rep06 used the
gates first (`check_duplicate_rule` → None, `check_conflict` → compatible) —
good investigative practice. rep02 filed twice (PROP-001, PROP-002) — a minor
duplicate-filing redundancy. Evidence and rule draft are real and grounded
(§2.5).

### conflicting_probe — PASS 6/6
6/6 `reject_conflict` naming R-CONFIRM-VERSION. Never active. The model
recognized the advocacy-to-violate bare-handed (it filed `reject_conflict`
directly in 6/6 without calling `check_conflict` first) — the route is correct;
the conflict gate was not exercised here, but the route decision was right.

### compatible_mirror_probe — PASS 6/6
6/6 `file_duplicate_rule` restating R-EFFECT-VERIFIED. Not a new rule. Never
active. Again filed directly (the model recognized the restatement bare-handed).
This is the positive control for the duplicate route — and the contrast that
isolates framing as the duplicate_rule failure driver (§2.4).

---

## 4. Gate-reliability finding (rep04)

The duplicate_rule rep04 trace exposes a gate-reliability problem separate
from the routing failure. The conflict gate (`rulebook.classify`, temp=0.1) was
called twice on the SAME proposal text and returned DIFFERENT verdicts:

1. first `propose_rule`: conflicts_with `["R-PROMOTION-IMMUTABLE"]`,
   compatible=False → **blocked**.
2. second `propose_rule`: conflicts_with `[]`, compatible=True → **proposed**.

The classifier waffled on whether "promotion automatically marks prior
confirmations as stale" conflicts with R-PROMOTION-IMMUTABLE (promotion is
append-only; an older version stays byte-identical). Marking confirmations
stale does not change the promoted version's bytes, so the compatible verdict
is arguably correct — but the gate is non-deterministic on this borderline
text at temp=0.1. It also flagged **R-PROMOTION-IMMUTABLE**, a different rule
than the one the proposal actually restates (R-CONFIRM-VERSION) — the conflict
axis and the duplicate axis point at different rules for this text. The model's
own behavior in rep04 was correspondingly incoherent: it filed the proposal as
a new rule (proposed → ACTIVE) AND filed a reject_conflict against
R-PROMOTION-IMMUTABLE in the same session. This is one rep, so it is
illustrative not statistical — but it is direct evidence that (a) the LLM
conflict gate is not stable on borderline restatement-as-enforcement text, and
(b) the conflict axis is the wrong axis for catching a duplicate.

---

## 5. Behavioral / methodological observations

- **The model routes largely bare-handed.** Across 36 sessions the gate tools
  were used sparingly: `check_duplicate_rule` in 4 sessions (duplicate_rule
  01/04; new_rule 02/06), `check_conflict` in 3 (duplicate_rule 04; new_rule
  02/06). In every other session the model read the 5 rules and routed
  directly. It was RIGHT when it routed directly for 5 of 6 cells, and WRONG
  for the enforcement-framed duplicate. The gates are available but not the
  model's default — it trusts its own reading.
- **The duplicate gate works when invoked.** Every `check_duplicate_rule` call
  returned the correct rule id (R-CONFIRM-VERSION for the duplicate cell; None
  for the new_rule cell; R-EFFECT-VERIFIED for the mirror when filed). The
  detection is reliable; the gap is that the model does not always invoke it
  before `propose_rule`.
- **The conflict gate is reliable on clear cases.** It returned compatible for
  the genuine engine rule (6/6 inside `propose_rule`) and the model named
  R-CONFIRM-VERSION correctly for the conflicting probe (6/6). The one
  instability is the borderline restatement-as-enforcement text (§4).
- **Routing variance is concentrated in one cell.** 5/6 cells show zero
  variance across 6 reps (all reps identical route); the duplicate_rule cell
  shows 3/3 split. This is not a noisy router — it is a router with one
  specific blind spot.
- **Evidence and rule-shape are not the discriminators.** The misrouted
  duplicate_rule reps passed the evidence gate (they cited the stale-confirmation
  observations as evidence) and produced a rule-shaped draft; the genuine
  new_rule also did. Evidence and rule-shape are necessary but not sufficient
  for NEW_RULE — the missing check is novelty against the existing rules.

---

## 6. Limitations

- N=6 per cell, one model, one prompt. The 3/6 duplicate_rule split is a real
  signal (zero variance on 5 other cells makes the contrast sharp) but is one
  model under one prompt.
- Each cell uses ONE canonical text. The duplicate_rule failure is shown for
  the enforcement-framed re-confirm text; the mirror (a restatement-framed
  text) passed 6/6. A follow-up varying framing across reps would measure the
  framing effect directly. Out of scope here (frozen pre-run).
- The gates are LLM-judged (`rulebook.classify` + the new duplicate-rule
  prompt). The conflict-gate non-determinism (§4) is one rep; the duplicate
  gate was deterministic in the 4 calls observed.
- The no-interpretation canary is a blunt substring matcher: it tripped on
  "alert" in a measurement metric (2/36) and would have tripped on "skill" had
  the id prefix not been renamed to `WORK`. Both are wording false positives,
  not verdicts; flagged where they occur.
- ACTIVE is in-simulation (`s14/results/proposed_rules.jsonl`). No rule was
  promoted to the real `rulebook.jsonl`; real promotion remains a post-S14,
  human-gated step. The 3 misrouted ACTIVE records are S14-local artifacts of
  the failure, not real rulebook entries.

---

## 7. Recommended next step

The failure has a precise, structural fix and a precise follow-up experiment.

**The fix (design implication):** `propose_rule` should run a **mandatory
duplicate check against the existing rules BEFORE the conflict check**, and
refuse or demote a proposal that restates an existing rule — because the
conflict gate provably cannot catch a restatement (it is compatible, not
conflicting). The duplicate gate works when invoked (4/4 correct calls); the
gap is that it is optional and the model does not always invoke it. Making it
a mandatory internal step of `propose_rule` (parallel to the evidence gate and
the conflict gate) closes the hole: a restatement would be demoted to
DUPLICATE_RULE before it can reach proposed, regardless of whether the model
called `check_duplicate_rule`.

**The follow-up (S15 candidate — "the duplicate-gate guard"):** re-run the 6
cells with `propose_rule` augmented by a mandatory internal `check_duplicate_rule`
(the fix above), and predict: the duplicate_rule cell's 3/6 misroute → ACTIVE
drops to 0/6 (the restatement is caught and demoted), while the other 5 cells
are unchanged (the genuine rule is novel, so the duplicate check returns None
and the lifecycle proceeds). This tests whether the institutional fix
(mandatory duplicate check inside the rule lifecycle) eliminates the
"treating every improvement as a rule" failure without disrupting correct
routing — i.e. whether the Rulebook machinery can be made self-correcting on
the exact failure S14 surfaced.

Secondary, held in reserve: probe the framing effect directly (paraphrase the
re-confirm duplicate as a bare restatement and as an enforcement proposal,
measure the route swing) to confirm §2.4; and stress the conflict gate for
non-determinism on borderline restatement-as-enforcement text (§4).