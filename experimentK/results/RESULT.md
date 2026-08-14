# Experiment K — Result: PASS_AS_PREDICTED

**Every frozen prediction held, on all 12 cases, including both preregistered
costs.** `agree = 10/12`, `fidelity_all = True`, `baseline_ok = True`,
`false_execute = [C8]`, `over_escalation = [C3]` — exactly the sets named in
`expected.json` before `dispatch.py` existed.

Deterministic. **No LLM was invoked anywhere in K.** Fully repeatable.

## The replay

```text
ID   changed                                  truth            actual
C1   nothing                                  EXECUTE          EXECUTE          ok
C2   the filename only                        EXECUTE          EXECUTE          ok
C3   two more products; total row moves       EXECUTE          REDEFINE_SCOPED  MISS
C4   Tuote -> Tuotekoodi                      REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C5   a Maa column inserted at B               REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C6   a new Kampanjat sheet                    REDEFINE_SCOPED  REDEFINE_SCOPED  ok
C7   Sales -> Myynnit                         DEFINE           DEFINE           ok
C8   same dimensions, product row -> subtotal REDEFINE_SCOPED  EXECUTE          MISS
C9   empty recipe store                       DEFINE           DEFINE           ok
C10  two recipes claim it                     AMBIGUOUS        AMBIGUOUS        ok
C11  recipe edited after approval             BLOCKED          BLOCKED          ok
C12  blocking ambiguity open                  BLOCKED          BLOCKED          ok
```

## The design claim held

**The applicability predicate is not a new artifact — it is the step-2 validator
re-run against the candidate file.** No signature format was invented, no hash of
preview rows, no filename. A recipe already declares everything its correctness
depends on, and re-validation turns that into a dispatch decision whose *problem
codes are the delta*:

```text
C3   row_unclassified: row0 9 (A1 row 10) is claimed by nothing
     row_unclassified: row0 10 (A1 row 11) is claimed by nothing
C4   unresolvable_referent: sheet:Sales!@Tuote -> header_not_found (Tuote)
     column_unclassified: col0 0 is claimed by nothing
C5   column_unclassified: col0 4 is claimed by nothing
C6   sheet_unclassified: every sheet must be given a role
C11  recipe was edited after approval (faf4c3c94632… != 15bf894528ef…)
```

The human is not told "this file changed"; they are told *which referent* no
longer holds. That is what makes `REDEFINE_SCOPED` scoped.

## Findings

**1 — DA-2 is fixed (C2).** `C1_identical.xlsx` and `C2_renamed_file.xlsx` are
byte-identical and hash the same; only the filename differs. Both dispatch to
`EXECUTE`. The demo's `_compute_structural_hash` folds the filename into the key,
so next month's file would have missed its own recipe — failing on precisely the
repeat case the macro exists for.

**2 — coverage totality catches the silent positional shift (C5).** This was the
non-obvious positive claim under test. Inserting a `Maa` column at B leaves the
recipe's positional binding `B:D` pointing at `Maa | Tammi | Helmi`, and the named
bindings still resolve — so nothing *fails*. What catches it is that `Maalis`
(`col0 4`) ends up claimed by nothing. `repo_reuse_map.md` defect D1 is exactly
this shift, in a tool where the run **succeeds** with silently shifted columns.
Coverage totality turns it into a refusal, and it does so via an accounting
property rather than a heuristic about what changed.

**3 — governance is enforced independently of matching (C11).** The workbook is
identical and every binding resolves; the recipe was edited after approval, and
it is `BLOCKED`. Matching and being allowed to run are different questions —
3E's gate-owns-authority applied to approval.

**4 — C3, the preregistered over-escalation, landed for the predicted reason.**
More data rows is the ordinary monthly case, so `EXECUTE` is the right answer and
the front door said `REDEFINE_SCOPED`. Cause as named in the freeze: recipe format
v1 anchors the data region absolutely (`sheet:Sales!5:8`) and the total row
positionally (`sheet:Sales!9`).

**5 — C8, the preregistered false EXECUTE, landed for the predicted reason.** Six
sheets, `A1:F9`, identical headers — and one product row is now a `VÄLISUMMA`
subtotal. Re-validation is clean, approval is intact, dispatch says `EXECUTE`, and
the subtotal would be consumed as a product. A structural predicate cannot see
this by construction.

## An observation the freeze did not anticipate (recorded, not scored)

On C3 the escalation is correct but **the delta under-describes the damage**. It
reports rows 10 and 11 as unclassified; it does not report that the exclusion
`sheet:Sales!9` — written to drop the total row — now points at `ART-005`, a real
product. Executing would have dropped a product *and* counted a total.

The dispatch outcome is unaffected (it escalates either way), so nothing about
the grading changes. But it matters for step 5: a scoped-redefinition dialogue
built on this delta would show a human two missing rows and stay silent about the
mis-aimed exclusion, which is the more dangerous half. Worth carrying forward as a
requirement on the delta, not a defect in the dispatch.

## What K establishes, and what it does not

**Establishes:** a deterministic front door can decide applicability from the
recipe itself; the filename plays no part; drift is reported as named referents;
approval is enforced separately from matching; and structural accounting catches
a class of silent column shift that a real tool gets wrong.

**Does not establish:** anything about content-semantics drift (C8 is the
measured boundary), anything about how often each change occurs in practice (the
UQ-1 question, kept separate), and anything about the lookup key, which is
deliberately weak here — "the recipe's data sheets exist" would match many
recipes on a common sheet name. C10 exercises the `AMBIGUOUS` branch but the key
itself was not under test.

## The two costs, and what they point at

```text
C3  over-escalation   the macro does not pay off on the normal monthly case
                      -> recipe format v1 needs relative row anchoring
                         (data_region: "remainder", exclusions by role not position)
C8  false EXECUTE     the unsafe direction, bounded and named
                      -> catching it needs ROW-LEVEL EVIDENCE (a label column
                         whose value class changes), not a shape predicate
```

Neither was patched during K; the hard stop forbade it, and patching either would
have destroyed the measurement. Both are now measured rather than assumed, which
is what makes them decidable next.

**C3 is the cheaper and more valuable fix**: it converts the *ordinary* case from
an escalation into an execution, which is the entire economic argument for saved
recipes. C8 is a genuine boundary and may be the right place to stop — a front
door that refuses to guarantee content semantics, and says so, is more honest than
one that pretends.
