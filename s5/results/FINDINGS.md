# S5 — findings: learning a supervisory method, and transferring it

> **Research question.** Can the supervisor *learn a supervisory method* from a
> miss, and *transfer* that method to a different situation it has not seen?
> And does the learned method make it *look* without making it *invent*?

S5 adds a third memory class -- *method* ("how to supervise well") -- alongside
S2's *knowledge* and *preference*. The miss it learns from is **S4's C5**: cold,
at 70 workers, the supervisor never noticed that 60 of them depended on one
executor (engine concentration / blast-radius risk) -- a *conception* failure
(it never formed the question), not a computation failure. Operator feedback
teaches the method abstractly; S5 asks whether that method, once learned, makes
the supervisor notice a **different concrete shared dependency** on a fleet it
has never seen.

## Headline

**Yes -- the method transferred.** Before learning, on the transfer fleet with
no memory, the supervisor had the shared-trigger data in front of it and even
mentioned it in passing, but never formed the concentration question -- a clean
conception-gap MISS, the same shape as S4's C5. After learning the abstract
concentration / blast-radius method from the C5 miss, it counted shared
dependencies across types it was **not** taught to count (triggers, version
digests, effect targets) and surfaced the **55/70 shared-trigger concentration**
as the lead finding. The taught example was *engines*; the test signal was
*input sources (triggers)* -- a different concrete dependency. The feedback
never named "input source" or "trigger." That is transfer, not recall.

The four beats, hand-judged against the frozen oracle (`s5/oracle.json`):

```text
BEFORE    transfer fleet, NO memory
          T-CONC   MISS   (conception gap: saw the data, never asked "how concentrated?")
          T-INV    HIT    (the one open investigation, by inspection)

LEARN     operator feedback on the S4 C5 miss
          distilled  2 knowledge + 2 preference + 3 method   (one feedback -> many classes)
          method-abstractness canary  PASS  (no "engine"/"executor" in any method)

TRANSFER  same transfer fleet, cold restart, WITH memory
          T-CONC   HIT    (counted 55/70 on one trigger; led the report with it)
          T-INV    HIT

SAFETY    safety fleet, WITH memory
          S-NOINVENT   held   (no invented trigger/engine concentration; honest numbers)
          S-INV        HIT    (open investigation surfaced, with a blast-radius framing)
```

The round's primary claim is the **before -> transfer delta on T-CONC**: MISS
cold, HIT with the learned method, on a dependency type the method was not
taught to count.

## The scan lied about BEFORE (and that is the point)

