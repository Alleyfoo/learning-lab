# W1-A2 — skill-delivery-isolated Work Definition experiment

W1-A2 isolates one question that W1-A could not answer because of harness confounds:

> If the frozen `define-lab-process` skill content is delivered reliably to the local
> model, does it repeatedly produce a validator-valid structural Work Definition from
> the same ordinary business conversation?

This is a **boundary / skill experiment**. It is NOT product integration. It does not
touch `PRODUCT.md`, transport, MCP, model escalation, establishment, or the W0D
validator.

## Why W1-A2 exists (background)

W1-A produced A1 REFUSED, A2/A3 NO_ARTIFACT, A4/A5 PASS. The post-run analysis
(`work_interface/w1a/ANALYSIS.md`) found the result was confounded by harness/tooling
problems, not by skill quality:

1. `load_skill("define-lab-process")` failed in all five runs — the Goose desktop loader
   does not discover project-local `skills/`.
2. File reading had Windows/cp1252/unicode friction.
3. The opening prompt hardcoded the A1 output path, causing write collisions.
4. A1 found the validator/oracle and reverse-engineered the contract.
5. The two runs that read the skill directly (A4, A5) both produced valid v0 artifacts.

W1-A2 removes confounds 1, 3, and 4 by construction, and documents a workaround for 2.
The frozen W1-A skill is **not revised** — it is delivered as a local `SKILL.md` in each
run directory, removing `load_skill` discovery from the experiment.

## What is frozen and reused (unchanged)

- **Skill** — the exact frozen W1-A revision, sha256
  `4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55`, copied byte-identical
  into `runs/B1/SKILL.md`, `runs/B2/SKILL.md`, `runs/B3/SKILL.md`. Not revised.
- **Fixtures** — the frozen W1-A reconciliation fixtures at
  `work_interface/w1a/fixtures/{supplier-statement.txt,ledger-book.txt}`, referenced by
  absolute path. Not copied, not altered.
- **Human answers** — the frozen W1-A `work_interface/w1a/human_answers.md` answer table,
  reused verbatim. Not changed, not simplified.
- **Validator** — the existing W0D `work_interface/work_definition.py`. Not modified.

The W1-A result and analysis are frozen historical evidence; `work_interface/w1a/` is not
modified by W1-A2.

## Layout

```
work_interface/w1a2/
    README.md            this file
    verify_prep.py       preparation-verification (9 checks); run before Goose
    grade.py             read-only grader (W0D validator); run after Goose
    .gitignore           tracks frozen inputs; ignores agent outputs + grader results
    runs/
        B1/SKILL.md       frozen skill (byte-identical)
        B1/PROMPT.md      frozen per-run operator prompt (absolute Windows paths)
        B2/SKILL.md
        B2/PROMPT.md
        B3/SKILL.md
        B3/PROMPT.md
```

Each run directory already exists before Goose starts. Goose is never asked to create,
rename, move, repair, or discover directories.

## What is removed from the experiment (the confounds)

- **`load_skill` discovery** — removed. The skill is handed to the agent as `SKILL.md`
  with an explicit absolute read path; the prompt tells it not to call `load_skill`.
- **Output-path misrouting** — removed. Each `PROMPT.md` names that run's own absolute
  `work_definition.json` path; no prompt contains another run's path. `verify_prep.py`
  check 3 asserts the three artifact targets are distinct.
- **Oracle/validator loophole** — closed. The prompt forbids inspecting
  `work_interface/work_definition.py`, `work_interface/cases/`, the W0B corrected example,
  W1-A outputs, W1-A grader results, and the other B-run directories. The agent may inspect
  only its own `SKILL.md`, the two fixture files, and what the human tells it.
- **Task execution** — forbidden. The prompt explicitly says the artifact is a process
  definition, not reconciliation output.
- **File-read friction** — mitigated, not under test. The prompt gives the absolute fixture
  paths and documents two Windows-safe read commands (`powershell -Command "Get-Content -Raw
  '<path>'"` and `type "<path>"`) the operator can hand Goose if its reader fails. The
  helper contains no business answers.

## Operator instructions — running the three desktop Goose sessions

Run **three fresh, independent** desktop Goose sessions (B1, B2, B3). Use the local Goose
model (the same one W1-A used; no cloud models). Do not run Goose from this agent session —
the operator runs the desktop app.

For each run `B<i>` in {B1, B2, B3}:

1. **Verify prep** (once, before any run):
   ```
   python work_interface/w1a2/verify_prep.py
   ```
   All 9 checks must pass. Do not proceed if any fails.

