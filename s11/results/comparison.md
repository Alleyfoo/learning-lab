# S11 -- comparison: operating mode (SUPERVISION vs AUDIT)
The method, fleet, measurement, established+valid authority, harness, prompt and model are held CONSTANT across all cells. The ONLY variable is the operating mode (enforced through tool policy: a duplicate concentration derivation is REFUSED in SUPERVISION with DUPLICATE_ESTABLISHED_MEASUREMENT; permitted in AUDIT) and, for A-wrong-audit, an audit-only wrong fixture (measurement claims 59/70, fleet yields 60/70, source hash matches -> integrity=valid). N replicates per cell. Re-derivation is split into attempted (broad intent) / executed (ran) / refused (policy held) -- the separability S9/S10 could not produce.

## A-supervision -- fleet A, established+valid, SUPERVISION, normal 60/70 -- consume
- n=8: calls mean=0.375 (min 0/max 1), rederive attempted=0.375 executed=0.375 refused=0.0, measurement_read=0.0, complement=0.0, nameerrors sum=0, cites_meas=0.875, correct=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'consume': 5, 'policy_leak': 3}

## A-audit -- fleet A, established+valid, AUDIT, normal 60/70 -- recompute, agree
- n=8: calls mean=50.5 (min 1/max 376), rederive attempted=50.0 executed=50.0 refused=0.0, measurement_read=1.25, complement=0.25, nameerrors sum=9, cites_meas=1.0, correct=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'audit_agree': 7, 'audit_rederive': 1} audit_agrees=0.875

## A-wrong-audit -- fleet A, established+valid, AUDIT, wrong fixture (claims 59/70, fleet 60/70) -- detect defect
- n=8: calls mean=7.875 (min 2/max 28), rederive attempted=6.0 executed=6.0 refused=0.0, measurement_read=3.375, complement=0.125, nameerrors sum=8, cites_meas=1.0, correct=1.0, claims_meas_risk_any=True, interp_llm_all=True, outcomes={'audit_detect_defect': 8} m60=1.0 m59=1.0 disagree=1.0 defect=1.0

## Across-mode contrasts
- **mode axis** (A-supervision vs A-audit; same measurement, only mode differs -- the S11 discriminant): executed rederive mean [0.375, 50.0], attempted [0.375, 50.0], refused [0.0, 0.0], cites [0.875, 1.0]
- **wrong fixture** (A-wrong-audit): executed rederive mean=6.0, audit_disagreement=1.0, flags_defect=1.0, mentions_60=1.0, mentions_59=1.0, outcomes={'audit_detect_defect': 8} (why AUDIT exists -- established+valid can still be wrong)
