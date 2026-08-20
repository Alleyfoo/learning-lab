# W1-B F1 — read-only causal analysis

**Evidence base: frozen commit `12ee391`.** This document is analysis only. No
skill, validator, Work Definition schema, harness, grader result or W1-B artifact
was modified in producing it, and none may be modified on the strength of it
until the roundtable decides where the next change belongs.

W1-B result for context: F1/F2/F3 all COMPLETED in 2 turns, one canonical block
each, zero silent turns, zero questions after the block. Grader 2/3 PASS —
F2 and F3 PASS, **F1 REFUSED for `load_bearing_unresolved`**.

---

## 1. The refusal path, reproduced

**One condition, one line.** `work_interface/work_definition.py:466-473`:

```python
for q in raw.get("open_questions") or []:                        # :466
    if not isinstance(q, dict):                                  # :467
        continue                                                 # :468
    if q.get("load_bearing") and q.get("status") != "resolved":   # :469
        problems.append(Problem(                                 # :470
            "load_bearing_unresolved", f"{where}:open_questions", # :471
            f"{q.get('id', '?')!r} is load-bearing and {q.get('status')!r}; "
            f"a load-bearing unresolved fact blocks entry to modelling"))
```

F1's `open_questions`, verbatim from the frozen artifact
(`runs/F1/work_definition.json`, sha256 `75991a38caef…`):

```text
[0] id=Q_match_key_field  load_bearing=false  status="resolved_by_producer"  -> exempt
[1] id=Q_authority        load_bearing=true   status="resolved_to_peers"     -> REFUSED
```

| condition | F1 actual | required |
|---|---|---|
| `load_bearing` | `true` | any falsy value exempts the entry |
| `status` | `"resolved_to_peers"` | the exact literal `"resolved"` |

Both must hold. The refusal was **not** inferred from the code name: it is the
single `!=` comparison at `:469`.

**Asymmetry, recorded because it is independent of F1's outcome.** Entry `[0]`
carries an equally invented status, `"resolved_by_producer"`, and passes
silently — the validator constrains `status` *only* when `load_bearing` is
truthy. An invented status on a non-load-bearing question is undetectable.

---

## 2. Producer-authority trace

### The literal `"resolved"` does not exist in any producer-facing frozen artifact

```text
file                     "resolved" substrings   not preceded by "un"
SKILL.md                 7                       0
PROMPT.md                0                       0
human_answers.md         0                       0
supplier-statement.txt   0                       0
ledger-book.txt          0                       0
```

All seven SKILL.md occurrences are inside the word `unresolved`.

### `open_questions[].status` is not a declared closed vocabulary

`SKILL.md:112` — *"Closed vocabularies (use these EXACT values, no others)"* —
enumerates eleven slots: `work_definition_version`, `task_family`,
`sources.<role>.basis`, `match_on.basis`/`compare[].basis`,
`compare[].comparison`, `compare[].tolerance`, `classify` keys, `output_order`,
`on_duplicate_key`, `on_non_numeric`, `requested_authority`.
**`open_questions[].status` is not among them.**

The only exemplar is the shape at `SKILL.md:98-104`:

```json
"open_questions": [
  { "id": "«stable id»", "question": "«a fact that remains unknown»",
    "load_bearing": false, "status": "unresolved" }
]
```

— a *non*-load-bearing unresolved question, i.e. the one combination line 469
never checks. It is an example, not an enumeration: it is presented inside the
shape block, not in the closed-vocabulary table, and no accompanying sentence
closes the value set.

### Classification of each refusal-relevant requirement

| Validator requirement | Producer authority | Class |
|---|---|---|
| `status == "resolved"` for a load-bearing question | none; slot absent from the closed-vocabulary table; sole exemplar is `"unresolved"` | **UNDER_SPECIFIED** |
| an answered fact belongs in `human_confirmations`, not `open_questions` | `SKILL.md:183-184` *"Record each answer verbatim in `human_confirmations` with a stable `id`"*; `:186-188` scopes `open_questions` to a fact that *"cannot be settled from the files or the human"* | **EXPLICITLY_SPECIFIED** |
| `load_bearing: true` + `status: "unresolved"` → refusal is the correct outcome | `SKILL.md:188-190`, stated outright | **EXPLICITLY_SPECIFIED** |
| whether an answered question may remain listed in `open_questions` at all | never addressed | **UNDER_SPECIFIED** |

### Where `load_bearing` becomes irrelevant after an answer

It does not. The skill teaches a **two-state world**:

```text
settled by the files or the human  -> human_confirmations   (:178-180, :183-184)
cannot be settled                  -> open_questions with
                                      load_bearing: true, status: "unresolved"  (:186-190)
```

**The state "load-bearing and answered" has no taught representation** — yet that
is precisely the state `:469` is written to accept.

---

## 3. `match_on.basis` — not part of the refusal

- **Vocabulary: EXPLICITLY_SPECIFIED.** `SKILL.md:119` permits `observed` or
  `human_confirmed` for executable choices; validator `BASIS_VOCABULARY:112`,
  `EXECUTABLE_BASIS:115`. F1's `observed` is a permitted executable basis.
- **Choice rule: UNDER_SPECIFIED, and deliberately unpoliced.**
  `work_definition.py:24-29`: *"It does not judge whether a `basis` label is the
  right epistemic label — only that it is one of a closed set… Whether 'observed'
  is actually appropriate for a given decision stays with the human/modeller."*
