# Workorder v0.6 — Recurring source identity (implementation, narrow)

**Architecture:** [`v0.6_recurring_source_identity.md`](v0.6_recurring_source_identity.md)
(the design note, commit `64a19fb` + amendments). That note is the authority on
*what* and *why*; this work order is the narrow *how*, sequenced for the
September-Acme probe. Read the note first — especially §3.0 (separate contract
file), §5.1 (one open input set), §6.1 (atomic run_input), §6.2 (digest-truthful
raw retention).
**Status:** design closed; implementation not started. This is the work order.
**Date:** 2026-08-18

## Scope and the one hard coupling

The probe is Acme September (two workbooks, no modeller). But the inbox path
today reads `w.identity["adapter_sheets"]` (`fleet/inbox.py:274-275`); v0.6 moves
the spec source to `input_contracts/v<N>.json`. **That move breaks Fazerish
unless Fazerish is migrated in the same step** — Fazerish is the only worker that
exercises the xlsx inbox today. So Fazerish migration is in the critical path,
not optional. The work order is therefore: contract file + loader → migrate the
inbox spec source AND Fazerish atomically → give Acme the operational shape →
input set + binding → atomic run_input → digest-safe retention → operator UI →
September probe.

Everything below reuses existing machinery: `adapters/xlsx.py`
(`convert`/`write_collections`/`SheetSpec`/`specs_from`), the `fleet/inbox.py`
poll loop, `fleet.record_run`, and the run engine. No new converter, no new
engine, no LLM.

**Backward-compat gate:** `input_contracts` is optional. Workers that take a JSON
request and have no sheet contract (`room-reservation`, `training-room`) keep
working unchanged — the inbox spec-source change is gated on
`w.input_contract is not None`, falling back to today's behaviour.

Convention: after each touched module, `python <module>.py --self-test` (the
repo's test convention; no pytest).

---

## Phase 1 — `input_contracts/v<N>.json` + loader

**File:** a new per-worker dir `<worker>/input_contracts/v<N>.json`, same `N` as
the current model version. Schema (contract only — shape, not roles):

```
{ "roles": {
    "statement":    {"sheet": "Statement",    "header_row": 3, "collection": "statement"},
    "transactions": {"sheet": "Transactions", "header_row": 2, "collection": "transactions"}
}}
```

Slot kind (sole/shared), role labels, required-ness, `input_adapter`,
`work_item_identity` stay on **identity** (stable roles) — see Phase 2/3.

**Loader:** `fleet/fleet.py` `Worker` gains an `input_contract` property that
loads `<dir>/input_contracts/v<current_version>.json` (mirroring how the version
model is loaded), returning `None` when absent (the back-comat gate). Add a
helper to turn a contract into `SheetSpec`s reusing `xlsx.specs_from`-shaped
logic (sheet/header_row/collection) — or extend `adapters/xlsx.py:specs_from`
to accept a contract dict.

**Self-test (fleet.py):** a scratch worker with `input_contracts/v1.json` loads
it; a worker without it returns `None`; a version bump reads `v2`.

## Phase 2 — Migrate the inbox spec source + Fazerish (atomic)

**inbox.py:** at `inbox.py:273-275`, source the specs from `w.input_contract`
(via the Phase 1 helper) when present; else fall back to today's
`w.identity["adapter_sheets"]` path (so non-contract workers are unaffected).
The `SheetSpec`→`convert`→`write_collections` flow is unchanged.

**Fazerish identity:** introduce a stable `source_roles` block on
`fleet/workers/fazerish-invoicing/worker.json`:

```
source_roles: {
  order_lines: {label: "order lines", slot: shared, required: true},
  price_list:  {label: "price list",  slot: shared, required: true}
}
input_adapter: "xlsx"
work_item_identity: "content_digest"
```

and remove the shape (sheet/header_row/collection) from the old `adapter_sheets`
(keep `input_adapter`/`work_item_identity`). Write
`fleet/workers/fazerish-invoicing/input_contracts/v1.json` from the old
`adapter_sheets` (Order lines/header 1/order_lines; Price list/header 1/
price_list). Optionally add `origin` to fazerish's `versions/v1.json` for
provenance parity with Acme.

**Self-test (inbox.py + operate.py):** the existing Fazerish end-to-end
(save_to_inbox → poll → ledger line + processed move + committing effect) stays
green after the spec-source move. This is the gate that the migration is atomic
and non-breaking.

## Phase 3 — Give Acme the operational shape

**`fleet/workers/acme-august-recon/worker.json`:** add stable roles + operational
policy (no shape):

```
source_roles: {
  statement:    {label: "supplier statement", slot: sole, required: true},
  transactions: {label: "ledger transactions", slot: sole, required: true}
}
input_adapter: "xlsx"
work_item_identity: "content_digest"
```

(Keep existing `name`/`purpose`/`task`/`base`/`trigger`/`customer`.) Note: role
labels drop cadence — "supplier statement", not "monthly supplier statement"
(design note wording fix).

**`fleet/workers/acme-august-recon/input_contracts/v1.json`:** from the existing
`origin` in `versions/v1.json` — statement: Statement/header 3/statement;
transactions: Transactions/header 2/transactions. `origin` in v1.json is
unchanged (founding provenance).

**Self-test (fleet.py):** Acme's `input_contract` loads and its collections
align one-to-one with `versions/v1.json` `sources` keys (statement, transactions).

## Phase 4 — Input set + binding (one open set per worker)

New small module `fleet/input_set.py` (or a thin extension of inbox), persisted
at `<worker>/input_set.json`: the worker's **one open input set** — which slots
are bound, to which document/digest/materialized path. v0.6 limitation: one open
set per worker (design §5.1); no `input_set_id` yet, but the run record carries
`input_set` so it is forward-compatible.

**Binding** an arriving document to a slot:
1. operator chooses the slot (explicit; never filename-inferred);
2. validate against that slot's contract via the existing `convert` (refusal →
   exception, no binding);
