#!/usr/bin/env python3
"""Fidelity / traceability checker -- slice 1.

Implements exactly the two operations preregistered in PREREGISTRATION.md:

  1. deterministic attribution   which frozen canonical row(s) a confirmation
                                 derives from
  2. exclusive classification    each confirmation gets exactly one verdict

No semantic matching, no LLM, no synonyms. Every test is string equality or
declared-span containment against frozen bytes. Read-only: this module never
writes to an artifact.

    python work_interface/fidelity/fidelity_check.py --run F1
    python work_interface/fidelity/fidelity_check.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK_INTERFACE = HERE.parent
sys.path.insert(0, str(WORK_INTERFACE / "w1b" / "harness"))
import block_harness as B  # noqa: E402  (table reader + MANDATED_ROWS only)

W1B_RUNS = WORK_INTERFACE / "w1b" / "runs"

# --- classifications -------------------------------------------------------
NORMAL = "normal"
FID_1 = "FID-1 UNCITED_HUMAN_FACT"
FID_2 = "FID-2 BUNDLED_CONFIRMATION"
FID_3 = "FID-3 PHANTOM_CONFIRMATION"
FID_4 = "FID-4 CONTRADICTED_DECISION"
FID_5 = "FID-5 UNRECORDED_HUMAN_ANSWER"
FID_6 = "FID-6 NONVERBATIM_CONFIRMATION"

# --- slot bindings (PREREGISTRATION.md §4) ---------------------------------
FID1_SLOTS = {0: "body.match_on", 1: "body.compare[Amount]"}
FID5_ROWS = (4, 5)          # delivered rows whose v0 decisions have no provenance slot
ROW3_NO_SLOT = 3            # participates in attribution, out of slot-level FID-1


# ===========================================================================
# Operation 1 -- deterministic attribution
# ===========================================================================

_TERMINAL = ".!?"


def normalize(s: str) -> str:
    """ATTRIBUTION ONLY. Never used to judge byte-exactness."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    while s and s[-1] in _TERMINAL:
        s = s[:-1].rstrip()
    return s


@dataclass
class Attribution:
    rows: list[int] = field(default_factory=list)
    partial: bool = False
    ambiguous: bool = False


def attribute(answer: str, canon: dict[int, str]) -> Attribution:
    """Return the canonical rows a confirmation answer derives from.

    Complete attribution runs longest-normalized-canonical first; a claimed span
    cannot be re-claimed by a nested shorter canonical. Partial (strict-prefix)
    attribution is attempted ONLY when no complete row attached, and only when
    exactly one canonical is matched.
    """
    na = normalize(answer)
    claimed: list[tuple[int, int]] = []
    rows: list[int] = []

    order = sorted(canon, key=lambda i: len(normalize(canon[i])), reverse=True)
    for row in order:
        nc = normalize(canon[row])
        if not nc:
            continue
        start = 0
        while True:
            idx = na.find(nc, start)
            if idx < 0:
                break
            end = idx + len(nc)
            if any(idx < ce and cs < end for cs, ce in claimed):
                start = idx + 1          # overlaps a claimed span; look further on
                continue
            claimed.append((idx, end))
            rows.append(row)
            break

    if rows:
        return Attribution(rows=sorted(rows))

    # --- partial: strict prefix of exactly one canonical --------------------
    if na:
        prefixes = [r for r in canon
                    if normalize(canon[r]).startswith(na) and normalize(canon[r]) != na]
        if len(prefixes) == 1:
            return Attribution(rows=[prefixes[0]], partial=True)
        if len(prefixes) > 1:
            return Attribution(ambiguous=True)
    return Attribution()


# ===========================================================================
# Operation 2 -- exclusive classification
# ===========================================================================

def subreason(answer: str, canonical: str, partial: bool) -> str:
    a, c = answer or "", canonical or ""
    if c.startswith(a) and a != c:
        return "TRUNCATED_PREFIX"
    if a.startswith(c) and a != c:
        return "TRAILING_CONTENT"
    if c in a:
        return "EMBEDDED"
    return "ALTERED"


