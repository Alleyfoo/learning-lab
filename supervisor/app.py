#!/usr/bin/env python3
"""Workspace v0.3 -- the Supervisor Streamlit surface, recentred on the System Map,
with the modeller integrated as a "Define work" flow.

The organizing concept is the **company's actual flow**: Company -> Incoming Data ->
Understanding -> Modelled Work -> Output. The Fleet System Map is the **primary
visual model**: it renders the *modelled-work* half of that flow (company/scope ->
declared inputs/sources -> modelled workers -> outputs, with exception/investigator
side paths) and begins after modelling. The raw "Incoming Data" the map does not yet
draw is supplied by the **incoming-file/workbook/sheet browser** to its left -- the
`data/` library (including data not yet modelled into a worker) and each worker's
inbox/processed/exceptions. The supervisor's **current assessment sits on top** of this
company context, so its verdict is visibly attached to the flows it describes.

v0.3 closes the gap between the two halves (PRODUCT.md priority #4): a `data/` dir in
the incoming browser that has **no worker and no model** carries a **"Define work"**
button. Clicking it opens a full-width panel that drives the EXISTING modeller floor
(via `supervisor/define.py`, a thin glue layer over `modeller/pipeline.py` +
`modeller/builder.py` -- not a second modeller) one stage at a time, with the operator
in the loop: inspect the selected data -> describe the job -> observe (program) /
interpret (LLM) / propose a task model (LLM) -> answer a load-bearing question only if
asked -> deterministic preview -> **explicitly Establish worker** -> return to the map
and see the new worker on it. Evidence boundaries (OBSERVED/INFERRED/CONFIRMED) and
the sufficiency gates are the modeller's, unchanged. Establishment is an EXPLICIT human
action: the LLM proposes the model; only the operator clicks "Establish worker"
(PRODUCT.md authority model -- the LLM may suggest freely; it cannot silently take
production authority).

  System Map (primary)   incoming browser (left) + the Fleet System Map (centre) +
                         the supervisor's current assessment (on top). The Review-fleet
                         action lives here and feeds the assessment. Live fleet only.
                         "Define work" opens here when an unmodelled incoming-data dir
                         is selected, and Establish returns here with the new worker
                         on the map.
  Dashboard              the full current assessment (supporting read).
  Improvements           the persistent append-only backlog (raise/route/activate).
  Rules                  rulebook.jsonl + pending activations.
  Fleet & run details    the raw snapshot + full counters + the last run's per-turn
                         evidence. Technical.

Everything reads the **live fleet** (`fleet/workers` + `data/`). The S1 fixture selector
is gone -- the map, the review, and the browser must describe one coherent fleet, and
the recentering is around the company's actual flows, not a lab condition. The surface
is read-only EXCEPT for the one explicit, human-gated write path: "Establish worker"
in the Define-work panel, which calls `fleet.establish` to write a new worker into
`fleet/workers/`. The LLM never writes; it only proposes.

  run-supervisor.bat   (or: python -m streamlit run supervisor/app.py)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
# HERE last so it wins as sys.path[0] (no collisions with fleet/s1 -- verified).
sys.path.insert(0, str(LAB / "s1"))
sys.path.insert(0, str(LAB / "fleet"))
sys.path.insert(0, str(HERE))

import fleet          # noqa: E402  (load_all -- the live fleet)
import system_map     # noqa: E402  (build, legend, status_legend, name_from)
import map_component  # noqa: E402  (the vis-network Streamlit component)
import incoming       # noqa: E402  (the read-only incoming-data browser)
import define         # noqa: E402  (v0.3: glue to the modeller floor + establishment)
import assessment     # noqa: E402
import backlog        # noqa: E402
import rulebook       # noqa: E402
import routing        # noqa: E402
import supervision    # noqa: E402
import snapshot as snap  # noqa: E402

st.set_page_config(page_title="Supervisor", layout="wide")

DATA_ROOT = LAB / "data"


# A single RoutingDesk holds only model config (no per-route state), so one
# shared instance is fine. Built lazily and cached in session_state.
def _desk() -> "routing.RoutingDesk":
    if "desk" not in st.session_state:
        st.session_state["desk"] = routing.RoutingDesk()
    return st.session_state["desk"]


def _incoming() -> dict:
    """The incoming-data scan, cached for the session (read-only; refreshed on Review)."""
    if "incoming" not in st.session_state:
        st.session_state["incoming"] = incoming.scan(fleet.load_all(), DATA_ROOT)
    return st.session_state["incoming"]


# ===========================================================================
# Renderers (defined before the tab blocks that call them)
# ===========================================================================

def _badge(label: str, color: str) -> str:
    """A small coloured HTML badge for the incoming browser."""
    return (f"<span style='background:{color};color:#fff;border-radius:3px;"
            f"padding:1px 5px;font-size:0.78em'>{label}</span>")


def _render_assessment_banner(am: dict | None) -> None:
    """The compact current assessment, on top of the company context."""
    if am is None:
        st.info("No assessment yet. Press **Review fleet** to generate one.")
        return
    filed = am.get("filed")
    if filed is None:
        st.warning("The supervisor did not file a structured assessment for this run. "
                   "See the Dashboard tab for the narrative.")
    else:
        nc = filed.get("normal_context") or "_(not stated)_"
        st.markdown(f"**Normal / no-action context.** {nc}")
        findings = filed.get("findings", [])
        priorities = filed.get("priorities", [])
        if findings:
            shown = findings[:3]
            more = f" …+{len(findings) - 3}" if len(findings) > 3 else ""
            st.caption("**Findings.** " + " · ".join(shown) + more)
        if priorities:
            shown = priorities[:3]
            more = f" …+{len(priorities) - 3}" if len(priorities) > 3 else ""
            st.caption("**Priorities.** " + " · ".join(shown) + more)
    suggestions = am.get("suggestions", [])
    if suggestions:
        st.caption(f"**{len(suggestions)} suggestion(s)** raised this run — see the "
                   "**Dashboard** tab. Route/activate on **Improvements**.")
    else:
        st.caption("No suggestions raised this run.")
    st.caption(f"run `{am.get('run_id')}` · {am.get('fleet_shape')} · "
               f"stop={am.get('stop_reason')} · turns={am.get('turn_count')} · "
               f"{am.get('elapsed_seconds')}s · model `{am.get('model')}`")


def _render_full_assessment(am: dict | None) -> None:
    """The full current assessment (Dashboard tab). Mirrors v0.1's Dashboard body."""
    if am is None:
        st.info("No assessment yet. Press **Review fleet** on the System Map tab to "
                "generate one.")
        return
    filed = am.get("filed")
    if filed is None:
        st.warning("The supervisor did not file a structured assessment for this run. "
                   "See the narrative below.")
    else:
        st.markdown("#### Normal / no-action context")
        st.markdown(filed.get("normal_context") or "_(not stated)_")

        st.markdown("#### Findings")
        findings = filed.get("findings", [])
        for f in findings:
            st.markdown(f"- {f}")
        if not findings:
            st.caption("none")

        st.markdown("#### Priorities")
        priorities = filed.get("priorities", [])
        for i, p in enumerate(priorities, 1):
            st.markdown(f"{i}. {p}")
        if not priorities:
            st.caption("none")

    st.markdown("#### Suggestions")
    suggestions = am.get("suggestions", [])
    if suggestions:
        for s in suggestions:
            st.markdown(f"- `{s['id']}` — {s.get('text', '')}"
                        + (f" _(evidence: {s.get('evidence')})_"
                           if s.get("evidence") else ""))
        st.caption("Route and activate these on the **Improvements** tab.")
    else:
        st.caption("none raised this run.")

    with st.expander("Narrative (supervisor's final response)", expanded=False):
        st.markdown(am.get("final_response") or "_(no final response)_")

    st.caption(f"run `{am.get('run_id')}` · {am.get('fleet_shape')} · "
               f"stop={am.get('stop_reason')} · turns={am.get('turn_count')} · "
               f"{am.get('elapsed_seconds')}s · model `{am.get('model')}`")