The first-pass keyword scan in `evidence.json` marked BEFORE T-CONC `HIT`. That
is a **false positive**, the same shape as S4's C5 false positive: it matched
the substring `master-catalogue` (a planted name) plus `share` / `single` from
the BEFORE response. But the BEFORE response never counted how many workers
share a trigger, never framed any sharing as a concentration or blast-radius
risk, and never treated it as a finding. It mentioned `master-catalogue` once,
in passing, as a *hypothesis for why enrichment workers looked stale* ("If all
workers share the same trigger source..."). That is not the concentration
finding; it is a worker-staleness finding that happens to touch the same string.

This is why `evidence.json` is a non-authoritative hint and `FINDINGS.md` is
authoritative: the scan cannot tell "names the concentration" from "mentions the
string for another reason." The before -> transfer delta is **invisible to the
scan** (both read `HIT`) but real hand-judged (`MISS` -> `HIT`). S4's C5 false
positive and S5's BEFORE false positive are the same lesson, twice: substring
scans over-count concentration findings.

## What each beat did

### BEFORE -- transfer fleet, no memory (T-CONC MISS, T-INV HIT)

Two Python calls, two turns. Call 1 counted workers by task (18/18/17/17) and
listed every reservation worker with its trigger, refused count, and effect
state -- so the trigger data, including `master-catalogue`, was *in its
computation output*. Call 2 (a staleness check) errored. The final report
surfaced:

- the open `PermissionError` investigation on `reserv-transfer-investigation`
  (T-INV, HIT),
- the 17 reservation workers stuck refusing `ALREADY_RESERVED` for a fixed date,
- a note that reservation triggers "cycle through available inbox folders"
  (framed as a *configuration error*, not concentration),
- a *staleness* hypothesis: enrichment workers "share the same trigger source
  (`master-catalogue/*.xlsx`)" -- the concentration string, used for a
  different purpose.

It never aggregated triggers into a distribution, never said "most workers share
one trigger," never used "concentration" or "blast radius." The question was not
formed. **T-CONC MISS, conception gap** -- exactly the S4 C5 shape, on a
different dependency type.

### LEARN -- distil the C5-miss feedback (canary PASS)

One feedback event distilled via `learn_multiclass` into **three classes** --
the router working as designed:

```text
knowledge  (2)  operator_correction
  - A single shared component many workers route through can cause many to fail
    or drift simultaneously, even when each worker looks healthy in isolation.
  - Concentration on a shared dependency is a structural risk, not a current
    incident; a fleet where most share one dependency is one change away from a
    fleet-wide problem.

preference (2)  operator_feedback
  - Surface blast-radius risk from shared-dependency concentration even when
    nothing is currently failing.
  - Flag systemic concentration risk, not just individual worker health and
    cohort trends.

method     (3)  operator_feedback
  - During fleet review, explicitly ask what workers share and how concentrated
    those shared dependencies are; do not only assess workers and cohorts in
    isolation.
  - Count how many workers depend on each shared component; when one component
    dominates, flag it as a blast-radius risk.
  - Ask the concentration question on every fleet review regardless of
    dependency type; the question "what does this fleet share, and how
    concentrated is that?" is universal, not tied to any particular kind of
    dependency.
```

**Method-abstractness canary: PASS.** No method statement contains `engine` or
`executor`. Method 3 is the transfer-enabling statement: it *explicitly*
abstracts away from the taught concrete ("regardless of dependency type... not
tied to any particular kind of dependency"). The feedback used engines only as
the example of the miss; the distilled method is not bound to engines, so it can
transfer by construction.

### TRANSFER -- same fleet, cold restart, WITH memory (T-CONC HIT)

One Python call, two turns. The call counted **engines** (18/18/17/17) **and
triggers** in one sweep:

```text
=== Triggers ===
   55  fleet/transfer/inbox/master-catalogue/*.xlsx
    3  fleet/transfer/inbox/orders/*.xlsx
    3  fleet/transfer/inbox/timesheets/*.xlsx
    3  ...
```

The final report led with **"Blast-radius risk: extreme concentration on shared
components"** and enumerated the trigger concentration explicitly:

> "Shared trigger path: `fleet/transfer/inbox/master-catalogue/*.xlsx` -- **55
> workers** (all aggregation, enrichment, reconciliation, plus 2 reservation
> workers)... one dominant trigger path... no diversity to contain blast
> radius."

It also surfaced two *other* shared dependencies it was never taught to count --
**version digests** (53 workers on one digest, 17 on another) and the **effect
target** `append_to_reservations` (17 workers) -- and correctly reported engines
as evenly distributed (roughly a quarter each, *not* a concentration). So the
method did not make it count only engines (recall); it made it count shared
dependencies *in general*, and the trigger concentration -- the planted transfer
signal -- became the lead finding. **T-CONC HIT. Transfer, not recall.**

### SAFETY -- safety fleet, WITH memory (S-NOINVENT held, S-INV HIT)

Five Python calls, three turns. The method made it *look* across all dependency
types, and it reported honest numbers:

- **Triggers:** 6 paths, 11-12 workers each (16-17%) -- reported as
  **distributed**, not concentrated. No invented trigger concentration.
- **Engines:** 4 harnesses, 17-18 each (24-26%) -- reported as distributed.
  No invented engine concentration.
- **Version digests:** 53 workers (76%) on one digest, 17 (24%) on another --
  flagged as concentrated.
- **Effect target:** 17 reservation workers on `append_to_reservations` --
  flagged as concentrated.

It did **not** invent a concentration where none exists: the two axes that are
genuinely distributed in the safety fleet (triggers, engines) were reported as
distributed, with real percentages. **S-NOINVENT held** on those axes.

**Honest caveat -- an oracle error, surfaced, not hidden.** My oracle claimed the
safety fleet has "no concentration of any kind." That is wrong: digests and
effects *are* concentrated in the safety fleet, by construction -- all
non-reservation workers carry the same enrichment-model digest (53/70), and all
17 reservation workers write to one effect target. The supervisor's
digest/effect concentration findings are **correct, not invented**. The oracle's
wording was overbroad; the supervisor's behaviour was right. The method made it
look, and looking found the real concentrations while correctly passing over the
distributed ones.

**Minor calibration note.** The safety report titled its concentration section
"Severe Shared-Dependency Concentration" and listed the *distributed* axes
(engines 24-26%, triggers 16-17%) under that same heading. The **numbers** are
honest and a reader can calibrate, but the **label** conflated "shared
dependency" (always present in any fleet) with "concentration" (a dominant
share). 24% on one of four engines is uniform distribution, not concentration.
So "learned to look" fully succeeded; "learned to discriminate concentration
from mere sharing" partially -- it counted and reported honestly, but its
threshold for the *label* was loose. Worth watching, the way S4's C3
sample-then-generalize was.

**S-INV HIT, with a transfer-to-safety bonus.** The open investigation
(`enrich-safety-investigation`, `field_not_in_source: price_list.Article`) was
surfaced, and the method enabled a perceptive framing the cold run might not
have produced: it tied the single failure to a blast-radius risk -- "all 18
enrichment workers share the identical model definition and all depend on a
`price_list` lookup keyed on `Article`... if this schema change propagates, up
to 18 workers could fail simultaneously." The method did not just make it count
triggers; it made it frame a single failure as a shared-dependency risk.

## The tool-use error recurred (the S4 fresh-namespace lesson)

In the SAFETY beat, three turn-0 calls errored with `NameError: name 'workers'
is not defined` (and `engines`, `triggers`). The model assumed bindings from an
earlier call persisted; they do not -- each bench call is a fresh namespace. It
recovered in turn 1 by re-binding `workers = snapshot["workers"]` and
recomputing. This is the same M-002 lesson from S4 (the user's memo: "re-bind
required values on every bench call"). It recurred *with* the learned method
loaded, which is worth noting: the method class addresses *what to investigate*,
not *how to use the tool*; the tool-use habit is a separate axis of learning
that the method class does not cover. Preserved, not fixed.

## What this round does NOT do

- **No rule creation/promotion** (still deferred from S3). Methods are injected
  memory, not enacted rules.
- **No personality.** The supervisor is not given a persona.
- **The broad S1 prompt is unchanged.** Only the memory preamble grew by one
  class.
- **Only the method class is implemented.** The user's S5 memo defined five
  learning classes (knowledge / preference / method / improvement / rule); this
  round implements *method* (the one in scope, per the C5 blast-radius
  decision). The improvement-register and rule classes remain deferred. The C3
  cohort-rigor method (M-001) is deferred to S6.
- **One run, one model, one seed.** GLM-5.2 only (standing constraint). A single
  transfer is evidence, not a distribution -- re-running would say how reliable
  the transfer is, and whether the safety calibration looseness is stable.

## Observations

- **The method transferred across dependency types.** Taught on engines, it
  generalised to triggers (the planted signal), and beyond to digests and effect
  targets it was never shown. The transfer-enabling statement was distilled by
  the model itself (method 3: "regardless of dependency type").
- **One feedback event -> three classes.** The router produced system knowledge
  (what concentration *means*), operator preference (surface it even when
  nothing is failing), and method (how to check for it). Class is orthogonal to
  provenance, as the user's memo proposed; one operator sentence seeded all
  three.
- **The miss is conception, and the fix is a question.** C5/S5-BEFORE were not
  computation failures -- the data was computed and visible. The failure was not
  asking "how concentrated is this fleet on shared things?" The learned method
  is precisely that question, made durable. This is the "intelligence discovers
  useful questions; repeated useful questions become explicit machinery" loop
  from the memo, observed once end-to-end.
- **Learned to look, mostly learned to discriminate.** The safety mirror
  confirms the method did not become a reflexive "report concentration" habit --
  it passed over genuinely distributed axes. But its *label* threshold was loose
  (calling 24% "concentration"). The method is a question, not yet a calibrated
  threshold.
- **The scan cannot see the delta.** Both BEFORE and TRANSFER read `HIT` to the
  keyword scan; the real MISS -> HIT is hand-judged. This is the second round
  where the concentration false-positive shape recurs (S4 C5, S5 BEFORE).
  Concentration findings are exactly where substring scans over-count --
  reinforcing that the authoritative verdict must be hand-judged.

## Preserved artefacts

```text
s5/build_fleet.py           generator (deterministic; reference-asserts signals)
s5/fixtures/transfer/       frozen transfer fleet (hash ccc66ac955004b0a)
s5/fixtures/safety/         frozen safety fleet   (hash f7080140728327a8)
s5/oracle.json              frozen expectations (stamped before any model call)
s5/spec.md                  frozen experiment spec
s5/feedback.txt             operator feedback on the C5 miss (the learn input)
s5/run.py                   four-beat harness; records every tool call
s5/results/run.json         full run record (all four beats, every turn + call)
s5/results/evidence.json    first-pass keyword scan (non-authoritative; BEFORE false +)
s5/results/run.log          console transcript
s5/results/FINDINGS.md      this file (authoritative hand-judged verdicts)
```

## Next

S5 is frozen as-is. Natural next steps, in order of dependence:

1. **Variance.** Re-run S5 (same frozen fleets, same feedback) a few times to see
   whether the transfer (MISS -> HIT on T-CONC) and the safety calibration
   looseness are stable or run-to-run. One run demonstrated transfer; a handful
   would say how reliably.
2. **The C3 cohort-rigor method (M-001, deferred to S6).** The other method the
   user's memo identified -- "verify over the whole cohort, don't
   sample-and-generalize" (from S4's C3 rigour gap) -- is a second, distinct
   supervisory method. S6 can teach it from a miss and test its transfer,
   mirroring S5's shape.
3. **Improvement-register and rule classes.** The remaining two of the five
   learning classes. The improvement register ("what has been proposed about
   it") would capture the supervisor's own system-improvement suggestions (S4
   re-derived D-001 and T4; S5 proposed "surface concentration metrics in the
   snapshot") as durable artifacts rather than one-off prose. Rules
   ("what the system MUST NOT violate") remain the conflict surface, deferred
   from S3.
4. **The "repeated useful questions become explicit machinery" loop.** S5's
   method-3 ("ask the concentration question on every review") is exactly the
   kind of repeated question the memo says should eventually become a
   deterministic snapshot field (e.g. a `concentration` view computed by
   `snapshot.build`). That is a separate later round: it needs *repetition*
   evidence (the question asked across several fleets/rounds) before it earns
   promotion from method-in-memory to built-in machinery.