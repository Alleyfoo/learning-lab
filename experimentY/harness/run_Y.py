#!/usr/bin/env python3
"""Run Y. Three conditions x three probes, same three stages as W and X."""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))

import build_prompts as y  # noqa: E402

boundary = y.boundary
_s = importlib.util.spec_from_file_location(
    "_w_run", LAB / "experimentW" / "harness" / "run_W.py")
w_run = importlib.util.module_from_spec(_s)
sys.modules["_w_run"] = w_run
_s.loader.exec_module(w_run)

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"

# The missing truth per condition. Only C should ever need it: A and B are
# mechanically sufficient and must not ask. Defined for all three so that an
# unexpected block in A or B is still answered honestly rather than stalling.
HUMAN_ANSWER = {"A": "orders.item matches products.sku",
                "B": "orders.item matches products.code",
                "C": "orders.item matches products.sku"}


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as response:
        return json.loads(response.read())["response"]


def node_of(text: str):
    keys = ("lookup", "outputs", "driving_source", "task", "model_version")
    found = None
    for obj in w_run._objects(text):
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 3:
            found = obj
    return found


def apply_human_answer(report, referents, answer: str):
    out = []
    for claim in boundary.confirm(report, referents):
        if claim.get("status") == "CONFIRMED":
            claim = dict(claim)
            body = dict(claim["claim"])
            if body.get("meaning") not in (None, answer):
                claim["superseded_meaning"] = body["meaning"]
            body.pop("question", None)
            body["meaning"] = answer
            claim["claim"] = body
            claim["confirmed_by"] = "human"
        out.append(claim)
    return out


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    for cond in y.CONDITIONS:
        observed = y.observe.observed_claims(ROOT / "fixtures" / cond)
        inspect = y.inspect_prompt(observed)
        for probe in (1, 2, 3):
            tag = f"{cond}_probe{probe}"
            f1 = RESULTS / f"{tag}_stage1_inspect_raw.txt"
            if not f1.exists():
                print(f"{tag} stage 1 ...", flush=True)
                f1.write_text(ask(inspect), encoding="utf-8")
            raw = w_run.claim_list(f1.read_text(encoding="utf-8"))
            if raw is None:
                print(f"{tag}: no claim list; chain stops")
                continue
            ingested = boundary.ingest(raw)
            report = boundary.merge(observed, ingested)
            (RESULTS / f"{tag}_stage1_report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")

            f2 = RESULTS / f"{tag}_stage2_model_raw.txt"
            if not f2.exists():
                print(f"{tag} stage 2 ...", flush=True)
                f2.write_text(ask(y.model_prompt(report, cond)), encoding="utf-8")
            text2 = f2.read_text(encoding="utf-8")
            block, node2 = w_run.block_of(text2), node_of(text2)
            if block is None:
                key = (node2 or {}).get("lookup", {}).get("match_right")
                print(f"{tag}: PROCEED, match_right={key!r}")
                continue
            refs = [{"source": b.get("source"), "field": b.get("field")}
                    for b in block]
            print(f"{tag}: BLOCK on {[(r['source'], r['field']) for r in refs]}")
            confirmed = apply_human_answer(report, refs, HUMAN_ANSWER[cond])
            (RESULTS / f"{tag}_stage3_report.json").write_text(
                json.dumps(confirmed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            f3 = RESULTS / f"{tag}_stage3_resume_raw.txt"
            if not f3.exists():
                print(f"{tag} stage 3 ...", flush=True)
                f3.write_text(ask(y.model_prompt(confirmed, cond, resumed=True)),
                              encoding="utf-8")
            node3 = node_of(f3.read_text(encoding="utf-8"))
            print(f"{tag}: resumed={node3 is not None}, "
                  f"match_right={(node3 or {}).get('lookup', {}).get('match_right')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
