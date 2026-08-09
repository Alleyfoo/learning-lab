# Experiment 2 — Agent-Discovered Data Normalization

**Research question:** can an agentic modelling system independently discover a *reusable*
normalization procedure across different data shapes, languages, naming conventions and locale
representations, **without being given the normalization strategy**?

The experiment succeeds by answering that clearly, including failures. It does not succeed
because files eventually get converted.

## Status

| Stage | State |
| --- | --- |
| Canonical dataset (hidden ground truth) | **done** — 77 rows, 4 countries, 5 products, 6 periods |
| 25 variants: 12 dev + 8 held-out + 5 ambiguity | **done** |
| Reuse corpus (same profiles, new canonical seed) | **done** — 66 rows |
| Task packet (agent-facing, leak-checked) | **done** |
| Procedure contract + deterministic executor | **done** |
| Evaluator, 7 measurement families | **done, validated by oracle** |
| **Agent run** | **not started** |

## What the agent receives

`artifacts/task_packet/` — `TASK.md` (objective, canonical schema, interface), `contract.py`,
and 12 development source files. Nothing else.

It is **not** told to find January, pivot or unpivot, use a synonym dictionary, infer locale,
use ISO country codes, canonicalize dates a particular way, use positional month relationships,
use regexes, or write lookup lists. Those are candidate solutions; discovering one is the
experiment.

## What is hidden

`artifacts/canonical.csv`, `artifacts/canonical_manifest.json`, `artifacts/corpus_manifest.json`
(labels: `canonical_source`, `representation_family`, `expected_output`, `equivalent`,
`ambiguity_expected`), the held-out and ambiguity source files, and
`harness/reference/oracle_reference.py`.

## Representation coverage

| Dimension | Development | Held out |
| --- | --- | --- |
| Shape | wide, long, period-value | same three |
| Month | ISO, `MM/YYYY`, `M/YYYY`, `MM`, `M`, en full/abbr/UPPER, fi full/abbr, de full | **sv, cs, fr, es** |
| Headers | en, fi, de | **sv, cs, fr, es** |
| Country | ISO2, ISO3, en, en-alt, endonym, formal endonym, fi/de exonyms | **sv, fr exonyms** |
| Numbers | `1234.50`, `1,234.50`, `1 234,50`, `1.234,50`, `1'234.50`, NBSP | same |
| Cosmetic | case, whitespace, NBSP, `;` separator | same |
| Mixed conventions | 2 profiles | 4 profiles |

Several profiles deliberately mix — English headers with Finnish month names and German
exonyms, Czech headers with Spanish months — so nothing can assume one file equals one locale.

## Running

```bash
python generator/canonical.py && python generator/render.py
python generator/canonical.py --seed 31415926 --suffix _reuse
python generator/render.py --suffix _reuse --no-packet
python harness/evaluate.py <submitted_procedure.py> --phase main
python harness/evaluate.py <submitted_procedure.py> --phase reuse
```

## Reported separately, never collapsed into one number

1. output correctness · 2. format coverage **by family** · 3. generalization (dev vs held-out) ·
4. correct refusal on ambiguity · 5. **incorrect canonicalization** · 6. unnecessary escalation ·
7. procedure reuse · 8. human questions

5 and 6 are a **pair** — too aggressive produces wrong equivalences, too conservative produces
needless escalation. Neither is reported without the other.

## Deliberately out of scope

Multiple sheets, workbook relationship discovery, cross-file joins, databases, warehouse output,
email, production APIs, UQ-1 historical research, UI, general agent-OS functionality.
