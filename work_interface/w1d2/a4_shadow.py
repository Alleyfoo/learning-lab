#!/usr/bin/env python3
"""W1-D2 A4 SHADOW AUDIT — descriptive only, after the complete batch.

    A4_SHADOW = CLEAN | WOULD_CONTEST

**This is not a W1-D2 verdict.** The primary independent outcomes remain
STRUCTURAL and FIDELITY. A4 did not terminate, alter, rescue or otherwise
influence L1/L2/L3 — the batch ran with `fs_enforcing=False`, so no filesystem
verdict was computed in-run and none could reach an outcome.

Its only job is to answer, descriptively: *would this worker have violated the
future Surface-A policy?* That makes W1-D2 comparable with W1-C (where H2 created
`temp_skill.txt`) without letting an unadopted surface change this experiment's
result.

The pre-run snapshot recorded by the harness is the baseline. Files the HARNESS
itself writes are excluded by name — they are not worker output and must not be
counted against the worker.

    python work_interface/w1d2/a4_shadow.py

Read-only. Nothing is deleted, moved or repaired.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WI = HERE.parent
sys.path.insert(0, str(WI / "authority"))
import fs_backstop as A4  # noqa: E402

RUNS = ["L1", "L2", "L3"]
ARTIFACT = "work_definition.json"

# Written by the harness, not by the worker.
HARNESS_OWNED = {"acp_transcript.jsonl", "harness_result.json"}

CLEAN, WOULD_CONTEST = "CLEAN", "WOULD_CONTEST"


def main() -> int:
    records, contested = [], 0
    for run in RUNS:
        d = HERE / "runs" / run
        hr = d / "harness_result.json"
        if not hr.is_file():
            records.append({"run": run, "a4_shadow": "NO_RUN_RECORD"})
            continue
        data = json.loads(hr.read_text(encoding="utf-8"))
        before = data.get("fs_snapshot_before") or {}
        after = {k: v for k, v in A4.snapshot(d).items()
                 if k not in HARNESS_OWNED}
        v = A4.verdict(before, after, designated=ARTIFACT)
        status = WOULD_CONTEST if v.violated else CLEAN
        if v.violated:
            contested += 1
        records.append({
            "run": run,
            "a4_shadow": status,
            "binding": False,
            "harness_outcome": data.get("outcome"),
            "violations": [{"kind": m.kind, "path": m.path,
                            "from_path": m.from_path, "detail": m.detail}
                           for m in v.mutations],
            "permitted": [{"kind": m.kind, "path": m.path} for m in v.allowed],
            "reason": v.reason,
        })

    lines = ["# W1-D2 A4 shadow audit", "",
             "**Descriptive only. NOT a W1-D2 verdict.** The primary independent",
             "outcomes are STRUCTURAL and FIDELITY. A4 ran in shadow mode and did",
             "not terminate, alter, rescue or influence any run.", "",
             "Harness-written files (`acp_transcript.jsonl`,",
             "`harness_result.json`) are excluded: they are not worker output.",
             "", "| run | A4_SHADOW | harness outcome | violations |",
             "|---|---|---|---|"]
    for r in records:
        lines.append(f"| {r['run']} | **{r['a4_shadow']}** | "
                     f"{r.get('harness_outcome', '-')} | "
                     f"{len(r.get('violations', []))} |")
    lines += ["", "## Detail", ""]
    for r in records:
        lines.append(f"### {r['run']} — {r['a4_shadow']}")
        for m in r.get("permitted", []):
            lines.append(f"- permitted: {m['kind']} `{m['path']}`")
        for m in r.get("violations", []):
            frm = f" (from `{m['from_path']}`)" if m.get("from_path") else ""
            lines.append(f"- **would contest**: {m['kind']} `{m['path']}`{frm} "
                         f"— {m['detail']}")
        if not r.get("violations") and r.get("permitted") is not None:
            lines.append("- no unauthorized filesystem mutation")
        lines.append("")
    lines += [f"**{contested}/{len(RUNS)} would have violated the future "
              f"Surface-A policy.**", ""]

    md = "\n".join(lines)
    (HERE / "A4_SHADOW.md").write_text(md, encoding="utf-8")
    (HERE / "A4_SHADOW.json").write_text(
        json.dumps({"binding": False, "runs": records}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    print(md)
    print("-" * 60)
    print(f"Wrote {HERE / 'A4_SHADOW.md'} and {HERE / 'A4_SHADOW.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
