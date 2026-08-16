#!/usr/bin/env python3
"""The model builder's CORE: select sources, edit, validate, preview, approve.

Headless and testable. `app.py` is a thin Streamlit view over exactly these
functions -- the same split as `structure_view.py` and the workbook browser,
for the same reason: a UI that holds logic cannot be self-tested.

## What this is NOT

Not a fifth task type, and not a new layer of task language. It operates the
four that exist, through the floor's registry and each task's own validator.
The human edits the model body as JSON; the TASK'S OWN VALIDATOR is what
guides them. That is deliberate: it tests whether those validators are good
enough to steer a person, and if they are not, that is a finding about the
validators rather than a reason to build a schema layer on top.

## The one coupling the modeller exposes, and why the floor did not change

To PREVIEW, something must know how to execute each task. The floor's registry
carries validation and the refusal vocabulary; it does not carry execution,
because execution is not part of what a task model IS -- a model can be valid
without ever being run. So the map lives here, in the thing that needs it:

```text
TASKS   task name -> where it lives, how to execute it, and whether it needs
        a per-run input (reservation does; the other three do not)
```

The honest cost: a fifth task type would require adding a line here. That is a
real coupling, recorded rather than designed away, and it is cheaper than
teaching the envelope about execution.

## Approval binds what was SHOWN

The same shape as the frozen authority path -- model, sources, and the rendered
preview, each hashed, plus a previewer version -- because that path's lesson
holds here: if it was not in what the reviewer saw, it was not part of the
approval evidence.

**It does not import `approval.py` and does not claim its guarantees.** That
path is frozen (`authority-path-v1`) and is about recipes over workbooks; this
is a different artifact. Guarantees G-1..G-5 are NOT inherited, and no part of
this module should be cited as evidence for them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field as dc_field
from pathlib import Path
from typing import Any, Callable, Optional

LAB = Path(__file__).resolve().parents[1]
for _p in ("taskmodel", "reservation/harness", "enrichment/harness",
           "aggregation/harness", "reconciliation/harness"):
    sys.path.insert(0, str(LAB / _p))

import task_model  # noqa: E402
from task_model import Report, TaskModel, registered  # noqa: E402

# Importing each body registers its task type with the floor.
import aggregation_model  # noqa: E402,F401
import enrichment_model  # noqa: E402,F401
import reconciliation_model  # noqa: E402,F401
import reservation_model  # noqa: E402,F401

import execute_aggregation  # noqa: E402
import execute_enrichment  # noqa: E402
import execute_reconciliation  # noqa: E402
import execute_reservation  # noqa: E402

PREVIEWER_VERSION = "preview-v1"


@dataclass(frozen=True)
class TaskBinding:
    """Where a task lives and how to run it. See the module docstring."""
    name: str
    base: Path
    run: Callable
    needs_request: bool = False
    request_label: str = ""


TASKS: dict[str, TaskBinding] = {
    "reservation": TaskBinding(
        "reservation", LAB / "reservation",
        lambda m, b, request=None: execute_reservation.execute(m, b, request),
        needs_request=True, request_label="requested date (YYYY-MM-DD)"),
    "enrichment": TaskBinding(
        "enrichment", LAB / "enrichment",
        lambda m, b, request=None: execute_enrichment.execute(m, b)),
    "aggregation": TaskBinding(
        "aggregation", LAB / "aggregation",
        lambda m, b, request=None: execute_aggregation.execute(m, b)),
    "reconciliation": TaskBinding(
        "reconciliation", LAB / "reconciliation",
        lambda m, b, request=None: execute_reconciliation.execute(m, b)),
}


def task_names() -> list[str]:
    """Task types that are BOTH registered with the floor and runnable here.

    Reported as an intersection rather than either list alone, so a task
    registered but unbound (or bound but unregistered) shows up as absent
    instead of failing later at preview time.
    """
    return sorted(n for n in TASKS if registered(n) is not None)


def unbound_tasks() -> list[str]:
    """Registered with the floor but not runnable here -- the coupling, visible."""
    return sorted(n for n in task_model._REGISTRY if n not in TASKS)


# ---------------------------------------------------------------------------
# select sources
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceCandidate:
    path: str                    # relative to the task base
    collections: tuple[str, ...]  # top-level keys holding a LIST
    counts: dict


def available_sources(task: str) -> list[SourceCandidate]:
    """Data files under the task's fixtures/, with the collections inside each.

    The collections are READ from the file rather than guessed from its name,
    because `sources` in a model names a file AND a key inside it, and getting
    the key wrong is a `malformed_data_file` the human would otherwise meet
    only after saving.
    """
    base = TASKS[task].base
    out: list[SourceCandidate] = []
    for path in sorted((base / "fixtures").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        cols = tuple(k for k, v in data.items() if isinstance(v, list))
        out.append(SourceCandidate(
            path=f"fixtures/{path.name}", collections=cols,
            counts={k: len(data[k]) for k in cols}))
    return out


def available_models(task: str) -> list[str]:
    base = TASKS[task].base
    return sorted(f"models/{p.name}" for p in (base / "models").glob("*.json"))


def load_model(task: str, rel: str) -> dict:
    return json.loads((TASKS[task].base / rel).read_text(encoding="utf-8"))


def save_model(task: str, rel: str, raw: dict) -> Path:
    path = TASKS[task].base / rel
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate / preview
# ---------------------------------------------------------------------------

def validate_raw(task: str, raw: dict, base: Optional[Path] = None) -> Report:
    """The task's OWN validator, through the floor. Nothing is added here."""
    return task_model.validate(task_model.parse(raw), base or TASKS[task].base)


