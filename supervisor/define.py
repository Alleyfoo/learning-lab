#!/usr/bin/env python3
"""Workspace v0.3 -- the thinnest callable interface from the supervisor to the
EXISTING modeller floor + fleet establishment.

This module does NOT reimplement observation, interpretation, proposal, preview,
or establishment. It calls `modeller/pipeline.py` + `modeller/builder.py` (the
same functions `modeller/app.py` and `modeller/journey.py` call) and
`fleet.establish` (the same function `fleet/seed.py` calls). The supervisor UI
drives these stages one at a time so the human stays in the loop:

    select incoming data -> observe (program) -> describe the job ->
    interpret (LLM) -> propose a task model (LLM) -> [answer a load-bearing
    question if asked] -> deterministic preview -> EXPLICIT Establish ->
    the new worker appears on the System Map.

Evidence boundaries are the modeller's, unchanged: OBSERVED is program-only;
INFERRED/UNKNOWN come only from the LLM through the boundary; CONFIRMED only
from a human answer (`pipeline.submit_answer`). Sufficiency gates
(`check_join_supported` / the task's own validator inside `pipeline.build`) run
before any worker is established. Establishment is an explicit human action --
this module never calls `fleet.establish` on its own; the UI calls it only when
the operator clicks "Establish worker".

The one modeller adaptation: `modeller/app.py` calls `pipeline.propose(...)`
without `task=`, so it always models as enrichment. Here the operator-chosen task
family is threaded into `propose(..., task=...)`, so reconciliation / aggregation
/ reservation models can be produced. `modeller/app.py` itself is NOT touched.

## What this module is NOT

Not a second modeller, not a new task language, not a UI. It is glue: the
smallest set of callable wrappers over machinery that already exists and is
self-tested elsewhere. The LLM `ask` is a local copy of the generate-form call
`modeller/journey.py` and `modeller/app.py` already duplicate -- factoring a
shared one would touch `modeller/` and `fleet/`, out of scope for v0.3.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
# `import fleet` resolves to fleet/fleet.py (no fleet/__init__.py; LAB/fleet on
# path). `import pipeline`/`builder` resolve via LAB/modeller (pipeline itself
# installs inspector + boundary + builder's task harness paths). `import
# incoming` is the supervisor's read-only scanner (used only by the self-test's
# linkage check).
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "modeller"))
sys.path.insert(0, str(LAB / "fleet"))

import fleet      # noqa: E402  (fleet/fleet.py: establish, load, load_all, ROOT)
import pipeline   # noqa: E402  (modeller/pipeline.py: the staged journey)
import incoming   # noqa: E402  (supervisor/incoming.py: scan -- self-test only)

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"
REQUEST_TIMEOUT = 900


# ---------------------------------------------------------------------------
# the LLM call -- generate form, same as modeller/journey.py:28-34
# ---------------------------------------------------------------------------

def ask(prompt: str) -> str:
    """One round-trip to local Ollama (generate form). Returns the response text.

    The supervisor's own `core._chat` uses the chat protocol and is not
    interchangeable: the modeller pipeline hands `interpret`/`propose` a single
    prompt string and expects a single response string. This is therefore a
    local copy of the call `modeller/journey.py` and `modeller/app.py` already
    hold; factoring a shared `ask` would touch `modeller/`+`fleet/` and is out of
    scope for v0.3.
    """
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read())["response"]


# ---------------------------------------------------------------------------
# 1. data -- resolve a selected incoming-data dir into a modeller Workspace
# ---------------------------------------------------------------------------

def workspace_for(data_dir: str) -> Optional[pipeline.Workspace]:
    """The modeller Workspace for a `data/<dir>/` name, or None if not reachable.

    `pipeline.workspaces()` already lists every `data/<dir>/` as a Workspace,
    so selecting an incoming-data dir IS selecting a workspace -- no new loader.
    """
    for ws in pipeline.workspaces():
        if ws.label == data_dir:
            return ws
    return None


def chosen_sources(ws: pipeline.Workspace) -> list[pipeline.SourceFile]:
    """All JSON collections in the workspace. The modeller needs >=2 to relate."""
    return pipeline.sources_in(ws)


def observed(ws: pipeline.Workspace, chosen: list[pipeline.SourceFile]) -> list[dict]:
    """Measured OBSERVED facts for the selected sources (program-only)."""
    return pipeline.observed_facts(ws, chosen)


def relationships(observed_facts: list[dict]) -> list[dict]:
    return pipeline.relationships(observed_facts)


def source_spec(ws: pipeline.Workspace, chosen: list[pipeline.SourceFile]) -> dict:
    """The `sources` dict that becomes the model's source bindings."""
    return pipeline.source_spec(ws, chosen)


