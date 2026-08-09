"""Representation profiles.

20 equivalent profiles (12 development + 8 held-out) plus a 5-case
ambiguity/refusal set.

Held-out profiles use locales that appear in NO development profile -- Swedish,
Czech, French, Spanish for months, headers and country names. A procedure that
memorised the development tokens cannot pass them; one that captured a reusable
rule might.

Mixed conventions are deliberate. Several profiles combine, say, English headers
with Finnish month names and German exonyms, so nothing can rely on "one file =
one locale".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    id: str
    split: str                    # dev | heldout | ambiguity
    shape: str                    # wide | long | period_value
    month_style: str
    header_lang: str
    country_style: str
    number_style: str
    cosmetics: tuple[str, ...] = ()
    sep: str = ","
    equivalent: bool = True       # does this file carry the same business information?
    ambiguity_expected: bool = False
    expected_behaviour: str = "normalize"   # normalize | escalate
    families: tuple[str, ...] = ()
    notes: str = ""


DEV: list[Profile] = [
    Profile("D01", "dev", "long", "iso", "en", "iso2", "plain",
            families=("long", "month_iso", "header_en", "country_code", "num_plain")),
    Profile("D02", "dev", "wide", "en_full", "en", "en", "us", ("title_case_values",),
            families=("wide", "month_name_en", "header_en", "country_en", "num_us", "cosmetic")),
    Profile("D03", "dev", "long", "en_abbr", "en", "iso3", "eu_space",
            families=("long", "month_abbr_en", "header_en", "country_code", "num_eu_space")),
    Profile("D04", "dev", "period_value", "mm_yyyy_slash", "fi", "endonym", "eu_dot",
            families=("period_value", "month_numeric", "header_fi", "country_endonym",
                      "num_eu_dot")),
    Profile("D05", "dev", "wide", "mm", "de", "de_exonym", "ch",
            families=("wide", "month_numeric", "header_de", "country_exonym", "num_ch")),
    Profile("D06", "dev", "long", "fi_full_year", "fi", "fi_exonym", "eu_space",
            ("pad_whitespace",),
            families=("long", "month_name_fi", "header_fi", "country_exonym", "num_eu_space",
                      "cosmetic")),
    Profile("D07", "dev", "period_value", "iso", "de", "en_alt", "eu_nbsp",
            families=("period_value", "month_iso", "header_de", "country_en", "num_eu_nbsp",
                      "mixed_conventions"),
            notes="German headers, ISO periods, English country names, NBSP numbers"),
    Profile("D08", "dev", "wide", "en_abbr_upper", "en", "iso2", "plain",
            sep=";",
            families=("wide", "month_abbr_en", "header_en", "country_code", "num_plain",
                      "cosmetic")),
    Profile("D09", "dev", "long", "m_yyyy_slash", "en", "endonym_formal", "us",
            families=("long", "month_numeric", "header_en", "country_endonym", "num_us")),
    Profile("D10", "dev", "long", "de_full_year", "de", "de_exonym", "eu_dot",
            families=("long", "month_name_de", "header_de", "country_exonym", "num_eu_dot")),
    Profile("D11", "dev", "period_value", "m", "fi", "iso3", "plain", ("upper_values",),
            families=("period_value", "month_numeric", "header_fi", "country_code",
                      "num_plain", "cosmetic")),
    Profile("D12", "dev", "wide", "fi_full_year", "en", "de_exonym", "eu_dot",
            families=("wide", "month_name_fi", "header_en", "country_exonym", "num_eu_dot",
                      "mixed_conventions"),
            notes="English headers, Finnish month names, German exonyms, EU-dot numbers"),
]

HELD_OUT: list[Profile] = [
    Profile("H01", "heldout", "long", "sv_full_year", "sv", "sv_exonym", "eu_space",
            families=("long", "month_name_sv", "header_sv", "country_exonym",
                      "num_eu_space")),
    Profile("H02", "heldout", "wide", "cs_full", "cs", "iso2", "eu_dot",
            families=("wide", "month_name_cs", "header_cs", "country_code", "num_eu_dot")),
    Profile("H03", "heldout", "period_value", "fr_full_year", "fr", "fr_exonym", "plain",
            families=("period_value", "month_name_fr", "header_fr", "country_exonym",
                      "num_plain")),
    Profile("H04", "heldout", "long", "es_full_year", "es", "en", "us",
            families=("long", "month_name_es", "header_es", "country_en", "num_us")),
    Profile("H05", "heldout", "wide", "sv_full", "en", "sv_exonym", "ch",
            families=("wide", "month_name_sv", "header_en", "country_exonym", "num_ch",
                      "mixed_conventions"),
            notes="English headers, Swedish months and exonyms"),
    Profile("H06", "heldout", "long", "cs_full_year", "en", "endonym_formal", "eu_nbsp",
            families=("long", "month_name_cs", "header_en", "country_endonym",
                      "num_eu_nbsp", "mixed_conventions")),
    Profile("H07", "heldout", "period_value", "fr_full_year", "en", "fr_exonym", "eu_space",
            ("pad_whitespace", "title_case_values"),
            families=("period_value", "month_name_fr", "header_en", "country_exonym",
                      "num_eu_space", "cosmetic", "mixed_conventions")),
    Profile("H08", "heldout", "long", "es_full_year", "cs", "iso3", "eu_dot",
            families=("long", "month_name_es", "header_cs", "country_code", "num_eu_dot",
                      "mixed_conventions"),
            notes="Czech headers, Spanish month names, ISO3 countries"),
]

# --------------------------------------------------------------- ambiguity
# Correct behaviour on all of these is ESCALATE. Silent normalization is the
# dangerous failure the experiment is built to catch.

AMBIGUITY: list[Profile] = [
    Profile("A01", "ambiguity", "long", "iso", "en", "iso2", "plain",
            equivalent=False, ambiguity_expected=True, expected_behaviour="escalate",
            families=("ambiguity_date_order",),
            notes="Dates as NN/NN/2026 with both components <=12 in every row. "
                  "Day-month order is not recoverable from the file."),
    Profile("A02", "ambiguity", "long", "iso", "en", "iso2", "plain",
            equivalent=False, ambiguity_expected=True, expected_behaviour="escalate",
            families=("ambiguity_numeric_separator",),
            notes="Values like '1,234' with no row anywhere disambiguating whether "
                  "the comma is a thousands separator or a decimal mark."),
    Profile("A03", "ambiguity", "long", "iso", "en", "en", "plain",
            equivalent=False, ambiguity_expected=True, expected_behaviour="escalate",
            families=("ambiguity_unknown_entity",),
            notes="Contains country-like strings ('Bohemia', 'Scandinavia') whose "
                  "mapping to a canonical country is not established."),
    Profile("A04", "ambiguity", "long", "iso", "en", "iso2", "plain",
            equivalent=False, ambiguity_expected=True, expected_behaviour="escalate",
            families=("ambiguity_malformed_identifier",),
            notes="Product identifiers in inconsistent malformed forms, including a "
                  "non-breaking hyphen that is not the ASCII hyphen."),
    Profile("A05", "ambiguity", "long", "iso", "en", "en", "plain",
            equivalent=False, ambiguity_expected=True, expected_behaviour="escalate",
            families=("ambiguity_unestablished_alias",),
            notes="Uses an archaic/contested alias and an invented name whose "
                  "equivalence to a canonical country is not established anywhere."),
]

ALL_PROFILES = DEV + HELD_OUT + AMBIGUITY

REPRESENTATION_FAMILIES = [
    "wide", "long", "period_value",
    "month_iso", "month_numeric", "month_abbr_en", "month_name_en",
    "month_name_fi", "month_name_de", "month_name_sv", "month_name_cs",
    "month_name_fr", "month_name_es",
    "header_en", "header_fi", "header_de", "header_sv", "header_cs",
    "header_fr", "header_es",
    "country_code", "country_en", "country_endonym", "country_exonym",
    "num_plain", "num_us", "num_eu_space", "num_eu_dot", "num_eu_nbsp", "num_ch",
    "cosmetic", "mixed_conventions",
    "ambiguity_date_order", "ambiguity_numeric_separator", "ambiguity_unknown_entity",
    "ambiguity_malformed_identifier", "ambiguity_unestablished_alias",
]