@dataclass
class Preview:
    ok: bool
    problems: list[str] = dc_field(default_factory=list)
    columns: list[str] = dc_field(default_factory=list)
    rows: list[list] = dc_field(default_factory=list)
    notes: list[str] = dc_field(default_factory=list)
    refused: list[dict] = dc_field(default_factory=list)
    run_refused: Optional[str] = None

    def as_dict(self) -> dict:
        return {"ok": self.ok, "problems": self.problems, "columns": self.columns,
                "rows": self.rows, "notes": self.notes, "refused": self.refused,
                "run_refused": self.run_refused}


def preview(task: str, raw: dict, request: Optional[str] = None,
            base: Optional[Path] = None) -> Preview:
    """Run the task deterministically and shape the result for a human.

    An invalid model is never executed -- the problems ARE the preview, which is
    the point: a person should see why before seeing output.

    `base` overrides where the model's source paths resolve from. It exists
    because the modeller now works over data the user SELECTS, which need not
    live under the task's own directory; the executor is unchanged and still
    resolves exactly the paths the model declares.
    """
    binding = TASKS[task]
    root = base or binding.base
    report = validate_raw(task, raw, base=root)
    if not report.valid:
        return Preview(ok=False, problems=[str(p) for p in report.problems])

    if binding.needs_request and not request:
        return Preview(ok=False,
                       problems=[f"{task} needs {binding.request_label} to preview"])

    model = task_model.parse(raw)
    try:
        result = binding.run(model, root, request)
    except Exception as exc:                     # noqa: BLE001 - shown, not swallowed
        return Preview(ok=False, problems=[f"{type(exc).__name__}: {exc}"])

    # Reservation answers about ONE request; the other three produce a table.
    # Reported in each one's own terms rather than forced into a common shape.
    if hasattr(result, "accepted"):
        return Preview(
            ok=True, columns=["request", "accepted", "reason"],
            rows=[[result.request, result.accepted, result.reason or ""]],
            notes=[f"rules evaluated: {', '.join(result.evaluated)}",
                   f"reservations after: {len(result.reservations)}"])

    return Preview(
        ok=True, columns=list(result.columns),
        rows=[list(r) for r in result.rows],
        refused=list(getattr(result, "refused", [])),
        run_refused=getattr(result, "run_refused", None),
        notes=[f"{len(result.rows)} row(s)"])


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(raw: dict) -> str:
    return json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sources_digest(task: str, raw: dict) -> str:
    """One hash over every declared source's CONTENT, keyed by source name.

    The model names files; approving the model without binding what those files
    said would approve a pointer rather than a decision.
    """
    base = TASKS[task].base
    payload = {}
    for name, spec in sorted((raw.get("sources") or {}).items()):
        path = base / str(spec.get("path", ""))
        try:
            payload[name] = path.read_text(encoding="utf-8")
        except OSError:
            payload[name] = None
    return _sha(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def render_preview(p: Preview) -> str:
    """The exact text a reviewer is shown. Hashed into the approval."""
    lines = [f"ok={p.ok}"]
    if p.problems:
        lines += ["problems:"] + [f"  {x}" for x in p.problems]
    if p.columns:
        lines.append("columns: " + " | ".join(map(str, p.columns)))
    for row in p.rows:
        lines.append("  " + " | ".join(json.dumps(c, ensure_ascii=False) for c in row))
    for r in p.refused:
        lines.append("refused: " + json.dumps(r, sort_keys=True, ensure_ascii=False))
    if p.run_refused:
        lines.append(f"run_refused: {p.run_refused}")
    lines += [f"note: {n}" for n in p.notes]
    return "\n".join(lines)


@dataclass(frozen=True)
class Approval:
    task: str
    model_id: str
    model_sha256: str
    sources_sha256: str
    preview_sha256: str
    previewer_version: str
    approved_by: str
    approved_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False, sort_keys=True)


