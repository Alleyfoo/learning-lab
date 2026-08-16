# S3 — findings: the smallest durable Rulebook and Improvement register

> **Research question.** Can the supervisor reason about *fixing the system*
> (not just supervising it) -- proposing improvements, while an explicit
> Rulebook catches proposals that contradict proven architecture?

S2 gave the supervisor two memories: operator-independent **semantic knowledge**
(what the system means) and **operator preference** (what this operator cares
about). S3 adds a third, different shape -- a **Rulebook** of already-proven
architectural rules, and an append-only **Improvement register** that records
every proposal with an explicit verdict. The four are deliberately distinct:

```text
knowledge       what the system MEANS              (interpretation)
preference      what the operator cares about       (threshold)
rulebook        what the system MUST NOT violate    (conflict surface)
improvements    what has been proposed about it     (register + verdict)
```

## Headline

**All predictions pass.** The supervisor model classified four proposals
correctly against a seeded rulebook of five proven rules: a compatible real
discovery, a paraphrased duplicate, a rule-violating proposal, and its
rule-respecting mirror. Conflict was explicit and **not positional** -- the same
conflict was named across every rule ordering.

```text
PREDICTION                                          RESULT
T1  D-001 compatible, no conflict, no duplicate     PASS
T2  paraphrase -> duplicate_of IMP-001              PASS  (semantic, not text match)
T3  confirmation-inheritance -> conflicts R-CONFIRM PASS  (violates version-bound rule)
T4  explicit re-confirmation -> no conflict         PASS  (respects the same rule)
permute  T3 always names R-CONFIRM-VERSION          PASS  (stable across 6 orderings)
permute  T4 never conflicts                         PASS  (stable across 6 orderings)
```

## The stores

```text
supervisor/rulebook.jsonl       5 seeded proven rules (id, area, statement, provenance)
supervisor/improvements.jsonl   4 registered proposals + verdict + provenance
```

The Rulebook is seeded once and **not modified in S3**: no rule creation, no
promotion of proposals into rules (both deferred). The Improvement register is
**append-only** -- every proposal is recorded, conflict and duplicate are
explicit metadata, never a rejection. Nothing is implemented automatically.

### The seeded rules (a handful, all already-proven)

| id | area | provenance |
|---|---|---|
| R-CONFIRM-VERSION | confirmations | 42b9b24 / 497ac32 — closed, canaried |
| R-REFUSAL-NOT-EXCEPTION | exceptions | investigation.py —self-test — canaried |
| R-EFFECT-VERIFIED | effects | 26aa00a committing runtime — canaried |
| R-PROMOTION-IMMUTABLE | versions | fleet — canaried across promotion |
| R-ITEM-IDENTITY | inbox | 74fd5dc / e6966c9 — canaried |

These are closed, canaried properties of the deterministic floor -- not learned
practice and not operator preference. Seeding proven rules (not generating them)
is what makes the conflict test meaningful: a violation is a violation of
something real.

## The four proposals

| tag | IMP | duplicate_of | conflicts_with | compatible |
|---|---|---|---|---|
| T1 D-001 | IMP-001 | — | — | true |
| T2 paraphrase | IMP-002 | IMP-001 | — | true |
| T3 inherit | IMP-003 | — | R-CONFIRM-VERSION | false |
| T4 re-confirm | IMP-004 | — | — | true |

### T1 — compatible real discovery (D-001)

The S1/S2 fleet defect (`pending_exceptions` misses inbox exceptions) registered
cleanly: no duplicate (register empty), no conflict. The rationale names every
rule and explains why none applies:

> "it does not contradict any rule about refusals, version confirmations, effect
> verification, promotion immutability, or item identity."

A genuine improvement to the floor, visible to the supervisor, not in tension
with any proven property. This is the S3 improvement-box material S1/S2 left on
purpose.

### T2 — paraphrased duplicate

T2 restates T1 in different words (no shared phrasing beyond "exceptions/" and
"pending_exceptions"). The classifier matched it to IMP-001 by **meaning**:

> "The proposal restates IMP-001: surface worker exceptions/ directory files in
> the fleet-wide pending_exceptions view."

No embeddings, no vector store -- the model judged paraphrase semantically.
T2 is still recorded (append-only) with `duplicate_of: IMP-001`; nothing was
rejected or merged.

### T3 — confirmation-inheritance (conflict)

T3 proposes that a promoted version automatically inherit the prior version's
human confirmations. The classifier flagged exactly the rule that forbids it:

> "The proposal advocates automatic inheritance of prior confirmations on
> promotion, which directly contradicts R-CONFIRM-VERSION's requirement that a
> promoted version does not inherit a prior version's confirmation and that
> truth must be re-established for the new version."

