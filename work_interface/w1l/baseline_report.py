#!/usr/bin/env python3
"""W1-L PRIMARY MEASURES — repeatability fingerprints across identical runs.

No treatment. Twelve runs of one configuration. This reports **how much the
worker moves when nothing is changed**.

Two independent fingerprints per run:

```text
1  PRESERVATION   rows 0-5 as EXACT | BUNDLED | NONVERBATIM | ABSENT
                  plus preserved_prefix_length, number_exact,
                  number_individually_preserved
2  TOKENIZATION   EXACT | SINGLE_FIELD_PAD | SYSTEMATIC_PAD |
                  UNSPLIT_HEADER | COLLAPSED | OTHER
                  with the offending declared tokens preserved verbatim, so
                  OTHER never becomes an opaque bucket
```

Both are **descriptors**. Neither assumes a mechanism, and neither is a pass
rate.

Every denominator is derived from `manifest.json`. The run set is
authoritative: this reporter never globs `runs/`, so a stray directory cannot
change a denominator. Backlog B-2.

    python work_interface/w1l/baseline_report.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WI = HERE.parent
sys.path.insert(0, str(WI / "harness"))
sys.path.insert(0, str(WI / "fidelity"))
sys.path.insert(0, str(WI / "w1b" / "harness"))
sys.path.insert(0, str(WI))
import pack_manifest as PM  # noqa: E402
import fidelity_check as F  # noqa: E402
import block_harness as B  # noqa: E402
import work_definition as wd  # noqa: E402

MANIFEST = PM.load(HERE)

EXACT, BUNDLED, NONVERBATIM, ABSENT = ("EXACT", "BUNDLED", "NONVERBATIM",
                                       "ABSENT")
TOK_EXACT = "EXACT"
TOK_SINGLE = "SINGLE_FIELD_PAD"
TOK_SYSTEMATIC = "SYSTEMATIC_PAD"
TOK_UNSPLIT = "UNSPLIT_HEADER"
TOK_COLLAPSED = "COLLAPSED"
TOK_OTHER = "OTHER"

ROW_LABEL = {0: "match key", 1: "compare", 2: "currency",
             3: "source of truth", 4: "report fields", 5: "context fields"}


# ---------------------------------------------------------------- primary 1 --

def preservation(art: dict, canon: dict[int, str]) -> dict:
    res = F.check_artifact(art, canon)
    confs = res["confirmations"]
    rows: dict[int, str] = {}
    for row in sorted(canon):
        carriers = [(cid, v) for cid, v in confs.items()
                    if row in (v.get("rows") or [])]
        if not carriers:
            rows[row] = ABSENT
        elif any(len(v.get("rows") or []) > 1 for _, v in carriers):
            rows[row] = BUNDLED
        elif carriers[0][1].get("verdict") != "normal" \
                or carriers[0][1].get("subreason"):
            rows[row] = NONVERBATIM
        else:
            rows[row] = EXACT

    order = MANIFEST.block_order
    prefix = 0
    for row in order:
        if rows.get(row) == EXACT:
            prefix += 1
        else:
            break
    return {
        "rows": rows,
        "preserved_prefix_length": prefix,
        "number_exact": sum(1 for v in rows.values() if v == EXACT),
        # individually attributable = carried by a confirmation that carries
        # ONLY that row, whether or not it is byte-exact
        "number_individually_preserved": sum(
            1 for v in rows.values() if v in (EXACT, NONVERBATIM)),
        "fingerprint": "".join({EXACT: "E", BUNDLED: "B", NONVERBATIM: "N",
                                ABSENT: "-"}[rows[r]] for r in sorted(rows)),
    }


# ---------------------------------------------------------------- primary 2 --

def classify_source(declared: list[str], canon: list[str]) -> dict:
    """One source's observed_fields against its fixture header."""
    offenders: list[dict] = []
    if declared == canon:
        return {"class": TOK_EXACT, "offenders": []}

    # the whole header line kept as ONE token (W1-K A1/B3)
    unsplit = [d for d in declared if d.count(",") >= 2]
    if unsplit:
        return {"class": TOK_UNSPLIT,
                "offenders": [{"declared": d, "why": "contains the delimiter; "
                               "the header line was never split"}
                              for d in unsplit]}

    padded, collapsed, other = [], [], []
    for d in declared:
        if d in canon:
            continue
        if d.strip() in canon and d.strip() != d:
            padded.append(d)
        elif any("".join(c.split()) == "".join(d.split()) and c != d
                 for c in canon):
            collapsed.append(d)
        else:
            other.append(d)

    if collapsed:
        offenders = [{"declared": d, "why": "internal whitespace altered"}
                     for d in collapsed]
        return {"class": TOK_COLLAPSED, "offenders": offenders}
    if other:
        offenders = [{"declared": d, "why": "not derivable from the header"}
                     for d in other]
        return {"class": TOK_OTHER, "offenders": offenders}
    if padded:
        offenders = [{"declared": d, "why": "delimiter-adjacent whitespace "
                      "retained"} for d in padded]
        return {"class": TOK_SINGLE if len(padded) == 1 else TOK_SYSTEMATIC,
                "offenders": offenders}
    return {"class": TOK_OTHER,
            "offenders": [{"declared": str(declared),
                           "why": "declared set differs from the header in an "
                                  "unclassified way"}]}


