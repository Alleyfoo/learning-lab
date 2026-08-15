#!/usr/bin/env python3
"""Send the FROZEN prompt to the model and capture the answer without mangling it.

## Why this exists

The first three probes were captured with `ollama run < prompt.txt`. That CLI
re-renders lines at wrap boundaries, and a shell redirect captures BOTH renders,
so the saved text contains duplicated fragments mid-JSON:

    "purpose": "...unless the date is malfo
    malformed, a holiday..."

The model's answer was not wrong; the RECORDING was. Those probes are preserved
as `probe{1,2,3}_raw.txt` and marked NON-EVIDENTIAL: they measured the capture,
not the model.

This uses the HTTP API with `stream: false`, which returns one JSON body and
cannot wrap-duplicate.

**The prompt is byte-identical to the frozen one.** Nothing about the experiment
changed -- only the transport. Repairing an instrument that never produced a
readable result is not the retry the preregistration forbids; that rule is about
re-running after seeing an answer one dislikes, and no answer was legible here.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"
RESULTS = HERE.parent / "results"
PROMPT = SPEC / "frozen_prompt.txt"

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"


def ask(prompt: str, model: str = MODEL, timeout: int = 300) -> dict:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    request = urllib.request.Request(ENDPOINT, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 3
    prompt = PROMPT.read_text(encoding="utf-8")
    RESULTS.mkdir(exist_ok=True)

    for i in range(1, n + 1):
        tag = f"clean{i}"
        payload = ask(prompt)
        answer = payload.get("response", "")
        (RESULTS / f"{tag}_raw.txt").write_text(answer, encoding="utf-8")
        print(f"probe {tag}: {len(answer)} chars captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
