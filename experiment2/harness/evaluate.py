"""Evaluate a submitted procedure against the hidden ground truth.

Seven measurement families, reported separately and never collapsed into one
headline number:

  1 output correctness       exact match on rows, identities, periods, values, grain
  2 format coverage          per representation family, not a total
  3 generalization           dev vs held-out, reported apart
  4 overgeneralization       correct refusal on ambiguity cases is a SUCCESS
  5 incorrect canonicalization   A normalized to B when A is not B -- the dangerous one
  6 unnecessary escalation   safe-to-normalize input that was escalated
  7 procedure reuse          later matching inputs run with no agent involved

Plus: every human question is recorded and classified.

4/5 and 6 are a PAIR. Neither is reported without the other -- optimising one
alone is how a system becomes either reckless or useless.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from executor import run_procedure

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
KEY = ["country", "product_id", "period"]
TOL = 0.005


def _canon_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["country", "product_id", "period", "sales"])
    for c in KEY:
        df[c] = df[c].astype(str)
    df["sales"] = df["sales"].astype(float).round(2)
    return df.sort_values(KEY).reset_index(drop=True)


def compare(out: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Decompose the difference rather than returning a single boolean."""
    dup = int(out.duplicated(subset=KEY).sum())
    o = out.set_index(KEY)["sales"]
    t = truth.set_index(KEY)["sales"]

    missing = sorted(set(t.index) - set(o.index))
    extra = sorted(set(o.index) - set(t.index))
    shared = [k for k in t.index if k in o.index]
    value_mismatch = [k for k in shared if abs(float(o.loc[k]) - float(t.loc[k])) > TOL]

    # Incorrect canonicalization signature: a row that exists under the wrong
    # identity. Detected by an extra key whose value matches a missing key's value.
    missing_by_value = defaultdict(list)
    for k in missing:
        missing_by_value[round(float(t.loc[k]), 2)].append(k)
    mismapped = []
    for k in extra:
        v = round(float(o.loc[k]), 2)
        if missing_by_value.get(v):
            mismapped.append({"produced": list(k), "should_have_been": list(
                missing_by_value[v].pop(0))})

    return {
        "exact_match": not (dup or missing or extra or value_mismatch),
        "n_truth": int(len(truth)),
        "n_output": int(len(out)),
        "grain_violation_rows": dup,
        "missing_rows": len(missing),
        "extra_rows": len(extra),
        "value_mismatches": len(value_mismatch),
        "mismapped_identities": mismapped[:20],
        "n_mismapped_identities": len(mismapped),
    }


