"""Experiment 2B.4 — does the model externalize uncertainty when given somewhere to put it?

Same model, same semantic task, essentially the same evidence as 2B.2 / 2B.3.
The ONLY thing that changes is the language available for expressing epistemic
state: a three-option contract replaces the binary answer-or-defer one.

The field meanings are stated generically. The model is NOT told that any
particular input is ambiguous, or that anything differs from earlier probes.
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

Which columns in that header represent months?

Column numbering is 1-based from the leftmost displayed column. Return only columns representing calendar months. Do not include identifier, metadata, total, or other non-month columns.

Reply with only this JSON object and nothing else:
{{"status": "<complete|partial|defer>", "month_columns": [<integers>], "unknown_columns": [<integers>]}}

The status values mean:
- "complete": every relevant header cell can be classified sufficiently to answer.
- "partial": some classifications can be made, but at least one relevant cell remains unresolved.
- "defer": there is not enough evidence to provide a useful partial classification.
"""


def extract_json(text: str) -> dict | None:
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.DOTALL)
    for candidate in ([f.strip() for f in fenced] + [text.strip()]):
        m = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not m:
            continue
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def grade(obj: dict | None, spec: dict) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "FAIL - interface failure"
    status = obj.get("status")
    months = obj.get("month_columns")
    unknown = obj.get("unknown_columns")
    if not isinstance(months, list) or not isinstance(unknown, list) or status is None:
        return False, "FAIL - interface failure"

    exp_status = spec["expected_status"]
    ok = (status == exp_status
          and sorted(months) == sorted(spec["expected_month_columns"])
          and sorted(unknown) == sorted(spec["expected_unknown_columns"]))
    if ok:
        return True, "PASS"
    if status == "complete" and exp_status == "partial":
        return False, "FAIL - silent omission persists despite an uncertainty channel"
    if exp_status == "complete" and status in ("partial", "defer"):
        return False, f"FAIL - over-deferral (status={status})"
    return False, f"FAIL - wrong content (status={status}, months={months}, unknown={unknown})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["R1", "A1"])
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--expect-digest", default=None)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    expected = json.loads((FIX / "expected_uncertainty.json").read_text(encoding="utf-8"))
    spec = expected["tests"][args.test]
    header_row = spec["given_header_row"]

    tags = json.loads(urllib.request.urlopen(
        "http://localhost:11434/api/tags", timeout=30).read())
    info = next(m for m in tags["models"] if m["name"] == args.model)
    if args.expect_digest and info["digest"] != args.expect_digest:
        raise SystemExit("ABORT: digest mismatch")

    prompt = PROMPT.format(rows=render(FIX / f"{args.test}.csv"), header_row=header_row)
    opts = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": args.seed,
            "num_ctx": args.num_ctx, "num_predict": args.num_predict}
    body = json.dumps({"model": args.model, "think": False, "stream": False,
                       "messages": [{"role": "user", "content": prompt}],
                       "options": opts}).encode()
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(OLLAMA, data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=1800).read())

    content = (resp.get("message") or {}).get("content") or ""
    obj = extract_json(content)
    correct, verdict = grade(obj, spec)

    record = {
        "test": args.test,
        "probe": "2B.4 three-option uncertainty contract",
        "model": {"tag": args.model, "digest": info["digest"],
                  "family": info["details"]["family"],
                  "parameter_size": info["details"]["parameter_size"],
                  "quantization": info["details"]["quantization_level"],
                  "ollama_version": subprocess.run(["ollama", "--version"],
                                                   capture_output=True, text=True).stdout.strip()},
        "think_enabled": False,
        "generation_options": opts,
        "given_header_row": header_row,
        "api_finished": resp.get("done_reason"),
        "content_present": bool(content.strip()),
        "json_parseable": obj is not None,
        "expected": {k: spec[k] for k in
                     ("expected_status", "expected_month_columns", "expected_unknown_columns")},
        "reported": obj,
        "correct": correct,
        "verdict": verdict,
        "raw_reply": content,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    (RESULTS / f"{args.test}_uncertainty_result.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"test={args.test}  api={record['api_finished']}  json={record['json_parseable']}")
    print(f"  expected: status={spec['expected_status']} "
          f"months={spec['expected_month_columns']} unknown={spec['expected_unknown_columns']}")
    print(f"  reported: {obj}")
    print(f"  -> {verdict}")
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
