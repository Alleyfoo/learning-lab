# Grading open-ended definition-phase output — design v0

**STATUS: DRAFT for designer review. NOT frozen. No probe has been run and none
is authorized.** Open decisions are listed at the end; the thresholds in §7 are
proposals, not frozen values.

## 1. The problem

Every probe in this repo grades `answer == expected_string`:

```text
3A/3B/3C   warrant == "supported" | "insufficient_evidence"
3D/3E      verdict == "A" | "B" | "C"       gate: month_columns == [2,3,5,6]
H          located row == 4                 gate: coverage == 12
I / J      format == "wide" | "long" | "unknown"
```

A definition-phase output is a *description*: what this source contains, what
structure it seems to have, what is ambiguous, what a human must decide. There
is no correct string. Three bad ways out, all of which break the lab's rules:

| Tempting | Why it is refused |
| --- | --- |
| Grade it by reading it afterwards | Post-hoc. Violates [freeze expected answers before the run]. Any output can be argued into "roughly right" |
| Ask an LLM judge for a score | The judge is the same kind of component under test. 3C showed judges are framing-sensitive and 3B showed they endorse unsupported claims across three model families. A judge as *authority* imports the exact failure the programme is about |
| Loosen until it passes | Then the instrument measures nothing |

## 2. The core move: grade referents, not prose

The programme already contains the answer, in the H↔I contrast:

```text
H  "locate the row where the known vocabulary appears"   -> deterministic, gradeable, PASS 4/4
I  "classify what this representation is"                 -> coarse heuristic, boundary located, FAIL
```

Locating an **object** is checkable. Characterising it is a judgement. So:

> **Require the output to point at objects. Grade the pointing. Never grade the
> phrasing.**

Objects in a source file are enumerable and finite — columns, rows, sheets,
cells, files. "Did the output point at the total row?" is a string comparison
against a frozen address. "Did the output describe it well?" is not, and is not
scored.

This does not forbid prose. It splits the output into a **scored projection**
(referents + enumerated classes) and an **unscored channel** (free notes),
recorded verbatim and adjudicated separately (§10).

## 3. Output contract (proposed)

One call per fixture, fresh isolated context, no handed proposition (3C's rule:
handing a proposal invites confirmation). The prompt asks an open question —
*"describe what this source contains and what a person would need to decide
before using it"* — and constrains only the **shape** of the answer:

```json
{
  "observations": [
    {"referent": "row:9", "class": "aggregate_row", "note": "free text"}
  ],
  "questions": [
    {"referent": "col:Kommentti", "question": "free text"}
  ],
  "structure": {
    "header_row": 4, "grain": "one row per product",
    "time_axis": "col:Tammi,col:Helmi,col:Maalis",
    "keys": ["col:Tuote"], "measures": ["col:Tammi", "..."]
  },
  "notes": "free prose — RECORDED, NEVER SCORED"
}
```

Constraining the output *shape* is not constraining the *reasoning*. This is the
same move H made: the locator may reason however it likes, but it returns a row
number.

### Addressing scheme (frozen, tolerant matcher)

```text
col:<verbatim header text>      row:<1-based index in the rendered extract>
sheet:<name>                    cell:<col>@<row>            file:<name>
```

Normalisation: strip, casefold, collapse internal whitespace. Matching is
equality on the normalised address — a frozen, self-tested matcher with a stated
boundary, exactly like H's `tolerant_match`. **No fuzzy or semantic matching.**

