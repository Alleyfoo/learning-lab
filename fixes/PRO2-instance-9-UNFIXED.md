# PRO-2 instance 9 — found by the value-domain corpus. **NOT FIXED.**

**Status: frozen unfixed**, following the discipline established for instance 8.
The chronology is the result; a fix in the same breath would blur what was known
when.

## The defect

Ingestion silently strips leading and trailing whitespace, so a value declared
`string` does not survive the boundary intact.

```text
case              admitted                 emitted
single_space      str(' ')            ->   str('')
bool_padded       str(' true ')       ->   str('true')
trailing_space    str('abc ')         ->   str('abc')
```

`WorkbookView.row_values()` returns `str(v).strip()`. A `string` declaration
authorises **representation as text and nothing else** — not whitespace removal.
Nothing in the recipe asked for it, nothing records that it happened, and the
emitted value is not the admitted value.

`single_space` is the sharpest of the three: a cell containing one space becomes
an empty string, which is a change of *blank/non-blank* semantics rather than a
cosmetic tidy. Anything downstream distinguishing "present but blank" from
"absent" is reading a different fact than the file contains.

## Why it is the same family

Eighth instance was a declared effect silently **lost**. This one is a value
silently **changed**. Both are the same shape: one layer applies an
interpretation another layer never declared, and nothing compares the two.

```text
No Partial Honour             accepted semantics must not silently disappear
No Undeclared Interpretation  semantics must not silently appear   <- this one
```

## The method chronology, extended

```text
author-written property generation   720 cases        -> 0 novel defects
grammar-derived composition          606 combinations -> instance 8
value-domain corpus                   22 values       -> instance 9
```

Both generated corpora found a defect on first application; the hand-written
suite found none. The reason is the same both times: **nobody writes a test for
a value that is merely a space.** It is not an interesting value. The language
permits it, and a corpus enumerating value shapes has no sense of interesting.

Worth stating precisely: this is now **two** data points for the method, not one.
It is still two, and two is not a trend.

## What the corpus did NOT find

Recorded because absence of a finding is only informative if it is stated:

- **Unicode normalisation did not occur.** `é` composed and `é` decomposed both
  survived byte-identical. The corpus was built expecting this to be a live
  question and it is not — for this ingestion path.
- **No numeric coercion of numeric-looking strings.** `"00123"`, `"1.0"`,
  `"1,0"`, `"1e6"`, `"NaN"` all emitted unchanged under a `string` declaration.
- **No date parsing.** `"03/04/2026"` and `"3.2.2026"` emitted unchanged. Gap G1
  remains a *declared-but-unhonoured* type rather than a silent guess, which is
  the correct side of that boundary.
- **Real `int` and `float` cells** emitted as `"123"` / `"1.5"` under a `string`
  declaration — authorised representation, not a violation.

## One boundary question, deliberately not called a defect

A cell containing `=SUM(A1:A2)` was admitted as `None` and emitted as `""`,
because ingestion uses `data_only=True` and the fixture has no cached value.
Under the stated rule that is *authorised representation of an absent value*, so
`no_undeclared_interpretation` correctly did not fire.

But a person opening that workbook in Excel sees a computed number where the
system sees nothing. That is the **white-text family** again — human and machine
reading the same file differently — and it belongs with that question, not this
one. A real Excel-saved file would carry a cached value; a synthetic one does
not, so this fixture cannot settle it.

## When it is fixed

The fix is not simply "stop stripping". Stripping exists because header matching
and label rules want it, and removing it blindly would change `@name` resolution
and `label_in` behaviour. The honest shape is a **declared** normalisation:
ingestion preserves the value, and any normalisation a construct needs is applied
at that construct and named in the contract — the same treatment every other
capability now gets.

A parity invariant should follow it:

> a value emitted under a `string` declaration is byte-identical to the value
> admitted, or the normalisation applied is one the language declares.

Not started, so this record describes only what was known when it was written.
