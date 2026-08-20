#!/usr/bin/env python3
"""`read_authorized_resource` — a purpose-built authorized text reader.

W1-E established that the *authority boundary* was correct but the *authorized
reader interface* was not operationally usable: `read_image` and `analyze` were
both PERMITTED on SKILL.md and both returned no text, and the only tool that has
ever reliably delivered file text in this line is shell, which is denied
(`work_interface/w1e/CLOSURE.md`).

This tool improves the ergonomics of authority already granted. It grants
**nothing new**: exactly the three resources the worker could already read.

```text
read_authorized_resource(resource_id)
    resource_id in {"skill", "supplier_statement", "ledger_book"}
```

Deliberately absent, and not reachable by any argument:

```text
no path argument           the caller cannot name a file at all
no directory listing       there is no enumerate/glob/tree route
no write capability        the tool only ever returns text
no shell route             no subprocess is spawned, ever
no other resource          an unknown id is refused by name
```

Because the only input is an identifier from a closed set, path traversal,
`..`, absolute paths, `file://` URIs and symlink tricks are not *filtered* —
they are **unrepresentable**.

Run as a stdio MCP server:

    python authorized_reader.py <run_dir>

Importable for offline calibration:

    from authorized_reader import RESOURCE_IDS, read_resource
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK_INTERFACE = HERE.parent
W1A = WORK_INTERFACE / "w1a"

RESOURCE_IDS = ("skill", "supplier_statement", "ledger_book")

TOOL_NAME = "read_authorized_resource"
TOOL_DESCRIPTION = (
    "Return the exact text of one authorized resource for this run. "
    "This is the only way to read the task's resources. "
    "`skill` is the process-definition skill you must follow. "
    "`supplier_statement` and `ledger_book` are the two business-data files. "
    "Pass the identifier only; there is no file path, and no other resource "
    "can be reached."
)

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "resource_id": {
            "type": "string",
            "enum": list(RESOURCE_IDS),
            "description": "Which authorized resource to read.",
        }
    },
    "required": ["resource_id"],
    "additionalProperties": False,
}


class UnknownResource(ValueError):
    pass


def resource_path(resource_id: str, run_dir: Path) -> Path:
    """Map an identifier to a path. The caller never supplies a path."""
    if resource_id == "skill":
        return Path(run_dir) / "SKILL.md"
    if resource_id == "supplier_statement":
        return W1A / "fixtures" / "supplier-statement.txt"
    if resource_id == "ledger_book":
        return W1A / "fixtures" / "ledger-book.txt"
    raise UnknownResource(
        f"unknown resource_id {resource_id!r}; authorized identifiers are "
        f"{list(RESOURCE_IDS)}")


def read_resource(resource_id: str, run_dir: Path) -> str:
    """The exact text of an authorized resource. No transformation of any kind."""
    if not isinstance(resource_id, str) or resource_id not in RESOURCE_IDS:
        raise UnknownResource(
            f"unknown resource_id {resource_id!r}; authorized identifiers are "
            f"{list(RESOURCE_IDS)}")
    return resource_path(resource_id, run_dir).read_text(encoding="utf-8")


def sha256_of(resource_id: str, run_dir: Path) -> str:
    return hashlib.sha256(
        resource_path(resource_id, run_dir).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# minimal stdio MCP server
# ---------------------------------------------------------------------------

def _result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code,
                                                   "message": message}}


def handle(msg: dict, run_dir: Path):
    """One request -> one response, or None for a notification."""
    method = msg.get("method")
    rid = msg.get("id")
    if method == "initialize":
        return _result(rid, {
            "protocolVersion": (msg.get("params") or {}).get(
                "protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "authorized-reader", "version": "1"}})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return _result(rid, {"tools": [{"name": TOOL_NAME,
                                        "description": TOOL_DESCRIPTION,
                                        "inputSchema": INPUT_SCHEMA}]})
    if method == "tools/call":
        params = msg.get("params") or {}
        if params.get("name") != TOOL_NAME:
            return _result(rid, {"content": [{"type": "text",
                                              "text": f"unknown tool "
                                                      f"{params.get('name')!r}"}],
                                 "isError": True})
        args = params.get("arguments") or {}
        try:
            text = read_resource(args.get("resource_id"), run_dir)
        except UnknownResource as e:
            return _result(rid, {"content": [{"type": "text", "text": str(e)}],
                                 "isError": True})
        except OSError as e:
            return _result(rid, {"content": [{"type": "text",
                                              "text": f"resource unavailable: {e}"}],
                                 "isError": True})
        return _result(rid, {"content": [{"type": "text", "text": text}]})
    if rid is None:
        return None
    return _error(rid, -32601, f"method not found: {method}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: authorized_reader.py <run_dir>", file=sys.stderr)
        return 2
    run_dir = Path(argv[0]).resolve()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        out = handle(msg, run_dir)
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
