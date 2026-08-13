# Experiment J — Result: COMPILE WITH PREDICTED COST

**STATUS: FROZEN (2026-08-13), tag `expJ-final`.** No further probes on this
line. The wide/long/transposed thread is closed at v2 — see "Stop rule" at the
end of this document before proposing v3.

**Question (designer's, verbatim):** *Can a human-reviewed failure be compiled
into macro v2 without regressing previously supported provider shapes?*

**Answer: Yes on the located shape, and it generalizes to a held-out transposed
variant — but not for free. The amendment costs exactly one preregistered
regression, and that regression is a refusal, not a false claim.**

Deterministic replay, no LLM invoked anywhere. Fully repeatable.

## The replay

```text
ID   set       ground    v1              v2              rule  hw  mcols  n_num
I1   retained  wide      wide     ok     wide     ok     R1    6   []     6
I2   retained  long      long     ok     long     ok     R2b   0   [1]    1
I3   retained  unknown   unknown  ok     unknown  ok     R4    0   []     5
I4   retained  unknown   long     MISS   unknown  ok     R2a   0   [0]    3
J1   held_out  wide      wide     ok     wide     ok     R1    4   []     5
J2   held_out  long      long     ok     long     ok     R2b   0   [2]    1
J3   held_out  long      long     ok     unknown  MISS   R2a   0   [1]    2
J4   held_out  unknown   long     MISS   unknown  ok     R2a   0   [0]    2
J5   held_out  long      long     ok     long     ok     R2b   0   [0]    1
J6   held_out  wide      unknown  MISS   unknown  MISS   R4    2   []     2
J7   held_out  unknown   unknown  ok     unknown  ok     R4    0   []     1

v1 8/11   v2 9/11
repairs {I4, J4}   regressions {J3}   shared misses {J6}
outcome = COMPILE_WITH_PREDICTED_COST
```

## Every frozen prediction held

`fidelity=True`, `rule_fidelity=True`, `v1_fidelity=True`,
`totals_as_predicted=True`, `fidelity_deviations=[]`.

The preregistration predicted, before `macro_v2.py` existed: v1 8/11, v2 9/11,
repairs `{I4, J4}`, regressions `{J3}`, shared misses `{J6}` — and, per fixture,
which of the six rule branches would fire. All eleven fixtures matched on label
**and** on rule branch. The author's hand-simulation of the frozen rule text was
correct, so the fidelity clause (a wrong prediction would have been recorded as
a result, not patched) was not exercised.

## What is and is not a finding

**Not a finding: v2 fixes I4.** v2 was written to fix I4. That is the premise.

**Finding 1 — the fix generalizes (J4).** `J4` is a held-out transposed layout
v2 never saw: different vocabulary (`Myymälä-A`/`Myymälä-B`, not `ART-00x`),
different entity type, six months instead of twelve, and the *minimum* spread
the rule can detect (exactly two columns, where I4 had three). v1 called it
`long`; v2 called it `unknown`. The amendment encodes a shape property, not the
I4 fixture.

**Finding 2 — the regression is real, predicted, and named (J3).**
`Tuote │ Kuukausi │ Myynti │ Kate` is a genuine long table with two measures.
v1 got it right; v2 refuses it. `n_num >= 2` cannot tell *two measures* from
*two entity instances* — both are "non-month columns carrying numbers". This was
frozen as the expected cost of the deterministic reading before any code ran.

**Finding 3 — the boundary did not over-refuse (J5).** `Kuukausi │ Myynti`, a
single time series, is months-down-a-column with no spread. v2 keeps it `long`.
So R2a is not "months down a column → unknown"; the spread condition is doing
the work.

**Finding 4 — the error direction inverted, which matters more than the count.**

```text
        false assertions     false refusals     total errors
v1        2  (I4, J4)          1  (J6)              3
v2        0                    2  (J3, J6)          2
```

`unknown` is a refusal — escalate to a human. v1's two errors on transposed
tables were **false assertions**: it confidently returned `long` for data that
is not long, and a downstream unpivot would have consumed that answer. v2 has
**no false assertions on this set**; both of its misses escalate. The compile
converted the unsafe error class into the safe one, and paid one extra escalation
(J3) to do it.

That is the same shape as the programme's other results — H's
`coverage==12 → accept, else ask_human`, and 3E's deterministic comparison gate.
An unsupported claim must not acquire authority; refusing is the acceptable
failure.

## What the amendment actually changed

v1 concluded `long` from *"month tokens run down a data column."* I4 falsified
that: a transposed monthly table has months down a column too. v2 keeps the
trigger unchanged and adds one question after it — *how many non-month columns
carry values?*

```text
R2a  n_num >= 2  -> unknown   values spread across a second axis: out of contract
R2b  n_num == 1  -> long      one measure column: canonical long
R2c  n_num == 0  -> unknown   no measure column
```

`J2` (`Tuote │ Maa │ Kuukausi │ Myynti`) is why the predicate counts *numeric*
columns rather than columns: a naive "several columns beside the month axis →
unknown" reading would have refused a perfectly ordinary long table with two
label columns. It was frozen as a regression trap and v2 passed it.

## Limitations (as frozen, plus what the run showed)

- **`J6` is a shared limitation, not a regression.** `Tuote │ Tammi │ Helmi` is
  wide by definition; both macros return `unknown` because `K_w = 3`. J did not
  retune the thresholds and the miss is identical in v1 and v2.
- **The J3 cost is inherent to the deterministic reading.** Distinguishing an
  entity-instance column from a measure column is a semantic judgement about
  what a header *names*. No token count reaches it.
- 11 in-lab fixtures. This is a controlled replay, not a sample of real provider
  files; it says nothing about how often each shape occurs (the UQ-1 question,
  kept separate).
- Finnish short-form month vocabulary only. No cross-language claim.
- Deterministic: no seeds, no sampling, no agent. The reliability caveat that
  attaches to every n=1 LLM probe in this programme does **not** apply to J —
  and that is precisely the point of compiling a rule.

## What this says about the macro-saver model

Experiment I ended with the agent failing three times on the same fixture and no
agent-supplied correction. J shows the lifecycle still closes without one:

```text
agent exposes the edge case   I4 -- the saved macro is wrong, and visibly so
human names the missing rule  "months down a column AND values spread across
                               >= 2 columns is not long"
system absorbs it             v2, deterministic, verified on held-out shapes
cost is measured, not assumed J3 -- one legitimate long table now escalates
```

The lab learned from a failure the agent did not correct. What was bought is a
shape the runtime no longer gets *wrong*; what was paid is a shape it now hands
to a human. Both were named before the run.

## The v3 question this locates

J3 is the handle on the next experiment. The single judgement v2 cannot make is:

> Do these two numeric columns name **measures of one entity** (`Myynti`,
> `Kate`) or **instances of an entity** (`ART-001`, `ART-002`)?

That is a question about what a header means, and it is exactly the kind of
question the macro-discovery project asks an agent to answer *once* so the answer
can be compiled. It is also a fair test: I4/I5/I6 showed the agent could not
classify the whole layout, but this is a much narrower question, asked about two
header cells rather than a table's global shape — and the 3A–3E line showed
narrow, symmetric, independently-established questions are where the reviewer
architecture works.

**Not authorized here. It needs its own preregistration** — what counts as the
rule being extracted, what the held-out replay is, and what the gate does when
the agent's answer is not established.

## Stop rule — the line is frozen here (designer, 2026-08-13)

**v3 is NOT the next experiment, and the wide/long/transposed thread is closed.**
The designer's ruling on freezing J:

> This is a laboratory and experimental, so we shouldn't go too deep into one
> issue. We are trying to find ways to use agents in the initial phase when
> defining the project, but a higher-level LLM should take care of the whole
> project as a kind of analyzer for the system.

Read against the record, that is a scope judgement, not a dissatisfaction with
the result. The 3A→3E→H→I→J line has now been pushed to the point of diminishing
return on **one** representation question: five experiments, three contract
variants, two macro versions, and a measured cost. Continuing to v3 would buy
one more predicate on one more table shape. The lab's purpose is **breadth of
agent-use patterns**, not depth on wide/long.

What J contributes to that purpose is the transferable part:

- a failure the agent could not correct still compiled into the deterministic
  system, and the compile was validated on shapes it was not designed for;
- the cost of an amendment can be *predicted and measured* rather than assumed;
- the safe error direction (refuse) can be bought with a named, bounded number
  of extra escalations.

Those hold regardless of whether the table was wide, long or transposed. The
next line asks a different question — see `.handoff.md`, "Redirection".

**Anyone picking this repo up: do not resume v3, do not tune v2 to pass J3, and
do not add a fourth label.** If the measure-vs-entity question is ever wanted, it
is a fresh preregistration and it should be justified on its own merits, not as
"the obvious continuation."
