# UQ-1 — Retrospective Archive Audit

**Status: instrument ready, awaiting data.** No archived provider files are in this repository.

The highest-value unknown in the whole study, and it needs no software beyond arithmetic:

> How often do these conditions actually occur in real business data?

| | |
| --- | --- |
| Protocol | [classification_protocol.md](classification_protocol.md) |
| Recording sheet | [register_template.csv](register_template.csv) → copy to `register.csv` |
| Summariser | `python uq1_audit/summarize.py` |

## Orthogonality

```text
EXPERIMENT 1 (closed)             UQ-1 (this)
synthetic / controlled            real archived history
"Does the warrant machinery       "How often do these conditions
 behave as claimed?"               actually occur?"
```

They must not inform each other's design. Experiment 1 is frozen at `exp1-runA-final`; its
generator and corpus spec were committed before any archive is opened, which is the
enforcement mechanism for the contamination rule.

## The one rule that is easy to break

**Classify by what actually changed, never by what would have been detected.** Otherwise the
mechanism's blind spots get baked into the prevalence estimate and the combination step becomes
circular — the machinery would look well-matched to reality because reality was only counted
where the machinery can see.

`grain_declared_would_catch` is the only detectability field, and it is filled in a **second
pass** after classification is locked.

## To start

Supply 12–24 months of archived deliveries from 1–5 providers, plus any correspondence that
would establish a confirmed definition change, plus whatever external totals exist for anchor
availability. Record the archive-access date and commit it before classifying.
