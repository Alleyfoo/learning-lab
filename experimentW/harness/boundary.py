#!/usr/bin/env python3
"""W's boundary: V's, plus every uncertainty must have an address.

V established that the interpretation channel cannot mint an observation, and
found the hole in the same breath: all 23 of its `UNKNOWN` claims carried a
free-text question and no subject.

```text
OBSERVED   machine-owned   structured   addressable
INFERRED   LLM-owned       structured   addressable
UNKNOWN    LLM-owned       free text    NOT addressable      <- V's bug
```

So when a probe said *"tier is probably a service level, but I don't know what
tier actually means"*, the first half attached to `reservations.tier` and the
second half floated. A downstream processor could not tell the two halves were
about the same field, which defeats the point of carrying status forward at all.

## The change, and nothing else

`UNKNOWN` becomes structurally parallel to `INFERRED`: an explicit referent.

```json
{"claim": {"source": "reservations", "field": "tier",
           "question": "What does this field represent in this domain?"},
 "status": "UNKNOWN"}
```

`field` may be `null` for a collection-level question, and `source` may be a
list where a question genuinely spans sources — but the referent is always
present and always machine-addressable. Absent or null `source` is a rejection.

V's harness is not edited; it belongs to a completed run. The unchanged parts are
imported from it so the delta stays visible.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent


def _load(name: str, path: Path):
    """Load a sibling experiment's module by path.

    V's module is also called `boundary`, and W's harness directory is on
    sys.path, so a plain import resolves to this file.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v = _load("_v_boundary", LAB / "experimentV" / "harness" / "boundary.py")

LLM_STATUSES = v.LLM_STATUSES
BASIS_KINDS = v.BASIS_KINDS
ALLOWED_KEYS = v.ALLOWED_KEYS
Ingested = v.Ingested
merge = v.merge

REJECTION_CODES = v.REJECTION_CODES + ("unknown_without_referent",)


def referent(claim: dict) -> tuple | None:
    """The machine-addressable subject of a claim, or None if it has none."""
    body = claim.get("claim")
    if not isinstance(body, dict):
        return None
    source = body.get("source")
    if isinstance(source, list):
        source = tuple(sorted(str(s) for s in source)) if source else None
    elif source is not None:
        source = str(source)
    if not source:
        return None
    return (source, body.get("field"))


def ingest(raw_claims) -> Ingested:
    """V's ingest, plus: an UNKNOWN with no referent does not enter the report."""
    out = v.ingest(raw_claims)
    kept = []
    for claim in out.accepted:
        if claim.get("status") == "UNKNOWN" and referent(claim) is None:
            out.rejected.append({
                "code": "unknown_without_referent",
                "detail": "an uncertainty with no subject cannot be associated "
                          "with the thing it is about",
                "raw": claim})
            continue
        kept.append(claim)
    out.accepted = kept
    return out


