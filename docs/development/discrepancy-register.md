# Discrepancy register

Places where a document and the repository disagree, with a disposition for each.

**This file has no authority.** It records disagreements and what was decided about them; it never resolves one by asserting a new fact.

Dispositions are one of four:

| Disposition | Means |
| --- | --- |
| `fix documentation` | The document is wrong. Correct it. Anyone may do this. |
| `fix authority` | The authority document is wrong. **Roundtable only.** |
| `create roadmap item` | Resolving it is real work. Route through [`initiatives.md`](initiatives.md) for Roundtable disposition. |
| `confirm as-is` | Not actually a disagreement. Record why, so it is not re-raised. |

Each entry states how it was established, so a later reader can re-check it rather than believe it.

---

## D1 — `.handoff.md` was stale by two closed packs

**Status:** resolved on this branch.
**Disposition:** `fix documentation`.

**Established by:** `.handoff.md` on `main` was titled "Handoff - W1-J executed and closed", while `git log` shows `dd10537` closing W1-K and `205c1a8` freezing W1-L afterwards. `work_interface/BACKLOG.md` also records B-1 and B-2 as closed in W1-L, which the handoff did not mention.

**Why it matters:** a handoff is the document a new worker reads first. This one described a work front that had already been superseded twice, and nothing in the repository said it could not be trusted. This is the concrete failure that motivated the precedence rule.

**Resolution:** `.handoff.md` rewritten to the actual state — W1-K closed, B-1/B-2 closed, W1-L frozen and not executed, B-4 still in progress, B-3 deliberately open — and marked non-authoritative in its own header. The engineering system now ranks handoffs last (§7), so this class of drift cannot silently win again.

---

## D2 — `README.md` describes the supervisor workspace at v0.1

**Status:** resolved on this branch.
**Disposition:** `fix documentation`.

**Established by:** `README.md` § "Supervisor Workspace v0.1" and the repository map row for `supervisor/` both say v0.1. `supervisor/app.py`'s module docstring opens "Workspace v0.3 -- the Supervisor Streamlit surface, recentred on the System Map, with the modeller integrated as a Define work flow", and version markers in `supervisor/*.py` and `fleet/*.py` count v0.3 ×15, v0.4 ×14, v0.5 ×30, v0.6 ×27. `README.md` was last changed in `1326d3b` (2026-08-17); `supervisor/app.py` in `eef0259` "feat(v0.6)" (2026-08-18).

The same section says the pieces "are still split across separate modeller, fleet/map and supervisor surfaces" and that "the next product step is to recenter them" — work the v0.3 docstring states has already landed.

**Resolution:** README's supervisor section and repository-map row corrected to point at the live module docstring as the current description rather than restating a frozen version number. The feature list was **not** rewritten: enumerating what v0.6 provides is product description, and `PRODUCT.md` owns that (see D3).

---

## D3 — `PRODUCT.md` priorities did not match the live v0.2–v0.6 system

**Status:** resolved, and narrowed to four named residual gaps.
**Disposition:** `fix authority` — performed by Roundtable's authorisation in issue #5, not by a Coder acting on the finding.

**Originally established by:** `PRODUCT.md` § "Current product priorities" listed six items as "the next meaningful product work"; `supervisor/app.py` described several of them as implemented. `PRODUCT.md` was last changed 2026-08-17; the v0.2–v0.6 work landed 2026-08-18.

**How it was resolved.** The suspicion was a lead, not a verdict. Each of the six priorities was re-grounded against live source in issue #5. Two are delivered; four are partially delivered; none was undelivered. The gaps are preserved rather than swept up into a "product direction closed" claim.

| # | Priority | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | Company as the top-level object | **partial** | Delivered: `system_map.parse_selection` types `scope:X` as `{"kind":"company"}`; `lanes()`/`scope_of()` derive lanes from each worker's declared `customer`; `app.py` `_render_company_panel` gathers a company's workers, incoming data, destinations and an add-data action; pre-worker identity via `incoming._read_intake` + `build(extra_scopes=…)`. Gap: nothing scopes the workspace to one company — `build()` renders every scope at once. |
| 2 | Incoming-data browser | **partial** | Delivered: `incoming.scan` returns the `data/` library and per-worker inbox/processed/exceptions; `_file_entry` carries `{name, kind, sheets}`; `app.py` `_render_incoming_browser` marks `worker:` / `no worker link` / `model exists` / `adapter`. Gap: `_file_entry` carries no columns or rows. Columns and samples exist only in `define.discover_workbook` (5-row preview), reachable only from the Define-work button, which `app.py` shows only when `worker is None and not has_model`. |
| 3 | System map as primary surface | **partial** | Delivered: `st.tabs` puts "System Map" first; it is the centre column with browser left and assessment on top; `system_map` self-test asserts `build()` writes nothing; pre-worker scope nodes render. Gap: `build()` emits nodes only from workers, scopes and shared executors — no incoming file/workbook/sheet node, and no edge from an arriving file to the work it became. |
| 4 | Modeller embedded in company context | **delivered** | `app.py` Define-work button -> `_render_discover_stage` (discover/declare/validate/materialize) -> the unchanged modeller journey -> deterministic preview -> explicit human-gated "Establish worker" -> `_clear_define()` and rerun return to the map with the new worker in its company lane. `customer` is captured at establish. Covered end to end by `define.py --self-test`. |
| 5 | Supervisor beside the map | **partial** | Delivered: `_render_assessment_banner` renders on top of the browser+map in the same tab; "Review fleet" runs there; the Dashboard tab is the supporting full read. Gap: `assessment.file_assessment_callable` takes `findings`, `priorities`, `normal_context` as strings, and `compose` projects suggestions to `{id, text, evidence}` with free-text evidence. No referent binds a finding to a worker, company or map node. |
| 6 | Improvements/Rules secondary | **delivered** | `st.tabs(["System Map", "Dashboard", "Improvements", "Rules", "Fleet & run details"])` — the map is the default; Improvements and Rules are separate later tabs. |