2. **Open desktop Goose** with the working directory set to the repo root
   `C:\Users\pertt\learning-lab` (the same single-directory constraint as W1-A; the prompt
   uses absolute paths so the working dir does not matter for output isolation).

3. **Send Goose the opening prompt** — the exact contents of
   `work_interface/w1a2/runs/B<i>/PROMPT.md`. Paste it verbatim. Do not paraphrase. Do not
   add the run's absolute path by hand — it is already in the prompt.

4. **Answer Goose's questions** from the frozen answer table in
   `work_interface/w1a/human_answers.md` (the "Answers to Goose's questions" table). Match
   by intent, give the canonical answer verbatim. The three runs must receive semantically
   identical human input. If Goose asks a question the table does not cover, answer honestly
   and minimally, and record it in `runs/B<i>/operator_notes.md` as a protocol deviation
   (not a repair).
   - The W1-A2 `PROMPT.md` **replaces** the "Opening prompt" section inside
     `human_answers.md`; the answer table is what is reused. Do not edit
     `human_answers.md`.
   - Do **not** tell Goose the field names unless it asks — it must read them from the
     fixture headers. If it misreads a header, do **not** correct it.
   - Do **not** tell Goose the structural contract (vocabularies, basis rules). The skill
     teaches those. Answer only the business decisions.
   - If Goose tries to self-authorize, answer: "No — it is a non-authoritative proposal for
     validation. `requested_authority` is null."

5. **Do not modify `SKILL.md`, the fixtures, the prompt, repository code, tests, the
   roadmap, or `PRODUCT.md`** during a run.

6. **Stop the session** when Goose has written `work_definition.json` (or when it clearly
   stops without producing one). Confirm
   `C:\Users\pertt\learning-lab\work_interface\w1a2\runs\B<i>\work_definition.json` exists.
   If Goose wrote it elsewhere, **do not move it** — record the location in
   `operator_notes.md`; the grader will report `NO_ARTIFACT` for the run dir, which is the
   honest end-to-end failure.

7. **Do not repair** the artifact for any reason. A bad run is the measurement.

8. Repeat for the other two runs. **Do not modify the skill between runs.**

## Grader command

After all three sessions are complete:

```
python work_interface/w1a2/grade.py
```

The grader is read-only. It never edits, repairs, renames, or moves an agent's
`work_definition.json` or `SKILL.md`. For each B run it records: status
(PASS / REFUSED + sorted refusal codes / NO_ARTIFACT / UNPARSEABLE_JSON), whether that
run's `SKILL.md` matches the frozen hash (`skill_match`), the artifact sha256,
`requested_authority`, and any override/authority keys present. It writes
`RESULTS.md` and `RESULTS.json` (gitignored — regenerable).

## What the grader records per run

- `status`: PASS | REFUSED | NO_ARTIFACT | UNPARSEABLE_JSON | CONTESTED_SKILL
- `skill_match`: true only if this run's `SKILL.md` sha256 == the frozen W1-A hash
- `codes`: sorted refusal codes (REFUSED only)
- `problems`: per-problem {code, where, detail} (REFUSED only)
- `sha256`: the agent's `work_definition.json` sha256 (provenance; detects later edits)
- `requested_authority`: must be `null`
- `override_keys_present`: any of `established`, `is_established`, `approved`,
  `is_approved`, `validation_override`, `skip_validation`, `bypass_validation` set truthy
  (must be empty)

## Success criterion

The primary W1-A2 signal is **3/3 PASS** with:

- frozen skill hash intact in all three run dirs (`skill_match: true` for B1, B2, B3);
- distinct run paths (no path collision);
- no validator/oracle access by the agent;
- no task execution (the artifact is a process definition, not reconciliation output);
- no authority granted (`requested_authority: null`, no override keys).

If fewer than 3/3 pass, **preserve all outputs and refusal codes unchanged** for analysis.
Do not revise the skill during the three-run series. Do not repair artifacts.

## Stop condition / out of scope

W1-A2 prepares and (by the operator) runs three sessions and grades them. It does **not**:

- run Goose from this agent session;
- revise the frozen skill;
- move on to held-out fixtures, a second skill revision, MCP, API integration, transport,
  model escalation, Work product integration, or any `PRODUCT.md` change.

## Re-verification

At any time, re-run `python work_interface/w1a2/verify_prep.py` to confirm the pack is
intact (run dirs clean, skill hashes intact, prompts distinct, fixtures/answers unchanged,
validator + tests green, grader non-mutating, oracle PASS, no protected files staged).