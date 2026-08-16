# Learning Lab

Research into a supervisory LLM that sits **above** a deterministic fleet of modelled tasks.

The project started as a data-task modelling study and then crossed into a broader question:

> **What is the main LLM actually for once established work is deterministic, explicit, inspectable, and usually does not need an LLM at runtime?**

The answer emerging from the experiments is not “put an agent in every workflow.” It is closer to:

> **The AI designs, supervises, investigates and improves the workers. The workers do the work.**

This repository is a research lab, not a production framework.

---

## The architecture

The inherited floor is a deterministic task-and-fleet system: task models, workers, inbox/recovery, committing runtime, confirmations, investigations and a system map. Ordinary established work runs without an LLM.

```text
new work       -> LLM helps DEFINE -> deterministic worker
normal work    -> deterministic runtime
something bad  -> exception -> LLM may INVESTIGATE

fleet-wide state / history
        ↓
SUPERVISORY LLM
        ↓
what matters?
what changed?
what should be investigated?
what could the platform improve?
```

The supervisor is not continuously “thinking.” The platform can remain continuously alive while the LLM wakes only when useful: operator request, event, schedule or later reflection trigger.

The deterministic fleet is the **experimental apparatus**. The research target is the intelligence above it.

---

## What the supervisor is for

Four roles have emerged:

| Role | Question |
| --- | --- |
| **Interpreter** | What does a new request mean, and what truths are load-bearing? |
| **Supervisor** | What is happening across the fleet that is worth the operator knowing? |
| **Investigator** | What changed, why did something fail, and what repair is safe to propose? |
| **Reflector** | What keeps recurring, what have we learned, and what should the system improve? |

The important separation is authority:

```text
LLM may observe, analyse, explain and propose
                    ≠
LLM may silently change production authority
```

The established runtime remains deterministic. The supervisor does not promote worker versions, apply effects, mutate customer data or quietly rewrite rules.

---

## The learning idea

“Learning” here does **not** mean updating model weights.

The experiments have produced several distinct things the supervisor can learn:

```text
KNOWLEDGE     what the system means
PREFERENCE    what the operator considers worth attention
METHOD        how to investigate/supervise well
IMPROVEMENT   what could make the platform better
RULE          what the system must not silently violate
```

These are deliberately different objects.

A human correction such as “enrichment workers are non-committing by design” is semantic knowledge, not a mechanically observed fact. An operator saying “do not interrupt me merely because run history is thin” is a preference. A lesson such as “check shared dependencies and blast radius, not only failing workers” is a supervisory method.

The Rulebook is different again: it records institutional constraints such as confirmations being version-bound or successful effects requiring read-back verification.

### The longer learning loop

The direction now being tested is:

```text
LLM invents a useful question
        ↓
uses tools / Python to analyse it
        ↓
the question proves useful repeatedly
        ↓
supervisor proposes a platform improvement
        ↓
Rulebook / authority / human gate
        ↓
mechanical deterministic measurement is added
        ↓
future LLM needs less ad-hoc reasoning for the same fact
```

This is intentionally almost the reverse of “make the agent increasingly autonomous.”

> **If the system learns successfully, repeated intelligence should become cheaper explicit machinery.**

The platform owns mechanically observed facts. The LLM still owns interpretation.

For example:

```text
OBSERVED
55 / 70 workers use dependency X

INFERRED
that concentration creates an important blast-radius risk
```

The second claim must never be laundered into the first.

---

## Supervisor harness

S6 established a small explicit harness around the supervisor rather than adopting a large external agent framework.

The harness owns runtime mechanics:

```text
trigger / operator request
        ↓
SupervisorHarness
  ├─ context providers
  ├─ model interaction
  ├─ scoped tools
  ├─ authority policy
  └─ append-only session events
        ↓
Supervisor LLM
        ↓
0..N tool-assisted steps
        ↓
final output / nothing
```

Current providers/capabilities wrap the existing code rather than replacing it:

- `supervisor/snapshot.py` — read-only fleet context
- `supervisor/bench.py` — restricted Python analysis over copied data
- `supervisor/memory.py` — knowledge, preferences and methods
- `supervisor/rulebook.py` — Rulebook and Improvement register
- `supervisor/harness.py` — explicit tool/context/policy/session boundary
- `supervisor/core.py` — original model loop retained for the earlier experiments

One design rule was borrowed from DeepSeek Harness because it fits this project unusually well:

> **Anything model-visible must be reconstructable from the session record.**

S6 records context, declared tools/authority, every model request/response, every tool call/result and the final supervisor output in an append-only session log.

### Authority floor

The harness may allow capabilities such as:

```text
read fleet state
analyse copied data
read knowledge / preferences / methods / rules
write supervisor-owned session history
write supervisor-owned improvement proposals
```

It explicitly denies production authority such as:

```text
modify workers or models
promote versions
execute the production runtime
apply effects
alter customer/source data
unrestricted filesystem
shell
network
```

---

## Experiments S1–S6

The current research staircase is deliberately empirical: each round is frozen before moving to the next.

### S1 — What is worth telling me?

A cold supervisor reviewed small read-only fleet snapshots with an optional Python bench.

It surfaced a real failed effect and distinguished healthy refusals from failures, but over-reported on a boring healthy worker and misread some system semantics. It also found genuine fleet-level reporting defects unprompted.

Python use: **0/4 runs**. At that scale, the fleet was readable directly.

See [`s1/results/FINDINGS.md`](s1/results/FINDINGS.md).

