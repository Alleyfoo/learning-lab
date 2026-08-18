#!/usr/bin/env python3
"""A fleet of established workers, on disk. Append-only where it matters.

```text
fleet/
  <worker>/
    worker.json        identity: purpose, task type, where its data lives
    versions/vN.json   the model as established. NEVER edited, never deleted
    history.jsonl      append-only: what was established, when, and why
    runs.jsonl         append-only: one line per run, TAGGED WITH ITS VERSION
    investigation.json present only while an exception is unresolved
```

## Why the history is append-only rather than "shown as" history

`scripts/agent_binding.py` fixed the rule for agent definitions and Experiment Z
carried it to workers: **adopting now certifies nothing about a past run.** A
dashboard that re-renders v1's runs under v2's model would quietly restate
history, which is the same defect in a friendlier costume. So a run line records
the version that produced it and nothing rewrites it; promoting appends and
leaves every earlier line byte-identical. The self-test canaries that.

## What this module does NOT do

No new task semantics, no input adapters, no exception classes. It reads what the
existing workers and executors already produce. The question it exists to answer
is whether a fleet stays understandable, not whether one worker can do more.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "worker"))
sys.path.insert(0, str(LAB / "modeller"))

import builder  # noqa: E402
import pipeline  # noqa: E402
import runtime  # noqa: E402
import worker as W  # noqa: E402

ROOT = HERE / "workers"

# Task types with a committing runtime. Everything else produces a result and
# changes nothing, so preview and production are the same execution.
COMMITTING_TASKS = ("reservation",)

# One engine per task type, shared by every worker of that type. This is the
# point of the design: 100 established models over a handful of audited
# executors, rather than 100 generated scripts.
ENGINES = {
    "enrichment": "enrichment/harness/execute_enrichment.py",
    "reservation": "reservation/harness/execute_reservation.py",
    "aggregation": "aggregation/harness/execute_aggregation.py",
    "reconciliation": "reconciliation/harness/execute_reconciliation.py",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


@dataclass
class Worker:
    directory: Path
    identity: dict
    versions: dict[int, dict] = dc_field(default_factory=dict)
    history: list[dict] = dc_field(default_factory=list)
    runs: list[dict] = dc_field(default_factory=list)
    investigation: Optional[dict] = None
    input_contracts: dict[int, dict] = dc_field(default_factory=dict)

    # --- identity ---------------------------------------------------------
    @property
    def name(self) -> str:
        return self.identity["name"]

    @property
    def purpose(self) -> str:
        return self.identity["purpose"]

    @property
    def task(self) -> str:
        return self.identity["task"]

    @property
    def engine(self) -> str:
        return ENGINES.get(self.task, "unknown")

    @property
    def base(self) -> Path:
        return LAB / self.identity["base"]

    @property
    def effect(self) -> Optional[str]:
        """What the model declares it does beyond producing a table.

        Enrichment, aggregation and reconciliation produce a result and change
        nothing. A reservation declares `on_accept`, which is an effect on the
        world -- and this console does NOT commit it. See `committing`.
        """
        return self.model.get("on_accept")

    @property
    def committing(self) -> bool:
        """Whether a run through this console lands the declared effect.

        True only when the worker declares an effect AND a committing runtime
        exists for its task. Preview stays non-committing; this is the separate
        path, and the distinction is a fact about the worker rather than a
        caption on a page.
        """
        return bool(self.effect) and self.task in COMMITTING_TASKS

    @property
    def trigger(self) -> str:
        """Where this worker's data comes from. A folder, today."""
        return self.identity.get("trigger") or self.identity["base"]

    @property
    def destination(self) -> Optional[dict]:
        """Where the result of this work BELONGS (a declared business fact).

        Distinct from `effect` (executable effect authority, a model field):
        a destination says where a result is intended to go, not that the
        worker can write there. Lives on identity alongside `customer`, so it
        never collides with `on_accept`/committing and persists across model
        versions. May be None (the worker just produces a result table).
        """
        return self.identity.get("destination")

    @property
    def delivery(self) -> Optional[dict]:
        """Desired delivery mode for the destination: view/export/approval/
        automatic. A progression of intent, NOT effect authority -- a worker
        may declare `automatic` without any connector existing."""
        return self.identity.get("delivery")

    @property
    def current_version(self) -> int:
        return max(self.versions) if self.versions else 0

    @property
    def model(self) -> dict:
        return self.versions[self.current_version]

    @property
    def input_contract(self) -> Optional[dict]:
        """The version-bound executable input contract for the current version,
        or None when the worker has none.

        Mirrors how the version model is loaded: a per-worker
        `input_contracts/v<N>.json`, same `N` as the current model version. A
        model answers what to do; an input contract answers what data
        representation this version is allowed to do it with. The stable
        SOURCE ROLES (labels, sole/shared, required-ness, adapter policy) live
        on identity (`source_roles`), so they survive a re-model; the contract
        carries shape only. None is the back-compat gate: workers that take a
        JSON request and have no sheet contract keep working unchanged.
        """
        return self.input_contracts.get(self.current_version)

    # --- run record, always per version ------------------------------------
    def runs_for(self, version: int) -> list[dict]:
        return [r for r in self.runs if r["version"] == version]

    @property
    def open_investigation(self) -> Optional[dict]:
        inv = self.investigation
        return inv if inv and inv.get("state") == "open" else None

    def summary(self) -> dict:
        current = self.runs_for(self.current_version)
        exceptions = [r for r in self.runs if not r["ok"]]
        return {
            "worker": self.name, "purpose": self.purpose, "task": self.task,
            "engine": self.engine, "trigger": self.trigger,
            "version": self.current_version,
            "versions": len(self.versions),
            "runs_total": len(self.runs),
            "runs_this_version": len(current),
            "successes": sum(1 for r in current if r["ok"]),
            "exceptions": sum(1 for r in current if not r["ok"]),
            "rows_refused": sum(r.get("refused", 0) for r in current),
            "declined": sum(1 for r in current if r.get("accepted") is False),
            "effects_applied": sum(1 for r in current
                                   if r.get("effect_applied") is True),
            "effects_failed": sum(1 for r in current
                                  if r.get("effect_applied") is False),
            "committing": any(r.get("committing") for r in current),
            "last_run": self.runs[-1]["at"] if self.runs else None,
            # Scoped to the CURRENT version. After a promotion the all-time last
            # run belongs to the version that was replaced, so reading it made a
            # freshly repaired worker look broken -- found by repairing one.
            "last_status": ("not yet run on this version" if not current
                            else "ok" if current[-1]["ok"] else "exception"),
            "last_status_all_time": ("never run" if not self.runs
                                     else "ok" if self.runs[-1]["ok"]
                                     else "exception"),
            "investigation": (self.investigation or {}).get("state", "none"),
            "all_time_exceptions": len(exceptions),
        }


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def load(directory: Path) -> Worker:
    identity = json.loads((directory / "worker.json").read_text(encoding="utf-8"))
    versions = {}
    for path in sorted((directory / "versions").glob("v*.json")):
        versions[int(path.stem[1:])] = json.loads(path.read_text(encoding="utf-8"))
    input_contracts = {}
    contracts_dir = directory / "input_contracts"
    if contracts_dir.is_dir():
        for path in sorted(contracts_dir.glob("v*.json")):
            input_contracts[int(path.stem[1:])] = json.loads(
                path.read_text(encoding="utf-8"))
    inv_path = directory / "investigation.json"
    return Worker(directory, identity, versions,
                  _read_lines(directory / "history.jsonl"),
                  _read_lines(directory / "runs.jsonl"),
                  json.loads(inv_path.read_text(encoding="utf-8"))
                  if inv_path.is_file() else None,
                  input_contracts)


