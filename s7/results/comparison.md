# S7 -- Phase A vs Phase D (does intelligence get cheaper?)

> Phase A: harnessed supervisor WITH the S5 method, WITHOUT the measurement, over the inherited snapshot.
> Phase D: COLD supervisor (no method) WITH the deterministic measurement attached to the snapshot.
> The thesis: after promotion, future supervision reaches the same useful conclusion with LESS ad-hoc computation.

## fleet A -- dominant: engine 60/70

| dimension | Phase A (method, no measurement) | Phase D (cold, with measurement) |
|---|---|---|
| python calls | 3 | 1 |
| turns | 2 | 2 |
| shape components | ['count', 'dominant', 'group', 'share'] | ['count', 'group'] |
| shape complete | True | False |
| dims touched | ['digest', 'effect', 'engine', 'trigger'] | ['trigger'] |
| grounded in measurement | n/a | cites=False share/count=False claims-measurement-says-risk=False |
| delta (A - D) | calls 2 turns 0 | |

## fleet D -- dominant: none (distributed mirror)

| dimension | Phase A (method, no measurement) | Phase D (cold, with measurement) |
|---|---|---|
| python calls | 3 | 9 |
| turns | 2 | 3 |
| shape components | ['count', 'dominant', 'group', 'share'] | ['count', 'dominant', 'group'] |
| shape complete | True | False |
| dims touched | ['digest', 'effect', 'engine', 'trigger'] | ['digest', 'trigger'] |
| grounded in measurement | n/a | cites=False share/count=False claims-measurement-says-risk=False |
| delta (A - D) | calls -6 turns -1 | |

The authoritative verdicts (did it identify the concentration? did interpretation remain with the LLM?) are hand-judged in `FINDINGS.md` from the preserved runs.
