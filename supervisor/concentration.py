#!/usr/bin/env python3
"""Deterministic dependency-concentration measurement for the supervisor snapshot.

This is the Phase C machinery of S7. A supervisory *method* (ask what workers
share and how concentrated those shared dependencies are) proved useful
repeatedly across fleets with different dependency structures. Phase B
proposed it become a deterministic platform measurement; a human authorized
it; this module is the authorized implementation.

## What it is, and what it is NOT

It is a **pure mechanical aggregation** over fields the snapshot already
declares (engine, trigger, effect, model digest). It counts workers per
dependency identity and computes each identity's share of the fleet. That is
all. It is attached to a snapshot for Phase D as `snap["dependency_concentration"]`;
`snapshot.py` itself is NOT modified -- the inherited read-only floor stays
frozen, and the attachment is the authorization switch.

It is NOT an interpretation. The critical S7 distinction:

```text
OBSERVED:   55 / 70 workers share trigger X        <- the platform MAY expose this
INFERRED:   this creates dangerous blast-radius risk <- the supervisor interprets
```

This module contains only the former. It never says a concentration is "risky",
"safe", "dominant", "critical", a "concern", a "blast radius", or anything else
that decides whether the facts matter. It reports the distribution; the LLM
still owns what the distribution means. Laundering "risk" into an observed fact
is exactly the failure this module exists to prevent, so a self-test canaries
that no interpretation word appears anywhere in its output.

## Output shape

```json
{
  "schema": "supervisor.dependency_concentration/v1",
  "worker_count": 70,
  "by_type": {
    "engine":  [{"identity": "...", "worker_count": 60, "fleet_share": 0.857}, ...],
    "trigger":  [{"identity": "...", "worker_count": 55, "fleet_share": 0.786}, ...],
    "effect":  [{"identity": "...", "worker_count": 17, "fleet_share": 0.243}, ...],
    "digest":  [{"identity": "<sha256>", "worker_count": 60, "fleet_share": 0.857}, ...]
  }
}
```

Each list is sorted by `worker_count` descending (a faithful ordering of facts,
not a verdict). `effect` omits workers that declare no effect. `fleet_share` is
`worker_count / worker_count` of the whole fleet, so the shares within a type
sum to 1.0 only for types every worker carries (engine, trigger, digest); for
`effect` the shares sum to the fraction of the fleet that has an effect.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Optional

SCHEMA = "supervisor.dependency_concentration/v1"

# Verdict words a measurement must never attach to a specific distribution. If
# any appears in the output (key or value), the measurement has crossed from
# OBSERVED fact into INFERRED verdict -- the exact failure S7 Phase C exists to
# prevent. Lower-cased substring match for the check.
#
# "concentration" is NOT here: it is the measurement's authorized NAME (the
# human-approved key is `dependency_concentration`), not a verdict about data.
# The canary forbids judging a *specific* distribution (risk / dominant / blast
# / critical / ...), not naming what the measurement measures.
_INTERPRETATION_WORDS = (
    "risk", "risky", "safe", "unsafe", "danger", "dangerous", "hazard",
    "dominant", "dominates", "dominated", "blast", "radius",
    "critical", "concern", "warn", "warning", "alert", "issue", "problem",
    "anomaly", "outlier", "unusual", "notable", "significant", "severe",
    "impact", "expose", "exposed", "vulnerab", "threat", "fail", "broken",
    "bad", "good", "healthy", "sick", "ill",
)


def _digest_of(worker: dict) -> Optional[str]:
    """The digest of the worker's current version, from version_history.

    Mirrors how `supervisor.snapshot` exposes history: each version_history
    entry carries `version` and `digest`. The current version's digest is the
    identity we count; a worker with no history carries no digest.
    """
    cur = worker.get("current_version")
    for h in worker.get("version_history", []):
        if h.get("version") == cur and h.get("digest"):
            return h["digest"]
    for h in reversed(worker.get("version_history", [])):
        if h.get("digest"):
            return h["digest"]
    return None


def _distribution(counts: dict, total: int) -> list[dict]:
    """Sorted list of {identity, worker_count, fleet_share}.

    `fleet_share` is always against the WHOLE fleet (`total`), never against
    the non-empty subset, so a type carried by every worker sums to 1.0 and a
    type carried by a subset (effect) sums to less. Sorting by count descending
    is an ordering of facts, not a verdict.
    """
    out = []
    for identity, count in counts.items():
        out.append({"identity": identity, "worker_count": count,
                    "fleet_share": round(count / total, 6) if total else 0.0})
    out.sort(key=lambda e: (-e["worker_count"], str(e["identity"])))
    return out


def measure(snapshot: dict) -> dict:
    """Pure mechanical aggregation. No model, no text, no verdict.

    Reads only `worker_count` and the per-worker `engine`/`trigger`/`effect`
    and current-version `digest`. Returns a new dict; the snapshot is not
    mutated (the caller attaches the result if it chooses to).
    """
    workers = snapshot.get("workers", [])
    total = snapshot.get("worker_count") or len(workers)
    engines = Counter(w.get("engine") for w in workers if w.get("engine") is not None)
    triggers = Counter(w.get("trigger") for w in workers if w.get("trigger") is not None)
    effects = Counter(w.get("effect") for w in workers if w.get("effect") is not None)
    digests = Counter(d for d in (_digest_of(w) for w in workers) if d)
    return {
        "schema": SCHEMA,
        "worker_count": total,
        "by_type": {
            "engine": _distribution(engines, total),
            "trigger": _distribution(triggers, total),
            "effect": _distribution(effects, total),
            "digest": _distribution(digests, total),
        },
    }


# ---------------------------------------------------------------------------
# self-test -- no model call; canaries the OBSERVED-only / faithful contract
# ---------------------------------------------------------------------------

def _contains_interpretation(obj) -> Optional[str]:
    """Return the first interpretation word found in any key or string value."""
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(k, str) and _word_hit(k):
                    return k
                found = walk(v)
                if found:
                    return found
        elif isinstance(x, list):
            for v in x:
                found = walk(v)
                if found:
                    return found
        elif isinstance(x, str) and _word_hit(x):
            return x
        return None
    return walk(obj)


def _word_hit(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in _INTERPRETATION_WORDS)


def _synthetic_snapshot() -> dict:
    """A tiny snapshot with a clear engine concentration, for the canary.

    Built by hand (not via the fleet builder) so this module stays independent
    of s7/. 5 workers: 3 on engine A (concentrated), 1 each on B/C; two share a
    trigger; one has an effect; distinct digests.
    """
    workers = [
        {"name": "w0", "engine": "engA", "trigger": "t0", "effect": None,
         "current_version": 1,
         "version_history": [{"version": 1, "digest": "d0"}]},
        {"name": "w1", "engine": "engA", "trigger": "t0", "effect": None,
         "current_version": 1,
         "version_history": [{"version": 1, "digest": "d1"}]},
        {"name": "w2", "engine": "engA", "trigger": "t1", "effect": "accept",
         "current_version": 1,
         "version_history": [{"version": 1, "digest": "d2"}]},
        {"name": "w3", "engine": "engB", "trigger": "t2", "effect": None,
         "current_version": 1,
         "version_history": [{"version": 1, "digest": "d3"}]},
        {"name": "w4", "engine": "engC", "trigger": "t3", "effect": None,
         "current_version": 1,
         "version_history": [{"version": 1, "digest": "d4"}]},
    ]
    return {"schema": "supervisor.snapshot/v1", "scopes": ["Acme Oy"],
            "worker_count": 5, "workers": workers, "pending_exceptions": []}


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    snap = _synthetic_snapshot()
    snap_before = json.dumps(snap, sort_keys=True)
    m = measure(snap)
    snap_after = json.dumps(snap, sort_keys=True)

    # --- CANARY: pure -- the snapshot is not mutated ----------------------
    check(snap_before == snap_after,
          "CANARY: measure() must not mutate the snapshot")

    # --- CANARY: OBSERVED only -- no interpretation word anywhere ---------
    bad = _contains_interpretation(m)
    check(bad is None,
          f"CANARY: output must contain no interpretation word (found '{bad}'). "
          f"The measurement reports distribution; the LLM owns what it means.")

    # --- faithful distribution: counts and shares -------------------------
    check(m["schema"] == SCHEMA, f"schema tag: {m['schema']}")
    check(m["worker_count"] == 5, f"worker_count echoed: {m['worker_count']}")
    eng = m["by_type"]["engine"]
    check(eng[0] == {"identity": "engA", "worker_count": 3, "fleet_share": 0.6},
          f"engine concentration reported, sorted desc, share vs whole fleet: {eng}")
    check(sum(e["worker_count"] for e in eng) == 5,
          f"engine counts cover the whole fleet (sum={sum(e['worker_count'] for e in eng)})")
    check(abs(sum(e["fleet_share"] for e in eng) - 1.0) < 1e-9,
          f"engine shares sum to 1.0 (every worker carries an engine)")
    # effect is carried by a subset -> shares sum to < 1.0
    eff = m["by_type"]["effect"]
    check(sum(e["worker_count"] for e in eff) == 1 and eff[0]["identity"] == "accept",
          f"effect omits workers with no effect: {eff}")
    check(abs(sum(e["fleet_share"] for e in eff) - 0.2) < 1e-9,
          f"effect shares sum to the fraction that has an effect (0.2), not 1.0")
    # trigger: two workers share t0
    trg = m["by_type"]["trigger"]
    check(trg[0]["worker_count"] == 2 and trg[0]["identity"] == "t0",
          f"trigger shares reported faithfully: {trg}")
    # digest: five distinct digests, one each
    dig = m["by_type"]["digest"]
    check(len(dig) == 5 and all(d["worker_count"] == 1 for d in dig),
          f"distribution is faithful even when nothing is concentrated: {dig}")

    # --- a fleet where one digest dominates (digest concentration) --------
    dig_workers = [
        {"name": f"w{i}", "engine": f"eng{i % 3}", "trigger": f"t{i % 4}",
         "effect": None, "current_version": 1,
         "version_history": [{"version": 1, "digest": "shared" if i < 4 else f"d{i}"}]}
        for i in range(6)
    ]
    m2 = measure({"worker_count": 6, "workers": dig_workers,
                  "pending_exceptions": []})
    check(_contains_interpretation(m2) is None,
          "CANARY: digest-concentrated fleet still reports no interpretation word")
    check(m2["by_type"]["digest"][0] == {"identity": "shared", "worker_count": 4,
                                         "fleet_share": round(4 / 6, 6)},
          f"digest concentration reported as a count+share, no verdict: "
          f"{m2['by_type']['digest']}")
    # engines distributed across 3 -> no engine concentration, and no label says so
    check(m2["by_type"]["engine"][0]["worker_count"] == 2,
          f"distributed engines reported as even counts, not 'safe': "
          f"{m2['by_type']['engine']}")

    # --- empty fleet: no division by zero, still no interpretation ---------
    m3 = measure({"worker_count": 0, "workers": [], "pending_exceptions": []})
    check(_contains_interpretation(m3) is None,
          "CANARY: empty fleet reports no interpretation word")
    check(all(m3["by_type"][t] == [] for t in ("engine", "trigger", "effect", "digest")),
          f"empty fleet -> empty distributions: {m3['by_type']}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (measure is pure / OBSERVED-only -- no interpretation "
          "word in any output / distribution faithful -- counts cover the fleet, "
          "shares vs the whole fleet, effect subset sums to its fraction, sorted "
          "desc as an ordering of facts / digest concentration and distributed "
          "engines both reported as counts+shares with no verdict / empty fleet "
          "safe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)