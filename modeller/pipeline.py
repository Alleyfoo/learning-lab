#!/usr/bin/env python3
"""The staged path from local data and a sentence to a deterministic worker.

```text
LOCAL DATA
    -> PROGRAMMATIC OBSERVER   measured OBSERVED facts only   inspector/observe.py
    -> LLM INSPECTOR           INFERRED / UNKNOWN, addressed  experimentW boundary
    -> TASK DEFINER            proposes the model, or blocks  experimentY rule
    -> SUFFICIENCY POLICY      sufficient -> continue
                               insufficient -> ask for the exact missing truth
    -> TASK MODEL
    -> DETERMINISTIC VALIDATOR builder.validate_raw
    -> DETERMINISTIC EXECUTOR  builder.preview
```

Nothing here is new machinery. Every stage calls a component that was frozen and
evidenced elsewhere; this module is the wiring and the human-facing shaping.

## What this module may not do

The LLM does not enrich anything, does not decide a runtime value, and cannot
emit `OBSERVED` or `CONFIRMED` — the last is structural, not a rule it is asked
to respect (`experimentW/harness/boundary.py`). The program computes the
sufficiency verdict itself rather than trusting the definer's word for it, so a
definer that proceeds on an insufficient binding is caught rather than obeyed.

## Selective autonomy is the behaviour under test

Experiment Y established it and this module must not weaken it: **ask only when
the local evidence cannot establish a load-bearing fact.** A UI that asks for the
join key every time would pass every safety check and be worthless.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "inspector"))

import builder  # noqa: E402
import manifest as manifest_mod  # noqa: E402
import observe  # noqa: E402


def _load(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


boundary = _load("_w_boundary", LAB / "experimentW" / "harness" / "boundary.py")
_w_run = _load("_w_run", LAB / "experimentW" / "harness" / "run_W.py")

# Task types the modeller can build.
#
# Structure ELIMINATES shapes that cannot be expressed; it does not pick the
# task. With one collection there is nothing to join, so enrichment is
# inexpressible and aggregation is what remains -- but "one collection means
# aggregation" is NOT a rule. A one-sheet job might be "calculate margin for
# every row", and a two-source job might aggregate after a join. Promoting
# workbook count to task semantics would be inventing meaning from a count.
TASKS = ("enrichment", "aggregation", "reconciliation")
TASK = "enrichment"          # kept for callers that model enrichment directly


def expressible(chosen) -> tuple:
    """Task shapes the selected sources could support. Eliminating, not choosing.

    One collection cannot be joined or compared, so only aggregation survives.
    Two can be either joined (enrichment) or compared (reconciliation), and
    **structure cannot tell those apart** -- both want two collections and a
    key. Which one is intended is a fact about the DELIVERABLE, and the only
    place that exists is what the person asked for.
    """
    return ("aggregation",) if len(chosen) < 2 else ("enrichment",
                                                     "reconciliation")


def task_for(chosen) -> str:
    """The remaining shape when only one is expressible.

    With more than one expressible, the choice is a modelling decision and this
    returns the first -- a place where the modeller currently decides too little,
    recorded rather than papered over.
    """
    return expressible(chosen)[0]


# ---------------------------------------------------------------------------
# 1. data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Workspace:
    """A directory of data files, and the base a model's paths resolve against."""
    label: str
    base: Path
    rel: str            # directory relative to base, e.g. "fixtures/A"

    @property
    def directory(self) -> Path:
        return self.base / self.rel


def workspaces() -> list[Workspace]:
    """Every directory of JSON collections this modeller can currently reach."""
    out = [Workspace("enrichment fixtures", LAB / "enrichment", "fixtures")]
    ydir = LAB / "experimentY" / "fixtures"
    for sub in sorted(p.name for p in ydir.glob("*") if p.is_dir()):
        out.append(Workspace(f"experiment Y - condition {sub}",
                             LAB / "experimentY", f"fixtures/{sub}"))
    ddir = LAB / "data"
    if ddir.is_dir():
        for sub in sorted(p.name for p in ddir.glob("*") if p.is_dir()):
            out.insert(0, Workspace(sub, LAB / "data", sub))
    xdir = LAB / "experimentX" / "fixtures"
    if xdir.is_dir():
        out.append(Workspace("experiment X - ambiguous join", LAB / "experimentX",
                             "fixtures"))
    return [w for w in out if w.directory.is_dir()]


@dataclass(frozen=True)
class SourceFile:
    filename: str
    collection: str
    rows: int
    fields: tuple[str, ...]


