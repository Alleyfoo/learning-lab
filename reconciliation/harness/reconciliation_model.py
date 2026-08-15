#!/usr/bin/env python3
"""The reconciliation task's BODY: two PEER sources and a declared match.

The fourth shape, and the first with no numeric semantics anywhere -- no
arithmetic, no dates, no coercion, and deliberately **no `on_non_numeric`
policy**. That absence is the point: the three earlier tasks all have such a
policy, and they may be siblings because they were written similarly rather than
because the structure is common. A shape with no reason to need one is the
independent evidence.

## What makes this a different shape

```text
reservation      sequential predicates over ONE value
enrichment       one-sided lookup: a driving source and a REFERENCE
aggregation      many rows -> one grouped row
reconciliation   two PEER sources -> classify the UNION by relationship
```

Enrichment has a subordinate side: the reference table is consulted, never
iterated. Here neither source is subordinate -- an output row can originate from
either side, and a key present only on the RIGHT must survive. An implementation
that quietly behaves like a left join loses those rows entirely, which is the
discriminator `run_reconciliation.py` is built around.

See `reconciliation/design/reconciliation_model_v1.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

from task_model import (  # noqa: E402
    Problem, Report, TaskModel, TaskType, load_collection, register,
    validate as validate_envelope,
)

RELATIONS = ("both", "only_left", "only_right")
OUTPUT_ORDERS = ("left_then_right", "sorted_by_key")

# What may happen when one side carries a key more than once. `deduplicate` and
# `separate_records` are DELIBERATELY ABSENT: both silently change what the data
# says, and following the enrichment precedent, a policy that quietly discards or
# multiplies rows must be a NAMED policy with its own evidence before it exists.
DUPLICATE_POLICIES = ("refuse_run", "refuse_key")

REFUSALS = ("DUPLICATE_KEY", "MISSING_MATCH_KEY")

BODY_PROBLEM_CODES = (
    "missing_key",
    "unknown_source",
    "same_source_both_sides",
    "unknown_output_order",
    "unknown_policy",
    "missing_classification",
    "duplicate_classification",
    "field_not_in_source",
    "malformed_data_file",
)


def left(model: TaskModel) -> str:
    return str(model.body.get("left", ""))


def right(model: TaskModel) -> str:
    return str(model.body.get("right", ""))


def match_on(model: TaskModel) -> tuple[str, str]:
    m = model.body.get("match_on") or {}
    return str(m.get("left_field", "")), str(m.get("right_field", ""))


def classify(model: TaskModel) -> dict:
    return dict(model.body.get("classify") or {})


def output_order(model: TaskModel) -> str:
    return str(model.body.get("output_order", ""))


def on_duplicate_key(model: TaskModel) -> str:
    return str(model.body.get("on_duplicate_key", ""))


def validate_body(model: TaskModel, base: Path) -> list[Problem]:
    problems: list[Problem] = []
    where = model.model_id or "<no model_id>"

    columns: dict[str, set[str]] = {}
    for name in model.sources:
        try:
            rows = load_collection(model, base, name)
        except (OSError, ValueError):
            continue                      # already reported by the envelope
        if not all(isinstance(r, dict) for r in rows):
            problems.append(Problem("malformed_data_file", f"{where}:sources.{name}",
                                    "expected a list of objects"))
            continue
        columns[name] = {k for row in rows for k in row}

    known = set(model.sources)
    lname, rname = left(model), right(model)
    for label, name in (("left", lname), ("right", rname)):
        if name not in known:
            problems.append(Problem("unknown_source", f"{where}:{label}", name))

    # Reconciling a source with itself makes every key BOTH by construction. It
    # is a modelling error, not a degenerate but meaningful run.
    if lname and lname == rname:
        problems.append(Problem("same_source_both_sides", where,
                                f"both sides name {lname!r}; every key would be "
                                f"BOTH by construction"))

    lfield, rfield = match_on(model)
    if not lfield or not rfield:
        problems.append(Problem("missing_key", f"{where}:match_on",
                                "left_field and right_field"))
    else:
        if lname in columns and lfield not in columns[lname]:
            problems.append(Problem("field_not_in_source", f"{where}:match_on.left_field",
                                    f"{lname}.{lfield}"))
        if rname in columns and rfield not in columns[rname]:
            problems.append(Problem("field_not_in_source", f"{where}:match_on.right_field",
                                    f"{rname}.{rfield}"))

    # Every relation must be given a label, and no two may share one -- a shared
    # label makes the output unreadable, which is worse than an absent one.
    labels = classify(model)
    for relation in RELATIONS:
        if not labels.get(relation):
            problems.append(Problem("missing_classification", f"{where}:classify",
                                    relation))
    seen: dict[str, str] = {}
    for relation, label in labels.items():
        if relation not in RELATIONS:
            problems.append(Problem("missing_classification", f"{where}:classify",
                                    f"unknown relation {relation!r}"))
            continue
        if label in seen:
            problems.append(Problem("duplicate_classification", f"{where}:classify",
                                    f"{relation!r} and {seen[label]!r} both use "
                                    f"{label!r}; the output could not be read"))
        else:
            seen[label] = relation

    if output_order(model) not in OUTPUT_ORDERS:
        problems.append(Problem("unknown_output_order", where, output_order(model)))
    if on_duplicate_key(model) not in DUPLICATE_POLICIES:
        problems.append(Problem("unknown_policy", f"{where}:on_duplicate_key",
                                on_duplicate_key(model)))

    return problems


TASK = register(TaskType(name="reconciliation", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def validate(model: TaskModel, base: Path) -> Report:
    return validate_envelope(model, base)


def _self_test() -> int:
    import copy
    import json
    import tempfile

    import task_model

    base = Path(__file__).resolve().parent.parent
    failures: list[str] = []
    seen: set[str] = set()

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    raw = json.loads((base / "models" / "reconciliation_v1.json").read_text(encoding="utf-8"))
    rep = validate(task_model.parse(raw), base)
    seen |= rep.codes()
    check(rep.valid, f"the shipped model must validate: {[str(p) for p in rep.problems]}")

    def probe(mutate) -> Report:
        bad = copy.deepcopy(raw)
        mutate(bad)
        r = validate(task_model.parse(bad), base)
        seen.update(r.codes())
        return r

    r = probe(lambda d: d.update(left="nope"))
    check("unknown_source" in r.codes(), f"left: {sorted(r.codes())}")
    r = probe(lambda d: d.update(right=d["left"]))
    check("same_source_both_sides" in r.codes(), f"self-reconcile: {sorted(r.codes())}")
    r = probe(lambda d: d["match_on"].update(left_field=""))
    check("missing_key" in r.codes(), f"match_on: {sorted(r.codes())}")
    r = probe(lambda d: d["match_on"].update(left_field="colour"))
    check("field_not_in_source" in r.codes(), f"bad field: {sorted(r.codes())}")
    r = probe(lambda d: d["classify"].pop("only_right"))
    check("missing_classification" in r.codes(), f"missing label: {sorted(r.codes())}")
    r = probe(lambda d: d["classify"].update(only_right=d["classify"]["only_left"]))
    check("duplicate_classification" in r.codes(), f"shared label: {sorted(r.codes())}")
    r = probe(lambda d: d.update(output_order="whatever_order_it_built"))
    check("unknown_output_order" in r.codes(), f"order: {sorted(r.codes())}")
    r = probe(lambda d: d.update(on_duplicate_key="deduplicate"))
    check("unknown_policy" in r.codes(),
          f"an absent policy must be REFUSED, not quietly accepted: {sorted(r.codes())}")

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text('{"users": ["not an object"]}', encoding="utf-8")
        m = task_model.parse({**raw, "sources": {
            **raw["sources"],
            "actual": {"path": bad.name, "collection": "users"}}})
        r2 = validate(m, Path(td))
        seen |= r2.codes()
        check("malformed_data_file" in r2.codes(), f"element shape: {sorted(r2.codes())}")

    untested = sorted(set(BODY_PROBLEM_CODES) - seen)
    check(not untested, f"declared but unexercised body problem codes: {untested}")

    # The point of this task, asserted rather than left implicit.
    check("on_non_numeric" not in json.dumps(raw),
          "this task must have NO on_non_numeric policy -- its absence is the "
          "evidence the fourth shape exists to provide")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print(f"SELF-TEST PASSED (shipped model valid / all {len(BODY_PROBLEM_CODES)} body "
          f"codes exercised / self-reconciliation refused / a shared classification "
          f"label refused / NO on_non_numeric policy anywhere)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
