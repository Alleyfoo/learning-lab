#!/usr/bin/env python3
"""Model builder — a human-facing view over the four existing task types.

Thin by design. Every decision lives in `builder.py`, which has a self-test; this
file arranges widgets and calls it. Same split as the workbook browser and
`structure_view.py`, for the same reason: logic inside a UI cannot be tested.

Five steps, in the order a person actually works:

    1. task        which of the four
    2. sources     what data is available, and what is inside each file
    3. model       construct or edit, as JSON
    4. validate    the TASK'S OWN validator, verbatim
    5. preview     deterministic execution -- no model, no guessing
    6. approve     binds the model, its sources, and the preview SHOWN

Step 4 is deliberately not softened. The validators already say exactly what is
wrong and where; putting a friendlier schema layer in front of them would hide
whether they are good enough to steer a person, which is a thing worth knowing.

    streamlit run modeller/app.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

import builder  # noqa: E402

st.set_page_config(page_title="Task model builder", layout="wide")
st.title("Task model builder")
st.caption("Operates the four existing task types. Deterministic preview — no model is invoked.")

# --- 1. task -----------------------------------------------------------------
task = st.sidebar.selectbox("Task type", builder.task_names())
binding = builder.TASKS[task]
st.sidebar.caption(f"base: `{binding.base.relative_to(builder.LAB)}`")

unbound = builder.unbound_tasks()
if unbound:
    st.sidebar.warning(
        f"Registered with the floor but not runnable here: {unbound}. "
        f"Add a binding in builder.TASKS.")

# --- 2. sources --------------------------------------------------------------
st.subheader("1 · Sources")
sources = builder.available_sources(task)
if not sources:
    st.info("No data files under this task's `fixtures/`.")
else:
    st.table([{"file": s.path,
               "collections": ", ".join(s.collections) or "(none)",
               "rows": ", ".join(f"{k}={v}" for k, v in s.counts.items())}
              for s in sources])
    st.caption("Collections are read from each file, not guessed from its name — "
               "a model names a file *and* a key inside it.")

# --- 3. model ----------------------------------------------------------------
st.subheader("2 · Model")
models = builder.available_models(task)
choice = st.selectbox("Start from", models + ["(blank)"])

state_key = f"draft::{task}::{choice}"
if state_key not in st.session_state:
    if choice == "(blank)":
        st.session_state[state_key] = json.dumps({
            "model_version": 1, "model_id": f"{task}_draft", "task": task,
            "sources": {}, }, indent=2)
    else:
        st.session_state[state_key] = json.dumps(
            builder.load_model(task, choice), indent=2, ensure_ascii=False)

text = st.text_area("Model JSON", value=st.session_state[state_key],
                    height=380, key=f"editor::{state_key}")

try:
    raw = json.loads(text)
    parse_error = None
except json.JSONDecodeError as exc:
    raw, parse_error = None, str(exc)

if parse_error:
    st.error(f"Not valid JSON — {parse_error}")
    st.stop()

# --- 4. validate -------------------------------------------------------------
st.subheader("3 · Validate")
report = builder.validate_raw(task, raw)
if report.valid:
    st.success("Valid.")
else:
    st.error(f"{len(report.problems)} problem(s). These are the task's own "
             f"validator, unedited:")
    st.table([{"code": p.code, "where": p.where, "detail": p.detail}
              for p in report.problems])

# --- 5. preview --------------------------------------------------------------
st.subheader("4 · Preview")
request = None
if binding.needs_request:
    request = st.text_input(binding.request_label, value="")

pv = builder.preview(task, raw, request=request or None)
if not pv.ok:
    st.warning("Not previewed:")
    for problem in pv.problems:
        st.write(f"- {problem}")
else:
    if pv.run_refused:
        st.error(f"Run refused — {pv.run_refused}")
        st.caption("A refused run delivers no rows at all, rather than a partial "
                   "table beside a refusal.")
    elif pv.rows:
        st.dataframe([dict(zip(pv.columns, row)) for row in pv.rows],
                     width="stretch")
    else:
        st.info("No rows.")
    for note in pv.notes:
        st.caption(note)
    if pv.refused:
        st.write("Refused:")
        st.table(pv.refused)

# --- 6. approve --------------------------------------------------------------
st.subheader("5 · Approve")
st.caption("Binds the model, the content of its sources, and the preview text "
           "shown above. It does not inherit the frozen authority path's "
           "guarantees — that path is about recipes over workbooks.")

with st.expander("What exactly will be hashed"):
    st.code(builder.render_preview(pv), language="text")

approver = st.text_input("Approved by", value="")
save_to = APP / "approvals"

if st.button("Approve", disabled=not (pv.ok and approver)):
    approval = builder.approve(task, raw, pv, approver,
                               datetime.now(timezone.utc).isoformat(timespec="seconds"))
    save_to.mkdir(exist_ok=True)
    out = save_to / f"{task}_{approval.model_id}_{approval.model_sha256[:12]}.json"
    out.write_text(approval.to_json() + "\n", encoding="utf-8")
    st.success(f"Approved. Recorded at `{out.relative_to(builder.LAB)}`")
    st.code(approval.to_json(), language="json")
elif not pv.ok:
    st.caption("Approval is unavailable until the preview succeeds — otherwise it "
               "would record agreement to something nobody saw working.")

# --- saving ------------------------------------------------------------------
st.divider()
col_a, col_b = st.columns([3, 1])
target = col_a.text_input("Save model as", value=choice if choice != "(blank)"
                          else f"models/{raw.get('model_id', 'draft')}.json")
if col_b.button("Save", disabled=not report.valid):
    path = builder.save_model(task, target, raw)
    st.success(f"Written to `{path.relative_to(builder.LAB)}`")
elif not report.valid:
    col_b.caption("Fix problems first")
