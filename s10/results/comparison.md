# S10 -- comparison: measurement authority (established / candidate / invalid)
The S9 capability-aware method is held CONSTANT across all cells. The ONLY variable is the `authority` block on the measurement envelope (status x integrity; integrity computed mechanically via source_snapshot_hash). N replicates per cell. Categorical outcome per run differs by authority state: established -> `read` (consume) / `rederive+cite` / `rederive`; candidate -> `verify` (rederive, correct -- not penalized) / `read`; invalid -> `reject` (rederives AND flags the mismatch) / `trust_invalid` (trusts 60/70 despite integrity=invalid).

## A-established -- fleet A, authority{established, valid} -- consume
- n=8: calls mean=1.5 (min 1/max 3), rederive mean=1.5, measurement_read mean=1.375, authority_read mean=0.0, complement mean=0.0, nameerrors sum=1, cites_meas=1.0, flags_invalid=0.0, treats_authoritative=0.0, correct=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'rederive+cite': 8}

## A-candidate -- fleet A, authority{candidate, unverified} -- verify is reasonable
- n=8: calls mean=1.375 (min 1/max 2), rederive mean=1.375, measurement_read mean=0.875, authority_read mean=0.0, complement mean=0.0, nameerrors sum=1, cites_meas=1.0, flags_invalid=0.0, treats_authoritative=0.5, correct=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'verify': 8}

## A-invalid -- fleet A, authority{established, invalid} -- reject / recompute
- n=8: calls mean=2.875 (min 1/max 6), rederive mean=2.875, measurement_read mean=1.5, authority_read mean=1.375, complement mean=0.0, nameerrors sum=6, cites_meas=1.0, flags_invalid=1.0, treats_authoritative=0.625, correct=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'reject': 8}

## D-established -- fleet D, authority{established, valid} -- mirror: established != risk
- n=8: calls mean=1.375 (min 1/max 4), rederive mean=1.375, measurement_read mean=0.75, authority_read mean=0.0, complement mean=0.0, nameerrors sum=2, cites_meas=0.5, flags_invalid=0.0, treats_authoritative=0.0, correct=1.0, claims_meas_risk_any=True, interp_llm_all=True, outcomes={'rederive+cite': 4, 'rederive': 4}

## Across-authority contrasts (fleet A)
- **status axis** (A-established vs A-candidate; same numbers, only status differs): rederive mean [1.5, 1.375], cites [1.0, 1.0]
- **integrity axis** (A-established vs A-invalid; same status, only integrity differs -- the discriminant): rederive mean [1.5, 2.875], flags_invalid [0.0, 1.0], treats_authoritative [0.0, 0.625]
- **mirror** (D-established): invents_false_concentration_any=False, claims_meas_risk_any=True (both must be False -- established != true)