def _render_incoming_browser(scan_result: dict) -> None:
    """The left-side incoming-data browser: data/ library + worker inboxes."""
    st.markdown("##### Incoming data")
    st.caption("The company's incoming data. `data/` dirs with no worker link may be "
               "not-yet-modelled — `model exists` marks a dir with an "
               "`established_model.json` that has not been deployed as a worker.")

    st.markdown("**Data library** (`data/`)")
    lib = scan_result.get("data_library", [])
    if not lib:
        st.caption("no `data/` directories.")
    for entry in lib:
        worker = entry.get("worker")
        bits = []
        status_parts = []
        if worker:
            bits.append(_badge(f"worker:{worker}", "#2a6f2a"))
            status_parts.append(f"worker:{worker}")
        else:
            bits.append(_badge("no worker link", "#8a6d3b"))
            status_parts.append("no worker link")
        if entry.get("has_model"):
            bits.append(_badge("model exists", "#3a6a9a"))
            status_parts.append("model exists")
        if entry.get("has_adapter"):
            bits.append(_badge("adapter", "#6a6a6a"))
            status_parts.append("adapter")
        # Streamlit's expander label does not render HTML, so the label is
        # plain text; the coloured badges live inside the expanded body.
        label = (f"{entry['dir']}/ · {' · '.join(status_parts)} · "
                 f"{len(entry['files'])} file(s)")
        with st.expander(label, expanded=False):
            st.markdown(" ".join(bits), unsafe_allow_html=True)
            for f in entry["files"]:
                line = f"- {f['name']} ({f['kind']})"
                if f["sheets"]:
                    line += " &nbsp; sheets: " + ", ".join(f["sheets"])
                st.markdown(line)
            # v0.3: a genuinely unmodelled dir (no worker link, no established
            # model) is a candidate to define work on. v0.4: an xlsx-only dir is
            # also a candidate -- the Define-work panel discovers its sheets and
            # materializes the operator-declared ones into _derived/ before the
            # unchanged v0.3 modeller journey.
            has_json = any(f["kind"] == "json" for f in entry["files"])
            has_xlsx = any(f["kind"] == "xlsx" for f in entry["files"])
            if worker is None and not entry.get("has_model") and (has_json or has_xlsx):
                if st.button("Define work", key=f"define_{entry['dir']}"):
                    st.session_state["define:dir"] = entry["dir"]
                    st.rerun()

    st.markdown("**Worker inboxes**")
    inboxes = scan_result.get("inboxes", [])
    if not inboxes:
        st.caption("no inbox files in any worker.")
    for ib in inboxes:
        customer = ib.get("customer") or "—"
        label = f"{ib['worker']} · {customer} · {len(ib['files'])} file(s)"
        with st.expander(label, expanded=False):
            by_stage = {"inbox": [], "processed": [], "exceptions": []}
            for f in ib["files"]:
                by_stage.setdefault(f["stage"], []).append(f)
            for stage in ("inbox", "processed", "exceptions"):
                if not by_stage.get(stage):
                    continue
                st.markdown(f"*{stage}*")
                for f in by_stage[stage]:
                    line = f"- {f['name']}"
                    if f["sheets"]:
                        line += " &nbsp; sheets: " + ", ".join(f["sheets"])
                    st.markdown(line)


def _render_system_map(workers: list, snap_by_name: dict, worker_by_name: dict) -> None:
    """The Fleet System Map + legend + click-to-select worker detail."""
    graph = system_map.build(workers)
    clicked = map_component.system_map(graph["nodes"], graph["edges"],
                                        height=720, key="supervisor_map")
    st.markdown(" · ".join(
        f"<span style='color:{colour}'>&#9632;</span> {label}"
        for label, colour in system_map.legend()), unsafe_allow_html=True)
    st.markdown("**status** &nbsp; " + " · ".join(
        f"<span style='color:{colour}'><b>{glyph}</b> {label}</span>"
        for glyph, label, colour in system_map.status_legend()), unsafe_allow_html=True)
    scopes = [s for s, _ in system_map.lanes(workers) if s]
    st.caption(f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
               f"{len(scopes)} scope(s): {', '.join(scopes) if scopes else 'none'}. "
               f"Lanes are derived from each worker's declared `customer`; engines and "
               f"the investigator are shared, so they sit outside every lane.")

    # click a node -> typed selection. The map only reports the clicked id;
    # Python interprets it. map_pick (bare worker name) is kept for the worker
    # panel below; map_selection carries the typed selection for other kinds.
    sel = system_map.parse_selection((clicked or {}).get("id"))
    if sel:
        st.session_state["map_selection"] = sel
        if sel["kind"] == "worker":
            st.session_state["map_pick"] = sel["worker"]
        else:
            st.session_state.pop("map_pick", None)
        st.rerun()

    pick = st.session_state.get("map_pick")
    if pick:
        rec = snap_by_name.get(pick)
        w = worker_by_name.get(pick)
        with st.expander(f"Worker: {pick}", expanded=True):
            if rec is None:
                st.caption("No snapshot record for this worker.")
            else:
                st.markdown(f"**Purpose.** {rec.get('purpose') or '_(none)_'}")
                s = rec.get("summary") or {}
                st.markdown(
                    f"**Task.** `{rec.get('task')}` · engine `{rec.get('engine')}` · "
                    f"customer `{rec.get('customer')}`")
                st.markdown(
                    f"**Version.** v{rec.get('current_version')} of "
                    f"{rec.get('version_count')} · "
                    f"{s.get('runs_total', 0)} run(s) total "
                    f"({s.get('runs_this_version', 0)} this version) · "
                    f"last status `{s.get('last_status')}`")
                inv = rec.get("investigation")
                if inv and inv.get("state") == "open":
                    st.warning(f"Open investigation since {inv.get('opened', '?')}: "
                               f"{inv.get('question', '')}")
                if w is not None:
                    st.caption(f"trigger: `{rec.get('trigger')}`  ·  "
                               f"directory: `{w.directory}`")
                if st.button("Clear selection", key="clear_map_pick"):
                    st.session_state.pop("map_pick", None)
                    st.session_state.pop("map_selection", None)
                    st.rerun()

    # a non-worker selection renders a type-appropriate operating/detail panel
    cur = st.session_state.get("map_selection")
    if cur and cur["kind"] != "worker":
        _render_typed_panel(cur, workers, worker_by_name, snap_by_name)


