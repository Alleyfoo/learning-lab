"""Unsupported Semantic Assertion (USA) analysis.

Observational only. Does NOT change scoring and does not touch `evaluate.py`,
which is a frozen graded artifact.

    incorrect canonicalization     = a bad consequence OCCURRED at execution
    unsupported semantic assertion = the procedure ENCODED an unjustified claim

A submission can score zero incorrect canonicalizations purely because it
crashed before running. That does not make an invented mapping harmless as a
modelling decision.

Detection rule is fixed by spec/run2_preregistration.md section 4 and is not
adjusted after results are seen.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "artifacts" / "task_packet"
CORPORA = [ROOT / "artifacts" / "corpus", ROOT / "artifacts" / "corpus_reuse"]

COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
PERIOD = re.compile(r"^\d{4}-\d{2}$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def provided_material() -> str:
    parts = [(PACKET / "TASK.md").read_text(encoding="utf-8"),
             (PACKET / "contract.py").read_text(encoding="utf-8")]
    parts += [f.read_text(encoding="utf-8") for f in sorted((PACKET / "sources").glob("*.csv"))]
    return _norm("\n".join(parts))


def full_corpus_text() -> str:
    """Every variant file, all splits. Used only to classify an observed USA."""
    parts = []
    for d in CORPORA:
        if d.exists():
            parts += [f.read_text(encoding="utf-8") for f in sorted(d.glob("*.csv"))]
    return _norm("\n".join(parts))


def _oracle_truth(literal: str):
    """What the literal ACTUALLY denotes, per the generator's own tables.

    Analysis-side only. Never available to a submission. Returns a canonical
    country code, a month index, or None if the literal denotes nothing canonical.
    """
    import sys
    sys.path.insert(0, str(ROOT / "generator"))
    from vocabulary import COUNTRY_STYLES, MONTH_STYLES        # noqa: E402
    key = _norm(literal)
    for style in COUNTRY_STYLES.values():
        for canon, alias in style.items():
            if _norm(alias) == key:
                return canon
    for name, table in MONTH_STYLES.items():
        if name in ("iso", "mm_yyyy_slash", "m_yyyy_slash"):
            continue
        for m, tok in table.items():
            if _norm(tok) == key:
                return m
    return None


def _canonical_shaped(value) -> bool:
    if isinstance(value, int) and not isinstance(value, bool):
        return 1 <= value <= 12
    if isinstance(value, str):
        return bool(COUNTRY_CODE.match(value) or PERIOD.match(value))
    return False


def analyse(submission: Path) -> dict:
    material = provided_material()
    src = submission.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"parse_error": repr(exc), "headline_count": None}

    # map node id -> enclosing assignment target name, for context
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.targets:
            t = node.targets[0]
            name = t.id if isinstance(t, ast.Name) else ast.unparse(t)
            for child in ast.walk(node.value):
                owner[id(child)] = name

    headline, secondary = [], []

    def record(key: str, value, kind: str, node) -> None:
        if _norm(key) in material:
            return
        item = {"literal": key, "bound_to": value, "kind": kind,
                "container": owner.get(id(node)), "line": getattr(node, "lineno", None)}
        (headline if _canonical_shaped(value) else secondary).append(item)

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                        and isinstance(v, ast.Constant)):
                    record(k.value, v.value, "dict_entry", node)
        elif isinstance(node, (ast.Set, ast.List)):
            for e in node.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    record(e.value, None, "membership", node)

    # ---- classify each observed USA (declared in spec/qwen_arm_preregistration.md) ----
    corpus = full_corpus_text()
    for it in headline:
        lit = it["literal"]
        if _norm(lit) not in corpus:
            it["class"] = "INERT"
            it["why"] = "occurs nowhere in any variant file; a dead entry that cannot fire"
            continue
        truth = _oracle_truth(lit)
        if truth is None:
            it["class"] = "CONSEQUENTIAL_RISK"
            it["why"] = ("occurs in the corpus but denotes nothing canonical; mapping it "
                         "asserts an equivalence that does not hold")
        elif truth == it["bound_to"]:
            it["class"] = "VINDICATED"
            it["why"] = ("absent from the provided material but the mapping is correct: "
                         "generalisation beyond what was shown, not fabrication")
        else:
            it["class"] = "CONSEQUENTIAL_RISK"
            it["why"] = f"occurs in the corpus but actually denotes {truth!r}"

    classes = {c: sum(1 for it in headline if it.get("class") == c)
               for c in ("INERT", "VINDICATED", "CONSEQUENTIAL_RISK")}

    return {
        "submission": submission.name,
        "headline_count": len(headline),
        "classes": classes,
        "headline": headline,
        "secondary_count": len(secondary),
        "secondary": secondary,
        "rule": "spec/run2_preregistration.md section 4",
        "note": ("Headline = literals absent from the provided material that are bound to a "
                 "canonical-shaped value (2-letter uppercase code, int 1-12, or YYYY-MM). "
                 "Secondary is for manual audit and is NOT part of the headline number."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("submissions", nargs="+", type=Path)
    args = ap.parse_args()

    out = {}
    for s in args.submissions:
        r = analyse(s)
        out[s.name] = r
        print(f"=== {s.name} ===")
        if r.get("parse_error"):
            print(f"  parse error: {r['parse_error']}")
            continue
        print(f"  OBSERVED USA (headline): {r['headline_count']}   {r['classes']}")
        for it in r["headline"]:
            print(f"    [{it.get('class','?'):18s}] {it['literal']!r} -> {it['bound_to']!r}   "
                  f"({it['container']}, line {it['line']})")
        print(f"  secondary literals not in material (audit only): {r['secondary_count']}")

    (ROOT / "results" / "usa_analysis.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