def sources_in(ws: Workspace) -> list[SourceFile]:
    out = []
    for path in sorted(ws.directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, value in data.items():
            if key.startswith("_") or not isinstance(value, list) or not value:
                continue
            out.append(SourceFile(path.name, key, len(value),
                                  tuple(sorted(value[0]))))
    return out


def source_spec(ws: Workspace, chosen: list[SourceFile]) -> dict:
    return {s.collection: {"path": f"{ws.rel}/{s.filename}",
                           "collection": s.collection} for s in chosen}


# ---------------------------------------------------------------------------
# 2. programmatic observation — the program owns OBSERVED
# ---------------------------------------------------------------------------

def observed_facts(ws: Workspace, chosen: list[SourceFile]) -> list[dict]:
    """Measured facts for the SELECTED sources only."""
    keep = {s.collection for s in chosen}
    return [c for c in observe.observed_claims(ws.directory)
            if _touches(c["claim"], keep)]


def _touches(claim: dict, collections: set) -> bool:
    if "candidate_relationship" in claim:
        rel = claim["candidate_relationship"]
        return all(side.split(".")[0] in collections
                   for side in (rel["left"], rel["right"]))
    return claim.get("source") in collections


def relationships(observed: list[dict]) -> list[dict]:
    return [c["claim"]["candidate_relationship"] for c in observed
            if "candidate_relationship" in c["claim"]]


# ---------------------------------------------------------------------------
# 3. the sufficiency policy — Experiment Y, computed by the program
# ---------------------------------------------------------------------------

def _complete(coverage: str) -> bool:
    left, _, right = coverage.partition("/")
    return left == right


def sufficiency(observed: list[dict], left: str) -> dict:
    """Y's policy, applied to the program's own measurements.

    > A candidate relationship is MECHANICALLY SUFFICIENT when it is the SOLE
    > candidate for that left field having BOTH complete left coverage AND
    > unique right-side keys.
    """
    candidates = [r for r in relationships(observed) if r["left"] == left]
    sufficient = [r for r in candidates
                  if _complete(r["left_coverage"]) and r["right_unique"]]
    return {"left": left, "candidates": candidates, "sufficient": sufficient,
            "established": len(sufficient) == 1,
            "verdict": ("established" if len(sufficient) == 1 else
                        "ambiguous" if len(sufficient) > 1 else "unsupported")}


def join_left_candidates(observed: list[dict]) -> list[str]:
    return sorted({r["left"] for r in relationships(observed)})


# ---------------------------------------------------------------------------
# 4. LLM inspection and task definition — the ONLY LLM stages
# ---------------------------------------------------------------------------

Ask = Callable[[str], str]

BASIS_KINDS = boundary.BASIS_KINDS

INSPECT_PROMPT = """You are the INTERPRETATION stage of a two-stage inspector.

A program has already inspected the data and produced the OBSERVED facts below by
reading the source structure directly: field names, value kinds, example values,
distinct counts, and — for each pair of fields across two sources — a
`candidate_relationship` reporting how much of the left field's values appear on
the right (`left_coverage`) and whether the right field identifies at most one row
per value (`right_unique`). Those are measurements. The program does not say which
pairing is intended.

--- BEGIN OBSERVED FACTS ---
{observed}
--- END OBSERVED FACTS ---

THE JOB the person wants:
{goal}

Say what this data probably MEANS for that job, and be honest about what cannot
be settled from it.

THE ONLY STATUSES AVAILABLE TO YOU:
  INFERRED   your interpretation. Must carry the basis it rests on.
  UNKNOWN    you have no supported interpretation.

BASIS IS A CLOSED VOCABULARY, drawn from exactly these kinds:
{basis_kinds}

EVERY CLAIM MUST NAME ITS SUBJECT — UNKNOWN as much as INFERRED. `source` is
required; `field` is required but may be null for a whole-collection question.
Where a claim concerns a relationship between two collections, `source` may be a
list of both.

Return a JSON list of claims and nothing else:
{shape}"""

SHAPE = [
    {"claim": {"source": "<collection>", "field": "<field, or null>",
               "meaning": "<what you think it means>"},
     "status": "INFERRED", "basis": ["<kinds from the list>"]},
    {"claim": {"source": "<collection, or a list>", "field": "<field, or null>",
               "question": "<what you cannot settle>"},
     "status": "UNKNOWN", "note": "<why>"},
]

# U2's rule with Y's sufficiency policy, verbatim from experimentY.
RULE = """A load-bearing binding may not be established from an INFERRED or UNKNOWN
claim without either independent evidence or explicit human confirmation.

Independent evidence may NOT reuse anything already listed in that claim's
`basis`, and may NOT substitute different evidence of the same KIND:

  - Naming evidence is ONE kind. A field name and a collection name are not
    independent of each other. Two names do not add up to a fact.
  - Value-kind and example evidence establish what values ARE, never what a
    field MEANS.
  - Independent evidence means: documentation, another trusted source, explicit
    human confirmation, or the mechanical sufficiency defined below.

The key a lookup joins on IS a load-bearing binding: it decides which reference
row supplies the output.

MECHANICAL SUFFICIENCY FOR A RELATIONSHIP BINDING:

A candidate relationship is MECHANICALLY SUFFICIENT when it is the SOLE candidate
for that left field having BOTH complete left coverage AND unique right-side keys.

A mechanically sufficient candidate IS established, by OBSERVED evidence. Use it,
and do NOT ask a human to confirm it.

If two or more candidates for the same left field are mechanically sufficient, or
none is, the binding is NOT established: block and ask which is intended.

A claim marked CONFIRMED is settled. Confirmation resolves that ONE claim and
nothing else -- it does not make neighbouring inferences trustworthy."""

BLOCK_SHAPE = {"CANNOT_ESTABLISH": [
    {"source": "<collection, or a list>", "field": "<field, or null>",
     "binding": "<what you cannot establish>",
     "claim_status": "<status of the claim it would rest on>",
     "question": "<the question a human must answer>"}]}



AGGREGATION_SKELETON = {
    "model_version": 1, "model_id": "...", "task": "aggregation",
    "sources": {}, "driving_source": "...",
    "group_by": ["... one or more fields to group by ..."],
    "group_order": "first_appearance",
    "aggregates": [{"target": "...", "op": "count"},
                   {"target": "...", "op": "sum", "field": "..."}],
    "select": [{"field": "...", "op": "starts_with", "value": "..."}],
    "on_non_numeric": "refuse_row",
}

AGGREGATION_RULES = """PERMITTED VALUES:
  driving_source        the single collection
  group_by              one or more of its fields
  group_order           "first_appearance" or "sorted"
  aggregates[].op       "count" or "sum"; `sum` also needs `field`
  select[].op           "equals" or "starts_with"
  on_non_numeric        "refuse_row" or "refuse_run"

ROW SELECTION IS PART OF THE MODEL. If the person asked for a period -- "this
month", "June" -- declare it in `select`. `starts_with` on an ISO date is how a
month is expressed; there is no date arithmetic. If they asked for no period,
omit `select` entirely rather than inventing one. Never assume the file has
already been narrowed for you: a total over rows nobody declared is a total
nobody can check."""


def aggregation_prompt(report: list[dict], goal: str, sources: dict,
                       resumed: bool = False) -> str:
    skeleton = json.loads(json.dumps(AGGREGATION_SKELETON))
    skeleton["sources"] = sources
    skeleton["driving_source"] = next(iter(sources), "...")
    resume = (chr(10) + "A human has since answered your questions. Those "
              "claims are now CONFIRMED above; nothing else changed." + chr(10)
              ) if resumed else ""

    return f"""An inspection produced the claims below. You did not perform it and cannot
see the data yourself.

--- BEGIN INSPECTION CLAIMS ---
{json.dumps(report, indent=2, ensure_ascii=False)}
--- END INSPECTION CLAIMS ---
{resume}
THE JOB the person wants, in their words:
{goal}

THE RULE YOU MUST FOLLOW:
{RULE}

Only claims the job's decisions depend on are load-bearing. Judge which.

WHAT THE DETERMINISTIC EXECUTOR ALREADY DOES, so do not ask about it:
  - Arithmetic is exact decimal. Values are emitted as the source wrote them.
  - Group order is declared, never incidental.
  - A value that must be numeric and is not is refused under `on_non_numeric`.
  - Rows excluded by `select` are counted and reported, never dropped silently.

If every load-bearing binding is supported, return ONLY the model definition:
{json.dumps(skeleton, indent=2)}

{AGGREGATION_RULES}

If a load-bearing binding is NOT supported, do NOT produce a model. Return ONLY:
{json.dumps(BLOCK_SHAPE, indent=2)}"""


SHAPES = {
    "enrichment": ("Takes each row of one collection and ADDS fields to it by "
                   "looking up a matching row in the other. The deliverable is "
                   "the first collection, enlarged. Rows with no match are a "
                   "problem to be refused under a declared policy."),
    "reconciliation": ("COMPARES two collections and reports how they differ: "
                       "what is in both, what is only on the left, what is only "
                       "on the right. The deliverable IS the disagreement. Rows "
                       "with no match are the answer, not an error."),
}


def choose_prompt(goal: str, order: tuple) -> str:
    joiner = chr(10) + chr(10)
    shapes = joiner.join(f"  {name}" + chr(10) + f"      {SHAPES[name]}" for name in order)
    return f"""A person has data and a job they want done. Two task shapes could be built
from data of this shape, and the data cannot tell them apart -- both join two
collections on a key. Only what the person ASKED FOR can decide.

WHAT THEY SAID:
{goal}

THE TWO SHAPES:

{shapes}

Answer with ONE of these and nothing else:

{{"TASK": "{order[0]}"}}
{{"TASK": "{order[1]}"}}

If what they said genuinely does not distinguish the two -- if it could
reasonably mean either -- do NOT guess. Return only:

{{"CANNOT_ESTABLISH": [{{"question": "<one question that would settle which
deliverable they want>"}}]}}"""


def choose_task(goal: str, candidates: tuple, ask: Ask):
    """Pick among structurally possible shapes from the STATED PURPOSE.

    Returns `(task, None)` or `(None, question)`.

    Deliberately not decided from the data. Overlap of 3/4 between a statement
    and a ledger is not evidence for reconciliation -- it is what a
    reconciliation exists to report, and an enrichment over the same files would
    show the same 3/4. Reading intent off coverage would make the deliverable a
    function of how messy the month was.
    """
    if len(candidates) == 1:
        return candidates[0], None

    def _once(order):
        text = ask(choose_prompt(goal, order))
        for obj in _w_run._objects(text):
            if isinstance(obj, dict) and obj.get("TASK") in candidates:
                return obj["TASK"], None
        block = _w_run.block_of(text)
        return None, (block[0].get("question") if block else None)

    # THE GATE. The shapes are presented in both orders and the answer must
    # hold. If the words decided it, order is irrelevant; if the answer flips,
    # position decided it and the goal did not -- so the person is asked.
    # Same technique the executors are graded with: permute the declaration and
    # require the outcome to follow.
    forward, q1 = _once(candidates)
    backward, q2 = _once(tuple(reversed(candidates)))
    if forward and forward == backward:
        return forward, None
    if forward != backward and forward and backward:
        return None, ("Do you want the statement rows enlarged with matching "
                      "ledger data, or a report of how the two disagree? What "
                      "you asked for could reasonably mean either.")
    return None, (q1 or q2 or
                  "Do you want the rows enlarged with matching data, or a "
                  "report of how the two disagree?")


RECONCILIATION_SKELETON = {
    "model_version": 1, "model_id": "...", "task": "reconciliation",
    "sources": {}, "left": "...", "right": "...",
    "match_on": {"left_field": "...", "right_field": "..."},
    "classify": {"both": "...", "only_left": "...", "only_right": "..."},
    "output_order": "left_then_right",
    "on_duplicate_key": "refuse_run",
}

# The same skeleton when the person asked to see WHERE VALUES DIFFER. The
# construct is not new -- `compare` and the four-way classification already
# exist in the reconciliation language. What was missing was the modeller
# producing them when the request asked for them, so a stated "or where the
# amounts differ" quietly became a plain matched/missing report.
RECONCILIATION_COMPARED_SKELETON = {
    "model_version": 1, "model_id": "...", "task": "reconciliation",
    "sources": {}, "left": "...", "right": "...",
    "match_on": {"left_field": "...", "right_field": "..."},
    "compare": [{"field": "...", "comparison": "exact"}],
    "classify": {"both_same": "...", "both_different": "...",
                 "only_left": "...", "only_right": "..."},
    "output_order": "left_then_right",
    "on_duplicate_key": "refuse_run",
}


def reconciliation_prompt(report: list[dict], goal: str, sources: dict,
                          resumed: bool = False) -> str:
    skeleton = json.loads(json.dumps(RECONCILIATION_SKELETON))
    compared = json.loads(json.dumps(RECONCILIATION_COMPARED_SKELETON))
    names = list(sources)
    for shape in (skeleton, compared):
        shape["sources"] = sources
        shape["left"], shape["right"] = (names + ["...", "..."])[:2]
    resume = (chr(10) + "A human has since answered your questions. Those "
              "claims are now CONFIRMED above; nothing else changed." + chr(10)
              ) if resumed else ""
    return f"""An inspection produced the claims below. You did not perform it and cannot
see the data yourself.

--- BEGIN INSPECTION CLAIMS ---
{json.dumps(report, indent=2, ensure_ascii=False)}
--- END INSPECTION CLAIMS ---
{resume}
THE JOB the person wants, in their words:
{goal}

THE RULE YOU MUST FOLLOW:
{RULE}

Only claims the job's decisions depend on are load-bearing. Judge which.

WHAT THE DETERMINISTIC EXECUTOR ALREADY DOES, so do not ask about it:
  - Every row of both sides is classified and reported. Rows present on only
    one side are the OUTPUT, never an error.
  - Values are emitted exactly as the source wrote them.
  - Output order is declared, never incidental.
  - A duplicated key is handled by `on_duplicate_key`.

INCOMPLETE OVERLAP IS NOT A PROBLEM HERE. A key present on one side and not the
other is precisely what this task reports, so do not block on coverage.

MATCHING ON A KEY IS NOT THE WHOLE DELIVERABLE. Read what they asked for. If
they asked to see where VALUES DIFFER between the two sides -- "where the
amounts differ", "which totals disagree" -- then a key that appears on both
sides with different values must be reported as different, and reporting it as
merely matched would drop half of what they asked for.

If they asked ONLY what is missing from either side, do NOT declare `compare`.
Numeric columns being present is not a reason to compare them; the request is.

If they asked to see differing values, return this shape:
{json.dumps(compared, indent=2)}

Otherwise return this one:
{json.dumps(skeleton, indent=2)}

PERMITTED VALUES:
  left, right          one of {json.dumps(names)}
  match_on             a field on each side; they may be named differently
  compare[].field      ONE field name, present on BOTH sides with the same
                       name. A field named differently on each side cannot be
                       compared by this construct.
  compare[].comparison "exact", "trim", "casefold", "trim_casefold", or
                       "within" (numeric, and then `tolerance` is required and
                       `on_non_numeric` must be "refuse_run" or "refuse_key")
  classify             WITHOUT compare: both / only_left / only_right
                       WITH compare:    both_same / both_different /
                                        only_left / only_right
  output_order         "left_then_right" or "sorted_by_key"
  on_duplicate_key     "refuse_run" or "refuse_key"

If a load-bearing binding is NOT supported, do NOT produce a model. Return ONLY:
{json.dumps(BLOCK_SHAPE, indent=2)}"""

def inspect_prompt(observed: list[dict], goal: str) -> str:
    return INSPECT_PROMPT.format(
        observed=json.dumps(observed, indent=2, ensure_ascii=False), goal=goal,
        basis_kinds=json.dumps(list(BASIS_KINDS), indent=2),
        shape=json.dumps(SHAPE, indent=2))


def define_prompt(report: list[dict], goal: str, sources: dict,
                  resumed: bool = False, deferred: Optional[list] = None) -> str:
    skeleton = {
        "model_version": 1, "model_id": "...", "task": "enrichment",
        "sources": sources, "driving_source": "...",
        "lookup": {"into": "...", "match_left": "...", "match_right": "...",
                   "on_missing": "...", "on_ambiguous": "..."},
        "outputs": ["... one entry per column the person asked for ..."],
        "on_non_numeric": "..."}
    resume = ("\nA human has since answered your questions. Those claims are now "
              "CONFIRMED above; nothing else changed.\n") if resumed else ""
    return f"""An inspection produced the claims below. You did not perform it and cannot
see the data yourself.

  OBSERVED   directly established from the source representation
  INFERRED   the inspector's interpretation, with what it inferred from
  UNKNOWN    no supported interpretation, naming the subject it is about
  CONFIRMED  an external authority resolved an inference or an unknown

--- BEGIN INSPECTION CLAIMS ---
{json.dumps(report, indent=2, ensure_ascii=False)}
--- END INSPECTION CLAIMS ---
{resume}
THE JOB the person wants, in their words:
{goal}

WHAT THE DETERMINISTIC EXECUTOR ALREADY DOES. These are facts about the runtime
you are writing for, not choices, so do not ask about them:

  - Arithmetic is exact decimal. There is no rounding, no currency conversion
    and no locale handling. A value that must be numeric is CHECKED, never
    rewritten, and is emitted exactly as the source wrote it.
  - `compute.op` may only be "multiply". There is no other operation available,
    so the shape of any computation is fixed: two declared operands, multiplied.
  - Every field of the driving source is preserved in the output automatically,
    ahead of the columns you declare. You do not need to add identity columns
    and should not ask whether to.
  - An operand that turns out not to be numeric is refused under
    `on_non_numeric`. Nothing is silently coerced.

THE RULE YOU MUST FOLLOW:
{RULE}

Only claims the job's decisions depend on are load-bearing. Judge which.

If every load-bearing binding is supported, return ONLY the model definition:
{json.dumps(skeleton, indent=2)}

An output entry is either a passthrough or a computation:
{json.dumps([{"target": "<column name>", "from": "<source>", "field": "<field>",
              "type": "number (only if it must be numeric)"},
             {"target": "<column name>",
              "compute": {"op": "multiply",
                          "left": {"from": "<source>", "field": "<field>"},
                          "right": {"from": "<source>", "field": "<field>"}}}],
            indent=2)}

PERMITTED VALUES:
  driving_source, lookup.into   one of {json.dumps(sorted(sources))}
  lookup.match_left             a field of the driving source
  lookup.match_right            a field of the looked-up source
  on_missing, on_ambiguous      "refuse_row" or "refuse_run"
  on_non_numeric                "refuse_row" or "refuse_run"
  compute.op                    "multiply"

If a load-bearing binding is NOT supported, do NOT produce a model. Return ONLY:
{json.dumps(BLOCK_SHAPE, indent=2)}"""


def interpret(observed: list[dict], goal: str, ask: Ask) -> tuple[list[dict], dict]:
    """LLM inspection, through the boundary that cannot carry OBSERVED."""
    raw = _w_run.claim_list(ask(inspect_prompt(observed, goal)))
    ingested = boundary.ingest(raw if raw is not None else [])
    return boundary.merge(observed, ingested), ingested.as_dict()


MANIFEST_ASK = """

ALSO RETURN A DELIVERABLE MANIFEST alongside the model, as a second JSON object.
The person's request was broken into these obligations, and every one must be
accounted for before this can be established:

{obligations}

{{"MANIFEST": {{"o1": {{"via": "construct", "construct": "<one referent from the
list below>"}}}}}}

`via` is "construct", "question" or "unsupported"; "unsupported" also needs a
`reason`.

A construct referent is CHECKED against what the task reports its body genuinely
contains, so naming one you did not build fails. A label is not a construct:
declaring a `both_different` classification does not by itself compare
anything."""


def with_manifest(prompt: str, obligations_list: list) -> str:
    """Ask for the manifest alongside the model, never instead of it."""
    if not obligations_list:
        return prompt
    listed = chr(10).join(f"  {o['id']}: {o['clause']}" for o in obligations_list)
    return prompt + MANIFEST_ASK.format(obligations=listed)


def manifest_of(text: str):
    for obj in _w_run._objects(text):
        if isinstance(obj, dict) and isinstance(obj.get("MANIFEST"), dict):
            return obj["MANIFEST"]
    return None


_LAST_MANIFEST: dict = {"value": None}


def define(report: list[dict], goal: str, sources: dict, ask: Ask,
           resumed: bool = False, deferred: Optional[list] = None,
           observed: Optional[list[dict]] = None, task: str = "enrichment",
           obligations_list: Optional[list[dict]] = None
           ) -> tuple[Optional[dict], Optional[list]]:
    if task == "aggregation":
        prompt = aggregation_prompt(report, goal, sources, resumed)
    elif task == "reconciliation":
        prompt = reconciliation_prompt(report, goal, sources, resumed)
    else:
        prompt = define_prompt(report, goal, sources, resumed, deferred)
    text = ask(with_manifest(prompt, obligations_list or []))
    _LAST_MANIFEST["value"] = manifest_of(text)
    block = _w_run.block_of(text)
    if block is not None:
        return None, block
    node = _node_of(text)
    if node is not None and task in ("aggregation", "reconciliation"):
        node["sources"] = json.loads(json.dumps(sources))
        node["task"] = task
        return node, None
    if node is not None:
        # The person SELECTED these files. Restating them is not a modelling
        # decision, and asking the definer to copy them unchanged produced
        # `missing_data_file` on the first real run -- it rewrote the paths.
        # The program owns what it already knows.
        node["sources"] = json.loads(json.dumps(sources))
        if observed is not None:
            node = preserve_input_row(node, observed)
    return node, None


def _operand_question(model: Optional[dict], observed: list[dict],
                      report: Optional[list[dict]]):
    """Turn the program's own operand refusal into one precise question."""
    if not model:
        return None
    complaint = check_operands_supported(model, observed, report)
    if not complaint or "nothing independently distinguishes" not in complaint:
        return None
    for out in model.get("outputs") or []:
        compute = out.get("compute")
        if not compute:
            continue
        # Ask about whichever operand is genuinely ambiguous, not a fixed side.
        # A definer may put either operand first, and asking about `Qty` -- the
        # only numeric field in its source -- produced a question with no
        # candidates and the raw internal complaint as its text.
        for side in ("right", "left"):
            ref = compute[side]
            siblings = [c for c in observed
                        if c["claim"].get("source") == ref["from"]
                        and c["claim"].get("value_kind") == "numeric_string"]
            if len(siblings) > 1:
                return ({"source": ref["from"], "field": ref["field"],
                         "binding": f"which field supplies `{out['target']}`",
                         "question": complaint},
                        f"`{out['target']}` is computed from "
                        f"`{ref['from']}.{ref['field']}`, and only its NAME "
                        f"distinguishes it from the other numeric field(s) in "
                        f"`{ref['from']}`")
    return None


def propose(report: list[dict], goal: str, sources: dict, observed: list[dict],
            ask: Ask, resumed: bool = False, task: str = "enrichment"):
    """Define, then triage any block. Returns (model, questions, deferred).

    A block made entirely of non-load-bearing questions is not put to the
    person: the definer is told why each is settled and asked again. Deferred
    questions are returned so they can be SHOWN -- filtered out of the way, not
    out of sight.
    """
    all_deferred: list = []
    for attempt in (1, 2):
        model, block = define(report, goal, sources, ask, resumed,
                              all_deferred or None, observed, task)
        if block is None:
            if task in ("aggregation", "reconciliation"):
                return model, [], all_deferred
            # The definer did not block -- but it is not the authority on
            # whether a binding is established. The program checks its own
            # measurements and, where they do not settle a load-bearing
            # operand, raises the question the definer failed to ask. The first
            # real workbook went straight past this: the definer picked
            # `Unit price` by name and never blocked, so nothing asked.
            unsupported = _operand_question(model, observed, report)
            if unsupported:
                return None, [unsupported], all_deferred
            return model, [], all_deferred
        asked, deferred = triage(block, observed)
        all_deferred += deferred
        if asked:
            return None, asked, all_deferred
        if attempt == 2 or not deferred:
            break
    return None, [], all_deferred


def _node_of(text: str):
    keys = ("lookup", "outputs", "driving_source", "task", "model_version",
            "group_by", "aggregates", "match_on", "classify")
    found = None
    for obj in _w_run._objects(text):
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 3:
            found = obj
    return found


# ---------------------------------------------------------------------------
# 4b. enrichment semantics: the input row is PRESERVED
# ---------------------------------------------------------------------------

def fields_of(observed: list[dict], source: str) -> list[str]:
    for claim in observed:
        if claim["claim"].get("source") == source and "fields" in claim["claim"]:
            return list(claim["claim"]["fields"])
    return []


def preserve_input_row(model: dict, observed: list[dict]) -> dict:
    """Enrichment ADDS fields to a row. It does not replace the row.

    The first real journeys all produced `price, line_total` and nothing else —
    literally what the sentence asked for, and three rows that cannot be traced
    back to an order. Identity is not something a person should have to request:
    a row you cannot attribute is not an enriched row, it is a different table.

    So the driving source's own fields lead every output, in the order the
    observer reports them. A column the definer already declared for one of
    those fields keeps ITS spec — including `type: number` — and simply moves
    into position, so nothing the definer decided is discarded.

    Done here, in the model, rather than in the executor: the executor stays
    unchanged and the model still declares in full what will happen.
    """
    driving = model.get("driving_source")
    declared = list(model.get("outputs") or [])
    if not driving or not declared:
        return model

    by_field = {out.get("field"): out for out in declared
                if out.get("from") == driving and out.get("field")}
    leading = []
    for field in fields_of(observed, driving):
        leading.append(by_field.get(field)
                       or {"target": field, "from": driving, "field": field})
    kept_targets = {out["target"] for out in leading}
    trailing = [out for out in declared
                if out.get("target") not in kept_targets
                and out not in by_field.values()]

    model["outputs"] = leading + trailing
    return model


# ---------------------------------------------------------------------------
# 5. the missing truth — one specific question, tied to its referent
# ---------------------------------------------------------------------------

@dataclass
class Question:
    """One load-bearing fact the system cannot establish locally."""
    source: object
    field: Optional[str]
    binding: str
    text: str
    options: list[str] = dc_field(default_factory=list)

    @property
    def referent(self) -> dict:
        return {"source": self.source, "field": self.field}


def _measured(observed: list[dict], source, field) -> Optional[dict]:
    if isinstance(source, list) or not field:
        return None
    for claim in observed:
        body = claim["claim"]
        if body.get("source") == source and body.get("field") == field:
            return body
    return None


def _relevant_lefts(observed: list[dict], source, field) -> list[str]:
    """The join directions a referent could actually be about.

    Direction matters, and getting it wrong is not theoretical: in condition A
    the reverse candidate `products.code -> orders.item` has 2/3 coverage and is
    therefore unestablished, which made A's perfectly settled join look
    ambiguous and asked the person a question the evidence had already answered.

    A relationship is only relevant here if it could be this model's lookup:

      - a relational claim (`source` is a list) is about `source[0].field`
      - a scalar referent may be a lookup TARGET, so every join into it counts
      - a scalar referent is only treated as a lookup KEY when at least one of
        its own candidates is complete and unique -- a field that matches
        nothing completely is not a join anybody is proposing
    """
    rels = relationships(observed)
    if isinstance(source, list):
        if not source:
            return []
        if field:
            return [f"{source[0]}.{field}"]
        # A question naming two collections and no field is a question about
        # their RELATIONSHIP -- the only cross-collection thing an enrichment
        # model expresses. Judging it against every join between them keeps a
        # join question load-bearing while a question about arithmetic between
        # the same two sources, which the model fixes as `op: multiply`, is not.
        others = set(source[1:])
        return sorted({r["left"] for r in rels
                       if r["left"].split(".")[0] == source[0]
                       and r["right"].split(".")[0] in others})
    if not field:
        return []

    me = f"{source}.{field}"
    # Only lefts that are plausible join keys at all. A left with no complete,
    # unique candidate is not a join anybody is proposing -- and coincidental
    # value overlap creates such candidates readily: `184.90` appearing in both
    # a total and a price produced a 1/4 "relationship" that made an OPERAND
    # question look relational and asked about it wrongly.
    lefts = [r["left"] for r in rels
             if r["right"] == me and sufficiency(observed, r["left"])["sufficient"]]
    if any(r["left"] == me for r in rels) and sufficiency(observed, me)["sufficient"]:
        lefts.append(me)
    return sorted(set(lefts))


def _in_unsettled_relationship(observed: list[dict], source, field) -> Optional[str]:
    """The first relevant join direction the policy has not settled, if any."""
    for left in _relevant_lefts(observed, source, field):
        if not sufficiency(observed, left)["established"]:
            return left
    return None


def triage(block: list, observed: list[dict]) -> tuple[list, list]:
    """Split a definer's block into what must be asked and what must not.

    > A question is surfaced only if different answers could alter the
    > executable model or the authoritative output.

    An enrichment model can express exactly two data-dependent decisions: which
    relationship the lookup joins on, and whether a field may serve as a numeric
    operand. Nothing else it declares varies with an interpretation.

    So a blocked referent is load-bearing when it is one side of a join the
    sufficiency policy has not settled, or when the observer never measured it
    at all. A field the observer HAS measured is settled either way — if
    `value_kind` is `numeric_string` it can be multiplied, and if it is `text` no
    human assurance makes `"two"` parse. Currency, units and domain meaning are
    real questions that this model does not branch on, so they are recorded and
    do not block a calculation that does not depend on them.

    This is judged on referents and measurements, never on the wording of the
    question -- prose classification is how three graders in this programme went
    wrong.
    """
    asked, deferred = [], []
    for entry in block:
        source, field = entry.get("source"), entry.get("field")
        lefts = _relevant_lefts(observed, source, field)
        unsettled = _in_unsettled_relationship(observed, source, field)
        if lefts:
            fit = sufficiency(observed, unsettled or lefts[0])
            if not fit["established"]:
                asked.append((entry, f"the lookup joins on this; the policy finds "
                                     f"{len(fit['sufficient'])} equally complete "
                                     f"candidates, so the answer changes which "
                                     f"reference row supplies every output"))
                continue
            deferred.append((entry, f"the join {fit['sufficient'][0]['right']} is "
                                    f"established by measured coverage"))
            continue

        measured = _measured(observed, source, field)
        if measured is None:
            asked.append((entry, "the observer measured nothing about this "
                                 "subject, so its role cannot be settled locally"))
            continue

        # A numeric field's ROLE is a separate question from its usability. Where
        # several numeric fields sit side by side, only their names tell them
        # apart, and a name may not settle a load-bearing binding. Measurement
        # settles it if a computation reconciles; otherwise a person must.
        if measured.get("value_kind") == "numeric_string":
            siblings = [c for c in observed
                        if c["claim"].get("source") == source
                        and c["claim"].get("value_kind") == "numeric_string"]
            if len(siblings) > 1:
                fit = operand_sufficiency(observed)
                if fit["established"]:
                    pair = fit["sufficient"][0]
                    deferred.append((entry, f"{pair['left']} x {pair['right']} "
                                            f"reconciles against {pair['equals']} "
                                            f"({pair['holds']}), which settles "
                                            f"the operand roles by measurement"))
                else:
                    asked.append((entry, f"`{source}` has "
                                         f"{len(siblings)} numeric fields and no "
                                         f"computation reconciles, so only the "
                                         f"field NAME distinguishes them -- which "
                                         f"cannot settle a load-bearing operand"))
                continue

        deferred.append((entry, f"observed `{source}.{field}` is "
                                f"{measured['value_kind']} "
                                f"(e.g. {', '.join(map(str, measured['examples']))}); "
                                f"no answer to this changes the model or its output"))
    return asked, deferred


def questions_from(block: list, observed: list[dict]) -> list[Question]:
    """Turn a definer's block into concrete questions, with evidence attached.

    Where the block is about a join, the candidate relationships supply both the
    options and the sentence -- the person is told WHY it is being asked.
    """
    out = []
    for entry in block:
        source, field = entry.get("source"), entry.get("field")
        text = entry.get("question") or entry.get("binding") or "Which is intended?"
        options: list[str] = []
        if isinstance(source, list) and field:
            left = f"{source[0]}.{field}"
            fit = sufficiency(observed, left)
            if fit["candidates"]:
                options = [r["right"] for r in fit["sufficient"]] or \
                          [r["right"] for r in fit["candidates"]]
                overlaps = ", ".join(
                    f"{r['right']} {r['left_coverage']}" for r in fit["candidates"])
                text = (f"`{left}` matches {overlaps}. "
                        f"Which field is the intended product identifier?")
        if not options and field:
            # An operand-role question: offer the numeric fields it could be
            # confused with, and say why it is being asked.
            siblings = sorted(
                f"{c['claim']['source']}.{c['claim']['field']}" for c in observed
                if c["claim"].get("source") == source
                and c["claim"].get("value_kind") == "numeric_string")
            if len(siblings) > 1:
                options = siblings
                text = (f"`{source}` has {len(siblings)} numeric fields and "
                        f"nothing in the data distinguishes them. Which one is "
                        f"meant here?")
        out.append(Question(source, field, entry.get("binding", ""), text, options))
    return out


# Answers given during DEFINE, before any version exists. A confirmation is
# version-bound and there is no version yet -- the model is still a proposal --
# so they wait here and are written at establishment, which is also the first
# moment their version number is known.
PENDING: list = []


def pending_clear() -> None:
    PENDING.clear()


def pending_answers() -> list:
    return list(PENDING)


def answer(report: list[dict], question: Question, human_answer: str,
           obligation: Optional[str] = None) -> list[dict]:
    """Apply a human answer to the ADDRESSED claim only.

    Confirmation resolves claims, not workflows: a second unresolved load-bearing
    claim must still stop the run, and does.
    """
    if obligation:
        source = question.source
        referent = (f"{source[0] if isinstance(source, list) else source}"
                    f".{question.field}" if question.field else str(source))
        PENDING.append({"obligation": obligation, "clause": question.text,
                        "referent": referent, "answer": human_answer})

    out, settled = [], False
    for claim in boundary.confirm(report, [question.referent]):
        if claim.get("status") == "CONFIRMED":
            claim = dict(claim)
            body = dict(claim["claim"])
            if body.get("meaning") not in (None, human_answer):
                claim["superseded_meaning"] = body["meaning"]
            body.pop("question", None)
            body["meaning"] = human_answer
            claim["claim"] = body
            claim["confirmed_by"] = "human"
            settled = True
        out.append(claim)

    if not settled:
        # The block came from the DEFINER, whose referent need not match any
        # claim the inspector wrote. When it does not, confirmation used to
        # match nothing silently -- the person answered, the report was
        # unchanged, and the definer blocked again on the same question.
        #
        # A human answer is authority in its own right, so it becomes a claim at
        # the referent that was actually asked about. There is no prior status
        # to preserve because there was no prior claim.
        out.append({"claim": {"source": question.source, "field": question.field,
                              "meaning": human_answer},
                    "status": "CONFIRMED", "confirmed_by": "human",
                    "was": None})
    return out


# ---------------------------------------------------------------------------
# 6. verification, validation, deterministic preview
# ---------------------------------------------------------------------------

def computations(observed: list[dict]) -> list[dict]:
    return [c["claim"]["candidate_computation"] for c in observed
            if "candidate_computation" in c["claim"]]


def _complete_hold(holds: str) -> bool:
    left, _, right = holds.partition("/")
    return left == right and left != "0"


def operand_sufficiency(observed: list[dict]) -> dict:
    """Which operand pair a computation may be built from, by MEASUREMENT.

    Coverage settles which rows go together. It says nothing about which columns
    are the operands, and `Unit price` next to `VAT rate` is told apart by its
    NAME alone -- exactly the evidence this programme refuses to let become
    authority. A real workbook exposed this: the answer was right because the
    column was well named, not because anything established it.

    > An operand pair is MECHANICALLY SUFFICIENT when it is the SOLE pair that
    > reconciles completely against an independently supplied target column.

    "Independently supplied" is the load-bearing part. The target was produced by
    someone else's system, so a pair that reproduces it is supported by evidence
    no one in this chain manufactured.
    """
    holding = [c for c in computations(observed) if _complete_hold(c["holds"])]
    by_target: dict[str, list] = {}
    for c in holding:
        by_target.setdefault(c["equals"], []).append(c)
    sufficient = [pair[0] for pair in by_target.values() if len(pair) == 1]
    return {"candidates": computations(observed), "reconciling": holding,
            "sufficient": sufficient,
            "established": len(sufficient) == 1,
            "verdict": ("established" if len(sufficient) == 1 else
                        "ambiguous" if len(sufficient) > 1 else "unsupported")}


def confirmed_operands(report: Optional[list[dict]]) -> Optional[tuple]:
    """An operand pair a human settled, as (left, right)."""
    for claim in report or []:
        if claim.get("status") != "CONFIRMED":
            continue
        meaning = str(claim["claim"].get("meaning") or "")
        if " multiplied by " in meaning:
            left, _, right = meaning.partition(" multiplied by ")
            return left.strip().strip(".`"), right.strip().strip(".`")
    return None


def check_operands_supported(model: dict, observed: list[dict],
                             report: Optional[list[dict]] = None) -> Optional[str]:
    """The program's own verdict on the model's declared compute operands.

    Same shape as `check_join_supported`: the definer is not taken at its word.
    A computation whose operands are neither reconciled by measurement nor
    settled by a human is refused, however plausible the column names are.
    """
    for out in model.get("outputs") or []:
        compute = out.get("compute")
        if not compute:
            continue
        left = f"{compute['left']['from']}.{compute['left']['field']}"
        right = f"{compute['right']['from']}.{compute['right']['field']}"

        settled = confirmed_operands(report)
        if settled:
            if {left, right} != set(settled):
                return (f"a human settled the operands as {settled[0]} x "
                        f"{settled[1]}, but the model declares {left} x {right}")
            continue

        fit = operand_sufficiency(observed)
        if fit["verdict"] == "unsupported":
            candidates = _operand_candidates(model, observed)
            if len(candidates) <= 1:
                continue      # only one numeric operand available; nothing to
                              # tell apart, so nothing to establish
            return (f"nothing independently distinguishes the operands of "
                    f"`{out['target']}`; {len(candidates)} numeric candidates "
                    f"and no column reconciles")
        if fit["verdict"] == "ambiguous":
            return (f"{len(fit['sufficient'])} operand pairs reconcile equally; "
                    f"the computation is not established by evidence")
        pair = fit["sufficient"][0]
        if {pair["left"], pair["right"]} != {left, right}:
            return (f"the declared operands {left} x {right} are not the pair "
                    f"that reconciles ({pair['left']} x {pair['right']})")
    return None


def _operand_candidates(model: dict, observed: list[dict]) -> list[str]:
    """Numeric fields in the looked-up source -- what could be mistaken for what."""
    into = (model.get("lookup") or {}).get("into")
    return sorted(f"{c['claim']['source']}.{c['claim']['field']}" for c in observed
                  if c["claim"].get("source") == into
                  and c["claim"].get("value_kind") == "numeric_string")


def confirmed_join(report: list[dict]) -> Optional[str]:
    """The right-hand side a human settled on, if one was ever asked for.

    Human confirmation is one of the two ways a binding becomes established --
    the other being mechanical sufficiency. Without this, the program's own
    check would keep refusing the very binding the person just supplied.
    """
    for claim in report:
        if claim.get("status") != "CONFIRMED":
            continue
        meaning = str(claim["claim"].get("meaning") or "")
        if " matches " in meaning:
            return meaning.split(" matches ", 1)[1].strip().strip(".`")
    return None


def check_join_supported(model: dict, observed: list[dict],
                         report: Optional[list[dict]] = None) -> Optional[str]:
    """The program's OWN verdict on the model's declared join.

    The definer is not taken at its word. A model that proceeds on a join
    neither established by the sufficiency policy nor settled by a human is
    refused here, which is what keeps Y's result from depending on the definer
    behaving.
    """
    lookup = model.get("lookup") or {}
    driving, into = model.get("driving_source"), lookup.get("into")
    left_field, right_field = lookup.get("match_left"), lookup.get("match_right")
    if not all((driving, into, left_field, right_field)):
        return None                      # the validator will report the shape
    declared = f"{into}.{right_field}"

    settled = confirmed_join(report or [])
    if settled:
        return None if settled == declared else (
            f"a human settled this join as {settled}, but the model declares "
            f"{declared}")

    fit = sufficiency(observed, f"{driving}.{left_field}")
    if fit["established"]:
        chosen = fit["sufficient"][0]["right"]
        if chosen != declared:
            return (f"the declared join {declared} is not the mechanically "
                    f"sufficient candidate ({chosen})")
        return None
    if fit["verdict"] == "ambiguous":
        return (f"{driving}.{left_field} has {len(fit['sufficient'])} equally "
                f"complete candidates; the join is not established by evidence "
                f"and no human has settled it")
    return None


def build(ws: Workspace, model: dict):
    """Validate and run through the existing deterministic components."""
    return builder.preview(str(model.get("task") or TASK), model, base=ws.base)


def readable(model: dict) -> list[str]:
    """The proposed task in sentences, for a person who will not read JSON."""
    lookup = model.get("lookup") or {}
    lines = [f"Read **{model.get('driving_source')}**, and for each row look up "
             f"a matching row in **{lookup.get('into')}**.",
             f"Match `{model.get('driving_source')}.{lookup.get('match_left')}` "
             f"to `{lookup.get('into')}.{lookup.get('match_right')}`."]
    for out in model.get("outputs") or []:
        if "compute" in out:
            c = out["compute"]
            lines.append(f"Compute **{out['target']}** as "
                         f"`{c['left']['field']}` {c['op']} `{c['right']['field']}`.")
        else:
            lines.append(f"Copy **{out['target']}** from "
                         f"`{out.get('from')}.{out.get('field')}`"
                         + (" (must be numeric)" if out.get("type") == "number" else ""))
    lines.append(f"If no matching row: {lookup.get('on_missing')}. "
                 f"If more than one: {lookup.get('on_ambiguous')}. "
                 f"If a value that must be numeric is not: "
                 f"{model.get('on_non_numeric')}.")
    return lines


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    by_label = {w.label: w for w in workspaces()}
    check(len(by_label) >= 4, f"workspaces must be discoverable: {list(by_label)}")

    # --- the sufficiency policy must reproduce Y's three verdicts -----------
    expected = {"A": ("established", "products.sku"),
                "B": ("established", "products.code"),
                "C": ("ambiguous", None)}
    for cond, (verdict, right) in expected.items():
        ws = by_label[f"experiment Y - condition {cond}"]
        chosen = sources_in(ws)
        observed = observed_facts(ws, chosen)
        fit = sufficiency(observed, "orders.item")
        check(fit["verdict"] == verdict,
              f"Y-{cond}: expected {verdict}, got {fit['verdict']} "
              f"({[(r['right'], r['left_coverage']) for r in fit['candidates']]})")
        if right:
            check(fit["sufficient"][0]["right"] == right,
                  f"Y-{cond}: expected {right}, got {fit['sufficient'][0]['right']}")

    # --- and the established binding must EXECUTE to Y's oracle -------------
    for cond, right in (("A", "sku"), ("B", "code")):
        ws = by_label[f"experiment Y - condition {cond}"]
        chosen = sources_in(ws)
        model = {
            "model_version": 1, "model_id": f"pipeline_{cond}", "task": "enrichment",
            "sources": source_spec(ws, chosen), "driving_source": "orders",
            "lookup": {"into": "products", "match_left": "item",
                       "match_right": right, "on_missing": "refuse_row",
                       "on_ambiguous": "refuse_run"},
            "outputs": [
                {"target": "item", "from": "orders", "field": "item"},
                {"target": "description", "from": "products", "field": "description"},
                {"target": "quantity", "from": "orders", "field": "quantity",
                 "type": "number"},
                {"target": "price", "from": "products", "field": "price",
                 "type": "number"},
                {"target": "line_total", "compute": {
                    "op": "multiply",
                    "left": {"from": "orders", "field": "quantity"},
                    "right": {"from": "products", "field": "price"}}}],
            "on_non_numeric": "refuse_row"}
        observed = observed_facts(ws, chosen)
        check(check_join_supported(model, observed, []) is None,
              f"Y-{cond}: the sufficient join must pass the program's own check")
        p = build(ws, model)
        check(p.ok and [r[-1] for r in p.rows] == ["3.00", "14.00", "10.00"]
              and not p.refused,
              f"Y-{cond}: must execute to the oracle: ok={p.ok} "
              f"rows={p.rows} problems={p.problems}")

        # --- CANARY: the wrong key must be refused BEFORE execution --------
        wrong = json.loads(json.dumps(model))
        wrong["lookup"]["match_right"] = "code" if right == "sku" else "sku"
        check(check_join_supported(wrong, observed, []) is not None,
              f"CANARY Y-{cond}: a join the policy does not establish must be "
              f"refused by the program, whatever the definer said")

    # --- C: ambiguous, and a question that carries its evidence ------------
    ws = by_label["experiment Y - condition C"]
    observed = observed_facts(ws, sources_in(ws))
    qs = questions_from([{"source": ["orders", "products"], "field": "item",
                          "binding": "the join", "question": "which?"}], observed)
    check(len(qs) == 1 and set(qs[0].options) == {"products.sku", "products.code"},
          f"the question must offer both sufficient candidates: {qs}")
    check("3/3" in qs[0].text and "orders.item" in qs[0].text,
          f"the question must show WHY it is asked: {qs[0].text}")

    # --- confirmation touches one claim, and observations survive ----------
    report = boundary.merge(observed, boundary.ingest([
        {"claim": {"source": ["orders", "products"], "field": "item",
                   "question": "which?"}, "status": "UNKNOWN"},
        {"claim": {"source": "orders", "field": "quantity",
                   "meaning": "how many"}, "status": "INFERRED",
         "basis": ["field_name"]}]))
    after = answer(report, qs[0], "orders.item matches products.sku")
    moved = [c for c in after if c.get("status") == "CONFIRMED"]
    check(len(moved) == 1 and moved[0]["was"] == "UNKNOWN",
          f"exactly the addressed claim is settled: {moved}")
    check([c for c in after if c["status"] == "OBSERVED"]
          == [c for c in report if c["status"] == "OBSERVED"],
          "the program's observations must pass through untouched")
    check([c for c in after if c["status"] == "INFERRED"],
          "CANARY: a neighbouring inference must NOT be settled by this answer")

    # --- a human answer establishes a join the policy cannot -------------
    # Found by running the journey: without this, C was refused at step 5 for
    # being ambiguous AFTER the person had just resolved it.
    wsc = by_label["experiment Y - condition C"]
    obs_c = observed_facts(wsc, sources_in(wsc))
    ambiguous = {"driving_source": "orders",
                 "lookup": {"into": "products", "match_left": "item",
                            "match_right": "sku"}}
    check(check_join_supported(ambiguous, obs_c, []) is not None,
          "C with no answer must be refused")
    settled = [{"status": "CONFIRMED", "was": "UNKNOWN",
                "claim": {"meaning": "orders.item matches products.sku"}}]
    check(check_join_supported(ambiguous, obs_c, settled) is None,
          "C must proceed once a human has settled it")
    wrong_after = json.loads(json.dumps(ambiguous))
    wrong_after["lookup"]["match_right"] = "code"
    check(check_join_supported(wrong_after, obs_c, settled) is not None,
          "CANARY: a model contradicting the human answer must be refused")

    # --- enrichment ADDS to the row, it does not replace it ----------------
    # Every first-run journey produced `price, line_total` and no `item`: three
    # rows nobody could trace back to an order.
    thin = {"driving_source": "orders", "outputs": [
        {"target": "price", "from": "products", "field": "price",
         "type": "number"},
        {"target": "line_total", "compute": {
            "op": "multiply", "left": {"from": "orders", "field": "quantity"},
            "right": {"from": "products", "field": "price"}}}]}
    obs_a = observed_facts(by_label["experiment Y - condition A"],
                           sources_in(by_label["experiment Y - condition A"]))
    kept = preserve_input_row(json.loads(json.dumps(thin)), obs_a)
    targets = [o["target"] for o in kept["outputs"]]
    check(targets[:2] == ["item", "quantity"] and targets[-1] == "line_total",
          f"the driving row must lead the output: {targets}")
    check("price" in targets and len(targets) == 4,
          f"added columns are kept, not duplicated: {targets}")

    # a definer-declared spec for a driving field keeps ITS spec, in position
    typed = {"driving_source": "orders", "outputs": [
        {"target": "quantity", "from": "orders", "field": "quantity",
         "type": "number"},
        {"target": "line_total", "compute": {
            "op": "multiply", "left": {"from": "orders", "field": "quantity"},
            "right": {"from": "products", "field": "price"}}}]}
    kept = preserve_input_row(typed, obs_a)
    quantity = next(o for o in kept["outputs"] if o["target"] == "quantity")
    check(quantity.get("type") == "number",
          f"a declared numeric assertion must survive repositioning: {quantity}")
    check([o["target"] for o in kept["outputs"]] == ["item", "quantity",
                                                     "line_total"],
          f"and must not be duplicated: {[o['target'] for o in kept['outputs']]}")

    # --- triage: ask only what could change the model ----------------------
    obs_c = observed_facts(by_label["experiment Y - condition C"],
                           sources_in(by_label["experiment Y - condition C"]))
    join_q = {"source": ["orders", "products"], "field": "item",
              "question": "code or sku?"}
    numeric_q = {"source": "orders", "field": "quantity",
                 "question": "are these really counts?"}
    currency_q = {"source": "products", "field": "price",
                  "question": "what currency is this?"}
    unknown_q = {"source": "orders", "field": "nonexistent",
                 "question": "what is this?"}

    asked, deferred = triage([join_q, numeric_q, currency_q], obs_c)
    check([e.get("field") for e, _ in asked] == ["item"],
          f"only the join may be asked in C: {[e.get('field') for e, _ in asked]}")
    check({e.get("field") for e, _ in deferred} == {"quantity", "price"},
          f"CANARY: numeric and currency questions must be deferred, not asked: "
          f"{[(e.get('field'), w) for e, w in deferred]}")
    check(all("numeric_string" in why for _, why in deferred),
          f"deferral must cite the MEASUREMENT that settles it: {deferred}")

    # in A the join IS established, so even a join question defers
    asked, deferred = triage([join_q, currency_q], obs_a)
    check(not asked, f"CANARY: nothing is asked in A: {[e for e, _ in asked]}")
    check(any("established by measured coverage" in why for _, why in deferred),
          f"an established join must defer with its reason: {deferred}")

    # a subject the observer never measured is still asked about
    asked, _ = triage([unknown_q], obs_a)
    check([e.get("field") for e, _ in asked] == ["nonexistent"],
          "CANARY: an unmeasured subject must still be asked about")

    # a cross-collection question with NO field is about the relationship
    formula_q = {"source": ["orders", "products"], "field": None,
                 "question": "what is the exact formula for the line total?"}
    asked, deferred = triage([formula_q], obs_a)
    check(not asked and deferred,
          f"CANARY: with the join established, a formula question between the "
          f"same two sources must NOT block -- the model fixes op: multiply: "
          f"{[(e.get('question'), w) for e, w in asked]}")
    asked, _ = triage([formula_q], obs_c)
    check(asked, "but with the join unsettled, a relational question IS asked")

    # a field referent that names one SIDE of an unsettled join is load-bearing
    side_q = {"source": "products", "field": "code", "question": "is this the key?"}
    asked, _ = triage([side_q], obs_c)
    check([e.get("field") for e, _ in asked] == ["code"],
          "CANARY: naming one side of an unsettled join is load-bearing, even "
          "though the field itself is measured")

    # --- an answer to a referent nobody claimed must still land ------------
    # Found on the second real journey: the definer blocked on a referent the
    # inspector had not written a claim for, confirmation matched nothing, and
    # condition C looped on the same question.
    bare = boundary.merge(obs_c, boundary.ingest(
        [{"claim": {"source": "orders", "field": "quantity",
                    "meaning": "how many"},
          "status": "INFERRED", "basis": ["field_name"]}]))
    q_novel = Question(["orders", "products"], "item", "the join", "which?")
    after = answer(bare, q_novel, "orders.item matches products.sku")
    settled_claims = [c for c in after if c.get("status") == "CONFIRMED"]
    check(len(settled_claims) == 1
          and settled_claims[0]["claim"]["field"] == "item",
          f"an answer must always produce exactly one confirmed claim: "
          f"{settled_claims}")
    check(confirmed_join(after) == "products.sku",
          f"…and the join check must be able to read it: {confirmed_join(after)}")
    check([c for c in after if c["status"] == "OBSERVED"]
          == [c for c in bare if c["status"] == "OBSERVED"],
          "…without disturbing a single observation")
    check(len([c for c in after if c["status"] == "INFERRED"]) == 1,
          "CANARY: and without settling the neighbouring inference")

    # --- OPERAND ROLES: measurement over naming, including the mirror ------
    def _ab(cond):
        return observe.observed_claims(LAB / "experimentAB" / "fixtures" / cond)

    def _model(right):
        return {"driving_source": "order_lines",
                "lookup": {"into": "price_list", "match_left": "Article",
                           "match_right": "Article"},
                "outputs": [{"target": "Cost", "compute": {
                    "op": "multiply",
                    "left": {"from": "order_lines", "field": "Qty"},
                    "right": {"from": "price_list", "field": right}}}]}

    obs_a, obs_b, obs_c = _ab("A"), _ab("B"), _ab("C")
    check(operand_sufficiency(obs_a)["sufficient"][0]["right"]
          == "price_list.Unit price", "A: the reconciling pair is Unit price")
    check(operand_sufficiency(obs_b)["sufficient"][0]["right"]
          == "price_list.VAT rate",
          "MIRROR: in B the arithmetic backs the WORSE-named field")
    check(operand_sufficiency(obs_c)["verdict"] == "unsupported",
          "C: nothing reconciles")

    check(check_operands_supported(_model("Unit price"), obs_a, []) is None,
          "A accepts the pair that reconciles")
    check(check_operands_supported(_model("VAT rate"), obs_a, []) is not None,
          "CANARY: A refuses the pair that does not, however it is named")
    check(check_operands_supported(_model("VAT rate"), obs_b, []) is None,
          "MIRROR: B accepts `VAT rate` because it is what reconciles")
    check(check_operands_supported(_model("Unit price"), obs_b, []) is not None,
          "CANARY: B REFUSES the plausibly named field -- naming is not "
          "authority")
    for name in ("Unit price", "VAT rate"):
        check(check_operands_supported(_model(name), obs_c, []) is not None,
              f"CANARY: C must refuse {name} -- nothing distinguishes them")

    # --- a human settles C, and the binding then holds --------------------
    settled = [{"status": "CONFIRMED", "was": "INFERRED", "claim": {
        "meaning": "order_lines.Qty multiplied by price_list.Unit price"}}]
    check(check_operands_supported(_model("Unit price"), obs_c, settled) is None,
          "C proceeds once a human settles the operands")
    check(check_operands_supported(_model("VAT rate"), obs_c, settled) is not None,
          "CANARY: and a model contradicting that answer is refused")

    # --- triage asks in C and stays quiet in A ----------------------------
    q = {"source": "price_list", "field": "Unit price",
         "question": "is this the unit price?"}
    asked_c, _ = triage([q], obs_c)
    check(asked_c and "only the field NAME" in asked_c[0][1],
          f"C must ASK about the operand role: {asked_c}")
    asked_a, deferred_a = triage([q], obs_a)
    check(not asked_a and any("reconciles against" in why for _, why in deferred_a),
          f"A must NOT ask -- measurement settled it: {asked_a or deferred_a}")

    # --- the LLM channel still cannot mint an observation ------------------
    r = boundary.ingest([{"claim": {"source": "orders", "field": "item"},
                          "status": "OBSERVED"}])
    check(not r.accepted, "the inspector channel must still refuse OBSERVED")

    # --- readable rendering ------------------------------------------------
    text = " ".join(readable(model))
    check("line_total" in text and "multiply" in text and "refuse_row" in text,
          f"the proposal must be readable without JSON: {text}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (workspaces discoverable / the sufficiency policy "
          "reproduces Y's A=sku B=code C=ambiguous / both established joins "
          "execute to the oracle / a join the policy does not establish is "
          "refused by the program whatever the definer said / the C question "
          "offers both candidates and shows why / confirmation settles exactly "
          "one claim, leaves a neighbouring inference alone and never touches an "
          "observation / the inspector channel still refuses OBSERVED / the "
          "proposal renders without JSON)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
