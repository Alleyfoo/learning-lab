# S6 — findings: the supervisor behind an explicit harness contract

> **Research question.** Can the existing supervisor run behind a small explicit
> *harness contract* while preserving its demonstrated behaviour and authority
> boundaries?

S6 is a **refactor/proof round, not a new intelligence experiment.** S1–S5 ran
the supervisor through `core.review` — a home-grown agent loop that mixed prompt
assembly, model calls, tool dispatch and recording into one function. That was
fine for discovering what the supervisor can do, but it left every future result
partly a statement about the quirks of that loop. S4 and S5 both hit the same
fresh-Python-namespace `NameError`, and it was impossible to say whether that was
"the model misunderstood the tool" or "the harness never stated the tool's
semantics," because there was no explicit tool contract to point at.

S6 builds the smallest explicit `SupervisorHarness` boundary around what already
exists, then proves it preserves behaviour and authority. It is the floor that
lets the staircase (S1 notice / S2 learn / S3 reason / S4 invent / S5 transfer)
continue without every future result being partly about the home-grown loop.

## Headline

**Yes — the supervisor runs behind the harness with its demonstrated behaviour
and authority intact, and the explicit tool contract changed exactly one thing:
the S4/S5 fresh-namespace `NameError` did not recur.**

Frozen S4 through the harness, hand-judged against the same oracle:

```text
                        old S4 (core.review)      harnessed S4 (SupervisorHarness)
stimulus                a38f6a5a1382ab03          a38f6a5a1382ab03  (identical)
model/settings          glm-5.2:cloud, t=0.2      glm-5.2:cloud, t=0.2  (identical)
prompt                  s1/prompt.txt             s1/prompt.txt  (identical)
memory/rulebook         none                      none  (cold, identical)
python calls            4                         4
turns                   3                         2
stop reason             final                     final
python errors           2 (recovered)             0
hand-judged signals     6/7 (C5 MISS)             6/7 (C5 MISS)
reconstructable record  no                        yes (canary PASS)
authority bound         implicit                  explicit (Policy)
```

The same six signals (L1/L2/C1/C2/C3/C6) are found; the same conception-gap miss
(C5, engine concentration) is preserved cold; the same 4 unprompted python calls
are made. The harness did not make the supervisor smarter or duller. It made its
execution substrate explicit and reconstructable — and, as a direct consequence
of stating the tool's semantics, eliminated the recurring tool-use error.

## The one delta, and it is the S6 thesis

Old S4 made **2 python errors** — the `NameError` from assuming bench bindings
persist across calls (they do not; each call is a fresh namespace), recovered in
a third turn. Harnessed S4 made **0 errors** and consolidated all 4 calls into
turn 0.

This is not an intelligence change. The `python_analysis` tool's contract
**explicitly declares the fresh-namespace semantics**: "each call runs in a
fresh, independent namespace; variables, imports and bindings you create in one
call do not persist to the next; re-bind anything you need at the top of every
call." Behind that stated contract, the model wrote self-contained calls and did
not assume persistence.

This is exactly the separability the S6 spec wanted. Before the harness, a
`NameError` was ambiguous — "the model misunderstood the tool" or "the harness
failed to state it"? After, the contract states it, so a future `NameError` is
unambiguously "the model misunderstood a stated contract." Here the model did not
misunderstand, so the error did not happen.

**The bench was not turned into a persistent kernel** to eliminate the error —
that was explicitly forbidden (it would hide a real tool-semantics question). The
bench is unchanged: fresh namespace per call, `deepcopy` of the snapshot, no
`open`/shell/network. The self-test confirms `os` and `open` are still refused
*behind the harness*. The error dropped because the contract stated the
semantics, not because the semantics changed.

## C5 — the same conception gap, preserved cold (and that is correct)

Both runs miss C5 (engine concentration / blast-radius). Hand-judged, both are a
clean MISS: no concentration language, no per-engine worker counts, no
`execute_enrichment` in any python stdout. The supervisor had the data in front
of it but never formed the question "how concentrated is this fleet on shared
engines?" — the same conception failure as S4, by design.

