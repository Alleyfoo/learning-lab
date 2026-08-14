#!/usr/bin/env python3
"""Recipe format v1 — model, loader, legacy adapter.

Spec: `design/recipe_format_v1.md`. Validation lives in `validate_recipe.py`;
this module only models and loads, so a malformed recipe still becomes an object
and is reported on rather than crashing the loader.

The recipe is the definition phase's output: the executable interpretation of an
unknown workbook. Every address in it is a frozen-grammar referent string
(`referent-grammar-v1`), and the grammar is not extended to carry meaning — a
referent says WHERE, the recipe says WHAT IT IS.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

RECIPE_VERSIONS = (1,)
SHEET_ROLES = ("data", "ignore", "metadata")
FIELD_ROLES = ("id", "measure", "period_measure", "metadata", "derived")
TRANSFORM_OPS = ("unpivot", "coerce", "derive")
TYPES = ("string", "number", "date", "boolean")

# v1.1 -- relative row anchoring (Experiment K's C3 finding).
#
# `data_region` may be the literal REMAINDER instead of a row referent: the data
# is every row not claimed by the header or by an exclusion. The region then
# grows with the file instead of being pinned to the row count of the day the
# recipe was written.
#
# Exclusions may carry a RULE instead of a referent, for things anchored to the
# bottom of a sheet (a grand-total row moves every month; a preamble does not).
# The principle: anchor positionally from the stable end, by rule from the
# unstable one.
#
# `label_in` takes a LITERAL value list -- no patterns, no regex. That is a
# security choice, not a simplification: a rule is a predicate over untrusted
# cell content, and a pattern language would be an expression language creeping
# in through the back door. Literal lists stay inspectable by the human who
# approves them.
REMAINDER = "remainder"
EXCLUDE_RULE_OPS = ("label_in", "row_blank")

# v1.2 -- row-shape expectation (Experiment K, C13). Declare what a data row
# LOOKS LIKE, so a row that does not qualify escalates instead of being
# absorbed by a `remainder` region.
#
# Both constraints are TYPE-LEVEL: they ask what KIND of value sits in a cell,
# never what it says. No patterns, no regex, no value lists -- a predicate
# language over untrusted cell content is an expression language arriving
# through the back door.
#
# This is the first check that reads data-row CONTENT. It is bounded on
# purpose: the validator learns only blank/numeric/neither per cell, so a
# hostile workbook can force an ESCALATION and nothing else.
ROW_SHAPE_CONSTRAINTS = ("require_non_blank", "require_numeric")

# v1.3 -- reconciliation (Experiment K, the C8 attack).
#
# A RELATIONAL check, not a content predicate: the file's own declared total
# must equal the sum of the rows the recipe treats as data. It catches a
# subtotal row without knowing what its label MEANS -- the evidence is
# arithmetic the provider put in the file.
#
# Narrower than what already exists: label_in compares strings,
# reconciliation only adds numbers.
RECONCILE_TOLERANCE = 1e-9

# Which referent kinds a field role may bind (spec sec.2).
COLUMN_KINDS = ("col", "colrange", "namedcol")
COLUMN_BOUND_ROLES = ("id", "measure", "period_measure")


@dataclass(frozen=True)
class Transform:
    op: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(raw: Mapping[str, Any]) -> "Transform":
        return Transform(op=str(raw.get("op", "")),
                         params={k: v for k, v in raw.items() if k != "op"})


@dataclass(frozen=True)
class Field:
    target: str
    role: str
    type: Optional[str] = None
    source: Optional[str] = None            # referent string; None for 'derived'
    transform: Optional[Transform] = None


@dataclass(frozen=True)
class ExcludeRule:
    op: str
    column: Optional[str] = None            # referent string (a column)
    values: tuple[str, ...] = ()

    @staticmethod
    def from_json(raw: Mapping[str, Any]) -> "ExcludeRule":
        return ExcludeRule(op=str(raw.get("op", "")),
                           column=raw.get("column"),
                           values=tuple(str(v) for v in raw.get("values", ()) or ()))


@dataclass(frozen=True)
class Exclusion:
    referent: Optional[str] = None          # a row/column address...
    rule: Optional[ExcludeRule] = None      # ...XOR a content rule (v1.1)
    reason: Optional[str] = None            # MANDATORY; absence is a problem


@dataclass(frozen=True)
class Ambiguity:
    referent: str
    question: str
    blocking: bool = False


@dataclass(frozen=True)
class RowShape:
    require_non_blank: tuple[str, ...] = ()   # column referents
    require_numeric: tuple[str, ...] = ()

    @staticmethod
    def from_json(raw: Mapping[str, Any]) -> "RowShape":
        return RowShape(
            require_non_blank=tuple(str(v) for v in raw.get("require_non_blank", ()) or ()),
            require_numeric=tuple(str(v) for v in raw.get("require_numeric", ()) or ()),
        )

    def columns(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            [("require_non_blank", c) for c in self.require_non_blank]
            + [("require_numeric", c) for c in self.require_numeric])


@dataclass(frozen=True)
class Reconcile:
    total_row: Optional[ExcludeRule] = None   # located the same way an exclusion is
    columns: Optional[str] = None             # column referent to sum
    reason: Optional[str] = None

    @staticmethod
    def from_json(raw: Mapping[str, Any]) -> "Reconcile":
        tr = raw.get("total_row")
        return Reconcile(
            total_row=ExcludeRule.from_json(tr) if isinstance(tr, Mapping) else None,
            columns=raw.get("columns"), reason=raw.get("reason"))


@dataclass(frozen=True)
class SheetEntry:
    sheet: str                              # 'sheet:X' or 'sheetset:Y'
    role: str
    reason: Optional[str] = None            # why it is ignored
    layout_from: Optional[str] = None       # prototype sheet for a sheetset
    header_row: Optional[str] = None
    data_region: Optional[str] = None
    fields: tuple[Field, ...] = ()
    exclude: tuple[Exclusion, ...] = ()
    ambiguities: tuple[Ambiguity, ...] = ()
    data_row_shape: Optional[RowShape] = None
    reconcile: tuple[Reconcile, ...] = ()

    @property
    def is_sheetset(self) -> bool:
        return self.sheet.strip().startswith("sheetset:")


@dataclass(frozen=True)
class Recipe:
    recipe_version: int
    recipe_id: str
    workbook: Mapping[str, Any] = field(default_factory=dict)
    sheetsets: Mapping[str, Sequence[str]] = field(default_factory=dict)
    sheets: tuple[SheetEntry, ...] = ()
    applicability: Optional[Mapping[str, Any]] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    def content_sha256(self) -> str:
        """Hash of the recipe as written, minus provenance.

        Approval binds to this (plan sec.8.5.2): a recipe edited after approval
        must not execute. Provenance is excluded so that recording the approval
        does not change the thing approved.
        """
        body = {k: v for k, v in self.raw.items() if k != "provenance"}
        blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def data_sheets(self) -> tuple[SheetEntry, ...]:
        return tuple(s for s in self.sheets if s.role == "data")


def _fields_from_json(raw: Sequence[Mapping[str, Any]]) -> tuple[Field, ...]:
    out: list[Field] = []
    for item in raw or ():
        transform = item.get("transform")
        out.append(Field(
            target=str(item.get("target", "")),
            role=str(item.get("role", "")),
            type=item.get("type"),
            source=item.get("source"),
            transform=Transform.from_json(transform) if isinstance(transform, Mapping) else None,
        ))
    return tuple(out)


def recipe_from_json(raw: Mapping[str, Any]) -> Recipe:
    sheets: list[SheetEntry] = []
    for entry in raw.get("sheets", ()) or ():
        sheets.append(SheetEntry(
            sheet=str(entry.get("sheet", "")),
            role=str(entry.get("role", "")),
            reason=entry.get("reason"),
            layout_from=entry.get("layout_from"),
            header_row=entry.get("header_row"),
            data_region=entry.get("data_region"),
            fields=_fields_from_json(entry.get("fields", ())),
            exclude=tuple(
                Exclusion(
                    referent=e.get("referent"),
                    rule=(ExcludeRule.from_json(e["rule"])
                          if isinstance(e.get("rule"), Mapping) else None),
                    reason=e.get("reason"),
                )
                for e in entry.get("exclude", ()) or ()
            ),
            ambiguities=tuple(
                Ambiguity(referent=str(a.get("referent", "")),
                          question=str(a.get("question", "")),
                          blocking=bool(a.get("blocking", False)))
                for a in entry.get("ambiguities", ()) or ()
            ),
            data_row_shape=(RowShape.from_json(entry["data_row_shape"])
                            if isinstance(entry.get("data_row_shape"), Mapping) else None),
            reconcile=tuple(Reconcile.from_json(r)
                            for r in entry.get("reconcile", ()) or ()
                            if isinstance(r, Mapping)),
        ))
    return Recipe(
        recipe_version=int(raw.get("recipe_version", -1)),
        recipe_id=str(raw.get("recipe_id", "")),
        workbook=raw.get("workbook", {}) or {},
        sheetsets=raw.get("sheetsets", {}) or {},
        sheets=tuple(sheets),
        applicability=raw.get("applicability"),
        provenance=raw.get("provenance", {}) or {},
        raw=raw,
    )


def load_recipe(path: str | Path) -> Recipe:
    return recipe_from_json(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Legacy adapter — the expressiveness proof (spec sec.6)
# ---------------------------------------------------------------------------

def from_legacy_manual_recipe(
    legacy: Mapping[str, Any],
    sheet_name: str,
    recipe_id: str = "from_legacy",
    n_rows: Optional[int] = None,
) -> Recipe:
    """Convert Data-agents-demo's `manual_recipe.json` into recipe format v1.

    Legacy pointers are 0-based and so is the frozen grammar, so indices carry
    across with NO arithmetic (grammar spec sec.5).

    The legacy object cannot say which sheet, where the data region ends, what
    to exclude, what transform applies, or what is ambiguous. Those are DA-1 and
    DA-3. The conversion therefore fills in what it can and leaves the rest for a
    human -- it does not invent a data region it was never told.
    """
    from referents import Referent  # local import: keeps this module dependency-light

    header_row0 = int(legacy.get("header_row_index", 0))
    fields: list[Field] = []
    for item in legacy.get("fields", ()) or ():
        target = str(item.get("target") or item.get("target_name") or "")
        pointer = item.get("source_pointer")
        source_type = item.get("source_type")
        dtype = item.get("data_type") or "string"
        if isinstance(pointer, Mapping) and "row" in pointer and "col" in pointer:
            ref = Referent(kind="cell", sheet=sheet_name,
                           row0=int(pointer["row"]), col0=int(pointer["col"]))
            role = "metadata"
        elif isinstance(pointer, Mapping) and "column" in pointer:
            ref = Referent(kind="namedcol", sheet=sheet_name, name=str(pointer["column"]))
            role = "id" if source_type == "column" else "measure"
        elif isinstance(pointer, str):
            ref = Referent(kind="namedcol", sheet=sheet_name, name=pointer)
            role = "measure"
        else:
            continue
        fields.append(Field(target=target, role=role, type=dtype, source=ref.render()))

    header_ref = Referent(kind="row", sheet=sheet_name, row0=header_row0).render()
    data_region = None
    if n_rows is not None and n_rows > header_row0 + 1:
        data_region = Referent(kind="rowrange", sheet=sheet_name,
                               row0=header_row0 + 1, row0_last=n_rows - 1).render()

    entry = SheetEntry(
        sheet=Referent(kind="sheet", sheet=sheet_name).render(),
        role="data",
        header_row=header_ref,
        data_region=data_region,
        fields=tuple(fields),
    )
    raw = {
        "recipe_version": 1,
        "recipe_id": recipe_id,
        "workbook": {},
        "sheets": [{"sheet": entry.sheet, "role": "data"}],
        "provenance": {"proposed_by": "legacy_adapter"},
    }
    return Recipe(recipe_version=1, recipe_id=recipe_id, sheets=(entry,),
                  provenance={"proposed_by": "legacy_adapter"}, raw=raw)
