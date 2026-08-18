#!/usr/bin/env python3
"""Graph data for the Fleet System Map. Pure, Streamlit-free, deterministic.

Same split as `food-prep`'s `ui/graph.py`: every decision lives here with a
self-test, and the view only arranges widgets.

## The map is a VIEW. It is never a source of truth.

Everything is derived from state that already exists and is already
authoritative — `worker.json`, `versions/vN.json`, `history.jsonl`,
`runs.jsonl`, `investigation.json`, `ledger.jsonl`, `fleet.ENGINES`. Nothing
here stores a position, a status or a grouping of its own, and **building the
graph writes nothing at all** — the self-test asserts that by comparing file
mtimes across a build.

A map that remembered where you dragged a node, or which customer a task
belonged to, would immediately be a second unversioned description of the
system, drifting against the one the workers actually run on.

## Lanes are derived, never maintained

A worker declares `customer` (or `scope`) in its own `worker.json`. The map
groups by that field and by nothing else. Adding a customer is a line of worker
metadata, not a UI change; a worker that declares nothing keeps its own unlaned
band, which is what the fleet looked like before customers existed.

**Shared infrastructure sits outside every lane.** Executors and the
investigator serve more than one customer, so drawing them inside a band would
be a lie about who owns them.

## Node types, typed IDs

```text
scope:<name>          a customer or scope, ONLY where a worker declares one
worker:<name>         a modelled task, labelled with its current version
input:<worker>        the inbox and its input adapter, where one exists
source:<worker>:<c>   a source collection the model declares
executor:<path>       a fixed engine. SHARED -- one node per engine, never one
                      per worker, and never inside a lane
effect:<worker>       an output; or committed state where the worker has effect
                      authority
exception:<worker>    a queued exception, only where one exists
capability:investigator   ONE shared node, connected only where there is an
                      exception path
```

## Layout is a decision, so it lives here

`physics: false` in the frontend. Position carries meaning: an executor inside a
customer lane, or the investigator on the normal processing path, should *look*
wrong. A force-directed layout would make that unsayable.
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

PALETTE = {
    "scope": "#8C7A5B", "worker": "#3E6B89", "input": "#6F8F6A",
    "source": "#7FA05C", "executor": "#B07C3A", "effect": "#5E7C8C",
    "exception": "#B23B2E", "capability": "#7A5B8C",
}

EDGE_STYLE = {
    "data": {"color": "#7FA05C", "dashes": False, "arrows": "to"},
    "owns": {"color": "#8C7A5B", "dashes": False, "arrows": ""},
    "executes": {"color": "#B07C3A", "dashes": False, "arrows": "to"},
    "effect": {"color": "#5E7C8C", "dashes": False, "arrows": "to"},
    "exception": {"color": "#B23B2E", "dashes": True, "arrows": "to"},
    # v0.5: a declared destination, not an executed effect. Dashed to read as
    # "intended, not landed" -- distinct from both data flow and effect authority.
    "intended": {"color": "#6A5ACD", "dashes": True, "arrows": "to"},
}

# Derived status. Worst first — a scope inherits the worst state beneath it.
# Nothing is stored: every value is computed on each build, so the map cannot
# disagree with the console about whether something is broken.
STATUS_ORDER = ("attention", "blocked", "never_run", "healthy")
STATUS_GLYPH = {"attention": "!", "blocked": "?", "never_run": "o",
                "healthy": "+"}
STATUS_COLOUR = {"attention": "#B23B2E", "blocked": "#C58A22",
                 "never_run": "#8A8A82", "healthy": "#4C8C5A"}

COL_SCOPE = -940
COL_INPUT = -620
COL_SOURCE = -300
COL_TASK = 60
COL_EFFECT = 460
ROW_HEIGHT = 190
BAND_GAP = 90
SHARED_DROP = 220


def worker_id(name: str) -> str:
    return f"worker:{name}"


def name_from(node_id: Optional[str]) -> Optional[str]:
    """The worker a clicked node selects, or None. The map's only action in v0.

    Kept for fleet/app.py. The supervisor uses parse_selection instead.
    """
    if not node_id or not node_id.startswith("worker:"):
        return None
    return node_id.split(":", 1)[1]


# The typed prefixes a node id may carry. Order matters only for readability;
# dispatch is by exact prefix, and source/destination carry trailing segments.
_SELECTION_PREFIXES = ("worker", "input", "scope", "source", "destination")


def parse_selection(node_id: Optional[str]) -> Optional[dict]:
    """A typed selection from a clicked node id, or None.

    The map's only action is to report the clicked id; Python interprets it.
    `name_from` is unchanged for fleet/app.py. This parser is the v0.5 contract:

        worker:W            -> {"kind": "worker", "worker": W}
        input:W             -> {"kind": "inbox",  "worker": W}
        scope:X             -> {"kind": "company", "company": X}
        source:W:C          -> {"kind": "source", "worker": W, "source": C}
        destination:<key>   -> {"kind": "destination", "key": <full node id>}
        anything else       -> None

    A destination id encodes a system[/area][/object] but the second segment is
    ambiguous (it may be area or object -- "Finance/Reskontra" vs
    "Catalog/Items"), so we do not split it here. The detail panel resolves the
    full declaration by matching destination_key() against the workers.

    Names containing ":" would break source splitting; no seeded name does, so
    the constraint is documented rather than enforced.
    """
    if not node_id or not isinstance(node_id, str):
        return None
    prefix, _, rest = node_id.partition(":")
    if prefix not in _SELECTION_PREFIXES or not rest:
        return None
    if prefix == "worker":
        return {"kind": "worker", "worker": rest}
    if prefix == "input":
        return {"kind": "inbox", "worker": rest}
    if prefix == "scope":
        return {"kind": "company", "company": rest}
    if prefix == "source":
        w, _, coll = rest.partition(":")
        if not coll:
            return None
        return {"kind": "source", "worker": w, "source": coll}
    # destination:<key> -- the panel matches destination_key() on the workers.
    return {"kind": "destination", "key": node_id}


def destination_key(dest: dict) -> str:
    """The deterministic node id for a destination declaration.

    Identical declarations converge on the same node; we never unify by label
    similarity, only by an exact declared identity.
    """
    parts = [dest.get("system"), dest.get("area"), dest.get("object")]
    return ":".join(["destination"] + [p for p in parts if p])


def scope_of(w) -> Optional[str]:
    """The customer or scope a worker DECLARES. Never inferred from a name."""
    return w.identity.get("customer") or w.identity.get("scope") or None


def status_of(w) -> str:
    """Derived, from state the console already reads. No new state anywhere.

    ```text
    attention   something failed and nobody has looked
    blocked     an investigation is open, waiting on a person
    never_run   established but not yet run on this version
    healthy     the last run on this version completed
    ```
    """
    if inv_mod.needs_investigation(w):
        return "attention"
    if (w.investigation or {}).get("state") in ("open", "proposed"):
        return "blocked"
    summary = w.summary()
    if summary["runs_this_version"] == 0:
        return "never_run"
    return "healthy" if summary["last_status"] == "ok" else "attention"


def worst(statuses) -> str:
    for candidate in STATUS_ORDER:
        if candidate in statuses:
            return candidate
    return "healthy"


def lanes(workers: list) -> list:
    """Workers grouped into scope bands, deterministically. Derived only."""
    bands: dict = {}
    for w in workers:
        bands.setdefault(scope_of(w), []).append(w)
    return [(scope, sorted(group, key=lambda w: w.name))
            for scope, group in sorted(
                bands.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))]


def _node(node_id: str, label: str, kind: str, x: int, y: int, *,
          title: str = "", clickable: bool = False, size: int = 16,
          status: str = "") -> dict:
    """A node. `status` colours the BORDER, never the fill.

    Kind stays legible by fill, so a lane full of red borders reads as "several
    tasks here need someone" without the node types becoming indistinguishable.
    """
    colour = ({"background": PALETTE[kind], "border": STATUS_COLOUR[status]}
              if status else PALETTE[kind])
    node = {"id": node_id, "label": label, "x": int(x), "y": int(y),
            "size": size, "shape": "dot", "color": colour,
            "title": title or label, "clickable": clickable, "kind": kind}
    if status:
        node["status"] = status
        node["borderWidth"] = 2 if status == "healthy" else 5
        node["label"] = f"{STATUS_GLYPH[status]} {label}"
    return node


def _edge(source: str, target: str, kind: str, label: str = "") -> dict:
    style = EDGE_STYLE[kind]
    return {"from": source, "to": target, "kind": kind, "label": label,
            "color": {"color": style["color"]}, "dashes": style["dashes"],
            "arrows": style["arrows"], "font": {"size": 11, "align": "middle"}}


def _emit_worker(w, y: int, nodes: list, edges: list, executors: dict) -> bool:
    """One task and everything it owns. Returns whether it has an exception."""
    summary = w.summary()
    wid = worker_id(w.name)
    status = status_of(w)

    nodes.append(_node(
        wid, f"{w.name}\nv{summary['version']}", "worker", COL_TASK, y,
        title=(f"{w.purpose}\n{w.task} · v{summary['version']} · "
               f"{summary['runs_this_version']} run(s) on this version · "
               f"{status}"),
        clickable=True, size=22, status=status))

    has_ledger = (w.directory / "ledger.jsonl").is_file()
    if has_ledger:
        box = inbox_mod.summary(w)
        adapter = w.identity.get("input_adapter")
        iid = f"input:{w.name}"
        nodes.append(_node(
            iid, f"inbox\n{adapter or 'json'}", "input", COL_INPUT, y,
            title=(f"{w.trigger}\n{box['processed']} processed · "
                   f"{box['waiting']} waiting · "
                   f"{box['exceptions']} queued exception(s)"),
            clickable=True))
        edges.append(_edge(iid, wid, "data", adapter or ""))

    sources = sorted((w.model.get("sources") or {}).items())
    for index, (name, spec) in enumerate(sources):
        sid = f"source:{w.name}:{name}"
        offset = (index - (len(sources) - 1) / 2) * 62
        nodes.append(_node(sid, name, "source", COL_SOURCE, y + offset, size=13,
                           title=f"{spec.get('path')} · {spec.get('collection')}",
                           clickable=True))
        edges.append(_edge(sid, wid, "data"))

    eid = f"executor:{w.engine}"
    executors[eid] = executors.get(eid, 0) + 1
    edges.append(_edge(wid, eid, "executes"))

    fid = f"effect:{w.name}"
    if w.committing:
        nodes.append(_node(
            fid, f"{w.effect}\ncommitted", "effect", COL_EFFECT, y,
            title=(f"effect authority · {summary['effects_applied']} applied, "
                   f"{summary['effects_failed']} failed")))
        edges.append(_edge(wid, fid, "effect", "applies"))
    elif w.destination:
        # v0.5: a declared destination, not an executed effect. The node id is
        # deterministic so identical declarations converge; we never unify by
        # label similarity. Distinct from the committing effect node above --
        # this is an INTENT, and the detail panel says so (authority: none).
        dest = w.destination
        did = destination_key(dest)
        label = "\n".join(v for v in (dest.get("system"), dest.get("area"))
                          if v)
        mode = (w.delivery or {}).get("mode", "")
        title = f"declared destination · delivery: {mode or 'unspecified'}"
        nodes.append(_node(did, label or "destination", "effect", COL_EFFECT, y,
                           clickable=True, size=15, title=title))
        edges.append(_edge(wid, did, "intended", mode))
    else:
        columns = [o.get("target") for o in (w.model.get("outputs") or [])]
        nodes.append(_node(fid, "result table", "effect", COL_EFFECT, y, size=13,
                           title=" · ".join(str(c) for c in columns) or "result"))
        edges.append(_edge(wid, fid, "data"))

    queued = inbox_mod.summary(w)["exceptions"] if has_ledger else 0
    if queued or w.investigation or inv_mod.needs_investigation(w):
        xid = f"exception:{w.name}"
        state = (w.investigation or {}).get("state", "queued")
        nodes.append(_node(
            xid, f"exception\n{state}", "exception", COL_TASK + 190, y + 95,
            size=13, title=f"{queued} queued · investigation: {state}"))
        edges.append(_edge(wid, xid, "exception"))
        edges.append(_edge(xid, "capability:investigator", "exception"))
        return True
    return False


def build(workers: Optional[list] = None) -> dict:
    """The whole graph, from fleet state. Reads only."""
    workers = sorted(workers if workers is not None else fleet.load_all(),
                     key=lambda w: w.name)
    nodes: list[dict] = []
    edges: list[dict] = []
    executors: dict[str, int] = {}
    any_exception = False
    y = 0

    for scope, group in lanes(workers):
        top = y
        for w in group:
            any_exception |= _emit_worker(w, y, nodes, edges, executors)
            y += ROW_HEIGHT
        if scope:
            # The lane label carries the WORST status beneath it, so an
            # exception under one customer is visible without opening anything
            # -- and is visibly theirs, not the fleet's.
            nodes.append(_node(
                f"scope:{scope}", scope, "scope", COL_SCOPE,
                (top + y - ROW_HEIGHT) / 2, size=26,
                status=worst([status_of(w) for w in group]),
                title=(f"{scope} — {len(group)} task(s) · worst state "
                       f"{worst([status_of(w) for w in group])}"),
                clickable=True))
            for w in group:
                edges.append(_edge(f"scope:{scope}", worker_id(w.name), "owns"))
        y += BAND_GAP

    # --- shared infrastructure, OUTSIDE every lane --------------------------
    base_y = y - BAND_GAP + SHARED_DROP
    for index, (eid, count) in enumerate(sorted(executors.items())):
        spread = (index - (len(executors) - 1) / 2) * 460
        nodes.append(_node(eid, eid.split("/")[-1], "executor",
                           COL_TASK + spread, base_y, size=20,
                           title=(f"{eid.split(':', 1)[1]}\nfixed engine, "
                                  f"shared by {count} task(s) across "
                                  f"{len(lanes(workers))} scope(s)")))
    if any_exception:
        nodes.append(_node(
            "capability:investigator", "investigator\n(LLM, on request)",
            "capability", COL_EFFECT + 260, base_y, size=18,
            title=("Woken only by an operator, only on an exception. Never in "
                   "poll() or recover(). Shared by every scope.")))

    return {"nodes": nodes, "edges": edges}


def legend() -> list[tuple[str, str]]:
    return [("data flow", EDGE_STYLE["data"]["color"]),
            ("customer owns", EDGE_STYLE["owns"]["color"]),
            ("runs on engine", EDGE_STYLE["executes"]["color"]),
            ("effect authority", EDGE_STYLE["effect"]["color"]),
            ("exception → investigator", EDGE_STYLE["exception"]["color"])]


def status_legend() -> list[tuple[str, str, str]]:
    return [(STATUS_GLYPH[s], s.replace("_", " "), STATUS_COLOUR[s])
            for s in STATUS_ORDER]


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    workers = fleet.load_all()
    check(len(workers) >= 4, f"needs the seeded fleet: {len(workers)}")

    # --- building writes NOTHING -------------------------------------------
    root = fleet.ROOT
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    data = build(workers)
    after = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    check(before == after,
          "CANARY: building the map must not write ANYTHING -- a stored "
          "position, status or grouping would be a second description of the "
          "system")

    ids = [n["id"] for n in data["nodes"]]
    by_id = {n["id"]: n for n in data["nodes"]}
    check(len(ids) == len(set(ids)), "node ids must be unique")

    # --- TWO REAL SCOPES, derived from worker metadata ---------------------
    scopes = sorted(s for s, _ in lanes(workers) if s)
    check(len(scopes) >= 2, f"the fleet must have two real scopes: {scopes}")
    for scope in scopes:
        check(f"scope:{scope}" in ids, f"{scope} must have a lane node")
    declared = {w.name: scope_of(w) for w in workers}
    check(all(declared.values()),
          f"every worker must DECLARE its scope: {declared}")

    # --- lanes are derived, and workers sit only in their own band ---------
    for scope, group in lanes(workers):
        if not scope:
            continue
        owned = {e["to"] for e in data["edges"]
                 if e["from"] == f"scope:{scope}" and e["kind"] == "owns"}
        check(owned == {worker_id(w.name) for w in group},
              f"{scope} must own exactly its declared workers: {owned}")
        ys = [by_id[worker_id(w.name)]["y"] for w in group]
        other = [by_id[worker_id(w.name)]["y"] for w in workers
                 if scope_of(w) != scope]
        check(not (set(ys) & set(other)),
              f"CANARY: {scope}'s band must not overlap another scope's rows")

    # --- ISOLATION: state, inbox and history are per worker ----------------
    acme = [w for w in workers if scope_of(w) == "Acme Oy"]
    fazerish = [w for w in workers if scope_of(w) == "Fazerish Oy"]
    check(acme and fazerish, "both scopes must have workers")
    dirs = {w.name: w.directory.resolve() for w in workers}
    check(len(set(dirs.values())) == len(dirs), "worker directories are distinct")
    for w in fazerish:
        for other in acme:
            check(not str(w.base.resolve()).startswith(str(other.base.resolve())),
                  f"CANARY: {w.name}'s state must not live under {other.name}'s")
    acme_items = {e["item_id"] for w in acme
                  if (w.directory / "ledger.jsonl").is_file()
                  for e in inbox_mod.ledger(w)}
    faz_items = {e["item_id"] for w in fazerish
                 if (w.directory / "ledger.jsonl").is_file()
                 for e in inbox_mod.ledger(w)}
    check(faz_items and not (acme_items & faz_items),
          "CANARY: work-item ledgers must not be shared across customers")

    # --- SHARED: one engine node across BOTH scopes ------------------------
    enrichment = [w for w in workers if w.task == "enrichment"]
    check({scope_of(w) for w in enrichment} >= {"Acme Oy", "Fazerish Oy"},
          "both scopes must have an enrichment task, or sharing is untested")
    targets = {e["to"] for e in data["edges"] if e["kind"] == "executes"
               and e["from"] in {worker_id(w.name) for w in enrichment}}
    check(len(targets) == 1,
          f"CANARY: tasks in DIFFERENT customers must converge on ONE engine "
          f"node: {targets}")
    engine_node = by_id[next(iter(targets))]
    check(engine_node["x"] < COL_SCOPE or engine_node["y"] > max(
        by_id[worker_id(w.name)]["y"] for w in workers),
        f"CANARY: a shared engine must sit OUTSIDE every lane, below the bands: "
        f"{engine_node['x']},{engine_node['y']}")

    # --- the investigator is one shared capability -------------------------
    caps = [n for n in data["nodes"] if n["kind"] == "capability"]
    check(len(caps) <= 1, f"the investigator must be a single node: {caps}")
    if caps:
        into = [e for e in data["edges"] if e["to"] == caps[0]["id"]]
        check(into and all(e["kind"] == "exception" for e in into),
              "CANARY: the investigator is reachable ONLY by exception edges")

    # --- STATUS is derived, and an exception is LOCAL to its customer -------
    for w in workers:
        node = by_id[worker_id(w.name)]
        check(node.get("status") == status_of(w),
              f"{w.name}'s status must be derived: {node.get('status')}")
        check(node["label"].startswith(STATUS_GLYPH[status_of(w)]),
              f"{w.name} must carry its status glyph: {node['label']!r}")

    troubled = [w for w in workers if status_of(w) != "healthy"]
    check(troubled, "the fleet must have a non-healthy worker to localise")
    hurt_scopes = {scope_of(w) for w in troubled}
    check(len(hurt_scopes) == 1,
          f"the exception should sit under ONE customer: {hurt_scopes}")
    hurt = hurt_scopes.pop()
    for scope in scopes:
        node = by_id[f"scope:{scope}"]
        expected = worst([status_of(w) for w in workers if scope_of(w) == scope])
        check(node["status"] == expected,
              f"{scope} must inherit the worst state beneath it: "
              f"{node['status']} != {expected}")
    check(by_id[f"scope:{hurt}"]["status"] != "healthy",
          f"CANARY: {hurt} carries the exception")
    clean = [s for s in scopes if s != hurt]
    for scope in clean:
        check(by_id[f"scope:{scope}"]["status"] == "healthy",
              f"CANARY: {scope} must stay healthy -- an exception under one "
              f"customer must NOT colour another")

    # --- structural integrity, determinism, click contract ------------------
    for edge in data["edges"]:
        check(edge["from"] in ids, f"dangling edge source: {edge}")
        check(edge["to"] in ids, f"dangling edge target: {edge}")
        check(edge["kind"] in EDGE_STYLE, f"unknown edge kind: {edge['kind']}")
    check(build(workers) == data, "CANARY: the layout must be deterministic")
    check(all(isinstance(n["x"], int) and isinstance(n["y"], int)
              for n in data["nodes"]), "every node needs an explicit position")
    check(name_from("worker:acme-timesheets") == "acme-timesheets",
          "a worker click must resolve to the existing worker view")
    for other in ("scope:Acme Oy", "executor:x", "source:x:y", None):
        check(name_from(other) is None, f"v1 acts on worker nodes only: {other}")

    # --- v0.5 typed selection contract ------------------------------------
    check(parse_selection("worker:acme-timesheets") ==
          {"kind": "worker", "worker": "acme-timesheets"},
          "worker: parses to a worker selection")
    check(parse_selection("input:fazerish-invoicing") ==
          {"kind": "inbox", "worker": "fazerish-invoicing"},
          "input: parses to an inbox selection")
    check(parse_selection("scope:Acme Oy") ==
          {"kind": "company", "company": "Acme Oy"},
          "scope: parses to a company selection")
    check(parse_selection("source:acme-august-recon:statement") ==
          {"kind": "source", "worker": "acme-august-recon", "source": "statement"},
          "source:W:C parses to a source selection")
    check(parse_selection("destination:finance") ==
          {"kind": "destination", "key": "destination:finance"},
          "destination: parses to a keyed selection")
    check(parse_selection("destination:finance:reskontra") ==
          {"kind": "destination", "key": "destination:finance:reskontra"},
          "destination:S:A keeps the full key")
    check(destination_key({"system": "finance", "area": "reskontra"}) ==
          "destination:finance:reskontra",
          "destination_key joins non-empty parts")
    check(destination_key({"system": "catalog", "object": "items"}) ==
          "destination:catalog:items",
          "destination_key omits empty middle parts")
    for other in ("executor:x", "capability:investigator", "exception:w",
                  "", "worker:", "source:nocoll", None, 123):
        check(parse_selection(other) is None,
              f"non-selectable ids parse to None: {other!r}")
    # the seeded scope/input/source nodes are now clickable
    for scope in scopes:
        check(by_id[f"scope:{scope}"]["clickable"] is True,
              f"{scope} scope node must be clickable")
    check(by_id["input:fazerish-invoicing"]["clickable"] is True,
          "inbox nodes must be clickable")
    check(by_id["source:acme-august-recon:statement"]["clickable"] is True,
          "source nodes must be clickable")

    # --- v0.5 destination vs effect authority (acceptance C/D/E) ------------
    # E: a committing worker keeps its real effect node, never a destination.
    res = next((w for w in workers if w.committing), None)
    check(res is not None, "the fleet must have a committing worker (reservation)")
    res_data = build([res])
    res_ids = [n["id"] for n in res_data["nodes"]]
    check(f"effect:{res.name}" in res_ids,
          f"CANARY E: {res.name} must keep its effect node (real authority)")
    res_label = next(n["label"] for n in res_data["nodes"]
                     if n["id"] == f"effect:{res.name}")
    check("committed" in res_label,
          f"CANARY E: {res.name}'s effect node must say 'committed'")
    check(not any(i.startswith("destination:") for i in res_ids),
          f"CANARY E: {res.name} must NOT get a destination node")
    check(any(e["kind"] == "effect" for e in res_data["edges"]),
          f"CANARY E: {res.name} keeps an 'effect' edge")

    # C/D: a noncommitting worker with a declared destination renders a
    # destination node (not 'result table') and an 'intended' edge -- even when
    # delivery is 'automatic', which must NOT read as effect authority.
    base = next((w for w in workers if not w.committing
                 and w.task == "reconciliation"), None)
    check(base is not None, "the fleet must have a reconciliation worker")
    fake = fleet.Worker(
        directory=base.directory,
        identity={**base.identity,
                  "destination": {"system": "catalog", "object": "items"},
                  "delivery": {"mode": "automatic"}},
        versions=base.versions, history=base.history,
        runs=base.runs, investigation=base.investigation)
    fdata = build([fake])
    fids = [n["id"] for n in fdata["nodes"]]
    check("destination:catalog:items" in fids,
          "CANARY C: a declared destination must produce a destination node")
    check(f"effect:{fake.name}" not in fids,
          "CANARY C: a noncommitting worker with a destination must NOT keep "
          "a 'result table' effect node")
    dest_node = next(n for n in fdata["nodes"]
                     if n["id"] == "destination:catalog:items")
    check(dest_node["clickable"] is True,
          "destination nodes must be clickable")
    intended = [e for e in fdata["edges"] if e["kind"] == "intended"]
    check(len(intended) == 1 and intended[0]["to"] == "destination:catalog:items",
          "CANARY D: a declared destination connects via an 'intended' edge")
    check(intended[0]["label"] == "automatic",
          "the intended edge carries the declared delivery mode")
    # delivery=automatic must NOT manufacture committing/effect authority
    check(fake.committing is False,
          "CANARY D: delivery=automatic must NOT make a worker committing")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED ({len(data['nodes'])} nodes, {len(data['edges'])} "
          f"edges, {len(scopes)} scopes / building writes NOTHING / lanes are "
          f"DERIVED from declared worker metadata and bands never overlap / "
          f"customer state, inboxes and ledgers are isolated / tasks in "
          f"different customers converge on ONE engine node placed outside "
          f"every lane / the investigator is one shared node on exception edges "
          f"only / status is derived and glyphed, a scope inherits the worst "
          f"state beneath it, and an exception under one customer leaves the "
          f"other healthy / deterministic, no dangling edges, click contract "
          f"holds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
