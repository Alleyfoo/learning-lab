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

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

import fleet  # noqa: E402

st.set_page_config(page_title="Worker fleet", layout="wide")

workers = fleet.load_all()
if not workers:
    st.error("No established workers. Run `python fleet/seed.py` first.")
    st.stop()

by_name = {w.name: w for w in workers}
choice = st.sidebar.radio("Workers", ["Fleet"] + list(by_name))
st.sidebar.caption(f"{len(workers)} established worker(s)\n\n"
                   f"{len({w.engine for w in workers})} engine(s) in use")

# ---------------------------------------------------------------------------
# FLEET
# ---------------------------------------------------------------------------
if choice == "Fleet":
    st.title("Fleet")
    attention = [w for w in workers if w.open_investigation
                 or (w.runs and not w.runs[-1]["ok"])]
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
if w.effect:
    st.write(f"On acceptance the model declares: `{w.effect}`")
    st.warning("This console executes and reports; it does **not** commit that "
               "effect. The source data is byte-identical after these runs. A "
               "committing runtime is `calendar_job/unattended.py`, which is a "
               "separate thing from this view.")
else:
    st.write("None declared — this worker produces a result and changes nothing.")

st.header(f"Model — v{s['version']}")
for line in fleet.readable(w):
    st.markdown("- " + line)
with st.expander("Advanced · model JSON"):
    st.json(w.model)

# --- investigation ---------------------------------------------------------
if w.investigation:
    st.header("Investigation")
    inv = w.investigation
    if inv["state"] == "open":
        st.warning(inv.get("question") or "Awaiting a human answer.")
    else:
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
    "reason": ", ".join(r.get("refusals") or []) or ", ".join(r.get("problems") or []),
} for r in recent], use_container_width=True, hide_index=True)

refused_total = sum(r.get("refused", 0) for r in w.runs)
if refused_total:
    st.caption(f"{refused_total} item(s) refused across all runs, under the "
               f"worker's own declared policy. Refusals are the worker working.")