def _clear_map_selection() -> None:
    st.session_state.pop("map_pick", None)
    st.session_state.pop("map_selection", None)


def _render_typed_panel(sel: dict, workers: list, worker_by_name: dict,
                        snap_by_name: dict) -> None:
    """Dispatch a non-worker map selection to its operating/detail panel."""
    kind = sel["kind"]
    if kind == "inbox":
        _render_inbox_panel(sel, worker_by_name)
    elif kind == "company":
        _render_company_panel(sel, workers)
    elif kind == "source":
        _render_source_panel(sel, worker_by_name)
    elif kind == "destination":
        _render_destination_panel(sel, workers)
    else:
        st.caption(f"(selection kind `{kind}` not yet implemented)")


# ---------------------------------------------------------------------------
# v0.5 operating/detail panels for non-worker map selections.
# Filled in across Phase 2 (inbox), Phase 3 (company), Phase 4 (destination),
# Phase 5 (source). Each renders inside the System Map tab, below the graph.
# ---------------------------------------------------------------------------

def _render_inbox_panel(sel: dict, worker_by_name: dict) -> None:
    st.caption(f"(inbox panel for `{sel.get('worker')}` -- Phase 2)")


def _render_company_panel(sel: dict, workers: list) -> None:
    st.caption(f"(company panel for `{sel.get('company')}` -- Phase 3)")


def _render_source_panel(sel: dict, worker_by_name: dict) -> None:
    """Read-only provenance panel for a source node (v0.5 item 9).

    Displays the v0.4 durable origin already carried in v1.json: the executable
    source path (what the worker runs against) plus the workbook/sheet/header_row
    origin (where that executable representation came from). Display only.
    """
    wname, coll = sel.get("worker"), sel.get("source")
    w = worker_by_name.get(wname)
    with st.expander(f"Source: {coll}", expanded=True):
        if w is None or coll not in (w.model.get("sources") or {}):
            st.caption(f"No source `{coll}` on worker `{wname}`.")
            if st.button("Clear selection", key="clear_source_pick"):
                _clear_map_selection()
                st.rerun()
            return
        spec = w.model["sources"][coll]
        st.markdown(f"**Collection.** `{coll}`")
        st.markdown(f"**Executable source.** `{spec.get('path')}`  "
                    f"(resolved under base `{w.identity.get('base')}`)")
        origin = spec.get("origin")
        if origin:
            st.markdown("**Origin.**")
            st.markdown(f"- workbook: `{origin.get('path')}`")
            st.markdown(f"- sheet: `{origin.get('sheet')}`")
            st.markdown(f"- header row: `{origin.get('header_row')}`")
            st.markdown(f"- kind: `{origin.get('kind')}`")
        else:
            st.caption("Direct JSON source — no workbook provenance.")
        st.markdown(f"**Used by.** `{wname}` · v{w.current_version} · task `{w.task}`")
        if st.button("Clear selection", key="clear_source_pick"):
            _clear_map_selection()
            st.rerun()


def _render_destination_panel(sel: dict, workers: list) -> None:
    """Detail panel for a declared destination node (the v0.5 D canary).

    Distinguishes DESIRED DELIVERY (declared intent) from AUTOMATED EFFECT
    AUTHORITY (grounded in executable machinery). A worker may declare
    `automatic` without any connector existing; the panel must never represent
    that as real authority. Destination nodes only exist for noncommitting
    workers in v0.5, so authority here is always 'none'.
    """
    key = sel.get("key")
    feeds = [w for w in workers
             if w.destination and system_map.destination_key(w.destination) == key]
    with st.expander("Destination", expanded=True):
        if not feeds:
            st.caption("No established worker declares this destination.")
            if st.button("Clear selection", key="clear_dest_pick"):
                _clear_map_selection()
                st.rerun()
            return
        dest = feeds[0].destination
        parts = [dest.get("system"), dest.get("area"), dest.get("object")]
        st.markdown(" / ".join(p for p in parts if p))
        st.markdown("**Receives from:**")
        for w in feeds:
            st.markdown(f"- `{w.name}` · task `{w.task}`")
        mode = (feeds[0].delivery or {}).get("mode", "unspecified")
        st.markdown(f"**Desired delivery:** `{mode}`")
        # Authority is sourced from the workers' real committing/effect facts,
        # never from delivery.mode. Destination nodes are noncommitting in v0.5.
        any_authority = any(w.committing for w in feeds)
        if any_authority:
            st.markdown("**Automated effect authority:** a feeding worker commits "
                        "a real effect (see its worker node).")
        else:
            st.markdown("**Automated effect authority:** none — these workers "
                        "commit no effect. The desired delivery is intent, not a "
                        "connector; no integration is implied.")
        st.caption("A destination may be known long before a connector exists. "
                   "Declaring `automatic` does not mint write authority.")
        if st.button("Clear selection", key="clear_dest_pick"):
            _clear_map_selection()
            st.rerun()


# ===========================================================================
# Define work (v0.3) -- drive the existing modeller floor + establish a worker
# ===========================================================================

_DEFINE_KEYS = ("define:dir", "define:goal", "define:task", "define:report",
                "define:ingest", "define:model", "define:asked", "define:deferred",
                "define:choice", "define:name", "define:customer",
                "define:derived_rel", "define:origins",
                # v0.5: declared destination / delivery (operator-entered at Establish)
                "define:dest_system", "define:dest_area", "define:dest_object",
                "define:delivery")


