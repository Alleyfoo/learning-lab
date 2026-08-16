#!/usr/bin/env python3
"""Model builder — from selected data and a sentence to a deterministic worker.

Thin by design. Every decision lives in `pipeline.py` and `builder.py`, both of
which have self-tests; this file arranges widgets and calls them.

```text
1  Data                 select sources; see what the PROGRAM measured
2  What do you want?    the job in plain language
3  Understanding        observed / inferred / unknown, as claims with evidence
4  Missing truth        only when a load-bearing claim cannot be established
5  Proposed task        readable, with the JSON under Advanced
6  Preview              the actual table the worker will produce
```

The LLM is used at steps 3 and 5 only — interpretation and task definition. It
never enriches anything, never decides a runtime value, and structurally cannot
emit `OBSERVED` or `CONFIRMED`. Runtime is the existing deterministic executor
and contains no model.

**Step 4 appears only when it must.** Experiment Y established that a sufficient
join is established from evidence without asking; a UI that asked every time
would be safe and useless. What is shown is claims, evidence and status — never
private reasoning.

The old JSON editor remains under Advanced. It is no longer the way in.

    streamlit run modeller/app.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

import builder  # noqa: E402
import pipeline  # noqa: E402

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"

st.set_page_config(page_title="Task modeller", layout="wide")
st.title("Task modeller")
st.caption("Select data, describe the job. The system works out the smallest "
           "deterministic worker — and asks only when the evidence cannot settle "
           "a load-bearing fact.")


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())["response"]


def reset(*keys: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)


S = st.session_state

# ---------------------------------------------------------------------------
# 1. Data
# ---------------------------------------------------------------------------
st.header("1 · Data")

spaces = {w.label: w for w in pipeline.workspaces()}
label = st.selectbox("Where the data is", list(spaces),
                     key="ws", on_change=lambda: reset("report", "model", "block"))
ws = spaces[label]

found = pipeline.sources_in(ws)
if not found:
    st.error(f"No JSON collections found in {ws.directory}")
    st.stop()

picked_names = st.multiselect(
    "Sources to use", [f"{s.filename} → {s.collection}" for s in found],
    default=[f"{s.filename} → {s.collection}" for s in found],
    on_change=lambda: reset("report", "model", "block"))
chosen = [s for s in found if f"{s.filename} → {s.collection}" in picked_names]
if len(chosen) < 2:
    st.info("Select at least two sources — enrichment joins one to another.")
    st.stop()

observed = pipeline.observed_facts(ws, chosen)

cols = st.columns(len(chosen))
for col, src in zip(cols, chosen):
    with col:
        st.subheader(src.collection)
        st.caption(f"{src.filename} · {src.rows} rows")
        for claim in observed:
            body = claim["claim"]
            if body.get("source") == src.collection and body.get("field"):
                st.write(f"`{body['field']}` · {body['value_kind']} · "
                         f"{body['distinct_values']} distinct · "
                         f"e.g. {', '.join(map(str, body['examples']))}")

rels = pipeline.relationships(observed)
if rels:
    st.markdown("**Measured candidate relationships**")
    st.table([{"left": r["left"], "right": r["right"],
               "left coverage": r["left_coverage"],
               "right unique": r["right_unique"]} for r in rels])
    st.caption("Measurements only. The program does not say which pairing is "
               "intended — that is a binding, and a binding is a decision.")

# ---------------------------------------------------------------------------
# 2. What do you want to do?
# ---------------------------------------------------------------------------
st.header("2 · What do you want to do?")
goal = st.text_area(
    "In your own words", key="goal",
    value="Enrich these orders with the matching product price and calculate "
          "the line total.", height=80)

if st.button("Work out the task", type="primary"):
    reset("report", "model", "block", "answered")
    with st.spinner("Inspecting…"):
        S["report"], S["ingest"] = pipeline.interpret(observed, goal, ask)
    with st.spinner("Defining the task…"):
        S["model"], S["block"] = pipeline.define(
            S["report"], goal, pipeline.source_spec(ws, chosen), ask)

if "report" not in S:
    st.stop()

# ---------------------------------------------------------------------------
# 3. Understanding
# ---------------------------------------------------------------------------
st.header("3 · Understanding")
report = S["report"]
left, right = st.columns(2)
with left:
    st.markdown("**Inferred** — the inspector's interpretation, with its basis")
    for c in report:
        if c["status"] == "INFERRED":
            b = c["claim"]
            where = f"{b.get('source')}" + (f".{b['field']}" if b.get("field") else "")
            st.write(f"`{where}` — {b.get('meaning')}")
            st.caption("basis: " + ", ".join(c.get("basis") or []))
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

dropped = (S.get("ingest") or {}).get("rejected") or []
stripped = (S.get("ingest") or {}).get("stripped") or []
if dropped or stripped:
    with st.expander(f"Boundary refused {len(dropped)} claim(s), "
                     f"stripped {len(stripped)}"):
        st.json({"rejected": dropped, "stripped": stripped})

for leftname in pipeline.join_left_candidates(observed):
    fit = pipeline.sufficiency(observed, leftname)
    if len(fit["candidates"]) > 1:
        st.caption(f"`{leftname}` → sufficiency policy says **{fit['verdict']}** "
                   f"({len(fit['sufficient'])} of {len(fit['candidates'])} "
                   f"candidates complete and unique)")

# ---------------------------------------------------------------------------
# 4. Missing truth
# ---------------------------------------------------------------------------
if S.get("block"):
    st.header("4 · One thing I cannot establish")
    questions = pipeline.questions_from(S["block"], observed)
    q = questions[0]
    st.warning(q.text)
    if len(questions) > 1:
        st.caption(f"{len(questions) - 1} further question(s) will be asked "
                   f"separately — confirmation resolves claims, not workflows.")
    choice = (st.radio("Answer", q.options, key="choice") if q.options
              else st.text_input("Answer", key="choice"))
    if st.button("That's the one"):
        answer = (f"{q.source[0] if isinstance(q.source, list) else q.source}"
                  f".{q.field} matches {choice}") if q.options else choice
        S["report"] = pipeline.answer(S["report"], q, answer)
        with st.spinner("Resuming…"):
            S["model"], S["block"] = pipeline.define(
                S["report"], goal, pipeline.source_spec(ws, chosen), ask,
                resumed=True)
        st.rerun()
    st.stop()

model = S.get("model")
if not model:
    st.error("The definer returned neither a model nor a question.")
    st.stop()

# ---------------------------------------------------------------------------
# 5. Proposed task
# ---------------------------------------------------------------------------
st.header("5 · Proposed task")
complaint = pipeline.check_join_supported(model, observed, S['report'])
if complaint:
    st.error(f"Refused by the sufficiency policy: {complaint}")
    st.caption("The definer is not taken at its word — the program checks the "
               "declared join against its own measurements.")
    st.stop()
for line in pipeline.readable(model):
    st.markdown("- " + line)
with st.expander("Advanced · model JSON"):
    edited = st.text_area("JSON", json.dumps(model, indent=2), height=320,
                          key="json")
    if st.button("Use this JSON instead"):
        try:
            S["model"] = json.loads(edited)
            st.rerun()
        except json.JSONDecodeError as exc:
            st.error(f"not valid JSON: {exc}")

# ---------------------------------------------------------------------------
# 6. Deterministic preview
# ---------------------------------------------------------------------------
st.header("6 · Deterministic preview")
st.caption("The existing validator and executor, unchanged. No model runs here.")
p = pipeline.build(ws, model)
if not p.ok:
    st.error("The model did not validate — it was not executed.")
    for problem in p.problems:
        st.code(problem)
    st.stop()

st.dataframe([dict(zip(p.columns, row)) for row in p.rows],
             use_container_width=True)
for note in p.notes:
    st.caption(note)
if p.refused:
    st.warning(f"{len(p.refused)} row(s) refused")
    st.table([{"key": r.get("key"), "reason": r.get("reason")} for r in p.refused])
if p.run_refused:
    st.error(f"Run refused: {p.run_refused}")
