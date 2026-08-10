"""Experiment 3B.2 — different-model reviewer under the ORIGINAL neutral contract.

Only the reviewer model changes relative to 3A's G3 reviewer: same A1 context, same
three propositions (C1, C2, T), same output schema, same single run each, but the
reviewer is a different model family invoked via the Ollama HTTP API, and the contract
is 3A's original neutral reviewer contract (NOT the evidence-burden one).

Model: llama3.1:8b (fallback gemma4:latest if a control proposition returns invalid JSON).
This tests model diversity, not epistemic independence (two models can share a prior).

Usage:
    python run_3b2.py
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path

from render_rows import render

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT.parent / "experiment2b" / "fixtures" / "A1.csv"
RESULTS = ROOT / "results"
JUDGE = ROOT / "judgements"
OLLAMA = "http://localhost:11434/api/chat"
TAGS = "http://localhost:11434/api/tags"

PRIMARY = "llama3.1:8b"
FALLBACK = "gemma4:latest"

# 3A's original NEUTRAL reviewer contract (verbatim).
NEUTRAL_CONTRACT = """You are WarrantReviewer, a narrow specialist.

You are reviewing whether a proposed classification is supported by evidence. You are NOT reclassifying from scratch.

Original source evidence (a tabular source file, one row per block, cells separated by " | "):

{rows}

The data header is row 4: Tuote | Tammi | Helmi | Jakso A | Huhti | Touko

Proposed classification: column {col}, cell "{cell}", is classified as {proposed} (i.e. this column {meaning}).

Your only task: determine whether the supplied evidence SUPPORTS that specific proposed classification.

Do not write code. Do not explain your reasoning. Do not assume facts not in the evidence. You see only the evidence above and the proposal — not any reasoning that produced the proposal.

Return exactly one JSON object and nothing else — no prose, no code fence, no commentary:

  {{"warrant": "supported"}}              — the evidence establishes the proposed classification
  {{"warrant": "insufficient_evidence"}}  — the evidence does not establish it

A proposal is "supported" only if the evidence is sufficient to establish that specific claim. If the evidence is consistent with the proposal AND with a different classification, the proposal is not established. Suggestive is not established. Positional adjacency is not, by itself, established evidence."""

VALID = {"supported", "insufficient_evidence"}
MEANING = {"month": "represents a calendar month", "not_month": "does NOT represent a calendar month"}

PROPOSITIONS = [
    {"id": "C1", "column": 2, "cell": "Tammi",   "proposed": "month"},
    {"id": "C2", "column": 1, "cell": "Tuote",   "proposed": "not_month"},
    {"id": "T",  "column": 4, "cell": "Jakso A", "proposed": "not_month"},
]


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


def call_ollama(model: str, prompt: str, opts: dict) -> tuple[str, str | None]:
    body = json.dumps({"model": model, "think": False, "stream": False,
                       "messages": [{"role": "user", "content": prompt}],
                       "options": opts}).encode()
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(OLLAMA, data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=1800).read())
    content = (resp.get("message") or {}).get("content") or ""
    obj = extract_json(content)
    warrant = obj.get("warrant") if isinstance(obj, dict) else None
    return content, warrant


def run_all(model: str, opts: dict, rows: str) -> list[dict]:
    out = []
    for p in PROPOSITIONS:
        prompt = NEUTRAL_CONTRACT.format(rows=rows, col=p["column"], cell=p["cell"],
                                         proposed=p["proposed"], meaning=MEANING[p["proposed"]])
        raw, warrant = call_ollama(model, prompt, opts)
        out.append({"id": p["id"], "column": p["column"], "cell": p["cell"],
                    "proposed": p["proposed"], "raw_output": raw, "warrant": warrant,
                    "valid": warrant in VALID})
        flag = warrant if warrant in VALID else f"INVALID({warrant!r})"
        print(f"  [{model}] {p['id']} {p['cell']!r:<10} {p['proposed']:<9} -> {flag}")
    return out


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    JUDGE.mkdir(exist_ok=True)
    rows = render(FIX)

    tags = json.loads(urllib.request.urlopen(TAGS, timeout=30).read())
    info = {m["name"]: m for m in tags["models"]}

    opts = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": 20260809,
            "num_ctx": 8192, "num_predict": 2048}

    model = PRIMARY
    if model not in info:
        model = FALLBACK
    digest = info[model]["digest"]
    print(f"3B.2 reviewer model: {model}  digest {digest[:12]}")

    results = run_all(model, opts, rows)
    used_fallback = False

    # Fallback rule (frozen): if a CONTROL proposition returns invalid JSON, re-run all
    # three with the fallback model and record the primary's interface failure.
    control_invalid = any(not r["valid"] for r in results if r["id"] in ("C1", "C2"))
    if control_invalid and model == PRIMARY and FALLBACK in info:
        print(f"  control produced invalid JSON on {PRIMARY}; falling back to {FALLBACK}")
        used_fallback = True
        model = FALLBACK
        digest = info[model]["digest"]
        results = run_all(model, opts, rows)

    def w(pid: str) -> str:
        v = next(r["warrant"] for r in results if r["id"] == pid)
        return v if v in VALID else f"INVALID({v!r})"

    c1, c2, t = w("C1"), w("C2"), w("T")
    if c1 == "supported" and c2 == "supported" and t == "insufficient_evidence":
        row, passed = "model_diversity_helps", True
    elif c1 == "supported" and c2 == "supported" and t == "supported":
        row, passed = "target_supported_ambiguity_harder", False
    elif c1 == "insufficient_evidence" and c2 == "insufficient_evidence" and t == "insufficient_evidence":
        row, passed = "paranoid", False
    else:
        row, passed = "mixed_or_interface", False

    record = {
        "probe": "3B.2",
        "model": {"tag": model, "digest": digest,
                  "family": info[model]["details"]["family"],
                  "parameter_size": info[model]["details"]["parameter_size"],
                  "ollama_version": subprocess.run(["ollama", "--version"],
                                                   capture_output=True, text=True).stdout.strip()},
        "used_fallback": used_fallback,
        "primary_interface_failed": control_invalid and used_fallback,
        "contract": "3A original neutral reviewer contract (NOT evidence-burden)",
        "generation_options": opts,
        "propositions": results,
        "pattern": {"C1_Tammi": c1, "C2_Tuote": c2, "T_JaksoA": t},
        "decision_row": row,
        "passed": passed,
        "pass_criterion": "C1=supported AND C2=supported AND T=insufficient_evidence",
    }
    (JUDGE / "3b2.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    (RESULTS / "3b2.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print(f"[3B.2] decision_row={row}  passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())