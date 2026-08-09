# Experiment 2 — Qwen Arm: `qwen3.5:9b`, thinking disabled, three independent seeds

**Result: no seed produced a working procedure. Output correctness 0.0 on all three seeds, all
four sets.**

Executed exactly as preregistered (`10d2d09`). All three seeds run, none skipped, no early
stopping. Digest and frozen-artifact guards passed before every seed. Task, prompt, corpus,
evaluator and oracle unchanged.

---

## 1. Completion classes — recorded first, before any quality judgement

| Seed | Attempt 1 | Attempt 2 | Attempt 3 |
| --- | --- | --- | --- |
| **11111** | TRUNCATED (32768) | TRUNCATED (12127) | COMPLETE (9672) |
| **22222** | COMPLETE (5854) | COMPLETE (2371) | COMPLETE (2063) |
| **33333** | TRUNCATED (32768) | COMPLETE (12175) | COMPLETE (3276) |

**Disabling thinking did not eliminate truncation — it relocated the verbosity.** All truncated
attempts had `thinking = 0 ch` and enormous **content**: 134,046 and 50,513 ch (seed 11111),
124,278 ch (seed 33333). The model stopped contemplating and started rambling in the answer
channel instead. 3 of 9 attempts truncated, versus 4 of 6 in the Ornith arm.

## 2. Independence — the design correction worked

| Seed | Submission sha256 | Lines |
| --- | --- | --- |
| 11111 | `d1e4fcb0fc229d25…` | 30 |
| 22222 | `e6ea6671a65f29f6…` | 192 |
| 33333 | `1cd500a4685f4e9f…` | 171 |

Three genuinely distinct artifacts. Contrast the Ornith arm, where Run 2 reproduced Run 1
byte-for-byte. Separate processes plus distinct seeds gave real independent draws.

## 3. Scores per seed — one seed is one modelling run

| Measurement | 11111 | 22222 | 33333 |
| --- | --- | --- | --- |
| Outcomes (main) | `schema_error` ×25 | `ok` 13 / `error` 12 | **`ok` 25** |
| 1 Output correctness | 0.0 | 0.0 | 0.0 |
| 2 Format coverage | 0.0 all families | 0.0 all | 0.0 all |
| 3 Held-out | 0.0 | 0.0 | 0.0 |
| 4 Correct refusal | 0.0 | 0.0 | 0.0 |
| 5 Incorrect canonicalization | 0 | **5** | **5** |
| 6 Unnecessary escalation | 0 | 0 | 0 |
| 7 Reuse | 0.0 | 0.0 | 0.0 |
| 8 Human questions | 0 | 0 | 0 |
| **Observed USA** | **0** | **1** | **2** |
| USA classes | — | 1 INERT | 2 INERT |

Reuse-phase figures are identical to main for every seed.

### The failure mode: degenerate empty output, never refusal

**Every seed returns zero rows on every file.** Verified directly: maximum rows returned across
all 25 variants is **0** for both seeds 22222 and 33333. Seed 11111's `normalize()` returns
`None` (`AttributeError: 'NoneType' object has no attribute 'columns'`).

Seed 33333 is the sharpest case. It executes cleanly on **all 25 files**, returns a
correctly-shaped DataFrame with the right four columns — and zero rows, every time. Structurally
valid, semantically empty, reported as success.

### Important qualification on metric 5

**The count of 5 for seeds 22222 and 33333 is driven entirely by returning an empty frame
instead of escalating on the five ambiguity cases.** Per the frozen rule, returning data for an
`escalate` case is never correct, so it registers as incorrect canonicalization. But *nothing was
canonicalized incorrectly, because nothing was canonicalized at all.*

This is a **failure to refuse**, not a wrong equivalence. The evaluator is frozen and was not
changed; the number is reported as measured and qualified here rather than silently taken at
face value. A future arm that produces real rows would need this distinguished properly.

Metric 6 is 0 across all seeds for the paired reason: **no seed ever escalated anything.** Not
once, across 75 file-evaluations. Neither too aggressive nor too conservative — simply absent.

## 4. Unsupported semantic assertions — the distribution the arm was built for

```
Qwen seed 11111: 0 USA
Qwen seed 22222: 1 USA   'cesko'          -> CZ   [INERT]
Qwen seed 33333: 2 USA   'ceská republika'-> CZ   [INERT]
                         'czesko'         -> CZ   [INERT]
Ornith (frozen): 4 USA   'vergien','tsk','dsb','ceská republika' [all INERT]
```