def expressible_tasks(chosen: list[pipeline.SourceFile]) -> tuple[str, ...]:
    """Task shapes the selected sources could support. Eliminating, not choosing.

    For >=2 collections: (enrichment, reconciliation, reservation). Structure
    cannot pick among these -- purpose does -- so the operator chooses.
    """
    return pipeline.expressible(chosen)


def suggest_task(goal: str, chosen: list[pipeline.SourceFile],
                 ask_fn=ask) -> tuple[Optional[str], Optional[dict]]:
    """The LLM task-shape choice (`pipeline.choose_task`), as a default suggestion.

    Returns (task, None) when the LLM settles the shape, or (None, question) when
    it cannot. Available for the UI to offer as a suggestion; v0.3 defaults to
    the expressible set and lets the operator pick (the LLM task-choice is a
    later slice). Thin wrapper -- not wired into the v0.3 UI by default.
    """
    return pipeline.choose_task(goal, expressible_tasks(chosen), ask_fn)


# ---------------------------------------------------------------------------
# 2-3. interpret (LLM) + propose (LLM) -- the one adaptation threads `task`
# ---------------------------------------------------------------------------

def interpret(observed_facts: list[dict], goal: str, ask_fn=ask) -> tuple[list[dict], dict]:
    """LLM inspection: INFERRED/UNKNOWN claims + the boundary ingest dict."""
    return pipeline.interpret(observed_facts, goal, ask_fn)


def propose(report: list[dict], goal: str, sources: dict, observed_facts: list[dict],
            task: str, ask_fn=ask, resumed: bool = False) -> tuple[Optional[dict], list, list]:
    """LLM task definition + triage, threading the operator-chosen `task`.

    This is the one modeller adaptation: `modeller/app.py` calls
    `pipeline.propose(...)` without `task=`, so it always models as enrichment.
    Here the chosen task family is passed through, so reconciliation /
    aggregation / reservation models can be produced from the same machinery.
    Returns (model, asked, deferred) exactly as `pipeline.propose` does.
    """
    return pipeline.propose(report, goal, sources, observed_facts, ask_fn,
                            resumed=resumed, task=task)


# ---------------------------------------------------------------------------
# 4. missing truth -- a load-bearing question the program cannot settle
# ---------------------------------------------------------------------------

def questions(asked: list, observed_facts: list[dict]) -> list:
    """Question objects for the asked block, carrying their obligation ids."""
    return pipeline.questions_from([e for e, _ in asked], observed_facts)


def build_answer(q, choice) -> str:
    """Assemble the human answer string from a UI choice, mirroring
    modeller/app.py:206-207. A join question (q.options) becomes
    `<source>.<field> matches <choice>`; a free-text question passes through."""
    if q.options:
        src = q.source[0] if isinstance(q.source, list) else q.source
        return f"{src}.{q.field} matches {choice}"
    return choice


def apply_answer(report: list[dict], q, answer: str) -> list[dict]:
    """Apply a human answer -> CONFIRMED claims (carries the obligation id back)."""
    return pipeline.submit_answer(report, q, answer)


# ---------------------------------------------------------------------------
# 5. deterministic preview + sufficiency gate
# ---------------------------------------------------------------------------

def check_join(model: dict, observed_facts: list[dict],
               report: Optional[list[dict]] = None) -> Optional[str]:
    """The program's own sufficiency check on the declared join (enrichment-
    oriented). None = OK, str = complaint. For reconciliation the authoritative
    validity gate is `preview` ok (the task's own validator via
    `builder.validate_raw`, run inside `pipeline.build`); this result is shown
    but is not the sole gate."""
    return pipeline.check_join_supported(model, observed_facts, report)


def preview(ws: pipeline.Workspace, model: dict):
    """Validate (the task's own validator) and run deterministically."""
    model = dict(model)
    model.setdefault("task", "enrichment")  # pipeline.build reads model["task"]
    return pipeline.build(ws, model)


# ---------------------------------------------------------------------------
# presentation -- the readable model. pipeline.readable is enrichment-only and
# fleet.fleet.readable covers enrichment/reservation; neither renders
# reconciliation, so render the key fields directly (presentation, not logic).
# ---------------------------------------------------------------------------

