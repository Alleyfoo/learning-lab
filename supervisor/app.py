#!/usr/bin/env python3
"""Workspace v0 -- the Supervisor Streamlit surface.

The S1 vertical slice (one button -> core.review) is replaced by a four-tab
tool whose purpose is to USE the supervisor and collect real behavior:

  Current       the read-only fleet snapshot the supervisor sees
  Flow          "Review fleet" -> a SupervisorHarness run (supervision.review),
                with the session summary, per-turn evidence, and the proposals
                raised in the run. Saved to supervisor/runs/<run_id>/.
  Improvements  the persistent append-only backlog (raise/route/activate),
                with on-demand Route / Route-all buttons (the S14/S15 routing
                desk) and a human-gated Activate button for NEW_RULE proposals
                (the only path that grows the real rulebook.jsonl).
  Rules         rulebook.jsonl -- the 5 proven rules plus any human-activated
                ones -- and the proposed rules pending activation.

Routing and activation are on-demand from the Improvements page: a run only
RAISES. Rule activation is genuinely human-gated (a deliberate button press).

  streamlit run supervisor/app.py
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

import backlog       # noqa: E402
import rulebook       # noqa: E402
import routing        # noqa: E402
import supervision     # noqa: E402
import snapshot as snap  # noqa: E402

st.set_page_config(page_title="Supervisor", layout="wide")

S1_FIX = LAB / "s1" / "fixtures"

# A single RoutingDesk holds only model config (no per-route state), so one
# shared instance is fine. Built lazily and cached in session_state.
def _desk() -> "routing.RoutingDesk":
    if "desk" not in st.session_state:
        st.session_state["desk"] = routing.RoutingDesk()
    return st.session_state["desk"]


# --- sidebar: snapshot source --------------------------------------------

st.sidebar.title("Supervisor")
st.sidebar.caption("The LLM view of the fleet. Read-only: this surface never "
                   "changes a worker, a model, or a run. Workspace v0.")

source = st.sidebar.radio(
    "Snapshot source",
    ["S1-A boring", "S1-B effect failure", "S1-C noisy healthy",
     "S1-D pattern", "Live fleet"],
    index=1,
)

if source == "Live fleet":
    root = snap.fleet.ROOT
    label = "live"
else:
    label = source.split()[0].split("-")[1]
    root = S1_FIX / label

if not root.is_dir() or not list(root.iterdir()):
    st.error(f"No fleet found at {root}. Run `python s1/build_conditions.py` "
             f"or `python fleet/seed.py` first.")
    st.stop()

snapshot = snap.build(root)
snapshot_hash = snap.hash_snapshot(snapshot)
st.sidebar.caption(f"snapshot hash: `{snapshot_hash}`\n\n"
                   f"{snapshot['worker_count']} worker(s) · "
                   f"{len(snapshot['pending_exceptions'])} pending exception(s)")

current, flow, improvements, rules_tab = st.tabs(
    ["Current", "Flow", "Improvements", "Rules"])

# --- Current: what the supervisor sees ------------------------------------

with current:
    st.subheader("Current fleet snapshot")
    c1, c2, c3 = st.columns(3)
    c1.metric("Workers", snapshot["worker_count"])
    c2.metric("Pending exceptions", len(snapshot["pending_exceptions"]))
    c3.metric("Scopes", len(snapshot.get("scopes", [])))
    with st.expander("Snapshot JSON (what the supervisor sees)", expanded=False):
        st.json(snapshot)

# --- Flow: review the fleet through the SupervisorHarness -----------------

with flow:
    st.subheader("Review fleet")
    st.caption("Runs the supervisor through the proven SupervisorHarness path. "
               "The supervisor may `raise_proposal(text, evidence)` to file "
               "improvements; routing and activation happen later, on demand.")
    if st.button("Review fleet", type="primary"):
        with st.spinner("Supervisor reviewing (this calls the local model)…"):
            t0 = time.time()
            try:
                session = supervision.review(snapshot, max_turns=6,
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

    if st.session_state.get("last_error"):
        st.error(f"Review failed: {st.session_state['last_error']}")
        st.caption("Is the local model running? `ollama serve` / check "
                   "`http://localhost:11434`.")

    session = st.session_state.get("last_session")
    if session is not None:
        st.markdown(session.get("final_response") or "_(no final response)_")
        recon = session.get("reconstructability", {})
        st.caption(
            f"stop={session.get('stop_reason')} · "
            f"turns={session.get('turn_count')} · "
            f"python used={session.get('python_used')} "
            f"({session.get('python_call_count')} call(s)) · "
            f"{session.get('elapsed_seconds')}s · "
            f"model `{session.get('model')}` · run `{session.get('run_id')}`")
        if session.get("budget_events"):
            st.warning(f"{len(session['budget_events'])} budget event(s)")

        raised = session.get("raised_proposals") or []
        if raised:
            st.markdown(f"**Proposals raised this run ({len(raised)}):**")
            for rp in raised:
                st.markdown(f"- `{rp['id']}` — {rp.get('text', '')}"
                            + (f" _(evidence: {rp.get('evidence')})_"
                               if rp.get("evidence") else ""))
            st.caption("Route and activate these on the **Improvements** tab.")
        else:
            st.caption("No proposals raised this run.")

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

# --- Improvements: the backlog + on-demand routing + human-gated activation --

with improvements:
    st.subheader("Improvements backlog")
    st.caption("Append-only: raise (during a run) -> route (on demand) -> activate "
               "(human-gated, grows rulebook.jsonl).")

    recs = backlog.load()
    if not recs:
        st.info("No proposals yet. Run **Review fleet** on the Flow tab to raise one.")

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

# --- Rules: the rulebook + pending activations ----------------------------

with rules_tab:
    st.subheader("Rulebook")
    st.caption("rulebook.jsonl -- the 5 proven rules plus any human-activated "
               "ones. Grows only via the Activate button on the Improvements tab.")
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