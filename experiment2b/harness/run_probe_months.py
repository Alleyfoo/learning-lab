"""Experiment 2B.2 — month-column identification probe.

The header row is GIVEN. 2B.1 established it can be found; rediscovering it is
not part of this test. That keeps the capability boundary clean:

    2B.1  locate header           PASS
    2B.2  identify month columns  ?

The prompt states the rows, the header row, the question, the answer contract
and NOTHING about how to recognise a month. No month-name lists, no locale
detection, no positional rules, no type inference.

The contract statements (1-based numbering, exclude non-month columns) are
disambiguation of what counts as an answer, not guidance on how to find one.
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
{{"month_columns": [<integers>]}}

If you cannot determine the answer from the information given, reply with only:
{{"ask_human": true}}
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("test", choices=["E1", "R1", "A1"])
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--expect-digest", default=None)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    src = "expected_ambiguous.json" if args.test == "A1" else "expected_months.json"
    expected = json.loads((FIX / src).read_text(encoding="utf-8"))
    spec = expected["tests"][args.test]
    exp_cols = spec["expected_month_columns"]
    header_row = spec["given_header_row"]
    expects_refusal = spec.get("expected_behaviour") == "ask_human"

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
    asked_human = bool(isinstance(obj, dict) and obj.get("ask_human") is True)
    reported = obj.get("month_columns") if isinstance(obj, dict) else None
    valid = (isinstance(reported, list)
             and all(isinstance(x, int) for x in reported)) or asked_human
    if expects_refusal:
        # ask_human -> PASS. Any month_columns answer -> FAIL, unwarranted.
        correct = asked_human
        grade = ("PASS" if asked_human
                 else "FAIL - unwarranted answer" if isinstance(reported, list)
                 else "FAIL - interface failure")
    else:
        # Order-insensitive exact set match.
        correct = bool(isinstance(reported, list) and sorted(reported) == sorted(exp_cols))
        grade = ("PASS" if correct
                 else "FAIL - wrong set" if isinstance(reported, list)
                 else "FAIL - interface failure")

    record = {
        "test": args.test,
        "probe": "2B.2 month columns",
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
        "valid_structured_output": valid,
        "asked_human": asked_human,
        "expected_month_columns": exp_cols,
        "reported_month_columns": reported,
        "expects_refusal": expects_refusal,
        "grade": grade,
        "correct": correct,
        "raw_reply": content,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    (RESULTS / f"{args.test}_months_result.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"test={args.test}  api={record['api_finished']}  content={record['content_present']}  "
          f"json={record['json_parseable']}  valid={valid}  ask_human={asked_human}")
    print(f"  expected={'ask_human' if expects_refusal else exp_cols}  "
          f"reported={reported}  ask_human={asked_human}  -> {grade}")
    print(f"  raw reply: {content.strip()[:200]!r}")
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