def _clear_define() -> None:
    """Drop every Define-work session_state key (cancel / new selection / after establish)."""
    for k in _DEFINE_KEYS:
        st.session_state.pop(k, None)
    # discover-stage widget values live under their own per-sheet keys and are
    # cleared on a fresh selection; validated results are transient.
    for k in list(st.session_state):
        if k.startswith("define:sel:") or k.startswith("define:coll:") \
                or k.startswith("define:hdr:") or k.startswith("define:inspect:") \
                or k == "define:validated":
            st.session_state.pop(k, None)


def _render_discover_stage(dir_name: str) -> None:
    """v0.4 discover -> declare -> validate -> materialize.

    The program discovers workbook structure (sheet names, row x col counts, a
    preview of the first rows) with NO LLM. The OPERATOR declares which sheets
    have business meaning, as which collection, and which row is the header -- the
    program never decides that. The existing XLSX adapter validates each
    declaration and REFUSES (before any model call) any sheet it cannot faithfully
    convert (uncalculated formula, blank/duplicate header, empty/missing sheet).
    Valid selections materialize into `data/_derived/<dir_name>/` (raw workbooks
    untouched), the origin map + derived rel are stashed in session_state, and the
    panel reruns and falls through to the unchanged v0.3 modeller journey.
    """
    st.markdown("#### Declare workbook sheets")
    st.caption("The program discovers sheets and their shape; you declare which "
               "have business meaning, as which collection, and which row is the "
               "header. A sheet the adapter cannot faithfully read is refused here "
               "-- before any model call.")
    scan_entry = next((e for e in _incoming().get("data_library", [])
                       if e["dir"] == dir_name), None)
    if scan_entry is None:
        st.warning(f"`{dir_name}/` is not in the incoming scan.")
        return
    xlsx_files = [f for f in scan_entry["files"] if f["kind"] == "xlsx"]
    if not xlsx_files:
        st.warning(f"`{dir_name}/` has no xlsx workbooks to declare.")
        return

    for f in xlsx_files:
        wb_name = f["name"]
        with st.expander(f"`{wb_name}` — sheets: {', '.join(f['sheets']) or 'none'}",
                         expanded=False):
            inspect_key = f"define:inspect:{wb_name}"
            if st.button("Inspect", key=f"define_inspect_{wb_name}"):
                st.session_state[inspect_key] = True
                st.rerun()
            if not st.session_state.get(inspect_key):
                st.caption("Click Inspect to see each sheet's shape and first rows.")
                continue
            xlsx_path = DATA_ROOT / dir_name / wb_name
            try:
                sheets = define.discover_workbook(xlsx_path)
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read {wb_name}: {type(e).__name__}: {e}")
                continue
            for s in sheets:
                st.markdown(f"**{s['name']}** — {s['rows']} row(s) × "
                            f"{s['cols']} col(s)")
                if s["preview"]:
                    st.dataframe(s["preview"], use_container_width=True,
                                 hide_index=False)
                else:
                    st.caption("(empty sheet)")
                col_a, col_b, col_c = st.columns([1, 2, 1])
                ck = f"define:sel:{wb_name}:{s['name']}"
                with col_a:
                    declare = st.checkbox(
                        "declare", key=ck, value=st.session_state.get(ck, False),
                        help="Materialize this sheet as a collection")
                with col_b:
                    coll_key = f"define:coll:{wb_name}:{s['name']}"
                    if coll_key not in st.session_state:
                        st.session_state[coll_key] = s["name"]
                    st.text_input("collection name", key=coll_key,
                                  disabled=not declare)
                with col_c:
                    hdr_key = f"define:hdr:{wb_name}:{s['name']}"
                    if hdr_key not in st.session_state:
                        st.session_state[hdr_key] = 1
                    st.number_input("header row", min_value=1, step=1,
                                    key=hdr_key, disabled=not declare)

    # gather declarations across all inspected workbooks/sheets
    declared: list[tuple] = []   # (wb_name, sheet, collection, header_row)
    for f in xlsx_files:
        wb_name = f["name"]
        if not st.session_state.get(f"define:inspect:{wb_name}"):
            continue
        for s_name in f["sheets"]:
            if st.session_state.get(f"define:sel:{wb_name}:{s_name}"):
                coll = (st.session_state.get(f"define:coll:{wb_name}:{s_name}")
                        or s_name).strip()
                hdr = int(st.session_state.get(f"define:hdr:{wb_name}:{s_name}")
                          or 1)
                if coll:
                    declared.append((wb_name, s_name, coll, hdr))

    if not declared:
        st.caption("No sheets declared yet. Inspect a workbook and tick 'declare' "
                   "on the sheets that have business meaning.")
        return

    st.markdown("---")
    if st.button("Validate selections", type="primary", key="define_validate"):
        results = []
        for wb_name, sheet, coll, hdr in declared:
            ok, problems, headers, rows = define.validate_selection(
                DATA_ROOT / dir_name / wb_name, sheet, hdr)
            results.append((wb_name, sheet, coll, hdr, ok, problems, headers, rows))
        st.session_state["define:validated"] = results
        st.rerun()

    results = st.session_state.get("define:validated") or []
    if not results:
        st.caption("Validate the selections before materializing.")
        return

    st.markdown("#### Validation")
    valid: list[tuple] = []   # (wb_name, sheet, collection, header_row)
    for wb_name, sheet, coll, hdr, ok, problems, headers, rows in results:
        if ok:
            st.success(f"`{wb_name}` · `{sheet}` → **{coll}** (header row {hdr}) — "
                       f"{rows} row(s); columns: {', '.join(headers) or '—'}")
            valid.append((wb_name, sheet, coll, hdr))
        else:
            st.error(f"`{wb_name}` · `{sheet}` → **{coll}** (header row {hdr}) — "
                     f"REFUSED: {'; '.join(problems)}")
            st.caption("This sheet is dropped from the materialize set; the others "
                       "still proceed.")

    if not valid:
        st.warning("No valid selections to materialize. Adjust the declarations "
                   "(e.g. the header row) and re-validate.")
        return

    st.markdown("#### Materialize")
    st.caption(f"The selected sheets materialize into `data/_derived/{dir_name}/` "
               f"as JSON collections; the raw workbooks stay untouched. The "
               f"unchanged modeller journey then runs over the derived collections.")
    if st.button("Materialize valid selections", type="primary",
                 key="define_materialize"):
        by_wb: dict[str, list] = {}
        for wb_name, sheet, coll, hdr in valid:
            by_wb.setdefault(wb_name, []).append((sheet, coll, hdr))
        all_written: list = []
        all_origins: dict = {}
        try:
            for wb_name, specs_raw in by_wb.items():
                specs = [define.SheetSpec(s, c, h) for s, c, h in specs_raw]
                written, origins = define.materialize_selections(
                    DATA_ROOT / dir_name / wb_name, specs, dir_name)
                all_written.extend(written)
                all_origins.update(origins)
        except Exception as e:  # noqa: BLE001
            st.error(f"Materialize failed: {type(e).__name__}: {e}")
            return
        st.session_state["define:derived_rel"] = f"_derived/{dir_name}"
        st.session_state["define:origins"] = all_origins
        st.session_state.pop("define:validated", None)
        st.session_state.pop("incoming", None)   # the raw dir's link will refresh
        st.success(f"Materialized {len(all_written)} collection(s) into "
                   f"`data/_derived/{dir_name}/`. Continuing to the modeller.")
        st.rerun()