def render_model(model: dict, task: str) -> list[str]:
    """The proposed task in sentences for a person who will not read JSON."""
    if task == "enrichment":
        return pipeline.readable(model)
    lines: list[str] = []
    srcs = model.get("sources") or {}
    lines.append("Read " + " and ".join(
        f"**{name}** (`{spec.get('collection')}`)" for name, spec in srcs.items()) + ".")
    if task == "reconciliation":
        m = model.get("match_on") or {}
        lines.append(f"Match **{model.get('left')}**.`{m.get('left_field')}` against "
                     f"**{model.get('right')}**.`{m.get('right_field')}`.")
        for c in model.get("compare") or []:
            how = c.get("comparison", "")
            extra = f" within {c['tolerance']}" if how == "within" else ""
            lines.append(f"Compare `{c.get('field')}` ({how}{extra}).")
        cls = model.get("classify") or {}
        if cls:
            lines.append("Classify each key as " + " / ".join(
                f"{rel}={label}" for rel, label in cls.items()) + ".")
    elif task == "aggregation":
        lines.append(f"Group **{model.get('driving_source')}** and aggregate "
                     f"(see the model JSON for the grouped outputs).")
    else:
        lines.append(f"(readable rendering for {task} is task-specific; see "
                      f"the model JSON.)")
    return lines


# ---------------------------------------------------------------------------
# 6. establishment -- the explicit human action. Wraps fleet.establish.
# ---------------------------------------------------------------------------

def establish(name: str, purpose: str, task: str, base: str, model: dict,
              trigger: str, customer: Optional[str] = None,
              root: Optional[Path] = None):
    """Establish a worker in the live fleet (or `root`). Writes exactly three
    files: worker.json, versions/v1.json, history.jsonl (see fleet.fleet.establish).

    `customer`, if given, is written into worker.json post-establish (the existing
    field the other workers carry; `fleet.establish`'s signature is fixed and not
    extended). Without it the worker renders in an unscoped map band
    (`system_map.lanes` handles None) -- not a Company entity.

    `model.setdefault("task", task)` defends against a definer that omits the task
    field; the executor reads `model["task"]` via `pipeline.build`.
    """
    root = root or fleet.ROOT
    model = dict(model)
    model.setdefault("task", task)
    w = fleet.establish(root, name, purpose, task, base, model, trigger=trigger)
    if customer:
        wp = w.directory / "worker.json"
        ident = json.loads(wp.read_text(encoding="utf-8"))
        ident["customer"] = customer
        wp.write_text(json.dumps(ident, indent=2) + "\n", encoding="utf-8")
        w = fleet.load(w.directory)  # reload so identity carries customer
    return w


def establish_workspace(ws: pipeline.Workspace, name: str, purpose: str, task: str,
                        model: dict, customer: Optional[str] = None,
                        root: Optional[Path] = None):
    """Establish from a Workspace, computing `base` and `trigger` from it.

    `base` is the lab-root-relative dir the model's source paths resolve against
    (= `data/` for `data/<dir>/` workspaces). `trigger` is the source data dir
    (`data/<dir>/`) -- this is what makes `incoming._link_worker` link the data
    dir to the new worker STRUCTURALLY via trigger-path containment, for free
    (the source-path provenance the incoming browser needs, without a new field).
    """
    base = str(ws.base.relative_to(LAB))
    trigger = f"{base}/{ws.rel}/"
    return establish(name, purpose, task, base, model, trigger,
                     customer=customer, root=root)


# ---------------------------------------------------------------------------
# self-test -- deterministic spine, no LLM, no real fleet. The LLM stages
# (interpret/propose) are proven by the real acceptance run, not here.
# ---------------------------------------------------------------------------

# A valid reconciliation model over the real kesko data: match Invoice (ledger)
# against "Their ref" (statement), compare Amount within 0.01. The amounts are
# numeric strings, so on_non_numeric is required (the within comparison is
# numeric) but never fires. Keys are text, which is fine -- the policy governs
# the compared OPERAND, not the match key.
_KESKO_MODEL = {
    "model_version": 1,
    "model_id": "kesko-reconciliation-selftest",
    "task": "reconciliation",
    "sources": {
        "purchase_ledger": {"path": "kesko-reconciliation/purchase_ledger.json",
                            "collection": "purchase_ledger"},
        "supplier_statement": {"path": "kesko-reconciliation/supplier_statement.json",
                               "collection": "supplier_statement"},
    },
    "left": "purchase_ledger",
    "right": "supplier_statement",
    "match_on": {"left_field": "Invoice", "right_field": "Their ref"},
    "compare": [{"field": "Amount", "comparison": "within", "tolerance": "0.01"}],
    "on_non_numeric": "refuse_run",
    "classify": {"both_same": "SAME", "both_different": "DIFFERENT",
                 "only_left": "ONLY_LEDGER", "only_right": "ONLY_STATEMENT"},
    "output_order": "left_then_right",
    "on_duplicate_key": "refuse_run",
}