# severity order, so a run's fingerprint is the worst thing it did
TOK_RANK = {TOK_EXACT: 0, TOK_SINGLE: 1, TOK_SYSTEMATIC: 2,
            TOK_COLLAPSED: 3, TOK_UNSPLIT: 4, TOK_OTHER: 5}


def tokenization(art: dict) -> dict:
    canon_by_role = {role: wd._fixture_headers(MANIFEST.fixture_path(role))
                     for role in MANIFEST.fixture_roles}
    all_canon = sorted({c for v in canon_by_role.values() for c in (v or [])})
    sources = art.get("sources")
    if not isinstance(sources, dict):
        return {"class": TOK_OTHER, "per_source": {},
                "offenders": [{"declared": "<no sources>", "why": "absent"}]}

    per_source, offenders = {}, []
    for role, spec in sources.items():
        if not isinstance(spec, dict):
            continue
        declared = spec.get("observed_fields")
        if not isinstance(declared, list):
            continue
        declared = [str(x) for x in declared]
        fixture = str(spec.get("fixture") or "")
        target = None
        for r, name in MANIFEST.fixture_roles.items():
            if fixture and Path(name).name == Path(fixture).name:
                target = canon_by_role[r]
        got = classify_source(declared, target if target else all_canon)
        per_source[role] = {"class": got["class"], "declared": declared,
                            "offenders": got["offenders"]}
        offenders.extend(got["offenders"])

    worst = TOK_EXACT
    for v in per_source.values():
        if TOK_RANK[v["class"]] > TOK_RANK[worst]:
            worst = v["class"]
    return {"class": worst, "per_source": per_source, "offenders": offenders}


# ---------------------------------------------------------------------------

