"""Locale vocabulary used to RENDER source variants.

This is generator-side only. It is never exposed to the modelling agent, and the
agent is never told that lookup tables are a viable strategy -- discovering that
(or anything else that works) is the experiment.

Written fresh. See BUILD_NOTES.md: Data-tool's `_normalize_month` was inspected
and declined -- it covers fi/en fully but sv/de only partially and has no cs/fr/es,
and half-copying a partial table would muddy provenance for no real saving.
"""

from __future__ import annotations

CANONICAL_COUNTRIES = ["FI", "CZ", "SE", "DE"]

# ---------------------------------------------------------------- months
# index 1..12 -> token, per style. Only months 1..6 are exercised by the
# canonical dataset, but full tables are kept so held-out periods stay possible.

MONTH_STYLES: dict[str, dict[int, str]] = {
    "iso": {m: f"{{year}}-{m:02d}" for m in range(1, 13)},
    "mm_yyyy_slash": {m: f"{m:02d}/{{year}}" for m in range(1, 13)},
    "m_yyyy_slash": {m: f"{m}/{{year}}" for m in range(1, 13)},
    "mm": {m: f"{m:02d}" for m in range(1, 13)},
    "m": {m: str(m) for m in range(1, 13)},
    "en_full": dict(enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"], 1)),
    "en_abbr": dict(enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)),
    "en_abbr_upper": dict(enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)),
    "fi_full": dict(enumerate(
        ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu",
         "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"], 1)),
    "fi_abbr": dict(enumerate(
        ["tammi", "helmi", "maalis", "huhti", "touko", "kesä",
         "heinä", "elo", "syys", "loka", "marras", "joulu"], 1)),
    "de_full": dict(enumerate(
        ["Januar", "Februar", "März", "April", "Mai", "Juni",
         "Juli", "August", "September", "Oktober", "November", "Dezember"], 1)),
    # ---- held-out locales: absent from every development profile ----
    "sv_full": dict(enumerate(
        ["januari", "februari", "mars", "april", "maj", "juni",
         "juli", "augusti", "september", "oktober", "november", "december"], 1)),
    "cs_full": dict(enumerate(
        ["leden", "únor", "březen", "duben", "květen", "červen",
         "červenec", "srpen", "září", "říjen", "listopad", "prosinec"], 1)),
    "fr_full": dict(enumerate(
        ["janvier", "février", "mars", "avril", "mai", "juin",
         "juillet", "août", "septembre", "octobre", "novembre", "décembre"], 1)),
    "es_full": dict(enumerate(
        ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], 1)),
}

# Styles that carry no year and therefore require a separate year column.
MONTH_STYLES_NEEDING_YEAR = {
    "mm", "m", "en_full", "en_abbr", "en_abbr_upper",
    "fi_full", "fi_abbr", "de_full", "sv_full", "cs_full", "fr_full", "es_full",
}

# Styles rendered as "<month> <year>" in one cell.
MONTH_WITH_YEAR_SUFFIX = {
    "en_full_year": "en_full", "en_abbr_year": "en_abbr",
    "fi_full_year": "fi_full", "fi_abbr_year": "fi_abbr",
    "de_full_year": "de_full", "sv_full_year": "sv_full",
    "cs_full_year": "cs_full", "fr_full_year": "fr_full",
    "es_full_year": "es_full",
}

# ------------------------------------------------------------- countries

