# W1-A2 – W1-A5: MEASUREMENT-INVALID for skill-quality inference

**Status: frozen and closed.** All runs are preserved as evidence **about the
dialogue measurement channel**, not about `define-lab-process`.

> **Do not reinterpret the PASS/FAIL ratios of W1-A2, W1-A3, W1-A4 or W1-A5 as
> `define-lab-process` performance.** They do not measure it.

## The finding that closes the line

The phrasing-coverage census (`work_interface/census/`) scored every worker
question fragment in the nine captured runs against the current frozen matcher:

```text
ROUTED_CORRECT   49   37%
MISSED           60   45%
MISROUTED        23   17%   <- a valid frozen answer sent for a DIFFERENT question
                ----
                 132        (plus 6 question-bearing lines the parser cannot
                             represent as interrogative)
```

**The 23 misroutes close the line, not the 60 misses.** A lossy channel is bad
but honest: a withheld answer leaves the worker uninformed, and that is
attributable. A channel that answers *"For output order: left_then_right or
sorted_by_key?"* with **`InvoiceNumber`** — a perfectly valid frozen canonical
answer to a different question — corrupts the stimulus itself. After that,
neither PASS nor FAIL can be attributed cleanly to the skill or to the worker.

Concrete instances, all from committed transcripts:

```text
E1t2  "Q6: For output order … left_then_right or sorted_by_key?"     -> "InvoiceNumber"
E1t2  "Q7: Duplicate key policy: if multiple ledger records …"       -> "InvoiceNumber"
E1t2  "Q8: Non-numeric policy … refuse_run or refuse_key?"           -> Amount/within-0.01
E2t3  "on_duplicate_key policy: same InvoiceNumber multiple times …" -> "InvoiceNumber"
E2t3  "output_order: should the output be left_then_right …"         -> "InvoiceNumber"
C3t1  "The amount is non-numeric (reject the run, or skip …)?"       -> Amount/within-0.01
```

**E2 passed while being mis-answered five times.** A PASS obtained through a
corrupted channel is not evidence of skill quality either.

## Why the outcomes were decided by phrasing coincidence

The same question, asked two ways, in two runs of the same experiment:

```text
E2  "…appear in the `reports_fields` array of the final report row?"  -> routed  -> PASS
E3  "…appear in the reconciled output's row names?"                   -> missed  -> REFUSED
```

Per-mandated-question routing coverage: S1 match key 86%, S4 source of truth
75%, S5 report/context 65%, **S2 compare 43%, S3 field-in-rule 33%**. Intents 6
and 7 (`more than once`, `not a number`) matched **zero times in 132 fragments**
while their topic was raised 14 times.

This is systematic, not a tail: every run with dialogue shows misses, across
three separate packs and two different matcher revisions.

## What the line DOES establish, and remains valid evidence for

These findings survive the disposition, because they are about the harness and
the platform, not about skill quality:

```text
W1-A2  Goose can destroy a frozen prompt by using `edit` as a reader, and can
       cross an experimental boundary to reconstruct a lost task (B2).
W1-A3  A per-fragment verdict rule cannot survive ordinary conversational
       trailers; exit codes must separate experimental from infrastructure
       outcomes.
W1-A4  Turn-level set classification delivers frozen answers correctly (D3);
       markdown-wrapped questions defeat naive interrogative detection (D1);
       an agent can complete a turn emitting no user-visible content (D2).
W1-A5  Presentation normalization fixes the D1 class; silent-turn re-entry
       recovers the D2 class (E3 recovered and produced an artifact);
       and the channel misroutes (E1, E2).
```

The ACP harness architecture itself is validated: sessions start, prompts are
delivered as text, the first-artifact hard stop holds, controlled-input
integrity held **15/15 in every executed batch**, and no forbidden path was ever
touched.

## Secondary finding, deliberately NOT acted on yet

`OWNERSHIP_CONTRACT_INCONSISTENT`. The nine-intent table asks two questions the
skill assigns to the worker (`on_duplicate_key`, `on_non_numeric`, closed
vocabularies at `SKILL.md:124-125`), and has no answer for four decisions
workers repeatedly ask about (left/right roles, classify labels, output order,
purpose — asked 20 times, answered 0). Both passing artifacts set
`on_non_numeric = refuse_key`, contradicting frozen intent 7's *"Refuse the
run — do not coerce"*, and the validator accepted both because it checks
structure, not fidelity.

**Ordering rationale:** there is no point arguing about whether duplicate-key
policy should be worker-owned while the harness is capable of answering
*"output order?"* with `InvoiceNumber`. Isolate the measurement channel first.

## Experimental staircase from here

```text
W1-A   frozen, closed, measurement-invalid for skill quality
  |
W1-B   perfect-information ablation -- can the worker perform the skill when all
       required human information is definitely available? No question
       recognition whatsoever.
  |
W1-C   only if capability survives: a structured dialogue channel with explicit
       question identity (the DeepSeek Harness `ask_user_question` id idea),
       i.e. dialogue competence WITHOUT lexical routing.
```

W1-B precedes W1-C because it is cheaper, changes no agent platform, and answers
the more fundamental question first. Repairing the lexical matcher is
deliberately **not** on this staircase: teaching it more English would fit it to
observed agent wording, which is the contamination the closed design exists to
prevent.

## W1-B design constraints (recorded here; not yet built)

- On every qualifying turn, deliver **one canonical frozen block** containing
  the five SKILL-mandated human-owned answers, always in the same order. No
  question recognition of any kind.
- The block contains **only** those five. It must **not** include duplicate-key
  or non-numeric policy, nor any of the four worker-owned decisions — otherwise
  the ablation would paper over the ownership inconsistency it is supposed to
  leave untouched.
- Record separately whether the worker keeps asking for information already
  supplied. **Do not fail an artifact for asking.** But a worker that blocks
  indefinitely while holding the information is a meaningful result.

Interpretation agreed in advance:

```text
3/3 PASS   the skill can execute under complete information; the old failures
           were dominated by the measurement channel. Do not spend effort
           teaching the lexical matcher more English.
failures   now interesting -- attributable to skill under-specification, worker
           contradiction, or artifact-validation fidelity, because the
           answer-delivery confound is gone.
mixed      inspect causality run by run. Do NOT increase N until we know what
           differs between the runs.
```

## Census reproduction

`work_interface/census/` holds the exact read-only instruments and their output:
`census_extract.py` (re-runs the current frozen parser over all nine committed
transcripts), `census_topic.py` (assigns each fragment its semantic topic and
scores routing), and the resulting `census.json` / `census_topic.json`. The
topic rules in `census_topic.py` are audit instruments only — deliberately
broader than the frozen matcher, and **not** a proposed matcher. Both scripts
carry an absolute repo path and are preserved as run, not generalised.
