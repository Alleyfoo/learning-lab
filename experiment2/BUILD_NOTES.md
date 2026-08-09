# Build Notes — Experiment 2

## Reuse assessment (required before coding)

Inspected `Alleyfoo/Data-tool` @ `ab10b8c`.

| Candidate | Decision |
| --- | --- |
| `src/services/schema_candidates.py::_normalize_month` — fi/en/sv/de month tokens | **Declined.** Covers fi and en completely but sv and de only partially, and has no cs/fr/es. Experiment 2 needs complete tables for seven locales; a half-copied partial table would have to be audited and completed anyway, and would muddy provenance for no real saving. Written fresh in `generator/vocabulary.py` |
| `src/config.yaml` synonyms | **Declined.** English-biased business terms, not the multi-locale header vocabulary this experiment needs |
| Country / locale data anywhere in the four repos | **None exists.** Searched all four; no country, locale or ISO data at all. Written fresh |
| `Template`, `filter_and_rename`, `DataEngine`, pandera schema | **Not applicable.** The artifact here is a submitted Python procedure behind a fixed interface, not a declarative template |
| Experiment 1 harness | **Not reused.** Different question (warrant vs normalization), different artifact, different metrics. Sharing would couple two experiments that must stay independent |

**Net: nothing copied.** No imports from, and no format compatibility with, any existing repo.
This is the "fresh code is preferred when adapting old machinery would cost more" rule applied
honestly — the inspection was real and the answer was no.

## Design decision: the procedure format is deliberately strategy-neutral

The agent submits a **Python module** exposing `normalize(source_path) -> DataFrame`.

A richer DSL was rejected. Any vocabulary of primitives — `unpivot`, `map_lookup`,
`parse_locale_date` — would disclose the strategy, which is the one thing the workorder forbids.
Plain Python expresses any procedure and hints at none. `contract.py` adds only the output schema
and two ways to decline.

## Integrity mechanisms

| Mechanism | Purpose |
| --- | --- |
| `artifacts/canonical.csv` hidden | Ground truth never enters the task packet |
| `artifacts/corpus_manifest.json` hidden | `equivalent`, `ambiguity_expected`, `expected_output`, `representation_family` are labels, not inputs |
| Task packet built by explicit copy, then leak-checked | Only `TASK.md`, `contract.py` and the 12 development sources are exposed |
| Held-out locales absent from every dev profile | sv/cs/fr/es months, headers and exonyms appear only in held-out variants |
| Separate reuse corpus, different canonical seed | "Later matching files" test reuse, not recall of values |
| Round-trip guard in `render.py` | An `equivalent=True` variant may not destroy information |
| Oracle reference confined to `harness/reference/` | Validates the evaluator; never enters the packet |

## A corpus bug the oracle caught

The first validation run scored the reference at 0.95, failing `D08` with 77 value mismatches.
Cause: `D08` used the `int_plain` number style, which **rounds away the decimals**. The file was
labelled `equivalent=True` but was not information-preserving — no procedure could have recovered
the canonical values.

Without a reference procedure this would have surfaced later as an unexplained agent failure and
been misattributed to the agent. That is the argument for building the oracle before the run.

Fixed twice over: `D08` switched to `plain`, and `render.py` now **asserts** that every
`equivalent=True` variant round-trips through `format_number`/`parse_number`, refusing to build a
corpus containing a lossy "equivalent" file.

## Evaluator validation

Oracle reference, both phases:

| | main | reuse |
| --- | --- | --- |
| Output correctness (equivalent) | 1.0 | 1.0 |
| Generalization dev / held-out | 1.0 / 1.0 | 1.0 / 1.0 |
| Correct refusal on ambiguity | 1.0 | 1.0 |
| Incorrect canonicalization | 0 | 0 |
| Unnecessary escalation | 0 | 0 |
| Families below 1.0 | none | none |

This establishes that the harness can recognise a correct procedure and correctly refuses all
five ambiguity cases. It says **nothing** about how hard the task is for an agent — that is the
actual experiment, and it has not been run.

## Known limitations, recorded now

1. **The executor is process isolation, not a security sandbox.** Submitted code runs with this
   user's privileges. Acceptable for a local experiment; not acceptable for untrusted submissions.
2. **One canonical dataset, one business domain.** Whether findings transfer to other domains is
   untested and out of scope.
3. **The ambiguity set is five hand-built cases**, chosen to be individually diagnostic rather
   than statistically representative. It measures whether refusal happens, not how often
   ambiguity occurs — that is UQ-1's question.
4. **`AskHuman` is offered but its classification is manual.** The evaluator records questions;
   deciding whether each was inferable from the source is a human judgement.
