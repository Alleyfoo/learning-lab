# W1-A results analysis

**Date:** 2026-08-18
**Frozen result (preserved as given):** A1 REFUSED · A2 NO_ARTIFACT · A3 NO_ARTIFACT · A4 PASS · A5 PASS
**Rule during analysis:** the frozen W1-A skill, validator, fixtures, human-answer script, and
run outputs were not modified. This document is a new file; it changes nothing the experiment
pinned. All run artifacts and session residue were preserved on disk exactly as produced.

The analysis below is grounded in: (a) the three on-disk artifacts (`runs/A1`, `runs/A4`,
`runs/A5`), (b) the Goose desktop session transcripts in
`%APPDATA%/Block/goose/data/sessions/sessions.db` and `…/logs/llm_request.*.jsonl`, and
(c) the filesystem residue the sessions left at repo root and under `work_interface/w1a/`.

## TL;DR

- **Strict end-to-end pass rate: 2/5 (40%)** — A4, A5. (Frozen result, preserved.)
- **The run directories are not cleanly attributable to runs.** Every session was instructed
  (operator prompt-template bug) to write to `runs/A1`. A4 and A5 disobeyed and wrote to their
  own dirs; A1, A2, A3 complied and **all wrote to `runs/A1`, overwriting each other**. The
  artifact currently graded "A1 REFUSED" is in fact the **A3 run's** output (it wrote last,
  19:11). The A1 run's own output (v0-shaped, but see below) was overwritten.
- **`load_skill("define-lab-process")` failed in all 5 runs** ("Skill not found"). The Goose
  desktop skill loader does not discover project-local `skills/`. The contract was acquired
  only by agents that read `skill.md` directly (A4, A5) — a file-read task made hard by a
  `cmd.exe` shell and a `read` tool that returned empty for the unicode-bearing `.md` files.
- **The PASS/REFUSED split is entangled across two independent failure axes** — output-path
  resolution and skill-contract acquisition — so W1-A does **not** cleanly answer "does the
  skill elicit the structural form?" It answers "can a Goose session, fighting the tooling,
  produce the structural form?", which is a different and weaker question.

---

## 1. Strict end-to-end pass rate

**2/5 = 40%** (A4, A5). This is the frozen result and is preserved as the headline number.
It is an *end-to-end* rate: a run passes only if a validator-valid `work_definition.json`
lands in its own run directory. By that bar A1, A2, A3 fail.

Caveat that must travel with the number: the five runs were not independent or isolated (see
§3), so 40% is not a clean binomial sample of "skill → structural form." It is the rate at
which a fresh Goose desktop session, given the frozen pack, delivered a valid artifact to the
right place.

## 2. Structural success rate conditional on an artifact being produced

Two ways to count, both reported honestly:

- **Conditional on an artifact being in the run's own directory** (the grader's view): 3 run
  dirs have artifacts (A1, A4, A5); 2 pass (A4, A5) → **2/3 ≈ 67%**. The `runs/A1` artifact
  is an invented schema (REFUSED).
- **Conditional on a run producing *any* artifact anywhere** (counting misrouted writes): all
  five runs produced an artifact somewhere. Of those five producer-runs:
  - A4 → v0, valid (skill-derived).
  - A5 → v0, valid (skill-derived).
  - A1 → v0-shaped (but **oracle-derived**: the session read `work_interface/cases/W0B_corrected.json`
    and `work_interface/work_definition.py` — the answer key and the validator — not the skill).
  - A2 → invented schema (never read the skill).
  - A3 → invented schema (never read the skill).
  → **3/5 runs produced v0-shaped output, 2/5 produced invented schema.** But of the 3
  v0-shaped, one (A1) is oracle-derived and is not honest evidence of skill-driven adoption,
  and its artifact was overwritten anyway. So the honest "skill-driven structural adoption"
  count is **2/5 (A4, A5)**.

## 3. Semantic/contract failures vs filesystem/interface failures

The failures split cleanly into two axes that the frozen labels conflate.

### Axis A — filesystem / interface failures (NOT contract-generation)

These are failures of the *harness*, not of the agent's understanding of the work:

