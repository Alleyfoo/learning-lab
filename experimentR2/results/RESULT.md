# Experiment R2 — RESULT: LOOP_CLOSED (3/3)

Frozen at `ecec842`. Probes run after the freeze, graded by the criteria fixed in
it. No retries, no prompt changes.

## Outcome

```text
probe   vocabulary listed                                  emitted order                                     G1     G2
A       not_reserved, date_well_formed, not_holiday        date_well_formed, not_holiday, not_reserved      VALID  EQUIVALENT
B       not_holiday, not_reserved, date_well_formed        date_well_formed, not_holiday, not_reserved      VALID  EQUIVALENT
C       date_well_formed, not_holiday, not_reserved        date_well_formed, not_holiday, not_reserved      VALID  EQUIVALENT
```

```text
all three emit the REQUIRED order   True
any probe follows VOCABULARY order  False
pairing correct                     3/3, and no probe was shown the pairing
all three PASS (G1 + G2)            True
```

**The frozen "MODELS" prediction came true exactly, and the mutually exclusive
"COPIES" prediction did not occur.** A was shown `not_reserved` first and did not
emit it first. B was shown `not_holiday` first and did not emit it first. Both
reordered to put `date_well_formed` first — the rule whose position carries the
actual semantics, since the other two have no defined answer for a string that
is not a date.

Probe C, the one the preregistration said to distrust, agrees — but it is the
only probe whose vocabulary already matched, so it contributes nothing on its
own. **A and B are the result.**

## The loop, end to end

Probe A's definition, run through the deterministic runtime against the
hand-written ten-minute Python oracle:

```text
   2026-07-14     oracle=ACCEPT                   node=ACCEPT
   2026-07-14     oracle=REJECT ALREADY_RESERVED  node=REJECT ALREADY_RESERVED
   2026-12-25     oracle=REJECT HOLIDAY           node=REJECT HOLIDAY
   2026-02-30     oracle=REJECT INVALID_DATE      node=REJECT INVALID_DATE
   2026-03-10     oracle=REJECT ALREADY_RESERVED  node=REJECT ALREADY_RESERVED
   2026-08-01     oracle=ACCEPT                   node=ACCEPT

   oracle final : ['2026-03-10', '2026-03-11', '2026-07-14', '2026-08-01']
   node final   : ['2026-03-10', '2026-03-11', '2026-07-14', '2026-08-01']
```

Same decisions **and** same final state. The chain the programme was built to
demonstrate now runs unbroken:

```text
local world + stated purpose
    -> LLM proposes a definition
    -> the task's own validator accepts it
    -> deterministic runtime, no LLM present
    -> behavioural equivalence to an independent hand-written reference
```

## What R2 establishes that R could not

R showed the model reproducing content and order **that its prompt already
contained**. R2 removed that: the order was permuted, the pairing was never shown
assembled, and the model constructed both correctly anyway.

```text
R      cannot separate reasoning from copying
R2     the two are separated, and the answer does not follow the prompt
```

R's diagnosis is confirmed. The failure there was the **socket shape**, not the
understanding: teaching only the shape — an empty skeleton with real key names —
moved 0/3 to 3/3 with the semantic content unchanged.

## What this does NOT establish

```text
one node, one job, one model family (glm-5.2), one run per probe, no seed
control. Three vocabulary orders out of six possible.
```

Three samples agreeing is three samples. It cannot distinguish *always* from
*three times*, and it says nothing about a second node type, a longer rule set, a
job whose correct rule order is genuinely ambiguous, or a description that omits
something the format requires.

The strongest honest statement: **for this node, with the socket shape supplied,
the model produced a definition that is behaviourally identical to an independent
reference implementation — and did so from three different prompt orderings.**

## A residual worth naming

The required order here is also the *only* order the validator accepts —
`wellformedness_not_first` refuses the alternatives. So a model that reasoned
correctly and a model that had learned "well-formedness checks come first" from
general programming exposure are not distinguished by this experiment. Testing
that would need a job whose correct order is not the conventional one, and is a
separate freeze.