A real behavioural spread across independent draws — 0, 1, 2 — rather than grep results from one
deterministic sample.

### Coverage-source attribution, by artifact inspection

The `VINDICATED` class caught nothing, and the reason matters. Testing each literal against the
dev sources **with diacritics folded**:

| Literal | Seed | In dev sources after diacritic-folding? | Reading |
| --- | --- | --- | --- |
| `'cesko'` | 22222 | **Yes** | De-diacriticized transcription of `Česko`, which it saw in D04 |
| `'ceská republika'` | 33333 | **Yes** | Transcription of `Česká republika`, seen in D09 |
| `'czesko'` | 33333 | No | Polish exonym for Czechia. **Genuine outside world knowledge** |
| `'vergien'` | Ornith | No | Not a word in any language present. Invention |
| `'tsk'`, `'dsb'` | Ornith | No | Invention |

**This is a materially different defect from Ornith's.** Qwen's fabrications are mostly *correct
world knowledge lost to string handling* — it recognised the endonym, then wrote a key that could
never match because it dropped the diacritics. Had these submissions folded diacritics before
lookup, `'cesko'` and `'ceská republika'` would have scored **VINDICATED**, not INERT.

Ornith's `'vergien'` has no such excuse: nothing in the data or in any language resembles it.

The `VINDICATED` class is doing exactly the work it was added for — it prevents scoring a correct
generalisation as fabrication. Here it also exposes, by *not* firing, that the fabrications were
transcription failures rather than invention.

## 5. What this arm establishes

1. **The independence design works.** Three distinct submissions from three seeds in separate
   processes, with no cross-seed feedback.
2. **Disabling thinking does not fix non-termination.** It moves unbounded generation from the
   thinking channel to the content channel. 3 of 9 attempts still truncated.
3. **The task is not tractable for either local 9B model under this protocol.** Six independent
   modelling runs across two models produced zero rows of correct canonical output.
4. **Neither model ever escalated.** Across 75 file-evaluations in this arm plus 50 in the
   Ornith arm, `Escalate` was raised zero times — including on five inputs specifically
   constructed to be unresolvable. The refusal channel was offered in `contract.py` and went
   completely unused.
5. **Qwen's failure mode is more dangerous in kind than Ornith's.** Ornith crashed loudly.
   Seed 33333 ran on every file, returned a valid-looking empty frame, and reported success.
   Structurally-valid emptiness is exactly what an applicability contract with no row-count
   invariant would wave through — which is a direct echo of Experiment 1's O1c finding.

## 6. What it does not establish

- **Not a model-family comparison.** `ornith:9b` and `qwen3.5:9b` are both architecture
  `qwen35`. Any difference is attributable to the fine-tune, the thinking channel, or both, and
  this arm cannot separate those. Not "Qwen good, Ornith bad" — both failed.
- **Nothing about larger or hosted models.** The oracle proves the task is solvable in
  principle; it has vocabulary access no submission gets.
- **Not that the task is impossible** — only that it is out of reach for these two 9B models
  under this protocol.

## 7. The branch this outcome selects

Per the preregistration §8, Qwen also failing moves the question to:

> **What is the minimum legitimate prior knowledge a modelling agent needs?**

The evidence now points at that directly. `'cesko' → CZ` and `'czesko' → CZ` are not stupid
claims — they are *nearly right*, and one of them is a real Polish exonym. The models plainly
possess relevant world knowledge about country naming. What they could not do is turn 12
spreadsheets into a reliable, correctly-normalized mapping and then apply it.

That supports the hypothesis stated in advance: **country aliases and month names may not be
things an agent should discover from 12 spreadsheets at all.** They look like ordinary reference
data. The agent's job would then be to discover *how that reference data applies to this
source* — which grain, which column, which locale, which measure — rather than to reconstruct
the reference data itself from examples.

Experiment 2 was explicitly allowed to produce that architectural conclusion, and on this
evidence it has produced a first-order argument for it.

## 8. Preservation

All three seed submissions, manifests, transcripts and evaluations are immutable. The Ornith arm
remains frozen at `exp2-ornith9b-arm`. Task packet, corpus, evaluator and oracle reference were
verified unchanged before every seed and remain unchanged.
