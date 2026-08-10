#!/usr/bin/env python3
"""Render a CSV to a neutral row representation for LLM prompts.

Copy of experimentH/harness/render_rows.py. Reads a UTF-8 CSV and emits:

    ROW 1:
    <cells joined by " | ">
    ROW 2:
    <cells joined by " | ">
    ...

Empty cells render as "(empty)". Output is UTF-8 to stdout. This is a pure
formatting helper; it performs no classification.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path


def render(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    out = []
    for i, row in enumerate(rows, start=1):
        cells = [(c if c.strip() != "" else "(empty)") for c in row]
        out.append(f"ROW {i}:\n" + " | ".join(cells))
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_rows.py <csv_path>\n")
        raise SystemExit(2)
    sys.stdout.write(render(Path(sys.argv[1])) + "\n")