#!/usr/bin/env python3
"""Transparent logging proxy in front of Ollama. PROBE INFRASTRUCTURE ONLY.

Goose is NOT modified. This only changes where Goose's configured provider
endpoint points (OLLAMA_HOST), and forwards every byte verbatim to the real
Ollama. Its sole purpose is to preserve the `tools` array actually offered to
the model, which the ACP surface never exposes.

Request bodies are logged in full. Response bodies are streamed straight
through and NOT logged (they are the model's output, already captured on the
ACP side).
"""
from __future__ import annotations

import http.client
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 11434

LOG_PATH = sys.argv[1]
LISTEN_PORT = int(sys.argv[2])

_lock = threading.Lock()


def log(obj: dict) -> None:
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silence stderr noise
        pass

    def _relay(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        record: dict = {"method": method, "path": self.path, "bytes": len(body)}
        if body:
            try:
                parsed = json.loads(body)
                tools = parsed.get("tools")
                if isinstance(tools, list):
                    names = []
                    for t in tools:
                        fn = t.get("function") if isinstance(t, dict) else None
                        if isinstance(fn, dict):
                            names.append(fn.get("name"))
                        elif isinstance(t, dict):
                            names.append(t.get("name"))
                    record["tool_names"] = names
                    record["tool_count"] = len(names)
                else:
                    record["tool_names"] = None
                record["model"] = parsed.get("model")
                record["body"] = parsed
            except Exception as exc:  # noqa: BLE001
                record["parse_error"] = str(exc)
                record["raw"] = body[:4000].decode("utf-8", "replace")
        log(record)

        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT,
                                          timeout=900)
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length")}
        if body:
            headers["Content-Length"] = str(len(body))
        conn.request(method, self.path, body=body, headers=headers)
        resp = conn.getresponse()

        self.send_response(resp.status)
        passthrough = [(k, v) for k, v in resp.getheaders()
                       if k.lower() not in ("transfer-encoding", "connection",
                                            "content-length")]
        for k, v in passthrough:
            self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            self.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        conn.close()

    def do_POST(self):
        self._relay("POST")

    def do_GET(self):
        self._relay("GET")


if __name__ == "__main__":
    log({"event": "proxy_start", "listen": LISTEN_PORT,
         "upstream": f"{UPSTREAM_HOST}:{UPSTREAM_PORT}"})
    ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), Handler).serve_forever()
