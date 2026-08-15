#!/usr/bin/env python3
"""Run V's frozen prompts. Raw text preserved verbatim, one file per probe.

HTTP API with `stream: false`. The `ollama run` CLI re-renders lines and
duplicated fragments mid-JSON in an earlier experiment, corrupting captures; the
API is used instead so what is graded is what the model returned.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "spec"
RESULTS = ROOT / "results"
MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())["response"]


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    arms = argv or ["V1", "V2"]
    for arm in arms:
        prompt = (SPEC / f"frozen_prompt_{arm}.txt").read_text(encoding="utf-8")
        for probe in (1, 2, 3):
            out = RESULTS / f"{arm}_probe{probe}_raw.txt"
            if out.exists():
                print(f"{out.name} exists -- not re-run (no retries)")
                continue
            print(f"{arm} probe {probe} ...", flush=True)
            out.write_text(ask(prompt), encoding="utf-8")
            print(f"  -> {out.name} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
