# `define-lab-process` — revision r2

```text
r1  4ff939d4810cb71c13364c5bb11a9bea83b0562fd25ae6fe0a8bf59bfe961d55   11111 bytes
r2  0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a   12093 bytes
```

**r1 is frozen and untouched.** It remains byte-identical at
`work_interface/w1a/skill/skill.md`, at `skills/define-lab-process/skill.md`, and
in every W1-A2…W1-B run directory. Twenty-nine files pin its sha256; none of them
change. r2 is for **future work only** — no existing pack adopts it, and no
historical hash, result or artifact is affected.

## What changed, and why

One contract correction, from the roundtable decision on
`work_interface/w1b/F1_ANALYSIS.md` (accepted at `dd9f7c6`).

W1-B F1 wrote `open_questions[].status = "resolved_to_peers"` for a fact the
canonical block had settled. The validator refused it because it required the
literal `"resolved"` — a value that appeared **nowhere** in any producer-facing
artifact, and a slot absent from r1's eleven-slot closed-vocabulary table. F1 had
an explicitly taught compliant path (move the fact to `human_confirmations`) and
missed it, but the state it chose had no derivable correct value.

r2 removes the ambiguity by stating the invariant the validator now enforces:

```text
settled human-supplied facts  ->  human_confirmations
unresolved facts              ->  open_questions, status "unresolved" ONLY
no "resolved" open-question state exists
any load-bearing open question refuses, whatever its status claims
```

## The diff — three insertions, no deletions

```text
:126       closed-vocabulary table gains a twelfth slot,
           `open_questions[].status` | `unresolved` only
:148-151   evidence/authority rules gain the disjointness invariant
:196-202   step 6 gains "Settled facts have exactly one home", naming the
           `open_question_status_invalid` refusal
```

r2 is a strict superset of r1's text: nothing was removed or reworded, so any
behaviour r1 elicited remains elicitable.

## Matching validator change

`work_interface/work_definition.py`:

```text
OPEN_QUESTION_STATUS_VOCABULARY = ("unresolved",)
new refusal code  open_question_status_invalid    (vocabulary now 27 codes)
load_bearing_unresolved now fires on ANY load-bearing open question
```

`work_definition_version` stays `0`. This is a v0 **contract correction**, not a
new schema version: no previously PASSing artifact changes verdict — proven
across all 14 frozen artifacts, where the only delta is F1 (already refusing)
gaining `open_question_status_invalid`.

## Deployment status

**r2 is cut but NOT deployed.** `skills/define-lab-process/skill.md` still holds
r1. Deploying r2 there is a separate deliberate act, and it will make
`work_interface/w1a/grade.py`'s live-skill check report drift against the frozen
r1 hash — correctly, since the deployed skill would then differ from the one
W1-A measured. That decision is deliberately left open.