1. **Skill loader is broken for project-local skills.** `load_skill("define-lab-process")`
   returned "Skill not found" in all 5 runs. The Goose desktop app's skill registry does not
   include `skills/define-lab-process/`. The skill the experiment pinned was therefore never
   loaded through the mechanism the skill itself tells the agent to use ("call
   `load_skill(name: "define-lab-process")`").
2. **File reading on Windows `cmd.exe` is severely impaired.** The shell is `cmd.exe`. Every
   run tried `cat`, `ls`, `head`, `Get-Content` (a PowerShell cmdlet, not valid in `cmd.exe`),
   and failed. The built-in `read` tool returned **empty** for `PROVENANCE.md` (a unicode
   `→`/`–` file) in the runs that tried it. Working read paths were discovered only by trial:
   `type` with **absolute backslash** paths (A4), `powershell -Command Get-Content` (A2, A3),
   and `python -c` with `latin-1`/`cp1252` fallbacks + `repr()` (A5). A5 burned ~70 of its 101
   messages on file-reading before it got the skill content (via `decode('latin-1')` + `repr`).
3. **Console encoding corrupts unicode.** `print()` of UTF-8 content hit
   `UnicodeEncodeError: 'charmap' codec can't encode character '\ufffd'` (cp1252 console).
   Observed corruption: `→` and `–` rendered as `->` / `?` (visible in `skill_content.txt`,
   which is actually a mis-capture of `PROVENANCE.md`, not `skill.md`).
4. **Output-path misrouting (operator template bug).** All five opening prompts hard-coded
   "write … to `work_interface/w1a/runs/A1/work_definition.json`". A1, A2, A3 complied and
   collided in `runs/A1`; A4, A5 resolved the contradiction ("this is run A4") in favour of
   their own dir. This is the direct cause of A2 and A3 being `NO_ARTIFACT` in their own dirs.
5. **Run isolation did not hold.** All sessions ran with `working_dir = C:\Users\pertt\learning-lab`
   (repo root), not the per-run dirs. The Goose desktop app opens one directory. Sessions
   shared the repo root and overwrote each other's output in `runs/A1`. Residue
   (`read_*.py`, `skill_content.txt`, `skill_frozen_copy.md`, `fixtures/tmp/PROVENANCE.md`)
   is shared across sessions and cannot be attributed to a single run.

### Axis B — semantic / contract failures

These are failures of the artifact's *form*, independent of where it was written:

- **A2 and A3 invented their own schema** (`{"process_name": …, "source_files": …}` and
  `{"version": "v0", "process_name": "Supplier Invoice Reconciliation", "matching_logic": …,
  "output_fields": …}`). They never acquired the v0 contract (never read `skill.md`), so they
  fell back to the prose-era W0B failure mode — but worse: A3's artifact embeds the *executed
  reconciliation results* (concrete `LDR-001..006` refs, `total_reconciled_amount: 9461.50`,
  specific discrepancy rows). The agent ran the task instead of defining it. This is a genuine
  contract/semantic failure, but it is **downstream** of Axis A (no skill → no contract →
  invented form).
- **A1 (the run) read the oracle and the validator.** The A1 session read
  `work_interface/cases/W0B_corrected.json` and `work_interface/work_definition.py`. It
  produced a v0-shaped artifact by reverse-engineering the contract from the answer key, not
  from the skill. The opening prompt forbade "outputs from A2–A5" but did not forbid the
  oracle/validator, so this was a loophole, not a crash. As W1-A evidence it is invalid
  (contaminated by the answer key), and the artifact was overwritten by A3 regardless.

### Per-run verdict (failure mode)

| run | frozen label | producer of artifact in its dir | acquired contract via | failure mode |
|---|---|---|---|---|
| A1 | REFUSED | **A3 run** (overwrote A1) | (A1 run: oracle+validator; A3 run: nothing) | interface (path collision) + contract (A3 invented schema) |
| A2 | NO_ARTIFACT | (none in `runs/A2`; wrote to `runs/A1`) | nothing | interface: output-path misrouting (instructed to write to `runs/A1`) + no skill → invented schema |
| A3 | NO_ARTIFACT | (none in `runs/A3`; wrote to `runs/A1`) | nothing | interface: output-path misrouting + no skill → invented schema (with executed data) |
| A4 | PASS | A4 run | read `skill.md` directly (`type`, abs path) | none — success |
| A5 | PASS | A5 run | read `skill.md` directly (`python` latin-1+repr) | none — success (after ~70 msgs of tooling friction) |

A2 and A3 are kept as end-to-end W1-A failures (per instruction). The evidence says their
failure is **interface (output-path misrouting) compounded by no-skill**, **not** a semantic
failure of contract generation in the sense of "the agent understood the work but modeled it
wrong." They never received the contract to model against.

## 4. Exact structural difference between A1 (the graded artifact) and A4/A5

The artifact in `runs/A1` (produced by the A3 run) is categorically not a Work Definition v0.
Field-by-field:

| v0 slot | A4 / A5 (PASS) | `runs/A1` artifact (REFUSED) |
|---|---|---|
| `work_definition_version` | `0` | **absent** — has `version: "v0"` (string) |
| `task_family` | `"reconciliation"` | **absent** — has `process_name: "Supplier Invoice Reconciliation"` |
| `model_id` / `provenance` | present | absent |
| `sources.<role>.fixture` | basename (`"ledger-book.txt"`) | **absent** — has `source_path` (full path) |
| `sources.<role>.observed_fields` | verbatim header list | **absent** — has `schema` (a type map: `{"Amount": "decimal", …}`) |
| `sources.<role>.basis` | `"observed"` | absent |
| `body` | present (`left`/`right`/`match_on`/`compare`/`classify`/policies) | **absent entirely** |
| match key | `body.match_on.{left_field,right_field} = "InvoiceNumber"`, `basis: human_confirmed` | `matching_logic.keys = ["Date","SupplierName","InvoiceNumber"]` (composite, prose `comparison_algorithm`) |
| compare | `compare: [{field:"Amount", comparison:"within", tolerance:"0.01", basis:human_confirmed}]` | **absent** — amount "comparison" only implied in `discrepancy_handling.amount_mismatch` prose |
| classify | `both_same/both_different/only_left/only_right` | absent |
| `output_order` / `on_duplicate_key` / `on_non_numeric` | closed-vocab values | absent |
| `output` | `reports_fields`/`context_fields` (declared field *names*) | `output_fields` containing **executed data**: `ledger_reference_numbers: [LDR-001..006]`, `supplier_invoices: […]`, `total_reconciled_amount: 9461.50`, `date_range`, `discrepancy_flags` with concrete rows |
| `human_confirmations` | recorded (A4: 2; A5: 8) | absent |
| `open_questions` | recorded (non-load-bearing) | absent |
| `requested_authority` | `null` | absent |
| authority override keys | none | none |

So the difference is not "a wrong value in a v0 field." It is **a different artifact kind**: A4/A5
are *process definitions* in the v0 envelope; the `runs/A1` artifact is an *invented report*
that mixes a partial, non-v0 definition with the **executed reconciliation output** (it did the
work and pasted the results in). The validator's four refusal codes follow exactly:
`unknown_work_definition_version` (`version:"v0"` ≠ `work_definition_version:0`), `unknown_task_family`
(no `task_family`), `missing_source_fixture` (sources use `source_path`, no `fixture`),
`match_key_not_declared` (no `body`/`match_on`).

## 5. A4 vs A5 — materially equivalent, or merely both validator-valid?

**Executable-semantically equivalent; not envelope-equivalent.** They share the same
deterministic core and differ in orientation, labelling, and evidence completeness.

### Same (the executable core)
- `work_definition_version: 0`, `task_family: "reconciliation"`.
- `match_on`: `InvoiceNumber`/`InvoiceNumber`, `basis: human_confirmed`.
- `compare`: `Amount`, `within`, tolerance `0.01`, `basis: human_confirmed`.
- `classify`: all four keys present (`both_same`/`both_different`/`only_left`/`only_right`).
- policies: `on_duplicate_key: refuse_run`, `on_non_numeric: refuse_run`, `output_order: sorted_by_key`.
- `output.reports_fields`: `["InvoiceNumber","Amount"]`.
- `requested_authority: null`; no override keys.

A runtime built from either would produce the same discrepancies (same key, same compare,
same policies, same output order).

### Different (within-contract degrees of freedom + completeness)
| aspect | A4 | A5 |
|---|---|---|
| `left`/`right` orientation | left=`ledger`, right=`statement` | left=`supplier_statement`, right=`ledger_book` (**opposite**) |
| role keys | `ledger`/`statement` | `supplier_statement`/`ledger_book` |
| `classify` labels | `matched`/`discrepancy`/`ledger_only`/`statement_only` | `amounts_match_within_tolerance`/`amount_mismatch`/`invoice_only_in_statement`/`invoice_only_in_ledger` |
| `output.context_fields` | `Date, Supplier Name, Status` | `Date, Supplier Name, Currency, Status` (adds `Currency`) |
| `human_confirmations` count | **2** (match key, amount) | **8** (all script answers: match, amount, currency, source-of-truth, report fields, context fields, duplicate policy, non-numeric policy) |
| currency handling | left as `open_questions` (non-load-bearing, unresolved) | captured as `human_confirmation Q_currency_not_part_of_rule` (settled) |
| source-of-truth | not recorded as a confirmation (implied by peer labels) | recorded (`Q_source_of_truth`) |
| `open_questions` | 2 (currency, notes) | 1 (notes) |

### Verdict
- **Merely both validator-valid?** No — their *executable semantics* are equivalent (same
  match/compare/classify/policies/order), so they are not two unrelated shapes that happened to
  pass. They are the same process.
- **Materially equivalent?** Not quite. The **orientation is opposite** (a real semantic
  choice that swaps the meaning of `only_left`/`only_right`), and the **evidence envelope
  differs substantially**: A5 captured the entire frozen human-answer script verbatim (8
  confirmations) and settled currency; A4 captured only the two executable decisions and left
  currency unresolved. A5 is strictly more faithful to the controlled human input. So: **same
  executable process, different (and unequal) evidence envelope.** If W1-A is graded on
  "faithful capture of the controlled human input," A5 is the better pass; if graded on
  "executable semantics," they tie.

A5's larger size (4346 vs 2728 bytes) is the 8-vs-2 confirmations plus the verbatim answers,
not padding.

## 6. Do the failures suggest one narrow skill change, a Goose/tooling issue, or insufficient evidence?

**A Goose/tooling issue, with one narrow skill-change corollary — not a skill-content problem.**

Evidence for "tooling, not skill content":
- The two runs that **read `skill.md`** (A4, A5) both produced valid v0 artifacts, and A5
  reproduced the controlled human answers verbatim. The skill content, when actually read,
  *does* elicit the structural form. That is the single strongest signal: the skill is not the
  bottleneck.
- The three runs that **did not read `skill.md`** failed to adopt the v0 form. A2/A3 invented
  schemas; A1 reached the v0 form only by reading the **oracle**, which is not skill-driven
  adoption.
- The dominant cost in every session was file-reading friction (A5: ~70/101 messages), not
  reasoning about the work. `load_skill` failing is a pure tooling defect.

Evidence against "one narrow skill change is the fix":
- A skill edit cannot fix `load_skill` returning "not found" (that is Goose's skill registry,
  not the skill file).
- A skill edit cannot fix the `cmd.exe`/encoding read failures.
- A skill edit cannot fix the operator's hardcoded `runs/A1` write-path (that is the prompt
  template, outside the skill).

