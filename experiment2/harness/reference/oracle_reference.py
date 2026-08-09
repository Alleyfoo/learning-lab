"""ORACLE-ASSISTED REFERENCE PROCEDURE — EVALUATOR VALIDATION ONLY.

**This is not a candidate solution and must never enter the task packet.**

It exists to answer one narrow question: can the harness recognise a correct
procedure when it sees one, and correctly refuse the ambiguity cases? Without it,
a score of zero would be indistinguishable between "the task is hard" and "the
evaluator is broken".

It cheats deliberately: it imports the generator's own vocabulary tables. A real
submission has no such access, and nothing here tells an agent that lookup tables
are the intended strategy — they are one strategy, used here because it is the
shortest obviously-correct one for validating a scorer.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "generator"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract import Escalate                      # noqa: E402
from vocabulary import COUNTRY_STYLES, MONTH_STYLES, MONTH_WITH_YEAR_SUFFIX  # noqa: E402

NBSP_CHARS = "   "
PRODUCT_RE = re.compile(r"^ART-\d{4}$")


def _clean(s: object) -> str:
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    for ch in NBSP_CHARS:
        s = s.replace(ch, " ")
    return unicodedata.normalize("NFC", s).strip()


def _fold(s: str) -> str:
    return _clean(s).casefold()


# reverse lookups, built from the generator's own tables
_COUNTRY = {}
for style in COUNTRY_STYLES.values():
    for canon, alias in style.items():
        _COUNTRY[_fold(alias)] = canon

_MONTH: dict[str, int] = {}
for name, table in MONTH_STYLES.items():
    if name in ("iso", "mm_yyyy_slash", "m_yyyy_slash"):
        continue
    for m, tok in table.items():
        _MONTH[_fold(tok)] = m


def _parse_period(token: str, year_hint: int | None) -> str:
    t = _clean(token)
    if re.fullmatch(r"\d{4}-\d{2}", t):
        return t
    parts = t.split("/")
    if len(parts) == 3:
        a, b = int(parts[0]), int(parts[1])
        if a <= 12 and b <= 12:
            raise Escalate("day/month order is not recoverable from this file",
                           {"example": t})
        raise Escalate("unexpected three-part date", {"example": t})
    if len(parts) == 2:
        m, y = int(parts[0]), int(parts[1])
        return f"{y:04d}-{m:02d}"
    words = t.split()
    if len(words) == 2 and re.fullmatch(r"\d{4}", words[1]):
        m = _MONTH.get(_fold(words[0]))
        if m:
            return f"{int(words[1]):04d}-{m:02d}"
    if re.fullmatch(r"\d{1,2}", t):
        if year_hint is None:
            raise Escalate("bare month number with no year available", {"example": t})
        return f"{year_hint:04d}-{int(t):02d}"
    m = _MONTH.get(_fold(t))
    if m:
        if year_hint is None:
            raise Escalate("bare month name with no year available", {"example": t})
        return f"{year_hint:04d}-{m:02d}"
    raise Escalate("unrecognised period token", {"example": t})


def _looks_periodish(token: str) -> bool:
    t = _clean(token)
    if re.fullmatch(r"\d{4}-\d{2}|\d{1,2}/\d{4}|\d{1,2}", t):
        return True
    words = t.split()
    if len(words) == 2 and re.fullmatch(r"\d{4}", words[1]):
        return _fold(words[0]) in _MONTH
    return _fold(t) in _MONTH


def _number_convention(values: list[str]) -> str:
    """Decide a column's numeric convention, or refuse if the evidence is short."""
    vals = [_clean(v).replace(" ", "").replace("'", "") for v in values if _clean(v)]
    if not vals:
        raise Escalate("no numeric values present")
    if any("." in v and "," in v for v in vals):
        sample = next(v for v in vals if "." in v and "," in v)
        return "dot_decimal" if sample.rfind(".") > sample.rfind(",") else "comma_decimal"
    single = [v for v in vals if v.count(",") == 1 and "." not in v]
    if single:
        if any(v.count(",") > 1 for v in vals):
            return "dot_decimal"
        tails = {len(v.split(",")[1]) for v in single}
        if tails == {3}:
            raise Escalate(
                "a single comma with exactly three following digits, and nothing "
                "anywhere in the file resolves whether it is a thousands separator "
                "or a decimal mark",
                {"example": single[0]})
        return "comma_decimal"
    return "dot_decimal"