COUNTRY_STYLES: dict[str, dict[str, str]] = {
    "iso2": {"FI": "FI", "CZ": "CZ", "SE": "SE", "DE": "DE"},
    "iso3": {"FI": "FIN", "CZ": "CZE", "SE": "SWE", "DE": "DEU"},
    "en": {"FI": "Finland", "CZ": "Czechia", "SE": "Sweden", "DE": "Germany"},
    "en_alt": {"FI": "Finland", "CZ": "Czech Republic", "SE": "Sweden", "DE": "Germany"},
    "endonym": {"FI": "Suomi", "CZ": "Česko", "SE": "Sverige", "DE": "Deutschland"},
    "endonym_formal": {"FI": "Suomi", "CZ": "Česká republika",
                       "SE": "Sverige", "DE": "Deutschland"},
    "fi_exonym": {"FI": "Suomi", "CZ": "Tšekki", "SE": "Ruotsi", "DE": "Saksa"},
    "de_exonym": {"FI": "Finnland", "CZ": "Tschechien", "SE": "Schweden", "DE": "Deutschland"},
    # ---- held-out ----
    "sv_exonym": {"FI": "Finland", "CZ": "Tjeckien", "SE": "Sverige", "DE": "Tyskland"},
    "fr_exonym": {"FI": "Finlande", "CZ": "Tchéquie", "SE": "Suède", "DE": "Allemagne"},
}

# --------------------------------------------------------------- headers

HEADER_STYLES: dict[str, dict[str, str]] = {
    "en": {"country": "country", "product": "product", "period": "period",
           "month": "month", "year": "year", "sales": "sales"},
    "fi": {"country": "maa", "product": "tuote", "period": "kausi",
           "month": "kuukausi", "year": "vuosi", "sales": "myynti"},
    "de": {"country": "Land", "product": "Produkt", "period": "Periode",
           "month": "Monat", "year": "Jahr", "sales": "Umsatz"},
    # ---- held-out ----
    "sv": {"country": "land", "product": "produkt", "period": "period",
           "month": "månad", "year": "år", "sales": "försäljning"},
    "fr": {"country": "pays", "product": "produit", "period": "période",
           "month": "mois", "year": "année", "sales": "ventes"},
    "es": {"country": "país", "product": "producto", "period": "periodo",
           "month": "mes", "year": "año", "sales": "ventas"},
    "cs": {"country": "země", "product": "produkt", "period": "období",
           "month": "měsíc", "year": "rok", "sales": "tržby"},
}

# --------------------------------------------------------------- numbers

NBSP = " "


def format_number(value: float, style: str) -> str:
    whole = f"{value:,.2f}"                      # 1,234.50
    if style == "plain":
        return f"{value:.2f}"
    if style == "us":
        return whole
    if style == "eu_space":
        return whole.replace(",", " ").replace(".", ",")
    if style == "eu_nbsp":
        return whole.replace(",", NBSP).replace(".", ",")
    if style == "eu_dot":
        return whole.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if style == "ch":
        return whole.replace(",", "'")
    if style == "int_plain":
        return f"{value:.0f}"
    raise ValueError(f"unknown number style: {style}")


NUMBER_STYLES = ["plain", "us", "eu_space", "eu_nbsp", "eu_dot", "ch", "int_plain"]

# Styles that DESTROY information and therefore may never be used on an
# `equivalent=True` variant. `int_plain` rounds away the decimals, so a variant
# rendered with it is not semantically equivalent to the canonical data and no
# procedure could recover it. Enforced by the round-trip guard in render.py.
LOSSY_NUMBER_STYLES = {"int_plain"}


def parse_number(text: str, style: str) -> float:
    """Exact inverse of `format_number`, used only by the corpus round-trip guard."""
    s = text.replace(NBSP, "").replace(" ", "").replace("'", "")
    if style in ("eu_space", "eu_nbsp", "eu_dot"):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def month_token(month: int, year: int, style: str) -> str:
    if style in MONTH_WITH_YEAR_SUFFIX:
        base = MONTH_STYLES[MONTH_WITH_YEAR_SUFFIX[style]][month]
        return f"{base} {year}"
    tok = MONTH_STYLES[style][month]
    return tok.format(year=year) if "{year}" in tok else tok


ALL_MONTH_STYLES = list(MONTH_STYLES) + list(MONTH_WITH_YEAR_SUFFIX)
