# S14 — routing classification worksheet

One row per session. `route_chosen` is the filing tool the model called; `expected` is the frozen ground truth. `auto_correct` is the NON-authoritative hint (route_chosen == expected_tool). The human verdict (route_correct + sub-outcome notes) goes in FINDINGS.md. Tool calls are compressed: tool(keyarg)[ok|FAIL].

## measurement  — expected route MEASUREMENT (file_measurement); emergence 2/24

- rep01: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per-customer refusal rate trend with threshold alert; refusal reason category distribution (no-match / duplicate-match / non-numeric)')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=False  bad=['file_measurement', 'filed: MEASUREMENT; id MEAS-001; metric: per-customer refusal rate trend with threshold alert; refusal reason category distribution (no-match / duplicate-match / non-numeric)']
- rep02: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate_trend')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep03: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep04: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep05: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per-customer refusal rate trend and concentration alert, with refusal-reason breakdown')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=False  bad=['file_measurement', 'filed: MEASUREMENT; id MEAS-001; metric: per-customer refusal rate trend and concentration alert, with refusal-reason breakdown']
- rep06: route_chosen=file_measurement  expected=file_measurement  auto_correct=True
    calls: file_measurement(metric='per_customer_refusal_rate_trend')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True

## skill_workflow  — expected route SKILL_WORKFLOW (file_skill); emergence 2/24

- rep01: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep02: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep03: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep04: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep05: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep06: route_chosen=file_skill  expected=file_skill  auto_correct=True
    calls: file_skill(procedure='Targeted permission/capability audit across all reservation workers to identify systemic gaps in effect-stage permissions, triggered by two reservation workers hitting effect-stage issues (rese-a-02 resolved, rese-a-inv open with PermissionError on append_to_reservations).')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True

## duplicate_rule  — expected route DUPLICATE_RULE (file_duplicate_rule); emergence 4/24

- rep01: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: check_duplicate_rule()[ok] ; file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=5
    canary: no_interpretation=True
- rep02: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep03: route_chosen=propose_rule  expected=file_duplicate_rule  auto_correct=False
    calls: propose_rule(evidence='enri-a-05, enri-a-11, enri-a-23 promoted v1→v2 this period; system permitted operation under stale (v1) confirmations without invalidation or renewal requirement. S13 independent-emergence count: 4/24.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='enri-a-05, enri-a-11, enri-a-23 promoted v1→v2 this period; system permitted operation under stale (v1) confirmations without invalidation or renewal requirement. S13 independent-emergence count: 4/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True
- rep04: route_chosen=propose_rule  expected=file_duplicate_rule  auto_correct=False
    calls: propose_rule(evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their v1 confirmations remained un-invalidated; the system allowed promotion without requiring renewal. S13 independent-emergence count: 4/24.')[FAIL] ; check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their v1 confirmations remained un-invalidated; the system allowed promotion without requiring renewal. S13 independent-emergence count: 4/24.')[ok] ; reject_conflict(conflicts='R-PROMOTION-IMMUTABLE')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=R-PROMOTION-IMMUTABLE  compatible=False  evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their v1 confirmations remained un-invalidated; the system allowed promotion without requiring renewal. S13 independent-emergence count: 4/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=8
    canary: no_interpretation=True
- rep05: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-CONFIRM-VERSION')[ok]
    sub: restated=R-CONFIRM-VERSION  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep06: route_chosen=propose_rule  expected=file_duplicate_rule  auto_correct=False
    calls: propose_rule(evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their v1 confirmations were not re-confirmed for v2, yet the system allowed promotion without invalidating or requiring renewal. S13 independent-emergence count: 4/24.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='Three enrichment workers (enri-a-05, enri-a-11, enri-a-23) were promoted from v1 to v2 this period. Their v1 confirmations were not re-confirmed for v2, yet the system allowed promotion without invalidating or requiring renewal. S13 independent-emergence count: 4/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True

## new_rule  — expected route NEW_RULE (propose_rule); emergence 20/24

- rep01: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single engine change can affect the majority of the fleet simultaneously. S13 independent-emergence count: 20/24 supervisors independently raised this concern.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single engine change can affect the majority of the fleet simultaneously. S13 independent-emergence count: 20/24 supervisors independently raised this concern.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True
- rep02: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); S13 independent-emergence count 20/24; a single engine change can affect the majority of the fleet at once.')[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); S13 independent-emergence count 20/24; a single engine change can affect the majority of the fleet at once.')[ok]
    sub: restated=None  conflicts=None  compatible=True  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); S13 independent-emergence count 20/24; a single engine change can affect the majority of the fleet at once.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=7
    canary: no_interpretation=True
- rep03: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True
- rep04: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24 supervisors independently raised this concern.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24 supervisors independently raised this concern.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True
- rep05: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: propose_rule(evidence='85.7% fleet share (60/70 workers depend on a single shared engine). S13 independent-emergence count: 20/24 supervisors independently raised this concern. A single engine change can affect the majority of the fleet simultaneously, creating correlated-failure risk that no existing rule addresses.')[ok]
    sub: restated=None  conflicts=None  compatible=None  evidence='85.7% fleet share (60/70 workers depend on a single shared engine). S13 independent-emergence count: 20/24 supervisors independently raised this concern. A single engine change can affect the majority of the fleet simultaneously, creating correlated-failure risk that no existing rule addresses.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=3
    canary: no_interpretation=True
- rep06: route_chosen=propose_rule  expected=propose_rule  auto_correct=True
    calls: check_duplicate_rule()[ok] ; check_conflict()[ok] ; propose_rule(evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.')[ok]
    sub: restated=None  conflicts=None  compatible=True  evidence='enrichment/harness/execute_enrichment.py is shared by 60 of 70 workers (85.7% fleet share); a single change can affect the majority of the fleet at once. S13 independent-emergence count: 20/24.'
    life: reached_proposed=True  reached_active=True  called_approve_rule=False  stop=final  ollama_calls=5
    canary: no_interpretation=True

## conflicting_probe  — expected route REJECT_CONFLICT (reject_conflict); emergence synthetic-0

- rep01: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep02: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep03: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep04: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep05: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep06: route_chosen=reject_conflict  expected=reject_conflict  auto_correct=True
    calls: reject_conflict(conflicts='R-CONFIRM-VERSION')[ok]
    sub: restated=None  conflicts=R-CONFIRM-VERSION  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True

## compatible_mirror_probe  — expected route DUPLICATE_RULE (file_duplicate_rule); emergence synthetic-0

- rep01: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep02: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep03: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep04: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep05: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True
- rep06: route_chosen=file_duplicate_rule  expected=file_duplicate_rule  auto_correct=True
    calls: file_duplicate_rule(restates='R-EFFECT-VERIFIED')[ok]
    sub: restated=R-EFFECT-VERIFIED  conflicts=None  compatible=None  evidence=None
    life: reached_proposed=False  reached_active=False  called_approve_rule=False  stop=final  ollama_calls=2
    canary: no_interpretation=True

