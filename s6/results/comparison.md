# S6 — old S4 vs harnessed S4 (regression comparison)

> Same frozen S4 fleet (hash `a38f6a5a1382ab03`), same `glm-5.2:cloud`, same
> `temperature=0.2` / `num_ctx=131072` / `max_turns=10`, same broad S1 prompt,
> same oracle, no memory/rulebook. The only variable is the execution boundary:
> old S4 ran through `core.review`; harnessed S4 runs through
> `SupervisorHarness.run`. Exact prose and tool calls need not match; behaviour
> and usefulness must. New misses and surprises are preserved, not hidden.

## At a glance

| dimension | old S4 (`20260816T182432Z`) | harnessed S4 (`20260816T190857Z`) |
|---|---|---|
| execution path | `core.review` | `SupervisorHarness.run` |
| python used | yes | yes |
| python calls | 4 | 4 |
| turns | 3 | 2 |
| stop reason | final | final |
| python errors (recovered) | 2 | **0** |
| scan verdicts (HIT/PARTIAL/MISS) | 7/0/0 | 6/1/0 |
| **hand-judged** signals hit | **6/7** (C5 MISS) | **6/7** (C5 MISS) |
| reconstructability canary | n/a (no event log) | **PASS** (`replay(events) == model_request.messages`) |
| authority bound | implicit (in `bench`/`core` prose) | explicit (`Policy`; `analyse_copied_data` only) |

## Behaviour preserved — the same six, the same miss

Both runs are cold (no memory, no rulebook) over the identical 70-worker fleet
with the unchanged S1 prompt. Both reach for computation on their own (4 python
calls each, never prompted). Both hit **L1, L2, C1, C2, C3, C6** and both
**miss C5** (engine concentration / blast-radius).

The C5 miss is the same *conception* gap in both: the data is in front of the
supervisor, but it never forms the question "how concentrated is this fleet on
shared engines?" S5 later showed this exact miss can be taught (the
concentration/blast-radius method transfers). S6 preserves the miss cold — which
is the right outcome: the harness is a refactor/proof round, not an intelligence
upgrade, so the cold supervisor's conception gap must survive unchanged.

### The scan vs hand-judgement on C5 (the recurring false-positive shape)

- **Old S4:** scan marked C5 `HIT` — a **false positive** (matched `share` inside
  "a shared source" in the C1 section). Hand-judged `MISS`.
- **Harnessed S4:** scan marked C5 `PARTIAL` (matched only the core term
  `enrichment`, no discriminating term). Hand-judged `MISS`.

So the scan moved (HIT → PARTIAL) but the hand-judged verdict did not (MISS →
MISS). This is the third round where the concentration-finding scan over- or
under-counts (S4 C5 false-positive HIT, S5 BEFORE false-positive HIT, S6 C5
PARTIAL). The authoritative verdict is hand-judged in every case; the scan is a
non-authoritative hint, as labelled.

## A real difference, and it is the S6 point: 0 errors vs 2

Old S4 made **2 python errors** — the fresh-namespace `NameError` (the model
assumed bench bindings persisted across calls; they do not), recovered in a
third turn by re-binding `workers = snapshot["workers"]`. Harnessed S4 made
**0 errors** and consolidated all 4 calls into a single turn 0, then answered
in turn 1.

This is not an intelligence difference. It is the **tool-contract difference**
the S6 spec predicted. The `python_analysis` tool's contract *explicitly
declares* the fresh-namespace semantics ("each call runs in a fresh namespace;
bindings do not persist; re-bind what you need on every call"). Behind that
stated contract, the model wrote self-contained calls and did not assume
persistence. With the contract declared, the S4/S5 M-002 `NameError` is now
separable: it is "the model misunderstood a stated contract" if it recurs, not
"the harness failed to state the tool's semantics." Here it did not recur.

**The harness did not silently turn the bench into a persistent kernel** to
eliminate the error — that was explicitly forbidden (it would hide a real
tool-semantics question). The bench is unchanged: fresh namespace per call,
deepcopy of the snapshot, no `open`/shell/network. The self-test confirms `os`
and `open` are still refused *behind the harness*. The error dropped because the
contract stated the semantics, not because the semantics changed.

## Usefulness preserved

The harnessed final report is a genuinely useful large-fleet supervision report:
it leads with the 6 `hidden-exception-*` workers invisible to
`pending_exceptions` (C6 / D-001 at scale), the two open investigations (L1/L2),
the 10 stale confirmations not re-confirmed after promotion (C3), the 5
post-promotion regressions at 80% refusal (C2), and the northwind refusal trend
(C1). It also re-derives the same system-improvement suggestions cold
(investigation auto-opening gap; stale-confirmation alerts; post-promotion
regression detection) — the same shape as old S4's cold re-derivation of D-001's
remedy and the T4 re-confirmation proposal. The harness did not make the
supervisor less useful; the demonstrated capability is intact.

## Reconstructability — the invariant holds on the real session

The append-only session record has 18 events in the expected order:

```
session_started → context_added → tools_declared → authority_declared
→ model_request → model_response
→ tool_call → tool_result  (×4)
→ model_request → model_response → supervisor_output → session_finished
```

`replay(events)` rebuilds the per-turn message lists from events alone.
Verified against the saved session (`s6/results/run.json` / `session.jsonl`):

```
replay(events) == model_request.messages : True
session.jsonl round-trips to the same 18 events : True
replayed turns (2) == turn_count (2) : True
```

Anything model-visible — the operator prompt, the fleet stimulus, the tool
contract (with the fresh-namespace declaration), the authority statement, every
model request/response, every tool call/result — is reconstructable from the
session record. This is the DeepSeek-Harness idea we kept, in its smallest form.

## Authority — explicitly bounded, not widened

- One tool registered: `python_analysis`, authority class `analyse_copied_data`
  (in `ALLOW`).
- One context registered: `fleet`, authority class `read_fleet` (in `ALLOW`).
- `NEVER` classes declared and enforced: `modify_workers`, `modify_models`,
  `promote_versions`, `execute_runtime`, `apply_effects`, `alter_customer_data`,
  `filesystem_unrestricted`, `shell`, `network`.
- The self-test refuses a `apply_effects` tool and an unknown-authority tool at
  registration, and confirms `os`/`open` are still refused behind the harness.

Harnessing did not widen power: the supervisor behind the harness has exactly
the read-only, analyse-a-copy authority it had inside `core.review`, now stated
declaratively and checked.

## Existing code remains available

`core.review` is untouched and still importable (self-test asserts it). S1–S5
ran through `core.review` and still can. The harness is a parallel path through
the same primitives (`core._chat` for the model round-trip, `bench.run` via the
tool for analysis). `snapshot`/`memory`/`rulebook` became providers
(`FleetContext`/`MemoryContext`/`RulebookContext`), not rewrites.

## Verdict

S6 passes its stop condition:

1. ✅ one clear harness boundary (`SupervisorHarness.run`);
2. ✅ reconstructable append-only session record (canary holds on the real run);
3. ✅ authority explicitly bounded and enforced;
4. ✅ frozen S4 still demonstrates useful large-fleet supervision through the
   harness (6/7 hand-judged, same C5 miss, same 4 calls, useful report);
5. ✅ existing S1–S5 behaviour/code remains available (`core.review` intact,
   providers wrap existing modules).

The one honest delta — **0 errors vs 2** — is the S6 thesis confirmed: stating
the tool's semantics in an explicit contract is separable from (and did not
require) changing the tool's semantics. The supervisor's intelligence is
unchanged; its execution substrate is now explicit and reconstructable.