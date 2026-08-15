# Authority Path — FREEZE v1 (designer, 2026-08-15)

**Tag: `authority-path-v1`.** No new mechanisms are added by this freeze. It
records what the current implementation is *intended* to guarantee, the evidence
for each guarantee, and the known residuals — so that later it is answerable
which guarantees existed when.

## What is frozen

```text
recipe declares X
     -> executor may degrade X
     -> degradation stays attached to the result
     -> reviewer is shown it
     -> approval records exactly what was shown
```

Implementing artifacts, hash-pinned in `frozen_manifest.json`:

```text
experimentL/harness/execute_recipe.py           degradation, derived
definition_phase/harness/approval.py            review-v3, record + verifier
scripts/check_surfaced.py                       the Observable Error check
definition_phase/design/observable_error_v1.md  the rule
```

A change to any of these after this freeze is a **re-freeze** and belongs in a
commit that says so. Do not edit a recorded hash to make a check pass.

## Three facts that must never be conflated

The whole freeze rests on keeping these apart:

```text
1. SYSTEM KNEW          Execution.degraded
2. HUMAN COULD KNOW     review-v3 actually displayed it
3. HUMAN AUTHORISED     approval binds the rendered view + renderer version
   UNDER THAT EVIDENCE
```

> If it was not in the review surface, it was not part of the approval evidence.

"It was somewhere in the object, so technically the reviewer had access" is the
inference this freeze exists to forbid. It is OPEN-2's mistake restated, and it
is available again every time a new diagnostic is added anywhere in the system.

## Guarantees, and the evidence for each

### G-1 Declared semantics cannot silently degrade without the result saying so

*Mechanism:* `Execution.degraded` / `.degradation`, derived from execution state,
not assignable, and placed by `as_dict()` alongside `columns`/`rows`.

*Evidence:* `scripts/check_surfaced.py --self-test` — clean result not degraded;
an unhonourable declaration degrades and names its gap; table and flag are one
artifact; `degraded` is derived and **not assignable**; incomplete-by-fact is not
flagged; G1 and G2 both degrade; **canary fires** on a suppressed flag.
Supporting: `numeric_breadth` run 2 `BREADTH_HONEST` (0 silently wrong).

### G-2 Degradation in the result does NOT imply informed approval

*Mechanism:* fact 1 and fact 3 are recorded separately and neither is derived
from the other. `verify()` never consults `Execution`.

*Evidence:* `approval.py --self-test` case 7 — a `review-v2` approval of a
**degraded** recipe is `historically_valid = True` and
`meets_current_review_policy = False`. The degradation existed in the execution;
the approval is still not credited with it.

### G-3 The current review shows degradation explicitly

*Mechanism:* `_render_v3` — declared types, observed-on-this-workbook, and a
`RESULT DEGRADED` / `RESULT NOT DEGRADED` line. Observed values come from the
**executor**, not a reimplementation of its coercion rules.

*Evidence:* `approval.py --self-test` case 7 — `RESULT DEGRADED` absent from v2,
present in v3, and v3 names *which* declaration was unhonoured. Case 8 CONTROL —
the same workbook with the one unhonourable declaration typed `string` renders
`RESULT NOT DEGRADED` and names nothing.

### G-4 Approval binds the exact review representation and version shown

*Mechanism:* `review_view_hash` + `renderer_version` on `ApprovalRecord`;
`verify()` recomputes under the record's **own** renderer.

*Evidence:* `approval.py --self-test` case 4 — a renderer whose OUTPUT changes
while its version string does not is caught by the view hash. Case 6 — a renderer
that is *gone* reports `RENDERER_UNAVAILABLE`, distinguishable from tampering.

### G-5 Old approvals stay historically valid but do not inherit newer protections

*Mechanism:* the `historically_valid` / `meets_current_review_policy` split.

*Evidence:* `approval.py --self-test` case 5 (a `review-v1` approval) and case 7
(a `review-v2` approval): both remain historically valid, neither meets current
policy, and the reason names both renderers.

## Limits — equally part of the freeze

```text
L-1  proven that evidence was SHOWN  !=  proven the human READ or UNDERSTOOD it
     The record binds what was rendered. Attention and comprehension are
     outside anything this mechanism can establish.

L-2  result-object inseparability  !=  a downstream UI cannot hide the field
     `as_dict()` cannot be serialised without `degraded`. No in-process
     mechanism can stop a consumer choosing not to display what it was handed.

L-3  DEGRADATION UNKNOWN  !=  NOT DEGRADED
     A recipe that cannot execute yields UNKNOWN. Reading that as "clean" would
     rebuild the exact silence this path exists to remove.

L-4  `degraded` is derived from `unhonoured_types` ALONE
     Any degradation mode that does not produce an unhonoured type is invisible
     to it. Dropped rows, partial honour and undeclared output are governed by
     other invariants (no_partial_honour, no_undeclared_output, cross-sheet
     laws 2-6) and are NOT covered by this flag.

L-5  the evidence is self-tests and author-chosen corpora
     Observable Error v1, review-v3 and cross-sheet laws 2-6 are INSTRUMENT
     work. No probe, no model, no preregistered experiment stands behind them.
     Each law's own stated limitation carries forward unchanged.

L-6  a green test can stop exercising what its name claims
     Found inside this very path: `approval.py` case 4 patched
     `RENDERERS["review-v2"]` by NAME while the record under test used
     CURRENT_RENDERER_VERSION, so it silently stopped testing anything the
     moment v3 became current. It would have kept passing indefinitely.
     Retained as a limit on the EVIDENCE, not on the mechanism.
```

## What this freeze deliberately does not do

No signing, no chains, no timestamps, no `review-v4`. There is no adversary in
this trust domain and no transit; those mechanisms answer questions nobody has
yet shown this system to have. They wait for evidence that they are needed.

## Change protocol

1. Any edit to a pinned artifact is a re-freeze, justified in its commit message.
2. Adding a guarantee requires adding its evidence in the same commit.
3. Removing or weakening a guarantee must say so explicitly — a guarantee that
   quietly weakens is worse than one never claimed (cross-sheet law 2 was
   weakened by designer ruling on 2026-08-15 and recorded, not rewritten).
