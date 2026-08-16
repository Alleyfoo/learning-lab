# Experiment AB — an operand role is a claim, not a column name

**STATUS: FROZEN before any run.**

## The gap a real workbook exposed

The April invoicing job produced correct money and asked nothing. But
`price_list` carried `Unit price` **and** `VAT rate`, both numeric, both
measured. Choosing the wrong one changes the money, and **only the field name
distinguished them.** The answer was right because the column was well named,
not because anything established it — precisely the evidence T through Y
established must not become authority.

Coverage settles *which rows go together*. It says nothing about *which columns
are the operands*.

## The independent evidence

Arithmetic reconciliation against a column **this chain did not produce**:

> An operand pair is MECHANICALLY SUFFICIENT when it is the SOLE pair that
> reconciles completely against an independently supplied target column.

`Checked total` comes from the customer's own system. A pair that reproduces it
is supported by evidence nobody here manufactured — independent of naming in
exactly the way a second field name is not.

## Three conditions

```text
A   Qty x Unit price == Checked total, 4/4       name and arithmetic AGREE
    expected: proceed on `Unit price`, no question

B   the columns were swapped on entry.
    Qty x VAT rate == Checked total, 4/4         name and arithmetic DISAGREE
    expected: proceed on `VAT rate` -- the WORSE-named field -- and REFUSE
    `Unit price`

C   no Checked total column at all               no independent evidence
    expected: one precise question, then persist the answer
```

**B is the experiment.** A system that follows the name passes A and C and fails
B. Getting A right proves nothing on its own.

Verified mechanically before any model ran: the observer reports one reconciling
pair in A (`Unit price`), one in B (`VAT rate`), none in C.

## Checks

```text
AB-1  measured        the observer reports reconciliation without interpreting
AB-2  discriminates   A accepts Unit price and refuses VAT rate; B accepts VAT
                      rate and REFUSES Unit price; C refuses both
AB-3  asks in C       triage marks the operand role load-bearing only when
                      nothing reconciles
AB-4  quiet in A/B    triage does NOT ask when a pair reconciles
AB-5  persists        a human answer settles it, a contradicting model is
                      refused, and later runs need no one
```

## Stated limitation

One operation (`multiply`), one target column, three rows of price data, two
candidate operands. Reconciliation needs an independently supplied answer
column; a workbook without one falls to C and asks — which is correct, and also
means this evidence is unavailable on most first contact. Division, addition,
multi-step formulas, rounding-tolerant reconciliation and operand roles inside
the driving source are all untested.
