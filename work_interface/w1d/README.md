# W1-D — Surface B only: lifecycle separation

> **W1-D changes ONLY lifecycle semantics relative to W1-C.** Every other
> variable is pinned to its W1-C value, including the worker capability
> environment. The fail-closed ACP permission policy is **not** adopted; Surface
> A becomes W1-E, and only after W1-D is closed.

## Pinned, unchanged from W1-C

```text
model                qwen3.5:9b, shared local Goose/Ollama config
skill                define-lab-process r2
                     0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a
fixtures             supplier-statement d0cb95ab…   ledger-book 284861d7…
canonical block      46158afa4b7e682a…  693 bytes, rows 0-5 of human_answers.md
validator            work_definition_version 0, aligned, 27 refusal codes
fidelity instrument  fidelity_check.py 11984c096b8fd74f… (gate refuses on drift)

worker capability environment -- IDENTICAL to W1-C, deliberately:
  goose acp, session mode `auto`
  NO client filesystem capability, so the `developer` extension does all file I/O
  shell available to the worker exactly as before
  NO permission policy, NO denials
```

## The only change: harness revision r2

```text
initial session/prompt              -> the run prompt
first completed non-artifact turn   -> the canonical block, EXACTLY ONCE
every subsequent non-artifact turn  -> exactly "Continue."
first artifact                      -> terminate immediately
```

W1-C H1 received the block four times; only the first carried information
(`w1c/H_ANALYSIS.md`). Under r2 the block is asserted once and never re-asserted,
so redundant authority is impossible by construction. `next_message()` takes only
`(block_sent, block)` — it cannot see the agent's text, which `verify_prep` check
14 asserts by signature.

**Post-block questions receive no business answer, regardless of wording.** Full
agent text is recorded verbatim; only `"Continue."` is sent. Ownership of rows
6/7 and `output_order` is unchanged.

Corrected silent-turn budget preserved:

```text
at most two consecutive silent re-entries
ONLY non-empty visible assistant content resets the streak
tool activity does NOT reset it
a visible post-block question resets the streak and still receives "Continue."
```

## Runs and N

**K1, K2, K3. N is fixed at 3** and is not increased after seeing the outcome.

## Primary outcomes — two, independent

```text
STRUCTURAL   grade.py          -> RESULTS.md / RESULTS.json
             PASS = the aligned v0 validator returns no problems

FIDELITY     fidelity_gate.py  -> FIDELITY.md / FIDELITY.json
             FIDELITY PASS = ZERO findings from the frozen FID-1..FID-6 checker
                             within its already-declared scope
```

No artifact-specific fidelity expectations are preregistered. The instrument's
declared scope is unchanged: rows 0/1 slot-level FID-1; rows 4/5 FID-5 only;
row 3 attributed but unbound in v0; rows 6/7 out of scope so `on_non_numeric`
remains an observed divergence; paraphrase invisible. FID-1 remains a proposed
fidelity invariant, not validator law.

## A4 shadow audit — descriptive, NOT a verdict

```text
A4_SHADOW = CLEAN | WOULD_CONTEST        a4_shadow.py -> A4_SHADOW.md / .json
```

**Filesystem authority is deliberately NOT part of the primary experimental
verdict.** The batch runs with `fs_enforcing=False`: the pre-run snapshot is
recorded as data, no filesystem verdict is computed in-run, and A4 **cannot
terminate, alter, rescue or otherwise influence K1/K2/K3**. The self-test proves
this — an identical stray write contests under `fs_enforcing=True` and does not
under `False`.

The audit runs only after the complete batch, over the preserved run-directory
state, and answers one descriptive question: *would this worker have violated the
future Surface-A policy?* That keeps W1-D comparable with W1-C — where H2 created
`temp_skill.txt` — without letting an unadopted surface change this experiment's
result. Harness-written files (`acp_transcript.jsonl`, `harness_result.json`) are
excluded; they are not worker output.

## Discipline

- **Do not increase N after seeing the outcome.**
- Do not rescue a run, alter the block, change lifecycle behaviour, or rerun an
  individual run.
- Do not repair an artifact. A bad run is the measurement.
- A CONTESTED run is neither a structural nor a fidelity failure.
- Do not adopt Surface A mid-experiment, and do not act on `A4_SHADOW`.

## Execution

```bash
python work_interface/harness/selftest_single_block.py && python work_interface/w1d/harness/run_batch.py --run all && python work_interface/w1d/grade.py && python work_interface/w1d/fidelity_gate.py && python work_interface/w1d/a4_shadow.py
```

Inspect the block without running anything:

```bash
python work_interface/w1d/harness/run_batch.py --show-block
```

## What W1-D can and cannot conclude

It can show whether removing redundant authority changes completion, structural
validity, or fidelity, with one variable moved. It cannot say anything about the
fail-closed permission policy — that is unadopted here, and `A4_SHADOW` is an
observation about a future surface, not a result about this one.
