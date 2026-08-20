#!/usr/bin/env python3
"""Fail-closed ACP permission policy — the executable form of `POLICY.md`.

Calibrated against the real wire shape recorded in
`work_interface/authority/a1_calibration/FINDINGS.md` (`ad78ed6`):

```json
{"method": "session/request_permission",
 "params": {"toolCall": {"title": ..., "rawInput": {...}},
            "options": [allow_always, allow_once, reject_once, reject_always]}}
```

**Default DENY.** An operation is permitted only by an explicit clause:

```text
ALLOW  structured read  of the exact authorized SKILL.md
ALLOW  structured read  of the exact declared fixtures
ALLOW  structured write of the exact designated work_definition.json
DENY   shell execution, unconditionally
DENY   arbitrary writes
DENY   reads of undeclared resources
DENY   unknown or unparseable requests
DENY   everything else
```

Classification is **structural**, from `rawInput`'s shape — never from the title,
never from prose. Path comparison reuses the canonicalization that replaced the
lexical scanning which voided W1-D (`harness/path_guard.py`).

This module decides. It does not teach: nothing here tells a worker which tool to
use, and the policy is identical whatever tool it reaches for.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from path_guard import canonicalize, PATH_FIELDS, COMMAND_FIELDS  # noqa: E402

# Payload keys that mean "this request carries content to be written".
WRITE_PAYLOAD_FIELDS = ("content", "text", "new_str", "after", "data")

ALLOW, DENY = "ALLOW", "DENY"
KIND_READ, KIND_WRITE, KIND_SHELL, KIND_UNKNOWN = (
    "READ", "WRITE", "SHELL", "UNKNOWN")


@dataclass(frozen=True)
class Decision:
    verdict: str          # ALLOW | DENY
    kind: str             # READ | WRITE | SHELL | UNKNOWN
    reason: str
    paths: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.verdict == ALLOW


class PermissionPolicy:
    def __init__(self, cwd: Path, readable: list[Path], writable: list[Path],
                 resource_ids: tuple[str, ...] = ()):
        self.cwd = Path(cwd)
        self.readable = {canonicalize(str(p), self.cwd) for p in readable}
        self.writable = {canonicalize(str(p), self.cwd) for p in writable}
        # Closed identifier set for the purpose-built authorized reader. Empty
        # for packs that do not enable it -- W1-E's policy is unchanged.
        self.resource_ids = tuple(resource_ids)

    # -- structural classification -------------------------------------
    @staticmethod
    def _raw(request: dict) -> dict | None:
        params = request.get("params")
        if not isinstance(params, dict):
            return None
        tc = params.get("toolCall")
        if not isinstance(tc, dict):
            return None
        raw = tc.get("rawInput")
        return raw if isinstance(raw, dict) else None

    def decide(self, request: dict) -> Decision:
        raw = self._raw(request)
        if raw is None:
            return Decision(DENY, KIND_UNKNOWN,
                            "request has no parseable toolCall.rawInput")

        # 0. the purpose-built authorized reader, if this pack enables it.
        #    Grants NOTHING new: the same three resources, reachable only by a
        #    closed identifier. Recognised STRUCTURALLY -- rawInput is exactly
        #    {"resource_id": <member of the closed set>} -- never by title.
        if self.resource_ids and set(raw.keys()) == {"resource_id"}:
            rid = raw.get("resource_id")
            if isinstance(rid, str) and rid in self.resource_ids:
                return Decision(ALLOW, KIND_READ,
                                f"authorized reader, resource_id={rid!r}")
            return Decision(DENY, KIND_READ,
                            f"authorized reader called with unknown "
                            f"resource_id {rid!r}")

        # 1. shell, unconditionally, before anything else
        for k in COMMAND_FIELDS:
            if k in raw:
                return Decision(DENY, KIND_SHELL,
                                f"shell execution is denied unconditionally "
                                f"(field {k!r})")

        # 2. structured path extraction from path-bearing fields only
        raw_paths = [v for k, v in raw.items()
                     if k in PATH_FIELDS and isinstance(v, str) and v.strip()]
        if len(raw_paths) != 1:
            return Decision(DENY, KIND_UNKNOWN,
                            f"expected exactly one path-bearing field, found "
                            f"{len(raw_paths)}: {sorted(raw_paths)[:3]}")
        target = canonicalize(raw_paths[0], self.cwd)

        # 3. write vs read, by payload shape
        carries_payload = any(
            k in raw and isinstance(raw[k], str) and raw[k] != ""
            for k in WRITE_PAYLOAD_FIELDS)

        if carries_payload:
            if target in self.writable:
                return Decision(ALLOW, KIND_WRITE,
                                "structured write of the designated artifact",
                                (target,))
            return Decision(DENY, KIND_WRITE,
                            "write to a path that is not the designated "
                            "artifact", (target,))

        if target in self.readable:
            return Decision(ALLOW, KIND_READ,
                            "structured read of an authorized resource",
                            (target,))
        if target in self.writable:
            return Decision(ALLOW, KIND_READ,
                            "structured read of the designated artifact path",
                            (target,))
        return Decision(DENY, KIND_READ,
                        "read of an undeclared resource", (target,))


def choose_option(options: list, allow: bool) -> str | None:
    """Pick from the options the agent actually offered.

    `*_once` is preferred over `*_always`: a policy that grants a standing
    permission stops being a per-request decision.
    """
    if not options:
        return None
    want = "allow" if allow else "reject"
    for o in options:
        kind = str(o.get("kind", "")).lower()
        if kind == f"{want}_once":
            return o.get("optionId")
    for o in options:
        kind = str(o.get("kind", "")).lower()
        name = str(o.get("optionId", "")).lower()
        if want in kind or want in name:
            if "always" in kind or "always" in name:
                continue
            return o.get("optionId")
    for o in options:                      # last resort, still the right side
        if want in str(o.get("kind", "")).lower():
            return o.get("optionId")
    return None
