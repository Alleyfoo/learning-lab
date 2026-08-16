# S2 — can correction and preference change supervision?

> **Research question.** Can this LLM become a better supervisor through
> experience, without changing the workers underneath it?

S1's key finding was reframed: the supervisor did not mainly fail because it
lacked memory. It failed because **explicit system state is not the same thing as
explicit system meaning.** In condition A it read perfectly real fields and
misinterpreted them -- `committing:false` became "dry-run mode" (normal for
enrichment), and `ledger_lines:2` vs `rows:3` became "possibly dropped data"
(those quantities do not describe the same thing). It was misunderstanding the
semantics of real values, not fabricating them.

That distinction shapes S2. There are two different kinds of learning, and they
must not become one memory:

```text
SYSTEM KNOWLEDGE        "What does this system mean?"      true for any operator
OPERATOR PREFERENCE     "What does this operator care about?"  supervision taste
```

## Memory v0

Two extremely boring append-only stores, nothing more:

```text
supervisor/knowledge.jsonl     system knowledge / corrections
supervisor/preferences.jsonl   operator supervision preferences
```

Each entry keeps the original human statement plus the structured interpretation
the model made (`kind`, `statement`, `original`, `basis`, `scope`, `at`,
`from_run`). No embeddings, no vector store, no confidence, no decay, no
retrieval scoring. Load every line and put it in front of the model. We have ten
lines' worth of memory; let's enjoy that luxury.

## The experiment

1. **Before.** Review the S1-A fixture (`fazerish-invoicing`, a healthy
   enrichment worker) with NO memory. Reproduce the A misreads.
2. **Learn.** Give the supervisor the frozen operator feedback (`feedback.txt`),
   which contains BOTH classes. `learn()` distils it into `knowledge.jsonl` and
   `preferences.jsonl`. We observe whether it classifies correctly.
3. **Cold restart -- transfer.** Wipe all conversation context. Reload
   `knowledge` + `preferences` from disk. Review a **different** healthy
   enrichment worker (`acme-order-cost`, a genuinely new execution -- different
   name, customer and purpose, same clean shape: non-committing, an inbox
   ledger, thin history, unexercised refusals). The supervisor must apply the
   *learned* memory, not recall worker X.
4. **Cold restart -- safety.** With the same memory loaded, review the S1-B
   fixture (`room-reservation` effect failure). It must still alert.

## Predictions

```text
correction  -> changes interpretation of system state
               (dry-run concern disappears; ledger-vs-rows concern disappears)
preference  -> changes threshold for interruption
               (thin-history and unexercised-refusal advisories disappear)
neither     -> suppresses genuine operational failure
               (B's effect failure must STILL be surfaced prominently)
```

Passing all three proves something stronger than "remember what I said about
worker X": architectural correction and attention preference transfer to a worker
the supervisor has never seen, without blunting real failure.

## Explicitly deferred (unchanged from S1)

memory framework beyond the two jsonl stores · rulebook · improvement register ·
scheduled wake-ups · event triggers · personality · fixed report schema ·
self-modification · automatic actions.

## Not fixed, deliberately

The two fleet defects S1 surfaced (`pending_exceptions` misses inbox exceptions;
`summary.committing` vs `worker.committing` for a never-run committing worker)
are recorded in `s1/discoveries.jsonl` and left unfixed. Fixing them would wander
back into developing the inherited fleet. They are pre-existing supervisor
discoveries for the improvement-box experiment (S3) to encounter.