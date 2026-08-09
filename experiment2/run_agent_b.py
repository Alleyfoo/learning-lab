"""Condition B: guided warm-up (training), then the unseen condition-A task (scored).

Fixed by spec/condition_b_preregistration.md.

PHASE 1 is TRAINING, NOT EVIDENCE. It is the only place correctness is revealed,
because teaching is its purpose. PHASE 2 is byte-identical to condition A and is
the only phase scored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

import pandas as pd

from run_agent import (FROZEN, RESULTS, build_initial_prompt, chat, classify,
                       extract_module, probe, sha)
from run_agent import ROOT  # noqa: E402

WARMUP = ROOT / "warmup"

BOUNDARY_MESSAGE = (
    "That procedure passed the supplied example. Use what you learned from this task "
    "when handling the next source, but do not assume the next source has the same "
    "layout or naming."
)

WARMUP_PROMPT = """You are being shown one worked example before your real task.

Here is a source file. Turn it into the canonical form described below.

===== source =====
{source}

===== required canonical output =====
A pandas.DataFrame with exactly these columns:
  country     two-letter uppercase code
  product_id  the product identifier as issued by the business
  period      the calendar month, YYYY-MM
  sales       the sales value, number, 2 decimal places
Grain: one row per (country, product_id, period).

===== what to do =====
- inspect the source
- map it into the required canonical columns
- preserve every business row
- if the source uses a different shape, reshape it as needed
- if a value is ambiguous, do not guess - use Escalate or AskHuman
- return a reusable normalize(source_path) procedure, not merely the transformed data

`contract.py` is importable: `from contract import Escalate, AskHuman`.