### S2 — Can feedback change supervision?

The S1 failure was split into two persistent memory classes:

- system semantic knowledge from operator correction;
- operator supervision preference.

The memory transferred to a genuinely different enrichment worker: the supervisor stopped repeating the S1 architecture misreads and low-value warnings, while still leading with a real failed-effect condition.

This established that experience can change interpretation and attention threshold **without changing the workers underneath**.

See [`s2/results/FINDINGS.md`](s2/results/FINDINGS.md).

### S3 — Improvement Box + Rulebook

The supervisor was given a durable Improvement register and a small Rulebook seeded only with already-established architectural constraints.

It correctly distinguished:

- a compatible real improvement;
- a semantic duplicate of that improvement;
- a proposal that conflicts with version-bound confirmations;
- a mirror proposal on the same topic that respects the rule.

The conflict stayed stable across rule ordering permutations.

Core principle:

> **An improvement may contradict an active rule. It may not do so silently.**

See [`s3/results/FINDINGS.md`](s3/results/FINDINGS.md).

### S4 — Does scale trigger computation?

A cold supervisor reviewed a frozen 70-worker / 473-run fleet with the same broad prompt and no memory, rulebook or personality.

At ~77k tokens of fleet state, it autonomously reached for the Python bench: **4 calls across 3 turns**, with no instruction to use Python.

It computed cross-worker/time-series findings such as:

- rising refusal trends;
- post-promotion regressions;
- stale confirmations after promotion;
- actual exception state minus fleet-reported exceptions.

It hit **6/7** planted signals. The clean miss was executor concentration: the data existed, but the supervisor never formed the concentration question.

See [`s4/results/FINDINGS.md`](s4/results/FINDINGS.md).

### S5 — Can a supervisor learn a method?

The S4 concentration miss became operator feedback:

> consider shared dependencies and blast radius, not only individual worker health.

The distiller produced a new **method** memory class. The learned method was deliberately abstracted away from the taught example (engines).

On a different fleet, the cold supervisor missed a 55/70 shared-input concentration. With the learned method loaded, it counted and surfaced that different dependency type, and also noticed other concentrations it had not been taught explicitly.

A distributed mirror showed that the method mainly taught the supervisor **to look**, rather than simply to invent concentration everywhere.

See [`s5/results/FINDINGS.md`](s5/results/FINDINGS.md).

### S6 — Supervisor Harness Floor

S6 was a refactor/proof round, not a new intelligence experiment.

The frozen S4 fleet was re-run through the explicit `SupervisorHarness`.

| | Old S4 loop | Harnessed S4 |
| --- | ---: | ---: |
| Python calls | 4 | 4 |
| Turns | 3 | 2 |
| Python errors | 2 | 0 |
| Hand-judged signals | 6/7 | 6/7 |
| Reconstructable session | no | yes |
| Authority boundary | implicit | explicit |

The intelligence result stayed the same, including the same concentration miss. The recurring fresh-namespace `NameError` disappeared because the Python tool contract finally stated that each call receives a fresh namespace; the bench semantics themselves were not changed.

See [`s6/results/FINDINGS.md`](s6/results/FINDINGS.md).

---

## Evidence discipline

This lab tries hard not to turn one successful run into a universal claim.

Recurring practices include:

- freeze expectations before model calls;
- preserve misses and surprising outputs;
- mirror/counterexample cases;
- permutation tests where ordering could confound a result;
- distinguish mechanically observed facts from LLM inference;
- distinguish operator correction from mechanical truth;
- keep historical experiments frozen;
- treat keyword scans as hints, not authoritative semantic grading;
- record model/tool transcripts and provenance.

Several rounds intentionally document errors in their own oracle or first-pass evaluator rather than silently correcting the result after the fact.

Individual experiments are still generally **one model / one seed / one run**, so they are evidence of behaviour, not a distribution of reliability.

---

## Current direction

The next research direction is to close the learning loop:

> **When a supervisory question repeatedly proves useful, can it be proposed, conflict-checked and human-approved into a deterministic platform measurement — while keeping fact and interpretation separate?**

The concentration/blast-radius method is a natural first candidate because it now has a history across S4–S6.

The intended test is not merely “can we add another field to the snapshot?” It is whether the full authority path works:

```text
repeated useful analysis
→ improvement proposal
→ rule/conflict check
→ human approval
→ deterministic measurement
→ cheaper future supervision
```

No autonomous self-modification is authorized.

---

## Repository history

This repository inherited the full history and tags of `Alleyfoo/Data-Task-Modelling-Lab`.

The old source repository was frozen at `bb128b8` / tag `learning-lab-start`; active development continues here. [`MIGRATION.json`](MIGRATION.json) records the crossing.

Older root-level research documents and experiment directories are intentionally preserved. They are the history and deterministic floor that led to the current Learning Lab; they are not the best starting point for understanding the current research target.

For the detailed chronological state, see [`.handoff.md`](.handoff.md).

---

## Status

**S1–S6 complete and frozen.**

Current floor:

```text
S1  supervisor can notice
S2  supervisor can learn meaning + attention
S3  supervisor can reason against institutional rules
S4  supervisor can invent computation at fleet scale
S5  supervisor can learn and transfer a way of investigating
S6  supervisor has an explicit auditable harness and authority boundary
```

The project is now testing whether useful intelligence can teach the deterministic platform what should become ordinary machinery — without giving the LLM silent production authority.