def _render_define_panel(dir_name: str) -> None:
    """The full-width Define-work panel. Mirrors modeller/app.py's stages, driven
    via supervisor/define.py glue. Returns having rendered the panel; the caller
    gates the normal System Map view off while this is active.

    Establishment is the one write path in the supervisor: it is explicit
    ("Establish worker" button) and only the operator can click it. The LLM only
    proposes; it never writes.
    """
    st.subheader(f"Define work  —  `{dir_name}/`")
    st.caption("Drive the existing modeller over this incoming data, then explicitly "
               "establish a worker. The LLM proposes the model; only you establish it. "
               "Cancel to return to the map.")
    c_cancel, _ = st.columns([1, 6])
    if c_cancel.button("Cancel", key="define_cancel"):
        _clear_define()
        st.rerun()
    st.markdown("---")

    # v0.4: a materialized dir resolves to the DERIVED workspace; an un-
    # materialized dir resolves to the raw incoming dir. An xlsx-only dir (no
    # JSON, or fewer than 2 collections) routes through the discover stage first
    # -- discover -> declare -> validate (REFUSE before any LLM) -> materialize
    # into _derived/ -> rerun -> fall through to the unchanged v0.3 journey below.
    if st.session_state.get("define:derived_rel"):
        ws = define.workspace_from_rel(st.session_state["define:derived_rel"])
    else:
        ws = define.workspace_for(dir_name)

    chosen = define.chosen_sources(ws) if ws is not None else []
    if not st.session_state.get("define:derived_rel") and len(chosen) < 2:
        scan_entry = next((e for e in _incoming().get("data_library", [])
                           if e["dir"] == dir_name), None)
        has_xlsx = bool(scan_entry and any(f["kind"] == "xlsx"
                                           for f in scan_entry["files"]))
        if has_xlsx:
            _render_discover_stage(dir_name)
        else:
            st.warning("The modeller needs at least two JSON collections to relate; "
                       "this directory has fewer, and no xlsx to declare.")
        return
    if len(chosen) < 2:
        st.warning("The modeller needs at least two JSON collections to relate; "
                   "the materialized workspace has fewer. Cancel and declare more "
                   "sheets, or add JSON collections to the incoming dir.")
        return

    obs = define.observed(ws, chosen)

    # --- 0 · selected data ------------------------------------------------
    with st.expander(f"Selected data — {len(chosen)} collection(s)", expanded=True):
        for s in chosen:
            st.markdown(f"- `{s.filename}` → **{s.collection}**  "
                        f"&nbsp; <span style='color:#888'>{s.rows} row(s)</span>",
                        unsafe_allow_html=True)
        rels = define.relationships(obs)
        if rels:
            st.caption("Candidate relationships (measured):")
            for r in rels:
                st.markdown(f"- `{r['left']}` ↔ `{r['right']}`  "
                            f"&nbsp; <span style='color:#888'>left coverage "
                            f"{r.get('left_coverage')} · right unique "
                            f"{r.get('right_unique')}</span>", unsafe_allow_html=True)

    # --- 1 · describe the job ----------------------------------------------
    goal = st.text_area(
        "In your own words", key="define:goal", value="", height=80,
        placeholder="e.g. Reconcile the purchase ledger against the supplier statement "
                    "by Invoice, comparing Amount.")
    tasks = define.expressible_tasks(chosen)
    task = st.selectbox("Task family (structure can't pick; you do)",
                        tasks, key="define:task")
    run = st.button("Work out the task", type="primary", key="define_run",
                    disabled=not goal.strip())

    if run:
        with st.spinner("Inspecting (this calls the local model)…"):
            try:
                report, ingest = define.interpret(obs, goal)
            except Exception as e:  # noqa: BLE001
                st.session_state["last_error"] = f"{type(e).__name__}: {e}"
                st.rerun()
        with st.spinner("Defining the task (this calls the local model)…"):
            try:
                model, asked, deferred = define.propose(
                    report, goal, define.source_spec(ws, chosen), obs, task)
            except Exception as e:  # noqa: BLE001
                st.session_state["last_error"] = f"{type(e).__name__}: {e}"
                st.rerun()
        st.session_state["define:report"] = report
        st.session_state["define:ingest"] = ingest
        st.session_state["define:model"] = model
        st.session_state["define:asked"] = asked
        st.session_state["define:deferred"] = deferred
        st.session_state["last_error"] = None
        st.rerun()

    if st.session_state.get("last_error"):
        st.error(f"Work out the task failed: {st.session_state['last_error']}")
        st.caption("Is the local model running? `ollama serve` / check "
                   "`http://localhost:11434`.")

    report = st.session_state.get("define:report")
    if report is None:
        return

    # --- 2 · understanding + proposed task ---------------------------------
    st.markdown("#### Understanding")
    left, right = st.columns(2)
    with left:
        st.markdown("**Inferred** — the inspector's interpretation, with its basis")
        inferred = [c for c in report if c["status"] == "INFERRED"]
        for c in inferred:
            b = c["claim"]
            where = f"{b.get('source')}" + (f".{b['field']}" if b.get("field") else "")
            st.write(f"`{where}` — {b.get('meaning')}")
            st.caption("basis: " + ", ".join(c.get("basis") or []))
        if not inferred:
            st.caption("None.")
    with right:
        st.markdown("**Unknown** — uncertainties, each addressed to its subject")
        unknowns = [c for c in report if c["status"] == "UNKNOWN"]
        for c in unknowns:
            b = c["claim"]
            where = f"{b.get('source')}" + (f".{b['field']}" if b.get("field") else "")
            st.write(f"`{where}` — {b.get('question')}")
        if not unknowns:
            st.caption("None outstanding.")
        st.markdown("**Confirmed**")
        settled = [c for c in report if c["status"] == "CONFIRMED"]
        for c in settled:
            st.write(f"{c['claim'].get('meaning')} — was {c.get('was')}, "
                     f"by {c.get('confirmed_by')}")
        if not settled:
            st.caption("Nothing has needed a human answer.")

    ingest = st.session_state.get("define:ingest") or {}
    dropped = ingest.get("rejected") or []
    stripped = ingest.get("stripped") or []
    if dropped or stripped:
        with st.expander(f"Boundary refused {len(dropped)} claim(s), "
                         f"stripped {len(stripped)}"):
            st.json({"rejected": dropped, "stripped": stripped})

    deferred = st.session_state.get("define:deferred") or []
    if deferred:
        with st.expander(f"{len(deferred)} question(s) recorded but not asked — "
                         f"the answer would not change the model"):
            for entry, why in deferred:
                st.write(f"`{entry.get('source')}.{entry.get('field')}` — "
                         f"{entry.get('question') or entry.get('binding')}")
                st.caption(why)

    asked = st.session_state.get("define:asked") or []
    model = st.session_state.get("define:model")

    # --- 3 · missing truth (only if a load-bearing question is pending) -----
    if asked:
        st.markdown("#### One thing I cannot establish")
        qs = define.questions(asked, obs)
        if not qs:
            st.warning("The definer blocked but produced no answerable question. "
                       "Rephrase the goal, or use the advanced JSON below.")
        else:
            q = qs[0]
            st.caption("Load-bearing: " + asked[0][1])
            st.warning(q.text)
            if len(qs) > 1:
                st.caption(f"{len(qs) - 1} further question(s) will be asked "
                           f"separately.")
            choice = (st.radio("Answer", q.options, key="define:choice")
                     if q.options else st.text_input("Answer", key="define:choice"))
            if st.button("That's the one", type="primary", key="define_answer"):
                answer = define.build_answer(q, choice)
                st.session_state["define:report"] = define.apply_answer(
                    st.session_state["define:report"], q, answer)
                with st.spinner("Resuming (this calls the local model)…"):
                    try:
                        model2, asked2, deferred2 = define.propose(
                            st.session_state["define:report"], goal,
                            define.source_spec(ws, chosen), obs, task, resumed=True)
                    except Exception as e:  # noqa: BLE001
                        st.session_state["last_error"] = f"{type(e).__name__}: {e}"
                        st.rerun()
                st.session_state["define:model"] = model2
                st.session_state["define:asked"] = asked2
                st.session_state["define:deferred"] = deferred2
                st.session_state.pop("define:choice", None)
                st.rerun()
        # While a question is pending, do not show preview/establish below.
        _render_advanced_model(ws, chosen, obs, task)
        return

    if model is None:
        st.error("The definer did not produce a model. Rephrase the goal, or paste a "
                "model in the advanced JSON below.")
        _render_advanced_model(ws, chosen, obs, task)
        return

    # --- proposed task -----------------------------------------------------
    st.markdown("#### Proposed task")
    for line in define.render_model(model, task):
        st.markdown(line)
    _render_advanced_model(ws, chosen, obs, task)

    # --- 4 · deterministic preview -----------------------------------------
    st.markdown("#### Deterministic preview")
    complaint = define.check_join(model, obs, report)
    if complaint:
        st.warning(f"Sufficiency check: {complaint}")
    p = define.preview(ws, model)
    if not p.ok:
        st.error("Preview failed — the model did not validate against the data:")
        for prob in p.problems:
            st.code(str(prob))
        st.caption("Edit the model in the advanced JSON above, or rephrase the goal "
                   "and run again.")
        return
    st.caption(f"{len(p.rows)} row(s) · {len(p.refused)} refused.")
    if p.rows:
        st.dataframe(p.rows, use_container_width=True, hide_index=True)
    if p.refused:
        with st.expander(f"Refused rows ({len(p.refused)})"):
            st.dataframe(p.refused, use_container_width=True, hide_index=True)
    if p.notes:
        st.caption("; ".join(p.notes))

    # --- 5 · establish (the explicit human write action) -------------------
    st.markdown("#### Establish worker")
    st.caption("This writes a new worker into `fleet/workers/` (worker.json + "
               "versions/v1.json + history.jsonl) and returns to the map. The LLM "
               "cannot do this; only you can.")
    name = st.text_input("Worker name", key="define:name", value=dir_name)
    customer = st.text_input("Scope / customer (optional — names the map lane; "
                             "leave blank for an unscoped lane)",
                             key="define:customer", value="")

    # v0.5: where does the result BELONG? A declared destination, not effect
    # authority -- the worker is not granted any write capability by stating
    # this. Optional; blank means the worker just produces a result table.
    with st.expander("Destination (optional — where the result belongs)", False):
        st.caption("Declares a business destination and a desired delivery mode. "
                   "This is INTENT, not authority: stating `automatic` does NOT "
                   "give the worker any write capability. Effect authority remains "
                   "grounded in executable machinery, separately.")
        dest_system = st.text_input("System (e.g. finance, catalog)",
                                    key="define:dest_system", value="")
        dest_area = st.text_input("Area (optional, e.g. reskontra)",
                                  key="define:dest_area", value="")
        dest_object = st.text_input("Object (optional, e.g. items)",
                                    key="define:dest_object", value="")
        delivery = st.selectbox(
            "Desired delivery mode",
            ["", "view", "export", "approval", "automatic"],
            key="define:delivery",
            help="view: visible here · export: produce an artifact · approval: "
                 "deliver on human authorization · automatic: unattended (only "
                 "real if an effect/connector exists -- declaring it does not "
                 "create one)")

    if st.button("Establish worker", type="primary", key="define_establish"):
        if not name.strip():
            st.error("Give the worker a name.")
            return
        # assemble the declared destination (drop blank segments); only real
        # when a system is named.
        dest = None
        if dest_system.strip():
            dest = {"system": dest_system.strip()}
            if dest_area.strip():
                dest["area"] = dest_area.strip()
            if dest_object.strip():
                dest["object"] = dest_object.strip()
        dlv = {"mode": delivery} if delivery else None
        try:
            # v0.4: on the xlsx-derived path the model's sources point at
            # _derived/*.json but carry no provenance yet -- attach the durable
            # workbook/sheet/header_row origin (injected here, after propose and
            # before establish) and establish with the RAW dir as trigger.
            origins = st.session_state.get("define:origins")
            est_model = define.attach_origin(model, origins) if origins else model
            if origins:
                w = define.establish_derived(
                    st.session_state["define:dir"], ws, name.strip(),
                    goal.strip() or name.strip(), task, est_model,
                    customer=customer.strip() or None,
                    destination=dest, delivery=dlv)
            else:
                w = define.establish_workspace(
                    ws, name.strip(), goal.strip() or name.strip(), task, est_model,
                    customer=customer.strip() or None,
                    destination=dest, delivery=dlv)
        except Exception as e:  # noqa: BLE001
            st.error(f"Establish failed: {type(e).__name__}: {e}")
            return
        st.success(f"Established `{w.name}` (v{w.current_version}) on the live fleet. "
                   f"Returning to the System Map.")
        _clear_define()
        # the new worker must be picked up by the un-cached fleet.load_all() and
        # re-linked by the incoming scan; drop the cached scan so it refreshes.
        st.session_state.pop("incoming", None)
        st.rerun()


