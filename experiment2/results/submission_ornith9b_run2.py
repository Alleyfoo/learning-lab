from __future__ import annotations

import re
from typing import Optional
from contract import Escalate, AskHuman


_MONTH_NAMES = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

_FINNISH_MONTHS = {
    "tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu",
    "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu",
}

_GERMAN_MONTHS = {
    "januar", "februar", "märz", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "dezember",
}


def _strip(val: str) -> Optional[str]:
    v = val.strip() if val is not None else ""
    return v.strip('"').strip("'") or None


def _parse_sales(raw: str) -> float:
    s = _strip(raw)
    if s is None or s == "":
        raise Escalate("missing sales", {"value": raw})
    # European-style decimal (comma) → period
    numeric = re.sub(r"[^0-9.\-]", "", s)
    return float(numeric)


def _normalize_country(raw: str) -> str:
    c = _strip(raw).upper()
    if not c or len(c) == 2 and c.isalpha():
        return c

    lower = raw.strip().lower()
    # Finnish short names (CZE, DEU style codes already handled above)
    fin_map = {
        "tšekki": "CZ", "tsk": "CZ",
        "saksa": "DE", "dsb": "DE",
        "suomi": "FI", "som": "FI",
        "ruotsi": "SE", "sve": "SE",
    }
    if lower in fin_map:
        return fin_map[lower]

    # Full country names (any language) → ISO code
    full_map = {
        "czechia": "CZ", "tschechien": "CZ", "ceská republika": "CZ",
        "germany": "DE", "deutschland": "DE",
        "finland": "FI",
        "sweden": "SE", "sverige": "SE", "schweden": "SE", "vergien": "SE",
    }
    if lower in full_map:
        return full_map[lower]

    # Fallback to first two uppercase letters (CZE→CZ, DEU→DE)
    if len(c) >= 2 and c[:2].isalpha():
        return c[:2]
    raise Escalate(f"unknown country: {raw!r}", {"value": raw})


def _normalize_period(raw: str) -> Optional[str]:
    r = _strip(raw)
    if not r or r == "":
        raise Escalate("missing period", {"value": raw})

    # YYYY-MM format (e.g. 2026-01, 2026/01)
    m = re.match(r"^(\d{4})([-/])(\d{1,2})$", r)
    if m:
        return f"{m.group(1)}-{int(m.group(3)):02d}"

    # MM/YYYY format (e.g. 01/2026)
    m = re.match(r"^(\d{1,2})([-/])(\d{4})$", r)
    if m:
        return f"{int(m.group(1)):02d}-{m.group(3)}"

    # English month + year in one cell (e.g. January 2026)
    for mn in _MONTH_NAMES:
        pattern = rf"^({re.escape(mn)})\s*(\d{{4}})$"
        if re.match(pattern, r, re.IGNORECASE):
            # Determine month number from name
            months = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
            idx = months.index(mn) + 1
            return f"{idx:02d}-{r.split()[-1]}"

    # German month + year in one cell (e.g. Januar 2026, März 2026)
    for mn in _GERMAN_MONTHS:
        pattern = rf"^({re.escape(mn)})\s*(\d{{4}})$"
        if re.match(pattern, r, re.IGNORECASE):
            german_months = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                              "Juli", "August", "September", "Oktober", "November", "Dezember"]
            idx = german_months.index(mn) + 1
            return f"{idx:02d}-{r.split()[-1]}"

    # Finnish month + year in one cell (e.g. tammikuu 2026)
    for mn in _FINNISH_MONTHS:
        pattern = rf"^({re.escape(mn)})\s*(\d{{4}})$"
        if re.match(pattern, r, re.IGNORECASE):
            fin_months = ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu",
                          "toukokuu", "kesäkuu", "heinäkuu", "elokuu",
                          "syyskuu", "lokakuu", "marraskuu", "joulukuu"]
            idx = fin_months.index(mn) + 1
            return f"{idx:02d}-{r.split()[-1]}"

    raise Escalate(f"unrecognized period: {raw!r}", {"value": raw})


