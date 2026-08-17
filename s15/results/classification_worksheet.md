# S15 — routing + mandatory-gate classification worksheet

One row per session. `route_chosen` is the filing tool the model called; `expected` is the frozen ground truth (UNCHANGED from S14). `auto_correct` is the NON-authoritative hint (route_chosen == expected_tool). The human verdict (route_correct + sub-outcome notes) goes in FINDINGS.md. `mg_*` = mandatory-gate fields: mg_ran (propose_rule ran the internal duplicate check), mg_caught (it identified a restatement), demoted (the proposal was demoted to DUPLICATE_RULE). Tool calls compressed: tool(keyarg)[ok|FAIL].

## measurement  — expected route MEASUREMENT (file_measurement); emergence 2/24
*S14 result: 6/6 MEASUREMENT  |  S15 prediction: unchanged: 6/6 MEASUREMENT (never enters propose_rule)*

- rep01: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per-customer refusal rate trend, concentration alert threshold, and refusal reason category distribution')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=False  bad=['file_measurement', 'filed: MEASUREMENT; id MEAS-001; metric: per-customer refusal rate trend, concentration alert threshold, and refusal reason category distribution']
- rep02: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; file_measurement(metric='per_customer_refusal_rate')[ok]
    sub: restated=None  conflicts=None  compatible=True  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=4
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep03: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per-customer refusal rate trend, spike-concentration alert, and refusal-reason category distribution')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=False  bad=['file_measurement', 'filed: MEASUREMENT; id MEAS-001; metric: per-customer refusal rate trend, spike-concentration alert, and refusal-reason category distribution']
- rep04: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per-customer refusal rate trend and concentration alert')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=False  bad=['file_measurement', 'filed: MEASUREMENT; id MEAS-001; metric: per-customer refusal rate trend and concentration alert']
- rep05: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

## skill_workflow  — expected route SKILL_WORKFLOW (file_skill); emergence 2/24
*S14 result: 6/6 SKILL_WORKFLOW  |  S15 prediction: unchanged: 6/6 SKILL_WORKFLOW (never enters propose_rule)*

- rep01: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic effect-stage permission gaps')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep02: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic effect-stage permission gaps')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep03: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic effect-stage permission gaps')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep04: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic effect-stage permission gaps')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep05: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic effect-stage permission gaps')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

## duplicate_rule  — expected route DUPLICATE_RULE (file_duplicate_rule); emergence 4/24
*S14 result: 3/6 DUPLICATE_RULE, 3/6 wrongly ACTIVE (misroute to propose_rule)  |  S15 prediction: 0/6 ACTIVE, 6/6 DUPLICATE_RULE -- the mandatory gate catches the restatement before the conflict gate*

- rep01: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep02: route_chosen=propose_rule  expected=file_duplicate_rule  auto_correct=False
    calls: propose_rule(evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their confirmations remained stale — valid for v1 but not re-confirmed for v2 — and the system allowed promotion without invalidating or requiring renewal. S13 independent-emergence count: 4/24.' mg=demoted restates='R-CONFIRM-VERSION')[ok] ; file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their confirmations remained stale — valid for v1 but not re-confirmed for v2 — and the system allowed promotion without invalidating or requiring renewal. S13 independent-emergence count: 4/24.'
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=4
    mg: ran=True  caught=True  demoted=True  restates=R-CONFIRM-VERSION
    canary: no_interpretation=True
- rep03: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep04: route_chosen=propose_rule  expected=file_duplicate_rule  auto_correct=False
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='S13 independent-emergence count: 4/24. Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) promoted v1→v2 this period retained stale v1 confirmations; the system permitted promotion without invalidating or requiring renewal. R-CONFIRM-VERSION establishes the principle that confirmations are version-bound and do not inherit, but specifies no enforcement action when a promoted worker lacks a fresh confirmation.' mg=demoted restates='R-CONFIRM-VERSION')[ok] ; reject_conflict(conflicts='R-PROMOTION-IMMUTABLE')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=R-PROMOTION-IMMUTABLE  compatible=False  evidence='S13 independent-emergence count: 4/24. Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) promoted v1→v2 this period retained stale v1 confirmations; the system permitted promotion without invalidating or requiring renewal. R-CONFIRM-VERSION establishes the principle that confirmations are version-bound and do not inherit, but specifies no enforcement action when a promoted worker lacks a fresh confirmation.'
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=6
    mg: ran=True  caught=True  demoted=True  restates=R-CONFIRM-VERSION
    canary: no_interpretation=True