def _render_advanced_model(ws, chosen, obs, task) -> None:
    """The advanced JSON editor / safety net (reuses modeller/app.py:234-242's
    fallback). Lets the operator paste or edit a model JSON and use it directly,
    bypassing a flaky LLM. It is previewed+validated by the normal path above."""
    with st.expander("Advanced — paste / edit the model JSON", expanded=False):
        current = st.session_state.get("define:model")
        seed = json.dumps(current, indent=2, ensure_ascii=False) if current else "{}"
        edited = st.text_area("Model JSON", value=seed, height=200,
                              key="define:json")
        if st.button("Use this JSON instead", key="define_use_json"):
            try:
                model = json.loads(edited)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                return
            model.setdefault("task", task)
            st.session_state["define:model"] = model
            # a hand-edited model is treated as settled: clear any pending question.
            st.session_state["define:asked"] = []
            st.rerun()


# ===========================================================================
# Sidebar: live fleet
# ===========================================================================

st.sidebar.title("Supervisor")
st.sidebar.caption("The LLM view of the fleet. Read-only EXCEPT for the one "
                   "explicit, human-gated write path: 'Establish worker' under "
                   "Define work. The LLM never writes; it only proposes. "
                   "Workspace v0.4 (declared XLSX materialization + durable "
                   "source provenance).")