The **one narrow skill-change corollary** that is justified: the skill currently *tells* the
agent to `load_skill("define-lab-process")`, which fails. A skill revision that instead tells
the agent the **explicit filesystem path** to read (`skills/define-lab-process/skill.md` or
the frozen `work_interface/w1a/skill/skill.md`) would remove one tooling dependency. But this
is a workaround for a broken loader, not a content improvement, and it should not be made
**during** W1-A (the skill is frozen). It belongs in W1-A2.

**Insufficient evidence to distinguish?** Partly. Because (a) `load_skill` failed for everyone,
no run ever experienced the intended skill-loading path, so we have **zero evidence** about
whether the skill *as loaded by Goose* would work; (b) the run dirs are contaminated (A1's
artifact is A3's; A2/A3 misrouted), so the per-run labels don't map cleanly to producer-runs.
What we *can* conclude: **when the skill content reaches the agent by any means, a capable
session can produce a valid v0 artifact (2/2 observed, A4/A5); when it doesn't, the agent
invents a non-v0 schema (2/2 observed, A2/A3).** That is enough to say the skill content is
not the failure, and the tooling is.

## 7. The smallest justified W1-A2 experiment

The goal of W1-A2 is to **remove the tooling confounds so the skill-content question can
actually be asked**, with the smallest possible change. Do not expand scope (no transport, no
MCP, no new families, no PRODUCT.md change).

### What W1-A2 must control (the confounds found)
1. `load_skill` fails → agent never gets the skill the intended way.
2. File reading on `cmd.exe` is unreliable; the `read` tool returns empty for unicode `.md`.
3. Output path is misrouted (operator template hardcoded `runs/A1`).
4. Runs are not isolated (shared repo root; `runs/A1` collisions).

### Smallest justified design
- **Fix the delivery, not the skill content.** Place the skill content where the agent will
  actually see it without `load_skill`: give each session the skill text **in the opening
  prompt** (or as a `SKILL.md` in the run dir the agent is told to read first). Keep the frozen
  skill bytes unchanged (still pinned by sha256). This isolates "does the content elicit the
  form" from "does `load_skill` work."
- **Fix the read path.** Tell the agent the single working read command up front
  (`powershell -Command "Get-Content '<abs path>'"` or, simpler, hand it the fixture
  **contents** in the prompt). The fixtures are frozen regardless; reading them is not the
  thing under test.
- **Fix the output path per run.** The opening prompt must name the run's **own** dir
  (`runs/A<i>`), and the run dir should be the session's `working_dir` if Goose allows, or the
  path must be absolute and run-specific. Verify no two runs share a write target.
- **Keep A4/A5 as the only prior evidence; do not reuse their outputs.** Fresh sessions only.
- **Same fixtures, same human-answer script, same validator, same skill bytes.** Change only
  the delivery/read/path harness.

### What W1-A2 is graded on (unchanged from W1-A's intent)
- **Primary:** of N fresh sessions that *receive the skill content by construction*, how many
  produce a validator-valid v0 artifact in their own run dir? This is the question W1-A could
  not answer because the skill never reached 3/5 agents cleanly.
- **Secondary:** do the valid artifacts converge on the executable core (match key, compare,
  policies) while varying only the within-contract degrees of freedom (orientation, labels,
  context fields)? A4 vs A5 suggests yes; W1-A2 with more runs would confirm.
- **Diagnostic still recorded:** refusal-code distribution, artifact sha256, whether the agent
  read the oracle/validator (forbid it explicitly this time — A1's loophole).

### Smallest justified size
**Three fresh sessions (A2-1, A2-2, A2-3)** with the confounds removed. Rationale: W1-A already
gave 2/2 clean-skill-read → PASS (A4, A5). W1-A2 tests whether that holds when the skill is
delivered by construction rather than by the agent fighting the tooling. Three runs distinguish
"2/2 was luck" from "the skill reliably elicits the form" better than two, cheaply. If 3/3
pass, the skill-content question is answered yes and the roadmap can move to W1-B (a second
skill revision / a second family) or W2; if <3/3, the refusal-code distribution points at the
next skill edit. Five runs (matching W1-A) is acceptable but not the *smallest* justified.

### Explicitly still out of scope for W1-A2
- No Goose API/MCP/transport integration.
- No automatic establishment, no production movement.
- No change to `PRODUCT.md`, the validator, the fixtures, the human-answer script, or the skill
  *content* (only its delivery path).
- No re-grading or repairing of W1-A run outputs.

---

## Evidence preserved (sha256)

On-disk run artifacts (gitignored by the pack; preserved on disk):
- `runs/A1/work_definition.json` — `cc8def72d857b15a30e4a0783e34f65bc7d12f75ffc03e61aa8e8782557b0254` (produced by the A3 run; invented schema)
- `runs/A4/work_definition.json` — `a4d56e657c06b9745367b33f0521a7db7a80781d265282936bc1acb4784eedb1` (v0, PASS)
- `runs/A5/work_definition.json` — `6343adc556eb8c82c875e514a272c0de27129a9369c6a015d3747053302d26f9` (v0, PASS)

Session-derived residue at repo root (shared across sessions; preserved, not attributed to a
single run): `read_skill.py` `818d9eae…`, `read_skill_content.py` `ae237fa7…`,
`skill_content.txt` `0134a436…` (a mis-capture of `PROVENANCE.md`, not `skill.md`),
`read_fixture.py` `d5682288…`, `read_human_answers.py` `9fd1eef8…`,
`read_answers_binary.py` `e0927d52…`, `read_all.py` `c07826ad…`.
Under `work_interface/w1a/`: `skill/skill_frozen_copy.md` `01db9dea…` (A5's re-rendered
plain-text copy of the skill), `fixtures/tmp/PROVENANCE.md` `40978892…` (A3's junk "placeholder").

Frozen skill (unchanged, still pinned): `work_interface/w1a/skill/skill.md` sha256
`4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55`; live
`skills/define-lab-process/skill.md` is byte-identical. Validator, fixtures, and human-answer
script untouched.

## Sources inspected
- `%APPDATA%/Block/goose/data/sessions/sessions.db` (sessions + messages tables, read-only).
- `%APPDATA%/Block/goose/data/logs/llm_request.*.jsonl` (mtimes; not parsed for content).
- `%APPDATA%/goose/recent-dirs.json`, `window-state.json`, `logs/main.log`.
- On-disk artifacts and residue.