3. materialize into `sources[role].path` via the existing `write_collections`
   (overwritten; no archive);
4. capture the raw digest; record the binding in the open input set.

**Completeness:** all required slots bound → run. **Control-flow change to
`inbox.poll`:** for a multi-sole-slot worker (Acme), polling one file **binds
and stages**, it does NOT run — a reconciliation cannot run on one side. For a
shared-slot worker (Fazerish), one document binds all shared slots at once →
complete on first arrival → run immediately (preserves today's per-file run).

**Self-test (input_set.py):** Acme — bind a statement → set partial (1/2), no
run; bind a transactions → complete (2/2) → run fires. Fazerish — bind one
workbook → complete (2/2) immediately → run.

## Phase 5 — Atomic `run_input` on `record_run`

**`fleet/fleet.py:record_run`** gains `run_input=None`; merge it into `record`
in each of the three branches (257/275/284) before the single `_append` (292).
The recurring path assembles `run_input` (design §6: `input_set`,
`input_contract` version, `model` version, per-slot
document/digest/sheet/header_row/materialized_as) and passes it in. Existing
callers pass nothing → back-comat.

**Self-test (fleet.py):** a run with `run_input` writes one line carrying it; a
run without it writes the legacy line unchanged.

## Phase 6 — Collision-safe raw retention

**`fleet/inbox.py:315`:** move to `processed/` namespaced by digest (e.g.
`processed/<digest>.<ext>` with the original name kept in the ledger), not the
bare filename, so two same-named different-bytes arrivals both survive. This is
**raw retention**, not a materialization archive (materialized JSON is still
overwritten per run). Required so the digest the run records is truthfully
retrievable (design §6.2).

**Self-test (inbox.py):** two files, same name, different bytes → both retained
in `processed/`, distinguishable by digest; ledger carries both.

## Phase 7 — Operator binding surface (v0.5 inbox panel)

Extend `supervisor/operate.py` + the v0.5 `_render_inbox_panel` with a
bind-to-slot step for multi-slot workers: operator drops
`supplier_sept.xlsx` → picks the `statement` slot → bind; drops
`ledger_sept.xlsx` → picks `transactions` → bind → complete → run. For
shared-slot workers (Fazerish) a single upload binds all shared slots (no
choice). Thin wrappers over Phase 4 (no dashboard execution path — same
principle as v0.5). AppTest simulates bindings via `session_state`.

## Phase 8 — September Acme acceptance probe

**Fixtures:** a September version of `data/acme-august/` — `supplier.xlsx`
(Statement, header 3, different numbers) and `ledger.xlsx` (Transactions, header
2, different numbers). Same shape, new content.

**End-to-end (no modeller):**
- bind `supplier_sept.xlsx` → `statement` → validate against
  `input_contracts/v1.json` → materialize → set partial (1/2);
- bind `ledger_sept.xlsx` → `transactions` → validate → materialize → complete
  (2/2) → run;
- the run record is ONE atomic `runs.jsonl` line carrying `model=v1`,
  `input_contract=v1`, `input_set=<X>`, and per slot
  document/digest/sheet/header_row/materialized_as;
- the raw arrivals are retained by digest → "show me the exact source used in
  this run" resolves worker → run → slot → digest → retained raw bytes.

**Negative probe:** a shape-changed October statement (header moved to row 4) →
binding fails at validation → exception, no run → operator may choose re-model
(new model version + new `input_contracts` version + new founding `origin`) as a
separate explicit action.

This probe is the gate for v0.6.

---

## Explicitly deferred (per design note §8)

No filename-pattern authority · no contract inside `versions/v1.json` · no
separate run/linkage record (run_input is a kwarg) · no multiple input sets in
flight (one open set per worker) · no connector work · no materialization archive
(raw retention only) · no decoupled model/contract version advancement.

## Sequencing risk to watch

Phase 2 MUST land Fazerish's `input_contracts/v1.json` in the same commit that
moves the inbox spec source — otherwise the live xlsx inbox breaks between
commits. The Phase 2 self-test (Fazerish end-to-end) is the gate that proves the
migration is atomic.