The scan moved (old: false-positive `HIT`; new: `PARTIAL`) but the hand-judged
verdict did not (`MISS` → `MISS`). This is the third round where the
concentration-finding scan over- or under-counts (S4 C5, S5 BEFORE, S6 C5). The
authoritative verdict is hand-judged; the scan is a non-authoritative hint, as
labelled. Preserving the C5 miss cold is the right outcome — S5 already showed
this miss is teachable; S6 is not an intelligence round and must not silently
fix it.

## Reconstructability — the invariant holds on the real session

The append-only session record (`s6/results/session.jsonl`, 18 events) is in the
expected order:

```text
session_started
context_added          (fleet stimulus, placement=user)
tools_declared         (python_analysis contract, incl. fresh-namespace)
authority_declared     (ALLOW / NEVER)
model_request  → model_response
tool_call → tool_result   (×4, all turn 0)
model_request  → model_response → supervisor_output
session_finished
```

The DeepSeek-Harness idea we keep — *anything model-visible must be
reconstructable from the session record* — is made executable by `replay(events)`,
which rebuilds the per-turn message lists from events alone. Verified against the
saved session:

```text
replay(events) == model_request.messages        : True
session.jsonl round-trips to the same 18 events : True
replayed turns (2) == turn_count (2)            : True
```

Everything the model saw — the operator prompt, the fleet stimulus, the tool
contract (with the fresh-namespace declaration), the authority statement, every
request/response, every tool call/result — is recoverable from the record. We
did not copy DeepSeek's whole event system; we kept the one idea that matters for
a research instrument.

## Authority — explicitly bounded, not widened

```text
ALLOW  read_fleet, analyse_copied_data, read_memory, read_rulebook,
       write_session_log, write_improvement_proposals
NEVER   modify_workers, modify_models, promote_versions, execute_runtime,
        apply_effects, alter_customer_data, filesystem_unrestricted, shell, network
```

The harnessed run registered one tool (`python_analysis`, `analyse_copied_data`)
and one context (`fleet`, `read_fleet`) — both in `ALLOW`. The self-test refuses
a `apply_effects` (NEVER) tool and an unknown-authority tool at registration, and
confirms `os`/`open` are still refused behind the harness. Harnessing did not
widen power: the supervisor has exactly the read-only, analyse-a-copy authority
it had inside `core.review`, now stated declaratively and checked.

## Existing code remains available

`core.review` is untouched and still importable (the self-test asserts it). S1–S5
ran through `core.review` and still can. The harness is a **parallel path**
through the same primitives: `core._chat` for the model round-trip, `bench.run`
(via the `python_analysis` tool) for analysis. `snapshot` / `memory` / `rulebook`
became providers (`FleetContext` / `MemoryContext` / `RulebookContext`), not
rewrites — `MemoryContext` even reuses `core._memory_preamble` so the rendered
text is identical. No S1–S5 code was rewritten around the abstraction.

## The harness itself

`supervisor/harness.py` is one module:

- **`Tool`** — `name, description, input_schema, output_schema, authority_class,
  execute`. The `python_analysis` tool wraps `bench.run`; its description states
  the fresh-namespace semantics.
- **`ContextProvider`** — `name, authority_class, placement (system|user),
  provide`. Built-ins: `FleetContext`, `MemoryContext`, `RulebookContext`.
- **`Policy`** — closed `ALLOW`/`NEVER` vocabulary; validates tools and contexts
  at registration.
- **`EventLog`** — append-only, typed, sequenced, stamped events.
- **`SupervisorHarness.run(operator_prompt, *, max_turns)`** — assembles the
  system message (operator prompt + system-placement context + tool contracts +
  authority statement) and user message (fleet stimulus), runs the model loop,
  emits the event log.
- **`replay(events)`** — rebuilds per-turn messages from events alone (the
  reconstructability invariant, executable).
