"""Deterministic CSV -> neutral row representation.

Identical to experiment2b/harness/render_rows.py so the input representation is a
constant across 2B and 3A. Infrastructure, not part of the agent task: the model is
handed the rows already rendered.

Blank rows are counted and rendered as (empty), so row numbers are 1-based positions
in the file.
"""
from __future__ import annotations
import csv
from pathlib import Path


def render(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    out = []
    for i, row in enumerate(rows, start=1):
        cells = [c.strip() for c in row]
        body = " | ".join(cells) if any(cells) else "(empty)"
        out.append(f"ROW {i}:\n{body}")
    return "\n\n".join(out)


def header_cells(path: Path, header_row: int) -> list[str]:
    """Return the stripped cells of a 1-based file row, deterministically."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    idx = header_row - 1
    if idx < 0 or idx >= len(rows):
        return []
    return [c.strip() for c in rows[idx]]


if __name__ == "__main__":
    import sys
    print(render(Path(sys.argv[1])))