def _self_test() -> int:
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- 1. workspace resolution + observation (no LLM) ---------------------
    ws = workspace_for("kesko-reconciliation")
    check(ws is not None, "workspace_for finds kesko-reconciliation (it is a data/ dir)")
    if ws is None:
        sys.stderr.write("SELF-TEST FAILED: kesko-reconciliation not reachable; "
                         "is data/kesko-reconciliation present?\n")
        return 1

    chosen = chosen_sources(ws)
    check(len(chosen) == 2, f"kesko has 2 collections to relate: {len(chosen)}")
    names = {c.collection for c in chosen}
    check(names == {"purchase_ledger", "supplier_statement"},
          f"collections are purchase_ledger + supplier_statement: {names}")

    obs = observed(ws, chosen)
    check(bool(obs), "observation produced OBSERVED facts")
    check(all(c["status"] == "OBSERVED" for c in obs),
          "OBSERVED is program-only -- no INFERRED/CONFIRMED from observation")

    tasks = expressible_tasks(chosen)
    check("reconciliation" in tasks,
          f"reconciliation is expressible for 2 collections: {tasks}")

    # --- 2. deterministic preview over the real kesko data -----------------
    p = preview(ws, _KESKO_MODEL)
    check(p.ok, f"the canned reconciliation model previews ok: {p.problems}")
    if p.ok:
        rows_text = json.dumps(p.rows, ensure_ascii=False)
        # PI-3301 same, PI-3303 different (119.94 vs 110.94), PI-3305 same,
        # PI-3350 only ledger, PI-3399 only statement.
        check("SAME" in rows_text and "DIFFERENT" in rows_text
              and "ONLY_LEDGER" in rows_text and "ONLY_STATEMENT" in rows_text,
              f"preview rows span all four relations: {rows_text[:300]}")

    # --- 3. render_model ----------------------------------------------------
    lines = render_model(_KESKO_MODEL, "reconciliation")
    check(bool(lines) and any("Invoice" in ln or "Their ref" in ln for ln in lines),
          f"render_model produces reconciliation sentences: {lines}")

    # --- 4. build_answer (the answer-string assembly) ----------------------
    class _FakeQ:
        options = ["supplier_statement.Their ref"]
        source = ["purchase_ledger"]
        field = "Invoice"
    check(build_answer(_FakeQ, "supplier_statement.Their ref")
          == "purchase_ledger.Invoice matches supplier_statement.Their ref",
          "a join answer assembles as <source>.<field> matches <choice>")
    class _FreeQ:
        options = []
        source = "purchase_ledger"
        field = "Booked"
    check(build_answer(_FreeQ, "a booking date") == "a booking date",
          "a free-text answer passes through unchanged")

    # --- 5. establish writes exactly 3 files + structural linkage -----------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        w = establish_workspace(ws, "kesko-reconciliation",
                                "Reconcile the purchase ledger against the "
                                "supplier statement.", "reconciliation",
                                _KESKO_MODEL, customer="kesko", root=root)
        check(w.task == "reconciliation", f"established worker task: {w.task}")
        check(w.current_version == 1, "established at v1")
        check(len(w.history) == 1, "one history line (established)")
        check(w.trigger == "data/kesko-reconciliation/",
              f"trigger is the source data dir: {w.trigger}")
        check(w.identity.get("customer") == "kesko",
              f"customer written into worker.json: {w.identity.get('customer')}")

        # exactly three files, no more (no state/inbox/runs/investigation)
        files = sorted(p2.name for p2 in w.directory.rglob("*") if p2.is_file())
        check(files == ["history.jsonl", "v1.json", "worker.json"],
              f"establish writes exactly worker.json + versions/v1.json + "
              f"history.jsonl: {files}")

        # the model is stored verbatim in v1.json
        stored = json.loads((w.directory / "versions" / "v1.json").read_text(encoding="utf-8"))
        check(stored["task"] == "reconciliation" and stored["match_on"]["left_field"] == "Invoice",
              "the established model is stored verbatim in v1.json")

        # structural linkage: incoming.scan links the data dir to this worker
        # via trigger-path containment (the provenance that falls out of
        # setting trigger = the data dir).
        scan = incoming.scan([w], LAB / "data")
        kesko = next((e for e in scan["data_library"] if e["dir"] == "kesko-reconciliation"), None)
        check(kesko is not None, "incoming.scan lists kesko-reconciliation")
        check(kesko and kesko["worker"] == "kesko-reconciliation",
              f"the data dir links STRUCTURALLY to the new worker via trigger: "
              f"{kesko['worker'] if kesko else None}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (workspace resolution + OBSERVED-only observation / "
          "reconciliation expressible / canned model previews ok with all four "
          "relations / render_model / build_answer join + free-text / establish "
          "writes exactly 3 files + customer / trigger links the data dir "
          "structurally). LLM stages (interpret/propose) are proven by the real "
          "acceptance run, not here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)