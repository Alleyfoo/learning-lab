#!/usr/bin/env python3
"""The shared floor under a task model: identity, sources, and the contract.

Extracted from the reservation and enrichment tasks by comparing them, NOT by
designing what a task model ought to look like. What is here is what both of them
actually had; what only one of them had stayed where it was.

## The evidence for the boundary

Comparing the two hand-written models:

```text
shared model KEYS          model_id, model_version                    (2)
shared PROBLEM CODES       unknown_model_version, missing_key,
                           missing_data_file, malformed_data_file     (4)
```

All four shared codes are about **identity and data sources**. Every other code
in either task -- `unknown_rule`, `wellformedness_not_first`, `unknown_op`,
`field_not_in_source`, `output_needs_field_or_compute` -- belongs to one task's
body and to nothing else.

So the floor is an **envelope**, not a task language. Reservation's `rules` and
enrichment's `lookup`/`outputs` are not two dialects of one thing on any evidence
available, and inventing a union with optional `rules?` / `lookup?` / `outputs?`
would be fitting a format to two examples rather than extracting one from them.

## What the envelope owns

```text
identity        model_version, model_id, task
sources         name -> (file, collection), each proven to exist, parse, and
                yield a LIST
task registry   each task type registers its CLOSED refusal vocabulary and its
                own body validator
parity          declared vocabulary vs executor capability -- written by hand
                twice before this existed
```

## What the envelope deliberately does NOT own

Element shape inside a collection. Reservation's sources are lists of date
STRINGS; enrichment's are lists of OBJECTS. The envelope proves a list arrived
and stops there, because "what a row looks like" is exactly the task-specific
knowledge it has no business holding.

Nor effects, precedence, joins, computation, or policies. Each of those exists in
one task only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Callable, Optional

MODEL_VERSIONS = (1,)

# The envelope's own vocabulary: exactly the codes both hand-written validators
# already had. Adding a fifth would mean claiming shared structure that the two
# examples did not demonstrate.
ENVELOPE_PROBLEM_CODES = (
    "unknown_model_version",
    "missing_key",
    "missing_data_file",
    "malformed_data_file",
    "unknown_task",
)


@dataclass(frozen=True)
class Problem:
    code: str
    where: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.code}@{self.where}: {self.detail}" if self.detail \
            else f"{self.code}@{self.where}"


@dataclass(frozen=True)
class Source:
    name: str
    path: str
    collection: str


@dataclass
class TaskModel:
    model_version: int
    model_id: str
    task: str
    sources: dict[str, Source]
    body: dict                      # task-specific; opaque here, by design

    def source_names(self) -> tuple[str, ...]:
        return tuple(self.sources)


@dataclass
class Report:
    problems: list[Problem] = dc_field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.problems

    def codes(self) -> set[str]:
        return {p.code for p in self.problems}


# ---------------------------------------------------------------------------
# task registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskType:
    """What a task must supply to sit on this floor.

    `refusals` is the CLOSED vocabulary of outcomes the task may report. Both
    tasks already had one; keeping it here lets `assert_refusal` be shared rather
    than re-implemented per executor.
    """
    name: str
    refusals: tuple[str, ...]
    validate_body: Callable[[TaskModel, Path], list[Problem]]
    body_problem_codes: tuple[str, ...] = ()


_REGISTRY: dict[str, TaskType] = {}


def register(task: TaskType) -> TaskType:
    _REGISTRY[task.name] = task
    return task


def registered(name: str) -> Optional[TaskType]:
    return _REGISTRY.get(name)


def assert_refusal(task_name: str, reason: str) -> str:
    """A refusal an executor emits must be in the task's declared vocabulary.

    Raises rather than returns: an executor inventing a reason is a defect in the
    executor, not an outcome to report to a caller.
    """
    task = _REGISTRY.get(task_name)
    if task is None:
        raise KeyError(f"no registered task {task_name!r}")
    if reason not in task.refusals:
        raise ValueError(
            f"{task_name} emitted refusal {reason!r}, which is not in its "
            f"declared vocabulary {list(task.refusals)}")
    return reason


# ---------------------------------------------------------------------------
# parse / validate / load
# ---------------------------------------------------------------------------

def parse(raw: dict) -> TaskModel:
    """Structural parse only. Judgement belongs to validate()."""
    sources: dict[str, Source] = {}
    for name, spec in (raw.get("sources") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        sources[name] = Source(name=name,
                               path=str(spec.get("path", "")),
                               collection=str(spec.get("collection", "")))
    known = {"model_version", "model_id", "task", "sources"}
    return TaskModel(
        model_version=raw.get("model_version", 0),
        model_id=str(raw.get("model_id", "")),
        task=str(raw.get("task", "")),
        sources=sources,
        body={k: v for k, v in raw.items() if k not in known and not k.startswith("_")},
    )


def load_model(path: Path) -> TaskModel:
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))


def validate(model: TaskModel, base: Path) -> Report:
    """Envelope first, then the registered task's own body validator."""
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"

    if model.model_version not in MODEL_VERSIONS:
        problems.append(Problem("unknown_model_version", where, str(model.model_version)))
    if not model.model_id:
        problems.append(Problem("missing_key", "<model>", "model_id"))
    if not model.task:
        problems.append(Problem("missing_key", where, "task"))

    task = _REGISTRY.get(model.task)
    if model.task and task is None:
        problems.append(Problem("unknown_task", where,
                                f"{model.task!r}; registered: {sorted(_REGISTRY)}"))

    if not model.sources:
        problems.append(Problem("missing_key", where, "sources"))

    for name, src in model.sources.items():
        swhere = f"{where}:sources.{name}"
        if not src.path or not src.collection:
            problems.append(Problem("missing_key", swhere, "path and collection"))
            continue
        path = (base / src.path).resolve()
        if not path.exists():
            problems.append(Problem("missing_data_file", swhere, src.path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(Problem("malformed_data_file", swhere, str(exc)))
            continue
        # A LIST arrived, and that is where the envelope stops. What a row looks
        # like is the body's business: reservation's rows are date strings,
        # enrichment's are objects, and the floor should not know either.
        if not isinstance(data.get(src.collection), list):
            problems.append(Problem("malformed_data_file", swhere,
                                    f"expected a list under {src.collection!r}"))

    if task is not None:
        problems.extend(task.validate_body(model, base))

    return Report(problems=problems)


def load_collection(model: TaskModel, base: Path, source: str) -> list:
    """The declared collection, as written. No parsing, no normalisation."""
    src = model.sources[source]
    data = json.loads((base / src.path).resolve().read_text(encoding="utf-8"))
    return list(data.get(src.collection, []))


def _self_test() -> int:
    """The floor's own evidence: every envelope code, and the registry contract."""
    import sys
    import tempfile

    failures: list[str] = []
    seen: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    def probe(raw: dict, base: Path) -> Report:
        r = validate(parse(raw), base)
        seen.update(r.codes())
        return r

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        (base / "data.json").write_text('{"items": ["a", "b"]}', encoding="utf-8")
        (base / "bad.json").write_text("{not json", encoding="utf-8")
        (base / "notalist.json").write_text('{"items": {"a": 1}}', encoding="utf-8")

        body_seen: dict = {}

        def body_validator(model: TaskModel, b: Path) -> list[Problem]:
            body_seen["called"] = True
            body_seen["body"] = dict(model.body)
            return []

        register(TaskType(name="probe_task", refusals=("ONLY_REASON",),
                          validate_body=body_validator))

        good = {"model_version": 1, "model_id": "m", "task": "probe_task",
                "sources": {"s": {"path": "data.json", "collection": "items"}},
                "extra": {"anything": 1}}

        # --- control ---------------------------------------------------------
        r = probe(good, base)
        check(r.valid, f"a well-formed envelope must validate: {[str(p) for p in r.problems]}")
        check(body_seen.get("called"), "the registered body validator must be called")
        check(body_seen.get("body") == {"extra": {"anything": 1}},
              f"the body must be everything OUTSIDE the envelope keys: "
              f"{body_seen.get('body')}")

        # --- every envelope code ---------------------------------------------
        r = probe({**good, "model_version": 99}, base)
        check("unknown_model_version" in r.codes(), f"version: {sorted(r.codes())}")
        r = probe({k: v for k, v in good.items() if k != "model_id"}, base)
        check("missing_key" in r.codes(), f"model_id: {sorted(r.codes())}")
        r = probe({**good, "task": "nope"}, base)
        check("unknown_task" in r.codes(), f"task: {sorted(r.codes())}")
        r = probe({**good, "sources": {"s": {"path": "gone.json", "collection": "items"}}}, base)
        check("missing_data_file" in r.codes(), f"missing file: {sorted(r.codes())}")
        r = probe({**good, "sources": {"s": {"path": "bad.json", "collection": "items"}}}, base)
        check("malformed_data_file" in r.codes(), f"unparseable: {sorted(r.codes())}")

        # A LIST is where the envelope stops -- element shape is the body's.
        r = probe({**good, "sources": {"s": {"path": "notalist.json", "collection": "items"}}},
                  base)
        check("malformed_data_file" in r.codes(), f"not a list: {sorted(r.codes())}")
        r = probe({**good, "sources": {"s": {"path": "data.json", "collection": "items"}}}, base)
        check(r.valid, "a list of STRINGS must satisfy the envelope: the floor does "
                       "not know what a row looks like")

        # --- refusal vocabulary ----------------------------------------------
        check(assert_refusal("probe_task", "ONLY_REASON") == "ONLY_REASON",
              "a declared refusal must pass through")
        try:
            assert_refusal("probe_task", "INVENTED")
            raised = False
        except ValueError:
            raised = True
        check(raised, "an executor inventing a refusal reason must raise, not return")

        # --- parity ------------------------------------------------------------
        p_ok = vocabulary_parity({"ops": ("a", "b")}, {"ops": ("a", "b")})
        p_bad = vocabulary_parity({"ops": ("a", "b")}, {"ops": ("a",)})
        check(p_ok["agree"] and not p_bad["agree"],
              f"parity must agree only when the vocabularies match: {p_ok} {p_bad}")
        check(p_bad["ops"]["declared_not_implemented"] == ["b"],
              f"parity must name WHICH token drifted: {p_bad}")

    untested = sorted(set(ENVELOPE_PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised envelope codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (all {len(ENVELOPE_PROBLEM_CODES)} envelope codes exercised "
          f"/ body is everything outside the envelope keys / the floor stops at 'a list "
          f"arrived' / an invented refusal raises / parity names the drifted token)")
    return 0


def vocabulary_parity(declared: dict[str, tuple], implemented: dict[str, tuple]) -> dict:
    """Declared vocabulary vs executor capability, per named dimension.

    Both tasks hand-wrote this before it lived here. It matters because each
    executor's "refuse what I cannot honour" guard is UNREACHABLE while the
    validator rejects unknown tokens first -- so the guard is defence in depth
    and this is the check with teeth: a token declared and never implemented.
    """
    out: dict[str, Any] = {"agree": True}
    for dimension, declared_values in declared.items():
        impl = set(implemented.get(dimension, ()))
        decl = set(declared_values)
        missing = sorted(decl - impl)
        extra = sorted(impl - decl)
        out[dimension] = {"declared_not_implemented": missing,
                          "implemented_not_declared": extra}
        if missing or extra:
            out["agree"] = False
    return out


if __name__ == "__main__":
    import sys

    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