- **`_self_test()`** — no model call; asserts the policy canaries, the
  fresh-namespace declaration, a stub session through the boundary, the
  reconstructability canary, the sandbox-canary, and that `core.review` is
  intact.

## What this round does NOT do

- **No new intelligence claim.** The supervisor's capability is unchanged; S6 is
  a refactor/proof round.
- **No new model, no new seed.** GLM-5.2:cloud only (standing constraint).
- **No S5 variance, no C3 method, no method promotion, no memory extension, no
  rule promotion** — all deferred per the S6 memo.
- **No DeepSeek installation, vendoring, TypeScript rewrite, or dependency.** Its
  concepts are evaluated in `s6/notes/deepseek_harness.md` only.
- **No rewrite of S1–S5 code.** `core.review` stays; providers wrap existing
  modules.
- **No persistent kernel.** The bench's fresh namespace is declared, not
  abolished.
- **No framework for its own sake.** The harness is the smallest boundary that
  makes context/model/tools/authority explicit and reconstructable.

## Observations

- **Stating tool semantics is separable from changing them.** The `NameError`
  dropped not because the bench became stateful but because the contract declared
  the fresh-namespace rule. This is the cleanest possible confirmation of the S6
  thesis: the home-grown loop's quirks were load-bearing on results, and an
  explicit contract removes one of them without touching the tool.
- **The conception gap is stable across the boundary.** C5 MISS cold in old S4
  and harnessed S4 alike. The harness does not invent intelligence; it preserves
  it. S5's method-transfer result is what teaches past this gap, not the harness.
- **The scan is not the verdict, round three.** C5 read HIT (old) and PARTIAL
  (new) to the scan, MISS (both) hand-judged. The concentration-finding
  false-positive shape is now reproducible across three rounds; the hand-judged
  `FINDINGS.md` remains authoritative.
- **One turn of clean computation.** All 4 calls consolidated into turn 0 with no
  errors, then the answer in turn 1. Old S4 needed 3 turns because the error and
  recovery split the work. The contract made the model's plan cleaner, not deeper.

## Preserved artefacts

```text
supervisor/harness.py         the SupervisorHarness boundary (Tool / ContextProvider /
                              Policy / EventLog / replay / self-test)
s6/spec.md                    frozen S6 spec
s6/notes/deepseek_harness.md  DeepSeek-Harness concept evaluation (research note)
s6/run.py                     frozen S4 through the harness; reuses s4/run.py assess
s6/results/run.json           full session record + assessment + comparison
s6/results/session.jsonl      the append-only event log (18 events)
s6/results/evidence.json      first-pass keyword scan (non-authoritative; C5 PARTIAL)
s6/results/comparison.json    old vs harnessed S4 (machine-readable)
s6/results/comparison.md      old vs harnessed S4 (human-readable)
s6/results/run.log            console transcript
s6/results/FINDINGS.md        this file (authoritative hand-judged verdicts)
```

## Verdict against the stop condition

S6 passes when all hold — and all hold:

1. ✅ supervisor execution goes through one clear harness boundary;
2. ✅ context, model calls and tools produce a reconstructable append-only
   session record (canary holds on the real run);
3. ✅ authority is explicitly bounded and enforced;
4. ✅ frozen S4 still demonstrates useful large-fleet supervision through the
   harness (6/7 hand-judged, same C5 miss, same 4 calls, useful report);
5. ✅ existing S1–S5 behaviour/code remains available rather than rewritten.

**Then stop.** The harness is no longer speculative infrastructure. It is the
floor that lets the staircase continue without every future result being partly
about the quirks of the home-grown agent loop.

## Next (not done in S6, per the memo)

The staircase's natural continuations remain as previously deferred: S5 variance
(how reliable is the method transfer); the C3 cohort-rigor method (M-001, the
second teachable method); improvement-register and rule classes (the remaining
two learning classes); and the "repeated useful questions become explicit
machinery" loop (S5's method-3 → a `concentration` view in `snapshot.build`,
after repetition evidence). The harness is now the substrate those run on.