"""Completion pipeline — replaces the overloaded COMPLETE/TRUNCATED classifier.

Correction earned by measurement, not by design taste. Condition B seed 33333
returned `done_reason = "stop"` on attempts whose content ended *inside an
identifier* with an unclosed code fence. The API said the generation finished;
the artifact was plainly incomplete. One boolean cannot carry both facts.

Six stages, recorded independently. Each is a fact, not a judgement:

    API_FINISHED          stop vs length
    CONTENT_PRESENT       yes/no
    SUBMISSION_EXTRACTED  yes/no
    PYTHON_PARSEABLE      yes/no
    MODULE_LOADABLE       yes/no
    PROCEDURE_EXECUTABLE  yes/no

Prior outcomes are NOT rewritten. This annotates them. Runs post hoc from a
transcript plus its submission, so it applies to every run already recorded.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PACKET = ROOT / "artifacts" / "task_packet"
FENCE = "`" * 3


def extract_strict(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.DOTALL)
    return blocks[-1].strip() + "\n" if blocks else None


def extract_lenient(text: str) -> str | None:
    """Everything after the last opening fence, closing fence not required."""
    i = text.rfind(FENCE + "python")
    if i < 0:
        i = text.rfind(FENCE + "py")
        if i < 0:
            return None
    body = text[i:].split("\n", 1)
    return body[1] if len(body) > 1 else None


def stages_for(reply: str, envelope: dict) -> dict:
    s = {
        "API_FINISHED": envelope.get("done_reason"),
        "CONTENT_PRESENT": bool((reply or "").strip()),
    }
    strict = extract_strict(reply or "")
    lenient = extract_lenient(reply or "")
    s["SUBMISSION_EXTRACTED"] = strict is not None
    s["SUBMISSION_EXTRACTED_LENIENT"] = lenient is not None

    def parses(src):
        if not src:
            return False, "no source"
        try:
            ast.parse(src)
            return True, None
        except SyntaxError as exc:
            return False, f"{exc.msg} (line {exc.lineno})"

    ok_s, err_s = parses(strict)
    ok_l, err_l = parses(lenient)
    s["PYTHON_PARSEABLE"] = ok_s
    s["PYTHON_PARSEABLE_LENIENT"] = ok_l
    s["parse_error_strict"] = err_s
    s["parse_error_lenient"] = err_l
    return s


def analyse_label(label: str) -> dict:
    tpath = RESULTS / f"transcript_{label}.json"
    if not tpath.exists():
        return {"label": label, "error": "no transcript"}
    transcript = json.loads(tpath.read_text(encoding="utf-8"))

    per_attempt = []
    for e in transcript:
        if e.get("role") != "assistant":
            continue
        if e.get("phase") == "warmup":
            continue          # phase 1 is training, not evidence
        env = e.get("envelope") or {"done_reason": e.get("done_reason")}
        st = stages_for(e.get("content", ""), env)
        st["attempt"] = e.get("attempt")
        st["legacy_class"] = e.get("completion_class")
        per_attempt.append(st)

    sub = RESULTS / f"submission_{label}.py"
    module = {"MODULE_LOADABLE": False, "PROCEDURE_EXECUTABLE": False}
    if sub.exists():
        try:
            ast.parse(sub.read_text(encoding="utf-8"))
            module["MODULE_LOADABLE"] = None      # filled below by real execution
        except SyntaxError as exc:
            module["parse_error"] = f"{exc.msg} (line {exc.lineno})"
        import sys
        sys.path.insert(0, str(ROOT / "harness"))
        from executor import run_procedure       # noqa: E402
        probe = run_procedure(sub, PACKET / "sources" / "D01.csv")
        module["MODULE_LOADABLE"] = probe["outcome"] not in ("load_error",)
        module["PROCEDURE_EXECUTABLE"] = probe["outcome"] in ("ok", "escalate", "ask_human")
        module["probe_outcome"] = probe["outcome"]

    return {"label": label, "per_attempt": per_attempt, "submission": module}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    args = ap.parse_args()

    out = {}
    for label in args.labels:
        r = analyse_label(label)
        out[label] = r
        print(f"=== {label} ===")
        if "error" in r:
            print(f"  {r['error']}")
            continue
        for a in r["per_attempt"]:
            print(f"  attempt {a['attempt']}: api={a['API_FINISHED']:6s} "
                  f"content={a['CONTENT_PRESENT']!s:5s} extracted={a['SUBMISSION_EXTRACTED']!s:5s} "
                  f"(lenient={a['SUBMISSION_EXTRACTED_LENIENT']!s:5s}) "
                  f"parses={a['PYTHON_PARSEABLE']!s:5s} "
                  f"(lenient={a['PYTHON_PARSEABLE_LENIENT']!s:5s})"
                  + (f"  [legacy={a['legacy_class']}]" if a.get("legacy_class") else ""))
        m = r["submission"]
        print(f"  submission: loadable={m['MODULE_LOADABLE']} "
              f"executable={m['PROCEDURE_EXECUTABLE']} probe={m.get('probe_outcome')}")

    (RESULTS / "completion_pipeline.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
