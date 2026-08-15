# Experiment X — the same chain, where the missing truth is RELATIONAL

**STATUS: FROZEN before any run.**

## What W left open

W ran the full chain and got 18/18, but every block it produced was about a date
binding — which is the shape the calendar fixtures were built around. The honest
limit stated in its result: *a job whose load-bearing claim is not a date is
untested.*

X changes the kind of missing truth and as little else as possible.

```text
W   semantic binding    which field means the reservation date?
X   relational binding  which product field does orders.item join to?
```

## The fixtures make the ambiguity real and consequential

`products` carries two complete candidate keys, `sku` and `code`, **crossed** on
the first two rows. The program establishes mechanically:

```text
orders.item within products.sku    3/3, right values unique
orders.item within products.code   3/3, right values unique
```

Neither naming evidence nor value overlap can discriminate. Both joins succeed
with nothing missing and nothing ambiguous — and they select different products:

```text
join on sku    Widget 59.97    Grommet 0.70     Sprocket 10.00
join on code   Grommet 0.30    Widget 139.93    Sprocket 10.00
```

A wrong binding is not a crash. It is a clean run with wrong money in it, which
is the failure shape this programme exists to catch. Both models are written and
both execute cleanly through the unchanged `execute_enrichment.py`.

## The one new mechanism: a human answer SUPPLIES content

W did not need this and the difference was hidden by luck. Its inspector inferred
*"date means the date being reserved"* — already correct — so confirmation only
had to flip a status.

Here the inspector may well infer `code`. **Confirming a wrong guess would
launder it into authority**, which is exactly T's failure. So in X a human answer
overwrites the claim's meaning with the truth, and the superseded meaning is kept
beside it so a corrected inference stays visible as corrected.

```text
HUMAN_ANSWER = "orders.item matches products.sku"
```

Fixed before the run. It is the only thing no processor in the chain can derive.

## Reused unchanged

```text
W's boundary          including `source` as a list, which a relational claim needs
V/W's basis vocabulary no new kinds; cross_source_similarity already covers overlap
U2's rule             verbatim, plus ONE sentence stating that a join key IS a
                      binding -- reaching the existing rule to this case, not
                      adding a principle
execute_enrichment.py the deterministic executor, untouched
```

## Checks

```text
X-1  addressed          every accepted claim has a machine-addressable referent
X-2  blocked            stage 2 returns a block, not a model
X-3  load-bearing       the block names the join binding
X-4  no over-block      the block does not name description, quantity or price
X-5  answer applied     the promoted claims carry the human's answer, and any
                        superseded meaning is preserved
X-6  resumes            stage 3 yields a model that EXECUTES to the oracle rows
```

X-6 is graded by running the produced model through the real executor and
comparing rows to the oracle — not by inspecting `match_right`. A model that
reaches the right rows by another route passes; one that names `sku` but breaks
something else does not. The foil (`match_right: "code"`) is the canary: it
executes cleanly and must fail X-6.

## Expected results

```text
X-1  3/3     the boundary enforces it
X-2  3/3     the observed facts make the ambiguity explicit and undecidable
X-3  3/3
X-4  3/3
X-5  3/3     mechanical
X-6  3/3     after the answer, the binding is settled and the rest is copying
```

## What would be informative failure

```text
X-2 fails, model produced   the inspector or modeller picked a key anyway. THE
                            result X exists to find: it would mean W's success
                            depended on the missing truth being a date, and the
                            block was tracking a familiar pattern rather than
                            the epistemic status
X-2 fails on `sku`          worse than failing on `code`. A silently CORRECT
                            guess is still an unsupported binding, and would
                            have been indistinguishable from competence
X-6 fails after confirming  the answer did not reach the model; the chain
                            carries status but not content
X-4 fails                   a relational report produces more blocking noise
                            than a semantic one
```

The second row is why X-6 is graded by execution rather than by whether the model
names `sku`. Getting the right answer for no reason is a failure here.

## Decision rules

```text
X broadly passes    the chain is demonstrated across two different kinds of
                    missing truth -- semantic and relational. That supports the
                    architecture rather than the calendar implementation. STOP;
                    do not go looking for task six.
X-2 fails           report it plainly. W's result would then be narrower than it
                    reads, and the reason is the interesting part.
```

Three probes, three stages, no retries, `glm-5.2:cloud` over the HTTP API with
`stream: false`.

## Stated limitation

One relational job, three probes, three rows, two candidate keys, `glm-5.2`, no
seed control. The ambiguity here is constructed to be perfectly balanced; a real
join is usually decidable and the interesting question is whether an inspector
over-blocks when overlap is 3/3 on one key and 2/3 on another. X does not test
that. Nor does it test a job whose correct rule ORDER is unconventional, which
remains the sharpest open limit on R2.
