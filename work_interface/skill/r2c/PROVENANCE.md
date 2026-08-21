# define-lab-process — r2c provenance

**Immutable.** Never edited in place; every prior pack's `SKILL.md` hash stays
valid.

```text
parent    r2    sha256 0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a
this      r2c   sha256 c9f9990133be9a1afb66842160c48d90beff956f6d714c52ad3419b5ef8d9c6d
sibling   r3    sha256 ea259e1a2af8663987d1dd5bed333a0a1ae33701752166a39f1c17446be3d5d5
```

r2c branches from **r2, not r3**. The tokenization line is parked
(`../../w1i/DISPOSITION.md`); dragging r3 into this experiment would put two
variables in one pack.

## What r2c changes — and only this

The **output provenance surface**. `output.reports_fields` and
`output.context_fields` gain the same `basis` / `confirmation` pair that
`body.match_on` and `body.compare[]` already carry.

```json
"output": {
  "reports_fields": [...],
  "context_fields": [...],
  "provenance": {
    "reports_fields": {"basis": "human_confirmed", "confirmation": "«id»"},
    "context_fields": {"basis": "human_confirmed", "confirmation": "«id»"}
  }
}
```

Three edits:

| # | site | change |
|---|---|---|
| 1 | title | revision marker only |
| 2 | the artifact shape | `output.provenance` added |
| 3 | Evidence / authority rules | one bullet requiring it, mirroring the existing match/compare rule |

## What r2c deliberately does NOT do

```text
no reminder prose            no "preserve all six", no "one answer per record"
no strengthened wording      every existing instruction is byte-identical
no tokenization change       r2c is not r3
no other rule, vocabulary, step or prohibition touched
```

The experimental variable is **the representation**, not a stronger
exhortation. `verify_prep` check 19 asserts mechanically that the added lines
contain none of "all six", "every answer", "one answer per", "make sure", "be
sure to", "remember to", "do not omit", and that r2c carries no r3 text.

## Why the slots are required rather than optional

They mirror the existing surface. `match_on` and `compare[]` do not offer an
optional basis — a load-bearing decision carries exactly one. An optional slot
would test a weaker and less interpretable thing: whether the worker
*volunteers* provenance, rather than whether having a place to put it changes
preservation.

## Status

Frozen and immutable. **Not yet used by any executed pack.** W1-K is its first
test, as the treatment arm of a paired differential against r2 + v0.
