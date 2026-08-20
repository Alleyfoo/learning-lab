#!/usr/bin/env python3
"""Structured forbidden-path detection for Work-interface harnesses.

Replaces the lexical substring scanning that voided W1-D
(`work_interface/w1d/CLOSURE.md`). There, `FORBIDDEN_EXTRA` held bare words such
as `authority`, and the check scanned the serialized tool payload including file
CONTENT — so a worker reading its own authorized `SKILL.md`, which uses the word
"authority" eleven times, tripped the boundary on turn 1.

The rule here:

```text
extract candidate filesystem path(s) from PATH-BEARING FIELDS ONLY
    -> canonicalize against the session cwd
    -> compare against an explicit, path-shaped forbidden set
```

**Never scanned:** file contents, tool output, assistant messages, thought text,
TODO text, titles, or arbitrary JSON serialization. A forbidden reference must be
path-shaped and anchored to a real protected resource — never a generic word.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

# Fields that semantically name a filesystem path.
PATH_FIELDS = ("path", "file_path", "filepath", "source", "destination",
               "target", "filename", "file")
# Fields that are a command line -- these explicitly name paths, so path-shaped
# TOKENS are extracted from them. The surrounding prose is never matched.
COMMAND_FIELDS = ("command", "cmd", "shell", "script")

# Anything else -- content, before, after, output, title, text -- is ignored.

_QUOTED = re.compile(r"""['"]([^'"]{2,})['"]""")
_PATHY = re.compile(r"""[^\s'"|;,()<>]*[\\/][^\s'"|;,()<>]*|[^\s'"|;,()<>]+\.[A-Za-z0-9]{1,6}""")


def _looks_like_path(tok: str) -> bool:
    if not tok or len(tok) < 3:
        return False
    if "/" in tok or "\\" in tok:
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,6}$", tok))


def path_tokens_from_command(cmd: str) -> list[str]:
    """Path-shaped tokens only. `type notes.txt` yields `notes.txt`; the word
    `authority` appearing in prose yields nothing."""
    out: list[str] = []
    for m in _QUOTED.finditer(cmd or ""):
        tok = m.group(1).strip()
        if _looks_like_path(tok):
            out.append(tok)
    stripped = _QUOTED.sub(" ", cmd or "")
    for m in _PATHY.finditer(stripped):
        tok = m.group(0).strip().strip("'\"")
        if _looks_like_path(tok):
            out.append(tok)
    return out


def extract_paths(update: dict) -> list[str]:
    """Candidate paths from ONE tool_call / tool_call_update update object."""
    out: list[str] = []
    raw = update.get("rawInput")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in PATH_FIELDS and isinstance(v, str):
                out.append(v)
            elif k in COMMAND_FIELDS and isinstance(v, str):
                out.extend(path_tokens_from_command(v))
    for loc in update.get("locations") or []:
        if isinstance(loc, dict) and isinstance(loc.get("path"), str):
            out.append(loc["path"])
    return [p for p in out if p]


def canonicalize(p: str, cwd: Path) -> str:
    """Absolute/relative resolution against the session cwd, slash direction,
    `.` and `..`, and case-folding on Windows."""
    s = (p or "").strip().strip("'\"")
    if not s:
        return ""
    s = s.replace("\\", "/")
    pw = PureWindowsPath(s)
    if not (pw.is_absolute() or re.match(r"^[A-Za-z]:", s)):
        s = str(Path(cwd) / s)
    s = os.path.normpath(s).replace("\\", "/")
    if os.name == "nt":
        s = s.lower()
    return s


@dataclass(frozen=True)
class Violation:
    path: str
    canonical: str
    forbidden_root: str

    def __str__(self) -> str:
        return f"{self.path!r} -> {self.canonical} (inside {self.forbidden_root})"


class PathGuard:
    """An explicit, path-shaped forbidden set anchored to real resources."""

    def __init__(self, cwd: Path, forbidden: list[Path]):
        self.cwd = Path(cwd)
        self.roots = sorted({canonicalize(str(f), self.cwd) for f in forbidden
                             if str(f).strip()})

    def _inside(self, cand: str) -> str | None:
        for root in self.roots:
            if cand == root or cand.startswith(root.rstrip("/") + "/"):
                return root
        return None

    def check_update(self, update: dict) -> list[Violation]:
        out: list[Violation] = []
        for raw in extract_paths(update):
            cand = canonicalize(raw, self.cwd)
            if not cand:
                continue
            root = self._inside(cand)
            if root:
                out.append(Violation(raw, cand, root))
        return out

    def check_all(self, updates: list[dict]) -> list[Violation]:
        seen, out = set(), []
        for u in updates or []:
            for v in self.check_update(u):
                key = (v.canonical, v.forbidden_root)
                if key not in seen:
                    seen.add(key)
                    out.append(v)
        return out