st.sidebar.markdown("**Live fleet**")
st.sidebar.caption("Map, Review, and the incoming browser all read the live "
                   "fleet (`fleet/workers` + `data/`).")

root = snap.fleet.ROOT
if not root.is_dir() or not list(root.iterdir()):
    st.error(f"No live fleet found at {root}. Run `python fleet/seed.py` first.")
    st.stop()

snapshot = snap.build(root)
snapshot_hash = snap.hash_snapshot(snapshot)
st.sidebar.caption(f"snapshot hash: `{snapshot_hash}`\n\n"
                   f"{snapshot['worker_count']} worker(s) · "
                   f"{len(snapshot['pending_exceptions'])} pending exception(s)")

workers = fleet.load_all()
worker_by_name = {w.name: w for w in workers}
snap_by_name = {r["name"]: r for r in snapshot["workers"]}

map_tab, dashboard, improvements, rules_tab, fleet_tab = st.tabs(
    ["System Map", "Dashboard", "Improvements", "Rules", "Fleet & run details"])

# ===========================================================================
# System Map (primary) -- incoming browser (left) + map (centre) + assessment (on top)
# ===========================================================================

with map_tab:
    st.subheader("System Map")

    # v0.3: the Define-work panel replaces the normal System Map view while an
    # incoming-data dir is selected for modelling. It is the one surface in the
    # supervisor that writes -- and only via the explicit, human-gated Establish
    # action. Cancel returns to the normal map view.
    if st.session_state.get("define:dir"):
        _render_define_panel(st.session_state["define:dir"])
    else:
        st.caption("The map renders the modelled-work half of the company's flow "
                   "(Company -> Modelled Work -> Output); the incoming-data browser "
                   "to the left supplies the not-yet-modelled side. The map is derived "
                   "entirely from fleet state; the supervisor's assessment sits on top "
                   "of it. Task nodes are clickable.")

        # --- action row: Review + secondary counters ------------------------
        c_act, c_w, c_e, c_s = st.columns([2, 1, 1, 1])
        if c_act.button("Review fleet", type="primary"):
            with st.spinner("Supervisor reviewing (this calls the local model)…"):
                t0 = time.time()
                try:
                    session = supervision.review(snapshot, max_turns=8,
                                                  request_timeout=900)
                except Exception as e:  # noqa: BLE001 -- surface any model/bench error
                    session = None
                    st.session_state["last_error"] = f"{type(e).__name__}: {e}"
                else:
                    st.session_state["last_error"] = None
                elapsed = round(time.time() - t0, 1)
            if session is not None:
                session["elapsed_seconds"] = elapsed
                st.session_state["last_session"] = session
                # a run may have landed files in a worker's inbox; refresh the scan
                st.session_state.pop("incoming", None)
            st.rerun()

        c_w.metric("Workers", snapshot["worker_count"])
        c_e.metric("Pending exceptions", len(snapshot["pending_exceptions"]))
        c_s.metric("Scopes", len(snapshot.get("scopes", [])))

        if st.session_state.get("last_error"):
            st.error(f"Review failed: {st.session_state['last_error']}")
            st.caption("Is the local model running? `ollama serve` / check "
                       "`http://localhost:11434`.")

        st.markdown("---")

        # --- assessment on top of the company context ----------------------
        _render_assessment_banner(assessment.load_current())

        # --- the company context: incoming browser (left) + System Map (right)
        left, right = st.columns([2, 10])
        with left:
            _render_incoming_browser(_incoming())
        with right:
            _render_system_map(workers, snap_by_name, worker_by_name)

# ===========================================================================
# Dashboard (supporting) -- the full current assessment
# ===========================================================================

with dashboard:
    st.subheader("Supervisor Dashboard")
    st.caption("The supervisor's full current assessment of this fleet. The compact "
               "view sits on top of the System Map; this is the complete read. The "
               "Review-fleet action lives on the System Map tab.")
    _render_full_assessment(assessment.load_current())

# ===========================================================================
# Improvements (supporting) -- backlog + on-demand routing + human-gated activation
# ===========================================================================

