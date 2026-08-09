"""Deterministic CSV -> neutral row representation.

Infrastructure, not part of the agent task. The model never needs to write code
to inspect a file; it is handed the rows already.

Blank rows are counted and rendered as (empty), so row numbers are 1-based
positions in the file.
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


if __name__ == "__main__":
    import sys
    print(render(Path(sys.argv[1])))
