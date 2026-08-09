"""Run the modelling agent against the task packet via Ollama.

Settings and limits are fixed by spec/run_protocol_ornith9b.md and are NOT
adjusted after results are seen.

The model receives the leak-checked task packet and nothing else. Between
attempts it receives execution feedback from DEVELOPMENT SOURCES ONLY -- whether
its code ran, error traces, and the shape and head of its own output. It never
receives a correctness signal, a held-out file, or any label.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKET = ROOT / "artifacts" / "task_packet"
RESULTS = ROOT / "results"
OLLAMA = "http://localhost:11434/api/chat"

FROZEN = [
    "artifacts/task_packet/TASK.md",
    "artifacts/task_packet/contract.py",
    "artifacts/corpus_manifest.json",
    "artifacts/canonical.csv",
    "harness/evaluate.py",
    "harness/executor.py",
    "harness/reference/oracle_reference.py",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_initial_prompt() -> str:
    parts = [
        "You are given a data task. Read everything, then produce your answer.",
        "\n\n===== TASK.md =====\n",
        (PACKET / "TASK.md").read_text(encoding="utf-8"),
        "\n\n===== contract.py (importable as `from contract import Escalate, AskHuman`) =====\n",
        (PACKET / "contract.py").read_text(encoding="utf-8"),
    ]
    for f in sorted((PACKET / "sources").glob("*.csv")):
        parts.append(f"\n\n===== sources/{f.name} =====\n")
        parts.append(f.read_text(encoding="utf-8"))
    parts.append(
        "\n\n===== YOUR ANSWER =====\n"
        "Reply with a single fenced ```python block containing the complete module. "
        "It must define normalize(source_path: str) -> pandas.DataFrame. "
        "The last fenced python block in your reply is what will be executed."
    )
    return "".join(parts)


def extract_module(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.DOTALL)
    return blocks[-1].strip() + "\n" if blocks else None


def probe(module_path: Path) -> tuple[str, list[dict]]:
    """Run the module on DEV SOURCES ONLY and summarise, with no correctness signal."""
    sys.path.insert(0, str(ROOT / "harness"))
    from executor import run_procedure           # noqa: E402

    reports = []
    for f in sorted((PACKET / "sources").glob("*.csv")):
        r = run_procedure(module_path, f)
        item = {"file": f.name, "outcome": r["outcome"]}
        if r["outcome"] == "ok":
            rows = r["rows"]
            item["n_rows"] = len(rows)
            item["head"] = rows[:3]
        elif r["outcome"] == "escalate":
            item["your_reason"] = r.get("reason")
        elif r["outcome"] == "ask_human":
            item["your_question"] = r.get("question")
        else:
            item["error"] = str(r.get("error") or r.get("missing_columns")
                                or r.get("stderr") or r.get("stdout"))[:600]
        reports.append(item)

    lines = ["Execution feedback from the development sources only.",
             "No correctness information is provided.\n"]
    for it in reports:
        lines.append(f"- {it['file']}: {it['outcome']}"
                     + (f", {it['n_rows']} rows, head={json.dumps(it['head'], ensure_ascii=False)}"
                        if it["outcome"] == "ok" else "")
                     + (f", reason={it['your_reason']!r}" if "your_reason" in it else "")
                     + (f", question={it['your_question']!r}" if "your_question" in it else "")
                     + (f", error={it['error']}" if "error" in it else ""))
    lines.append("\nRevise if you wish. Reply with the complete module in one fenced "
                 "```python block. If you consider it finished, reply with the same module.")
    return "\n".join(lines), reports


def classify(resp: dict) -> str:
    """Mechanical completion class, decided from the API envelope only.

    Declared in spec/run2_preregistration.md section 3. A TRUNCATED attempt is
    preserved but is never evidence about procedure competence.
    """
    content = (resp.get("message") or {}).get("content") or ""
    if resp.get("done_reason") == "length":
        return "TRUNCATED"
    return "COMPLETE" if content.strip() else "EMPTY_NONTRUNCATED"


def chat(model: str, messages: list[dict], opts: dict, think: bool = True) -> dict:
    body = json.dumps({"model": model, "messages": messages, "think": think,
                       "stream": False, "options": opts}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=7200) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ornith:9b")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--label", default="ornith9b")
    ap.add_argument("--num-ctx", type=int, default=32768)
    ap.add_argument("--num-predict", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--no-think", action="store_true",
                    help="disable the model's thinking channel (Ollama think=false)")
    ap.add_argument("--expect-digest", default=None,
                    help="abort unless the model digest matches exactly")
    ap.add_argument("--expect-frozen", type=Path, default=None,
                    help="abort unless frozen sha256 match this manifest's")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    opts = {"temperature": 0.6, "top_p": 0.95, "top_k": 20,
            "seed": args.seed, "num_ctx": args.num_ctx, "num_predict": args.num_predict}
    think = not args.no_think

    frozen = {f: sha(ROOT / f) for f in FROZEN}
    tags = json.loads(urllib.request.urlopen(
        "http://localhost:11434/api/tags", timeout=30).read())
    info = next(m for m in tags["models"] if m["name"] == args.model)

    if args.expect_digest and info["digest"] != args.expect_digest:
        raise SystemExit(f"ABORT: digest {info['digest']} != expected {args.expect_digest}")
    if args.expect_frozen:
        prior = json.loads(args.expect_frozen.read_text(encoding="utf-8"))["frozen_sha256"]
        drift = {k: (prior[k], frozen[k]) for k in prior if prior.get(k) != frozen.get(k)}
        if drift:
            raise SystemExit(f"ABORT: frozen artifacts changed since the prior run: {drift}")
        print("frozen artifacts verified identical to prior run")

    transcript, completion = [], []
    messages = [{"role": "user", "content": build_initial_prompt()}]
    submission = RESULTS / f"submission_{args.label}.py"
    final_module, attempts_used, probes = None, 0, []

    for attempt in range(1, args.attempts + 1):
        attempts_used = attempt
        print(f"--- attempt {attempt}/{args.attempts} ---", flush=True)
        resp = chat(args.model, messages, opts, think=think)
        reply = (resp.get("message") or {}).get("content") or ""
        cls = classify(resp)
        env = {"done_reason": resp.get("done_reason"),
               "eval_count": resp.get("eval_count"),
               "prompt_eval_count": resp.get("prompt_eval_count"),
               "thinking_chars": len((resp.get("message") or {}).get("thinking") or ""),
               "content_chars": len(reply)}
        completion.append({"attempt": attempt, "class": cls, **env})
        print(f"  {cls}  done_reason={env['done_reason']} eval={env['eval_count']} "
              f"content={env['content_chars']}ch thinking={env['thinking_chars']}ch")
        transcript.append({"attempt": attempt, "role": "assistant", "content": reply,
                           "completion_class": cls, "envelope": env})
        messages.append({"role": "assistant", "content": reply})

        module = extract_module(reply)
        if module is None:
            print("  no fenced python block in reply")
            if attempt < args.attempts:
                fb = ("Your reply contained no fenced ```python block. Reply with the "
                      "complete module in one fenced ```python block.")
                transcript.append({"attempt": attempt, "role": "user", "content": fb})
                messages.append({"role": "user", "content": fb})
            continue

        final_module = module
        submission.write_text(module, encoding="utf-8")
        fb, rep = probe(submission)
        probes.append({"attempt": attempt, "reports": rep})
        ok = sum(1 for r in rep if r["outcome"] == "ok")
        esc = sum(1 for r in rep if r["outcome"] == "escalate")
        print(f"  dev probe: ok={ok}/12 escalate={esc}/12")

        if attempt < args.attempts:
            transcript.append({"attempt": attempt, "role": "user", "content": fb})
            messages.append({"role": "user", "content": fb})

    manifest = {
        "label": args.label,
        "model": {"tag": args.model, "digest": info["digest"],
                  "family": info["details"]["family"],
                  "parameter_size": info["details"]["parameter_size"],
                  "quantization": info["details"]["quantization_level"],
                  "context_length": info["details"]["context_length"],
                  "ollama_version": subprocess.run(
                      ["ollama", "--version"], capture_output=True, text=True
                  ).stdout.strip()},
        "generation_options": opts,
        "think_enabled": think,
        "seed": args.seed,
        "attempts_allowed": args.attempts,
        "attempts_used": attempts_used,
        "completion_classes": completion,
        "completion_summary": {c: sum(1 for x in completion if x["class"] == c)
                               for c in ("COMPLETE", "TRUNCATED", "EMPTY_NONTRUNCATED")},
        "packet_files": ["TASK.md", "contract.py"] + sorted(
            f.name for f in (PACKET / "sources").glob("*.csv")),
        "withheld": ["canonical.csv", "canonical_manifest.json", "corpus_manifest.json",
                     "H*.csv", "A*.csv", "corpus_reuse/*", "generator/vocabulary.py",
                     "harness/reference/oracle_reference.py"],
        "frozen_sha256": frozen,
        "submission": submission.name if final_module else None,
        "submission_sha256": sha(submission) if final_module else None,
        "dev_probes": probes,
    }
    (RESULTS / f"run_{args.label}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / f"transcript_{args.label}.json").write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nsubmission: {submission if final_module else 'NONE PRODUCED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
