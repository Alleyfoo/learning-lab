#!/usr/bin/env python3
"""Run S3: the smallest durable Rulebook and Improvement register.

Flow:
  0. SEED     -- force-seed the rulebook (5 proven rules); clear the register.
  1. T1       -- register D-001 (compatible real discovery). Expect no conflict.
  2. T2       -- register a paraphrase of T1. Expect duplicate_of IMP-001.
  3. T3       -- register confirmation-inheritance. Expect conflict with
                 R-CONFIRM-VERSION.
  4. T4       -- register the explicit-re-confirmation mirror. Expect no conflict.
  5. PERMUTE  -- re-classify T3 and T4 against several rule orderings (empty
                 register, to isolate conflict). Assert the conflict verdict is
                 stable across orderings -- not positional.

Every proposal is recorded (append-only); conflict and duplicate are explicit
metadata, never a rejection. Nothing is implemented. Predictions live in
s3/spec.md; verdicts are preserved in s3/results/verdicts.json.

Usage:
  python s3/run.py            # full run
  python s3/run.py --raw      # also print full model rationales
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "supervisor"))

import core  # noqa: E402
import rulebook as rb  # noqa: E402

RESULTS = HERE / "results"
PROPOSALS = (HERE / "proposals.txt").read_text(encoding="utf-8")
R_CONFIRM = "R-CONFIRM-VERSION"

PREDICTIONS = {
    "T1": "duplicate_of=null, conflicts_with=[] -- a compatible real discovery",
    "T2": "duplicate_of=IMP-001, conflicts_with=[] -- a paraphrase, not a new idea",
    "T3": "conflicts_with includes R-CONFIRM-VERSION -- violates the version-bound rule",
    "T4": "conflicts_with=[] -- respects the version-bound rule (the mirror)",
    "PERMUTE-T3": "R-CONFIRM-VERSION named in EVERY ordering; conflict set stable",
    "PERMUTE-T4": "no conflict in EVERY ordering",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_proposals(text: str) -> dict[str, str]:
    """Parse labelled [TAG] sections from proposals.txt into {tag: body}."""
    out: dict[str, str] = {}
    label: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]") and "-" in s:
            if label:
                out[label] = "\n".join(buf).strip()
            label = s.strip("[]")
            buf = []
        elif label:
            buf.append(line)
    if label:
        out[label] = "\n".join(buf).strip()
    return out


def _perms_around(rules: list[dict], target_id: str) -> list[tuple[str, list[dict]]]:
    """target at each position (others fixed around it) + the full reverse."""
    target = next(r for r in rules if r["id"] == target_id)
    others = [r for r in rules if r["id"] != target_id]
    perms = [(f"{target_id}@pos{p}", others[:p] + [target] + others[p:])
             for p in range(len(rules))]
    perms.append(("full-reverse", list(reversed(rules))))
    return perms


def main(argv: list[str]) -> int:
    raw = "--raw" in argv
    RESULTS.mkdir(parents=True, exist_ok=True)

    print("=== S3 SEED (force-seed rulebook, clear register) ===", flush=True)
    rb.reset_improvements()
    seeded = rb.seed_rules(force=True)
    print(f"  {len(seeded)} rules: {[r['id'] for r in seeded]}")

    props = _parse_proposals(PROPOSALS)
    order = [("T1", "T1-D001"), ("T2", "T2-PARAPHRASE"),
             ("T3", "T3-INHERIT"), ("T4", "T4-RECONFIRM")]

    entries: list[dict] = []
    print("\n=== S3 REGISTER (T1..T4) ===", flush=True)
    for tag, key in order:
        e = rb.register(props[key], source=f"s3:{tag}")
        e["tag"] = tag
        e["prediction"] = PREDICTIONS[tag]
        entries.append(e)
        dup = e["duplicate_of"] or "none"
        conf = ",".join(e["conflicts_with"]) or "none"
        comp = e["compatible"]
        print(f"  {tag} -> {e['id']}  duplicate_of={dup}  "
              f"conflicts_with={conf}  compatible={comp}")
        if e.get("parse_error"):
            print(f"    PARSE ERROR: {e['parse_error']}")
        if raw:
            print(f"    rationale: {e['rationale']}")

    # --- permutation sub-test: conflict selection is not positional ----------
    print("\n=== S3 PERMUTE (conflict must be stable across rule orderings) ===",
          flush=True)
    rules = rb.load_rules()
    perm_results: list[dict] = []
    t3_sets: list[set[str]] = []
    t4_sets: list[set[str]] = []
    for name, perm in _perms_around(rules, R_CONFIRM):
        v3 = rb.classify(props["T3-INHERIT"], rules=perm, improvements=[],
                         options={"temperature": 0.1})
        v4 = rb.classify(props["T4-RECONFIRM"], rules=perm, improvements=[],
                         options={"temperature": 0.1})
        s3 = set(v3.get("conflicts_with", []) or [])
        s4 = set(v4.get("conflicts_with", []) or [])
        t3_sets.append(s3)
        t4_sets.append(s4)
        perm_results.append({"ordering": name,
                             "rule_order": [r["id"] for r in perm],
                             "T3_conflicts": sorted(s3),
                             "T4_conflicts": sorted(s4),
                             "T3_rationale": v3.get("rationale"),
                             "T4_rationale": v4.get("rationale"),
                             "T3_parse_error": v3.get("parse_error"),
                             "T4_parse_error": v4.get("parse_error")})
        print(f"  {name:18s} T3={sorted(s3) or '[]'}  T4={sorted(s4) or '[]'}")

    t3_stable = len(set(frozenset(s) for s in t3_sets)) == 1
    t4_stable = len(set(frozenset(s) for s in t4_sets)) == 1
    t3_names_rule = all(R_CONFIRM in s for s in t3_sets)
    t4_never = all(not s for s in t4_sets)
    print(f"\n  T3 stable across orderings: {t3_stable}  | names {R_CONFIRM} "
          f"in all: {t3_names_rule}")
    print(f"  T4 stable across orderings: {t4_stable}  | never conflicts: {t4_never}")

    out = {"run_id": _stamp(),
           "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "model": core.MODEL, "endpoint": core.ENDPOINT,
           "seeded_rules": [r["id"] for r in seeded],
           "predictions": PREDICTIONS,
           "registrations": entries,
           "permutation": {"target_rule": R_CONFIRM,
                           "results": perm_results,
                           "T3_stable_across_orderings": t3_stable,
                           "T3_names_target_in_all": t3_names_rule,
                           "T4_stable_across_orderings": t4_stable,
                           "T4_never_conflicts": t4_never}}
    (RESULTS / "verdicts.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n  preserved: {RESULTS / 'verdicts.json'}")
    print(f"  register:  {rb.IMPROVEMENTS_FILE}")
    print(f"  rulebook:  {rb.RULEBOOK_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))