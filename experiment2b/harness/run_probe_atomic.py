"""Experiment 2B.5 — atomic header-cell classification.

One cell, one judgement. No list construction, no indexing, no trailing-column
boundary, and no requirement to preserve four correct answers while expressing
one uncertainty at the same time.

`unknown` now costs essentially nothing. In 2B.3 the interface forced a choice
between discarding four known answers and omitting the unresolved one. Here there
is no such trade-off.

Composition and escalation are NOT the model's job. Deterministic code assembles
the aggregate and decides whether a human is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

from render_rows import render

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
RESULTS = ROOT / "results"
OLLAMA = "http://localhost:11434/api/chat"

PROMPT = """Below is a tabular source file, shown one row at a time. Cells within a row are separated by |.

{rows}

The data header is row {header_row}.

Consider only this one header cell, column {col} of that row: "{cell}"

Is this column a calendar month?

Return exactly one of these JSON objects and nothing else:
{{"classification": "month"}}
{{"classification": "not_month"}}
{{"classification": "unknown"}}

The values mean:
- "month": the cell denotes a calendar month.
- "not_month": the cell denotes something that is not a calendar month.
- "unknown": it cannot be determined from the available evidence.
"""

VALID = {"month", "not_month", "unknown"}


def extract_json(text: str) -> dict | None:
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.DOTALL)
    for candidate in ([f.strip() for f in fenced] + [text.strip()]):
        m = re.search(r"\{.*?\}", candidate, flags=re.DOTALL)
        if not m:
            continue
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def classify_cell(model, fixture, header_row, col, cell, opts, digest_ok) -> dict:
    prompt = PROMPT.format(rows=render(FIX / f"{fixture}.csv"),
                           header_row=header_row, col=col, cell=cell)
    body = json.dumps({"model": model, "think": False, "stream": False,
                       "messages": [{"role": "user", "content": prompt}],
                       "options": opts}).encode()
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(OLLAMA, data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=1800).read())
    content = (resp.get("message") or {}).get("content") or ""
    obj = extract_json(content)
    got = obj.get("classification") if isinstance(obj, dict) else None
    return {
        "api_finished": resp.get("done_reason"),
        "json_parseable": obj is not None,
        "valid_value": got in VALID,
        "reported": got,
        "raw_reply": content,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--expect-digest", default=None)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    plan = json.loads((FIX / "expected_atomic.json").read_text(encoding="utf-8"))

    tags = json.loads(urllib.request.urlopen(
        "http://localhost:11434/api/tags", timeout=30).read())
    info = next(m for m in tags["models"] if m["name"] == args.model)
    if args.expect_digest and info["digest"] != args.expect_digest:
        raise SystemExit("ABORT: digest mismatch")

    opts = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": args.seed,
            "num_ctx": args.num_ctx, "num_predict": args.num_predict}

    results = []
    for p in plan["probes"]:
        r = classify_cell(args.model, p["fixture"], p["header_row"], p["column"],
                          p["cell"], opts, args.expect_digest)
        r.update({"probe": p["id"], "fixture": p["fixture"], "column": p["column"],
                  "cell": p["cell"], "expected": p["expected"]})
        r["correct"] = r["reported"] == p["expected"]
        results.append(r)
        flag = "OK " if r["correct"] else "XX "
        print(f"  {flag}{p['id']}  {p['fixture']} col{p['column']:<2} {p['cell']!r:<12} "
              f"expected={p['expected']:<9} reported={r['reported']}")

    # ---- deterministic aggregation: the model never builds this object -----
    aggregation = {}
    for fixture, spec in plan["aggregate"].items():
        cells = [r for r in results if r["fixture"] == fixture]
        if len(cells) != spec["n_cells_required"]:
            aggregation[fixture] = {"status": "not attempted - partial cell coverage"}
            continue
        months = sorted(r["column"] for r in cells if r["reported"] == "month")
        unknowns = sorted(r["column"] for r in cells if r["reported"] == "unknown")
        aggregation[fixture] = {
            "month_columns": months,
            "unknown_columns": unknowns,
            "expected_month_columns": spec["expected_month_columns"],
            "expected_unknown_columns": spec["expected_unknown_columns"],
            "matches_expected": (months == spec["expected_month_columns"]
                                 and unknowns == spec["expected_unknown_columns"]),
            "orchestration_decision": ("request human clarification"
                                       if unknowns else "proceed"),
        }

    n_ok = sum(1 for r in results if r["correct"])
    record = {
        "probe": "2B.5 atomic header classification",
        "model": {"tag": args.model, "digest": info["digest"],
                  "family": info["details"]["family"],
                  "parameter_size": info["details"]["parameter_size"],
                  "quantization": info["details"]["quantization_level"],
                  "ollama_version": subprocess.run(["ollama", "--version"],
                                                   capture_output=True, text=True).stdout.strip()},
        "think_enabled": False,
        "generation_options": opts,
        "per_cell": results,
        "per_cell_correct": f"{n_ok}/{len(results)}",
        "deterministic_aggregation": aggregation,
    }
    (RESULTS / "atomic_result.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nper-cell: {n_ok}/{len(results)} correct")
    for fixture, agg in aggregation.items():
        if "status" in agg:
            print(f"  {fixture}: {agg['status']}")
            continue
        print(f"  {fixture}: months={agg['month_columns']} unknown={agg['unknown_columns']} "
              f"matches_expected={agg['matches_expected']} "
              f"-> orchestration: {agg['orchestration_decision']}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
