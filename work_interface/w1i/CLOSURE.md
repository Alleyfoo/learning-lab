# W1-I closure — additive

Evidence commit `6ce7bd1`. Pack frozen at `92bc885`; prompts, skills and
controlled inputs byte-identical before and after. Executed as **one six-run
batch with no inspection between arms**, so the treatment arm inherited no human
reaction to the control results. **Nothing in `runs/` was edited, repaired, or
rerun.**

## 1. PRIMARY — tokenization

Reported first, and independent of the structural verdict.

```text
run   revision   exact   padded   collapsed   other   sep-ws survives   internal-ws preserved
U1    r2           11       0          0        0           no                  yes
U2    r2           11       0          0        0           no                  yes
U3    r2           11       0          0        0           no                  yes
V1    r3           11       0          0        0           no                  yes
V2    r3           11       0          0        0           no                  yes
V3    r3           11       0          0        0           no                  yes
```

Every run declared all 11 canonical tokens across both sources, exactly:

```text
statement   Charge Period, Client Ref, Net Value, Tax Band, Settlement State
ledger      Charge Period, Internal Key, Client Ref, Net Value,
            Settlement State, Remarks
```

### Verdict, per the preregistered branch

```text
U and V both EXACT
-> the fixture did not discriminate in these six runs
   NOT evidence that r3 is unnecessary
```

**No efficacy claim follows.** r2 produced clean tokenization unprompted in all
three control runs, so this fixture never created the condition r3 exists to
resolve. The amendment was neither confirmed nor refuted here.

Two things the run *does* establish, both negative and both worth having:

- **r3 did not cause over-normalization.** `collapsed = 0` in every V run, and
  internal whitespace is preserved in all six. The internal-space canary — the
  reason `Charge Period`, `Client Ref`, `Net Value`, `Tax Band`,
  `Settlement State` and `Internal Key` all carry significant internal spaces —
  fired in neither direction. An over-aggressive reading of "discard the
  whitespace" would have shown up here and did not.
- **r3 did not regress anything else measured.** Both arms are identical on
  every layer below.

## 2. Secondary layers

```text
ARTIFACT PRODUCTION   6/6   two turns, four capability calls, every run
AUTHORITY             6/6   CLEAN, 4 ALLOW / 0 DENY, no shell, 0 non-designated
STRUCTURAL            6/6   PASS
FIDELITY              1/6   PASS, 9 findings across 5 runs
RESOURCE CONSUMPTION  reported NO -> VOID, see §3; corrected 6/6
```

### Fidelity — all confirmation-recording, none about tokens

```text
U1  FID-5 x2   rows 4,5 recorded nowhere
U2  FID-6      row 1 nonverbatim (TRAILING_CONTENT)
    FID-2      rows 4,5 bundled into one confirmation
U3  clean
V1  FID-5 x2   rows 4,5 recorded nowhere
V2  FID-2      rows 1,2,3,4,5 bundled into one confirmation
V3  FID-5 x2   rows 4,5 recorded nowhere
```

Every finding concerns **how confirmations were recorded** — dropped, bundled,
or paraphrased. **None concerns token representation.** Per the preregistered
rule they are secondary observations and bear neither for nor against the
token-boundary amendment.

They do sharpen issue B from `../w1h/ACCEPTANCE.md`. W1-H P2 dropped rows 4 and
5; here rows 4 and 5 are dropped again in three of six runs, and bundled in two
more. Across W1-H and W1-I the same two rows — report fields and context fields
— are the ones that lose their home. That is a **pattern worth its own
experiment**, and it is emphatically not a reason to touch r3.

## 3. Two reporter columns are void

Both are constants I failed to repoint when cloning the pack. Neither is worker
behaviour, and the evidence is left exactly as produced.

**`RESOURCE_CONSUMPTION` reads NO for both fixtures in all six runs.**
`authority_report.py:47` still carries the W1-A fixture titles:

```python
CONSUMPTION_MARKERS = {"supplier_statement": "Supplier Statement File",
                       "ledger_book": "Internal Ledger Book"}
```

Fixture T's titles are `Vendor Charge Summary` and `Internal Charge Ledger`, so
the markers can never match. Corrected reading, from the frozen permission log:
**every run read all three resources** (`skill`, `supplier_statement`,
`ledger_book`, then one write — four calls, all ALLOW). The tokenization measure
independently proves the fixture text reached the model: 11 exact header tokens
cannot be produced without it.

**Corrected RESOURCE CONSUMPTION: 6/6 on all three resources.**

**`skill_match` reads `no` for the whole V arm.** `grade.py` pins that column to
the r2 hash, which is wrong by construction for a differential pack. Verified
independently: every V run's `SKILL.md` is byte-identical to frozen r3
(`ea259e1a2af86639`), every U run's to frozen r2 (`0230969ea7fd00ed`), each
matches its recorded `skill_revision`, and `run_batch` gated each run on its own
arm's hash before executing. **No contamination; a mis-pinned column.**

Both are fixed for future packs, with regressions, in the commit following this
one.

## 4. What may not be claimed

- **No efficacy claim for r3.** The control arm was clean, so the comparison had
  nothing to separate.
- **Do not convert 3 + 3 into a rate or percentage.** Six observations are
  reported as six observations.
- **Do not pool** W1-I with W1-G or W1-H: different fixture, different revision
  set.
- `STRUCTURAL 6/6` is not the tokenization measure and is not evidence about the
  amendment.
- The fidelity findings are **not** evidence about tokenization, in either
  direction.
- A clean V arm does not show r3 is safe in general — only that on this fixture,
  in three runs, it produced no over-normalization.

## 5. Next

The token-boundary question remains **open and untested**. The honest options,
in order of what they would actually buy:

1. **Accept r3 on its merits as a contract clarification** and stop trying to
   demonstrate it behaviourally. It closes a real gap identified by causal
   analysis; W1-G showed the gap is reachable. A fixture that reliably elicits
   the slip may not exist without becoming adversarial, which the design
   explicitly forbids.
2. **Design a fixture that discriminates** — but note the constraint that bit
   here: the padding must be ordinary enough to stay plausible, and ordinary
   padding is exactly what this worker already handles correctly. That tension
   should be resolved before another six runs are spent.

**Issue B is now the better-evidenced target.** Rows 4 and 5 have lost their
recorded provenance in P2, U1, V1, V3, and been bundled in U2 and V2 — six
occurrences across two packs and two revisions, on the same two rows. That is a
far stronger signal than the tokenization slip ever produced, and it deserves
the next line.
