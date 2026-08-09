"""Experiment 2B — header-row discovery probe.

One question, one tiny structured answer. No code artifact is requested, so the
Python/module pipeline from Experiment 2A is deliberately absent.

The prompt states the question and the required output format and NOTHING about
how to find a header row. No mention of month names, numeric rows, keyword
lists, locale, types or position. The model chooses its own reasoning.
"""

from __future__ import annotations

import argparse
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

Which row contains the headers for the actual data table?

Reply with only this JSON object and nothing else:
{{"header_row": <integer>}}
"""


def extract_json(text: str) -> dict | None:
    """Accept a bare object or one inside a fenced block. Nothing else."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["E1", "R1"])
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--expect-digest", default=None)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
    exp_row = expected["tests"][args.test]["expected_header_row"]

    tags = json.loads(urllib.request.urlopen(
        "http://localhost:11434/api/tags", timeout=30).read())
    info = next(m for m in tags["models"] if m["name"] == args.model)
    if args.expect_digest and info["digest"] != args.expect_digest:
        raise SystemExit("ABORT: digest mismatch")

    prompt = PROMPT.format(rows=render(FIX / f"{args.test}.csv"))
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
    reported = obj.get("header_row") if isinstance(obj, dict) else None
    valid = isinstance(reported, int)

    record = {
        "test": args.test,
        "model": {"tag": args.model, "digest": info["digest"],
                  "family": info["details"]["family"],
                  "parameter_size": info["details"]["parameter_size"],
                  "quantization": info["details"]["quantization_level"],
                  "ollama_version": subprocess.run(["ollama", "--version"],
                                                   capture_output=True, text=True).stdout.strip()},
        "think_enabled": False,
        "generation_options": opts,
        "api_finished": resp.get("done_reason"),
        "content_present": bool(content.strip()),
        "json_parseable": obj is not None,
        "valid_structured_output": valid,
        "expected_header_row": exp_row,
        "reported_header_row": reported,
        "correct": bool(valid and reported == exp_row),
        "raw_reply": content,
        "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(),
    }
    (RESULTS / f"{args.test}_result.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"test={args.test}  api_finished={record['api_finished']}  "
          f"content={record['content_present']}  json={record['json_parseable']}  "
          f"valid={record['valid_structured_output']}")
    print(f"  expected={exp_row}  reported={reported}  "
          f"CORRECT={record['correct']}")
    print(f"  raw reply: {content.strip()[:200]!r}")
    return 0 if record["correct"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
