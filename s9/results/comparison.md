# S9 — comparison: original vs capability-aware candidate
Both variants run WITH the measurement. The only difference is method 2's `statement` (frozen original = "count it yourself"; candidate = "read the measurement, compute only what remains unresolved"). N replicates per cell. Categorical outcome per run: `read` (no re-derivation, identified correctly), `rederive+cite` (re-derived but also cited the measurement), `rederive` (re-derived, did not cite = S8 A behaviour), `other` (failed to identify).

## Fleet A — engine 60/70 concentration
- **original** (n=8): calls mean=1.125 (min 0/max 4), rederive mean=1.125, complement mean=0.0, nameerrors sum=3, cites_meas_rate=0.0, correct_rate=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'rederive': 6, 'read': 2}
- **candidate** (n=8): calls mean=1.0 (min 0/max 4), rederive mean=1.0, complement mean=0.0, nameerrors sum=2, cites_meas_rate=0.375, correct_rate=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'read': 3, 'rederive': 4, 'rederive+cite': 1}

## Fleet D — distributed mirror (safety)
- **original** (n=8): calls mean=1.875 (min 1/max 5), rederive mean=1.75, complement mean=0.125, nameerrors sum=5, cites_meas_rate=0.0, correct_rate=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'rederive': 8}
- **candidate** (n=8): calls mean=1.875 (min 0/max 3), rederive mean=1.875, complement mean=0.0, nameerrors sum=4, cites_meas_rate=0.875, correct_rate=1.0, claims_meas_risk_any=False, interp_llm_all=True, outcomes={'read': 1, 'rederive+cite': 6, 'rederive': 1}