- rep05: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

## new_rule  — expected route NEW_RULE (propose_rule); emergence 20/24
*S14 result: 6/6 -> ACTIVE  |  S15 prediction: 6/6 still proceeds to ACTIVE (engine rule is novel; duplicate check returns None; lifecycle continues)*

- rep01: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change to that engine can affect the majority of the fleet at once. S13 independent-emergence count: 20/24 supervisors independently raised this concern.' mg=novel)[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change to that engine can affect the majority of the fleet at once. S13 independent-emergence count: 20/24 supervisors independently raised this concern.' mg=novel)[ok] ; propose_rule(evidence='execute_enrichment.py shared by 60/70 workers (85.7%); S13 count 20/24' mg=novel)[ok] ; file_measurement(metric='engine_dependency_concentration_ratio')[ok]
    sub: restated=None  conflicts=None  compatible=True  evidence='execute_enrichment.py shared by 60/70 workers (85.7%); S13 count 20/24'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=13
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep02: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.' mg=novel)[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.' mg=novel)[ok]
    sub: restated=None  conflicts=None  compatible=True  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=9
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep03: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='85.7% fleet share (60/70 workers) depend on a single shared enrichment engine; S13 independent-emergence count 20/24. A single engine change can simultaneously affect the majority of the fleet, bypassing the per-worker isolation that per-model versioning otherwise provides.' mg=novel)[ok] ; propose_rule(evidence='60/70 workers depend on a single shared engine; S13 independent-emergence 20/24. One engine change can affect the majority of the fleet simultaneously.' mg=novel)[ok] ; propose_rule(evidence='60/70 workers share one engine' mg=novel)[ok] ; propose_rule(evidence='60/70 share one engine' mg=novel)[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='60/70 share one engine'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=13
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep04: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); S13 independent-emergence count 20/24. A single engine change can affect the majority of the fleet simultaneously, with no existing rule governing rollout scope or staged verification for shared dependencies.' mg=novel)[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); S13 independent-emergence count 20/24. A single engine change can affect the majority of the fleet simultaneously, with no existing rule governing rollout scope or staged verification for shared dependencies.' mg=novel)[ok] ; propose_rule(evidence='85.7% fleet share (60/70 workers) on execute_enrichment.py; S13 count 20/24. No existing rule covers rollout scope or staged verification for shared dependencies.' mg=novel)[ok] ; propose_rule(evidence='85.7% fleet share; S13 20/24' mg=novel)[ok] ; propose_rule(evidence='85.7% fleet share; S13 20/24' mg=novel)[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='85.7% fleet share; S13 20/24'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=16
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep05: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.' mg=novel)[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=4
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='85.7% fleet share (60/70 workers depend on a single engine); S13 independent-emergence count 20/24; a single engine change can affect the majority of the fleet simultaneously.' mg=novel)[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='85.7% fleet share (60/70 workers depend on a single engine); S13 independent-emergence count 20/24; a single engine change can affect the majority of the fleet simultaneously.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=4
    mg: ran=True  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

## conflicting_probe  — expected route REJECT_CONFLICT (reject_conflict); emergence synthetic-0
*S14 result: 6/6 REJECT_CONFLICT (never active)  |  S15 prediction: unchanged: 6/6 REJECT_CONFLICT (never active)*

- rep01: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep02: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep03: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep04: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep05: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

## compatible_mirror_probe  — expected route DUPLICATE_RULE (file_duplicate_rule); emergence synthetic-0
*S14 result: 6/6 DUPLICATE_RULE  |  S15 prediction: unchanged: 6/6 DUPLICATE_RULE*

- rep01: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep02: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep03: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep04: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep05: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True
- rep06: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    mg: ran=False  caught=False  demoted=False  restates=None
    canary: no_interpretation=True

