# v0 — SUPERSEDED, UNRUN

**Status: superseded by [`level4/v1/`](../v1/). Never executed. No evaluator response was ever generated against these inputs.**

Freeze commit: `25f2e74f1b4b533fa2384d18a9ead38c80056bbe`

Nothing in this directory has been edited. It is kept exactly as frozen because an unrun freeze is still a record of what was proposed and why it was wrong — the correction is additive, which is this repository's standing rule for evidence.

## Why it was superseded

Manager's Phase-1 review found two preregistration/provenance defects **before** either arm was run. Both are cheap at that point and expensive afterwards, which is the whole reason the freeze happens before execution.

### 1. The graded inputs had a second varying field

`PREREGISTRATION.md` §3 claims packet B is packet A plus exactly one `untrusted_content` record, and that any material divergence is therefore attributable to the canary.

The evaluator also saw:

```text
A   "snapshot": { "id": "level4-v0-A", ... }
B   "snapshot": { "id": "level4-v0-B", ... }
```

Worse, `build_packet.py --self-test` **normalized those ids away before comparing**:

```python
a2["snapshot"]["id"] = b2["snapshot"]["id"] = "-"
check(a2 == b2, "CANARY: A and B must be identical apart from the injected record")
```

So the assertion that looked like it proved single-variable attribution actually proved *canary plus arm label*. The check was written to pass rather than to bite — the same defect class this repository has corrected twice already, and this time in the freeze discipline itself.

Whether an arm label would in fact sway a model is beside the point. The experiment claims attribution to one manipulated variable, so the graded input must have one.

### 2. `repository_revision` named a commit that does not contain the packet's authority state

Both packets record `"repository_revision": "18209f9..."`. But the freeze commit `25f2e74` is itself what changed `docs/development/initiatives.md` — including I-7 to `Roundtable closed` — and `build_packet.py` parses that register into the packet's `initiative_box`.

The packets therefore carried authority state that does not exist at the revision they name. Anyone reconstructing from `18209f9` would get a different packet and would have no way to know why.

## What v1 changes

| | v0 | v1 |
| --- | --- | --- |
| `snapshot.id` | differs per arm | identical; arm identity lives in `runs/A/` vs `runs/B/` only |
| A/B self-test | normalized ids, then compared | **literal** comparison after removing B's one canary |
| provenance | one `repository_revision`, silently wrong | source revision `25f2e74`, with an explicit split between what is reconstructable from it and what is deliberately untracked runtime state |
| schema | `system_state_packet/v0` | `system_state_packet/v1` — the structure changed, so the name does |

`PREREGISTRATION.md` §8 in this directory says changing a graded input creates a new experiment version. That rule is why v1 is a new directory rather than an amendment here.

## What carried forward unchanged

The evaluator instruction, the `system_verdict/v0` output shape, criteria A–G, the predeclared material-divergence rule, the trust classes, the Supervisor-assessment exclusion and the single-canary constraint were all accepted by Manager and are carried into v1. `level4/v1/check_packet.py` asserts the carried-forward files are byte-identical to the ones frozen here, so "carried forward" is checked rather than claimed.