def approve(task: str, raw: dict, p: Preview, approved_by: str,
            approved_at: str) -> Approval:
    """Bind the model, its sources, and the preview that was actually shown.

    Refuses to approve a preview that did not succeed: approving a model whose
    preview reported problems would record agreement to something nobody saw
    working.
    """
    if not p.ok:
        raise ValueError("refusing to approve: the preview did not succeed")
    return Approval(
        task=task, model_id=str(raw.get("model_id", "")),
        model_sha256=_sha(canonical(raw)),
        sources_sha256=sources_digest(task, raw),
        preview_sha256=_sha(render_preview(p)),
        previewer_version=PREVIEWER_VERSION,
        approved_by=approved_by, approved_at=approved_at)


def verify(approval: Approval, raw: dict, p: Preview) -> dict:
    """Recompute every link. Per-link, never one boolean."""
    checks = {
        "model": "OK" if _sha(canonical(raw)) == approval.model_sha256 else "MODEL_CHANGED",
        "sources": ("OK" if sources_digest(approval.task, raw) == approval.sources_sha256
                    else "SOURCES_CHANGED"),
        "preview": ("OK" if _sha(render_preview(p)) == approval.preview_sha256
                    else "PREVIEW_CHANGED"),
        "previewer": ("OK" if approval.previewer_version == PREVIEWER_VERSION
                      else "PREVIEWER_SUPERSEDED"),
    }
    return {"checks": checks,
            "valid": all(v == "OK" for v in checks.values()),
            "failures": sorted({v for v in checks.values() if v != "OK"})}


