# Experiment M — breadth: what can the schema NOT say?

**STATUS: FROZEN before any recipe is written for these shapes.**
Deterministic — **no LLM anywhere.**

## The question

Experiment L answered *"does working only with the schema work?"* with **yes, and
here is one place it stops** (gap G1: no date format string). L's own limitation
was that it used one recipe on one shape.

M measures the thing L could not: **across a set of plausible provider shapes,
how many can recipe format v1.3 express, and what exactly is missing from the
rest?**

Every gap is also a security question. The containment argument rests on
transforms being a **closed enum** rather than an expression language. Each shape
the enum cannot express is pressure to add an escape hatch, and an escape hatch is
where arbitrary computation — and therefore the injection surface — comes back.
So counting gaps is counting the pressure on the boundary.

## Method

For each shape: attempt a recipe using only frozen format v1.3, validate it, and
execute it with Experiment L's executor. Then classify:

```text
EXPRESSIBLE   a valid recipe exists and executes to the correct table
GAP           no valid recipe exists without a capability the format lacks
               -> the missing capability is NAMED
```

**The format is not extended during M.** A gap is recorded, never patched — the
J and K lesson. Naming the missing capability precisely *is* the deliverable.

## The six shapes and the frozen predictions

| ID | Shape | Predicted | Missing capability if GAP |
| --- | --- | --- | --- |
| S1 | clean wide monthly | `EXPRESSIBLE` | — the shape the format was designed on |
| S2 | two-row stacked header (`2026` over `Tammi`) | **`GAP`** | a single `header_row` cannot name a two-row header; needs multi-row header flattening |
| S3 | two measure blocks (units *and* euros over the same months) | **`GAP`** | one `unpivot` per sheet; needs two, plus a way to say which columns belong to which measure |
| S4 | already long | `EXPRESSIBLE` | — `id` + `measure` fields, no unpivot |
| S5 | formatted numbers (`1 234,50`, `12 %`) | **`GAP`** | `type: number` has no format declaration; same family as L's G1 |
| S6 | note row in the *middle* of the data | **`GAP`** | `label_in` needs the literal text in advance; an unforeseen note is absorbed by `remainder` |

**Predicted: 2 expressible, 4 gaps.**

### On S6, and why it is not simply "use a rule"

`label_in` *can* exclude the note if someone already knows the string. The gap is
that an unforeseen note in the middle of the data is silently absorbed, and — unlike
K's C13 — it is **not** at the bottom where a shape rule catches it. `row_blank`
does not match either, since the label cell is populated. Predicted to execute
"successfully" with a wrong extra row, which makes S6 the most dangerous of the four.

### On S5, and the honest expectation

The recipe will be *valid* and will execute; the numbers will come out as strings
with the declared type unhonoured, exactly like G1. Whether that counts as `GAP`
or `EXPRESSIBLE` is a judgement, and it is made **here, before the run**: it is a
`GAP`, because the recipe cannot produce the correct table — a downstream sum
would fail.

## Grading (frozen)

```text
per shape   classification in {EXPRESSIBLE, GAP} + the named missing capability
totals      n_expressible, n_gap
fidelity    classification == prediction, per shape
```

| Condition | Outcome |
| --- | --- |
| every shape classified as predicted | **PASS_AS_PREDICTED** — the boundary is where it was thought to be |
| a predicted GAP turns out expressible | **RESULT_MORE_CAPABLE** — record how; the format is stronger than believed |
| a predicted EXPRESSIBLE turns out a gap | **RESULT_LESS_CAPABLE** — the more important direction |
| a shape executes to a *wrong table* while the recipe validates | **flag `SILENT_WRONG`** separately — that is the unsafe class, not merely a gap |

`SILENT_WRONG` is called out because S6 is predicted to land there, and a gap
that produces wrong data silently is categorically worse than one that refuses.

## Hard stop

No LLM. No changes to the frozen grammar, to recipe format v1.3, to L's executor
behaviour, or to any recorded result. **No capability is added to the format
during M**, however obvious the fix looks.
