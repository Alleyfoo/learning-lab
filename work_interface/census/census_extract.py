#!/usr/bin/env python3
"""W1 phrasing-coverage census -- extraction pass. READ ONLY.

Reconstructs every agent turn from the nine committed transcripts and runs the
CURRENT (w1a5) frozen parser/matcher over all of them uniformly. Writes a JSON
census to the scratchpad. Modifies nothing in the repo.
"""
import json
import re
import sys
from pathlib import Path

LAB = Path(r"C:\Users\pertt\learning-lab")
sys.path.insert(0, str(LAB / "work_interface" / "w1a5" / "harness"))
import acp_harness as H  # noqa: E402

RUNS = [("C1", "w1a3"), ("C2", "w1a3"), ("C3", "w1a3"),
        ("D1", "w1a4"), ("D2", "w1a4"), ("D3", "w1a4"),
        ("E1", "w1a5"), ("E2", "w1a5"), ("E3", "w1a5")]

I = H.load_answer_table()


def agent_turns(path: Path):
    """Split the transcript into agent turns: text accumulated between our
    outgoing session/prompt messages."""
    turns, cur = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        d = m.get("dir")
        msg = m.get("msg") or {}
        if d == "out" and msg.get("method") == "session/prompt":
            if cur:
                turns.append("".join(cur))
                cur = []
            continue
        if d != "in":
            continue
        u = (msg.get("params") or {}).get("update") or {}
        if u.get("sessionUpdate") == "agent_message_chunk":
            cur.append((u.get("content") or {}).get("text", ""))
    if cur:
        turns.append("".join(cur))
    return turns


census = []
for run, pack in RUNS:
    p = LAB / "work_interface" / pack / "runs" / run / "acp_transcript.jsonl"
    if not p.is_file():
        print(f"MISSING {p}", file=sys.stderr)
        continue
    for ti, text in enumerate(agent_turns(p), 1):
        frags = H.segment_fragments(text)
        # lines that look like questions but produced no fragment
        qlines = [l.strip() for l in text.splitlines() if "?" in l]
        covered = set()
        for f in frags:
            for l in qlines:
                if H._norm(f)[:40] and H._norm(f)[:40] in H._norm(l):
                    covered.add(l)
        unrepresentable = [l for l in qlines if l not in covered]
        for f in frags:
            hits = [i.index for i in H.intents_in(f, I)]
            terms = []
            n = H._norm(f)
            for i in I:
                if i.index in hits:
                    for g in i.terms:
                        for a in g:
                            if a in n:
                                terms.append((i.index, a))
            census.append({"run": run, "turn": ti, "kind": "fragment",
                           "text": f, "routed": bool(hits),
                           "intents": hits, "matched_terms": terms})
        for l in unrepresentable:
            census.append({"run": run, "turn": ti, "kind": "unrepresentable",
                           "text": l, "routed": False,
                           "intents": [], "matched_terms": []})
        if not text.strip():
            census.append({"run": run, "turn": ti, "kind": "silent_turn",
                           "text": "", "routed": False,
                           "intents": [], "matched_terms": []})

out = Path(__file__).resolve().parent / "census.json"
out.write_text(json.dumps(census, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"turns/fragments captured: {len(census)} -> {out}")
frag = [c for c in census if c["kind"] == "fragment"]
print(f"  fragments      : {len(frag)}   routed {sum(1 for c in frag if c['routed'])}"
      f"  missed {sum(1 for c in frag if not c['routed'])}")
print(f"  unrepresentable: {sum(1 for c in census if c['kind']=='unrepresentable')}")
print(f"  silent turns   : {sum(1 for c in census if c['kind']=='silent_turn')}")