def confirm(report: list[dict], referents, who: str = "human") -> list[dict]:
    """Settle claims by REFERENT, whatever their status.

    V confirmed only INFERRED claims. A modeller may equally block on an
    UNKNOWN -- a human answering "what does tier mean?" settles it, and the
    result is a claim that is no longer a guess. Both promote to CONFIRMED and
    both remember what they were.
    """
    wanted = {(tuple(sorted(map(str, r["source"]))) if isinstance(r.get("source"), list)
               else str(r.get("source")), r.get("field")) for r in referents}
    out = []
    for claim in report:
        claim = dict(claim)
        if claim.get("status") in LLM_STATUSES and referent(claim) in wanted:
            claim["was"] = claim["status"]
            claim["status"] = "CONFIRMED"
            claim["confirmed_by"] = who
        out.append(claim)
    return out


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- V's guarantees still hold ------------------------------------------
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "OBSERVED"}])
    check(not r.accepted and r.rejected[0]["code"] == "status_not_in_channel",
          f"V's enum must still hold: {r.as_dict()}")
    r = ingest([{"claim": {"source": "reservations", "field": "date"},
                 "status": "INFERRED", "basis": ["field_name"],
                 "confidence": "certain", "requires_confirmation": False}])
    check(len(r.accepted) == 1 and r.stripped, "V's stripping must still hold")

    # --- THE FIX: V's actual output shape is now rejected -------------------
    # Verbatim from experimentV/results/V1_probe1_raw.txt.
    floating = ingest([{"claim": {"question": "What does 'tier' actually "
                                              "represent in this domain?"},
                        "status": "UNKNOWN",
                        "note": "Field names and types do not reveal whether "
                                "this is a hotel room class, a customer support "
                                "priority level, or another type of category."}])
    check(not floating.accepted
          and floating.rejected[0]["code"] == "unknown_without_referent",
          f"V's own unaddressable unknown must now be refused: {floating.as_dict()}")

    # --- an addressed unknown passes ----------------------------------------
    addressed = ingest([{"claim": {"source": "reservations", "field": "tier",
                                   "question": "What does this field represent?"},
                         "status": "UNKNOWN"}])
    check(len(addressed.accepted) == 1
          and referent(addressed.accepted[0]) == ("reservations", "tier"),
          f"an addressed unknown must pass and be addressable: {addressed.as_dict()}")

    # --- collection-level: field null is explicit, not missing --------------
    collection = ingest([{"claim": {"source": "holidays", "field": None,
                                    "question": "Do these dates prohibit booking?"},
                          "status": "UNKNOWN"}])
    check(len(collection.accepted) == 1
          and referent(collection.accepted[0]) == ("holidays", None),
          f"a collection-level unknown is addressable: {collection.as_dict()}")

    # --- a genuinely cross-source question ----------------------------------
    spanning = ingest([{"claim": {"source": ["holidays", "reservations"],
                                  "field": None,
                                  "question": "May a reservation fall on a holiday?"},
                        "status": "UNKNOWN"}])
    check(len(spanning.accepted) == 1
          and referent(spanning.accepted[0]) == (("holidays", "reservations"), None),
          f"a question spanning sources keeps both referents: {spanning.as_dict()}")

    # --- CANARY: an empty source is not a referent --------------------------
    for bad in ({"source": "", "question": "?"}, {"source": None, "question": "?"},
                {"source": [], "question": "?"}, {"question": "?"}):
        r = ingest([{"claim": bad, "status": "UNKNOWN"}])
        check(not r.accepted and r.rejected[0]["code"] == "unknown_without_referent",
              f"CANARY: {bad} must not count as a referent: {r.as_dict()}")

    # --- the property W exists to provide -----------------------------------
    both = ingest([
        {"claim": {"source": "reservations", "field": "tier",
                   "meaning": "a service or priority tier"},
         "status": "INFERRED", "basis": ["field_name"]},
        {"claim": {"source": "reservations", "field": "tier",
                   "question": "What does a tier actually represent here?"},
         "status": "UNKNOWN"}])
    refs = [referent(c) for c in both.accepted]
    check(len(both.accepted) == 2 and refs[0] == refs[1] == ("reservations", "tier"),
          f"the candidate meaning and its uncertainty share one address: {refs}")

    # --- confirming an UNKNOWN, which V could not do ------------------------
    report = merge([{"claim": {"source": "reservations", "field": "tier"},
                     "status": "OBSERVED", "basis": "measured_from_values"}], both)
    after = confirm(report, [{"source": "reservations", "field": "tier"}])
    moved = [c for c in after if c.get("status") == "CONFIRMED"]
    check(len(moved) == 2 and {m["was"] for m in moved} == {"INFERRED", "UNKNOWN"},
          f"one human answer settles both claims at that address: {moved}")
    check([c for c in after if c["status"] == "OBSERVED"] == [report[0]],
          "…and the program's observation is untouched")

    # --- CANARY: confirmation does not spill to other referents -------------
    after = confirm(report, [{"source": "reservations", "field": "date"}])
    check(not [c for c in after if c.get("status") == "CONFIRMED"],
          "CANARY: confirming a DIFFERENT field must settle nothing")

    # --- every declared rejection code reachable ----------------------------
    seen = set()
    for payload in ([], [{"status": "INFERRED"}], [{"claim": {}, "status": "OBSERVED"}],
                    [{"claim": {}}], [{"claim": {"source": "x"}, "status": "INFERRED"}],
                    [{"claim": {"source": "x"}, "status": "INFERRED", "basis": "prose"}],
                    [{"claim": {"question": "?"}, "status": "UNKNOWN"}]):
        seen |= {x["code"] for x in ingest(payload).rejected}
    seen |= {x["code"] for x in ingest("not a list").rejected}
    untested = sorted(set(REJECTION_CODES) - seen)
    check(not untested, f"declared but unexercised rejection codes: {untested}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (V's enum and stripping still hold / V's own "
          "unaddressable unknown is now refused / an addressed unknown passes and "
          "is addressable / field null is explicit for collection-level / a "
          "cross-source question keeps both referents / empty, null, [] and "
          "missing source are all refused / a meaning and its uncertainty share "
          "one address / one human answer settles both, each remembering what it "
          "was / confirming a different field settles nothing / all "
          f"{len(REJECTION_CODES)} rejection codes exercised)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
