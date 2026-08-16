#!/usr/bin/env python3
"""Graph data for the Fleet System Map. Pure, Streamlit-free, deterministic.

Same split as `food-prep`'s `ui/graph.py`: every decision lives here with a
self-test, and the view only arranges widgets.

## The map is a VIEW. It is never a source of truth.

Everything below is derived from state that already exists and is already
authoritative — `worker.json`, `versions/vN.json`, `history.jsonl`,
`runs.jsonl`, `investigation.json`, `ledger.jsonl`, `fleet.ENGINES`. Nothing
here stores a position, a status or a relationship of its own, and **building
the graph writes nothing at all** — the self-test asserts that by comparing file
mtimes across a build.

That matters more than it sounds. A map that remembered where you dragged a node
would immediately be a second, unversioned description of the system, drifting
against the one the workers actually run on.

## Node types, typed IDs

```text
scope:<name>          a customer or scope, ONLY where a worker declares one
worker:<name>         a modelled task, labelled with its current version
input:<worker>        the inbox and its input adapter, where one exists
source:<worker>:<c>   a source collection the model declares
executor:<path>       a fixed engine. SHARED -- one node per engine, never one
                      per worker
effect:<worker>       an output; or committed state where the worker has effect
                      authority
exception:<worker>    a queued exception, only where one exists
capability:investigator   ONE shared node, connected only where there is an
                      exception path
```

IDs are typed from the start so a later version can act on an `executor:` or
`source:` click without renaming anything.

**One executor node, not one per worker.** `acme-timesheets` and
`orders-enrichment` converge on `execute_enrichment.py`, and the picture must
show that: drawing an engine per task would recreate the "100 generated scripts"
misunderstanding the whole architecture exists to avoid.

## Layout is a decision, so it lives here

`physics: false` in the frontend. Columns, left to right: inputs and sources,
then tasks, then outputs and effects. Shared infrastructure sits below the tasks
it serves; the investigator sits apart, reached only by exception edges.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fleet  # noqa: E402
import inbox as inbox_mod  # noqa: E402
import investigation as inv_mod  # noqa: E402

# Node kinds, and the one colour decision per kind.
PALETTE = {
    "scope": "#8C7A5B",
    "worker": "#3E6B89",
    "input": "#6F8F6A",
    "source": "#7FA05C",
    "executor": "#B07C3A",
    "effect": "#5E7C8C",
    "exception": "#B23B2E",
    "capability": "#7A5B8C",
}

# Edge kinds. Three meanings, kept visually distinct.
EDGE_STYLE = {
    "data": {"color": "#7FA05C", "dashes": False, "arrows": "to"},
    "executes": {"color": "#B07C3A", "dashes": False, "arrows": "to"},
    "effect": {"color": "#5E7C8C", "dashes": False, "arrows": "to"},
    "exception": {"color": "#B23B2E", "dashes": True, "arrows": "to"},
}

COL_INPUT = -620
COL_SOURCE = -300
COL_TASK = 60
COL_EFFECT = 460
ROW_HEIGHT = 190
EXECUTOR_DROP = 150
INVESTIGATOR_X = 460


def worker_id(name: str) -> str:
    return f"worker:{name}"


def name_from(node_id: Optional[str]) -> Optional[str]:
    """The worker a clicked node selects, or None. The map's only action in v0."""
    if not node_id or not node_id.startswith("worker:"):
        return None
    return node_id.split(":", 1)[1]


def _node(node_id: str, label: str, kind: str, x: int, y: int, *,
          title: str = "", clickable: bool = False, size: int = 16) -> dict:
    return {"id": node_id, "label": label, "x": x, "y": y, "size": size,
            "shape": "dot", "color": PALETTE[kind], "title": title or label,
            "clickable": clickable, "kind": kind}


def _edge(source: str, target: str, kind: str, label: str = "") -> dict:
    style = EDGE_STYLE[kind]
    return {"from": source, "to": target, "kind": kind, "label": label,
            "color": {"color": style["color"]}, "dashes": style["dashes"],
            "arrows": style["arrows"], "font": {"size": 11, "align": "middle"}}