A finding may be legitimately pointed at from more than one angle ("there is a
title row" vs "the header is row 4"), so each frozen finding carries a list of
`accepted_referents`; any one of them counts as located.

## 4. The frozen inventory — four sets, both directions

Per fixture, authored and frozen before any run:

| Set | Meaning | Failing it is |
| --- | --- | --- |
| `findables` | Defects/features a competent survey must notice. Each: id, `accepted_referents`, `accepted_classes`, `critical: true\|false` | **silence** — a miss |
| `clean_regions` | Referents that are ordinary and must NOT be flagged | **noise** — a false flag |
| `ambiguities` | Genuinely unresolvable from the material; must appear in `questions` | **silence** — an unasked question |
| `resolvables` | Answered by the material; must NOT appear in `questions` | **noise** — a false escalation |

Recall alone is trivially gamed by flagging everything; `clean_regions` and
`resolvables` are the anti-paranoia controls, and they are the same "controls in
both directions" that made 3D interpretable.

### Totality (learned while building the instrument, §14)

Noise is only counted when a flagged referent is in `clean_regions`. So an
inventory that leaves any object unclassified lets an agent **flag it for free**
— the noise measure quietly loses its teeth in proportion to the gaps.

> **Requirement: the inventory must be TOTAL over the observation channel** —
> every column and every row of the fixture appears in exactly one of
> `findables` / `clean_regions`. Machine-checked before grading; an inventory
> with a hole is rejected rather than silently graded.

Totality is achievable because these fixtures are small and the addressable
surface is finite. The **question channel is deliberately not total**: some
questions about unlisted objects are defensible (*"is `Yhteensä` a total or a
period?"*), so only the frozen `resolvables` produce false escalations.

## 5. Two grading levels — located vs characterized

For each frozen finding, score twice:

```text
located        an observation matched an accepted referent    (class ignored)
characterized  located AND its class is in accepted_classes   (frozen enum)
```

**`located` gates the result; `characterized` is measured and reported but does
not gate.** The programme's own evidence justifies the split: H (locate) passed
4/4; I (classify) located a boundary and failed. Requiring correct
characterisation would re-test the thing already known to be weak and would make
the instrument fail for vocabulary reasons (I5/I6: the label the model reaches
for is fragile; what it points at is less so).

**Preregisterable prediction, before any probe runs: `located` ≫ `characterized`.**

## 6. Error directions — and which one is unsafe *here*

```text
silence   a real defect goes unnoticed into the project definition
noise     an ordinary column is flagged / a resolvable question is escalated
```

**The unsafe direction is inverted from Experiment J.** In J, `unknown` was a
refusal and refusing was safe — a human looks at it. In the definition phase the
opposite holds: an unnoticed defect is *silently baked into the project spec*
and surfaces later as rework, while noise costs only attention in a review that
a human is already doing. So the safe direction is domain-dependent and must be
argued per experiment, not inherited.

Consequence for grading: **critical findables gate at 100%; noise gates against a
frozen budget.** Both are reported separately, never as a single accuracy number.

## 7. Decision rules (PROPOSED — designer freezes the numbers)

```text
pass = critical_located == 100%
       AND false_flags <= B_flag
       AND ambiguities_questioned == 100%
       AND false_escalations <= B_esc
```

Proposal: `B_flag = 0`, `B_esc = 0` on the all-clean control, `B_flag = 1`,
`B_esc = 1` elsewhere. These are strict and may well fail; that is a measurement,
and the K_w=3 / coverage==12 precedent says pick a number, freeze it, and live
with the consequence rather than tune it afterwards.

Non-gating, reported: `characterized` rate, non-critical `located` rate, novel
findings (§10), and the `structure` slots (each with a frozen expected value or
a frozen `unknown`).

## 8. Controls

- **All-clean fixture.** At least one source with **no** planted findables and no
  ambiguities. Any observation is a false flag; any question is a false
  escalation. Without this, "always flag something" is a winning strategy — and
  3B/3C say models do assert when handed material to inspect. **This is the
  control most likely to fail, and it is the one worth running first.**
- **Resolvables** in every fixture (things the material plainly answers).
- **Clean regions** in every fixture, including fixtures that do have defects.

## 9. Anti-tautology guards (carried from J)

1. **Held-out fixtures.** The inventory author knows what they planted, so the
   first fixture proves only that the instrument runs. Hold out sources whose
   inventories are authored before any output is seen.
2. **Ground truth by definition.** A finding is `critical` because of what it
   does to a downstream project, decided at freeze time — never because the
   agent did or did not catch it.
3. **Predicted cost, named in advance.** Predict per fixture which findings will
   be missed and which controls will produce noise, and let the prediction be
   wrong on the record.

## 10. What this instrument does NOT measure (state it, do not hide it)

- **Unknown-unknowns.** By construction it measures *recall of known findables*.
  A genuinely novel observation the inventory does not contain scores **zero**.
  Handling: a **non-scoring novel-findings channel** — record such observations
  verbatim, have a human adjudicate afterwards, and **never fold them into that
  run's pass criterion**. Adjudicated-real ones become frozen findables in the
  *next* inventory. That is the absorption loop applied to the instrument itself:
  the agent exposes something, a human names it, the frozen set absorbs it.
- **Insight expressed without pointing.** A correct observation phrased with no
  referent scores zero. Preserved in `notes`, adjudicated, never scored.
- **Noise is only as sharp as `clean_regions` is complete.** Mitigated by the
  totality requirement (§4), which is machine-checked — but totality is over the
  *addressable* surface (columns and rows). An agent flagging something at a
  finer or cross-cutting granularity still lands in the unscored novel channel.
- **Prevalence.** Planted defects are as findable as their author made them. This
  is a controlled instrument, not a sample of real sources (the UQ-1 question,
  kept separate — and if archive-derived fixtures are ever used, the
  `operating_procedure.md` ordering rule applies).
- **The analyzer role.** §12.

## 11. Where an LLM judge is allowed

As a **secondary, non-authoritative reading only** — recorded exactly like 3E's
orchestrator-disposition call, which agreed with the deterministic gate but did
not own the outcome. Deterministic referent matching owns authority. A judge may
never convert a miss into a hit. If judge and gate disagree, that disagreement is
data about the judge.

## 12. The analyzer role (sketch — not designed yet)

The higher-level LLM analyses *the whole project*, so its input is the set of
definition-phase outputs, not a source file. Same machinery, different objects:
plant **contradictions across agent outputs** (one says the grain is monthly,
another weekly) and require the analyzer to surface the conflict *pointing at
both sources*. Control: material with no contradiction must not produce a
manufactured one. This needs the definition-phase grading working first, and its
own design pass — it is listed here only so the addressing scheme is chosen with
it in mind.

## 13. Worked example — the design is checkable, not just plausible

`operating_procedure.md` §2.1: *a rule is only worth stating if it is checkable.*
So the design ships with a running instrument and three **hand-written** mock
outputs (no LLM has been involved at any point):

```text
fixtures/D1_myyntiraportti.csv   title + timestamp + blank + header on row 4,
                                 4 products x 3 months, a Yhteensä total COLUMN,
                                 a YHTEENSÄ total ROW, a sparse Kommentti column
                                 with one 'korjattu' marker
inventory/D1.json                4 findables (3 critical), 7 clean regions,
                                 1 ambiguity, 4 resolvables — total over
                                 the observation channel
harness/grade_definition.py      matcher + integrity checks + grader + self-test
```

```text
mock            role                        verdict         why
good            competent survey            PASS            4/4 located, 3/4 characterized,
                                                            0 flags, 0 escalations
silent          fluent, notices nothing     FAIL_SILENCE    misses F1/F2/F3; would load the
                                                            total row and total column as data
paranoid        flags everything            FAIL_NOISE      3/3 criticals, 4/4 located,
                                                            4/4 characterized, ambiguity
                                                            caught — and still fails:
                                                            4 false flags, 2 false escalations
```

**The paranoid mock is the load-bearing one.** It has *perfect recall and perfect
characterisation* and the instrument still fails it. That is the evidence that
"suspect everything" is not a winning strategy here — the property recall-only
grading cannot have.

The self-test also asserts the instrument rejects a **holed** inventory (one
unclassified column) and a **self-contradictory** one (a referent both findable
and clean), so the integrity checks are exercised, not merely declared.

```bash
python definition_phase/harness/grade_definition.py --self-test
```

Note what this does and does not establish: it shows the *grader* discriminates
across the three behaviours that matter. It says nothing about how any real model
behaves — no probe has been run, and none is authorized.

## 14. Open decisions for the designer

1. **Thresholds** `B_flag` / `B_esc` (§7) — freeze the numbers, or accept the
   proposal.
2. **Does `characterized` gate?** Proposal: no (§5). It is the stricter, more
   interesting number and the one most likely to fail.
3. **Fixture sourcing** — in-lab authored only for the first freeze, or
   archive-derived later under the UQ-1 ordering rule?
4. **Scope of the first probe.** Proposal: the all-clean control plus one
   defective fixture — the smallest pair that can distinguish a competent survey
   from a paranoid one. Two calls, one model.
5. **Is the output contract too constrained** to still count as "definition-phase
   work"? The honest statement is that the *scored* part is a projection of the
   output; if that projection is judged to miss the point of the phase, this
   design needs rethinking rather than tuning.