- **No override rule exists.** Nothing in SKILL.md states that a human
  confirmation must supersede an earlier `observed` basis (searched for
  override / supersede / prefer-human; the only hits are the authority-key
  prohibitions at `:152` and `:211`).

**Conclusion: `match_on.basis = "observed"` contributed nothing to the refusal.**
It survives as fidelity evidence only — F1 held the confirmation and labelled the
decision self-observed. Per §5 this is not called an error, because the contract
does not establish what F1 should have done.

---

## 4. F1 / F2 / F3 structural comparison

```text
field                      F1                      F2                F3               verdict
task_family                reconciliation          =                 =                identical
match_on.left/right        InvoiceNumber/same      =                 =                identical
compare[0] field/comp/tol  Amount/within/0.01      =                 =                identical
compare[0].basis           human_confirmed         =                 =                identical
reports_fields             [InvoiceNumber, Amount] =                 =                identical
on_duplicate_key           refuse_run              =                 =                identical
requested_authority        None                    =                 =                identical
requested_destination      review_only             =                 =                identical
---------------------------------------------------------------------------------------------
match_on.basis             observed                human_confirmed   human_confirmed  F1 alone
match_on.confirmation      None                    Q_match_key       Q_match_key      F1 alone
on_non_numeric             refuse_run              refuse_key        refuse_key       F1 alone
#open_questions            2                       0                 0                F1 alone
---------------------------------------------------------------------------------------------
output_order               left_then_right         sorted_by_key     left_then_right  all differ
context_fields             +SupplierName (4 items) block-exact (3)   merged w/ slash  all differ
#human_confirmations       1                       3                 4                all differ
```

**The single behavioural difference that produced the refusal:** F2 and F3
recorded **zero** `open_questions`, filing `Q_source_of_truth` as a confirmation
carrying the block's answer. F1 alone routed that same supplied answer into
`open_questions`.

Confirmation counts trace to how much of the six-part block each recorded:

```text
F1  1   Q_compare_amount   (Amount only)
F2  3   Q_match_key, Q_compare_rule, Q_source_of_truth
F3  4   Q_match_key, Q_compare_policy, Q_source_of_truth, Q_report_fields
```

**On convergence — 2/3 agreement is not authority.** F2 and F3 agree on
`on_non_numeric = refuse_key`, a worker-owned decision deliberately **not**
supplied by the block. It diverges from the frozen, withheld intent-7 answer
*"Refuse the run — do not coerce"*, which **F1 alone matched** with `refuse_run`.
Here the majority selects the less faithful value. `Q_match_key` as a confirmation
id is likewise unspecified — `SKILL.md:99` says only `«stable id»` — so its
recurrence is natural naming, not contract compliance.

---

## 5. Causal classification

### Proximate cause: `PRODUCER_ERROR`

**An explicitly specified compliant path existed and F1 did not take it.**
`SKILL.md:183-184` directs every answer into `human_confirmations`; `:186-188`
restricts `open_questions` to facts that cannot be settled. The source-of-truth
fact *was* settled — the canonical block supplied *"Neither — both are peer
sources…"*, and F1 demonstrably received it (one block delivery, sha256
`46158afa4b7e682a…`, recorded in `runs/F1/harness_result.json`). F2 and F3
demonstrate the path is reachable by this worker on this stimulus.

### Root / architectural cause: `VALIDATOR_CONTRACT_MISMATCH` + `SKILL_UNDERSPECIFICATION`

Line `:469` defines a **twelfth constrained slot** — `open_questions[].status` —
whose accepted value the producer-facing contract never enumerates, exemplifies
or names. Once F1 chose to keep the question listed, **no compliant value was
derivable**: `"resolved_to_peers"` is a plausible invention, and so would
`"answered"`, `"settled"` or `"closed"` have been. The producer surface (shape
plus the eleven-slot table) is not derived from the validator's actual accepted
value space; the two drifted.

This hole exists independently of F1. It would bite any producer that lists an
answered load-bearing question, and it is invisible in the non-load-bearing case
(§1 asymmetry).

### Separate fidelity observations — `FIDELITY_GAP`, none refused

The validator checks structure, not faithfulness to the human script, so none of
these were detected:

```text
F1      match_on.basis "observed" while holding the supplied confirmation
F2, F3  two block answers merged into a single confirmation record
        (Q_compare_rule / Q_compare_policy each carry Amount AND Currency),
        against SKILL.md:183 "Record each answer verbatim"
F2, F3  on_non_numeric = refuse_key, diverging from the withheld frozen intent
```

### The qualification that matters

**F1 was not left without a valid way to satisfy the validator — it had one and
missed it.** What it lacked was a valid way to satisfy the validator *along the
path it chose*. This is therefore a genuine producer/validator contract hole
**surfaced by** a producer error, not a hole that **forced** the error. Any
remedy argued from this evidence must respect that distinction.

---

## 6. Decision input for the roundtable — no fix proposed

Two things are true and separable:

1. **F1 violated an explicit rule.** Answered facts belong in
   `human_confirmations`. On that reading the correct action is *nowhere* — the
   contract was clear and the producer did not follow it.
2. **The contract still has a real hole.** A state the validator accepts has no
   producer-side vocabulary, and the `load_bearing` gate hides the same class of
   invention whenever the flag is false.

Candidate homes for a change — listed as the decision surface, **not** as
recommendations: the skill (teach the vocabulary), the validator (accept or
reject on a stated producer-visible basis), the Work Definition schema (make the
producer surface derive from the accepted value space), or nowhere.

Nothing in this document authorises a change to any of them.
