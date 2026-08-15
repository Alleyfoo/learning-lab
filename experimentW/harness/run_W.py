#!/usr/bin/env python3
"""Run the W chain. Three stages per probe, everything preserved verbatim.

```text
stage 1  inspect   observed facts -> INFERRED + UNKNOWN, each addressed
stage 2  model     the ingested report -> a node, or a structured block
stage 3  resume    after confirming EXACTLY the referents stage 2 named
```

Stage 3 runs only if stage 2 blocked, and confirms only what stage 2 asked
about. Nothing is chosen by hand -- that is the difference from U2.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))

import boundary  # noqa: E402
import build_prompts as w  # noqa: E402

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())["response"]


def _objects(text: str):
    """Every top-level JSON value in the text, in order."""
    body = re.sub(r"```(?:json)?", "", text)
    out = []
    for opener, closer in (("[", "]"), ("{", "}")):
        for start in (i for i, c in enumerate(body) if c == opener):
            depth = 0
            for i in range(start, len(body)):
                if body[i] == opener:
                    depth += 1
                elif body[i] == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            out.append((start, json.loads(body[start:i + 1])))
                        except json.JSONDecodeError:
                            pass
                        break
    return [obj for _, obj in sorted(out)]


def claim_list(text: str):
    best = None
    for obj in _objects(text):
        if (isinstance(obj, list) and obj
                and all(isinstance(x, dict) and "claim" in x for x in obj)):
            if best is None or len(obj) > len(best):
                best = obj
    return best


def block_of(text: str):
    for obj in _objects(text):
        if isinstance(obj, dict) and isinstance(obj.get("CANNOT_ESTABLISH"), list):
            return obj["CANNOT_ESTABLISH"]
    return None


def node_of(text: str):
    keys = ("task", "rules", "on_accept", "model_version")
    found = None
    for obj in _objects(text):
        if isinstance(obj, dict) and sum(k in obj for k in keys) >= 2:
            found = obj
    return found


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    observed = w.u_claims.observed_claims()
    inspect = w.inspect_prompt(observed)

    for probe in (1, 2, 3):
        tag = f"probe{probe}"

        # --- stage 1 --------------------------------------------------------
        f1 = RESULTS / f"{tag}_stage1_inspect_raw.txt"
        if not f1.exists():
            print(f"{tag} stage 1 inspect ...", flush=True)
            f1.write_text(ask(inspect), encoding="utf-8")
        raw = claim_list(f1.read_text(encoding="utf-8"))
        if raw is None:
            print(f"{tag}: stage 1 produced no claim list; chain stops here")
            continue
        ingested = boundary.ingest(raw)
        report = boundary.merge(observed, ingested)
        (RESULTS / f"{tag}_stage1_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{tag} stage 1: {len(raw)} emitted, {len(ingested.accepted)} accepted, "
              f"{len(ingested.rejected)} rejected {[r['code'] for r in ingested.rejected]}")

        # --- stage 2 --------------------------------------------------------
        f2 = RESULTS / f"{tag}_stage2_model_raw.txt"
        if not f2.exists():
            print(f"{tag} stage 2 model ...", flush=True)
            f2.write_text(ask(w.model_prompt(report)), encoding="utf-8")
        text2 = f2.read_text(encoding="utf-8")
        block = block_of(text2)
        if block is None:
            print(f"{tag} stage 2: NO BLOCK -- node produced: {node_of(text2) is not None}")
            continue
        refs = [{"source": b.get("source"), "field": b.get("field")} for b in block]
        print(f"{tag} stage 2: blocked on {len(block)} referent(s): "
              f"{[(r['source'], r['field']) for r in refs]}")

        # --- stage 3: confirm EXACTLY what was asked -------------------------
        confirmed = boundary.confirm(report, refs)
        (RESULTS / f"{tag}_stage3_report.json").write_text(
            json.dumps(confirmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        moved = [c for c in confirmed if c.get("status") == "CONFIRMED"]
        print(f"{tag} stage 3: {len(moved)} claim(s) promoted at those referents")
        f3 = RESULTS / f"{tag}_stage3_resume_raw.txt"
        if not f3.exists():
            print(f"{tag} stage 3 resume ...", flush=True)
            f3.write_text(ask(w.model_prompt(confirmed, resumed=True)), encoding="utf-8")
        print(f"{tag} stage 3: node produced: "
              f"{node_of(f3.read_text(encoding='utf-8')) is not None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
