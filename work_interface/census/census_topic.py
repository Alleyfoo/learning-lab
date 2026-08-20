#!/usr/bin/env python3
"""Census pass 2: assign each fragment its SEMANTIC topic and compare with routing.

The topic rules below are AUDIT INSTRUMENTS ONLY. They are not a proposed matcher
and are deliberately broader than the frozen matcher: their job is to say what the
worker was asking about, so routing can be scored against it.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
census = json.loads((HERE / "census.json").read_text(encoding="utf-8"))

# skill-mandated questions (SKILL.md step 5) and their table intents
S = {
    "S1_match_key":      {"intents": [0]},
    "S2_compare":        {"intents": [1]},
    "S3_field_in_rule":  {"intents": [2]},
    "S4_source_of_truth": {"intents": [3]},
    "S5_report_context": {"intents": [4, 5]},
}
WORKER_OWNED = "W_worker_owned"      # left/right, classify labels, output order, purpose
CONTESTED = "X_contested_ownership"  # duplicate-key, non-numeric  (table 6/7 vs closed vocab)
OTHER = "Z_other"


def topic(t: str) -> str:
    s = t.lower()
    if re.search(r"duplicate key|same .{0,20}appears? (multiple|more than)|multiple (ledger )?records|duplicate keys|dupkey|on_duplicate_key", s):
        return CONTESTED
    if re.search(r"non.?numeric|not a number|on_non_numeric|numeric=", s):
        return CONTESTED
    if re.search(r"\bleft\b.*\bright\b|left_then_right|which plays which role|body\.left|output order|output_order|sorted_by_key|classification labels?|classify|label names|purpose", s):
        return WORKER_OWNED
    if re.search(r"source of truth|authoritative|authority model|peer", s):
        return "S4_source_of_truth"
    if re.search(r"report|context_fields|context-only|context only|reports_fields|row names|which are \*\*context", s):
        return "S5_report_context"
    if re.search(r"same record|match key|matching key|identifies? the same|primary key|match on|matching logic|match logic|better candidate|combine fields", s):
        return "S1_match_key"
    if re.search(r"part of the reconciliation rule|incidental|status.*(compar|reconcil)|currency", s):
        return "S3_field_in_rule"
    if re.search(r"compar|toleranc|within|exact", s):
        return "S2_compare"
    if re.search(r"\bcontext\b", s):
        return "S5_report_context"
    return OTHER


rows = []
for c in census:
    if c["kind"] != "fragment":
        continue
    tp = topic(c["text"])
    expected = S.get(tp, {}).get("intents", [])
    got = c["intents"]
    if not got:
        verdict = "MISSED"
    elif expected and set(got) & set(expected):
        verdict = "ROUTED_CORRECT"
    elif tp in (WORKER_OWNED, CONTESTED, OTHER):
        verdict = "MISROUTED_OUT_OF_SCOPE"
    else:
        verdict = "MISROUTED_WRONG_INTENT"
    rows.append({**c, "topic": tp, "verdict": verdict})

(HERE / "census_topic.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                        encoding="utf-8")

from collections import Counter
print("VERDICTS:", dict(Counter(r["verdict"] for r in rows)))
print()
print(f"{'topic':22s} {'asked':>5s} {'routed_ok':>9s} {'missed':>6s} {'misrouted':>9s}  coverage")
for tp in list(S) + [WORKER_OWNED, CONTESTED, OTHER]:
    g = [r for r in rows if r["topic"] == tp]
    ok = sum(1 for r in g if r["verdict"] == "ROUTED_CORRECT")
    ms = sum(1 for r in g if r["verdict"] == "MISSED")
    mr = len(g) - ok - ms
    cov = f"{100*ok/len(g):.0f}%" if g else "-"
    print(f"{tp:22s} {len(g):5d} {ok:9d} {ms:6d} {mr:9d}  {cov}")
print()
print("### MISROUTED (a frozen answer was sent for a DIFFERENT question)")
for r in rows:
    if r["verdict"].startswith("MISROUTED"):
        print(f"  {r['run']}t{r['turn']} topic={r['topic']:22s} sent_intents={r['intents']}  {r['text'][:95]}")
