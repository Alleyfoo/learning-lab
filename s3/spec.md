# S3 — the smallest durable Rulebook and Improvement register

> **Research question.** Can the supervisor reason about *fixing the system*
> (not just supervising it) -- proposing improvements, while an explicit
> Rulebook catches proposals that contradict proven architecture?

S2 gave the supervisor two memories: operator-independent **semantic knowledge**
(what the system means) and **operator preference** (what this operator cares
about). Neither is the right place for *architectural rules a proposal may
contradict*. That is the Rulebook's job, and it is a different shape:

```text
knowledge       what the system MEANS              (interpretation)
preference      what the operator cares about       (threshold)
rulebook        what the system MUST NOT violate    (conflict surface)
improvements    what has been proposed about it     (register + verdict)
```

## The two stores

Smallest durable form, same shape as the S2 memory stores:

```text
supervisor/rulebook.jsonl       seeded rules (id, area, statement, provenance)
supervisor/improvements.jsonl   registered proposals + verdict + provenance
```

The Rulebook is **seeded once** with a handful of already-proven architectural
rules from the inherited floor. In S3 there is **no rule creation and no
promotion of proposals into rules** -- both deferred. The Improvement register
is **append-only**: every proposal is recorded, with an explicit verdict. Nothing
is implemented automatically.

## Conflict is allowed but explicit

A proposal that contradicts a rule is still recorded -- `conflicts_with` names
the rule(s). The verdict is metadata, not a gate. The supervisor may raise a
conflicting proposal; the Rulebook's only job is to make the conflict visible so
a human decides with eyes open.

## Classification is semantic, not positional

The supervisor model judges duplication (paraphrase) and conflict by meaning, not
by wording or by where a rule sits in the list. The rule-order **permutation
test** proves conflict selection is not positional: a proposal that conflicts
with `R-CONFIRM-VERSION` must be flagged regardless of where that rule appears in
the list presented to the model.

## The test set

Four proposals, registered in order against the seeded rulebook:

```text
T1  D-001 (real discovery)            compatible -- no conflict, no duplicate
T2  paraphrase of T1                  duplicate_of T1 -- same proposal, new words
T3  confirmation-inheritance          CONFLICTS with R-CONFIRM-VERSION
T4  explicit re-confirmation (mirror) no conflict -- respects the same rule
```

`T3` and `T4` are a mirror pair around the version-bound-confirmation rule: T3
asks to inherit v1's confirmation into v2 (violates the rule); T4 asks to prompt
the operator to re-confirm for v2 (respects the rule). Both touch the same rule;
only one conflicts. That separates "mentions the rule" from "violates the rule".

After registration, the permutation sub-test re-classifies T3 and T4 against
several orderings of the rulebook (R-CONFIRM-VERSION moved to each position,
plus the full reverse) and asserts the conflict verdict is stable across
orderings -- so the classifier is not just picking the first or last rule.

## Predictions

```text
T1  duplicate_of=null, conflicts_with=[]          (compatible real discovery)
T2  duplicate_of=IMP-001, conflicts_with=[]       (paraphrase, not a new idea)
T3  conflicts_with includes R-CONFIRM-VERSION      (violates version-bound rule)
T4  conflicts_with=[]                             (respects version-bound rule)
permute  T3 always names R-CONFIRM-VERSION; T4 never conflicts, in every order
```

## Explicitly deferred

rule creation from proposals · promotion of a proposal into a rule · automatic
implementation of any improvement · conflict resolution (a human resolves; S3
only surfaces) · scoring/ranking of improvements · embeddings or vector
matching (duplication is judged semantically by the model) · a second handful
of rules (seed is frozen for this round).