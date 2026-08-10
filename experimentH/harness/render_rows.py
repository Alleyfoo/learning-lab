"""Deterministic CSV -> neutral row representation. Identical to
experiment2b/3a/3b/3c/3d/3e harness/render_rows.py so the input representation is a
constant across the programme. Infrastructure, not part of the agent task.
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