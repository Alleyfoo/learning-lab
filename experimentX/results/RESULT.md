# Experiment X — RESULT: the chain holds on a relational binding

Frozen at `9394d35`. Three probes, three stages. One run voided for a harness
bug before any grading (see `void_wrong_prompt/`).

```text
probe    X1     X2     X3     X4     X5     X6
probe1   pass   pass   pass   pass   pass   pass
probe2   pass   pass   pass   pass   pass   FAIL*
probe3   pass   pass   pass   pass   pass   pass
```

`*` probe 2 did not fail. It blocked a second time, correctly. See below.

## The join binding was refused 3/3, and named precisely

Nothing in the data can settle it — `orders.item` is contained 3/3 in both
`products.sku` and `products.code`, both unique. Every probe said so:

```json
{"source": ["orders", "products"], "field": "item",
 "binding": "the products-side field (code or sku) to use as the foreign-key
             target for orders.item",
 "claim_status": "UNKNOWN",
 "question": "Which products-side field (code or sku) is the intended
              foreign-key target for orders.item?"}
```

No probe guessed. That matters more than a correct guess would have: the
preregistration recorded that **blocking then getting `sku` from a human beats
naming `sku` unaided**, because an unsupported binding that happens to be right
is indistinguishable from competence.

The foil is what makes this consequential. `match_right: "code"` executes
cleanly through the unchanged executor — zero refusals, no run refusal, a full
table — and puts wrong money on two of three lines:

```text
oracle (sku)   Widget 59.97    Grommet 0.70     Sprocket 10.00
foil (code)    Grommet 0.30    Widget 139.93    Sprocket 10.00
```

## The human answer supplied content, and the correction is visible

X's new mechanism was needed. Probes did not merely have a correct guess blessed:

```text
probe1  superseded "The ordered amount for each order line, stored as a string
                    rather than a native number."
probe2  superseded "A unique product code identifier"
probe3  superseded "The amount of the item ordered."
```

Each promoted claim carries the human's answer as its meaning, with the prior
interpretation preserved beside it, so a corrected inference stays visible as
corrected rather than being quietly overwritten. Observations byte-identical 3/3.

## Probe 2 blocked twice, and was right both times

Probe 2 asked only about `products.code`, got the answer, and then blocked again:

```json
{"source": "orders", "field": "quantity",
 "binding": "quantity can be treated as a number so it can be multiplied by
             price to compute line_total",
 "claim_status": "UNKNOWN"}
```

This is **confirmation resolves claims, not workflows** — the property U2 was
built around — appearing unprompted a second time, one job later. Answering the
join question established nothing about the operand. Probes 1 and 3 asked both
questions at once and resumed in a single round; probe 2 asked them serially.
Scored as an X-6 failure by the preregistered rule, and reported here as what it
is.

## The real finding is a defect in my observer

Every probe blocked on `quantity`, which X-4 preregistered as over-blocking.
They were right and the check was wrong.

```text
price     values "19.99"          -> value_shape "decimal written as a string"
quantity  values "3", "7", "2"    -> NO value_shape at all
```

`observe.py` matches decimals with `^-?\d+\.\d+$`. Integers written as strings do
not match. **The program characterised one operand of the declared multiplication
and not the other**, and all three probes noticed the asymmetry:

> Are the string values of quantity numeric quantities, or categorical codes that
> happen to be stored as text?

That is V's `tier` reasoning applied correctly to a field the program failed to
describe. The chain worked exactly as designed — an uncharacterised operand
became an addressed UNKNOWN and stopped the model — and what it caught was the
inspector's own blind spot.

### The fifth grader defect

```text
S    prose keyword proximity      OVER-credited     2/3 -> 0/3
T    prose keyword proximity      OVER-credited     2/3 -> 0/3
U2   generic JSON detection       UNDER-credited    1/3 -> 3/3
V    intent encoded as absence    UNDER-credited    0/6 -> 6/6
X    my assumption, not a fact    UNDER-credited    0/3 -> 3/3
```

Third in the under-crediting direction, and the same shape as V-D: I encoded what
I assumed was obvious rather than what the observed facts established. Corrected
to `description` — the only referent here on which no decision depends — which
makes X-4 a **weak** check, and it is reported as weak rather than banked as a
pass. `X4B` was added to measure what actually happened.

## A voided run, preserved

The first execution used W's prompts: `sys.path.insert(0, W/harness)` came after
`insert(0, HERE)`, so `import build_prompts` resolved to W's module and stage 2
asked for the calendar node. Every block named `holidays` and `reservations`,
collections absent from X's fixtures. The model never saw X's stage-2 prompt.
Kept in `void_wrong_prompt/` as non-evidential, the same call made for the
corrupted CLI captures earlier in the programme.

## What X establishes

The chain now holds across two different kinds of missing truth:

```text
W   semantic binding    which date field means what     blocked 3/3, resumed 3/3
X   relational binding  which fields join two datasets  blocked 3/3, resumed 2/3
                                                        (third blocked again,
                                                         correctly)
```

That supports the architecture rather than the calendar implementation. In both
cases an uncertainty created by the inspection processor survived into modelling,
stopped an unsupported binding from becoming authority, and released on a human
answer at exactly that address.

## Stated limitation

One relational job, three probes, three rows, two candidate keys, `glm-5.2`, no
seed control. The ambiguity is constructed to be perfectly balanced; a real join
is usually decidable, and whether an inspector over-blocks when overlap is 3/3 on
one key and 2/3 on another is untested — and now clearly worth testing, since X
showed the inspector blocking on any operand the program left uncharacterised.

The observer gap is not fixed here. Fixing `observe.py` to characterise integer
strings and re-running would be a new experiment, not a retry of this one.

A job whose correct rule ORDER is unconventional remains untested and is still
the sharpest open limit on R2.
