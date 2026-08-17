#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S13 -- post-run classification worksheet generator (MECHANICAL; no verdict).

Run AFTER s13/run.py completes. It collects every session's verbatim
final_response, pre_tool_observation, skill use, investigation targets and
auto-extracted suggestions into one reviewable document
(s13/results/classification_worksheet.md), grouped by desk, with the oracle's
frozen classification_ground_truth per desk printed as the reference panel.

It does NOT classify. Classification is the human verdict against the frozen
7-category rubric (oracle.rubric.categories) + the 5 rules
(oracle.structure_shared.rulebook_rules_for_classification). The worksheet
leaves a blank `category:` + `grounded_in:` slot under each auto-extracted
suggestion for the human to fill; the human may also surface suggestions the
auto-extractor missed by reading final_response directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ORACLE = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
DESKS = tuple(ORACLE["desks"].keys())
RUBRIC = ORACLE["rubric"]["categories"]
RULES = ORACLE["structure_shared"]["rulebook_rules_for_classification"]
GT = ORACLE["classification_ground_truth"]
N = ORACLE["run"]["replicates_per_desk"]


def _load_sessions() -> dict:
    by_desk = {d: [] for d in DESKS}
    for desk in DESKS:
        for r in range(1, N + 1):
            p = RESULTS / desk / f"{r:02d}" / "run.json"
            if not p.is_file():
                continue
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                by_desk[desk].append({"replicate": r, "_load_error": str(e)})
                continue
            if s.get("failed"):
                by_desk[desk].append({"replicate": r, "_failed": s.get("error", "?")})
                continue
            by_desk[desk].append(s)
    return by_desk


def _rubric_block() -> str:
    lines = ["## The 7-category rubric (frozen; classify each suggestion into ONE)\n"]
    for c in RUBRIC:
        lines.append(f"- **{c['id']}** -- {c['label']}: {c['meaning']}")
    lines.append("\n## The 5 Rulebook rules (applied post-hoc; supervisor did NOT see them)\n")
    for r in RULES:
        lines.append(f"- **{r['id']}** ({r['area']}): {r['summary']}")
    return "\n".join(lines) + "\n"


def _gt_block(desk: str) -> str:
    g = GT.get(desk, {})
    lines = [f"### classification ground truth (reference panel; NOT shown to supervisor)\n"]
    for k in ("genuinely_worth_attention", "healthy_noise", "structural_established",
              "duplicate_if_suggested", "interesting_new_if_suggested",
              "noise_chasing_test", "hardest_test"):
        if k in g:
            v = g[k]
            if isinstance(v, list):
                lines.append(f"- **{k}**:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"- **{k}**: {v}")
    return "\n".join(lines) + "\n"


def _session_block(s: dict) -> str:
    if "_load_error" in s:
        return f"#### rep {s['replicate']:02d} -- LOAD ERROR: {s['_load_error']}\n"
    if "_failed" in s:
        return f"#### rep {s['replicate']:02d} -- FAILED: {s['_failed']}\n"
    rep = s.get("replicate", "?")
    lines = [f"#### rep {rep:02d}  (stop={s.get('stop_reason')}, "
             f"calls={s.get('python_call_count')}, turns={s.get('turn_count')}, "
             f"hand_rolled={s.get('hand_rolled_calls')}, "
             f"budget_events={s.get('budget_events_count')})\n"]
    pre = s.get("pre_tool_observation") or ""
    lines.append(f"**pre_tool_observation** (what it noticed bare-handed, before any tool):\n")
    lines.append(f"```\n{pre.strip() or '(empty -- it used a tool immediately)'}\n```\n")
    sk = s.get("skill_invocations") or []
    if sk:
        lines.append("**skill_invocations**:")
        for x in sk:
            lines.append(f"  - turn {x.get('turn')}: `{x.get('skill')}({x.get('args')})` ok={x.get('ok')}")
    else:
        lines.append("**skill_invocations**: none")
    lines.append(f"**investigation_targets**: {s.get('investigation_targets') or 'none'}\n")
    dr = s.get("drafted_improvements") or []
    if dr:
        lines.append("**drafted_improvements** (via draft_improvement skill):")
        for d in dr:
            lines.append(f"  - `{d.get('id')}`: {d.get('text')}")
    sg = s.get("suggestions") or []
    lines.append("\n**auto-extracted suggestions** (non-authoritative; fill category + grounded_in; "
                 "also scan final_response for suggestions the extractor missed):\n")
    if not sg:
        lines.append("  - (extractor found none; read final_response yourself)\n")
    for i, x in enumerate(sg, 1):
        lines.append(f"  - S{i}: {x.get('text','')}")
        lines.append(f"    - category: ______  grounded_in: ______\n")
    op = s.get("operator_recs") or []
    if op:
        lines.append("**operator_recs** (operator-facing; classify as requires_human if not a system proposal):")
        for x in op:
            lines.append(f"  - {x.get('text','')}")
    lines.append("\n**final_response (VERBATIM)**:\n")
    lines.append(f"```\n{(s.get('final_response') or '(none)').strip()}\n```\n")
    return "\n".join(lines)


def main(argv: list) -> int:
    by_desk = _load_sessions()
    out = ["# S13 -- classification worksheet\n"]
    out.append("MECHANICAL aggregation of the 24 sessions. The human classifies each "
               "suggestion against the frozen rubric + 5 rules, and judges the "
               "investigation-quality axes (noise_chasing, story_combination) per desk. "
               "The verdict goes in FINDINGS.md.\n")
    out.append(_rubric_block())
    out.append("\n---\n")
    for desk in DESKS:
        sess = by_desk.get(desk, [])
        n_ok = sum(1 for s in sess if "_load_error" not in s and "_failed" not in s)
        out.append(f"\n## desk: {desk}  ({n_ok}/{N} sessions loaded)\n")
        out.append(f"_{ORACLE['desks'][desk]['summary']}_\n")
        out.append(f"**facts_worth_attention (frozen)**: {ORACLE['desks'][desk]['facts_worth_attention']}\n")
        out.append(_gt_block(desk))
        out.append("\n### sessions\n")
        for s in sorted(sess, key=lambda x: x.get("replicate", 0)):
            out.append(_session_block(s))
    text = "\n".join(out)
    (RESULTS / "classification_worksheet.md").write_text(text, encoding="utf-8")
    print(f"wrote {RESULTS / 'classification_worksheet.md'}  ({len(text)} chars)")
    # also a compact json index of what was found, for FINDINGS cross-reference
    idx = {}
    for desk in DESKS:
        idx[desk] = []
        for s in by_desk[desk]:
            if "_failed" in s or "_load_error" in s:
                idx[desk].append({"replicate": s.get("replicate"), "status": "failed"})
                continue
            idx[desk].append({
                "replicate": s.get("replicate"), "stop": s.get("stop_reason"),
                "calls": s.get("python_call_count"),
                "hand_rolled": s.get("hand_rolled_calls"),
                "skills_used": sorted({x["skill"] for x in (s.get("skill_invocations") or [])}),
                "n_auto_suggestions": len(s.get("suggestions") or []),
                "n_drafted": len(s.get("drafted_improvements") or []),
                "investigation_targets": s.get("investigation_targets"),
            })
    (RESULTS / "classification_index.json").write_text(
        json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {RESULTS / 'classification_index.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))