**One distinction worth keeping.** Two capabilities are implemented and self-tested but **not exercised by current live data**: no `intake.json` sidecar exists anywhere under `data/`, and no worker in `fleet/workers/` declares a `destination`. Both paths have self-test coverage (`incoming.py`, `system_map.py`, `define.py`). That is not a delivery gap — it is seed data that does not use them — but a reader comparing the map to the code should know why neither appears on screen today.

**What remains open.** The four residual gaps are now carried in `PRODUCT.md` § "Current product priorities" as the next product work. This register entry no longer tracks them; product authority does.

---

## D4 — the first component diagram's edges did not exist in the code

**Status:** resolved on this branch.
**Disposition:** `fix documentation`, plus ADR-0002 — accepted by Roundtable in issue #3 — so the class of error stays detectable.

**Established by:** measuring imports across the twelve live packages, accounting for the repository's `sys.path` bare-module import style, and comparing the result with the fifteen edges drawn in the original `02-live-component-map.puml`. Of those fifteen:

```text
 2  match a real dependency in the direction drawn
    modeller -> taskmodel, supervisor -> fleet

 8  are drawn opposite to the real dependency
    inspector -> modeller, taskmodel -> {reservation, enrichment,
    aggregation, reconciliation}, reservation -> worker,
    worker -> fleet, fleet -> supervisor

 5  exist in neither direction
    adapters -> inspector, calendar_job -> worker,
    enrichment -> worker, aggregation -> worker,
    reconciliation -> worker
```

and 13 of the 22 real edges appear nowhere in it, including `modeller -> {the four task families}`, `worker -> modeller`, `worker -> taskmodel`, `fleet -> modeller`, `fleet -> adapters` and `supervisor -> modeller`.

Two concrete cases: `calendar_job/unattended.py` imports `execute_reservation`, `reservation_model` and `task_model` — not `worker`. And `worker/runtime.py` imports only the reservation family, not all four; the drawn `enrichment | aggregation | reconciliation -> worker` edges have no counterpart in either direction.

**Why it happened, and why it is not simply a mistake:** the diagram was rendering *intended data flow* — which is a legitimate and useful view, and mostly correct as one — in a component diagram's notation, where an arrow reads as a dependency. The two claims were mixed in one file.

**Resolution:** split into two views that each state their kind.

- `02-live-responsibility-map.puml` — INTENDED. Responsibility and data flow as `PRODUCT.md` and `README.md` describe it. Says in its header that its arrows are not import edges.
- `05-package-dependencies.puml` — MEASURED. Every edge extracted from the source, and re-derivable by `scripts/check_architecture_grounding.py`.

ADR-0002 makes it a standing convention that architecture views declare which kind they are and that the measured one is script-checked. The split and the check landed here as the evidence for that proposal; Roundtable accepted it in issue #3.

---

## D5 — `README.md` presented the handoff as a current-state document

**Status:** resolved on this branch.
**Disposition:** `fix documentation`.

**Established by:** `README.md` § "Where to read next" listed `.handoff.md` as "detailed current implementation handoff", with nothing distinguishing its authority from `PRODUCT.md` listed immediately above it. At the time it was written, the handoff was two packs stale (D1).

**Resolution:** the entry now says what a handoff is worth. Correcting D1 without this would have left the entry point still inviting a reader to treat a transient note as current truth.

---

## D6 — workbook ingestion does not enter through the modeller

**Status:** closed.
**Disposition:** `confirm as-is`.

**Established by:** measured imports. `modeller/` does not import `adapters/`. The xlsx adapter is reached from `supervisor/define.py` and `fleet/inbox.py`; `modeller/pipeline.py` imports `observe` from `inspector/`, not the adapter.

**Why this is not a defect:** neither `README.md` nor `PRODUCT.md` claims the modeller reads workbooks directly. `supervisor/define.py` is described in `supervisor/app.py` as "a thin glue layer over `modeller/pipeline.py` + `modeller/builder.py` -- not a second modeller", which is consistent with the adapter being called by the glue rather than by the modeller. Recorded so the shape is not re-raised as drift, and noted on the measured view.
