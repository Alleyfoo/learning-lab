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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / "taskmodel"))

from task_model import (  # noqa: E402
    Problem, Report, TaskModel, TaskType, load_collection, register,
    validate as validate_envelope,
)

# Two relation sets, and WHICH ONE applies is decided by whether the model
# declares attribute comparison. A model that compares attributes but still
# reports a flat `both` would hide every difference it just went looking for --
# so the pairing is enforced rather than left to the author's care.
RELATIONS_KEY_ONLY = ("both", "only_left", "only_right")
RELATIONS_COMPARED = ("both_same", "both_different", "only_left", "only_right")

# How a compared attribute is compared. DECLARED, never assumed: whether
# `alice@X` equals `alice@x` is a property of the job, not of the executor.
# PRO-2 instance 9 is the precedent -- normalisation is something a construct
# declares, and the default is to preserve.
COMPARISONS = ("exact", "trim", "casefold", "trim_casefold", "within")

# `within` is the only comparison with numeric semantics, and it is what gives
# this task a reason to want a non-numeric policy at all. That reason arrived
# because the JOB needed it -- a reconciliation of balances cannot be done by
# string equality -- not because the other numeric tasks have one.
NUMERIC_COMPARISONS = ("within",)

# What may happen when a numerically-compared operand is not a number. The unit
# here is a KEY, not a row: this task's output is one row per key in the union,
# so "refuse_row" would name a thing that does not exist. Same idea as
# enrichment's and aggregation's policy, different unit -- which is itself
# evidence about how reusable the idea is.
NON_NUMERIC_POLICIES = ("refuse_run", "refuse_key")

OUTPUT_ORDERS = ("left_then_right", "sorted_by_key")

# What may happen when one side carries a key more than once. `deduplicate` and
# `separate_records` are DELIBERATELY ABSENT: both silently change what the data
# says, and following the enrichment precedent, a policy that quietly discards or
# multiplies rows must be a NAMED policy with its own evidence before it exists.
DUPLICATE_POLICIES = ("refuse_run", "refuse_key")

REFUSALS = ("DUPLICATE_KEY", "MISSING_MATCH_KEY", "NON_NUMERIC_OPERAND")

