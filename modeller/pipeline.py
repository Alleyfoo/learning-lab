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

TASK = "enrichment"


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


def inspect_prompt(observed: list[dict], goal: str) -> str:
    return INSPECT_PROMPT.format(
        observed=json.dumps(observed, indent=2, ensure_ascii=False), goal=goal,
        basis_kinds=json.dumps(list(BASIS_KINDS), indent=2),
        shape=json.dumps(SHAPE, indent=2))


def define_prompt(report: list[dict], goal: str, sources: dict,
                  resumed: bool = False) -> str:
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


def define(report: list[dict], goal: str, sources: dict, ask: Ask,
           resumed: bool = False) -> tuple[Optional[dict], Optional[list]]:
    text = ask(define_prompt(report, goal, sources, resumed))
    block = _w_run.block_of(text)
    if block is not None:
        return None, block
    node = _node_of(text)
    if node is not None:
        # The person SELECTED these files. Restating them is not a modelling
        # decision, and asking the definer to copy them unchanged produced
        # `missing_data_file` on the first real run -- it rewrote the paths.
        # The program owns what it already knows.
        node["sources"] = json.loads(json.dumps(sources))
    return node, None


def _node_of(text: str):
    keys = ("lookup", "outputs", "driving_source", "task", "model_version")
    found = None
    for obj in _w_run._objects(text):
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 3:
            found = obj
    return found


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
        out.append(Question(source, field, entry.get("binding", ""), text, options))
    return out


def answer(report: list[dict], question: Question, human_answer: str) -> list[dict]:
    """Apply a human answer to the ADDRESSED claim only.

    Confirmation resolves claims, not workflows: a second unresolved load-bearing
    claim must still stop the run, and does.
    """
    out = []
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
        out.append(claim)
    return out


# ---------------------------------------------------------------------------
# 6. verification, validation, deterministic preview
# ---------------------------------------------------------------------------

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
    return builder.preview(TASK, model, base=ws.base)


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
