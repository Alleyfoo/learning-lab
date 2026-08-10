# Experiment 3C — Proposal-Direction × Evidence: Result

**Mechanism located: `directional_prior + lexical_origin`.**

The reviewer does not ratify whatever it is handed, and the failure is not
structural. It applies a **closed-world lexical test** — "does this token look
like a month name?" — and an unfamiliar token defaults to `not_month`. Hiding the
token removes the default. The evidence-burden contract's operative clause
("the absence of evidence that a header is a month is not evidence that it is
not a month") did not prevent this: the reviewer treats *"Jakso A doesn't look
like a month name"* as positive evidence for `not_month`.

This is the preregistered **directional_prior** primary outcome (the designer's
scenario A) **combined with** the **lexical_origin** secondary outcome (scenario
C), plus a sharper corroboration from the masked month direction.

---

## Results

| ID | Evidence | Proposal | Result | Normative |
| --- | --- | --- | --- | --- |
| **F1** | Full (`Jakso A`) | `not_month` | `supported` | `insufficient_evidence` |
| **F2** | Full (`Jakso A`) | `month` | `insufficient_evidence` | `insufficient_evidence` ✓ |
| **M1** | Masked (`[TARGET]`) | `not_month` | `insufficient_evidence` | `insufficient_evidence` ✓ |
| **M2** | Masked (`[TARGET]`) | `month` | `supported` | `insufficient_evidence` |

All four reviewer calls returned well-formed JSON; zero parse failures. A1
fixture sha256 matched the frozen value. The contract, reviewer model, and
invocation mechanism were identical to 3B.1 (the clean arm); only proposal
direction and evidence masking varied.

### Read as a 2×2

```text
                 not_month        month
Full  Jakso A     supported      insufficient      <- direction matters; not_month wins
Masked [TARGET]   insufficient   supported         <- masking inverts the default to month
```

The two diagonals are `supported`; the two anti-diagonals are `insufficient`.
That cross is the signal.

## Run identity

| | |
| --- | --- |
| Reviewer | GLM-5.2 (the session model), fresh isolated agent calls (general-purpose), one per condition, four run concurrently — structural independence |
| Contract | evidence-burden (verbatim from 3B.1) |
| Sampling | one run per condition; no seed control over GLM-5.2 in the agent tool — cannot distinguish *always* from *once* |
| Fixtures | frozen A1 from Experiment 2B, referenced by path, unmodified |
| Freeze | preregistration + expected answers + harness committed at `fc390be` before any 3C condition ran |
| Masking | full A1 with one substitution: row 4 col 4 `Jakso A` → `[TARGET]`; all other cells (incl. data 9, 14 under col 4) preserved — a clean single-variable contrast vs F1 |

---

## The three findings

### 1. Direction matters — it is a directional prior, not proposition-ratifying

F1 (`Jakso A = not_month`) → `supported`; F2 (`Jakso A = month`) →
`insufficient_evidence`. The reviewer endorsed `not_month` but withheld on
`month` for the same token in the same evidence. It is **not** ratifying whichever
direction it is handed (that would have been F1=S, F2=S — the nastier failure the
designer flagged). It has a directional bias: for an unfamiliar token, the
`not_month` proposal acquires warrant and the `month` proposal does not.

This is the closed-world assumption the designer hypothesized: *if I don't
recognize it as a month, treat it as not-a-month.* The proposal direction
exploits a prior that is already there; it does not create the judgement from
nothing.

### 2. The prior is lexical, not structural

F1 (full, `not_month`) → `supported`; M1 (masked, `not_month`) →
`insufficient_evidence`. Hiding the single token `Jakso A` (→ `[TARGET]`) flips
the `not_month` warrant from `supported` to `insufficient_evidence`. The
unwarranted `not_month` judgement is **created by seeing the lexical string**,
not by the column's structural position. M1 vs F1 is a clean single-variable
contrast — identical except for that one cell — so this reading is unambiguous:
remove the non-month-looking text and the `not_month` default disappears.

### 3. The structure is month-positive — M2 inverts the default

M1 (masked, `not_month`) → `insufficient_evidence`; M2 (masked, `month`) →
`supported`. With the lexical token hidden, the *same* structural context — a
token in the March position between `Helmi` (Feb) and `Huhti` (Apr), with a
numeric data column (9, 14) like the neighbouring months — reads as `month` to
the reviewer, while `not_month` is withheld. The structural surroundings are
**month-positive**. The only thing driving the `not_month` judgement in the full
condition is the lexical token `Jakso A` not looking like a month name; once that
is removed, the structure pushes the other way.

So the closed-world lexical test is not merely present — it is **overriding
month-positive structural evidence**. The reviewer sees a column that,
structurally, looks exactly like the month columns, and classifies it `not_month`
anyway because the text "Jakso A" is not a recognised month name.

---

## What this establishes

### The 3A/3B blind spot has a located mechanism

Across 2B.5, 3A, 3B.1 the `Jakso A = not_month` assertion acquired warrant, but
*why* was unknown. 3C locates it: a closed-world lexical default, exposed by the
asymmetric proposal framing. The reviewer treats "not a recognised month name"
as sufficient evidence for `not_month`, despite (a) the evidence-burden contract
explicitly forbidding that inference, and (b) the structural context pointing the
other way.

### The evidence-burden contract does not enforce its own clause

The contract stated: *"the absence of evidence that a header is a month is not
evidence that it is not a month."* That is precisely the inference the reviewer
made on F1. A contract clause written in prose does not, by itself, relocate the
model's default. 3B.1 showed the contract did not change the judgement on the
target; 3C shows *why* — the closed-world lexical default operates below the
level the contract addresses. The clause names the fallacy; the model still
commits it.

### The reviewer is calibrated on the structural/positional signal

M2 shows the reviewer reads "[TARGET] between months, numeric column" as `month`.
So the reviewer is not blind to structure — it uses it when no lexical token
overrides it. The failure is specifically the **lexical token winning over
correct structural reading**, in the `not_month` direction. This refines 3B's
finding: it is not that the reviewer has no discrimination, it is that one
specific cue (unfamiliar lexical token) triggers a default that the contract
cannot suppress.

### F1 reproduces 3B.1 — the blind spot is run-stable

F1 (identical to 3B.1's T proposition) returned `supported` again, on an
independent run. The blind spot is now observed twice on GLM-5.2 under the
evidence-burden contract, across two sessions. This is not *always* (no seed
control), but it is no longer a single sample.

## What this does NOT establish

- **One run per condition, one model, no seed control.** The 2×2 cross is one
  sample of each cell. The mechanism is *located*, not *measured for frequency*.
  A run where F2 or M1 came back `supported` would change the reading; this run
  did not, but reliability is unmeasured.
- **Only GLM-5.2 tested.** The closed-world lexical default may or may not be
  shared by other families. 3B.2's llama3.1:8b datapoint (which endorsed the
  target but failed its C1 control and appears not to recognise Finnish month
  names) is consistent with a similar lexical default but was not probed with
  the 3C four-condition design. The wider model sweep remains parked.
- **The masked condition is not free of all lexical cues.** Hiding `Jakso A`
  preserves the surrounding month *names* (`Tammi`, `Helmi`, `Huhti`, `Touko`). A
  reviewer that recognises Finnish months can still infer `[TARGET]` is in a
  month position — which is exactly what M2 shows it doing. "Masked" means "free
  of the target's own text," not "free of all text." This was intentional
  (preserves structure) and is in fact what makes M2 interpretable.
- **Not** that a symmetric reviewer would fix it. The architectural implication
  below is a hypothesis for a future experiment, not a result of this one.
- **Not** that the reviewer "refuses to say insufficient_evidence." It said
  `insufficient_evidence` on F2 and M1 — twice — so the behaviour is available.
  It is applied selectively: withheld in the month direction and under masking,
  not in the full-text not_month direction. The discrimination exists; it is
  deployed against the wrong cue.

---

## The architectural implication (hypothesis, not tested here)

The 3C mechanism suggests the **framing of the review question is itself the
contamination.** "Is `Jakso A = not_month` warranted?" hands the reviewer a
proposition in a direction that aligns with its closed-world default, and the
default answers before the evidence-burden clause can bite. The designer's
proposed alternative is a **symmetric** review question:

```text
Given only this evidence, which claims are established?
  A. month
  B. not_month
  C. neither is established
```

Here `C` is an ordinary classification outcome, not "refusing the proposed
answer." The closed-world default ("unfamiliar → not_month") would have to
*select B over C*, against a symmetric field, rather than confirm a handed
proposition. That may — or may not — move the boundary. It is the obvious next
experiment, and it is **not run in 3C** because it changes the instrument again;
3C was scoped to establish whether proposition direction is contaminating review.
It is.

## Hard stop — honored

No normalization, no transformation code, no country mappings, no numeric
parsing, no multiple sheets, no joins, no procedure synthesis, and no
symmetric-classification reviewer redesign were added. 3C tested whether
proposal direction and lexical masking contaminate warrant review. It ended
there.

## Capability boundary after 3C

```text
2B.1  locate header              PASS
2B.2  identify month columns     PASS   (aggregate, binary contract)
2B.3  refuse when unresolved     FAIL   (silent omission)
2B.4  aggregate + uncertainty    INCONCLUSIVE (control failed)
2B.5  atomic classification      6/7    (composition solved; warrant not)
3A.G1 orchestrate easy           PASS
3A.G2 orchestrate Finnish        PASS   (incl. warrant reviewer calibrated)
3A.G3 escalate via warrant       FAIL   (reviewer endorsed over-assertion)
3B.1  evidence-burden reviewer   FAIL   (still_overconfident; controls pass)
3B.2  model-diversity reviewer   FAIL   (target supported; C1 control broken)
3C    direction x evidence       DIAGNOSTIC — mechanism located
```

3C is the first probe in the programme that *diagnoses a failure mechanism*
rather than only registering the failure. Composition solved twice; escalation
failed six times; **the reason escalation fails is now located**: a closed-world
lexical default, exposed by asymmetric proposal framing, that the evidence-burden
contract does not suppress.

## Decision rule — which branch fired

Preregistered: the combined `directional_prior + lexical_origin` outcome, with
F1=S anchoring (blind spot reproduced). Fired exactly. The M2 inversion
(`masking_inverts_to_month_default`) is an additional corroboration not named as
a primary branch but fully consistent with — and sharpening — the lexical_origin
reading: the structure is month-positive, so masking flips the default to month.

## Where this points (not a commitment, not authorization)

The mechanism is located. The next move, if authorized, follows directly:

1. **3D — symmetric reviewer.** Replace "is `X = not_month` warranted?" with
   "which is established: A. month / B. not_month / C. neither?" on the same A1
   cell, same GLM-5.2. Tests whether removing the asymmetric proposition framing
   lets `C` (neither) appear — i.e., whether the closed-world default still
   selects B over C when it must compete symmetrically. This is the designer's
   explicit next candidate and is the most direct test of the architectural
   implication above.
2. **A lexical-only reviewer** — deny all cell text, give only column shapes and
   positions. 3C's M2 already hints this would read as month; a dedicated probe
   would confirm whether structure-only review escalates correctly on this cell.
3. **The parked wider model sweep** with the 3C four-condition design attached,
   so each family gets a mechanism diagnosis rather than only a target verdict.
   Lower priority now that the mechanism is located on GLM-5.2.

The honest summary: the gate is still waiting for an `insufficient_evidence`
signal. 3C shows the signal fails to appear because a closed-world lexical
default, triggered by the target's text and invited by the asymmetric question,
endorses `not_month` before the evidence standard can apply. The next question is
whether a symmetric question lets the standard reach the cell.