def classify(answer: str, canon: dict[int, str]) -> dict:
    att = attribute(answer, canon)
    if len(att.rows) == 0:
        return {"verdict": FID_3, "rows": [], "subreason": None,
                "ambiguous": att.ambiguous}
    if len(att.rows) >= 2:
        return {"verdict": FID_2, "rows": att.rows, "subreason": None,
                "ambiguous": False}
    row = att.rows[0]
    if answer == canon[row]:
        return {"verdict": NORMAL, "rows": [row], "subreason": None,
                "ambiguous": False}
    return {"verdict": FID_6, "rows": [row],
            "subreason": subreason(answer, canon[row], att.partial),
            "ambiguous": False}


# ===========================================================================
# Artifact-level findings
# ===========================================================================

def check_artifact(artifact: dict, canon: dict[int, str]) -> dict:
    confs = {}
    for c in artifact.get("human_confirmations") or []:
        if isinstance(c, dict) and c.get("id"):
            confs[c["id"]] = classify(c.get("answer") or "", canon)

    findings: list[dict] = []

    # --- FID-1: slots that HAVE provenance machinery -----------------------
    body = artifact.get("body") or {}
    slots = {0: body.get("match_on") or {}}
    for c in body.get("compare") or []:
        if isinstance(c, dict) and c.get("field") == "Amount":
            slots[1] = c
    for row, where in FID1_SLOTS.items():
        slot = slots.get(row)
        if slot is None:
            continue
        basis, ref = slot.get("basis"), slot.get("confirmation")
        if basis != "human_confirmed":
            findings.append({"finding": FID_1, "where": where, "row": row,
                             "detail": f"basis={basis!r}, not 'human_confirmed'"})
            continue
        v = confs.get(ref)
        if v is None:
            findings.append({"finding": FID_1, "where": where, "row": row,
                             "detail": f"confirmation {ref!r} resolves to no record"})
        elif v["verdict"] != NORMAL or v["rows"] != [row]:
            findings.append({"finding": FID_1, "where": where, "row": row,
                             "detail": f"confirmation {ref!r} is {v['verdict']} "
                                       f"rows={v['rows']}; provenance must be "
                                       f"exclusive and byte-exact"})

    # --- FID-5: delivered rows with no provenance slot ---------------------
    attributed_anywhere = {r for v in confs.values() for r in v["rows"]}
    for row in FID5_ROWS:
        if row not in attributed_anywhere:
            findings.append({"finding": FID_5, "where": "human_confirmations",
                             "row": row,
                             "detail": "delivered canonical recorded nowhere"})

    # --- FID-4: row 2 negative assertion -----------------------------------
    compared = {c.get("field") for c in (body.get("compare") or [])
                if isinstance(c, dict)}
    if "Currency" in compared:
        findings.append({"finding": FID_4, "where": "body.compare", "row": 2,
                         "detail": "Currency compared, contradicting the delivered "
                                   "answer that it is not part of the rule"})

    # --- confirmation-level findings --------------------------------------
    for cid, v in confs.items():
        if v["verdict"] in (FID_2, FID_3, FID_6):
            findings.append({"finding": v["verdict"],
                             "where": f"human_confirmations[{cid}]",
                             "row": None, "detail":
                             f"rows={v['rows']}" +
                             (f" subreason={v['subreason']}" if v["subreason"] else "")})

    return {"confirmations": confs, "findings": findings}


def canonical_rows() -> dict[int, str]:
    rows = B.load_table_rows()
    return {i: rows[i][1] for i in B.MANDATED_ROWS}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fidelity slice 1 checker")
    ap.add_argument("--run", choices=["F1", "F2", "F3"])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    canon = canonical_rows()
    runs = ["F1", "F2", "F3"] if args.all or not args.run else [args.run]
    for r in runs:
        art = json.loads((W1B_RUNS / r / "work_definition.json").read_text(encoding="utf-8"))
        res = check_artifact(art, canon)
        print(f"\n=== {r} ===")
        for cid, v in res["confirmations"].items():
            sub = f" [{v['subreason']}]" if v["subreason"] else ""
            print(f"  {cid:20s} rows={v['rows']}  {v['verdict']}{sub}")
        for f in res["findings"]:
            print(f"  {f['finding']:32s} {f['where']:28s} {f['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
