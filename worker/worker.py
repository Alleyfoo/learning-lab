#!/usr/bin/env python3
"""An established worker: a pinned model, a fixed executor, and no LLM.

```text
ESTABLISH   a model is agreed once and pinned by digest
RUN         validate against the declared world, then execute. No LLM, no human,
            no per-run approval -- the same rule calendar_job/unattended.py runs
            under
DETECT      a run whose declared world no longer exists does not degrade into a
            best guess. It stops and produces an exception PACKET
```

Nothing here investigates anything. The packet is assembled from measurements
and the model's own declarations, so the expensive stage can stay asleep until
there is something specific to look at.

## Versions do not reach backwards

`v2` says nothing about the runs `v1` performed. This is the rule
`scripts/agent_binding.py` fixed for agent definitions -- *adopting now
certifies nothing about a past run* -- and it applies unchanged here: a worker
promoted after 437 successful runs has 437 runs of v1 history and zero of v2.
`promote()` therefore starts a fresh record and leaves the old one alone.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "modeller"))
sys.path.insert(0, str(LAB / "inspector"))

import builder  # noqa: E402
import observe  # noqa: E402

TASK = "enrichment"


def digest(model: dict) -> str:
    return hashlib.sha256(builder.canonical(model).encode("utf-8")).hexdigest()


@dataclass
class Established:
    """A worker as agreed. The model is authority; this object cannot edit it."""
    name: str
    version: int
    model: dict
    base: Path
    established: str                      # ISO date, informational
    supersedes: Optional[int] = None
    runs: list[dict] = dc_field(default_factory=list)

    @property
    def model_digest(self) -> str:
        return digest(self.model)

    def as_dict(self) -> dict:
        return {"worker": self.name, "version": self.version,
                "model_digest": self.model_digest, "established": self.established,
                "supersedes": self.supersedes, "runs": len(self.runs),
                "successes": sum(1 for r in self.runs if r["ok"]),
                "exceptions": sum(1 for r in self.runs if not r["ok"])}


@dataclass
class Outcome:
    ok: bool
    rows: list = dc_field(default_factory=list)
    columns: list = dc_field(default_factory=list)
    refused: list = dc_field(default_factory=list)
    packet: Optional[dict] = None


# ---------------------------------------------------------------------------
# what the model DECLARES it needs -- read off the model, not guessed
# ---------------------------------------------------------------------------

def declared_fields(model: dict) -> dict[str, list[str]]:
    used: dict[str, set] = {}

    def add(source, field):
        if source and field:
            used.setdefault(str(source), set()).add(str(field))

    lookup = model.get("lookup") or {}
    add(model.get("driving_source"), lookup.get("match_left"))
    add(lookup.get("into"), lookup.get("match_right"))
    for out in model.get("outputs") or []:
        if "compute" in out:
            for side in ("left", "right"):
                ref = (out["compute"] or {}).get(side) or {}
                add(ref.get("from"), ref.get("field"))
        else:
            add(out.get("from"), out.get("field"))
    return {k: sorted(v) for k, v in sorted(used.items())}


def observed_fields(base: Path, model: dict) -> dict[str, list[str]]:
    """What the declared source files actually contain right now."""
    out: dict[str, list[str]] = {}
    for name, spec in (model.get("sources") or {}).items():
        path = base / spec.get("path", "")
        if not path.is_file():
            out[name] = []
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get(spec.get("collection"))
        out[name] = sorted(rows[0]) if isinstance(rows, list) and rows else []
    return out


def exception_packet(est: Established, problems: list[str]) -> dict:
    """Everything an investigator needs, measured -- and nothing interpreted."""
    expected = declared_fields(est.model)
    present = observed_fields(est.base, est.model)
    directory = {(est.base / spec["path"]).parent
                 for spec in (est.model.get("sources") or {}).values()}
    measured = []
    for folder in sorted(directory):
        if folder.is_dir():
            measured = [c["claim"]["candidate_relationship"]
                        for c in observe.observed_claims(folder)
                        if "candidate_relationship" in c["claim"]]
            break

    difference = {}
    for source, wanted in expected.items():
        have = set(present.get(source, []))
        gone = [f for f in wanted if f not in have]
        if gone:
            difference[source] = {
                "declared_but_absent": gone,
                "present_and_undeclared": sorted(have - set(wanted))}

    return {"worker": est.name, "version": est.version,
            "model_digest": est.model_digest,
            "failure": problems,
            "expected_fields": expected,
            "observed_fields": present,
            "difference": difference,
            "measured_relationships": measured,
            "history": {"runs": len(est.runs),
                        "successes": sum(1 for r in est.runs if r["ok"])}}


def run(est: Established, established_digest: Optional[str] = None) -> Outcome:
    """One unattended run. No LLM is reachable from here.

    A pinned digest that no longer matches stops the run rather than executing
    an edited authority -- and that is a refusal, not an approval step.
    """
    if established_digest and established_digest != est.model_digest:
        packet = {"worker": est.name, "version": est.version,
                  "failure": [f"model digest is {est.model_digest}, "
                              f"pinned as {established_digest}"],
                  "expected_fields": declared_fields(est.model),
                  "observed_fields": {}, "difference": {},
                  "measured_relationships": [], "history": {}}
        est.runs.append({"ok": False, "reason": "definition_changed"})
        return Outcome(ok=False, packet=packet)

    preview = builder.preview(est.model.get("task") or TASK, est.model, base=est.base)
    if not preview.ok:
        est.runs.append({"ok": False, "reason": "contract_failed"})
        return Outcome(ok=False,
                       packet=exception_packet(est, list(preview.problems)))
    est.runs.append({"ok": True, "rows": len(preview.rows)})
    return Outcome(ok=True, rows=preview.rows, columns=preview.columns,
                   refused=preview.refused)


def promote(est: Established, new_model: dict, when: str) -> Established:
    """A new version. It inherits authority, never history."""
    return Established(name=est.name, version=est.version + 1,
                       model=json.loads(json.dumps(new_model)), base=est.base,
                       established=when, supersedes=est.version, runs=[])


def apply_replacements(model: dict, replacements: list[dict]) -> dict:
    """Rename a field everywhere the model declares it, and nowhere else.

    An investigator proposes REPLACEMENTS, never a rewritten model. Applying
    them mechanically is what keeps a v2 to the change that was justified: a
    proposal cannot quietly alter a policy or drop a column on the way past.
    """
    out = json.loads(json.dumps(model))
    for rep in replacements:
        source, before, after = rep.get("source"), rep.get("from"), rep.get("to")
        if not all((source, before, after)):
            continue
        lookup = out.get("lookup") or {}
        if out.get("driving_source") == source and lookup.get("match_left") == before:
            lookup["match_left"] = after
        if lookup.get("into") == source and lookup.get("match_right") == before:
            lookup["match_right"] = after
        for spec in out.get("outputs") or []:
            if "compute" in spec:
                for side in ("left", "right"):
                    ref = (spec["compute"] or {}).get(side) or {}
                    if ref.get("from") == source and ref.get("field") == before:
                        ref["field"] = after
            elif spec.get("from") == source and spec.get("field") == before:
                spec["field"] = after
                if spec.get("target") == before:
                    spec["target"] = after
    return out


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    base = LAB / "data"
    model = json.loads((HERE / "established" / "timesheet-cost-v1.json")
                       .read_text(encoding="utf-8"))
    est = Established("timesheet-cost", 1, model, base, "2026-08-16")

    # --- it runs, unattended -----------------------------------------------
    outcome = run(est, est.model_digest)
    check(outcome.ok and len(outcome.rows) == 4 and not outcome.refused,
          f"the established worker must run: {outcome.packet or outcome.rows}")
    check([r[-1] for r in outcome.rows]
          == ["318.750", "1520.00", "633.9375", "1615.00"],
          f"…and produce the agreed numbers: {[r[-1] for r in outcome.rows]}")

    # --- a pinned digest that moved stops the run --------------------------
    stopped = run(est, "0" * 64)
    check(not stopped.ok and "pinned" in stopped.packet["failure"][0],
          f"CANARY: an edited authority must not execute: {stopped.packet}")

    # --- declared fields are read off the model ----------------------------
    declared = declared_fields(model)
    check(declared["staff"] == ["hourly_rate", "name", "staff_id"]
          and "staff_ref" in declared["timesheets"],
          f"declared fields must come from the model: {declared}")

    # --- DETECT: the world changed -----------------------------------------
    moved = Established("timesheet-cost", 1, model,
                        LAB / "experimentZ" / "fixtures" / "A", "2026-08-16")
    broken = run(moved)
    check(not broken.ok, "a worker whose join target vanished must refuse")
    packet = broken.packet
    check(any("field_not_in_source" in p for p in packet["failure"]),
          f"the failure must name the contract breach: {packet['failure']}")
    check(packet["difference"]["staff"]["declared_but_absent"] == ["staff_id"],
          f"the packet must say what vanished: {packet['difference']}")
    check("employee_id" in packet["difference"]["staff"]["present_and_undeclared"],
          f"…and what appeared: {packet['difference']}")
    rel = [r for r in packet["measured_relationships"]
           if r["left"] == "timesheets.staff_ref"]
    check(any(r["right"] == "staff.employee_id" and r["left_coverage"] == "4/4"
              and r["right_unique"] for r in rel),
          f"…and carry the measurements, uninterpreted: {rel}")
    check(not any("employee_id" in json.dumps(v) and "meaning" in json.dumps(v)
                  for v in packet.values()),
          "the packet interprets nothing")

    # --- replacements are applied mechanically -----------------------------
    v2model = apply_replacements(model, [{"source": "staff", "from": "staff_id",
                                          "to": "employee_id"}])
    check((v2model["lookup"]["match_right"] == "employee_id"
           and model["lookup"]["match_right"] == "staff_id"),
          "a replacement must not mutate the established model")
    check(json.dumps(v2model["outputs"]) == json.dumps(model["outputs"]),
          f"CANARY: nothing outside the named field may change: "
          f"{v2model['outputs']}")
    fixed = run(Established("timesheet-cost", 2, v2model,
                            LAB / "experimentZ" / "fixtures" / "A", "2026-08-16"))
    check(fixed.ok and [r[-1] for r in fixed.rows]
          == ["318.750", "1520.00", "633.9375", "1615.00"],
          f"…and v2 must reproduce v1's numbers on the changed world: "
          f"{fixed.packet or [r[-1] for r in fixed.rows]}")

    # --- v2 inherits authority, never history ------------------------------
    before = len(est.runs)
    v2 = promote(est, v2model, "2026-08-16")
    check(v2.version == 2 and v2.supersedes == 1 and v2.runs == [],
          f"a new version starts with no run history: {v2.as_dict()}")
    check(len(est.runs) == before and est.version == 1,
          "CANARY: promoting must not touch v1's record")
    check(v2.model_digest != est.model_digest,
          "a changed model must have a different digest")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (the established worker runs unattended and produces "
          "the agreed numbers / an edited authority does not execute / declared "
          "fields are read off the model / a vanished join target refuses and "
          "produces a packet naming what went and what appeared, with "
          "measurements and no interpretation / replacements apply mechanically "
          "without mutating v1 or touching anything unnamed / v2 reproduces v1's "
          "numbers on the changed world / v2 inherits authority and no history)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
