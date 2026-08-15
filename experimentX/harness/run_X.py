#!/usr/bin/env python3
"""Run the X chain. Same three stages as W, relational missing truth."""
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
# X's harness ONLY. W's modules share these names and are loaded by
# explicit path below -- putting W's directory on sys.path made
# `import build_prompts` resolve to W's calendar prompts and voided a run.
sys.path.insert(0, str(HERE))

import observe  # noqa: E402
import build_prompts as x  # noqa: E402

boundary = x.boundary
_w_run = importlib.util.spec_from_file_location(
    "_w_run", LAB / "experimentW" / "harness" / "run_W.py")
w_run = importlib.util.module_from_spec(_w_run)
sys.modules["_w_run"] = w_run
_w_run.loader.exec_module(w_run)

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"

# THE MISSING TRUTH. Fixed before the run, and the only thing no processor in
# the chain can derive.
#
# W did not need this. Its inspector inferred *"date means the date being
# reserved"*, which was already correct, so confirmation only had to flip a
# status. Here the inspector may well infer `code`, and confirming a wrong guess
# would launder it into authority -- the exact failure T exhibited.
#
# So a human answer SUPPLIES content, it does not merely bless what is there.
# The claim's own meaning is overwritten with the answer and the previous
# meaning is preserved beside it, so a corrected inference stays visible as
# having been corrected.
HUMAN_ANSWER = "orders.item matches products.sku"


def apply_human_answer(report: list[dict], referents) -> list[dict]:
    """Settle the named referents with the human's actual answer."""
    confirmed = boundary.confirm(report, referents)
    out = []
    for claim in confirmed:
        if claim.get("status") == "CONFIRMED":
            claim = dict(claim)
            body = dict(claim["claim"])
            if body.get("meaning") not in (None, HUMAN_ANSWER):
                claim["superseded_meaning"] = body["meaning"]
            body.pop("question", None)
            body["meaning"] = HUMAN_ANSWER
            claim["claim"] = body
            claim["confirmed_by"] = "human"
        out.append(claim)
    return out


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())["response"]


def node_of(text: str):
    """An enrichment model, as opposed to any JSON in the answer."""
    keys = ("lookup", "outputs", "driving_source", "task", "model_version")
    found = None
    for obj in w_run._objects(text):
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 3:
            found = obj
    return found


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    observed = observe.observed_claims()
    inspect = x.inspect_prompt(observed)

    for probe in (1, 2, 3):
        tag = f"probe{probe}"
        f1 = RESULTS / f"{tag}_stage1_inspect_raw.txt"
        if not f1.exists():
            print(f"{tag} stage 1 inspect ...", flush=True)
            f1.write_text(ask(inspect), encoding="utf-8")
        raw = w_run.claim_list(f1.read_text(encoding="utf-8"))
        if raw is None:
            print(f"{tag}: stage 1 produced no claim list; chain stops")
            continue
        ingested = boundary.ingest(raw)
        report = boundary.merge(observed, ingested)
        (RESULTS / f"{tag}_stage1_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{tag} stage 1: {len(raw)} emitted, {len(ingested.accepted)} accepted, "
              f"rejected {[r['code'] for r in ingested.rejected]}")

        f2 = RESULTS / f"{tag}_stage2_model_raw.txt"
        if not f2.exists():
            print(f"{tag} stage 2 model ...", flush=True)
            f2.write_text(ask(x.model_prompt(report)), encoding="utf-8")
        text2 = f2.read_text(encoding="utf-8")
        block, node2 = w_run.block_of(text2), node_of(text2)
        if block is None:
            key = (node2 or {}).get("lookup", {}).get("match_right")
            print(f"{tag} stage 2: NO BLOCK -- model produced, match_right={key!r}")
            continue
        refs = [{"source": b.get("source"), "field": b.get("field")} for b in block]
        print(f"{tag} stage 2: blocked on {[(r['source'], r['field']) for r in refs]}")

        confirmed = apply_human_answer(report, refs)
        (RESULTS / f"{tag}_stage3_report.json").write_text(
            json.dumps(confirmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        moved = [c for c in confirmed if c.get("status") == "CONFIRMED"]
        print(f"{tag} stage 3: {len(moved)} promoted")
        f3 = RESULTS / f"{tag}_stage3_resume_raw.txt"
        if not f3.exists():
            print(f"{tag} stage 3 resume ...", flush=True)
            f3.write_text(ask(x.model_prompt(confirmed, resumed=True)), encoding="utf-8")
        node3 = node_of(f3.read_text(encoding="utf-8"))
        print(f"{tag} stage 3: model produced={node3 is not None}, "
              f"match_right={(node3 or {}).get('lookup', {}).get('match_right')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
