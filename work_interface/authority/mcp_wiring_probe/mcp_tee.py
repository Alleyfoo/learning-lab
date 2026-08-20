#!/usr/bin/env python3
"""PROBE ONLY. Wraps authorized_reader and tees the MCP conversation to a log.

Used once to prove Goose actually loads and handshakes with the server. The real
reader is never given a write capability; this wrapper exists only in scratch.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\pertt\learning-lab\work_interface\authority")
import authorized_reader as R

LOG = Path(sys.argv[1])
run_dir = Path(sys.argv[2]).resolve()


def log(direction, obj):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"dir": direction, "msg": obj},
                            ensure_ascii=False) + "\n")


log("start", {"argv": sys.argv[1:]})
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        log("raw", line)
        continue
    log("in", msg)
    out = R.handle(msg, run_dir)
    if out is not None:
        # never log full resource text; record only its size
        red = json.loads(json.dumps(out))
        try:
            c = red["result"]["content"][0]["text"]
            red["result"]["content"][0]["text"] = f"<{len(c)} chars>"
        except Exception:
            pass
        log("out", red)
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
