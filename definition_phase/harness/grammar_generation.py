#!/usr/bin/env python3
"""Grammar-derived generation — combinations implied by the language, not by me.

`parity_properties.py` says, in effect: *here are the variations I believe
matter.* This says something different and less flattering to its author:

    here are the combinations implied by the language we claim to support

That distinction is not academic. The seventh defect — the executor cannot run a
sheetset — was missed precisely because a sheetset is not an enum value anybody
remembered to put on a checklist. A generator that mechanically traverses
referent kinds, roles, transforms and multiplicities has no checklist to forget.

```text
recipe grammar
   |
enumerate legal and illegal compositions
   |
INDEPENDENT expectation  (from the contract, never from the system)
   |
system under test
```

**The independent expectation is the oracle**, and it is computed from the
executor contract plus the format's own pairing rules — not by asking the
validator. Where they disagree, exactly one of two things is true, and both are
worth knowing:

* the system is wrong, or
* this module's model of the language is wrong.

A disagreement is therefore reported as a **disagreement**, never silently
resolved in the system's favour. Resolving it in the system's favour would make
the generator agree with whatever the code does, which is the circularity the
whole exercise exists to avoid.

One axis is deliberately held constant: every generated recipe covers its sheet
completely (each column bound or excluded, `data_region: remainder`). Coverage is
already well understood and well tested; holding it fixed keeps the varying axis
— composition — legible.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentL" / "harness"))

from executor_contract import (  # noqa: E402
    MAX_UNPIVOTS_PER_SHEET, SUPPORTED_DERIVE_SOURCES, SUPPORTED_FIELD_ROLES,
    SUPPORTED_SHEET_REFS, SUPPORTED_SHEET_ROLES, SUPPORTED_TRANSFORM_OPS,
    pairing_reason,
)
from parity_properties import Case, Outcome, no_partial_honour, run_case  # noqa: E402
from recipe import (  # noqa: E402
    COLUMN_KINDS, FIELD_ROLES, SHEET_ROLES, TRANSFORM_OPS, TYPES,
)

# The canonical workbook. Composition varies; the data does not.
SHEETS = {
    "S": [["Tuote", "A", "B", "Note"],
          ["E1", 1, 2, "n1"],
          ["E2", 3, 4, "n2"]],
    "T": [["Tuote", "A", "B", "Note"],
          ["F1", 5, 6, "m1"],
          ["F2", 7, 8, "m2"]],
}

# Source referent shapes the grammar allows for a field, by kind.
SOURCES = {
    "namedcol": "sheet:S!@Tuote",
    "col": "sheet:S!B",
    "colrange": "sheet:S!B:C",
    "cell": "sheet:S!B1",
    "none": None,
}
COLUMN_BOUND = ("id", "measure", "period_measure")


@dataclass
class Expectation:
    accept: bool
    reasons: list


def expected(sheet_ref: str, sheet_role: str, field_role: str, source_kind: str,
             transform_op: Optional[str], n_unpivots: int) -> Expectation:
    """The oracle: what the LANGUAGE says must happen.

    Derived from the executor contract and the format's pairing rules. It never
    calls validate() or execute().
    """
    reasons: list[str] = []

    if sheet_role not in SHEET_ROLES:
        reasons.append(f"sheet role {sheet_role!r} is not a declared role")
    elif sheet_role not in SUPPORTED_SHEET_ROLES:
        reasons.append(f"sheet role {sheet_role!r} is declared but unsupported")

    # ORACLE CORRECTION (b): when the sheet role is not `data`, build_case emits
    # an entry with NO fields at all. Evaluating field rules against a field the
    # recipe does not contain is this module's own modelling defect -- it produced
    # 177 false disagreements in run 1, and 191 after correction (a) widened the
    # same hole. Zero of them ever occurred on a data sheet.
    if sheet_role != "data":
        return Expectation(accept=not reasons, reasons=reasons)

    # The sheetset restriction is on DATA entries specifically: the contract says
    # the executor cannot union a sheetset it must read. An IGNORED sheetset is
    # coherent -- its members are covered and never touched. Applying the rule
    # unconditionally was the same modelling error in a second place.
    if sheet_ref not in SUPPORTED_SHEET_REFS:
        reasons.append(f"{sheet_ref} data entry is not supported")

    if field_role not in FIELD_ROLES:
        reasons.append(f"field role {field_role!r} is not a declared role")
    elif field_role not in SUPPORTED_FIELD_ROLES:
        reasons.append(f"field role {field_role!r} is declared but unsupported")

    # pairing rules from recipe_format_v1 sec.2
    if field_role in COLUMN_BOUND and source_kind not in COLUMN_KINDS:
        reasons.append(f"{field_role} needs a column source, got {source_kind}")
    if field_role == "metadata" and source_kind != "cell":
        reasons.append(f"metadata needs a cell source, got {source_kind}")
    if field_role == "derived" and source_kind != "none":
        reasons.append("derived takes no source")
    if field_role != "derived" and source_kind == "none":
        reasons.append(f"{field_role} needs a source")

    if transform_op is not None:
        if transform_op not in TRANSFORM_OPS:
            reasons.append(f"transform {transform_op!r} is not declared")
        elif transform_op not in SUPPORTED_TRANSFORM_OPS:
            reasons.append(f"transform {transform_op!r} is declared but unsupported")
    # ORACLE CORRECTION (a): the language gained a role x transform pairing rule
    # when instance 8 was fixed. The oracle models the LANGUAGE, so it learns the
    # rule because the language has one -- not because the system disagreed.
    why = pairing_reason(field_role, transform_op)
    if why:
        reasons.append(why)
    if n_unpivots > MAX_UNPIVOTS_PER_SHEET:
        reasons.append(f"{n_unpivots} unpivots exceeds {MAX_UNPIVOTS_PER_SHEET}")

    return Expectation(accept=not reasons, reasons=reasons)


def build_case(sheet_ref: str, sheet_role: str, field_role: str, source_kind: str,
               transform_op: Optional[str], n_unpivots: int) -> Case:
    """Compose a recipe from the axes, keeping coverage complete throughout."""
    sheet_token = "sheetset:M" if sheet_ref == "sheetset" else "sheet:S"

    field: dict = {"target": "probe", "role": field_role, "type": "string"}
    src = SOURCES[source_kind]
    if src is not None:
        field["source"] = src
    if transform_op == "unpivot":
        field["transform"] = {"op": "unpivot", "var_target": "kk", "value_target": "probe"}
    elif transform_op == "derive":
        field["transform"] = {"op": "derive", "from": sorted(SUPPORTED_DERIVE_SOURCES)[0]}
    elif transform_op is not None:
        field["transform"] = {"op": transform_op}

    fields = [field]
    for extra in range(1, n_unpivots):
        fields.append({"target": f"extra{extra}", "source": "sheet:S!B:C",
                       "role": "period_measure", "type": "number",
                       "transform": {"op": "unpivot", "var_target": f"kk{extra}",
                                     "value_target": f"extra{extra}"}})

    # Coverage held constant: everything not bound above is excluded by name.
    bound = {"Tuote"} if source_kind == "namedcol" else set()
    if source_kind == "col":
        bound |= {"A"}
    if source_kind == "colrange" or n_unpivots > 1:
        bound |= {"A", "B"}
    exclude = [{"referent": f"sheet:S!@{c}", "reason": "coverage"}
               for c in ("Tuote", "A", "B", "Note") if c not in bound]

    entry = {"sheet": sheet_token, "role": sheet_role,
             "header_row": "sheet:S!1", "data_region": "remainder",
             "fields": fields, "exclude": exclude, "ambiguities": []}
    if sheet_ref == "sheetset":
        entry["layout_from"] = "sheet:S"
    if sheet_role != "data":
        entry = {"sheet": sheet_token, "role": sheet_role, "reason": "generated"}

    sheets = [entry]
    # every other workbook sheet must be classified, or coverage would vary
    for name in SHEETS:
        if f"sheet:{name}" != sheet_token and not (sheet_ref == "sheetset" and name == "S"):
            sheets.append({"sheet": f"sheet:{name}", "role": "ignore", "reason": "generated"})

    raw = {"recipe_version": 1, "recipe_id": "grammar", "workbook": {},
           "sheets": sheets, "applicability": None,
           "provenance": {"proposed_by": "grammar", "approved_by": "grammar",
                          "approved_recipe_sha256": None}}
    if sheet_ref == "sheetset":
        raw["sheetsets"] = {"M": ["S"]}

    return Case("grammar_derived", copy.deepcopy(SHEETS), raw,
                note=(f"ref={sheet_ref} sheet_role={sheet_role} field_role={field_role} "
                      f"source={source_kind} transform={transform_op} unpivots={n_unpivots}"))


def enumerate_cases():
    refs = ("sheet", "sheetset")
    sheet_roles = tuple(SHEET_ROLES)
    field_roles = tuple(FIELD_ROLES)
    source_kinds = tuple(SOURCES)
    transforms = (None,) + tuple(TRANSFORM_OPS)
    for ref, srole, frole, skind, top in itertools.product(
            refs, sheet_roles, field_roles, source_kinds, transforms):
        n_unpivots = 2 if (top == "unpivot" and frole == "period_measure"
                           and skind == "colrange") else 1
        yield ref, srole, frole, skind, top, 1
        if n_unpivots == 2:
            yield ref, srole, frole, skind, top, 2


def run_all() -> dict:
    agree = 0
    disagreements: list[dict] = []
    partial: list[dict] = []
    total = 0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for combo in enumerate_cases():
            total += 1
            exp = expected(*combo)
            case = build_case(*combo)
            out = run_case(case, tmp)

            accepted = out.executed
            if accepted == exp.accept:
                agree += 1
            else:
                disagreements.append({
                    "combo": case.note,
                    "language_says": "ACCEPT" if exp.accept else "REFUSE",
                    "language_reasons": exp.reasons,
                    "system_did": "EXECUTE" if accepted else "REFUSE",
                    "system_codes": sorted(out.codes),
                    "system_refusal": out.refused_reason,
                    "case": case.as_dict(),
                })
            why = no_partial_honour(case, out)
            if why:
                partial.append({"combo": case.note, "detail": why,
                                "case": case.as_dict()})

    return {"combinations": total, "agree": agree,
            "disagreements": disagreements, "partial_honour": partial,
            "n_disagreements": len(disagreements), "n_partial": len(partial)}


def _self_test() -> int:
    out = run_all()
    sys.stdout.write(
        f"  grammar-derived combinations : {out['combinations']}\n"
        f"  language and system agree    : {out['agree']}\n"
        f"  disagreements                : {out['n_disagreements']}\n"
        f"  partial honour               : {out['n_partial']}\n")

    if out["n_disagreements"] or out["n_partial"]:
        path = HERE.parent / "results" / "grammar_disagreements.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.stdout.write(f"\n  written verbatim to {path}\n")
        for d in out["disagreements"][:12]:
            sys.stdout.write(f"    {d['combo']}\n"
                             f"      language={d['language_says']} "
                             f"({'; '.join(d['language_reasons']) or 'all supported'})\n"
                             f"      system  ={d['system_did']} {d['system_codes']}\n")
        # A disagreement is a finding to investigate, not a pass/fail verdict:
        # either the system is wrong or this module's model of the language is.
        return 2
    sys.stdout.write("\nGRAMMAR PARITY: the language and the system agree on every "
                     "enumerated combination\n")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--json"]:
        print(json.dumps(run_all(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    raise SystemExit(_self_test())