def load_all(root: Path = ROOT) -> list[Worker]:
    if not root.is_dir():
        return []
    return [load(d) for d in sorted(root.iterdir())
            if (d / "worker.json").is_file()]


# ---------------------------------------------------------------------------
# writing -- append-only, except identity
# ---------------------------------------------------------------------------

def establish(root: Path, name: str, purpose: str, task: str, base: str,
              model: dict, trigger: Optional[str] = None) -> Worker:
    directory = root / name
    (directory / "versions").mkdir(parents=True, exist_ok=True)
    (directory / "worker.json").write_text(json.dumps(
        {"name": name, "purpose": purpose, "task": task, "base": base,
         "trigger": trigger or base}, indent=2) + "\n", encoding="utf-8")
    (directory / "versions" / "v1.json").write_text(
        json.dumps(model, indent=2) + "\n", encoding="utf-8")
    _append(directory / "history.jsonl",
            {"version": 1, "at": _now(), "event": "established",
             "digest": W.digest(model), "why": "first established"})
    return load(directory)


def record_run(w: Worker, request: Optional[str] = None) -> dict:
    """Run the worker as established, and append the outcome. No LLM here."""
    est = W.Established(w.name, w.current_version, w.model, w.base, _now())
    if w.committing:
        # THE COMMITTING PATH. A refusal is healthy and attempts no effect; an
        # acceptance whose effect did not land is an exception, because
        # something downstream is entitled to believe the decision.
        result = runtime.commit(w.model, w.base, request)
        record = {"at": _now(), "version": w.current_version, "ok": result.ok,
                  "request": request, "committing": True,
                  "decision": result.decision, "reason": result.reason,
                  "effect": result.effect, "effect_applied": result.effect_applied,
                  "accepted": result.decision == "accepted",
                  "refused": 0 if result.decision == "accepted" else 1,
                  "refusals": [result.reason] if result.reason else [],
                  "state_before": result.state_before,
                  "state_after": result.state_after,
                  "problems": [result.error] if result.error else []}
    elif w.task == "reservation":
        preview = builder.preview(w.task, w.model, request=request, base=w.base)
        ok = preview.ok
        # A run that COMPLETED is not a run that accepted. A refused
        # reservation is the worker doing its job, and showing it as a failure
        # would make an operator chase healthy behaviour.
        row = preview.rows[0] if ok and preview.rows else None
        accepted = bool(row[1]) if row else None
        record = {"at": _now(), "version": w.current_version, "ok": ok,
                  "request": request, "detail": row, "committing": False,
                  "accepted": accepted,
                  "refused": 0 if accepted or accepted is None else 1,
                  "refusals": [] if accepted or not row else [row[2]],
                  "problems": [] if ok else list(preview.problems)}
    else:
        outcome = W.run(est, est.model_digest)
        ok = outcome.ok
        record = {"at": _now(), "version": w.current_version, "ok": ok,
                  "rows": len(outcome.rows), "refused": len(outcome.refused),
                  "refusals": [r.get("reason") for r in outcome.refused],
                  "problems": (outcome.packet or {}).get("failure", [])}
        if not ok:
            (w.directory / "last_packet.json").write_text(
                json.dumps(outcome.packet, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
    _append(w.directory / "runs.jsonl", record)
    w.runs.append(record)
    return record


def open_investigation(w: Worker, packet: dict, question: Optional[str],
                       state: str = "open") -> None:
    record = {"opened": _now(), "from_version": w.current_version, "state": state,
              "failure": packet.get("failure", []),
              "difference": packet.get("difference", {}),
              "question": question}
    (w.directory / "investigation.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    w.investigation = record


def promote(w: Worker, new_model: dict, why: str,
            replacements: Optional[list] = None) -> Worker:
    """Append a version. Nothing earlier is touched -- not the model, not the runs."""
    version = w.current_version + 1
    (w.directory / "versions" / f"v{version}.json").write_text(
        json.dumps(new_model, indent=2) + "\n", encoding="utf-8")
    _append(w.directory / "history.jsonl",
            {"version": version, "at": _now(), "event": "promoted",
             "digest": W.digest(new_model), "supersedes": w.current_version,
             "why": why, "replacements": replacements or []})
    if w.investigation:
        record = dict(w.investigation, state="resolved",
                      resolved_at=_now(), resolved_to_version=version,
                      proposal=replacements or [])
        (w.directory / "investigation.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load(w.directory)


def rebase(w: Worker, base: str) -> Worker:
    """Point a worker at different data. Used to simulate the world changing.

    Identity is the only mutable file: it says where to look, not what is true.
    """
    identity = dict(w.identity, base=base, trigger=base)
    (w.directory / "worker.json").write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    return load(w.directory)


# ---------------------------------------------------------------------------
# presentation helpers -- the readable model comes from the modeller
# ---------------------------------------------------------------------------

def readable(w: Worker, version: Optional[int] = None) -> list[str]:
    model = w.versions[version or w.current_version]
    if w.task == "enrichment":
        return pipeline.readable(model)
    if w.task == "reservation":
        rules = [r.get("rule") for r in model.get("rules", [])]
        lines = [f"Accept a requested date only if it passes, in order: "
                 f"{', '.join(rules)}."]
        for rule in model.get("rules", []):
            lines.append(f"If `{rule.get('rule')}` fails, refuse with "
                         f"**{rule.get('refusal')}**.")
        lines.append(f"On acceptance: {model.get('on_accept')}.")
        return lines
    return [f"(no readable rendering for task type {w.task})"]


def version_diff(w: Worker, older: int, newer: int) -> list[str]:
    """What actually changed between two established versions."""
    a, b = w.versions[older], w.versions[newer]
    out = []
    for key in sorted(set(a) | set(b)):
        if json.dumps(a.get(key), sort_keys=True) != json.dumps(b.get(key), sort_keys=True):
            out.append(f"{key}: {json.dumps(a.get(key))} -> {json.dumps(b.get(key))}")
    return out or ["(no difference)"]


def _self_test() -> int:
    import shutil
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    model = json.loads((LAB / "worker" / "established" /
                        "timesheet-cost-v1.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        w = establish(root, "tw", "Cost each timesheet entry.", "enrichment",
                      "data", model)
        check(w.current_version == 1 and len(w.history) == 1,
              f"establishing writes v1 and one history line: {w.history}")

        for _ in range(3):
            record_run(w)
        check(len(w.runs_for(1)) == 3 and all(r["ok"] for r in w.runs),
              f"three healthy runs recorded against v1: {w.runs}")

        runs_before = (w.directory / "runs.jsonl").read_text(encoding="utf-8")
        history_before = (w.directory / "history.jsonl").read_text(encoding="utf-8")
        v1_before = (w.directory / "versions" / "v1.json").read_text(encoding="utf-8")

        # the world changes
        w = rebase(w, "experimentZ/fixtures/A")
        broken = record_run(w)
        check(not broken["ok"] and broken["version"] == 1,
              f"the exception belongs to v1: {broken}")
        packet = json.loads((w.directory / "last_packet.json").read_text(encoding="utf-8"))
        open_investigation(w, packet, None)
        check(w.open_investigation is not None, "an unresolved exception is open")

        v2model = W.apply_replacements(
            model, [{"source": "staff", "from": "staff_id", "to": "employee_id"}])
        w = promote(w, v2model, "join target renamed",
                    [{"source": "staff", "from": "staff_id", "to": "employee_id"}])

        # --- IMMUTABILITY -------------------------------------------------
        check((w.directory / "versions" / "v1.json").read_text(encoding="utf-8")
              == v1_before, "CANARY: v1's model must be byte-identical after promotion")
        check((w.directory / "runs.jsonl").read_text(encoding="utf-8")
              .startswith(runs_before),
              "CANARY: existing run lines must be untouched -- append only")
        check((w.directory / "history.jsonl").read_text(encoding="utf-8")
              .startswith(history_before),
              "CANARY: existing history lines must be untouched")
        check(len(w.history) == 2 and w.history[1]["supersedes"] == 1,
              f"promotion appends one line naming what it supersedes: {w.history}")

        # --- v2 inherits authority, not history ---------------------------
        check(w.current_version == 2 and w.runs_for(2) == [],
              f"v2 starts with no runs of its own: {w.summary()}")
        check(len(w.runs_for(1)) == 4,
              f"v1 keeps all four of its runs: {len(w.runs_for(1))}")
        record_run(w)
        check(w.runs_for(2) and w.runs_for(2)[0]["ok"],
              "v2 runs healthily on the changed world")
        check(w.summary()["runs_this_version"] == 1
              and w.summary()["runs_total"] == 5,
              f"the summary separates this version from all time: {w.summary()}")

        # --- the investigation closed, and says what closed it -------------
        check(w.investigation["state"] == "resolved"
              and w.investigation["resolved_to_version"] == 2
              and w.investigation["proposal"],
              f"a resolved investigation records the proposal: {w.investigation}")
        check(w.open_investigation is None, "…and is no longer open")

        # --- the diff is real, not narrated --------------------------------
        diff = version_diff(w, 1, 2)
        check(len(diff) == 1 and "lookup" in diff[0]
              and "employee_id" in diff[0] and "staff_id" in diff[0],
              f"exactly one key differs between v1 and v2: {diff}")

        # --- readable rendering, and a shared engine -----------------------
        check(any("timesheets.staff_ref" in line and line.startswith("Match")
                  for line in readable(w)),
              f"the model renders as sentences: {readable(w)}")
        check(w.engine.endswith("execute_enrichment.py"),
              f"the engine is named so it can be audited: {w.engine}")
        check(readable(w, 1) != readable(w, 2),
              "an older version renders as it was, not as the current one")

    # --- input_contracts: version-bound executable input contract -----------
    # A model answers what to do; an input contract answers what data
    # representation this version is allowed to do it with. It lives in a
    # SEPARATE file (input_contracts/v<N>.json), not in versions/v<N>.json,
    # because taskmodel.parse would otherwise contaminate the task body with
    # the unknown top-level key (task_model.py:191). Same N as the model.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        w = establish(root, "ic", "Bind recurring evidence.", "enrichment",
                      "data", model)
        check(w.input_contract is None,
              "a worker with no input_contracts/ returns None (back-compat gate)")

        contracts_dir = w.directory / "input_contracts"
        contracts_dir.mkdir()
        c1 = {"roles": {"statement": {"sheet": "Statement", "header_row": 3,
                                      "collection": "statement"}}}
        (contracts_dir / "v1.json").write_text(
            json.dumps(c1, indent=2) + "\n", encoding="utf-8")
        w = load(w.directory)
        check(w.input_contract is not None
              and w.input_contract["roles"]["statement"]["sheet"] == "Statement",
              f"v1 input contract loads: {w.input_contract}")
        check(set(w.input_contracts) == {1},
              f"input_contracts keyed by version: {w.input_contracts}")

        # a version bump to v2 with its own contract reads v2, not v1
        v2model = W.apply_replacements(
            model, [{"source": "staff", "from": "staff_id", "to": "employee_id"}])
        w = promote(w, v2model, "contract advanced",
                    [{"source": "staff", "from": "staff_id", "to": "employee_id"}])
        check(w.current_version == 2 and w.input_contract is None,
              "v2 with no input_contracts/v2.json returns None (gate per version)")
        c2 = {"roles": {"statement": {"sheet": "Stmt2", "header_row": 2,
                                      "collection": "statement"}}}
        (contracts_dir / "v2.json").write_text(
            json.dumps(c2, indent=2) + "\n", encoding="utf-8")
        w = load(w.directory)
        check(w.input_contract["roles"]["statement"]["sheet"] == "Stmt2",
              f"after a version bump, input_contract reads v2: {w.input_contract}")
        check(set(w.input_contracts) == {1, 2},
              f"both contract versions retained: {set(w.input_contracts)}")

    # --- Acme carries the operational shape: roles on identity, shape on ---
    # contract, and the contract's collections align 1:1 with the model's
    # sources. `origin` in v1.json stays as founding provenance; the contract
    # is the forward shape future arrivals must match.
    acme = load(ROOT / "acme-august-recon")
    check(acme.input_contract is not None,
          "acme has an input_contracts/v1.json")
    contract_colls = {r["collection"]
                      for r in acme.input_contract["roles"].values()}
    model_colls = {s["collection"] for s in acme.model["sources"].values()}
    check(contract_colls == model_colls == {"statement", "transactions"},
          f"acme contract collections align 1:1 with model sources: "
          f"{contract_colls} vs {model_colls}")
    check(set(acme.input_contract["roles"])
          == set(acme.model["sources"]),
          f"acme contract roles align 1:1 with model source keys: "
          f"{set(acme.input_contract['roles'])} vs {set(acme.model['sources'])}")
    check(set(acme.identity.get("source_roles", {}))
          == set(acme.model["sources"]),
          f"acme stable source_roles on identity align with model sources: "
          f"{set(acme.identity.get('source_roles', {}))}")
    check(all(r["slot"] == "sole" and r["required"]
             for r in acme.identity["source_roles"].values()),
          "acme's two roles are sole + required (N-of-M completeness, 2 docs)")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (establish writes v1 and one history line / runs "
          "record against the version that produced them / an exception belongs "
          "to v1 and opens an investigation / promotion leaves v1's model, runs "
          "and history byte-identical / v2 inherits authority and no history "
          "while v1 keeps all four runs / the summary separates this version "
          "from all time / a resolved investigation records what closed it / "
          "exactly one key differs between v1 and v2 / an older version renders "
          "as it was / the engine is named so it can be audited)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
