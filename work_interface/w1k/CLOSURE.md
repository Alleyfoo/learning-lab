# W1-K closure — additive

Evidence commit `a9af352`. Pack frozen at `d9e656a`; prompts, skills and
controlled inputs byte-identical before and after. Executed as **one six-run
batch with no inspection between arms**. **Nothing in `runs/` was edited,
repaired, or rerun.**

## 1. PRIMARY — the ladder

```text
control    targets (4,5)   offered 0/6  populated 0/6  binding 0/6  EXACT 0/6
           positive (0,1)  offered 6/6  populated 6/6  binding 5/6  EXACT 3/6
           negative (2,3)  offered 0/6  populated 0/6  binding 0/6  EXACT 0/6

treatment  targets (4,5)   offered 6/6  populated 6/6  binding 6/6  EXACT 4/6
           positive (0,1)  offered 6/6  populated 6/6  binding 6/6  EXACT 3/6
           negative (2,3)  offered 0/6  populated 0/6  binding 0/6  EXACT 3/6
```

Per run:

```text
      row0    row1    row2    row3    row4    row5
A1    EXACT   ABS     ABS     ABS     ABS     ABS
A2    EXACT   BUND    BUND    ABS     ABS     ABS
A3    EXACT   NONVB   ABS     ABS     ABS     ABS
B1    EXACT   EXACT   EXACT   EXACT   EXACT   EXACT
B2    BUND    EXACT   BUND    EXACT   EXACT   EXACT
B3    BUND    BUND    ABS     ABS     BUND    BUND
```

## 2. Verdict: **broad treatment effect**

The preregistered branch reached is:

```text
4/5 improve, but 0/1/2/3 also shift substantially
  -> broad treatment effect; cannot attribute specifically to the new slots
```

Targets went EXACT 0/6 → 4/6. But **rows 2 and 3 gained no slot in either arm**
and moved EXACT 0/6 → 3/6 — a shift of the same magnitude. Whatever changed in
arm B improved preservation across rows that the treatment did not touch.

**Surface C is not established.** The result is consistent with the affordance
helping, and equally consistent with the treatment arm simply producing more
complete artifacts for some other reason.

### What the treatment *did* establish, cleanly

**The producer adopted the new interface without being told to.**

```text
slots offered      6/6
slots populated    6/6
bindings valid     6/6      cited id exists AND names a confirmation
                            that carries that row
output_provenance_* refusals   0
```

Three treatment runs, every required slot filled, every citation pointing at
the right confirmation, and not one of the five new refusal codes fired. The
`r2c` shape and the `v0+C` contract are usable as written. That is a real
result about the **interface**, and it is independent of the preservation
question.

### Positive controls were stable, not healthy

Rows 0/1 sat at EXACT 3/6 in **both** arms — stable, so the "positive-control
collapse" branch was not triggered. But 3/6 is not health: row 1, the live
control carried in from W1-J, was ABSENT / BUNDLED / NONVERBATIM across the
three control runs and only recovered in the treatment arm. A slot continues
not to guarantee preservation.

## 3. The control arm is worse than W1-H, and that matters

Same model, same r2, same v0, same fixtures, same canonical order, same
capability box — and:

```text
W1-H   P1 = 6/6 rows EXACT   P2 = 2/6   P3 = 6/6
W1-K   A1 = 1/6              A2 = 2/6   A3 = 1/6
```

Two perfect runs in one pack, none in the other, with **no declared variable
between them**. Cutting a fresh paired control was therefore the right call —
W1-H would have been a misleading baseline. It also caps how much any three-run
comparison in this line can carry: run-to-run variation in a fixed
configuration is of the same order as the effect being measured.

## 4. Secondary layers

```text
ARTIFACT PRODUCTION   6/6
AUTHORITY             6/6 CLEAN, 0 non-designated files
RESOURCE CONSUMPTION  3/3 all three resources, every run
STRUCTURAL            4/6 PASS
FIDELITY              control 5/4/4 findings; treatment 0/1/3
```

### A third tokenization form, in both arms

A1 and B3 refused with `observed_field_not_in_source` — but neither is padding.
Both declared the **entire header line as one unsplit string**:

```text
'Date, Supplier Name, InvoiceNumber, Amount, Currency, Status'
```

That is a third distinct form:

```text
W1-G O2   one field padded            sporadic slip
W1-J Q3   every field after the first  systematic split-without-strip
W1-K A1/B3  no split at all            the whole line as one token
```

It appeared in **both arms**, so it is not arm-related and says nothing about
r2c. **Tokenization stays parked** (`../w1i/DISPOSITION.md`). Recorded only
because the failure family is broader than either earlier pack showed.

## 5. One reporter column is void

`skill_match` reads `no` for the entire B arm. `grade.py` inherited W1-H's pin
to the r2 hash, so any arm on a different revision is marked a mismatch by
construction — **the same defect fixed in W1-I and logged as backlog B-2, which
I reintroduced by cloning from W1-H rather than from W1-I.**

Verified independently, from the frozen bytes: every B run's `SKILL.md` is
byte-identical to frozen r2c (`c9f9990133be9a1a`), every A run's to frozen r2
(`0230969ea7fd00ed`), each matches its recorded `skill_revision`, and
`run_batch` gated each run on its own arm's hash before executing. **No
contamination; a mis-pinned column.** `RESULTS.md` is left exactly as produced.

## 6. What may not be claimed

- N=3 per arm. **No percentages, no rates, no reliability estimate.**
- **Surface C is not shown to work.** The negative controls moved too.
- Nor is it shown *not* to work — the design cannot separate them from these six
  runs.
- Do not pool with W1-H, W1-I or W1-J.
- The clean interface adoption (6/6 populated, 6/6 bound) is a statement about
  **usability of the new surface**, not about preservation.
- §3's control-arm variance is an observation, not a measured variance estimate.

## 7. Disposition

```text
Surface C interface        USABLE — adopted correctly, unprompted, 6/6
Surface C preservation     NOT ESTABLISHED — broad effect, unattributable
confirmation preservation  still unexplained after order (W1-J) and
                           affordance (W1-K) were each isolated
```

Two mechanisms have now been isolated and neither accounts for the behaviour.
Before a third is proposed, §3 deserves attention: a fixed configuration
produced 6/6, 2/6, 6/6 in one pack and 1/6, 2/6, 1/6 in another. Until that
variation is characterised, three-run arms cannot resolve effects of this size,
and further single-variable packs risk measuring noise.

The honest next step is not another treatment. It is to establish how much this
system varies with **no variable moved at all** — a repeatability baseline, N
larger than 3, no schema or skill change — so that later experiments have a
scale to be read against.
