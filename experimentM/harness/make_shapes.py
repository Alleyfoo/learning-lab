#!/usr/bin/env python3
"""Experiment M — the breadth fixtures.

Six provider shapes, each varying ONE thing that a real supplier file plausibly
does. The question is not whether these can be *read* — it is whether recipe
format v1.3's closed enums can EXPRESS them without an escape hatch.

  S1  clean wide monthly          the shape the format was designed on
  S2  two-row stacked header      "2026" over "Tammi | Helmi | Maalis"
  S3  two measure blocks          units AND euros, each spread over months
  S4  already long                one row per product-month; nothing to unpivot
  S5  formatted numbers           "1 234,50" and "12 %" as text
  S6  interleaved note row        a comment row in the MIDDLE of the data

Every gap these expose is also a security question: an escape hatch is exactly
where an expression language comes back.

.xlsx output is not byte-reproducible, so each file is written only when asked
for by stem.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures"


def _wb(rows: list[list[object]], title: str = "Sales") -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    for row in rows:
        ws.append(row)
    return wb


SHAPES = {
    "S1_clean_wide": [
        ["Tuote", "Tammi", "Helmi", "Maalis"],
        ["ART-001", 10, 12, 8],
        ["ART-002", 7, 9, 11],
    ],
    # S2: the year sits on its own row above the month names -- a single
    # `header_row` cannot name a two-row header.
    "S2_stacked_header": [
        [None, "2026", "2026", "2026"],
        ["Tuote", "Tammi", "Helmi", "Maalis"],
        ["ART-001", 10, 12, 8],
        ["ART-002", 7, 9, 11],
    ],
    # S3: two measure blocks over the same months.
    "S3_two_measure_blocks": [
        ["Tuote", "Tammi kpl", "Helmi kpl", "Tammi eur", "Helmi eur"],
        ["ART-001", 10, 12, 100.0, 120.0],
        ["ART-002", 7, 9, 70.0, 90.0],
    ],
    "S4_already_long": [
        ["Tuote", "Kuukausi", "Myynti"],
        ["ART-001", "Tammi", 10],
        ["ART-001", "Helmi", 12],
        ["ART-002", "Tammi", 7],
    ],
    # S5: numbers written as text with a thousands space and a percent sign.
    "S5_formatted_numbers": [
        ["Tuote", "Tammi", "Helmi"],
        ["ART-001", "1 234,50", "12 %"],
        ["ART-002", "2 000,00", "8 %"],
    ],
    # S6: a note row in the MIDDLE of the data, not at the bottom.
    "S6_interleaved_note": [
        ["Tuote", "Tammi", "Helmi"],
        ["ART-001", 10, 12],
        ["Huom: hinnat muuttuivat", None, None],
        ["ART-002", 7, 9],
    ],
}


def main(only: str | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, rows in SHAPES.items():
        if only is not None and only != stem:
            continue
        _wb(rows).save(OUT / f"{stem}.xlsx")
        written.append(stem)
    for stem in written:
        print(f"wrote {stem}.xlsx")
    if only is None:
        print("WARNING: wrote every shape; frozen hashes elsewhere are now void")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
