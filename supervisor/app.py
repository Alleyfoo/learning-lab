#!/usr/bin/env python3
"""Workspace v0.2 -- the Supervisor Streamlit surface, recentred on the System Map.

The organizing concept is the **company's actual flow**: Company -> Incoming Data ->
Understanding -> Modelled Work -> Output. The Fleet System Map is back as the **primary
visual model**: it renders the *modelled-work* half of that flow (company/scope ->
declared inputs/sources -> modelled workers -> outputs, with exception/investigator
side paths) and begins after modelling. The raw "Incoming Data" the map does not yet
draw is supplied by a new **incoming-file/workbook/sheet browser** to its left -- the
`data/` library (including data not yet modelled into a worker) and each worker's
inbox/processed/exceptions. "Understanding"/modelling still happens on a separate
surface (PRODUCT.md priority #4 -- the next milestone, not yet done). The supervisor's
**current assessment sits on top** of this company context, so its verdict is visibly
attached to the flows it describes.

  System Map (primary)   incoming browser (left) + the Fleet System Map (centre) +
                         the supervisor's current assessment (on top). The Review-fleet
                         action lives here and feeds the assessment. Live fleet only.
  Dashboard              the full current assessment (supporting read).
  Improvements           the persistent append-only backlog (raise/route/activate).
  Rules                 rulebook.jsonl + pending activations.
  Fleet & run details    the raw snapshot + full counters + the last run's per-turn
                         evidence. Technical.

Everything reads the **live fleet** (`fleet/workers` + `data/`). The S1 fixture selector
is gone -- the map, the review, and the browser must describe one coherent fleet, and
the recentering is around the company's actual flows, not a lab condition. Read-only:
this surface never changes a worker, a model, or a run.

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
        if worker:
            bits.append(_badge(f"worker:{worker}", "#2a6f2a"))
        else:
            bits.append(_badge("no worker link", "#8a6d3b"))
        if entry.get("has_model"):
            bits.append(_badge("model exists", "#3a6a9a"))
        if entry.get("has_adapter"):
            bits.append(_badge("adapter", "#6a6a6a"))
        header = (f"`{entry['dir']}/` &nbsp; " + " ".join(bits)
                  + f" &nbsp; <span style='color:#888;font-size:0.8em'>"
                  f"{len(entry['files'])} file(s)</span>")
        with st.expander(header, expanded=False):
            for f in entry["files"]:
                line = f"- {f['name']} ({f['kind']})"
                if f["sheets"]:
                    line += " &nbsp; sheets: " + ", ".join(f["sheets"])
                st.markdown(line)

    st.markdown("**Worker inboxes**")
    inboxes = scan_result.get("inboxes", [])
    if not inboxes:
        st.caption("no inbox files in any worker.")
    for ib in inboxes:
        header = (f"`{ib['worker']}` &nbsp; <span style='color:#888;font-size:0.8em'>"
                  f"{ib.get('customer') or '—'}</span> &nbsp; "
                  f"<span style='color:#888;font-size:0.8em'>{len(ib['files'])} "
                  f"file(s)</span>")
        with st.expander(header, expanded=False):
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

    # click a worker node -> show its detail from the snapshot record
    picked = system_map.name_from((clicked or {}).get("id"))
    if picked:
        st.session_state["map_pick"] = picked
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
                    st.rerun()


# ===========================================================================
# Sidebar: live fleet
# ===========================================================================

st.sidebar.title("Supervisor")
st.sidebar.caption("The LLM view of the fleet. Read-only: this surface never "
                   "changes a worker, a model, or a run. Workspace v0.2.")
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
    st.caption("The map renders the modelled-work half of the company's flow "
               "(Company -> Modelled Work -> Output); the incoming-data browser to the "
               "left supplies the not-yet-modelled side. The map is derived entirely "
               "from fleet state; the supervisor's assessment sits on top of it. "
               "Task nodes are clickable.")

    # --- action row: Review + secondary counters ----------------------------
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

    # --- assessment on top of the company context --------------------------
    _render_assessment_banner(assessment.load_current())

    # --- the company context: incoming browser (left) + System Map (right) -
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