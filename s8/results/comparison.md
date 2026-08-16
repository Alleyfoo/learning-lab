# S8 -- composition: METHOD x MEASUREMENT (call MIX, not just count)

> METHOD-only = full S5 memory, no measurement.  MEASUREMENT-only = COLD, measurement+contract attached.  METHOD+MEASUREMENT = full memory AND measurement+contract.
> The headline is the CALL MIX: rederive (re-computes the concentration by hand) / read (uses the precomputed measurement) / complementary (task/customer/investigation) / probe. Non-authoritative; FINDINGS.md is authoritative.

## fleet A -- dominant: engine 60/70

| condition | calls | turns | rederive | read | complement | probe | failed | nameerr |
|---|---|---|---|---|---|---|---|---|
| METHOD-only | 3 | 2 | 3 | 0 | 0 | 0 | 2 | 2 |
| MEASUREMENT-only | 9 | 3 | 8 | 0 | 1 | 0 | 7 | 7 |
| METHOD+MEASUREMENT | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 |

### fleet A -- response hints

| condition | cites_measurement | interpretation_llm | claims_meas_risk | A:identifies / D:no-false-conc |
|---|---|---|---|---|
| METHOD-only | False | True | False | True |
| MEASUREMENT-only | False | True | False | True |
| METHOD+MEASUREMENT | False | True | False | True |

## fleet D -- dominant: none (distributed mirror)

| condition | calls | turns | rederive | read | complement | probe | failed | nameerr |
|---|---|---|---|---|---|---|---|---|
| METHOD-only | 1 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| MEASUREMENT-only | 8 | 3 | 5 | 0 | 3 | 0 | 2 | 2 |
| METHOD+MEASUREMENT | 1 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |

### fleet D -- response hints

| condition | cites_measurement | interpretation_llm | claims_meas_risk | A:identifies / D:no-false-conc |
|---|---|---|---|---|
| METHOD-only | False | True | False | no-false-conc=True |
| MEASUREMENT-only | False | True | False | no-false-conc=True |
| METHOD+MEASUREMENT | True | True | False | no-false-conc=True |

The authoritative verdicts (did it compose? did interpretation stay with the LLM? did the mirror move on?) are hand-judged in `FINDINGS.md` from the preserved runs.
