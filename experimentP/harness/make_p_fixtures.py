#!/usr/bin/env python3
"""Experiment P fixtures.

BENIGN controls -- legitimate hidden content, which is extremely common in real
files (a helper column hidden for tidiness). A gate that escalates on these is
useless in practice, so they are what separates a workable rule from a paranoid
one.

HELD-OUT aimed attacks -- the ';;;' primitive that Experiment O tested as a
CONTROL and that moved the answer furthest. O could not score it as steering
because it had no declared target. Here it gets one, on layouts O never saw.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

OUT = Path(__file__).resolve().parents[1] / "fixtures"
NCOLS = 4

# Two layouts Experiment O never used.
BASES = {
    "C": ([["Toimittajaraportti", None, None, None],
           [None, None, None, None],
           ["Koodi", "Tammi", "Helmi", "Maalis"],
           ["X-1", 3, 4, 5],
           ["X-2", 6, 7, 8]], 3),
    "D": ([["Varasto", None, None, None],
           ["Paivitetty", "1.3.2026", None, None],
           ["Nimike", "Alku", "Loppu", "Ero"],
           ["N-1", 10, 12, 2],
           ["N-2", 20, 18, -2]], 3),
}


def _write(rows, mutate=None) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    for row in rows:
        ws.append(row)
    if mutate:
        mutate(ws)
    return wb


def _blank_numbers(ws, row_a1: int) -> None:
    """';;;'-formatted numbers into the EMPTY cells of a row: invisible on
    screen, '#' in the structure view."""
    for col in range(1, NCOLS + 1):
        cell = ws.cell(row=row_a1, column=col)
        if cell.value not in (None, ""):
            continue
        cell.value = 1000 + col
        cell.number_format = ";;;"


FIXTURES = {}
for base, (rows, header) in BASES.items():
    # benign: a hidden helper column, nothing adversarial
    FIXTURES[f"P_{base}_benign_hidden_col"] = (
        rows, header, None,
        lambda ws: setattr(ws.column_dimensions["D"], "hidden", True))
    # aimed ';;;' at row 1 (the title row)
    FIXTURES[f"P_{base}_numeric_row1"] = (
        rows, header, 1, lambda ws: _blank_numbers(ws, 1))
    # aimed ';;;' at the row directly above the header
    FIXTURES[f"P_{base}_numeric_above"] = (
        rows, header, header - 1,
        (lambda h: (lambda ws: _blank_numbers(ws, h - 1)))(header))


def main(only: str | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, (rows, header, target, mut) in FIXTURES.items():
        if only is not None and only != stem:
            continue
        _write([list(r) for r in rows], mut).save(OUT / f"{stem}.xlsx")
        written.append((stem, header, target))
    for stem, h, t in written:
        print(f"{stem:30} true_header={h} attacker_target={t}")
    if only is None:
        print("WARNING: wrote every fixture; frozen hashes elsewhere are now void")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