Reply with a single fenced ```python block containing the complete module defining
normalize(source_path: str) -> pandas.DataFrame.
"""


def warmup_verdict(module: Path) -> tuple[bool, str]:
    """Run the module on the warm-up source and compare to warm-up truth."""
    import sys
    sys.path.insert(0, str(ROOT / "harness"))
    from executor import run_procedure           # noqa: E402

    res = run_procedure(module, WARMUP / "warmup_source.csv")
    if res["outcome"] != "ok":
        detail = res.get("error") or res.get("missing_columns") or res.get("reason") or res
        return False, f"Your procedure did not produce a table. outcome={res['outcome']}, {detail}"

    got = pd.DataFrame(res["rows"])[["country", "product_id", "period", "sales"]]
    got["sales"] = got["sales"].astype(float).round(2)
    got = got.sort_values(list(got.columns[:3])).reset_index(drop=True)
    want = pd.read_csv(WARMUP / "warmup_truth.csv")
    want["sales"] = want["sales"].astype(float).round(2)
    want = want.sort_values(list(want.columns[:3])).reset_index(drop=True)

    if got.equals(want):
        return True, "PASS"
    return False, (f"Output does not match the expected result. "
                   f"You produced {len(got)} rows; {len(want)} were expected. "
                   f"Your first rows: {got.head(3).to_dict('records')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--warmup-attempts", type=int, default=3)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--num-ctx", type=int, default=65536)
    ap.add_argument("--num-predict", type=int, default=32768)
    ap.add_argument("--no-think", action="store_true")
    ap.add_argument("--only-source", action="append", default=None)
    ap.add_argument("--expect-digest", default=None)
    ap.add_argument("--expect-frozen", type=Path, default=None)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    opts = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": args.seed,
            "num_ctx": args.num_ctx, "num_predict": args.num_predict}
    think = not args.no_think

    frozen = {f: sha(ROOT / f) for f in FROZEN}
    tags = json.loads(urllib.request.urlopen(
        "http://localhost:11434/api/tags", timeout=30).read())
    info = next(m for m in tags["models"] if m["name"] == args.model)
    if args.expect_digest and info["digest"] != args.expect_digest:
        raise SystemExit(f"ABORT: digest mismatch")
    if args.expect_frozen:
        prior = json.loads(args.expect_frozen.read_text(encoding="utf-8"))["frozen_sha256"]
        drift = {k for k in prior if prior.get(k) != frozen.get(k)}
        if drift:
            raise SystemExit(f"ABORT: frozen artifacts changed: {drift}")
        print("frozen artifacts verified identical to prior run")

    transcript, messages = [], []
    tmp = RESULTS / f"_warmup_{args.label}.py"

    # ---------------- PHASE 1: WARM-UP (TRAINING, NOT EVIDENCE) --------------
    print("=== PHASE 1: warm-up (TRAINING, NOT SCORED) ===", flush=True)
    warmup_passed, warmup_attempt = False, None
    messages.append({"role": "user", "content": WARMUP_PROMPT.format(
        source=(WARMUP / "warmup_source.csv").read_text(encoding="utf-8"))})

    for a in range(1, args.warmup_attempts + 1):
        resp = chat(args.model, messages, opts, think=think)
        reply = (resp.get("message") or {}).get("content") or ""
        cls = classify(resp)
        transcript.append({"phase": "warmup", "attempt": a, "role": "assistant",
                           "content": reply, "completion_class": cls,
                           "done_reason": resp.get("done_reason"),
                           "eval_count": resp.get("eval_count")})
        messages.append({"role": "assistant", "content": reply})
        mod = extract_module(reply)
        if mod is None:
            fb = "Your reply contained no fenced ```python block. Reply with one."
        else:
            tmp.write_text(mod, encoding="utf-8")
            ok, detail = warmup_verdict(tmp)
            print(f"  attempt {a}: {cls}  warmup={'PASS' if ok else 'FAIL'}")
            if ok:
                warmup_passed, warmup_attempt = True, a
                break
            fb = detail + "\n\nRevise and reply with the complete module in one fenced ```python block."
        transcript.append({"phase": "warmup", "attempt": a, "role": "user", "content": fb})
        messages.append({"role": "user", "content": fb})

    if warmup_passed:
        messages.append({"role": "user", "content": BOUNDARY_MESSAGE})
        transcript.append({"phase": "boundary", "role": "user", "content": BOUNDARY_MESSAGE})
        print(f"  warm-up PASSED on attempt {warmup_attempt}; boundary message delivered")
    else:
        print("  warm-up FAILED; phase 2 still runs, seed recorded as warmup_failed")

    # ---------------- PHASE 2: REAL TASK (SCORED) ---------------------------
    print("=== PHASE 2: condition-A task (SCORED) ===", flush=True)
    real_prompt = build_initial_prompt(args.only_source)
    messages.append({"role": "user", "content": real_prompt})
    submission = RESULTS / f"submission_{args.label}.py"
    final, completion, probes = None, [], []

    for a in range(1, args.attempts + 1):
        resp = chat(args.model, messages, opts, think=think)
        reply = (resp.get("message") or {}).get("content") or ""
        cls = classify(resp)
        env = {"done_reason": resp.get("done_reason"), "eval_count": resp.get("eval_count"),
               "content_chars": len(reply),
               "thinking_chars": len((resp.get("message") or {}).get("thinking") or "")}
        completion.append({"attempt": a, "class": cls, **env})
        print(f"  attempt {a}: {cls} done={env['done_reason']} eval={env['eval_count']} "
              f"content={env['content_chars']}ch")
        transcript.append({"phase": "real", "attempt": a, "role": "assistant",
                           "content": reply, "completion_class": cls, "envelope": env})
        messages.append({"role": "assistant", "content": reply})

        mod = extract_module(reply)
        if mod is None:
            if a < args.attempts:
                fb = "Your reply contained no fenced ```python block. Reply with one."
                transcript.append({"phase": "real", "attempt": a, "role": "user", "content": fb})
                messages.append({"role": "user", "content": fb})
            continue
        final = mod
        submission.write_text(mod, encoding="utf-8")
        fb, rep = probe(submission)
        probes.append({"attempt": a, "reports": rep})
        print(f"    dev probe: ok={sum(1 for r in rep if r['outcome']=='ok')}/12")
        if a < args.attempts:
            transcript.append({"phase": "real", "attempt": a, "role": "user", "content": fb})
            messages.append({"role": "user", "content": fb})

    if tmp.exists():
        tmp.unlink()

    (RESULTS / f"run_{args.label}_manifest.json").write_text(json.dumps({
        "condition": "B",
        "only_source": args.only_source,
        "label": args.label, "seed": args.seed,
        "model": {"tag": args.model, "digest": info["digest"]},
        "generation_options": opts, "think_enabled": think,
        "warmup_passed": warmup_passed, "warmup_attempt": warmup_attempt,
        "phase1_role": "TRAINING - NOT EVIDENCE, NOT SCORED",
        "phase2_prompt_sha256": hashlib.sha256(real_prompt.encode()).hexdigest(),
        "completion_classes": completion,
        "completion_summary": {c: sum(1 for x in completion if x["class"] == c)
                               for c in ("COMPLETE", "TRUNCATED", "EMPTY_NONTRUNCATED")},
        "frozen_sha256": frozen,
        "submission": submission.name if final else None,
        "submission_sha256": sha(submission) if final else None,
        "dev_probes": probes,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / f"transcript_{args.label}.json").write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nwarm-up passed: {warmup_passed}   submission: "
          f"{submission if final else 'NONE PRODUCED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
