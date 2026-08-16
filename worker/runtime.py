#!/usr/bin/env python3
"""The committing runtime. Separate from preview, on purpose.

`builder.preview` executes and reports; it writes nothing and stays safe to run
in the modeller. This module is the other path: an established worker whose
model declares an effect, run for real.

Derived from `calendar_job/unattended.py`, which established the discipline —
the executor returns the state as it *would* stand and writes nothing, and
persisting is the RUNTIME's act, on acceptance only. That separation is why the
same executor can be previewed safely and trusted here.

## Three outcomes, not two

```text
REFUSED by policy          healthy run. No effect is attempted, because none
                           was earned. A worker declining a holiday booking is
                           working, not failing.
ACCEPTED, effect applied   healthy run. The world changed and it was VERIFIED
                           to have changed.
ACCEPTED, effect FAILED    exception. This is the case that must never be
                           filed as success: a decision was made, something
                           downstream is entitled to believe it, and the world
                           does not reflect it.
```

## Applied means verified, not attempted

A write that raised is obviously a failure. A write that returned quietly and
did not land is the dangerous one, so the effect is re-read from disk and
checked before it is called applied. `write_text` succeeding is not evidence.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "taskmodel"))
sys.path.insert(0, str(LAB / "reservation" / "harness"))

import reservation_model  # noqa: E402,F401  (registers the task type)
import task_model  # noqa: E402
from execute_reservation import execute  # noqa: E402
from reservation_model import source_field  # noqa: E402

# Effects this runtime knows how to apply. An effect a model declares and this
# runtime cannot honour stops the run rather than being ignored.
SUPPORTED_EFFECTS = ("append_to_reservations",)


class UnhonourableEffect(Exception):
    """The model declares an effect this runtime cannot apply."""


@dataclass
class ProductionRun:
    request: str
    decision: str                       # "accepted" | "refused"
    reason: Optional[str] = None        # the decisive refusal, when refused
    effect: Optional[str] = None        # what the model declared
    effect_applied: Optional[bool] = None   # None when none was attempted
    ok: bool = True
    error: Optional[str] = None
    evaluated: list = dc_field(default_factory=list)
    state_before: Optional[int] = None
    state_after: Optional[int] = None

    def as_dict(self) -> dict:
        return {"request": self.request, "decision": self.decision,
                "reason": self.reason, "effect": self.effect,
                "effect_applied": self.effect_applied, "ok": self.ok,
                "error": self.error, "evaluated": list(self.evaluated),
                "state_before": self.state_before, "state_after": self.state_after}


def declared_effect(model: dict) -> Optional[str]:
    return model.get("on_accept")


def _state_path(parsed, base: Path) -> Path:
    return base / parsed.sources["reservations"].path


def _read_state(parsed, base: Path) -> tuple[dict, list]:
    path = _state_path(parsed, base)
    state = json.loads(path.read_text(encoding="utf-8"))
    return state, list(state[parsed.sources["reservations"].collection])


def _apply_append(parsed, base: Path, request: str, decision) -> None:
    """Persist the acceptance, in the shape the source actually holds."""
    path = _state_path(parsed, base)
    state, _ = _read_state(parsed, base)
    collection = parsed.sources["reservations"].collection
    field = source_field(parsed, "reservations")
    if field is None:
        state[collection] = list(decision.reservations)
    else:
        state[collection] = list(state[collection]) + [{field: request}]
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _landed(parsed, base: Path, request: str) -> bool:
    """Re-read from disk. `write_text` returning is not evidence."""
    try:
        _, items = _read_state(parsed, base)
    except (OSError, json.JSONDecodeError, KeyError):
        return False
    field = source_field(parsed, "reservations")
    return any((item.get(field) if isinstance(item, dict) else item) == request
               for item in items)


def commit(model: dict, base: Path, request: str,
           apply: Optional[Callable] = None) -> ProductionRun:
    """Decide, and on acceptance apply the declared effect and verify it.

    `apply` exists ONLY so the self-test can substitute an effect that fails
    silently and prove the exception path is reachable. Nothing in production
    passes it.
    """
    parsed = task_model.parse(model)
    report = task_model.validate(parsed, base)
    if not report.valid:
        return ProductionRun(request=request, decision="refused", ok=False,
                             error="; ".join(str(p) for p in report.problems[:4]),
                             reason="INVALID_DEFINITION")

    effect = declared_effect(model)
    if effect is not None and effect not in SUPPORTED_EFFECTS:
        raise UnhonourableEffect(f"{effect!r} is declared but not implemented")

    _, before = _read_state(parsed, base)
    decision = execute(parsed, base, request)

    run = ProductionRun(request=request,
                        decision="accepted" if decision.accepted else "refused",
                        reason=decision.reason, effect=effect,
                        evaluated=list(decision.evaluated),
                        state_before=len(before))

    if not decision.accepted:
        # A policy refusal is a healthy run. No effect was earned, so none is
        # attempted, and `effect_applied` stays None rather than False -- "not
        # attempted" and "attempted and failed" are different facts.
        _, after = _read_state(parsed, base)
        run.state_after = len(after)
        return run

    if effect is None:
        run.state_after = run.state_before
        return run

    try:
        (apply or _apply_append)(parsed, base, request, decision)
    except Exception as exc:                       # noqa: BLE001 -- recorded
        run.error = f"{type(exc).__name__}: {exc}"

    run.effect_applied = _landed(parsed, base, request)
    _, after = _read_state(parsed, base)
    run.state_after = len(after)
    if not run.effect_applied:
        run.ok = False
        run.error = run.error or ("the effect did not land; the decision was "
                                  "accepted but the world does not reflect it")
    return run


def _self_test() -> int:
    import shutil
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    model = json.loads((LAB / "reservation" / "models" / "reservation_v1.json")
                       .read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        shutil.copytree(LAB / "reservation" / "fixtures", base / "fixtures")

        # --- a policy refusal is a HEALTHY run ----------------------------
        for request, expected in (("2026-12-25", "HOLIDAY"),
                                  ("2026-03-10", "ALREADY_RESERVED"),
                                  ("not-a-date", "INVALID_DATE")):
            run = commit(model, base, request)
            check(run.decision == "refused" and run.ok
                  and run.reason == expected and run.effect_applied is None,
                  f"a {expected} refusal must be a healthy run with no effect "
                  f"attempted: {run.as_dict()}")
            check(run.state_after == run.state_before,
                  f"…and must not change worker state: {run.as_dict()}")

        # --- an acceptance changes the world, verifiably -------------------
        run = commit(model, base, "2026-04-02")
        check(run.decision == "accepted" and run.ok
              and run.effect_applied is True,
              f"an acceptance must apply its effect: {run.as_dict()}")
        check(run.state_after == run.state_before + 1,
              f"…and worker state must actually grow: {run.as_dict()}")
        check(_landed(task_model.parse(model), base, "2026-04-02"),
              "…and the date must be readable back from disk")

        # --- and it is now already reserved --------------------------------
        again = commit(model, base, "2026-04-02")
        check(again.decision == "refused" and again.reason == "ALREADY_RESERVED"
              and again.ok,
              f"CANARY: the committed state must affect the NEXT decision: "
              f"{again.as_dict()}")

        # --- ACCEPTED + FAILED EFFECT is an exception ----------------------
        def silent_noop(parsed, base, request, decision):
            return None                       # writes nothing, raises nothing

        run = commit(model, base, "2026-05-05", apply=silent_noop)
        check(run.decision == "accepted" and run.effect_applied is False
              and not run.ok,
              f"CANARY: an accepted decision whose effect did not land must be "
              f"an EXCEPTION: {run.as_dict()}")
        check(run.state_after == run.state_before,
              f"…and state must be unchanged: {run.as_dict()}")
        check("does not reflect it" in (run.error or ""),
              f"…and must say what is wrong: {run.error}")

        # --- a write that RAISES is also an exception ----------------------
        def explode(parsed, base, request, decision):
            raise OSError("disk full")

        run = commit(model, base, "2026-05-06", apply=explode)
        check(not run.ok and run.effect_applied is False
              and "disk full" in (run.error or ""),
              f"CANARY: a raising effect must be an exception naming the cause: "
              f"{run.as_dict()}")

        # --- an unimplemented effect stops the run -------------------------
        # The task's OWN validator refuses `on_accept: email_the_customer`
        # before this runtime is reached, which is the better of the two
        # places for it to be caught. `UnhonourableEffect` remains for an
        # effect a validator accepts and this runtime cannot apply.
        odd = json.loads(json.dumps(model))
        odd["on_accept"] = "email_the_customer"
        try:
            stopped = commit(odd, base, "2026-06-01")
            check(not stopped.ok and stopped.reason == "INVALID_DEFINITION",
                  f"CANARY: an unimplemented effect must stop the run: "
                  f"{stopped.as_dict()}")
        except UnhonourableEffect:
            pass

        # --- the refusals never wrote anything -----------------------------
        _, final = _read_state(task_model.parse(model), base)
        check(len(final) == 4,
              f"exactly one acceptance landed across all of the above: {final}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (HOLIDAY, ALREADY_RESERVED and INVALID_DATE refusals "
          "are healthy runs that attempt no effect and change no state / an "
          "acceptance applies its effect, grows state and is readable back / the "
          "committed state changes the NEXT decision / an accepted decision "
          "whose effect silently did not land is an EXCEPTION with state "
          "unchanged / a raising effect is an exception naming the cause / an "
          "unimplemented effect stops the run / exactly one acceptance landed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)
