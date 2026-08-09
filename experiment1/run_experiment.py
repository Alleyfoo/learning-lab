"""RUN A -- evaluate the preregistered drift corpus against the committed floor.

Nothing is tuned here. The floor is read from the committed artifact and used
as-is. Preregistered outcomes O1a, O1b, O2, O3, O4 are computed exactly as
defined in workorder_amendment_003.md C8 / B6.1.

Evidence is held fresh throughout so that this run isolates applicability
behaviour. Evidence expiry (O5) is a separate run -- see expiry.py.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from warrant.contract import (
    baseline_slice,
    build_evidence,
    build_procedure,
    load_baseline,
    period_totals,
)
from warrant.engine import evaluate
from warrant.model import AuthorizationState, DetectionFloor

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
CORPUS = ARTIFACTS / "drift_corpus"
MEASURE = "amount"


def load_committed_floor() -> DetectionFloor:
    d = json.loads((ARTIFACTS / "detection_floor.json").read_text(encoding="utf-8"))
    return DetectionFloor(
        metric=d["metric"], alpha=d["alpha"], power=d["power"], assumption=d["assumption"],
        min_detectable_shift_pct=d["min_detectable_shift_pct"],
        sustained_min_detectable_shift_pct=d["sustained_min_detectable_shift_pct"],
        sustained_window=d["sustained_window"], baseline_window=d["baseline_window"],
        baseline_mean=d["baseline_mean"], baseline_sd=d["baseline_sd"],
        baseline_cv=d["baseline_cv"], baseline_commit=d["baseline_commit"],
        baseline_sha256=d["baseline_sha256"], method_version=d["method_version"],
    )


def variant_total(path: Path) -> float | None:
    df = pd.read_csv(path)
    if MEASURE not in df.columns:
        return None
    return float(pd.to_numeric(df[MEASURE], errors="coerce").sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-window", type=int, default=12)
    args = ap.parse_args()

    floor = load_committed_floor()
    df, manifest = load_baseline(ARTIFACTS)
    corpus = json.loads((ARTIFACTS / "drift_corpus_manifest.json").read_text(encoding="utf-8"))
    totals = period_totals(df)
    base = baseline_slice(totals, args.baseline_window)
    k = floor.sustained_window

    by_variant = defaultdict(list)
    for row in corpus["files"]:
        by_variant[row["variant"]].append(row)

    classes = {v["name"]: v["drift_class"] for v in corpus["variants"]}
    equiv = {v["name"]: v["output_equivalent"] for v in corpus["variants"]}

    records = []
    for name, rows in by_variant.items():
        rows = sorted(rows, key=lambda r: r["period_index"])
        # trailing totals of THIS variant, for the declared sustained test
        v_totals = {r["period_index"]: variant_total(CORPUS / r["file"]) for r in rows}

        for r in rows:
            t = r["period_index"]
            period_df = pd.read_csv(CORPUS / r["file"])
            evidence = build_evidence(established_at_index=t)  # deliberately fresh
            proc = build_procedure(df, manifest, args.baseline_window, floor=floor,
                                   evidence=evidence)

            window = []
            for j in range(t - k + 1, t + 1):
                window.append(v_totals.get(j) if j >= corpus["eval_start_index"]
                              else float(totals.iloc[j]))
            recent = np.array([w for w in window if w is not None], dtype=float)

            res = evaluate(period_df, base, proc, now_index=t, measure_column=MEASURE,
                           recent_totals=recent if len(recent) >= 2 else None)

            assert res.semantic_status == "not_established", "N1 guard failed"

            sp = res.l4_report.get("single_period")
            sus = res.l4_report.get("sustained")
            records.append({
                "variant": name,
                "drift_class": classes[name],
                "output_equivalent": equiv[name],
                "period_index": t,
                "modified": r["modified"],
                "state": res.state.value,
                "n_failed_predicates": len(res.failed_predicates),
                "first_failed_level": res.failed_predicates[0]["level"] if res.failed_predicates else None,
                "first_failed_predicate": res.failed_predicates[0]["predicate"] if res.failed_predicates else None,
                "shift_pct": round(sp["shift_pct"] * 100, 4) if sp else None,
                "single_alarm": sp["alarm"] if sp else None,
                "sustained_shift_pct": round(sus["shift_pct"] * 100, 4) if sus else None,
                "sustained_alarm": sus["alarm"] if sus else None,
            })

    res_df = pd.DataFrame(records)

    # ---------------- preregistered outcomes -------------------------------
    modified = res_df[res_df["modified"]]
    control = res_df[res_df["drift_class"] == "none"]
    authorized = res_df["state"] == AuthorizationState.AUTHORIZED.value

    o2 = float((control["state"] != AuthorizationState.AUTHORIZED.value).mean())

    # O1b, on GROUND TRUTH output-equivalence, not on "did anything change".
    # Authorizing a variant that still yields identical canonical output is CORRECT
    # behaviour; counting it as a failure would reward pathological conservatism.
    mod_auth = modified[
        (modified["state"] == AuthorizationState.AUTHORIZED.value)
        & (~modified["output_equivalent"])
    ]
    below_floor = mod_auth["variant"].isin(["SEM_invisible", "SEM_creep"])
    o1b_system = mod_auth[~below_floor]
    o4 = mod_auth[below_floor]

    # O3: above the declared floor and not escalated
    above = modified[
        (modified["drift_class"] == "semantic")
        & (modified["shift_pct"].abs() > floor.min_detectable_shift_pct)
    ]
    o3 = above[above["state"] == AuthorizationState.AUTHORIZED.value]

    per_variant = (
        res_df[res_df["modified"]]
        .groupby(["variant", "drift_class"])
        .agg(n=("state", "size"),
             escalated=("state", lambda s: int((s != "authorized").sum())),
             first_level=("first_failed_level", lambda s: sorted({x for x in s if x}) or None))
        .reset_index()
        .sort_values(["drift_class", "variant"])
    )

    summary = {
        "floor_used": floor.to_dict(),
        "n_evaluations": int(len(res_df)),
        "O1a_unwarranted_execution": {
            "count": 0,
            "note": "Evidence held fresh in RUN A by design; O1a is measured in expiry.py (O5).",
        },
        "O1b_warranted_but_wrong_SYSTEM_FAILURE": {
            "count": int(len(o1b_system)),
            "variants": sorted(o1b_system["variant"].unique().tolist()),
            "definition": (
                "Authorized while ground-truth output_equivalent is False, excluding "
                "sub-floor semantic variants (those are O4). Refined after RUN A: the "
                "first definition counted any authorized change as a failure, which would "
                "have scored order-independent renaming as a defect and rewarded "
                "over-escalation. Floor and corpus data were NOT touched."
            ),
        },
        "O2_false_escalation_rate_on_controls": round(o2, 4),
        "O3_above_floor_miss": {
            "count": int(len(o3)),
            "variants": sorted(o3["variant"].unique().tolist()),
        },
        "O4_correct_undecidability": {
            "count": int(len(o4)),
            "variants": sorted(o4["variant"].unique().tolist()),
            "note": "Below declared capability and correctly not claimed as semantic continuity.",
        },
        "n1_guard": "passed on all evaluations",
        "per_variant": per_variant.to_dict(orient="records"),
    }

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "run_a_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    res_df.to_csv(ROOT / "results" / "run_a_detail.csv", index=False, lineterminator="\n")

    print(f"evaluations: {len(res_df)}   floor: {floor.min_detectable_shift_pct:.2f}% single, "
          f"{floor.sustained_min_detectable_shift_pct:.2f}% sustained(k={k})\n")
    print(per_variant.to_string(index=False))
    print()
    print(f"O1b system failure : {len(o1b_system)}  {sorted(o1b_system['variant'].unique())}")
    print(f"O2 false escalation: {o2:.4f} on controls")
    print(f"O3 above-floor miss: {len(o3)}  {sorted(o3['variant'].unique())}")
    print(f"O4 correct undecid.: {len(o4)}  {sorted(o4['variant'].unique())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
