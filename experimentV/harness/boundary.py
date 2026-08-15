#!/usr/bin/env python3
"""The ingest boundary: an interpretation processor CANNOT mint observations.

Not a rule the model is asked to follow. A channel that cannot carry the thing.

```text
PROGRAM   owns observations. Computed from the data, never from a model.
LLM       may emit INFERRED and UNKNOWN only, each with a basis from a CLOSED
          vocabulary of basis KINDS.
HUMAN     owns CONFIRMED.
```

## The smuggling vectors this closes

Rejecting `{"status": "OBSERVED"}` is the easy half. The same semantic promotion
can be attempted sideways, and prose is very good at it:

```text
status: OBSERVED                          rejected -- not in the channel's enum
status: CONFIRMED                         rejected -- only a human confirms
basis: "directly established by the data"  rejected -- basis is a closed
                                           vocabulary of KINDS, not free text
confidence: "certain"                      stripped and logged
requires_confirmation: false               stripped and logged
a claim overwriting an OBSERVED one        impossible -- observations are added
                                           after, from the program's own output
```

The last three matter most. `INFERRED` stays inferred **even if the model writes
a 900-word defence of why it is definitely true**, because the authority a
downstream processor reads is the status field, and prose has no access to it.

Stripping rather than rejecting on unknown fields is deliberate: a legitimate
inference should not be lost because the model decorated it. What is removed is
recorded, so an attempt is visible rather than silently tolerated.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any

# The ONLY statuses this channel accepts. OBSERVED and CONFIRMED are absent by
# construction, not by policy.
LLM_STATUSES = ("INFERRED", "UNKNOWN")

# Basis is a closed vocabulary of KINDS. Free text here is exactly where
# "directly established by the data" would be smuggled in.
BASIS_KINDS = ("field_name", "collection_name", "value_pattern",
               "value_examples", "cross_source_similarity", "field_order")

# Fields a claim may carry. Anything else is stripped and logged.
ALLOWED_KEYS = ("claim", "status", "basis", "note")

REJECTION_CODES = (
    "status_not_in_channel",
    "missing_status",
    "inferred_without_basis",
    "basis_not_a_known_kind",
    "malformed_claim",
)


@dataclass
class Ingested:
    accepted: list[dict] = dc_field(default_factory=list)
    rejected: list[dict] = dc_field(default_factory=list)
    stripped: list[dict] = dc_field(default_factory=list)

    def as_dict(self) -> dict:
        return {"accepted": self.accepted, "rejected": self.rejected,
                "stripped": self.stripped}


def ingest(raw_claims: Any) -> Ingested:
    """Take whatever the interpretation processor emitted; keep only what the
    channel can carry."""
    out = Ingested()
    if not isinstance(raw_claims, list):
        out.rejected.append({"code": "malformed_claim",
                             "detail": f"expected a list, got {type(raw_claims).__name__}",
                             "raw": raw_claims})
        return out

    for raw in raw_claims:
        if not isinstance(raw, dict) or "claim" not in raw:
            out.rejected.append({"code": "malformed_claim", "raw": raw})
            continue

        status = raw.get("status")
        if status is None:
            out.rejected.append({"code": "missing_status", "raw": raw})
            continue
        if status not in LLM_STATUSES:
            # The headline case: OBSERVED and CONFIRMED are not in this channel.
            out.rejected.append({"code": "status_not_in_channel",
                                 "detail": f"{status!r} cannot be emitted by an "
                                           f"interpretation processor",
                                 "raw": raw})
            continue

        basis = raw.get("basis")
        if status == "INFERRED":
            kinds = basis if isinstance(basis, list) else ([basis] if basis else [])
            if not kinds:
                out.rejected.append({"code": "inferred_without_basis", "raw": raw})
                continue
            unknown = [k for k in kinds if k not in BASIS_KINDS]
            if unknown:
                out.rejected.append({
                    "code": "basis_not_a_known_kind",
                    "detail": f"{unknown} -- basis is a closed vocabulary of kinds, "
                              f"not free text",
                    "raw": raw})
                continue

        extra = sorted(k for k in raw if k not in ALLOWED_KEYS)
        if extra:
            out.stripped.append({"claim": raw.get("claim"), "removed": extra,
                                 "values": {k: raw[k] for k in extra}})

        out.accepted.append({k: raw[k] for k in ALLOWED_KEYS if k in raw})

    return out


def merge(observations: list[dict], ingested: Ingested) -> list[dict]:
    """Program observations FIRST, and unmodifiable.

    The interpretation channel produced `ingested.accepted`; it never had a way
    to express an OBSERVED claim, so nothing here can overwrite an observation.
    Merging in this order makes that structural rather than checked.
    """
    return [dict(o) for o in observations] + [dict(c) for c in ingested.accepted]


def confirm(report: list[dict], targets: list[dict], who: str = "human") -> list[dict]:
    """Human authority promotes INFERRED to CONFIRMED. One claim at a time.

    CONFIRMED is a fourth state, not a rewrite of INFERRED, so afterwards it is
    still visible that the claim began as a guess and who settled it.
    """
    out = [dict(c) for c in report]
    for target in targets:
        for claim in out:
            body = claim.get("claim", {})
            if (claim.get("status") == "INFERRED"
                    and all(body.get(k) == v for k, v in target.items())):
                claim["status"] = "CONFIRMED"
                claim["confirmed_by"] = who
                claim["was"] = "INFERRED"
    return out


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- the channel carries what it should ---------------------------------
    ok = ingest([
        {"claim": {"source": "reservations", "field": "date",
                   "meaning": "booking date"},
         "status": "INFERRED", "basis": ["field_name", "collection_name"]},
        {"claim": {"source": "reservations", "field": "tier", "meaning": "?"},
         "status": "UNKNOWN", "note": "values A/B/C carry no meaning"},
    ])
    check(len(ok.accepted) == 2 and not ok.rejected,
          f"legitimate interpretations must pass: {ok.as_dict()}")

    # --- SMUGGLING 1: the direct attempt ------------------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "OBSERVED"}])
    check(not r.accepted and r.rejected[0]["code"] == "status_not_in_channel",
          f"OBSERVED must be impossible in this channel: {r.as_dict()}")

    # --- SMUGGLING 2: self-confirmation -------------------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "CONFIRMED", "confirmed_by": "the model"}])
    check(not r.accepted and r.rejected[0]["code"] == "status_not_in_channel",
          f"a model may not confirm its own inference: {r.as_dict()}")

    # --- SMUGGLING 3: authority in the BASIS --------------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "INFERRED",
                 "basis": "directly established by the data"}])
    check(not r.accepted and r.rejected[0]["code"] == "basis_not_a_known_kind",
          f"basis is a closed vocabulary, so prose cannot enter it: {r.as_dict()}")

    # --- SMUGGLING 4: authority in adjacent fields --------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "INFERRED", "basis": ["field_name"],
                 "confidence": "certain", "requires_confirmation": False}])
    check(len(r.accepted) == 1, "a decorated but legitimate inference survives")
    check(r.accepted[0] == {"claim": {"source": "reservations", "field": "date"},
                            "status": "INFERRED", "basis": ["field_name"]},
          f"…with the smuggled authority REMOVED: {r.accepted[0]}")
    check(r.stripped and set(r.stripped[0]["removed"])
          == {"confidence", "requires_confirmation"},
          f"…and the attempt recorded rather than silently tolerated: {r.stripped}")

    # --- SMUGGLING 5: prose volume ------------------------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "INFERRED", "basis": ["field_name"],
                 "note": "This is certain. " * 200}])
    check(r.accepted[0]["status"] == "INFERRED",
          "INFERRED stays inferred no matter how long the argument is")

    # --- an inference with no basis at all ----------------------------------
    r = ingest([{"claim": {"source": "x", "field": "y"}, "status": "INFERRED"}])
    check(r.rejected[0]["code"] == "inferred_without_basis",
          f"an inference must say what it was inferred FROM: {r.as_dict()}")

    # --- observations cannot be overwritten ---------------------------------
    observations = [{"claim": {"source": "reservations", "field": "date",
                               "value_shape": "YYYY-MM-DD"},
                     "status": "OBSERVED", "basis": "measured_from_values"}]
    merged = merge(observations, ok)
    check(merged[0] == observations[0],
          "the program's observation must pass through untouched")
    check(sum(1 for c in merged if c["status"] == "OBSERVED") == 1,
          f"exactly one OBSERVED claim, and it is the program's: "
          f"{[c['status'] for c in merged]}")

    # --- confirmation is narrow ---------------------------------------------
    confirmed = confirm(merged, [{"source": "reservations", "field": "date"}])
    moved = [c for c in confirmed if c.get("status") == "CONFIRMED"]
    check(len(moved) == 1 and moved[0]["was"] == "INFERRED",
          f"exactly one claim moves, and it remembers it was a guess: {moved}")
    still = [c for c in confirmed if c["status"] == "INFERRED"]
    check(all(c.get("claim", {}).get("field") != "date" for c in still),
          "…and the confirmed one is no longer inferred")

    # --- every declared rejection code is reachable -------------------------
    seen = set()
    for payload in ([], [{"status": "INFERRED"}], [{"claim": {}, "status": "OBSERVED"}],
                    [{"claim": {}}], [{"claim": {}, "status": "INFERRED"}],
                    [{"claim": {}, "status": "INFERRED", "basis": "prose"}]):
        seen |= {x["code"] for x in ingest(payload).rejected}
    seen |= {x["code"] for x in ingest("not a list").rejected}
    untested = sorted(set(REJECTION_CODES) - seen)
    check(not untested, f"declared but unexercised rejection codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (legitimate interpretations pass / OBSERVED and "
          "CONFIRMED are impossible in this channel / prose cannot enter the basis "
          "/ confidence and requires_confirmation are stripped AND logged / "
          "INFERRED survives a 200-fold assertion of certainty / an inference "
          "without a basis is rejected / observations pass through untouched / "
          "confirmation moves exactly one claim and it remembers it was a guess / "
          f"all {len(REJECTION_CODES)} rejection codes exercised)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