def build(workers: Optional[list] = None) -> dict:
    """The whole graph, from fleet state. Reads only."""
    workers = sorted(workers if workers is not None else fleet.load_all(),
                     key=lambda w: w.name)
    nodes: list[dict] = []
    edges: list[dict] = []
    executors: dict[str, int] = {}          # engine -> count, for the shared node
    scopes: dict[str, int] = {}
    any_exception = False

    for row, w in enumerate(workers):
        y = row * ROW_HEIGHT
        summary = w.summary()
        wid = worker_id(w.name)

        status = ("exception" if summary["last_status"] == "exception"
                  else "attention" if inv_mod.needs_investigation(w)
                  else summary["last_status"])
        nodes.append(_node(
            wid, f"{w.name}\nv{summary['version']}", "worker", COL_TASK, y,
            title=(f"{w.purpose}\n{w.task} · v{summary['version']} · "
                   f"{summary['runs_this_version']} run(s) on this version · "
                   f"{status}"),
            clickable=True, size=22))

        # --- scope, ONLY where the worker declares one --------------------
        # No worker does today. `customer` is not a field in fleet state and one
        # is deliberately not invented here; adding it to worker.json is the
        # single change that makes customer lanes real.
        scope = w.identity.get("customer") or w.identity.get("scope")
        if scope:
            sid = f"scope:{scope}"
            if sid not in scopes:
                scopes[sid] = y
                nodes.append(_node(sid, scope, "scope", COL_INPUT - 300, y,
                                   size=20))
            edges.append(_edge(sid, wid, "data", "owns"))

        # --- input: inbox and adapter --------------------------------------
        if (w.directory / "ledger.jsonl").is_file():
            box = inbox_mod.summary(w)
            adapter = w.identity.get("input_adapter")
            iid = f"input:{w.name}"
            nodes.append(_node(
                iid, f"inbox\n{adapter or 'json'}", "input", COL_INPUT, y,
                title=(f"{w.trigger}\n{box['processed']} processed · "
                       f"{box['waiting']} waiting · "
                       f"{box['exceptions']} queued exception(s)")))
            edges.append(_edge(iid, wid, "data", adapter or ""))

        # --- source collections the MODEL declares --------------------------
        for index, (name, spec) in enumerate(sorted(
                (w.model.get("sources") or {}).items())):
            sid = f"source:{w.name}:{name}"
            offset = (index - (len(w.model.get("sources") or {}) - 1) / 2) * 62
            nodes.append(_node(sid, name, "source", COL_SOURCE,
                               int(y + offset), size=13,
                               title=f"{spec.get('path')} · {spec.get('collection')}"))
            edges.append(_edge(sid, wid, "data"))

        # --- the SHARED executor -------------------------------------------
        eid = f"executor:{w.engine}"
        executors[eid] = executors.get(eid, 0) + 1
        edges.append(_edge(wid, eid, "executes"))

        # --- output, or committed effect ------------------------------------
        fid = f"effect:{w.name}"
        if w.committing:
            nodes.append(_node(
                fid, f"{w.effect}\ncommitted", "effect", COL_EFFECT, y,
                title=(f"effect authority · {summary['effects_applied']} applied, "
                       f"{summary['effects_failed']} failed")))
            edges.append(_edge(wid, fid, "effect", "applies"))
        else:
            columns = [o.get("target") for o in (w.model.get("outputs") or [])]
            nodes.append(_node(
                fid, "result table", "effect", COL_EFFECT, y, size=13,
                title=" · ".join(str(c) for c in columns) or "result"))
            edges.append(_edge(wid, fid, "data"))

        # --- exception path, only where one exists --------------------------
        queued = (inbox_mod.summary(w)["exceptions"]
                  if (w.directory / "ledger.jsonl").is_file() else 0)
        has_investigation = bool(w.investigation)
        if queued or has_investigation or inv_mod.needs_investigation(w):
            xid = f"exception:{w.name}"
            state = (w.investigation or {}).get("state", "queued")
            nodes.append(_node(
                xid, f"exception\n{state}", "exception", COL_TASK + 190,
                int(y + 95), size=13,
                title=f"{queued} queued · investigation: {state}"))
            edges.append(_edge(wid, xid, "exception"))
            edges.append(_edge(xid, "capability:investigator", "exception"))
            any_exception = True

    # --- shared infrastructure, below the tasks it serves --------------------
    base_y = (len(workers) - 1) * ROW_HEIGHT + EXECUTOR_DROP
    for index, (eid, count) in enumerate(sorted(executors.items())):
        spread = (index - (len(executors) - 1) / 2) * 460
        nodes.append(_node(
            eid, eid.split("/")[-1], "executor", int(COL_TASK + spread),
            base_y, size=20,
            title=(f"{eid.split(':', 1)[1]}\nfixed engine, shared by "
                   f"{count} task(s)")))

    if any_exception:
        nodes.append(_node(
            "capability:investigator", "investigator\n(LLM, on request)",
            "capability", INVESTIGATOR_X, base_y, size=18,
            title=("Woken only by an operator, only on an exception. Never in "
                   "poll() or recover().")))

    return {"nodes": nodes, "edges": edges}


