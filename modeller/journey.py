#!/usr/bin/env python3
"""Run the modeller's journey headlessly. Same pipeline the Streamlit app calls.

    python modeller/journey.py "experiment Y - condition A"

Exists so the end-to-end behaviour can be checked and reported without driving a
browser, and so the milestone's success criterion is something that can be RUN
rather than asserted.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pipeline  # noqa: E402

GOAL = ("Enrich these orders with the matching product price and calculate the "
        "line total.")
MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["response"]


# What a human would answer if asked. Supplied only when the system asks.
HUMAN = {"A": "products.sku", "B": "products.code", "C": "products.sku"}


def run(ws, human_answer: str, goal: str = GOAL) -> dict:
    chosen = pipeline.sources_in(ws)
    observed = pipeline.observed_facts(ws, chosen)
    sources = pipeline.source_spec(ws, chosen)
    out = {"workspace": ws.label, "observed": len(observed),
           "sufficiency": pipeline.sufficiency(observed, "orders.item")["verdict"]}

    report, ingest = pipeline.interpret(observed, goal, ask)
    out["claims"] = {s: sum(1 for c in report if c["status"] == s)
                     for s in ("OBSERVED", "INFERRED", "UNKNOWN")}
    out["rejected"] = [r["code"] for r in ingest["rejected"]]
    out["stripped"] = [s["removed"] for s in ingest["stripped"]]

    model, block = pipeline.define(report, goal, sources, ask)
    out["asked"] = block is not None
    if block is not None:
        q = pipeline.questions_from(block, observed)[0]
        out["question"] = q.text
        out["options"] = q.options
        # Answer what was ACTUALLY asked. The first real run asked about the
        # join in C but about `price` and `quantity` semantics in A and B, and
        # a script that always replies with a join sentence answers a question
        # nobody put.
        is_join = bool(q.options) or (isinstance(q.source, list))
        reply = (f"orders.item matches {human_answer}" if is_join
                 else "Yes, that is correct.")
        out["answer_given"] = reply
        report = pipeline.answer(report, q, reply)
        out["confirmed"] = [c["claim"] for c in report if c["status"] == "CONFIRMED"]
        model, block = pipeline.define(report, goal, sources, ask, resumed=True)
        out["asked_again"] = block is not None
    if model is None:
        out["error"] = "no model produced"
        return out

    out["join"] = f"{model['driving_source']}.{model['lookup']['match_left']} -> " \
                  f"{model['lookup']['into']}.{model['lookup']['match_right']}"
    out["policy_check"] = pipeline.check_join_supported(model, observed, report) or "ok"
    out["model"] = model
    p = pipeline.build(ws, model)
    out["valid"] = p.ok
    out["problems"] = p.problems
    out["columns"] = p.columns
    out["rows"] = p.rows
    out["refused"] = p.refused
    return out


def main(argv: list[str]) -> int:
    spaces = {w.label: w for w in pipeline.workspaces()}
    wanted = argv or [l for l in spaces if "condition" in l]
    for label in wanted:
        ws = spaces[label]
        cond = label.strip()[-1]
        result = run(ws, HUMAN.get(cond, "products.sku"))
        print("=" * 70)
        print(json.dumps({k: v for k, v in result.items() if k != "model"},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
