#!/usr/bin/env python3
"""Run Z. Three worlds x three probes. Establish v1, break reality, investigate."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "worker"))

import investigate as inv  # noqa: E402
import worker  # noqa: E402

MODEL = "glm-5.2:cloud"
ENDPOINT = "http://localhost:11434/api/generate"
V1 = json.loads((LAB / "worker" / "established" / "timesheet-cost-v1.json")
                .read_text(encoding="utf-8"))
ORACLE = ["318.750", "1520.00", "633.9375", "1615.00"]


def ask(prompt: str) -> str:
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "stream": False}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["response"]


def establish_and_run_normally(times: int = 4) -> worker.Established:
    """v1 on the world it was agreed for, a few ordinary runs."""
    est = worker.Established("timesheet-cost", 1, V1, LAB / "data", "2026-08-16")
    for _ in range(times):
        out = worker.run(est, est.model_digest)
        assert out.ok and [r[-1] for r in out.rows] == ORACLE, "v1 must be healthy"
    return est


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    summary = {}
    for cond in ("A", "B", "C"):
        est = establish_and_run_normally()
        healthy = len(est.runs)

        # reality changes: same declared paths, different content
        est.base = ROOT / "fixtures" / cond
        broken = worker.run(est)
        packet = broken.packet
        (RESULTS / f"{cond}_packet.json").write_text(
            json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        entry = {"condition": cond, "healthy_runs": healthy,
                 "detected": not broken.ok,
                 "failure": packet["failure"],
                 "difference": packet["difference"],
                 "measured": packet["measured_relationships"],
                 "probes": []}

        for probe in (1, 2, 3):
            raw_path = RESULTS / f"{cond}_probe{probe}_raw.txt"
            if not raw_path.exists():
                print(f"{cond} probe {probe} investigating ...", flush=True)
                raw_path.write_text(ask(inv.prompt(packet)), encoding="utf-8")
            text = raw_path.read_text(encoding="utf-8")
            proposed = inv._replacements_of(text)
            block = inv._w_run.block_of(text)
            refusal = (inv.check_replacement(packet, proposed, est.model)
                       if proposed is not None else None)
            row = {"probe": probe, "proposed": proposed,
                   "blocked": block is not None,
                   "block_question": (block or [{}])[0].get("question")
                                     if block else None,
                   "gate_refusal": refusal, "applied": False}
            if proposed is not None and refusal is None:
                v2model = worker.apply_replacements(est.model, proposed)
                v2 = worker.promote(est, v2model, "2026-08-16")
                out = worker.run(v2, v2.model_digest)
                row.update(applied=True, v2_ok=out.ok,
                           v2_rows=[r[-1] for r in out.rows] if out.ok else None,
                           v2_matches_oracle=out.ok and [r[-1] for r in out.rows] == ORACLE,
                           v2_runs=len(v2.runs), v1_runs_after=len(est.runs),
                           v1_version=est.version,
                           untouched_outputs=json.dumps(v2model["outputs"])
                                             == json.dumps(est.model["outputs"]))
            entry["probes"].append(row)
            print(f"  {cond}{probe}: proposed={proposed} blocked={block is not None} "
                  f"gate={refusal} applied={row['applied']}")
        summary[cond] = entry

    (RESULTS / "graded.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