def legend() -> list[tuple[str, str]]:
    return [("data flow", EDGE_STYLE["data"]["color"]),
            ("runs on engine", EDGE_STYLE["executes"]["color"]),
            ("effect authority", EDGE_STYLE["effect"]["color"]),
            ("exception → investigator", EDGE_STYLE["exception"]["color"])]


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    workers = fleet.load_all()
    check(len(workers) >= 3, f"needs the seeded fleet: {len(workers)} worker(s)")

    # --- THE INVARIANT: building writes nothing --------------------------
    root = fleet.ROOT
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    data = build(workers)
    after = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    check(before == after,
          "CANARY: building the map must not write ANYTHING -- a map that "
          "stored anything would be a second description of the system, "
          f"drifting against the one workers run on: "
          f"{[str(p) for p in set(before) ^ set(after)][:3]}")

    ids = [n["id"] for n in data["nodes"]]
    check(len(ids) == len(set(ids)), f"node ids must be unique: {ids}")

    # --- every worker once, at its CURRENT version -----------------------
    for w in workers:
        wid = worker_id(w.name)
        check(ids.count(wid) == 1,
              f"{w.name} must appear exactly once: {ids.count(wid)}")
        node = next(n for n in data["nodes"] if n["id"] == wid)
        check(f"v{w.current_version}" in node["label"],
              f"{w.name} must show its current version: {node['label']!r}")
        check(node["clickable"] is True, f"{w.name} must be clickable")

    # --- the shared executor, which is the point of the picture ----------
    enrichment = [w for w in workers if w.task == "enrichment"]
    check(len(enrichment) >= 2, "the fleet must have >1 enrichment worker")
    targets = {e["to"] for e in data["edges"] if e["kind"] == "executes"
               and e["from"] in {worker_id(w.name) for w in enrichment}}
    check(len(targets) == 1,
          f"CANARY: every enrichment task must converge on ONE engine node, "
          f"not one each: {targets}")
    engine_nodes = [n for n in data["nodes"] if n["kind"] == "executor"]
    check(len(engine_nodes) == len({w.engine for w in workers}),
          f"one node per ENGINE, not per worker: {len(engine_nodes)} nodes for "
          f"{len(workers)} workers")

    # --- effect authority is distinguished from a result table -----------
    committing = [w for w in workers if w.committing]
    check(committing, "the fleet must have a committing worker")
    for w in committing:
        effect_edges = [e for e in data["edges"]
                        if e["from"] == worker_id(w.name) and e["kind"] == "effect"]
        check(len(effect_edges) == 1,
              f"{w.name} commits, so it must have an effect edge: {effect_edges}")
    for w in workers:
        if w.committing:
            continue
        check(not [e for e in data["edges"]
                   if e["from"] == worker_id(w.name) and e["kind"] == "effect"],
              f"CANARY: {w.name} commits nothing and must NOT claim effect "
              f"authority")

    # --- the investigator is ONE shared capability -----------------------
    caps = [n for n in data["nodes"] if n["kind"] == "capability"]
    check(len(caps) <= 1, f"the investigator must be a single node: {caps}")
    if caps:
        into = [e for e in data["edges"] if e["to"] == caps[0]["id"]]
        check(into and all(e["kind"] == "exception" for e in into),
              f"CANARY: the investigator is reachable ONLY by exception edges "
              f"-- never on a run path: {[e['kind'] for e in into]}")

    # --- acme's real investigation shows -------------------------------
    acme = next((w for w in workers if w.name == "acme-timesheets"), None)
    if acme and acme.investigation:
        check(f"exception:{acme.name}" in ids,
              f"acme's investigation relationship must appear: {ids}")

    # --- structural integrity -------------------------------------------
    for edge in data["edges"]:
        check(edge["from"] in ids, f"dangling edge source: {edge}")
        check(edge["to"] in ids, f"dangling edge target: {edge}")
        check(edge["kind"] in EDGE_STYLE, f"unknown edge kind: {edge['kind']}")

    # --- deterministic -----------------------------------------------------
    again = build(workers)
    check(again == data, "CANARY: the layout must be deterministic")
    check(all(isinstance(n["x"], int) and isinstance(n["y"], int)
              for n in data["nodes"]),
          "physics is disabled, so every node needs an explicit position")

    # --- status is DERIVED, never stored -----------------------------------
    for w in workers:
        node = next(n for n in data["nodes"] if n["id"] == worker_id(w.name))
        check(str(w.summary()["runs_this_version"]) in node["title"],
              f"{w.name}'s status must be read from fleet state: {node['title']!r}")

    # --- the click contract -------------------------------------------------
    check(name_from("worker:acme-timesheets") == "acme-timesheets",
          "a worker click must resolve to the existing worker view")
    for other in ("executor:enrichment/harness/execute_enrichment.py",
                  "source:x:y", "capability:investigator", None):
        check(name_from(other) is None,
              f"v1 acts on worker nodes only: {other} -> {name_from(other)}")

    # --- no scope invented --------------------------------------------------
    declared = [w.name for w in workers
                if w.identity.get("customer") or w.identity.get("scope")]
    check([n for n in data["nodes"] if n["kind"] == "scope"] == [] or declared,
          "CANARY: a scope node may only exist where a worker DECLARES one")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED ({len(data['nodes'])} nodes, {len(data['edges'])} "
          f"edges / building writes NOTHING / every worker appears once at its "
          f"current version / every enrichment task converges on ONE engine node "
          f"/ effect authority only where the worker commits / the investigator "
          f"is one node reachable only by exception edges / no dangling edges / "
          f"deterministic layout with explicit positions / status derived from "
          f"fleet state / worker clicks resolve and other kinds do not / no "
          f"scope invented)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
