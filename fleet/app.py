#!/usr/bin/env python3
"""Operations console for a fleet of established workers.

Not a chat interface. The question it answers is the one an operator actually
has: *is anything wrong, and if so what, and what does that worker even do.*

Thin by design — every decision lives in `fleet.py`, which has a self-test.

```text
FLEET      one row per worker: version, runs, exceptions, investigation state
WORKER     purpose, trigger, engine, the readable model, run history, versions
```

Two distinctions the layout is built around, because both were easy to get
wrong and both would mislead an operator:

  - **A completed run is not an accepted outcome.** `orders-enrichment` refuses
    8 rows across 4 healthy runs; `room-reservation` declines 4 of 5 requests.
    Neither is a fault. Showing them as failures would send someone chasing a
    worker that is doing exactly its job.
  - **A version's runs belong to that version.** v1's history is never
    re-rendered under v2's model.

    streamlit run fleet/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import urllib.request

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

import fleet  # noqa: E402
import inbox as inbox_mod  # noqa: E402
import investigation as inv_mod  # noqa: E402
import map_component  # noqa: E402
import system_map  # noqa: E402

st.set_page_config(page_title="Worker fleet", layout="wide")

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"


def ask(prompt: str) -> str:
    """The ONLY model call in the console, and only when an operator asks."""
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())["response"]

workers = fleet.load_all()
if not workers:
    st.error("No established workers. Run `python fleet/seed.py` first.")
    st.stop()

def has_inbox(w) -> bool:
    return (w.directory / "ledger.jsonl").is_file()


by_name = {w.name: w for w in workers}
# A map click selects a worker in the view that already exists. The map is
# navigation, not a second task-detail implementation.
options = ["Fleet", "System map"] + list(by_name)
if "map_pick" in st.session_state and st.session_state["map_pick"] in by_name:
    st.session_state["nav"] = st.session_state.pop("map_pick")
choice = st.sidebar.radio("Workers", options, key="nav")
st.sidebar.caption(f"{len(workers)} established worker(s)\n\n"
                   f"{len({w.engine for w in workers})} engine(s) in use")

# ---------------------------------------------------------------------------
# SYSTEM MAP
# ---------------------------------------------------------------------------
if choice == "System map":
    st.title("System map")
    st.caption("Derived entirely from fleet state — nothing here is stored, and "
               "nothing you do to the picture changes the system.")
    graph = system_map.build(workers)
    clicked = map_component.system_map(graph["nodes"], graph["edges"],
                                       height=720, key="fleet_map")
    st.markdown(" · ".join(
        f"<span style='color:{colour}'>&#9632;</span> {label}"
        for label, colour in system_map.legend()), unsafe_allow_html=True)
    st.markdown("**status** &nbsp; " + " · ".join(
        f"<span style='color:{colour}'><b>{glyph}</b> {label}</span>"
        for glyph, label, colour in system_map.status_legend()),
        unsafe_allow_html=True)
    scopes = [s for s, _ in system_map.lanes(workers) if s]
    st.caption(f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
               f"{len(scopes)} scope(s): {', '.join(scopes)}. Lanes are derived "
               f"from each worker's declared `customer`; engines and the "
               f"investigator are shared, so they sit outside every lane. Task "
               f"nodes are clickable.")
    picked = system_map.name_from((clicked or {}).get("id"))
    if picked:
        st.session_state["map_pick"] = picked
        st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# FLEET
# ---------------------------------------------------------------------------
if choice == "Fleet":
    st.title("Fleet")
    attention = [w for w in workers if w.open_investigation
                 or inv_mod.needs_investigation(w)
                 or (w.runs and not w.runs[-1]["ok"])
                 or (has_inbox(w) and (inbox_mod.summary(w)["exceptions"]
                                       or inbox_mod.summary(w)["in_flight"]))]
    if attention:
        st.error(f"{len(attention)} worker(s) need attention: "
                 + ", ".join(w.name for w in attention))
    else:
        st.success("No worker is waiting on anyone.")

    rows = []
    for w in workers:
        s = w.summary()
        rows.append({
            "": "!" if (w.open_investigation or s["last_status"] == "exception") else "",
            "worker": s["worker"],
            "task": s["task"],
            "version": f"v{s['version']}",
            "runs (this version)": s["runs_this_version"],
            "ok": s["successes"],
            "exceptions": s["exceptions"],
            "rows refused": s["rows_refused"],
            "inbox waiting": inbox_mod.summary(w)["waiting"] if has_inbox(w) else "",
            "queued exceptions": inbox_mod.summary(w)["exceptions"] if has_inbox(w) else "",
            "investigation": s["investigation"],
            "last run": (s["last_run"] or "").replace("T", " ")[:16],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("`rows refused` is the worker declining individual items under "
               "its declared policy — that is it working, not failing. "
               "`exceptions` is a run that could not proceed at all.")

    st.subheader("Engines in use")
    engines: dict[str, list] = {}
    for w in workers:
        engines.setdefault(w.engine, []).append(f"{w.name} v{w.current_version}")
    st.table([{"engine": engine, "workers": ", ".join(names),
               "count": len(names)} for engine, names in sorted(engines.items())])
    st.caption("Models vary per worker; the engine does not. Audit the engine "
               "once, read each worker's model on its own page.")
    st.stop()

# ---------------------------------------------------------------------------
# WORKER
# ---------------------------------------------------------------------------
w = by_name[choice]
s = w.summary()
st.title(w.name)
st.caption(f"{w.task} · v{s['version']} · {s['runs_this_version']} run(s) on "
           f"this version")

open_inv = w.open_investigation
if open_inv:
    st.error("Investigation open — this worker is stopped and waiting on a person.")
elif s["last_status"] == "exception":
    st.error("Last run raised an exception.")

st.header("Purpose")
st.write(w.purpose)

left, right = st.columns(2)
with left:
    st.header("Input")
    st.code(w.trigger)
    st.caption("A watched folder today. The lifecycle above it does not depend "
               "on that.")
with right:
    st.header("Engine")
    st.code(w.engine)
    st.caption("Shared, fixed and audited once. The worker is the model below, "
               "not generated code.")

st.header("Effect")
if not w.effect:
    st.write("None declared — this worker produces a result and changes nothing, "
             "so preview and production are the same execution.")
elif w.committing:
    st.write(f"On acceptance the model declares: `{w.effect}`")
    st.success(f"**Committing runtime** (`worker/runtime.py`). "
               f"{s['effects_applied']} effect(s) applied and verified, "
               f"{s['effects_failed']} failed, on this version.")
    st.caption("Applied means re-read from disk and confirmed — a write that "
               "returned is not evidence. A policy refusal attempts no effect "
               "and is a healthy run; an accepted decision whose effect did not "
               "land is an exception, because something downstream is entitled "
               "to believe the decision.")
else:
    st.write(f"On acceptance the model declares: `{w.effect}`")
    st.warning("No committing runtime for this task type, so runs here execute "
               "and report without landing the effect.")

st.header(f"Model — v{s['version']}")
for line in fleet.readable(w):
    st.markdown("- " + line)
with st.expander("Advanced · model JSON"):
    st.json(w.model)

# --- investigation ---------------------------------------------------------
if inv_mod.needs_investigation(w):
    st.header("Exception")
    packet = inv_mod.packet_of(w)
    st.error("The established model no longer fits the source.")
    for problem in packet["failure"]:
        st.code(problem)
    for source, diff in (packet.get("difference") or {}).items():
        st.write(f"**{source}** — expected `"
                 + "`, `".join(diff["declared_but_absent"]) + "`; observed `"
                 + "`, `".join(diff["present_and_undeclared"]) + "`")
    st.table([{"left": r["left"], "right": r["right"],
               "coverage": r["left_coverage"], "unique right key": r["right_unique"]}
              for r in packet.get("measured_relationships", [])])
    st.caption("Measured by the program. Nothing has interpreted them yet — a "
               "model is woken only when you ask.")
    if st.button("Investigate", type="primary"):
        with st.spinner("Investigating…"):
            inv_mod.investigate(w, ask)
        st.rerun()
    st.stop()

if w.investigation:
    st.header("Investigation")
    inv = w.investigation
    if inv["state"] == "proposed":
        st.info("A repair is proposed. It has not been applied — a live worker "
                "changes when you say so.")
        st.write(f"**Why:** {inv.get('why', '')}")
        st.table([{"source": r["source"], "from": r["from"], "to": r["to"]}
                  for r in inv["proposal"]])
        if st.button(f"Establish v{w.current_version + 1}", type="primary"):
            w2 = inv_mod.apply_proposal(w)
            retried = inv_mod.retry_queued(w2)
            st.success(f"v{w2.current_version} established; "
                       f"{len(retried)} queued item(s) retried.")
            st.rerun()
        st.stop()
    if inv["state"] == "open":
        st.warning(inv.get("question") or "Awaiting a human answer.")
        options = inv.get("options") or []
        if options:
            choice = st.radio("Which replaces it?", options, key="inv_choice")
            if st.button("That's the one"):
                inv_mod.answer(w, choice)
                st.rerun()
        st.stop()
    if inv.get("resolved_to_version"):
        st.success(f"Resolved — promoted to v{inv['resolved_to_version']}")
    st.write("**What failed**")
    for problem in inv["failure"]:
        st.code(problem)
    if inv.get("difference"):
        st.write("**What changed in the source**")
        st.json(inv["difference"])
    if inv.get("proposal"):
        st.write("**What was changed in the model**")
        st.table([{"source": r["source"], "from": r["from"], "to": r["to"]}
                  for r in inv["proposal"]])

# --- inbox -----------------------------------------------------------------
if has_inbox(w):
    st.header("Inbox")
    box = inbox_mod.summary(w)
    cols = st.columns(4)
    cols[0].metric("waiting", box["waiting"])
    cols[1].metric("processed", box["processed"])
    cols[2].metric("queued exceptions", box["exceptions"])
    cols[3].metric("duplicates skipped", box["duplicates_skipped"])
    if box["in_flight"]:
        st.warning(f"{box['in_flight']} item(s) left claimed by an interrupted "
                   f"pass. Run recovery — it reconciles each against the "
                   f"worker's actual state before deciding to retry.")
    st.caption(f"{box['items_seen']} distinct work item(s) seen, "
               f"{box['completed']} completed, {box['in_flight']} in flight, "
               f"{box['recovered']} resolved by recovery. "
               f"An item is identified by the sha256 of its content, so a resent "
               f"file is the same work — it is not run again and its effect is "
               f"not applied again.")
    st.dataframe([{
        "at": e["at"].replace("T", " ")[11:19],
        "file": e.get("file", ""),
        "state": e["state"],
        "request": e.get("request", ""),
        "decision": e.get("decision", ""),
        "reason": e.get("reason", "") or "",
        "effect": ("" if e.get("effect_applied") is None
                   else "applied" if e["effect_applied"] else "FAILED"),
        "verdict": e.get("verdict", ""),
        "item": (e.get("item_id") or "")[:10],
    } for e in inbox_mod.ledger(w)], use_container_width=True, hide_index=True)
    st.caption("Append-only. An item is claimed before it runs, so an "
               "interrupted pass leaves evidence rather than a file that looks "
               "fresh.")

# --- version history -------------------------------------------------------
st.header("Version history")
st.caption("Append-only. A version's runs belong to that version; promoting "
           "never restates what an earlier version did.")
history = []
for entry in w.history:
    version = entry["version"]
    runs = w.runs_for(version)
    history.append({
        "version": f"v{version}",
        "event": entry["event"],
        "established": entry["at"].replace("T", " ")[:16],
        "runs": len(runs),
        "ok": sum(1 for r in runs if r["ok"]),
        "exceptions": sum(1 for r in runs if not r["ok"]),
        "digest": entry["digest"][:12],
        "why": entry.get("why", ""),
    })
st.dataframe(history, use_container_width=True, hide_index=True)

if len(w.versions) > 1:
    versions = sorted(w.versions)
    picked = st.selectbox("Compare with", versions[:-1],
                          format_func=lambda v: f"v{v}")
    st.write(f"**v{picked} → v{w.current_version}**")
    for line in fleet.version_diff(w, picked, w.current_version):
        st.code(line)
    with st.expander(f"How v{picked} read at the time"):
        for line in fleet.readable(w, picked):
            st.markdown("- " + line)

# --- runs ------------------------------------------------------------------
st.header("Runs")
recent = list(reversed(w.runs))[:15]
st.dataframe([{
    "at": r["at"].replace("T", " ")[:19],
    "version": f"v{r['version']}",
    "status": "ok" if r["ok"] else "EXCEPTION",
    "request": r.get("request", ""),
    "rows": r.get("rows", ""),
    "refused": r.get("refused", 0),
    "outcome": ("" if r.get("accepted") is None
                else "accepted" if r["accepted"] else "declined"),
    "effect": ("—" if r.get("effect_applied") is None
               else "applied" if r["effect_applied"] else "FAILED"),
    "state": (f"{r['state_before']}→{r['state_after']}"
              if r.get("state_before") is not None else ""),
    "reason": ", ".join(r.get("refusals") or []) or ", ".join(r.get("problems") or []),
} for r in recent], use_container_width=True, hide_index=True)

refused_total = sum(r.get("refused", 0) for r in w.runs)
if refused_total:
    st.caption(f"{refused_total} item(s) refused across all runs, under the "
               f"worker's own declared policy. Refusals are the worker working.")
if w.committing:
    st.caption("`state` is the worker's own state before and after the run. A "
               "refusal leaves it unchanged; that is the point of the column.")