with improvements:
    st.subheader("Improvements backlog")
    st.caption("Append-only: raise (during a run) -> route (on demand) -> activate "
               "(human-gated, grows rulebook.jsonl).")

    recs = backlog.load()
    if not recs:
        st.info("No proposals yet. Run **Review fleet** on the System Map tab to "
                "raise one.")

    # Route all un-routed
    unrouted = [r for r in recs if r["state"] == "raised"]
    if unrouted:
        c1, c2 = st.columns([1, 3])
        if c1.button(f"Route all un-routed ({len(unrouted)})",
                     key="route_all", disabled=not unrouted):
            desk = _desk()
            with c1.spinner("Routing…"):
                for r in unrouted:
                    try:
                        desk.route(r["id"])
                    except Exception as e:  # noqa: BLE001
                        st.session_state["last_route_error"] = \
                            f"{r['id']}: {type(e).__name__}: {e}"
                        break
            st.rerun()
        if c2.checkbox("Show routing help", value=False):
            c2.caption("Routing calls the local model (the S14/S15 routing desk + "
                       "mandatory duplicate gate). ~10-60s per proposal.")

    if st.session_state.get("last_route_error"):
        st.error(f"Routing failed: {st.session_state['last_route_error']}")

    for r in recs:
        st.markdown("---")
        cols = st.columns([1, 2, 3])
        with cols[0]:
            st.markdown(f"**{r['id']}**")
            st.caption(f"state: `{r['state']}`")
            if r.get("raised_at"):
                st.caption(f"raised {r['raised_at'][:19]}")
            if r.get("source_run"):
                st.caption(f"from `{r['source_run']}`")
        with cols[1]:
            st.markdown(r.get("text", "_(no text)_"))
            if r.get("evidence"):
                st.caption(f"evidence: {r['evidence']}")
        with cols[2]:
            if r["state"] == "raised":
                if st.button("Route", key=f"route_{r['id']}"):
                    desk = _desk()
                    with st.spinner("Routing (calls the local model)…"):
                        try:
                            result = desk.route(r["id"])
                        except Exception as e:  # noqa: BLE001
                            st.session_state["last_route_error"] = \
                                f"{type(e).__name__}: {e}"
                        else:
                            st.session_state["last_route_error"] = None
                            st.session_state["last_route_result"] = result
                    st.rerun()
            elif r["state"] == "activatable":
                rmeta = r.get("route_metadata") or {}
                st.markdown(f"route: **{r.get('suggested_route')}** · "
                            f"lifecycle `{rmeta.get('lifecycle_state')}`")
                if rmeta.get("rule_draft"):
                    st.caption(f"rule draft: {rmeta['rule_draft']}")
                if st.button("Activate", key=f"act_{r['id']}",
                             help="Appends this rule to rulebook.jsonl (human-gated)."):
                    desk = _desk()
                    res = desk.activate(r["id"])
                    if res.get("activated"):
                        st.success(f"Activated as `{res['rule_id']}` — added to "
                                   "rulebook.jsonl. See the Rules tab.")
                    else:
                        st.error(f"Activation refused: {res.get('error')}")
                    st.rerun()
            elif r["state"] == "active":
                st.markdown(f"route: **{r.get('suggested_route')}** · "
                            f"rule `{r.get('rule_id')}`")
                st.caption(f"activated {r.get('activated_at', '')[:19]}")
            else:  # routed
                rmeta = r.get("route_metadata") or {}
                st.markdown(f"route: **{r.get('suggested_route')}**")
                mg = rmeta.get("mandatory_gate") or {}
                bits = []
                if rmeta.get("restated_rule"):
                    bits.append(f"restates {rmeta['restated_rule']}")
                if rmeta.get("conflicts_with"):
                    bits.append(f"conflicts {rmeta['conflicts_with']}")
                if rmeta.get("compatible") is not None:
                    bits.append(f"compatible={rmeta['compatible']}")
                if mg.get("ran"):
                    bits.append(f"gate ran/caught={mg.get('caught')}/"
                                f"demoted={mg.get('demoted')}")
                if rmeta.get("rule_draft"):
                    bits.append(f"draft: {rmeta['rule_draft'][:60]}…")
                if bits:
                    st.caption(" · ".join(bits))

# ===========================================================================
# Rules (supporting) -- the rulebook + pending activations
# ===========================================================================

with rules_tab:
    st.subheader("Rulebook")
    st.caption("rulebook.jsonl -- the proven rules plus any human-activated ones. "
               "Grows only via the Activate button on the Improvements tab.")
    rules = rulebook.load_rules()
    if rules:
        rows = [{"id": r["id"], "area": r.get("area", ""),
                 "statement": r["statement"],
                 "provenance": r.get("provenance", ""),
                 "seeded": r.get("seeded")} for r in rules]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"{len(rules)} rule(s) — "
                   f"{sum(1 for r in rules if r.get('seeded'))} proven, "
                   f"{sum(1 for r in rules if not r.get('seeded'))} activated.")
    else:
        st.warning("No rules. Run `python supervisor/rulebook.py --self-test` "
                   "or seed the rulebook first.")

    pending = [r for r in backlog.load() if r["state"] == "activatable"]
    st.markdown("#### Pending activation")
    if pending:
        for r in pending:
            rmeta = r.get("route_metadata") or {}
            st.markdown(f"- `{r['id']}` — {r.get('text', '')}  \n"
                        f"  rule draft: {rmeta.get('rule_draft', '')}")
        st.caption("Activate these on the Improvements tab.")
    else:
        st.caption("No proposed rules pending activation.")

# ===========================================================================
# Fleet & run details (supporting) -- raw snapshot + counters + last run evidence
# ===========================================================================

with fleet_tab:
    st.subheader("Fleet & run details")
    st.caption("The raw machine state the supervisor sees, and the evidence from the "
               "last run. Technical.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Workers", snapshot["worker_count"])
    c2.metric("Pending exceptions", len(snapshot["pending_exceptions"]))
    c3.metric("Scopes", len(snapshot.get("scopes", [])))

    with st.expander("Snapshot JSON (what the supervisor sees)", expanded=False):
        st.json(snapshot)

    session = st.session_state.get("last_session")
    if session is not None:
        st.markdown("---")
        st.markdown(f"**Last run** `{session.get('run_id')}`")
        st.caption(
            f"stop={session.get('stop_reason')} · "
            f"turns={session.get('turn_count')} · "
            f"python used={session.get('python_used')} "
            f"({session.get('python_call_count')} call(s)) · "
            f"{session.get('elapsed_seconds')}s · "
            f"model `{session.get('model')}`")
        if session.get("budget_events"):
            st.warning(f"{len(session['budget_events'])} budget event(s)")

        raised = session.get("raised_proposals") or []
        if raised:
            st.markdown(f"**Proposals raised this run ({len(raised)}):**")
            for rp in raised:
                st.markdown(f"- `{rp['id']}` — {rp.get('text', '')}"
                            + (f" _(evidence: {rp.get('evidence')})_"
                               if rp.get("evidence") else ""))

        with st.expander("Evidence / analysis used", expanded=False):
            for turn in session.get("turns", []):
                st.markdown(f"**Turn {turn['turn'] + 1}**"
                            + (" · final answer" if turn.get("ended_run") else ""))
                with st.expander("assistant text", expanded=False):
                    st.text(turn["assistant"])
                for i, call in enumerate(turn.get("python_calls", []), 1):
                    st.markdown(f"Python call {i} — "
                                f"{'ok' if call['ok'] else 'error'}"
                                + (" (refused)" if call.get("refused") else ""))
                    st.code(call["code"], language="python")
                    if call.get("stdout"):
                        st.code(call["stdout"], language="text")
                    if call.get("error"):
                        st.code(call["error"], language="text")
    else:
        st.caption("No run in this session yet. Run **Review fleet** on the System Map "
                   "tab to populate per-run evidence here.")