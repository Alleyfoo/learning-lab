#!/usr/bin/env python3
"""Minimal Streamlit Supervisor surface for S1.

Not the final UI. Just enough to show the LLM view of the fleet alongside the
existing machine-view console:

  Supervisor
  ──────────
  [Review fleet]

  <LLM output>

  Evidence / analysis used   (expandable)

No Memory, Rulebook or Improvements functionality yet. If the LLM spontaneously
proposes an improvement, it is preserved as prose in the response and the tool
log -- no register is built around it.

  streamlit run supervisor/app.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "fleet"))
sys.path.insert(0, str(LAB / "s1"))

import core  # noqa: E402
import snapshot as snap  # noqa: E402

st.set_page_config(page_title="Supervisor", layout="wide")

S1_FIX = LAB / "s1" / "fixtures"
S1_PROMPT = (LAB / "s1" / "prompt.txt").read_text(encoding="utf-8").strip()

st.title("Supervisor")
st.caption("The LLM view of the fleet. Read-only: this surface never changes a "
           "worker, a model, or a run. S1 vertical slice.")

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
st.sidebar.caption(f"snapshot hash: `{snap.hash_snapshot(snapshot)}`\n\n"
                   f"{snapshot['worker_count']} worker(s) · "
                   f"{len(snapshot['pending_exceptions'])} pending exception(s)")

with st.sidebar.expander("Snapshot (what the supervisor sees)"):
    st.json(snapshot)

if st.button("Review fleet", type="primary"):
    with st.spinner("Supervisor reviewing…"):
        t0 = time.time()
        record = core.review(snapshot, S1_PROMPT, max_turns=6, request_timeout=600)
        record["elapsed_seconds"] = round(time.time() - t0, 1)
        st.session_state["supervisor_record"] = record

record = st.session_state.get("supervisor_record")
if not record:
    st.stop()

st.subheader("Supervisor output")
st.markdown(record["final_response"] or "_(no final response)_")
st.caption(f"stop={record['stop_reason']} · turns={record['turn_count']} · "
           f"python used={record['python_used']} "
           f"({record['python_call_count']} call(s)) · "
           f"{record['elapsed_seconds']}s · model `{record['model']}`")

with st.expander("Evidence / analysis used", expanded=False):
    if not record["turns"]:
        st.write("_(no turns recorded)_")
    for turn in record["turns"]:
        st.markdown(f"**Turn {turn['turn'] + 1}**" +
                    (" · final answer" if turn["ended_run"] else ""))
        with st.expander("assistant text", expanded=False):
            st.text(turn["assistant"])
        for i, call in enumerate(turn["python_calls"], 1):
            st.markdown(f"Python call {i} — "
                        f"{'ok' if call['ok'] else 'error'}"
                        + (" (refused)" if call["refused"] else ""))
            st.code(call["code"], language="python")
            if call["stdout"]:
                st.code(call["stdout"], language="text")
            if call["error"]:
                st.code(call["error"], language="text")