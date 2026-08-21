# define-lab-process — r3 provenance

**Immutable.** Once committed, this revision is never edited in place. Every
prior pack's `SKILL.md` hash must remain valid, so r2 is untouched and r3 is a
new file.

```text
parent    r2   sha256 0230969ea7fd00edd0989dc19e6f9658bcfedd4320415efe1f6c5e8cfe9a089a
this      r3   sha256 ea259e1a2af8663987d1dd5bed333a0a1ae33701752166a39f1c17446be3d5d5
```

r2 remains byte-identical and is still the skill used by W1-A through W1-H.

## Why r3 exists

W1-G run O2 was refused with `observed_field_not_in_source` for declaring
`" Supplier Name"` — the column name plus the space following the comma
delimiter. Causal analysis (`../../w1g/O2_ANALYSIS.md`, accepted at `fe32ee0`):

```text
proximate cause      PRODUCER_ERROR
architectural cause  SKILL_UNDERSPECIFICATION
```

r2 makes `observed_fields` load-bearing and demands "EXACT strings … verbatim"
from a `, `-delimited line, while containing **zero** occurrences of
`whitespace`, `trim`, `strip`, `padding`, `delimiter` or `tokeni*`. It never
states where a column name begins.

## What r3 changes — and only this

**The interpretation of delimiter-adjacent separator whitespace.**

```text
the comma and the spaces around it are SYNTAX
they are not part of a field name
after tokenization: spelling, case, punctuation and INTERNAL whitespace
are preserved exactly
```

Four edits, all at that boundary:

| # | site | change |
|---|---|---|
| 1 | title | revision marker only |
| 2 | Evidence / authority rules, bullet 1 | separator whitespace named as syntax; worked example added |
| 3 | Procedure step 2 | split on commas, discard separator whitespace, then record verbatim |
| 4 | Prohibitions | "do not normalize" restated as: no re-casing, re-spacing, merging or renaming |

## What r3 deliberately does NOT do

```text
no general "normalize/trim fields" instruction
no change to any other rule, vocabulary, step or prohibition
no change to the validator, the fidelity checker, the capability box or the policy
no attempt to address W1-H P2's dropped human_confirmations
no guidance for headers that are not comma-delimited
```

Edit 4 is a restatement, not a relaxation: it enumerates what "normalize" means
so the prohibition cannot be read as forbidding the tokenization the amendment
just defined. The rule that `Supplier Name` and `SupplierName` are different
fields is preserved verbatim, and the worked example states the
internal-space-removal case as wrong.

**P2's confirmation-preservation failure is a separate producer-contract
problem** (`../../w1h/ACCEPTANCE.md`). It is not addressed here and must not be
folded in later without its own experiment.

## Field vocabulary — deliberate

r3's worked example uses `Supplier Name` (vocabulary r2 already carries) plus
`Region Code`. It introduces no field token belonging to any experiment fixture,
so a later differential experiment can use a fixture whose canonical tokens are
given away by **neither** revision. This is a fairness property of the r3/r2
comparison and must be preserved if r3 is ever superseded.

## Status

Frozen and immutable. **Not yet used by any executed pack.** W1-I is its first
test, as the treatment arm of a differential r2-vs-r3 experiment.
