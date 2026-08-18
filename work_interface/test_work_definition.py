#!/usr/bin/env python3
"""Tests for the Work Definition v0 boundary.

Derived from the boundary, not from implementation convenience:

- Case A: the byte-preserved W0B Qwen artifact. MUST NOT pass cleanly into
  authoritative modelling. The validator names concrete reasons.
- Case B: the minimally corrected candidate. PASSES Work Definition validation
  only; carries no establishment/production authority; strips to a task_model
  that the existing floor accepts (the hand-off).
- Canaries: narrow falsification cases around the boundary, each mapping to a
  real W0B defect or a roadmap W2 case.

Run:  python work_interface/test_work_definition.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB / "taskmodel"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import task_model  # noqa: E402
import work_definition as wd  # noqa: E402

CASES = Path(__file__).resolve().parent / "cases"
EVIDENCE = Path(__file__).resolve().parent / "evidence"
FIXTXT = EVIDENCE / "W0B_fixtures"
FIXJSON = CASES / "fixtures"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case A -- the frozen W0B Qwen artifact (negative fixture)
# ---------------------------------------------------------------------------

def test_case_A_frozen_w0b_must_not_pass() -> None:
    """The byte-preserved W0B artifact must not pass cleanly, for named reasons.

    The honest result: the W0B artifact is prose-shaped, not Work-Definition-
    shaped. The validator refuses it at the structural gate with concrete named
    reasons -- it does NOT return 'generic invalid JSON' and it does NOT crash.
    The deeper W0B contradictions (conflicting basis, ReferenceNumber in output,
    load-bearing currency, the SupplierName normalization) are NOT derivable
    from this prose shape; they become detectable only in the v0 structural
    shape, which the canaries below demonstrate. That split is itself the
    finding the prompt asked for.
    """
    raw = load_json(EVIDENCE / "W0B_process_definition.original.json")
    r = wd.validate(raw, evidence_dir=FIXTXT)
    check(not r.valid, f"A must not validate: codes={sorted(r.codes())}")
    check(isinstance(r, task_model.Report), "A must produce a Report, not raise")

    codes = r.codes()
    # No structural body at all: the matching key and the comparison live only
    # in prose ("Join on InvoiceNumber...", "Compare Amount field..."). This is
    # the core boundary finding -- a key recoverable only from prose is not a
    # declared executable choice.
    check("match_key_not_declared" in codes,
          f"A should report match_key_not_declared (no structural body): {sorted(codes)}")
    # The W0B sources are a LIST, not a role-keyed object -- the malformed
    # external shape task_model learned to refuse by name (Experiment R).
    check("malformed_sources" in codes,
          f"A should report malformed_sources (sources is a list): {sorted(codes)}")
    # The artifact used a prose task label, not the registered family name.
    check("unknown_task_family" in codes,
          f"A should report unknown_task_family: {sorted(codes)}")
    check("unknown_work_definition_version" in codes,
          f"A should report unknown_work_definition_version: {sorted(codes)}")

    # And what the validator honestly CANNOT derive from this prose shape: it
    # must not pretend to have checked the deeper contradictions.
    check("conflicting_basis" not in codes and "output_field_not_declared" not in codes
          and "load_bearing_unresolved" not in codes,
          "A is prose-shaped; the validator must not claim to have detected "
          f"contradictions it cannot honestly derive: {sorted(codes)}")


# ---------------------------------------------------------------------------
# Case B -- the minimally corrected candidate
# ---------------------------------------------------------------------------

def test_case_B_corrected_passes_boundary_only() -> None:
    """B passes Work Definition validation; carries no establishment authority."""
    raw = load_json(CASES / "W0B_corrected.json")
    r = wd.validate(raw, evidence_dir=FIXTXT)
    check(r.valid, f"B must validate cleanly: {[str(p) for p in r.problems]}")

    # The strongest success state is NOT established. The artifact explicitly
    # requests no authority, and no override key is present.
    check(raw.get("requested_authority") is None,
          "B must not request authority")


def test_case_B_strips_into_existing_floor() -> None:
    """A valid Work Definition hands off to the EXISTING modelling/preview path.

    Stripped of its evidence/authority envelope, B becomes a task_model that
    passes the shared envelope AND the reconciliation body validator against
    materialized fixtures -- with no new authority and no second conversation.
    This is the roadmap W1 property: "Lab can translate/interpret it into its
    existing preview/establishment path."
    """
    raw = load_json(CASES / "W0B_corrected.json")
    r = wd.validate(raw, evidence_dir=FIXTXT)
    check(r.valid, f"B must validate before strip: {[str(p) for p in r.problems]}")

    model_dict = wd.to_task_model(raw)
    # The Work-Definition-only basis/confirmation tags are gone from the body.
    check("basis" not in model_dict.get("match_on", {}),
          "stripped model must not carry Work-Definition basis tags")

    model = task_model.parse(model_dict)
    # task_model validates the envelope + the reconciliation body against the
    # materialized JSON fixtures (field presence, classify/compare pairing,
    # closed vocabulary).
    report = task_model.validate(model, FIXJSON)
    check(report.valid,
          f"stripped B must pass the existing floor: {[str(p) for p in report.problems]}")

    # And the reconciliation body's own construct inventory reports the
    # genuine referents -- the same inventory the obligations manifest checks.
    try:
        from reconciliation.harness import reconciliation_model as recon  # noqa: E402
        inv = recon.constructs(model)
        check("match_binding" in inv and "compare:Amount" in inv
              and "difference_classification" in inv,
              f"stripped B must report genuine referents: {inv}")
    except Exception as exc:  # pragma: no cover
        check(False, f"reconciliation constructs() unavailable: {exc!r}")


# ---------------------------------------------------------------------------
# Canaries -- narrow falsification around the boundary
# ---------------------------------------------------------------------------

def _good() -> dict:
    return json.loads(json.dumps(load_json(CASES / "W0B_corrected.json")))


def test_canary_conflicting_basis() -> None:
    """Same semantic decision marked both observed and human_confirmed (W0B #1)."""
    a = _good()
    a["body"]["match_on"]["basis"] = ["observed", "human_confirmed"]
    check("conflicting_basis" in wd.validate(a, FIXTXT).codes(),
          "conflicting basis canary")


def test_canary_undeclared_field_in_output() -> None:
    """Undeclared matching field appears in executable output semantics (W0B #2)."""
    a = _good()
    a["output"] = {"reports_fields": ["InvoiceNumber", "ReferenceNumber"],
                   "context_fields": []}
    check("output_field_not_declared" in wd.validate(a, FIXTXT).codes(),
          "undeclared output field canary (ReferenceNumber)")


def test_canary_compare_field_only_in_prose() -> None:
    """Classify reports differences but no compare is declared (W0B #3 form)."""
    a = _good()
    del a["body"]["compare"]
    check("compare_not_declared" in wd.validate(a, FIXTXT).codes(),
          "compare-only-in-prose canary")


def test_canary_load_bearing_unresolved() -> None:
    """A load-bearing unresolved question blocks entry to modelling (W0B #3)."""
    a = _good()
    a["open_questions"] = [{"id": "Q_currency", "question": "currency part of rule?",
                            "load_bearing": True, "status": "unresolved"}]
    check("load_bearing_unresolved" in wd.validate(a, FIXTXT).codes(),
          "load-bearing unresolved canary")


def test_canary_unknown_source_role() -> None:
    """Unknown source role / missing required source information."""
    a = _good()
    a["body"]["left"] = "not_a_real_role"
    check("unknown_source" in wd.validate(a, FIXTXT).codes(),
          "unknown source role canary")


def test_canary_effect_authority_requested() -> None:
    """Work requests automatic delivery/effect but has no effect authority (W2-B)."""
    a = _good()
    a["requested_authority"] = "effect"
    check("authority_requested" in wd.validate(a, FIXTXT).codes(),
          "effect authority requested canary")


def test_canary_claims_approved() -> None:
    """Artifact claims it is 'approved'/'established' (W2-C)."""
    a = _good()
    a["established"] = True
    check("prose_override_attempt" in wd.validate(a, FIXTXT).codes(),
          "self-approval canary")


def test_canary_prose_override() -> None:
    """Confident prose attempts to override a deterministic failure (W2-E)."""
    a = _good()
    a["validation_override"] = True
    check("prose_override_attempt" in wd.validate(a, FIXTXT).codes(),
          "override canary")


def test_canary_malformed_external_shape_refuses_not_crashes() -> None:
    """Malformed external producer shape must refuse, not crash (task_model R)."""
    for bad in ("a string", [1, 2, 3], 42, None, {"sources": "x"}):
        r = wd.validate(bad, FIXTXT)
        check(not r.valid, f"malformed {bad!r} must not validate")
        check(isinstance(r, task_model.Report), f"malformed {bad!r} must return a Report")
    # sources as a list (the shape an outside producer most often reaches for)
    a = _good()
    a["sources"] = [{"fixture": "x"}]
    check("malformed_sources" in wd.validate(a, FIXTXT).codes(),
          "sources-as-list canary")


def test_canary_body_completeness_vs_floor() -> None:
    """A Work Definition that passes the gate must be safe to enter the existing
    path -- so the gate enforces the same body completeness the floor does.
    Missing output_order or on_non_numeric (when a numeric compare is declared)
    must fail at the gate, not slip through to the floor."""
    a = _good()
    del a["body"]["output_order"]
    check("unknown_output_order" in wd.validate(a, FIXTXT).codes(),
          "missing output_order canary")
    a = _good()
    del a["body"]["on_non_numeric"]
    check("missing_on_non_numeric" in wd.validate(a, FIXTXT).codes(),
          "missing on_non_numeric (numeric compare declared) canary")


def test_canary_validated_but_authority_field_claims() -> None:
    """The W0B artifact says requested_authority=null AND 'authority_status' prose.
    The validator must ignore the prose self-claim and verify structurally:
    a clean B passes despite carrying that self-description, but an explicit
    requested_authority fails."""
    a = _good()
    a["requested_delivery"]["authority_status"] = "non-authoritative proposal"
    check(wd.validate(a, FIXTXT).valid,
          "B with a prose self-claim must still pass (prose is not authority)")
    a["requested_authority"] = "established"
    check("authority_requested" in wd.validate(a, FIXTXT).codes(),
          "but requested_authority=established must fail")


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

TESTS = [name for name in globals() if name.startswith("test_")]


def _self_test() -> int:
    for name in sorted(TESTS):
        globals()[name]()
    if failures:
        sys.stderr.write("WORK DEFINITION TESTS FAILED:\n  " +
                         "\n  ".join(failures) + "\n")
        return 1
    print(f"WORK DEFINITION TESTS PASSED ({len(TESTS)} tests): "
          f"A refuses with named reasons / B passes & strips into the existing "
          f"floor / all boundary canaries fire / malformed shapes refuse not crash")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)