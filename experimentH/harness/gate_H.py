"""Experiment H — deterministic-first + tolerant-coverage gate + grader.

The architecture (frozen):

    supplied reference vocabulary (12 Finnish month names)  -- the "world"
        |
        v
    deterministic-first scan: does any row contain all 12 references exactly
    (case-insensitive, trimmed, full-token)?  --> if yes, that row is the answer;
        the LLM is NOT invoked.  "Boring deterministic code wins" on the clean case.
        |
        v  (no exact 12/12 row)
    invoke the locator LLM: "find the single row covering the reference set,
    allowing harmless formatting variation; else ask_human."
        |
        v
    LLM returns {"header_row": r} or {"ask_human": true}
        |
        v
    DETERMINISTIC VERIFICATION GATE (code, not LLM; authoritative):
        count how many of the 12 references appear in the claimed row r under a
        tolerant match (reference is a prefix of the cell, case-insensitive,
        trimmed, followed by a non-letter or end-of-cell -- i.e. suffix-tolerant).
        coverage == 12  -> accept row r
        coverage < 12   -> ask_human, REGARDLESS of what the LLM said
        (parse failure / ask_human from LLM -> ask_human)

This gate is the 3E comparison-gate transposed: the model claims a result; code
checks a verifiable property (coverage); an unsupported claim cannot acquire
authority. On the H3 interloper case (11/12), a model that confidently picks the
row is overridden to ask_human -- the same safety property 3E established,
applied to row-location instead of cell-classification.

NON-SCORING DIAGNOSTIC -- counterfactual all-row tolerant scan:
    After grading each fixture, apply the frozen tolerant-coverage function to
    EVERY row and record which rows reach 12/12 and whether the accepted row is
    unique. This does NOT affect the H result. It answers a separate question:
    "could a tolerant deterministic locator have found the row without the LLM?"
    If the scan uniquely reaches 12/12 on the accepted row, the LLM was not
    *needed* (only *correct*); the engineering conclusion is to automate the
    provider with the tolerant deterministic locator. The LLM still had to
    *propose* the row for the gate to authorize it, so the run is not wasted --
    it may reveal that the task is already deterministic.

Match functions (frozen):

  exact_match(cell, ref)    : cell.strip().lower() == ref.strip().lower()
                             used by deterministic-first (the realistic deterministic
                             path handles casing/spacing trivially; suffixes defeat it)
  tolerant_match(cell, ref) : exact, OR cell startswith ref and the next char is a
                             non-letter (suffix-tolerant). Used by the verification
                             gate AND the counterfactual scan. Designed for the H2
                             suffix variation; other variation kinds (abbreviations
                             etc.) would need their own tolerant_match in later H
                             probes.

Grading is stage-aware: judgements/H.json holds the probes run so far. H1/H2 are
graded and frozen before H3a/H3b are run. Pass flags for not-yet-run probes are
null; overall is null until all four are graded.

Usage:
    python gate_H.py            # self-test (no judgements needed); real grade if
                                # judgements/H.json is present
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "reference" / "months.json"
EXPECTED_PATH = ROOT / "expected.json"
JUDGE_PATH = ROOT / "judgements" / "H.json"
RESULTS = ROOT / "results"

REF = json.loads(REF_PATH.read_text(encoding="utf-8"))["months"]
N_REF = len(REF)


def _norm(s: str) -> str:
    return s.strip().lower()


def exact_match(cell: str, ref: str) -> bool:
    return _norm(cell) == _norm(ref)


def tolerant_match(cell: str, ref: str) -> bool:
    """Suffix-tolerant prefix match. 'Tammi 2026' matches 'Tammi'; 'Tammixyz' does not."""
    c, r = _norm(cell), _norm(ref)
    if not c.startswith(r):
        return False
    if len(c) == len(r):
        return True  # exact
    return not c[len(r)].isalpha()  # next char must be a boundary (space/digit/end-ish)


def coverage(row_cells: list[str], match_fn) -> int:
    return sum(1 for ref in REF if any(match_fn(cell, ref) for cell in row_cells))


def read_rows(csv_path: Path) -> list[list[str]]:
    with csv_path.open(encoding="utf-8", newline="") as fh:
        return [[c.strip() for c in r] for r in csv.reader(fh)]


def deterministic_first(rows: list[list[str]]) -> int | None:
    """Return 1-indexed row whose exact-match coverage == N_REF, else None."""
    for i, cells in enumerate(rows, start=1):
        if coverage(cells, exact_match) == N_REF:
            return i
    return None


def counterfactual_scan(fixture_path: Path) -> dict:
    """Non-scoring: apply the frozen tolerant-coverage function to EVERY row.

    Records which rows reach 12/12 and whether the max-coverage row is unique.
    Answers: could a tolerant deterministic locator have found the row without
    the LLM? Does not affect the H result.
    """
    rows = read_rows(fixture_path)
    cov_by_row = {i: coverage(cells, tolerant_match)
                  for i, cells in enumerate(rows, start=1)}
    rows_at_12 = [i for i, c in cov_by_row.items() if c == N_REF]
    max_cov = max(cov_by_row.values()) if cov_by_row else 0
    rows_at_max = [i for i, c in cov_by_row.items() if c == max_cov]
    return {
        "rows_reaching_12": rows_at_12,
        "unique_12": len(rows_at_12) == 1,
        "max_coverage": max_cov,
        "rows_at_max": rows_at_max,
        "max_unique": len(rows_at_max) == 1,
        "note": "non-scoring; does not affect the H result",
    }


def gate(fixture_path: Path, llm_answer: dict | None) -> dict:
    """Run the full gate for one fixture given the LLM's recorded answer.

    llm_answer is None when the LLM was not invoked (deterministic-first solved it).
    """
    rows = read_rows(fixture_path)
    det = deterministic_first(rows)
    if det is not None:
        return {
            "header_row": det,
            "source": "deterministic",
            "coverage": N_REF,
            "llm_invoked": False,
        }
    # no exact 12/12 row -> LLM was (or should have been) invoked
    if llm_answer is None:
        # deterministic path did not solve, and no LLM answer recorded
        return {"ask_human": True, "reason": "no_deterministic_no_llm", "llm_invoked": False}
    if llm_answer.get("ask_human") is True:
        return {"ask_human": True, "reason": "llm_asked", "llm_invoked": True}
    r = llm_answer.get("header_row")
    if not isinstance(r, int) or r < 1 or r > len(rows):
        return {"ask_human": True, "reason": "llm_parse_failure", "llm_invoked": True}
    cov = coverage(rows[r - 1], tolerant_match)
    if cov == N_REF:
        return {"header_row": r, "source": "llm_accepted", "coverage": cov, "llm_invoked": True}
    return {
        "ask_human": True,
        "reason": "gate_coverage_short",
        "claimed_row": r,
        "coverage": cov,
        "llm_invoked": True,
    }


def _fixture_path(name_or_rel: str) -> Path:
    """Resolve a fixture reference. Absolute/relative-to-experimentH, or a frozen
    fixture referenced by path (e.g. ../experiment2b/fixtures/A1.csv)."""
    p = Path(name_or_rel)
    if p.is_absolute():
        return p
    cand = ROOT / p
    if cand.exists():
        return cand
    cand2 = ROOT.parent / p  # ../ relative to repo root
    if cand2.exists():
        return cand2
    return cand  # let the caller see the missing-path error


def _llm_answer_of(entry) -> dict | None:
    """judgements entries may be None (not invoked), a dict with an 'llm_answer'
    key (full record), or a bare answer dict ({header_row/ask_human})."""
    if entry is None:
        return None
    if isinstance(entry, dict) and "llm_answer" in entry:
        return entry["llm_answer"]
    return entry  # bare answer dict or None


def grade() -> dict:
    """Stage-aware grading: grade the probes present in judgements/H.json.
    H1/H2 first; H3a/H3b appended and graded later. Adds the non-scoring
    counterfactual tolerant scan per probe."""
    exp = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    judg = json.loads(JUDGE_PATH.read_text(encoding="utf-8"))
    per_probe = {}
    graded = []
    for key, spec in exp["probes"].items():
        if key not in judg:
            continue  # not run at this stage
        fpath = _fixture_path(spec["fixture"])
        llm = _llm_answer_of(judg[key])
        out = gate(fpath, llm)
        out["counterfactual_tolerant_scan"] = counterfactual_scan(fpath)
        per_probe[key] = out
        graded.append(key)

    h1_ok = h2_ok = h3a_ok = h3b_ok = None
    if "H1" in per_probe:
        h1_ok = per_probe["H1"].get("header_row") == exp["probes"]["H1"]["expected_header_row"]
    if "H2" in per_probe:
        h2_ok = (per_probe["H2"].get("header_row") == exp["probes"]["H2"]["expected_header_row"]
                 and per_probe["H2"].get("source") == "llm_accepted")
    if "H3a" in per_probe:
        h3a_ok = per_probe["H3a"].get("ask_human") is True
    if "H3b" in per_probe:
        h3b_ok = per_probe["H3b"].get("ask_human") is True
    h1h2_pass = (h1_ok is True and h2_ok is True) if ("H1" in per_probe and "H2" in per_probe) else None
    h3_pass = (h3a_ok is True and h3b_ok is True) if ("H3a" in per_probe and "H3b" in per_probe) else None
    overall = (h1h2_pass is True and h3_pass is True) if (h1h2_pass is not None and h3_pass is not None) else None

    if set(graded) == {"H1", "H2"}:
        stage = "H1_H2"
    elif set(graded) == {"H1", "H2", "H3a", "H3b"}:
        stage = "full"
    else:
        stage = "partial:" + ",".join(graded)

    result = {
        "probe": "H",
        "stage": stage,
        "graded": graded,
        "per_probe": per_probe,
        "h1_ok": h1_ok, "h2_ok": h2_ok, "h3a_ok": h3a_ok, "h3b_ok": h3b_ok,
        "h1h2_pass": h1h2_pass,
        "h3_pass": h3_pass,
        "overall": overall,
        "pass_criteria": exp["pass_criteria"],
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "H.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    return result


def selftest() -> int:
    """Verify gate logic on the frozen fixtures with mock LLM answers. No real run."""
    print("[H] self-test: gate logic on frozen fixtures (mock LLM answers)")
    cases = [
        ("H1", "fixtures/H1.csv", None,
         {"header_row": 4, "source": "deterministic", "llm_invoked": False}),
        ("H2", "fixtures/H2.csv", {"header_row": 4},
         {"header_row": 4, "source": "llm_accepted", "coverage": 12, "llm_invoked": True}),
        ("H2-wrong-partial", "fixtures/H2.csv", {"header_row": 6},
         {"ask_human": True, "reason": "gate_coverage_short", "claimed_row": 6, "llm_invoked": True}),
        ("H2-asked", "fixtures/H2.csv", {"ask_human": True},
         {"ask_human": True, "reason": "llm_asked", "llm_invoked": True}),
        ("H3a-A1", "../experiment2b/fixtures/A1.csv", {"header_row": 4},
         {"ask_human": True, "reason": "gate_coverage_short", "claimed_row": 4, "llm_invoked": True}),
        ("H3b", "fixtures/H3b.csv", {"header_row": 4},
         {"ask_human": True, "reason": "gate_coverage_short", "claimed_row": 4, "coverage": 11, "llm_invoked": True}),
        ("H3b-asked", "fixtures/H3b.csv", {"ask_human": True},
         {"ask_human": True, "reason": "llm_asked", "llm_invoked": True}),
    ]
    ok = True
    for label, fx, mock, want in cases:
        out = gate(_fixture_path(fx), mock)
        match = all(out.get(k) == v for k, v in want.items())
        ok = ok and match
        print(f"   {label:<16} {fx}")
        print(f"      mock={mock}")
        print(f"      out ={out}")
        print(f"      want={want}  {'OK' if match else 'MISMATCH'}")
    print()
    print("[H] self-test: counterfactual all-row tolerant scan (non-scoring)")
    for label, fx in [("H1", "fixtures/H1.csv"), ("H2", "fixtures/H2.csv"),
                      ("H3a-A1", "../experiment2b/fixtures/A1.csv"),
                      ("H3b", "fixtures/H3b.csv")]:
        cs = counterfactual_scan(_fixture_path(fx))
        print(f"   {label:<8} {fx}  rows_at_12={cs['rows_reaching_12']} "
              f"unique_12={cs['unique_12']} max={cs['max_coverage']} "
              f"rows_at_max={cs['rows_at_max']}")
    print(f"[H] self-test {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if JUDGE_PATH.exists():
        r = grade()
        print(f"[H] stage={r['stage']} graded={r['graded']}")
        for k in r["graded"]:
            p = r["per_probe"][k]
            cs = p["counterfactual_tolerant_scan"]
            print(f"   {k}: {p}")
            print(f"      counterfactual: rows_at_12={cs['rows_reaching_12']} "
                  f"unique_12={cs['unique_12']} max={cs['max_coverage']} rows_at_max={cs['rows_at_max']}")
        print(f"[H] h1h2_pass={r['h1h2_pass']}  h3_pass={r['h3_pass']}  overall={r['overall']}")
        if r["stage"] == "full":
            raise SystemExit(0 if r["overall"] is True else 1)
        if r["stage"] == "H1_H2":
            raise SystemExit(0 if r["h1h2_pass"] is True else 1)
        raise SystemExit(0)  # partial stage: informational
    raise SystemExit(selftest())