def main() -> int:
    problems = MANIFEST.verify()
    tbl = B.load_table_rows(MANIFEST.answers_path)
    canon = {i: tbl[i][1] for i in MANIFEST.block_order}
    runs = MANIFEST.runs
    D = MANIFEST.denominators()

    records = []
    for run in runs:
        d = HERE / "runs" / run
        rec: dict = {"run": run}
        art_path = d / MANIFEST.artifact
        hres = d / "harness_result.json"
        rec["harness"] = (json.loads(hres.read_text(encoding="utf-8"))
                          if hres.is_file() else None)
        if not art_path.is_file():
            rec["status"] = "NO_ARTIFACT"
            records.append(rec)
            continue
        try:
            art = json.loads(art_path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            rec["status"] = "UNPARSEABLE_JSON"
            rec["error"] = f"{type(e).__name__}: {e}"
            records.append(rec)
            continue
        rec["status"] = "GRADED"
        rec["preservation"] = preservation(art, canon)
        rec["tokenization"] = tokenization(art)
        records.append(rec)

    graded = [r for r in records if r["status"] == "GRADED"]
    n = len(runs)

    L = ["# W1-L baseline results", "",
         "Generated by `work_interface/w1l/baseline_report.py`. Read-only.", "",
         "**No treatment.** Twelve runs of one fixed configuration. Every "
         "denominator below is derived from `manifest.json`; the run set is "
         "authoritative and is never globbed.", "",
         "```text",
         f"runs declared     {n}   ({runs[0]}..{runs[-1]})",
         f"resources         {D['resources']}",
         f"rows per run      {D['rows']}",
         f"artifacts graded  {len(graded)}/{n}",
         "```", ""]
    if problems:
        L += ["> **manifest problems**", ""] + [f"> - {p}" for p in problems] + [""]
    if MANIFEST.undeclared_run_dirs():
        L += ["> **undeclared run directories present:** "
              + str(MANIFEST.undeclared_run_dirs()), ""]

    # provider configuration
    provs = {json.dumps((r["harness"] or {}).get("provider", {})
                        .get("fingerprint"), sort_keys=True)
             for r in records if r["harness"]}
    L += ["## Provider configuration", ""]
    first = next((r["harness"]["provider"] for r in records
                  if r["harness"] and r["harness"].get("provider")), None)
    if first:
        L += ["```text",
              f"model        {first.get('model')}",
              f"parameters   {first.get('parameters')}",
              f"fingerprint  {first.get('fingerprint', '')[:32]}",
              "```", "",
              f"**Identical across all runs: "
              f"{'YES' if len(provs) == 1 else 'NO -- ' + str(len(provs)) + ' distinct'}**",
              "",
              "Recorded from the declared provider configuration, not from "
              "intercepted traffic: a tee would sit in the worker's request "
              "path and would itself change the configuration this pack "
              "reproduces. Observation only -- nothing was tuned.", ""]
    else:
        L += ["_not captured (no runs yet)_", ""]

    # -- primary 1 ----------------------------------------------------------
    L += ["## PRIMARY 1 — preservation fingerprint", "",
          "| run | " + " | ".join(f"row {r}" for r in sorted(canon))
          + " | fingerprint | prefix | exact | individual |",
          "|---|" + "---|" * (len(canon) + 4)]
    for rec in records:
        if rec["status"] != "GRADED":
            L.append(f"| {rec['run']} | " + " | ".join(["-"] * len(canon))
                     + f" | {rec['status']} | - | - | - |")
            continue
        p = rec["preservation"]
        L.append(f"| {rec['run']} | "
                 + " | ".join(p["rows"][r] for r in sorted(canon))
                 + f" | `{p['fingerprint']}` | {p['preserved_prefix_length']}"
                 f" | {p['number_exact']} | "
                 f"{p['number_individually_preserved']} |")
    L.append("")
    if graded:
        fps = Counter(r["preservation"]["fingerprint"] for r in graded)
        L += ["### distinct preservation fingerprints", "", "```text"]
        for fp, c in fps.most_common():
            L.append(f"{fp}   x{c}")
        L += [f"", f"{len(fps)} distinct fingerprint(s) across "
              f"{len(graded)} graded run(s)", "```", "",
              "```text",
              "per-row EXACT counts, denominator = graded runs",
              ""]
        for r in sorted(canon):
            e = sum(1 for g in graded if g["preservation"]["rows"][r] == EXACT)
            L.append(f"row {r} ({ROW_LABEL[r]:16s}) EXACT {e}/{len(graded)}")
        L += ["```", ""]

    # -- primary 2 ----------------------------------------------------------
    L += ["## PRIMARY 2 — tokenization fingerprint", "",
          "| run | class | offending declared tokens |", "|---|---|---|"]
    for rec in records:
        if rec["status"] != "GRADED":
            L.append(f"| {rec['run']} | {rec['status']} | - |")
            continue
        t = rec["tokenization"]
        offs = "; ".join(repr(o["declared"])[:44] for o in t["offenders"][:3])
        L.append(f"| {rec['run']} | **{t['class']}** | "
                 + (offs if offs else "—") + " |")
    L.append("")
    if graded:
        tc = Counter(r["tokenization"]["class"] for r in graded)
        L += ["### distinct tokenization classes", "", "```text"]
        for k, c in tc.most_common():
            L.append(f"{k:18s} x{c}")
        L += [f"", f"{len(tc)} distinct class(es) across {len(graded)} graded "
              f"run(s)", "```", "",
              "Offending tokens are preserved verbatim per run in "
              "`BASELINE.json`, so `OTHER` is never an opaque bucket.", ""]

    # -- secondary ----------------------------------------------------------
    L += ["## Secondary layers", "", "```text"]
    def cnt(fn):
        return sum(1 for r in records if r["harness"] and fn(r["harness"]))
    with_h = [r for r in records if r["harness"]]
    markers = MANIFEST.consumption_markers()
    L += [f"RESOURCE DISCOVERY    "
          f"{cnt(lambda h: len({e['rawInput']['resource_id'] for e in h.get('permission_log', []) if 'resource_id' in (e.get('rawInput') or {})}) > 0)}"
          f"/{n} runs invoked the reader",
          f"RESOURCE CONSUMPTION  see the matrix below "
          f"(runs x resources, {n} x {D['resources']})",
          f"ARTIFACT PRODUCTION   {cnt(lambda h: h.get('artifact'))}/{n} runs",
          f"AUTHORITY             reported by authority_report.py",
          f"STRUCTURAL            reported by grade.py",
          f"FIDELITY              reported by fidelity_gate.py",
          "```", ""]
    if with_h:
        L += ["### RESOURCE CONSUMPTION — runs x resources", "",
              "| resource | " + " | ".join(r["run"] for r in with_h) + " | total |",
              "|---|" + "---|" * (len(with_h) + 1)]
        for rid in ["skill"] + list(MANIFEST.fixture_roles):
            cells, tot = [], 0
            for r in with_h:
                ids = {e["rawInput"]["resource_id"]
                       for e in r["harness"].get("permission_log", [])
                       if "resource_id" in (e.get("rawInput") or {})
                       and e["verdict"] == "ALLOW"}
                ok = rid in ids
                tot += ok
                cells.append("YES" if ok else "NO")
            L.append(f"| {rid} | " + " | ".join(cells)
                     + f" | {tot}/{len(with_h)} |")
        L += ["",
              f"Denominators are derived: {len(with_h)} run(s) x "
              f"{D['resources']} resource(s) = "
              f"{len(with_h) * D['resources']} observations.", ""]

    L += ["**Descriptive.** N=12 characterises THIS frozen setup only. No "
          "model reliability percentage and no population claim follows from "
          "it.", ""]

    (HERE / "BASELINE.md").write_text("\n".join(L), encoding="utf-8")
    (HERE / "BASELINE.json").write_text(
        json.dumps({"manifest_problems": problems,
                    "denominators": D,
                    "runs": [{k: v for k, v in r.items() if k != "harness"}
                             for r in records]},
                   indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