BODY_PROBLEM_CODES = (
    "missing_key",
    "unknown_comparison",
    "duplicate_compare_field",
    "classify_split_mismatch",
    "comparison_tolerance_mismatch",
    "malformed_tolerance",
    "policy_comparison_mismatch",
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


def compare_of(model: TaskModel) -> tuple[dict, ...]:
    """Declared attribute comparisons, in order, as raw dicts."""
    return tuple(dict(c) for c in (model.body.get("compare") or ()))


def compares_numerically(model: TaskModel) -> bool:
    return any(c.get("comparison") in NUMERIC_COMPARISONS for c in compare_of(model))


def on_non_numeric(model: TaskModel) -> str:
    return str(model.body.get("on_non_numeric", ""))


def compares_attributes(model: TaskModel) -> bool:
    return bool(model.body.get("compare"))


def relations_for(model: TaskModel) -> tuple[str, ...]:
    return RELATIONS_COMPARED if compares_attributes(model) else RELATIONS_KEY_ONLY


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

    # --- declared attribute comparison ---------------------------------------
    compares = compare_of(model)
    seen_fields: set[str] = set()
    for i, spec in enumerate(compares):
        field, how = str(spec.get("field", "")), str(spec.get("comparison", ""))
        cwhere = f"{where}:compare[{i}]"

        # PAIRING, both directions: `within` needs a tolerance and nothing else
        # may carry one. A tolerance on a casefold comparison implies a
        # numeric reading that is never applied.
        tolerance = spec.get("tolerance")
        if how in NUMERIC_COMPARISONS and tolerance is None:
            problems.append(Problem("comparison_tolerance_mismatch", cwhere,
                                    f"{how!r} needs a declared tolerance"))
        if how not in NUMERIC_COMPARISONS and tolerance is not None:
            problems.append(Problem(
                "comparison_tolerance_mismatch", cwhere,
                f"{how!r} takes no tolerance, but {tolerance!r} was given -- it "
                f"implies a numeric reading that is never applied"))
        if tolerance is not None:
            try:
                value = Decimal(str(tolerance))
            except (InvalidOperation, ValueError, ArithmeticError):
                problems.append(Problem("malformed_tolerance", cwhere, repr(tolerance)))
            else:
                if value < 0:
                    problems.append(Problem("malformed_tolerance", cwhere,
                                            f"{tolerance!r} is negative"))
        if not field:
            problems.append(Problem("missing_key", cwhere, "field"))
        elif field in seen_fields:
            problems.append(Problem("duplicate_compare_field", cwhere, field))
        else:
            seen_fields.add(field)
        if how not in COMPARISONS:
            problems.append(Problem("unknown_comparison", cwhere, how))
        # A compared attribute must exist on BOTH sides. Comparing a field only
        # one source has would report every matched pair as different for a
        # reason that is about the schema, not the data.
        for label, name in (("left", lname), ("right", rname)):
            if field and name in columns and field not in columns[name]:
                problems.append(Problem("field_not_in_source", cwhere,
                                        f"{name}.{field} ({label})"))

    # Every relation must be given a label, and no two may share one -- a shared
    # label makes the output unreadable, which is worse than an absent one.
    # WHICH relations are required depends on whether attributes are compared.
    relations = relations_for(model)
    labels = classify(model)
    for relation in relations:
        if not labels.get(relation):
            problems.append(Problem("missing_classification", f"{where}:classify",
                                    relation))
    stray = sorted(set(labels) - set(relations))
    if stray:
        problems.append(Problem(
            "classify_split_mismatch", f"{where}:classify",
            f"declares {stray} but {'compares attributes' if compares else 'does not compare attributes'}, "
            f"so the relations are {list(relations)}. A model that compares "
            f"attributes and still reports a flat `both` would hide every "
            f"difference it went looking for"))

    seen: dict[str, str] = {}
    for relation, label in labels.items():
        if relation not in relations:
            continue                       # already reported as classify_split_mismatch
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

    # PAIRING: the non-numeric policy exists if and only if something is compared
    # numerically. Required so the policy's PRESENCE stays attributable -- it is
    # here because this job compares balances, not because two other tasks have
    # one.
    policy = on_non_numeric(model)
    numeric = compares_numerically(model)
    if numeric and not policy:
        problems.append(Problem(
            "policy_comparison_mismatch", where,
            "a numeric comparison is declared, so on_non_numeric must say what "
            "happens when an operand is not a number"))
    if policy and not numeric:
        problems.append(Problem(
            "policy_comparison_mismatch", where,
            f"on_non_numeric={policy!r} is declared but nothing is compared "
            f"numerically, so the policy could never apply"))
    if policy and policy not in NON_NUMERIC_POLICIES:
        problems.append(Problem("unknown_policy", f"{where}:on_non_numeric", policy))

    return problems


TASK = register(TaskType(name="reconciliation", refusals=REFUSALS,
                         validate_body=validate_body,
                         body_problem_codes=BODY_PROBLEM_CODES))


def constructs(model: TaskModel) -> tuple[str, ...]:
    """Executable constructs this body GENUINELY contains, as semantic referents.

    Not paths. A path can name a thing that merely sounds like the requirement --
    `classify.both_different` is a LABEL, and a manifest that accepted it as
    discharge for "show me where the amounts differ" would pass a model with no
    comparison in it at all. That happened, which is why this exists.

    A referent appears only when the construct that delivers it is present:

    ```text
    match_binding                  a key is bound on both sides
    peer_presence_classification   presence on one side only is reported
    difference_classification      same/different is reported -- ONLY alongside
                                   an actual comparison
    compare:<field>                that field is really compared
    ```

    Removing `compare` removes every `compare:<field>` referent and the
    difference classification with them, however the labels are named.
    """
    out: list[str] = []
    match = model.body.get("match_on") or {}
    if match.get("left_field") and match.get("right_field"):
        out.append("match_binding")

    classify = model.body.get("classify") or {}
    if classify.get("only_left") and classify.get("only_right"):
        out.append("peer_presence_classification")

    compares = compare_of(model)
    for spec in compares:
        field = str(spec.get("field", ""))
        if field:
            out.append(f"compare:{field}")
    # The difference classification is only real when something is compared.
    # Labels alone do not make a model report differences.
    if compares and classify.get("both_same") and classify.get("both_different"):
        out.append("difference_classification")
    return tuple(out)


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

    # --- v2: declared attribute comparison -----------------------------------
    v2raw = json.loads((base / "models" / "reconciliation_v2.json").read_text(encoding="utf-8"))
    rep2 = validate(task_model.parse(v2raw), base)
    seen |= rep2.codes()
    check(rep2.valid, f"the v2 model must validate: {[str(x) for x in rep2.problems]}")

    def probe2(mutate) -> Report:
        bad = copy.deepcopy(v2raw)
        mutate(bad)
        r = validate(task_model.parse(bad), base)
        seen.update(r.codes())
        return r

    r = probe2(lambda d: d["compare"][0].update(comparison="approximately"))
    check("unknown_comparison" in r.codes(), f"comparison: {sorted(r.codes())}")
    r = probe2(lambda d: d["compare"].append(dict(d["compare"][0])))
    check("duplicate_compare_field" in r.codes(), f"duplicate field: {sorted(r.codes())}")
    r = probe2(lambda d: d["compare"][0].update(field="colour"))
    check("field_not_in_source" in r.codes(), f"compared field absent: {sorted(r.codes())}")

    # The PAIRING, both directions. This is the load-bearing rule of v2.
    r = probe2(lambda d: d.update(classify={"both": "BOTH", "only_left": "L",
                                            "only_right": "R"}))
    check("classify_split_mismatch" in r.codes(),
          f"comparing attributes while reporting a flat `both` would hide every "
          f"difference: {sorted(r.codes())}")
    r = probe(lambda d: d.update(classify={"both_same": "S", "both_different": "D",
                                           "only_left": "L", "only_right": "R"}))
    check("classify_split_mismatch" in r.codes(),
          f"reporting SAME vs DIFFERENT while comparing nothing is meaningless: "
          f"{sorted(r.codes())}")

    # --- v3: tolerance-based numeric comparison ------------------------------
    v3raw = json.loads((base / "models" / "reconciliation_v3.json").read_text(encoding="utf-8"))
    rep3 = validate(task_model.parse(v3raw), base)
    seen |= rep3.codes()
    check(rep3.valid, f"the v3 model must validate: {[str(x) for x in rep3.problems]}")

    def probe3(mutate) -> Report:
        bad = copy.deepcopy(v3raw)
        mutate(bad)
        r = validate(task_model.parse(bad), base)
        seen.update(r.codes())
        return r

    # PAIRING 1: `within` <-> tolerance, both directions.
    r = probe3(lambda d: d["compare"][1].pop("tolerance"))
    check("comparison_tolerance_mismatch" in r.codes(),
          f"`within` without a tolerance: {sorted(r.codes())}")
    r = probe3(lambda d: d["compare"][0].update(tolerance="0.01"))
    check("comparison_tolerance_mismatch" in r.codes(),
          f"a tolerance on an `exact` comparison implies a numeric reading that "
          f"is never applied: {sorted(r.codes())}")

    r = probe3(lambda d: d["compare"][1].update(tolerance="a bit"))
    check("malformed_tolerance" in r.codes(), f"unparseable tolerance: {sorted(r.codes())}")
    r = probe3(lambda d: d["compare"][1].update(tolerance="-0.01"))
    check("malformed_tolerance" in r.codes(), f"negative tolerance: {sorted(r.codes())}")

    # PAIRING 2: numeric comparison <-> non-numeric policy, both directions.
    # This is what keeps the policy's PRESENCE attributable.
    r = probe3(lambda d: d.pop("on_non_numeric"))
    check("policy_comparison_mismatch" in r.codes(),
          f"a numeric comparison with no policy for non-numeric operands: "
          f"{sorted(r.codes())}")
    r = probe2(lambda d: d.update(on_non_numeric="refuse_key"))
    check("policy_comparison_mismatch" in r.codes(),
          f"a policy that could never apply, because nothing is compared "
          f"numerically: {sorted(r.codes())}")
    r = probe3(lambda d: d.update(on_non_numeric="refuse_row"))
    check("unknown_policy" in r.codes(),
          f"this task's unit is a KEY, not a row -- `refuse_row` names something "
          f"that does not exist here: {sorted(r.codes())}")

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
    print(f"SELF-TEST PASSED (v1, v2 and v3 models valid / all {len(BODY_PROBLEM_CODES)} "
          f"body codes exercised / self-reconciliation refused / a shared "
          f"classification label refused / classify-vs-compare pairing enforced in "
          f"BOTH directions / tolerance and policy pairings enforced both ways / "
          f"`refuse_row` refused because this task's unit is a KEY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