`conflicts_with: ["R-CONFIRM-VERSION"]`, `compatible: false`. The proposal is
still recorded -- conflict is allowed but explicit. A human decides whether to
pursue it (which would mean changing the rule on purpose) or drop it.

### T4 — explicit re-confirmation (the mirror, no conflict)

T4 touches the **same rule** as T3 but respects it: prompt the operator to
re-confirm for the new version, *because* confirmations do not carry forward.
The classifier returned no conflict and -- notably -- identified the mirror
relationship itself:

> "The proposal explicitly respects R-CONFIRM-VERSION by requiring
> re-confirmation on promotion rather than automatic inheritance, and it is the
> opposite stance from IMP-003, so it is neither a duplicate nor a conflict."

This is the key discriminant: "mentions the rule" is not "violates the rule".
T3 and T4 both concern confirmation inheritance; only T3 conflicts. The
classifier separated semantics from topic.

## The permutation test — conflict is not positional

To prove the classifier names a conflict by meaning rather than by rule position,
T3 and T4 were re-classified against six orderings of the rulebook:
`R-CONFIRM-VERSION` placed at each of the five positions (the other four fixed
around it) plus the full reverse. The register was passed empty to isolate
conflict from duplication.

```text
R-CONFIRM-VERSION@pos0   T3=[R-CONFIRM-VERSION]  T4=[]
R-CONFIRM-VERSION@pos1   T3=[R-CONFIRM-VERSION]  T4=[]
R-CONFIRM-VERSION@pos2   T3=[R-CONFIRM-VERSION]  T4=[]
R-CONFIRM-VERSION@pos3   T3=[R-CONFIRM-VERSION]  T4=[]
R-CONFIRM-VERSION@pos4   T3=[R-CONFIRM-VERSION]  T4=[]
full-reverse             T3=[R-CONFIRM-VERSION]  T4=[]

T3 stable across orderings: True   names R-CONFIRM-VERSION in all: True
T4 stable across orderings: True   never conflicts:               True
```

The conflict set is identical in every ordering. Whether the target rule is
first, last, or anywhere between, the same rule is named. Conflict selection is
semantic, not positional.

## What this round does NOT do

- **No rule creation or promotion.** The Rulebook is seeded and frozen for S3.
  Adding rules from proposals, or promoting a proposal into a rule, is deferred.
- **No automatic implementation.** A conflicting or duplicate proposal is
  recorded, not enacted or rejected. A human resolves.
- **No conflict resolution.** S3 surfaces conflict; it does not arbitrate.
- **No embeddings / vector matching.** Duplication is judged semantically by the
  model (T2 proves it works for paraphrase at this scale).
- **One model, one seed.** GLM-5.2 only (standing constraint). The seed is five
  rules; a larger rulebook and rule-interaction conflicts are later questions.

## Observations

- **The mirror was the hardest case and it held.** T3/T4 share a topic and a
  rule; only one violates it. The classifier's rationale for T4 explicitly
  contrasts it with IMP-003, which means it is reading stance, not keywords.
- **Paraphrase detection is semantic.** T2 shares almost no wording with T1 and
  was still matched to IMP-001. Text matching would have missed it; the model
  did not.
- **Conflict is precise.** T3 conflicts with exactly one rule, not "all
  confirmation-related rules" or "the first rule". The permutation test makes
  that non-positional.

## Preserved artefacts

```text
s3/spec.md                       frozen S3 spec, predictions, deferred items
s3/proposals.txt                 the four labelled test proposals
s3/run.py                        seed -> register T1..T4 -> permutation test
s3/results/verdicts.json         all registrations + permutation results + rationales
s3/results/run.log               console transcript
supervisor/rulebook.jsonl        5 seeded proven rules
supervisor/improvements.jsonl    4 registered proposals with verdicts
```

## Next

S3 is frozen as-is. The natural next steps, in order of dependence:

1. **Rule creation / promotion** (the deliberately-deferred S3 mechanism): let a
   proposal become a candidate rule, and decide what evidence "proven" requires
   before it joins the Rulebook. The mirror and permutation tests established
   here are the regression bar for any such mechanism.
2. **Conflict resolution** -- once a conflict is surfaced, what does the
   supervisor recommend (restate to respect the rule, or explicitly propose
   changing the rule), and who approves?
3. **S4 -- the large snapshot** (~100 workers, ~2000 runs, 28 confirmation
   histories, 17 promotions): the round that should force the Python bench to be
   reached, and that gives the Rulebook + register enough volume to test
   rule-interaction conflicts and duplicate drift at scale.