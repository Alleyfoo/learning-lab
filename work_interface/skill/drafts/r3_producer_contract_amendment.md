# DRAFT — r3 producer-contract amendment: separator whitespace is syntax

> **STATUS: DRAFT. NOT DEPLOYED. WIRED TO NOTHING.**
> This file is not a skill. It is not loaded by any pack, is not referenced by
> any harness, and does not affect W1-H. `skill/r2/skill.md` is **unchanged**.
> **W1-I owns this change, and only after W1-H is closed.**

## Why

W1-G O2 was refused with `observed_field_not_in_source` for declaring
`" Supplier Name"` — the fixture's column name plus the space that follows the
comma delimiter. Causal analysis (`../../w1g/O2_ANALYSIS.md`, accepted at
`fe32ee0`):

```text
proximate cause      PRODUCER_ERROR
architectural cause  SKILL_UNDERSPECIFICATION
```

r2 makes `observed_fields` load-bearing and demands "EXACT strings … verbatim"
from a `, `-delimited line, but contains **zero** occurrences of `whitespace`,
`trim`, `strip`, `padding`, `delimiter` or `tokeni*`. It never says where a
column name begins. The validator strips its own reference tokens
(`work_definition.py:201`, `c.strip()`) and then compares the producer's value by
exact equality — an asymmetry the producer is never shown and is forbidden by
prompt from inspecting.

The gap is one sentence wide: **is the separator's whitespace part of the name?**

## Scope of this amendment

**Only** the tokenization boundary. Every other exact/verbatim requirement stays
exactly as r2 states it.

```text
CHANGED    delimiter-adjacent whitespace is SYNTAX, not part of the field name
UNCHANGED  observed_fields must be the EXACT header strings, in order
UNCHANGED  do not normalize, merge, or rename
UNCHANGED  `Supplier Name` and `SupplierName` remain different fields
UNCHANGED  internal spacing, case, punctuation and spelling are preserved exactly
UNCHANGED  human answers recorded verbatim
UNCHANGED  every other rule, vocabulary, step and prohibition in r2
```

## Proposed text

Replace the first bullet of **Evidence / authority rules** (r2 L131–134):

> - **`observed_fields` must be the EXACT strings from the fixture's `Header:`
>   line, in order.** Do not normalize, merge, or rename. `Supplier Name` and
>   `SupplierName` are different fields; if you write `SupplierName` when the
>   header says `Supplier Name`, the artifact is refused. Read the header, copy
>   each column name verbatim.

with:

> - **`observed_fields` must be the EXACT column names from the fixture's
>   `Header:` line, in order.** The header is a delimited list: the comma **and
>   any spaces around it are separator syntax, not part of a column name.**
>   Split on the commas, then discard leading and trailing whitespace from each
>   name — that discarding is the only alteration permitted, and it is not
>   "normalizing". Everything inside the name is preserved exactly: spacing,
>   case, punctuation and spelling. Do not normalize, merge, or rename.
>   `Supplier Name` and `SupplierName` are different fields; if you write
>   `SupplierName` when the header says `Supplier Name`, the artifact is
>   refused. For `Header: Date, Supplier Name, InvoiceNumber`, the column names
>   are exactly `Date`, `Supplier Name`, `InvoiceNumber` — **not**
>   `" Supplier Name"` with a leading space.

And amend the corresponding step (r2 L168–169):

> 2. **Inspect the two sample files** … find the `Header:` line, and record the
>    column names **verbatim**.

to:

> 2. **Inspect the two sample files** … find the `Header:` line, split it on the
>    commas, discard the whitespace around each name, and record the column
>    names **verbatim** from there.

And the prohibition (r2 L222):

> - Do not normalize or "fix" field names. Copy header strings verbatim.

to:

> - Do not normalize or "fix" field names — do not re-case, re-space, merge or
>   rename them. Copy each column name verbatim once the separator whitespace
>   around it has been discarded.

## Why phrased this way

- **Names the whitespace as syntax**, which is the actual missing concept. A
  rule phrased as "remember to trim" would sit in direct tension with "do not
  normalize"; calling the padding *separator syntax* removes the contradiction
  instead of adding an exception to it.
- **Keeps the rename counterexample**, which is load-bearing for a different
  failure mode and was never at issue.
- **Adds a worked example with real values.** r2's two `observed_fields`
  examples are both `«placeholders»`; the correct token for this field is
  currently recoverable only incidentally, from a backticked string inside the
  rename counterexample.
- **States the negative case explicitly** (`" Supplier Name"` is wrong), because
  that is the observed failure.
- **Does not reveal the validator.** It states the producer's contract, not
  `c.strip()`. The producer is still forbidden from inspecting the validator,
  and the skill must remain readable as a process definition rather than a
  restatement of a checker.

## Deliberately excluded

```text
no change to the validator                 accepted as-is, no contract change
no change to any other r2 rule             this is one boundary, not a rewrite
no change to the fidelity checker
no change to the capability box or policy
no guidance on headers that are not comma-delimited   out of scope, unobserved
no tolerance for internal whitespace differences      that must stay a refusal
```

## Before W1-I may adopt this

1. **W1-H must be closed first.** Adopting a producer-contract change inside the
   transport-measurement pack would confound both.
2. The amendment becomes **r3**, a new frozen revision with a new sha256. r2 is
   never edited in place — every prior pack's `SKILL.md` hash must stay valid.
3. W1-I's declared variable is then *the producer contract*, exactly one change
   from W1-H, and its own preregistration states what would count as the
   amendment working: `observed_fields` accepted on all runs, with no other
   layer regressing.
4. **N=3 cannot show that the amendment fixed anything.** W1-G's failure was 1
   of 3, sporadic, and appeared in one of six fields in one of three
   occurrences. A clean W1-I is consistent with the amendment working *and* with
   the slip simply not recurring. That limit must be stated in W1-I's
   preregistration up front, not discovered afterwards.
