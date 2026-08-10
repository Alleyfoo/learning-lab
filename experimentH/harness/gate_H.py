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
row is overridden to ask_human -- the same safety property 3E established, applied
to row-location instead of cell-classification.

Match functions (frozen):

  exact_match(cell, ref)    : cell.strip().lower() == ref.strip().lower()
                             used by deterministic-first (the realistic deterministic
                             path handles casing/spacing trivially; suffixes defeat it)
  tolerant_match(cell, ref): exact, OR cell startswith ref and the next char is a
                             non-letter (suffix-tolerant). Used by the verification
                             gate. Designed for the H2 suffix variation; other
                             variation kinds (abbreviations etc.) would need their own
                             tolerant_match in later H probes.

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


def grade() -> dict:
    """Real grading: read judgements/H.json, run gate per probe, compare to expected."""
    exp = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    judg = json.loads(JUDGE_PATH.read_text(encoding="utf-8"))
    per_probe = {}
    for key, spec in exp["probes"].items():
        fpath = _fixture_path(spec["fixture"])
        llm = judg.get(key)
        out = gate(fpath, llm)
        per_probe[key] = out
    # pass criteria
    h1 = per_probe.get("H1", {})
    h2 = per_probe.get("H2", {})
    h3a = per_probe.get("H3a", {})
    h3b = per_probe.get("H3b", {})
    h1_ok = h1.get("header_row") == exp["probes"]["H1"]["expected_header_row"]
    h2_ok = (h2.get("header_row") == exp["probes"]["H2"]["expected_header_row"]
             and h2.get("source") == "llm_accepted")
    h3a_ok = h3a.get("ask_human") is True
    h3b_ok = h3b.get("ask_human") is True
    h1h2_pass = bool(h1_ok and h2_ok)
    h3_pass = bool(h3a_ok and h3b_ok)
    result = {
        "probe": "H",
        "per_probe": per_probe,
        "h1_ok": h1_ok, "h2_ok": h2_ok, "h3a_ok": h3a_ok, "h3b_ok": h3b_ok,
        "h1h2_pass": h1h2_pass,
        "h3_pass": h3_pass,
        "overall": bool(h1h2_pass and h3_pass),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "H.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    return result


def selftest() -> int:
    """Verify gate logic on the frozen fixtures with mock LLM answers. No real run."""
    print("[H] self-test: gate logic on frozen fixtures (mock LLM answers)")
    cases = [
        # (probe, fixture, mock llm_answer, expected disposition keys)
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
    print(f"[H] self-test {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if JUDGE_PATH.exists():
        r = grade()
        print("[H] graded result:")
        print(json.dumps(r, indent=2, ensure_ascii=False))
        for k in ["H1", "H2", "H3a", "H3b"]:
            print(f"   {k}: {r['per_probe'][k]}")
        print(f"[H] h1h2_pass={r['h1h2_pass']}  h3_pass={r['h3_pass']}  overall={r['overall']}")
        raise SystemExit(0 if r["overall"] else 1)
    raise SystemExit(selftest())