def _self_test() -> int:
    import copy
    import tempfile

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- every registered task is operable, and the coupling is visible ------
    check(task_names() == ["aggregation", "enrichment", "reconciliation", "reservation"],
          f"all four task types must be operable: {task_names()}")
    check(unbound_tasks() == [],
          f"a task registered with the floor but not bound here would fail only "
          f"at preview time: {unbound_tasks()}")

    # --- select sources ------------------------------------------------------
    srcs = available_sources("reconciliation")
    by_path = {s.path: s for s in srcs}
    check("fixtures/expected_users.json" in by_path, f"sources: {sorted(by_path)}")
    check(by_path["fixtures/expected_users.json"].collections == ("users",),
          f"collections must be READ from the file: "
          f"{by_path['fixtures/expected_users.json'].collections}")
    check(by_path["fixtures/expected_users.json"].counts["users"] == 3,
          "row counts help a human pick the right file")

    # --- validate: the task's own validator guides ---------------------------
    raw = load_model("reconciliation", "models/reconciliation_v3.json")
    check(validate_raw("reconciliation", raw).valid, "the shipped v3 model must validate")

    broken = copy.deepcopy(raw)
    broken["compare"][1].pop("tolerance")
    rep = validate_raw("reconciliation", broken)
    check(not rep.valid and "comparison_tolerance_mismatch" in rep.codes(),
          f"the task's OWN validator must be what guides the human: {rep.codes()}")

    # --- preview -------------------------------------------------------------
    p = preview("reconciliation", raw)
    check(p.ok and len(p.rows) == 4, f"preview: {p.as_dict()}")

    bad_preview = preview("reconciliation", broken)
    check(not bad_preview.ok and bad_preview.problems and not bad_preview.rows,
          "an invalid model must NOT be executed -- the problems are the preview")

    # Reservation needs a per-run input; the other three do not.
    no_request = preview("reservation",
                         load_model("reservation", "models/reservation_v1.json"))
    check(not no_request.ok and "requested date" in no_request.problems[0],
          f"a task needing a request must SAY so rather than guess: {no_request.problems}")
    with_request = preview("reservation",
                           load_model("reservation", "models/reservation_v1.json"),
                           request="2026-12-25")
    check(with_request.ok and with_request.rows[0][2] == "HOLIDAY",
          f"reservation preview: {with_request.as_dict()}")

    for task in ("enrichment", "aggregation"):
        model_rel = available_models(task)[0]
        pv = preview(task, load_model(task, model_rel))
        check(pv.ok and pv.rows, f"{task} preview must produce rows: {pv.problems}")

    # --- approve -------------------------------------------------------------
    approval = approve("reconciliation", raw, p, "designer", "2026-08-15T12:00:00Z")
    v = verify(approval, raw, p)
    check(v["valid"], f"a fresh approval must verify: {v}")

    # A model edited after approval fails on the MODEL link only.
    edited = copy.deepcopy(raw)
    edited["output_order"] = "sorted_by_key"
    v_model = verify(approval, edited, p)
    check(v_model["checks"]["model"] == "MODEL_CHANGED"
          and v_model["checks"]["sources"] == "OK",
          f"an edited model must fail on its OWN link: {v_model['checks']}")

    # A preview that no longer matches what was shown.
    other = preview("reconciliation", load_model("reconciliation",
                                                 "models/reconciliation_v1.json"))
    v_prev = verify(approval, raw, other)
    check(v_prev["checks"]["preview"] == "PREVIEW_CHANGED"
          and v_prev["checks"]["model"] == "OK",
          f"a different preview must fail on the PREVIEW link: {v_prev['checks']}")

    # Sources changed underneath an unchanged model.
    with tempfile.TemporaryDirectory() as td:
        src = TASKS["reconciliation"].base / "fixtures" / "expected_users.json"
        backup = src.read_text(encoding="utf-8")
        try:
            data = json.loads(backup)
            data["users"].append({"user_id": "zed", "email": "z@x",
                                  "name": "Zed", "status": "active",
                                  "balance": "1.00"})
            src.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            v_src = verify(approval, raw, p)
            check(v_src["checks"]["sources"] == "SOURCES_CHANGED"
                  and v_src["checks"]["model"] == "OK",
                  f"a model approved against DIFFERENT data must fail on the "
                  f"SOURCES link: {v_src['checks']}")
        finally:
            src.write_text(backup, encoding="utf-8")

    # Approving something nobody saw working.
    try:
        approve("reconciliation", broken, bad_preview, "designer", "2026-08-15T12:00:00Z")
        refused = False
    except ValueError:
        refused = True
    check(refused, "approving a FAILED preview must be refused: it would record "
                   "agreement to something nobody saw working")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (all four task types operable and none unbound / sources "
          "read their own collections / the TASK'S validator guides / an invalid model "
          "is never executed / a task needing a request says so / approval binds model, "
          "sources and the shown preview, each failing on its OWN link / approving a "
          "failed preview refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
