# W1-J closure — additive

Evidence commit `af0a09a`. Pack frozen at `f51666f`; prompts, skills and
controlled inputs byte-identical before and after. **Nothing in `runs/` was
edited, repaired, or rerun.** No reporter defect was found in this pack.

## 1. PRIMARY — preservation by delivery position

```text
pos  W1-H row            P1     P2    P3     W1-J row            Q1     Q2     Q3
1    0 match key       EXACT  EXACT EXACT   5 context fields   BUND   BUND   EXACT
2    1 compare         EXACT  EXACT EXACT   4 report fields    BUND   ABS    EXACT
3    2 currency        EXACT  ABS   EXACT   3 source of truth  ABS    EXACT  EXACT
4    3 source of truth EXACT  ABS   EXACT   2 currency         ABS    ABS    ABS
5    4 report fields   EXACT  ABS   EXACT   1 compare          NONVB  ABS    NONVB
6    5 context fields  EXACT  ABS   EXACT   0 match key        EXACT  BUND   EXACT

preserved_prefix_length   P1=6  P2=2  P3=6   |   Q1=0  Q2=0  Q3=3
```

Same six answers, same text, same everything — delivered last-to-first.

## 2. Verdict: **neither simple mechanism survives**

The preregistered branch reached is *"both patterns visible → likely mixed
mechanism"*, but the evidence is sharper than that phrasing, in both directions.

### Truncation (B) is contradicted

B predicts early rows survive and late rows are lost. Under reversal:

```text
positions 1-2 (rows 5,4, no slot)  lossy in 2 of 3 runs   <- should be safest
position  6   (row 0, slot)        EXACT in 2 of 3 runs   <- should be most exposed
```

Being delivered **first did not protect** rows 5 and 4. Being delivered **last
did not destroy** row 0. And the contiguous-prefix signature — which held in
**6 of 6** lossy runs in the census — **broke**: Q1 and Q2 have
`preserved_prefix_length = 0`, and loss is scattered rather than a clean suffix.

### Provenance surface (A) is partly supported, partly contradicted

```text
row 0  match key  SLOT  EXACT in 2/3 despite being delivered LAST     supports A
row 1  compare    SLOT  EXACT in 0/3 — NONVERBATIM, ABSENT, NONVERBATIM   contradicts A
```

Row 0 is the strongest single signal in the pack: it kept its independent
identity from the final delivery position, where truncation predicts it should
be most vulnerable. But row 1 carries the same kind of slot and degraded
completely, so "has a slot" is not sufficient on its own.

### A third factor the design did not anticipate

**Reordering itself degraded preservation.** The control had two perfect runs
(P1, P3 at prefix 6); the treatment has none, and every W1-J run has fidelity
findings. Total loss rose under reversal even though no answer text changed.

A plausible reading, offered as a hypothesis and **not** as a finding: the
skill's own procedure asks its questions in a logical sequence, and a block
delivered against that sequence may be harder to map onto the worker's own
question ids — independently of position or provenance. This pack cannot
distinguish that from the other two, and no further variable should be inferred
from three runs.

## 3. Secondary layers

```text
ARTIFACT PRODUCTION   3/3
AUTHORITY             3/3 CLEAN, 0 non-designated files
RESOURCE CONSUMPTION  3/3 all three resources, every run
STRUCTURAL            2/3 PASS
FIDELITY              0/3 PASS
```

### Two incidental observations worth preserving

**The single-shot writer fired in a live run for the first time.** Q1 called the
writer twice — 3683 chars, then 3555. The **policy ALLOWED both**, correctly:
each is a well-formed authorized writer call, and authority is its job. The
**capability refused the second**, because the artifact already existed:

> work_definition.json already exists for this run; write_work_definition may be
> called only once…

The worker tried to revise its own artifact and the single-shot guard held. The
separation of authority from semantics, designed in W1-G and calibrated before
any run, worked exactly as intended against a real attempt.

**Q3's structural refusal is the systematic padding pattern.** Not W1-G O2's
single-field slip — *every* field after the first, in both sources:

```text
statement  5 of 6 padded   [' Supplier Name', ' InvoiceNumber', ' Amount', …]
ledger     6 of 7 padded   [' ReferenceNumber', ' SupplierName', …]
```

That is split-on-comma-without-strip, the mechanical form. **It occurred under
r2.** It is secondary to this pack's question and is **not** evidence about r3 —
W1-J has no r3 arm, and the tokenization line is parked. It is recorded because
it is the first appearance of the systematic form in this corpus, and because it
means the failure r3 was written against is reachable with r2 in a pack that was
not looking for it.

## 4. What may not be claimed

- N=3 per pack. **No percentages, no rates, no reliability estimate.**
- **Cross-pack differential**, not simultaneously randomized arms — the packs
  ran at different times, with everything else pinned.
- Do not pool with W1-I: different fixtures.
- The mixed reading is a description of six observations, **not** a
  decomposition of causes. No weighting of A against B is available.
- The reordering-difficulty hypothesis in §2 is a hypothesis. It was not
  preregistered and this pack cannot test it.
- Q3's padding is **not** evidence that r3 is needed, nor that r2 is
  insufficient. It is one observation in a pack with no comparison arm.

## 5. Disposition

```text
order/truncation mechanism    CONTRADICTED as the dominant explanation
provenance-surface mechanism  PARTIALLY SUPPORTED, insufficient alone
confound                      BROKEN — order and slot are no longer confounded
```

The census confound is resolved: order and provenance surface **are** separable,
and separating them shows that **neither alone accounts for the loss**.

**Surface C is now a legitimate next step**, and its interpretation is no longer
blocked by the ordering confound — but it is also no longer expected to be
sufficient. A `output.provenance` experiment would now be asking a narrower and
better-posed question: *does giving rows 4/5 a place to cite authority change
their preservation, given that position demonstrably does not?*

Row 1's collapse under reversal should be carried into that design as the
control question it now raises: a row **with** a slot lost its identity in 3 of
3 runs, which no version of the provenance-affordance story predicts.
