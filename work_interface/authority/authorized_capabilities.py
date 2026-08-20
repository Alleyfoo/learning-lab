#!/usr/bin/env python3
"""The worker's entire capability box: two verbs, nothing else.

W1-F established two things. The purpose-built reader is discovered and used
unprompted (3/3). And attaching an MCP server **replaces** Goose's builtin tool
surface rather than extending it — calibration `d511894`, direct from provider
traffic.

W1-G stops fighting that and uses it. The worker is not handed a general-purpose
computer with a policy bolted on top; it is handed exactly the capabilities its
role requires.

```text
READ AUTHORITY   read_authorized_resource(skill | supplier_statement | ledger_book)
WRITE AUTHORITY  write_work_definition(content)
everything else  DENY
```

Absent, and unreachable by any argument:

```text
no shell                no subprocess is imported, ever
no generic filesystem   neither tool accepts a path
no path-bearing write   the destination is fixed internally
no directory listing    there is no enumerate/glob/tree route
no edit/append/rename/delete
no second artifact      the writer is single-shot and refuses to overwrite
```

`content` is deliberately **text, not a parsed JSON object**. If the worker
emits malformed JSON, the structural gate must still be able to observe that
failure. This tool supplies authority, never a silent improvement to the
worker's output — it does not parse, reformat, pretty-print or validate.

The frozen `authorized_reader.py` is imported, not modified: W1-F's reader
behaviour is reused byte-for-byte.

Run as a stdio MCP server:

    python authorized_capabilities.py <run_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# RESOURCE_IDS / resource_path / sha256_of are re-exported unchanged so
# calibration can import the whole capability box from one module.
from authorized_reader import (  # noqa: E402,F401
    RESOURCE_IDS, INPUT_SCHEMA as READ_INPUT_SCHEMA, TOOL_DESCRIPTION as
    READ_TOOL_DESCRIPTION, TOOL_NAME as READ_TOOL_NAME, UnknownResource,
    read_resource, resource_path, sha256_of)

ARTIFACT_NAME = "work_definition.json"

WRITE_TOOL_NAME = "write_work_definition"
WRITE_TOOL_DESCRIPTION = (
    "Write the finished work definition for this run. "
    "Pass the complete artifact text as `content`; it is written verbatim as "
    "UTF-8. The destination is fixed for this run and there is no file path to "
    "supply. This is the only way to produce the artifact, and it may be "
    "called only once — a second call is refused because the artifact already "
    "exists."
)

WRITE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "The complete text of the work definition artifact, "
                           "written verbatim.",
        }
    },
    "required": ["content"],
    "additionalProperties": False,
}


class WriteRefused(RuntimeError):
    """The single-shot writer refused. Never rescued, never retried for it."""


def artifact_path(run_dir: Path) -> Path:
    """The fixed destination. The caller never supplies, or influences, this."""
    return Path(run_dir) / ARTIFACT_NAME


def write_work_definition(content: str, run_dir: Path) -> dict:
    """Write the artifact verbatim, exactly once.

    No parsing, no reformatting, no validation of the payload: malformed JSON
    must survive to the structural gate intact.
    """
    if not isinstance(content, str):
        raise WriteRefused(
            f"`content` must be a string, got {type(content).__name__}")
    target = artifact_path(run_dir)
    if target.exists():
        raise WriteRefused(
            f"{ARTIFACT_NAME} already exists for this run; "
            f"write_work_definition may be called only once and will not "
            f"overwrite, append to, or replace it")
    # newline='' so the bytes written are exactly the bytes supplied.
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    return {"written": ARTIFACT_NAME, "bytes": len(content.encode("utf-8"))}


TOOLS = [
    {"name": READ_TOOL_NAME,
     "description": READ_TOOL_DESCRIPTION,
     "inputSchema": READ_INPUT_SCHEMA},
    {"name": WRITE_TOOL_NAME,
     "description": WRITE_TOOL_DESCRIPTION,
     "inputSchema": WRITE_INPUT_SCHEMA},
]


# ---------------------------------------------------------------------------
# minimal stdio MCP server
# ---------------------------------------------------------------------------

def _result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code,
                                                   "message": message}}


def _tool_error(rid, text):
    return _result(rid, {"content": [{"type": "text", "text": text}],
                         "isError": True})


def handle(msg: dict, run_dir: Path):
    """One request -> one response, or None for a notification."""
    method = msg.get("method")
    rid = msg.get("id")
    if method == "initialize":
        return _result(rid, {
            "protocolVersion": (msg.get("params") or {}).get(
                "protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "authorized-capabilities", "version": "1"}})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return _result(rid, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == READ_TOOL_NAME:
            try:
                text = read_resource(args.get("resource_id"), run_dir)
            except UnknownResource as e:
                return _tool_error(rid, str(e))
            except OSError as e:
                return _tool_error(rid, f"resource unavailable: {e}")
            return _result(rid, {"content": [{"type": "text", "text": text}]})

        if name == WRITE_TOOL_NAME:
            try:
                info = write_work_definition(args.get("content"), run_dir)
            except WriteRefused as e:
                return _tool_error(rid, str(e))
            except OSError as e:
                return _tool_error(rid, f"write failed: {e}")
            return _result(rid, {"content": [
                {"type": "text",
                 "text": f"wrote {info['bytes']} bytes to {info['written']}"}]})

        return _tool_error(rid, f"unknown tool {name!r}; this run's "
                                f"capabilities are "
                                f"{[t['name'] for t in TOOLS]}")
    if rid is None:
        return None
    return _error(rid, -32601, f"method not found: {method}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: authorized_capabilities.py <run_dir>", file=sys.stderr)
        return 2
    run_dir = Path(argv[0]).resolve()
    # MCP stdio is UTF-8. sys.stdin defaults to the console codepage on Windows
    # (cp1252 here), which silently mangles every non-ASCII byte on the INPUT
    # path -- an em dash arrived as three characters and was written back
    # double-encoded, voiding W1-G's FIDELITY layer (see ../w1g/CLOSURE.md §3).
    # Responses were never affected because json.dumps escapes non-ASCII.
    if getattr(sys.stdin, "reconfigure", None) is not None:
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
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
