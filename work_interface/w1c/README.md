# W1-C — the first BLIND fidelity experiment

> **This is the first blind application of the fidelity instrument.** W1-B F1/F2/F3
> were pre-inspected, so the slice-1 run at `70e1484` calibrated the *instrument*
> and could say nothing about worker fidelity. H1/H2/H3 have never been seen.
> **No artifact-specific expected findings are preregistered** — deliberately.

Model: **`qwen3.5:9b`** via the shared local Goose/Ollama configuration, one fresh
`goose.exe acp` session per run.

## Pins

```text
skill                define-lab-process r2
                     0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a
fixtures             supplier-statement.txt  d0cb95ab5755bef320390f11899c53034548a60678e27430882e556ce1a45feb
                     ledger-book.txt         284861d7d948dd6f0cd3a5e7826a6794d15db0ce2aafe108dafa37752c36f25e
canonical block      46158afa4b7e682a32e3891cb5790df4b517bfb608f014c9c50cd60371db5330
                     693 bytes, rows 0-5 of human_answers.md (5fe99a5bb41a3f36…)
                     byte-identical to the frozen W1-B block
validator            work_definition_version 0, aligned, 27 refusal codes
fidelity instrument  fidelity_check.py  11984c096b8fd74f40549d17f9300dc732f3dbe1d4e1112f3dc0f412036b41d4
                     frozen at 70e1484; the gate refuses to run if this drifts
```

**W1-C is the first pack to pin skill r2.** Every earlier pack pins r1
(`4ff939d4…`), which is untouched, so all historical graders stay reproducible.
The live `skills/define-lab-process/skill.md` is still r1 and is not deployed
from here.

## Lifecycle — unchanged from W1-B

Goose receives the run prompt, then **the complete canonical information block**
after every completed non-artifact turn, delivered unconditionally. **No semantic
question matcher exists anywhere in the harness** — `verify_prep` check 10 proves
this by AST, by runtime attribute audit, and by import audit. Hard termination at
the first artifact write.

```text
COMPLETED                                     artifact written; session ended at once
CONTESTED: BLOCKED_WITH_COMPLETE_INFORMATION  no artifact although the block was held
CONTESTED                                     timeout, forbidden path, mutated input
HARNESS_ERROR                                 infrastructure only (exit 1)
```

## The two verdicts are independent

They are produced by different tools, recorded in different files, and **must be
reported separately**.

```text
STRUCTURAL   grade.py       -> RESULTS.md / RESULTS.json
             PASS = the aligned v0 validator returns no problems

FIDELITY     fidelity_gate.py -> FIDELITY.md / FIDELITY.json
             FIDELITY PASS = ZERO findings from the frozen FID-1..FID-6 checker
                             within its already-declared scope
```

**That zero-findings test is the only fidelity gate.** No per-artifact
expectations, no hand-derived table, no comparison against anything seen before.

### The instrument's declared scope, carried over unchanged

```text
rows 0, 1     slot-level FID-1 (body.match_on, body.compare[Amount])
rows 4, 5     FID-5 only -- v0 gives their output slots no provenance machinery
row 3         participates in attribution; no bound v0 decision slot, so no FID-1
rows 6, 7     not delivered -> out of scope. on_non_numeric therefore remains an
              OBSERVED DIVERGENCE and can never be a finding here.
paraphrase    invisible to the instrument by construction
```

**FID-1 is a proposed fidelity invariant, not structural-validator law**
(`work_definition.py:24-29` deliberately declines to judge a `basis` label).

## Preregistered outcome classes

Exactly four. Each is a real result; none is a failure of the experiment.

```text
1  STRUCTURAL PASS + FIDELITY PASS
   the artifact is valid AND every delivered human fact is traceable into v0's
   provenance machinery.

2  STRUCTURAL PASS + FIDELITY FINDINGS
   valid but untraceable. The validator's blind spot is real and measurable, and
   the fidelity invariant is doing work the structural gate cannot.

3  STRUCTURAL REFUSED + FIDELITY PASS
   provenance is faithful but the artifact is structurally wrong. Separates
   "recorded the human correctly" from "assembled the artifact correctly".

4  STRUCTURAL REFUSED + FIDELITY FINDINGS
   both. Causal analysis must not assume one caused the other.
```

## Discipline

- **Do not increase N after seeing the outcome.** Three runs, one batch.
- Do not rescue a run, alter the block, change lifecycle behaviour, or rerun an
  individual run.
- Do not repair an artifact. A bad run is the measurement.
- A CONTESTED run is neither a structural nor a fidelity failure; it is a
  lifecycle result and must not be graded as either.
- Do not modify the skill, validator, block, harness or instrument after seeing
  the result.

## Execution

```bash
python work_interface/w1c/harness/selftest.py && python work_interface/w1c/harness/block_harness.py --run all && python work_interface/w1c/grade.py && python work_interface/w1c/fidelity_gate.py
```

Inspect the block without running anything:

```bash
python work_interface/w1c/harness/block_harness.py --run all --show-block
```

## What this experiment cannot conclude

That a clean result means high fidelity in general. It measures three runs of one
9B model on one fixture pair, over four rows, with paraphrase invisible and rows
3/6/7 out of scope. It is the first blind data point, not a rate.
