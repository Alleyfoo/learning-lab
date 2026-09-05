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

## D3 — `PRODUCT.md` lists product priorities that appear already delivered

**Status:** open. Requires Roundtable.
**Disposition:** `create roadmap item` — raised as [I-1](initiatives.md#i-1).

**Established by:** `PRODUCT.md` § "Current product priorities" lists six items as "the next meaningful product work", including #1 company as top-level object, #2 incoming-data browser, #3 restore the system map as a primary surface, #4 embed the modeller, #5 put the supervisor beside the map. `supervisor/app.py` describes all of those as implemented: the System Map is the primary tab, an incoming file/workbook/sheet browser sits to its left, the assessment sits on top, and v0.3 "closes the gap between the two halves (PRODUCT.md priority #4)" with a Define-work panel and an explicit human-gated Establish. `fleet/system_map.py` and `supervisor/app.py` both handle pre-worker company identity from `intake.json` sidecars.

`PRODUCT.md` was last changed 2026-08-17; the v0.2–v0.6 work landed 2026-08-18.

**Why it is not fixed here:** `PRODUCT.md` is rank-2 authority (engineering system §7) and only Roundtable may change it. A Coder correcting the priority list would be exactly the `Implemented -> Roundtable closed` transition the process forbids. What the delivered work *means* for the roadmap is a closure decision, not a documentation edit.

**What Roundtable has to decide:** which of priorities #1–#6 are closed by v0.2–v0.6, what remains open in each, and what the next priority actually is.

---

## D4 — the first component diagram's edges did not exist in the code

**Status:** resolved on this branch.
**Disposition:** `fix documentation`, plus ADR-0002 so the class of error is detectable.

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

ADR-0002 records the decision that architecture views declare which kind they are and that the measured one is script-checked.

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