def _to_float(v: str, conv: str) -> float:
    s = _clean(v).replace(" ", "").replace("'", "")
    if conv == "comma_decimal":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def _sniff_sep(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        head = fh.readline()
    return ";" if head.count(";") > head.count(",") else ","


def normalize(source_path: str) -> pd.DataFrame:
    sep = _sniff_sep(source_path)
    raw = pd.read_csv(source_path, sep=sep, dtype=str, keep_default_na=False)
    raw.columns = [_clean(c) for c in raw.columns]
    for c in raw.columns:
        raw[c] = raw[c].map(_clean)

    def _frac(col, pred):
        vals = [v for v in raw[col] if v]
        return sum(pred(v) for v in vals) / len(vals) if vals else 0.0

    def _numericish(v):
        return bool(re.fullmatch(r"[\d.,'\s  ]+", v))

    # A column is the year if every value is a plausible 4-digit year.
    year_col = next((c for c in raw.columns if _frac(c, lambda v: bool(
        re.fullmatch(r"\d{4}", v)) and 1990 <= int(v) <= 2100) == 1.0), None)

    # Wide iff SEVERAL HEADERS are period-like.
    header_month_cols = [c for c in raw.columns
                         if c != year_col and _looks_periodish(c)]

    if len(header_month_cols) > 1:
        idx = [c for c in raw.columns if c not in header_month_cols]
        df = raw.melt(id_vars=idx, value_vars=header_month_cols,
                      var_name="_tok", value_name="_val")
        df = df[df["_val"].astype(str).str.strip() != ""].reset_index(drop=True)
        period_src, value_src = "_tok", "_val"
    else:
        df = raw.copy()
        # Otherwise a column whose VALUES are period-like carries the period.
        period_src = max(
            (c for c in raw.columns if c != year_col),
            key=lambda c: _frac(c, _looks_periodish), default=None)
        if period_src is None or _frac(period_src, _looks_periodish) < 0.9:
            raise Escalate("no period-bearing column identified")
        candidates = [c for c in raw.columns if c not in (period_src, year_col)]
        value_src = max(candidates, key=lambda c: _frac(c, _numericish), default=None)
        if value_src is None or _frac(value_src, _numericish) < 0.9:
            raise Escalate("no numeric measure column identified")

    id_cols = [c for c in df.columns
               if c not in (period_src, value_src, year_col, "_tok", "_val")]

    country_col = next(
        (c for c in id_cols
         if sum(_fold(v) in _COUNTRY for v in df[c] if v) > 0.5 * max(1, (df[c] != "").sum())),
        None,
    )
    if country_col is None:
        unknown = sorted({v for c in id_cols for v in df[c] if v})[:5]
        raise Escalate("no column resolves to established country identities",
                       {"unmatched_examples": unknown})

    bad_country = sorted({v for v in df[country_col] if v and _fold(v) not in _COUNTRY})
    if bad_country:
        raise Escalate("country-like values whose equivalence is not established",
                       {"unresolved": bad_country[:5]})

    product_col = next((c for c in id_cols if c != country_col), None)
    if product_col is None:
        raise Escalate("no product identifier column identified")
    bad_product = sorted({v for v in df[product_col]
                          if v and not PRODUCT_RE.fullmatch(_clean(v).upper())})
    if bad_product:
        raise Escalate("product identifiers are malformed or inconsistent",
                       {"unresolved": bad_product[:5]})

    year_hint = None
    if year_col is not None:
        years = {int(v) for v in df[year_col] if v}
        year_hint = years.pop() if len(years) == 1 else None

    conv = _number_convention(list(df[value_src]))

    out = pd.DataFrame({
        "country": [_COUNTRY[_fold(v)] for v in df[country_col]],
        "product_id": [_clean(v).upper() for v in df[product_col]],
        "period": [_parse_period(v, year_hint) for v in df[period_src]],
        "sales": [round(_to_float(v, conv), 2) for v in df[value_src]],
    })
    return out.sort_values(["country", "product_id", "period"]).reset_index(drop=True)