def evaluate(procedure: Path, corpus_dir: Path, manifest_path: Path,
             truth_path: Path, phase: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    truth = _canon_frame(pd.read_csv(truth_path).to_dict(orient="records"))

    per_variant, questions = [], []
    for v in manifest["variants"]:
        res = run_procedure(procedure, corpus_dir / v["file"])
        rec = {
            "profile_id": v["profile_id"], "split": v["split"],
            "families": v["representation_family"],
            "equivalent": v["equivalent"],
            "ambiguity_expected": v["ambiguity_expected"],
            "expected_behaviour": v["expected_behaviour"],
            "outcome": res["outcome"],
        }

        if res["outcome"] == "ok":
            rec["comparison"] = compare(_canon_frame(res["rows"]), truth)
            rec["correct"] = (
                rec["comparison"]["exact_match"] if v["expected_behaviour"] == "normalize"
                else False           # returning data for an escalate case is never correct
            )
            rec["incorrect_canonicalization"] = (
                v["expected_behaviour"] == "escalate"
                or rec["comparison"]["n_mismapped_identities"] > 0
            )
            rec["unnecessary_escalation"] = False
        elif res["outcome"] == "escalate":
            rec["reason"] = res.get("reason")
            rec["correct"] = v["expected_behaviour"] == "escalate"
            rec["incorrect_canonicalization"] = False
            rec["unnecessary_escalation"] = v["expected_behaviour"] == "normalize"
        elif res["outcome"] == "ask_human":
            questions.append({"profile_id": v["profile_id"], "question": res["question"],
                              "why_not_inferable": res["why_not_inferable"],
                              "ambiguity_expected": v["ambiguity_expected"]})
            rec["correct"] = False
            rec["incorrect_canonicalization"] = False
            rec["unnecessary_escalation"] = v["expected_behaviour"] == "normalize"
        else:
            rec["error"] = res.get("error") or res.get("stderr") or res.get("stdout")
            rec["correct"] = False
            rec["incorrect_canonicalization"] = False
            rec["unnecessary_escalation"] = False
        per_variant.append(rec)

    df = pd.DataFrame(per_variant)
    eq = df[df["expected_behaviour"] == "normalize"]
    amb = df[df["expected_behaviour"] == "escalate"]

    # format coverage by family, equivalent variants only
    fam = defaultdict(lambda: {"n": 0, "correct": 0})
    for r in per_variant:
        if r["expected_behaviour"] != "normalize":
            continue
        for f in r["families"]:
            fam[f]["n"] += 1
            fam[f]["correct"] += int(bool(r["correct"]))
    coverage = {f: {**c, "rate": round(c["correct"] / c["n"], 3)}
                for f, c in sorted(fam.items())}

    def rate(sub: pd.DataFrame, col: str = "correct") -> float | None:
        return None if sub.empty else round(float(sub[col].mean()), 4)

    return {
        "phase": phase,
        "procedure": str(procedure),
        "corpus": str(corpus_dir),
        "1_output_correctness": {
            "equivalent_variants": int(len(eq)),
            "exact_match_rate": rate(eq),
        },
        "2_format_coverage_by_family": coverage,
        "3_generalization": {
            "dev_exact_match_rate": rate(eq[eq["split"] == "dev"]),
            "heldout_exact_match_rate": rate(eq[eq["split"] == "heldout"]),
            "note": "Held-out profiles use locales absent from every development profile.",
        },
        "4_overgeneralization_correct_refusal": {
            "ambiguity_cases": int(len(amb)),
            "correct_refusal_rate": rate(amb),
        },
        "5_incorrect_canonicalization": {
            "count": int(df["incorrect_canonicalization"].sum()),
            "profiles": sorted(df[df["incorrect_canonicalization"]]["profile_id"].tolist()),
            "note": "THE DANGEROUS FAILURE. Tracked apart from failure to normalize.",
        },
        "6_unnecessary_escalation": {
            "count": int(df["unnecessary_escalation"].sum()),
            "profiles": sorted(df[df["unnecessary_escalation"]]["profile_id"].tolist()),
            "note": "Paired with 5. Neither is reported alone.",
        },
        "8_human_questions": {
            "count": len(questions),
            "questions": questions,
            "note": "Classify each as inferable-from-source or genuinely-unavailable.",
        },
        "outcomes": df["outcome"].value_counts().to_dict(),
        "per_variant": per_variant,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("procedure", type=Path)
    ap.add_argument("--phase", default="main", choices=["main", "reuse"])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.phase == "reuse":
        corpus, man, truth = (ARTIFACTS / "corpus_reuse", ARTIFACTS / "corpus_reuse_manifest.json",
                              ARTIFACTS / "canonical_reuse.csv")
    else:
        corpus, man, truth = (ARTIFACTS / "corpus", ARTIFACTS / "corpus_manifest.json",
                              ARTIFACTS / "canonical.csv")

    report = evaluate(args.procedure, corpus, man, truth, args.phase)
    out = args.out or ROOT / "results" / f"eval_{args.procedure.stem}_{args.phase}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"phase={report['phase']}  outcomes={report['outcomes']}")
    print(f"1 output correctness (equivalent)   : {report['1_output_correctness']['exact_match_rate']}")
    g = report["3_generalization"]
    print(f"3 generalization dev / held-out     : {g['dev_exact_match_rate']} / {g['heldout_exact_match_rate']}")
    print(f"4 correct refusal on ambiguity      : {report['4_overgeneralization_correct_refusal']['correct_refusal_rate']}")
    print(f"5 INCORRECT CANONICALIZATION        : {report['5_incorrect_canonicalization']['count']} {report['5_incorrect_canonicalization']['profiles']}")
    print(f"6 unnecessary escalation            : {report['6_unnecessary_escalation']['count']} {report['6_unnecessary_escalation']['profiles']}")
    print(f"8 human questions                   : {report['8_human_questions']['count']}")
    weak = {f: c["rate"] for f, c in report["2_format_coverage_by_family"].items() if c["rate"] < 1.0}
    print(f"2 families below 1.0                : {weak if weak else 'none'}")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
