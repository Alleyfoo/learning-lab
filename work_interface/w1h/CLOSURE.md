# W1-H closure — additive

Evidence commit `9c078c2`. Pack frozen at `bf01224`; prompts, skills and
controlled inputs byte-identical before and after. **Nothing in `runs/` was
edited, repaired, or rerun.** No reporter defect was found in this pack; the
layers below are reported as produced.

## Result by layer

```text
RESOURCE DISCOVERY      3/3   both verbs, unprompted
RESOURCE CONSUMPTION    3/3   skill + supplier_statement + ledger_book
ARTIFACT PRODUCTION     3/3   write_work_definition invoked
AUTHORITY               3/3   CLEAN
STRUCTURAL              3/3   PASS
FIDELITY                2/3   PASS  <- MEASURED
```

## 1. Primary purpose achieved: fidelity is now measured

W1-G's `FIDELITY 3/3 clean` was a **recomputation** from the bytes the model
sent, because the capability server decoded stdio as `cp1252` and wrote
non-ASCII back double-encoded (`../w1g/CLOSURE.md` §3). W1-H's number is a
**measurement**, taken through the corrected transport on artifacts as they
exist on disk.

The transport claim, verified per run:

```text
run   artifact on disk == content the model sent   em dash intact   mojibake
P1    True                                          yes              none
P2    True                                          n/a (see §3)     none
P3    True                                          yes              none
```

The decisive detail: in P1 and P3 **all six confirmations map to rows 0–5,
including row 3** — the em-dash row that produced `FID-3 PHANTOM_CONFIRMATION`
in every W1-G run. That failure mode is gone, and its disappearance is
attributable to the single changed input.

```text
W1-G  transport broken     row 3 unmatched in 3/3 runs   FIDELITY void
W1-H  transport corrected  row 3 matched in every run that recorded it
```

## 2. The capability-box result replicates

Identical to W1-G on fresh run IDs: **four capability calls, two turns, no
continuations, no denials, no shell**, in every run.

```text
ALLOW READ   resource_id=skill
ALLOW READ   resource_id=supplier_statement
ALLOW READ   resource_id=ledger_book
ALLOW WRITE  content
-> COMPLETED: artifact written; session terminated immediately
```

Neither verb is named in the prompt; both were discovered and used in all six
runs across the two packs. AUTHORITY is 3/3 CLEAN with zero non-designated
files.

**STRUCTURAL improved to 3/3.** The W1-G whitespace slip did not recur — no
`observed_fields` entry in any run carries delimiter-adjacent padding. This is
consistent with `../w1g/O2_ANALYSIS.md`, which classified that failure as a
sporadic `PRODUCER_ERROR` rather than a systematic rule application. **It is not
evidence that anything was fixed:** r2 is unamended, and a 1-in-3 sporadic slip
failing to recur in 3 runs is an unremarkable outcome.

## 3. P2 — two genuine fidelity findings

```text
FID-5 UNRECORDED_HUMAN_ANSWER @ human_confirmations  row 4
FID-5 UNRECORDED_HUMAN_ANSWER @ human_confirmations  row 5
```

P2 recorded **2 of 6** confirmations (`Q_match_key`, `Q_amount_comparison`).
Rows 2 and 3 were not flagged, their content being traceable elsewhere in the
artifact; rows 4 and 5 are recorded nowhere. Yet the answers were plainly used:

```json
"output": {"reports_fields": ["InvoiceNumber", "Amount"],
           "context_fields": ["Date", "Supplier Name", "Status"]}
```

Those are exactly the human answers for rows 4 and 5. **The facts are in the
artifact; their human-confirmed provenance is not.** That is precisely the
r2 rule "settled facts have exactly one home" failing, and it is worker-caused —
the artifact on disk is byte-identical to what the model sent.

P2 is also the reason its em-dash column reads `n/a` above: having never
recorded the source-of-truth confirmation, it contains no em dash to corrupt.

**P2 passed STRUCTURAL.** A structurally valid Work Definition can silently lose
the provenance of the decisions inside it. That is the argument for keeping
fidelity as an independent layer, and this is the first time the two layers have
disagreed on a real artifact.

## 4. What may not be claimed

- N=3, one model, one fixture pair. **No population-level reliability claim.**
- **W1-H does not pool with W1-G.** The transport differs, so this is a fresh
  N=3, not N=6. `2/3` and `3/3-recomputed` are measurements of different things.
- `STRUCTURAL 3/3` is **not** evidence that the tokenization gap is closed. r2
  is unamended; the gap identified in `../w1g/O2_ANALYSIS.md` is untouched and
  still live.
- `FIDELITY 2/3` is a measurement of three runs, not a rate.
- The transport fix is established for **non-ASCII on the write path**. It was
  exercised by the em dash in canonical row 3 and nothing else.

## 5. What this establishes

The corrected transport works, measured end to end: what the model sends is what
lands on disk, byte for byte, including non-ASCII. The capability-box
architecture replicates cleanly on fresh run IDs — discovery, consumption,
production and authority all 3/3, in two turns, with no denials.

With the instrument no longer corrupting its own evidence, the remaining
findings are all about **what the worker wrote**: P2 dropped four of six
confirmations while using their content. That is a real, specific, observable
producer behaviour — the kind of finding this lab was built to produce.

## 6. Next

W1-H is closed. **W1-I now owns the producer-contract change**, and only that
change: the draft at `../skill/drafts/r3_producer_contract_amendment.md`
promoted to a frozen r3, one variable moved from W1-H.

Two things W1-I's preregistration must state up front, not discover afterwards:

- **N=3 cannot show the amendment fixed the whitespace gap.** W1-G's slip was 1
  of 3 and did not recur in W1-H *without* any amendment. A clean W1-I is
  consistent with the amendment working and with the slip simply not recurring.
- P2's `FID-5` is a **separate** producer behaviour — dropped confirmations, not
  field tokenization. The r3 draft does not address it, and W1-I must not be
  quietly widened to cover both. If it deserves a contract change, that is a
  later pack and its own variable.