def _detect_period_col(headers):
    """Return index of the column that contains period info, or -1."""
    for i, h in enumerate(headers):
        h = str(h).strip().lower()
        # YYYY-MM / MM/YYYY style
        if re.match(r"^\d{4}[-/]\d{1,2}$", h) or re.match(r"^\d{1,2}[-/]\d{4}$", h):
            return i

    for h in headers:
        hl = str(h).strip().lower()
        # Month name + year combined (e.g. "January 2026")
        if re.search(r"january|february|march|april|may|june|july|august|september|october|november|december", hl, re.IGNORECASE):
            return i
        # German month name + year combined (e.g. "Januar 2026")
        if re.search(r"januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember", hl, re.IGNORECASE):
            return i
        # Finnish month name + year combined (e.g. "tammikuu 2026")
        if re.search(r"tammikuu|helmikuu|maaliskuu|huhtikuu|toukokuu|kesäkuu|heinäkuu|elokuu|syyskuu|lokakuu|marraskuu|joulukuu", hl, re.IGNORECASE):
            return i

    for h in headers:
        if "period" in str(h).lower():
            return h_index_by_content(headers)

    # Check content of each column for YYYY-MM patterns (D01)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if re.match(r"^\d{4}[-/]\d{1,2}$", str(val).strip()):
                return j

    # Check content for MM/YYYY patterns (D04)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            if re.match(r"^\d{1,2}/\d{4}$", str(val).strip()):
                return j

    raise Escalate("could not detect period column", {"headers": headers})


def _detect_sales_col(headers):
    """Return index of the column that contains sales values."""
    for h in headers:
        hl = str(h).strip().lower()
        if "sales" in hl or "umsatz" in hl or "myynti" in hl:
            return h_index_by_content(headers)

    # Heuristic: a column whose header contains only digits is likely sales
    for i, h in enumerate(headers):
        if re.match(r"^\d+$", str(h).strip()):
            return i

    raise Escalate("could not detect sales column", {"headers": headers})


def _detect_product_col(headers):
    """Return index of the column that contains product IDs."""
    for h in headers:
        hl = str(h).strip().lower()
        if "product" in hl or "tuote" in hl:
            return h_index_by_content(headers)

    # Heuristic: a column whose values look like ART-XXXX patterns
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            v = str(val).strip()
            if re.match(r"^ART-\d{4}$", v):
                return j

    raise Escalate("could not detect product column", {"headers": headers})


def _detect_country_col(headers):
    """Return index of the column that contains country names."""
    for h in headers:
        hl = str(h).strip().lower()
        if "country" in hl or "maa" in hl or "land" in hl or "landes" in hl:
            return h_index_by_content(headers)

    # Heuristic: a column whose values are known country names
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            v = str(val).strip()
            if _normalize_country(v) == v.upper():  # already normalized → likely country
                return j

    raise Escalate("could not detect country column", {"headers": headers})


def normalize(source_path: str) -> "pandas.DataFrame":
    import pandas as pd

    df = pd.read_csv(source_path, dtype=str, keep_default_na=False)
    rows = [tuple(str(c) for c in r) for r in df.values.tolist()]
    headers = list(df.columns)

    country_idx = _detect_country_col(headers)
    product_idx = _detect_product_col(headers)
    period_idx = _detect_period_col(headers, rows)
    sales_idx = _detect_sales_col(headers)

    out = []
    for row in rows:
        c = _normalize_country(row[country_idx])
        p = row[product_idx].strip()
        per = _normalize_period(row[period_idx])
        s = _parse_sales(row[sales_idx])
        out.append((c, p, per, f"{s:.2f}"))

    return pd.DataFrame(out, columns=["country", "product_id", "period", "sales"])
