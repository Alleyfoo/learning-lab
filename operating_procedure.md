# Operating Procedure — Measurement Phase

**Not a conceptual amendment.** Conceptual amendments are closed at
[amendment 003](workorder_amendment_003.md). This document records how the two authorized
measurements are run so they stay independent, and how they combine afterwards.

**Authorized work: exactly two items. Nothing else.**

---

## 1. The two measurements are orthogonal

```text
EXPERIMENT 1                      UQ-1 AUDIT
synthetic / controlled            real archived history

asks:                             asks:
"Does the warrant machinery       "How often do these conditions
 behave as claimed?"               actually occur in business data?"
```

Experiment 1 is a question about the **instrument**. UQ-1 is a question about the **world**.
They must not be allowed to inform each other's design.

---

## 2. Contamination rule

> **Do not use UQ-1 observations to tune Experiment 1 after its preregistered floor/corpus
> sequence has begun.**

Real-history knowledge leaking into the synthetic generator makes the controlled falsification
less clean — the generator starts reproducing the very phenomena the experiment claims to
discover independently.

### 2.1 Enforcement, same mechanism as the floor ordering

The rule is only worth stating if it is checkable. Extend the git-ordering protocol from
[B6.2](workorder_amendment_002.md):

1. Commit the **synthetic generator and corpus specification** before the first archived
   provider file is opened.
2. Record the **archive-access date** in the repository at the moment UQ-1 begins.
3. Any change to the generator or corpus spec committed *after* that date must be justified in
   its commit message on grounds independent of the archive, or the run is re-preregistered.

Anyone reading the history later can verify the ordering. If the two measurements are run by
different people, so much the better, but the commit ordering is the mechanism that does not
depend on that.

### 2.2 The rule is directional, and the reverse direction has its own trap

UQ-1 must not inform Experiment 1's design. The reverse leak is subtler and more damaging:

> **UQ-1 classification must be by what actually changed, never by what would have been
> detected.**

Classifying real historical events as "cosmetic / structural / semantic" according to whether
the mechanism *would have caught them* bakes the mechanism's blind spots into the prevalence
estimate. The combination step in §3 then becomes circular — the machinery looks well-matched to
reality because reality was only counted where the machinery can see.

Classify on ground truth: what the provider changed, established from the files, correspondence
and system-of-record evidence. Detectability is scored separately, afterwards, and never used as
a classification criterion.

---

## 3. Combination, after both complete

```text
Experiment 1:  what can the mechanism distinguish?
                        ×
UQ-1:          how often does the real world present those cases?
                        ↓
        Is the architecture actually worth building?
```

Both outcomes are informative and both are acceptable results:

| UQ-1 finds | Reading |
| --- | --- |
| 24 months × providers: ~96% identical format, ~3% cosmetic, ~1% structural, **0 observed semantic changes** | Impressive machinery solving a rare problem. The economically correct system is L0–L2 plus a synonym store. **Report this plainly and do not build the rest** |
| Constant renames, ERP changes, wide ↔ long, changed grains, changed definitions, missing periods, manual adjustments | The modelling network has a concrete reason to exist, and the human gate is the product rather than an afterthought |

Neither result is a failure of the research. The distribution is the deliverable.

---

## 4. What synthetic RUN B does and does not establish

Named correctly so it is not over-read later:

- **Establishes:** internal calibration stability under the assumed world model.
- **Does not establish:** external validity.

That is not a flaw in the design. It is a flaw only if the limitation goes unnamed and the
result is later cited as evidence the floor holds on real data. It does not.

---

## 5. Sequence

```text
1. Commit synthetic generator + corpus spec        (before any archive access)
2. Compute detection floor from frozen baseline    (commit before corpus exists - B6.2)
3. RUN A  - calibration / falsification
4. RUN B  - separately preregistered certification
5. Record archive-access date; begin UQ-1 audit    (may run in parallel from step 1 onward,
                                                    provided steps 1-2 are already committed)
6. Combine (§3) -> build / narrow / stop decision
```

Steps 1–4 and step 5 may overlap in wall-clock time. They may not overlap in influence.

---

## 6. Standing constraints during the measurement phase

- No agents. No LLM in either measurement.
- No modification to `Data-tool`, `Data-agents`, `Pipe-transformation` or `data-frame-tool`.
  Defect D1 is fixed in the lab copy only.
- No further conceptual amendments. If something genuinely fails in reality, that is a
  measurement result and gets recorded as one — then the architecture may move.
