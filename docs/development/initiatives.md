# Initiative / backlog intake

Where a discovery goes when it is **outside the current work order**.

**This file has no authority.** An entry here is a candidate, not work, not a roadmap item, and not permission to start. Roundtable dispositions entries into `Roundtable accepted`, `Parked` or `Rejected` (engineering system §4.2).

## What belongs here

Cross-cutting discoveries: engineering-system issues, product-authority drift, repository hygiene, anything found while doing something else.

Work-interface *research infrastructure* smells continue to go to [`work_interface/BACKLOG.md`](../../work_interface/BACKLOG.md), which is that research line's own backlog and stays where it is. Two intakes, no overlap: this one is for the repository and the development system, that one is for the work-interface pack machinery.

Neither is a roadmap. `docs/roadmap/` is.

## Entry format

```markdown
## I-N — one-line title

**State:** Discovered | Initiative | Roundtable accepted | Parked | Rejected | Superseded
**Raised by:** who/what, and during which work
**Established by:** how anyone can re-check it

What was observed. What it would cost to leave. What deciding it would require.
```

State changes past `Initiative` are Roundtable's, and the reason is recorded in the entry.

---

## I-1 — `PRODUCT.md` priorities may be closed by v0.2–v0.6

**State:** Initiative
**Raised by:** issue #2, establishing the engineering system
**Established by:** [discrepancy register D3](discrepancy-register.md#d3--productmd-lists-product-priorities-that-appear-already-delivered)

`PRODUCT.md` § "Current product priorities" lists six items as the next work. The live `supervisor/app.py` describes #1–#5 as implemented, and states of #4 that v0.3 "closes the gap between the two halves (PRODUCT.md priority #4)". `PRODUCT.md` predates that work by a day.

Only Roundtable may change `PRODUCT.md`. What is needed is a closure decision — which priorities are closed, what remains open inside each, and what the next priority is — not a documentation edit. Until then a new worker reading `PRODUCT.md` will plan work that already exists.

---

## I-2 — supervisor runtime state is neither tracked nor ignored

**State:** Discovered
**Raised by:** issue #2, while grounding the repository
**Established by:** `git status --porcelain` reports `supervisor/backlog.jsonl`, `supervisor/current_assessment.json` and `supervisor/runs/` as untracked; `.gitignore` covers `fleet/workers/*/` runtime state with an explicit rationale but says nothing about the supervisor's.

Fleet runtime state was deliberately decided: ignored, with the reasoning written into `.gitignore`. The supervisor accrues the same kind of state — assessments, backlog, session runs — and no decision was recorded either way, so it sits permanently in the untracked list.

The question is which of these are operational history (ignore, like the fleet's) and which are evidence that should be committed. Deciding it costs little; leaving it undecided means a real change is hard to see among the noise.

---

## I-3 — an untracked duplicate of a frozen skill sits inside a frozen pack

**State:** Discovered
**Raised by:** issue #2, while grounding the repository
**Established by:** `work_interface/w1a/skill/` tracks `skill.md` and `PROVENANCE.md` (which records the frozen sha256). `work_interface/w1a/skill/skill_frozen_copy.md` is untracked and opens with the same "frozen revision" header.

A second, uncommitted copy of a frozen artifact can drift from the one whose hash is recorded, and reads as if it were the frozen one. Nothing is currently known to be wrong with it — the tracked pair remains the authority — but this is the shape of defect the lab's freeze discipline exists to prevent.

Deciding it means one of: it is the same bytes and is redundant; it is evidence and should be tracked; or it is scratch and should not be in a pack directory.

---

## I-4 — root working tree carries undispositioned scratch files

**State:** Discovered
**Raised by:** issue #2, while grounding the repository
**Established by:** `git status --porcelain` lists `W0B/`, `W0B_TODO.md`, `_shotA.png`, `_shotB.html`, `_shotB.png`, `read_all.py`, `read_answers_binary.py`, `read_fixture.py`, `read_human_answers.py`, `read_skill.py`, `read_skill_content.py`, `skill_content.txt`, `tmp/`, `skills/CodeReview/` and `work_interface/w1a/fixtures/tmp/` as untracked.

These are local to one machine and invisible to anyone cloning the repository, so this is not a repository-state defect. It is a working-copy one: `W0B_TODO.md` and `W0B/` look like they may hold real W0B material, and they are indistinguishable from throwaway scripts in the same listing.

Deciding it means separating the ones that are evidence from the ones that are scratch. Nothing here should be deleted on a passing agent's judgement.

---

## I-5 — live task-family code lives under directories named `harness/`

**State:** Discovered
**Raised by:** issue #2, while building the measured architecture view
**Established by:** `reservation/`, `enrichment/`, `aggregation/` and `reconciliation/` contain no top-level module; all four hold exactly `harness/<family>_model.py`, `harness/execute_<family>.py` and `harness/run_<family>.py`. `PRODUCT.md` and `README.md` both list the four packages as live system path. Elsewhere in this repository `harness/` means experiment scaffolding — `definition_phase/harness/`, `experimentL/harness/`, `work_interface/harness/`.

The same directory name therefore means "live task semantics" in four places and "experiment scaffolding" in many others, in a repository whose main navigation problem is telling live code from research record.

This is a naming observation, not a defect: the code is live and is imported by `modeller/`, `worker/` and `calendar_job/`. Renaming touches import paths across live packages and frozen evidence, so it is worth doing only if Roundtable judges the confusion real.

---

## I-6 — the stale-handoff class could be made checkable

**State:** Discovered
**Raised by:** issue #2
**Established by:** [discrepancy register D1](discrepancy-register.md#d1--handoffmd-was-stale-by-two-closed-packs)

`.handoff.md` was two closed packs out of date and nothing detected it. The precedence rule now means a stale handoff cannot *win*, but it can still be believed by whoever reads it first, and it was believed for several commits.

The lab's own position is that a rule worth stating is worth making checkable (`operating_procedure.md` §2.1). A cheap check exists in principle — the newest `work_interface/w1*` pack with a `CLOSURE.md` or a freeze commit should be the one the handoff names.

Deliberately **not** built here. It is a new mechanism, and the existing-system-first rule (engineering system §1) requires demonstrating that the precedence rule alone is insufficient before adding one. That evidence does not exist yet: the rule is one commit old.

---

## I-7 — `verify_frozen.py`'s verdict depends on the checkout's line endings

**State:** Discovered
**Raised by:** issue #2, running the existing checks before proposing this branch
**Established by:** `python scripts/verify_frozen.py` reports **27 mismatches across 76 checked artifacts** in this working copy. Re-hashing each artifact in both renderings gives:

```text
76  artifacts checked
49  the working file matches the frozen hash
      -- of which 11 hashes match ONLY the CRLF rendering,
         so the committed LF blob does not match them
27  match only after the line endings are changed
 0  match NEITHER rendering
```

**No frozen evidence has drifted.** Every artifact still matches its recorded hash in one rendering or the other. `core.autocrlf` is `false` here, and no `.gitattributes` sets `text`/`eol`, so the working tree carries CRLF from an earlier checkout while the committed blobs are LF.

What that means in practice: the check reports 27 false alarms on a CRLF checkout, and would report the other 11 on a clean LF one. It cannot currently pass anywhere. Its failure message — "An artifact was modified after being frozen" — is wrong in both cases, and it is the message a worker would act on.

`scripts/check_surfaced.py` has the same root cause and fails the same way: it
reports `VOID: experimentI/harness/gate_I.py sha256 4319d94f... != frozen da76ed98...`,
and `da76ed98...` is exactly the hash of the committed blob. Both integrity checks in
`scripts/` therefore currently report corruption in a clean checkout of `main`.

This is the same defect class as backlog item B-1: a verifier whose verdict is not a property of the thing verified. It is adjacent to the cp1252 decoding defects already recorded in W1-F and B-3, and it is more consequential than either, because this check is what stands between the evidence estate and silent corruption. While it cries wolf, a real change would not be believed.

**Deliberately not fixed here.** Both plausible fixes — normalising line endings before hashing, or re-freezing the eleven CRLF-derived hashes — change frozen-evidence machinery, which is not this task's scope and is not a Coder's call. `frozen_manifest.json` says so itself: "Do not edit a hash to make a check pass -- if an artifact legitimately changed, that is a re-freeze and belongs in a commit that says so." Nothing legitimately changed, so neither a re-freeze nor a hash edit is obviously right, and choosing between them is a decision.

The measurement above is the useful part: it establishes that the estate is intact, which is the question a failing integrity check actually raises.
