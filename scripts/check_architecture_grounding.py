#!/usr/bin/env python3
"""Check that the measured architecture view still matches the source.

`docs/architecture/uml/05-package-dependencies.puml` claims to be MEASURED:
every edge in it was extracted from the repository. A claim like that decays
silently -- a package gains an import, the diagram does not, and the next
contributor plans against a structure that no longer exists.

ADR-0002 records the decision that the measured view is checked by a script
rather than by eye, and `operating_procedure.md` §2.1 is the existing position
it rests on: a rule is only worth stating if it is checkable.

## What is measured

The live packages named in `PRODUCT.md` do NOT use package-qualified imports.
They put sibling directories on `sys.path` and import bare module names::

    import task_model          # taskmodel/task_model.py
    import worker as W         # worker/worker.py
    import observe             # inspector/observe.py
    import adapters.xlsx       # package-qualified, also used

So a plain grep for ``from <package>`` finds three of the twenty-two real
edges. This checker resolves BOTH forms: a bare module name is attributed to
the package that owns a file of that name, and a package-qualified name is
attributed directly.

An edge ``A -> B`` means "some module in A imports a module owned by B". That
is the dependency that constrains change, which is what the view is for.

## What is NOT measured

Only static, top-level `import` / `from ... import` statements. Dynamic imports
(`importlib`), imports inside function bodies indented under a def, and runtime
`sys.path` games are not resolved. The check is therefore a floor: an edge it
reports is real; an edge it misses is possible. It has never yet missed one --
if that changes, the fix is here, not in the diagram.

## Resolution when it fails

Fixed by the engineering system's precedence rule (§7): the code is what
exists, so the diagram is corrected. If the CODE is the thing that looks wrong,
record it in `docs/development/discrepancy-register.md` and let Roundtable
disposition it. Never satisfy the check by deleting the assertion.

Usage::

    python scripts/check_architecture_grounding.py
    python scripts/check_architecture_grounding.py --self-test
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
VIEW = LAB / "docs" / "architecture" / "uml" / "05-package-dependencies.puml"

# The live packages, per PRODUCT.md "What is live code vs research record".
# Research directories are deliberately absent: they are evidence, not the
# live system, and drawing them here would blur exactly the line the
# repository map exists to keep.
LIVE_PACKAGES = (
    "adapters", "inspector", "modeller", "taskmodel", "worker", "fleet",
    "supervisor", "reservation", "enrichment", "aggregation",
    "reconciliation", "calendar_job",
)

_IMPORT = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))"
)
# Only `A --> B`, optionally labelled. PlantUML comments start with a single
# quote and are skipped, so prose in the header cannot fake an edge.
_EDGE = re.compile(r"^\s*([a-z_][a-z_0-9]*)\s*-->\s*([a-z_][a-z_0-9]*)\s*(?::.*)?$")

Edge = tuple[str, str]


def _owners(root: Path, packages: tuple[str, ...]) -> dict[str, set[str]]:
    """Map an importable name to the package(s) that own it.

    Both forms: the package's own name (``adapters.xlsx`` -> ``adapters``) and
    every module file stem inside it (``task_model`` -> ``taskmodel``), because
    the sys.path style imports the stem.
    """
    owners: dict[str, set[str]] = {}
    for pkg in packages:
        owners.setdefault(pkg, set()).add(pkg)
        directory = root / pkg
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            owners.setdefault(path.stem, set()).add(pkg)
    return owners


def measure(root: Path = LAB,
            packages: tuple[str, ...] = LIVE_PACKAGES) -> set[Edge]:
    """Every cross-package dependency edge visible in the source."""
    owners = _owners(root, packages)
    edges: set[Edge] = set()
    for pkg in packages:
        directory = root / pkg
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                match = _IMPORT.match(line)
                if not match:
                    continue
                head = (match.group(1) or match.group(2)).split(".")[0]
                for owner in owners.get(head, ()):
                    if owner != pkg:
                        edges.add((pkg, owner))
    return edges


def declared(view: Path = VIEW) -> set[Edge]:
    """Every edge asserted by the MEASURED view."""
    edges: set[Edge] = set()
    for line in view.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("'"):          # PlantUML comment
            continue
        match = _EDGE.match(line)
        if match:
            edges.add((match.group(1), match.group(2)))
    return edges


def compare(measured: set[Edge], asserted: set[Edge]) -> dict:
    """Drift in both directions. Both are defects; neither is worse."""
    return {
        "in_code_not_in_view": sorted(measured - asserted),
        "in_view_not_in_code": sorted(asserted - measured),
        "agree": sorted(measured & asserted),
    }


def _report(result: dict) -> int:
    missing = result["in_code_not_in_view"]
    extra = result["in_view_not_in_code"]
    if not missing and not extra:
        print(f"OK  {len(result['agree'])} package dependency edges, "
              f"view and source agree")
        return 0
    if missing:
        print("DRIFT  in the code but NOT in the view "
              "(the view is incomplete):")
        for a, b in missing:
            print(f"         {a} --> {b}")
    if extra:
        print("DRIFT  in the view but NOT in the code "
              "(the view asserts an edge that does not exist):")
        for a, b in extra:
            print(f"         {a} --> {b}")
    print()
    print("The code is what exists (engineering system, precedence rule): "
          "correct the view.")
    print("If the CODE looks wrong instead, record it in "
          "docs/development/discrepancy-register.md rather than editing "
          "either side to agree.")
    return 1


# ---------------------------------------------------------------------------
# self-test -- exercises the checker, not the repository
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: list[str] = []

    def check(condition: bool, why: str) -> None:
        if not condition:
            failures.append(why)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "alpha").mkdir()
        (root / "beta").mkdir()
        (root / "gamma").mkdir()
        # beta owns a module whose stem differs from its package name --
        # the sys.path style this repository actually uses.
        (root / "beta" / "beta_thing.py").write_text("X = 1\n", encoding="utf-8")
        (root / "gamma" / "g.py").write_text("Y = 2\n", encoding="utf-8")
        (root / "alpha" / "a.py").write_text(
            "import sys\n"
            "import beta_thing        # bare stem -> beta\n"
            "from gamma.g import Y    # package-qualified -> gamma\n",
            encoding="utf-8")
        pkgs = ("alpha", "beta", "gamma")

        measured = measure(root, pkgs)
        check(("alpha", "beta") in measured,
              "bare sys.path-style stem import was not resolved to its package")
        check(("alpha", "gamma") in measured,
              "package-qualified import was not resolved")
        check(("beta", "alpha") not in measured,
              "an edge was invented in the direction nothing imports")
        check(len(measured) == 2,
              f"expected exactly 2 edges from the fixture, got {sorted(measured)}")

        # a package importing its own sibling module is not a cross-package edge
        (root / "beta" / "beta_other.py").write_text(
            "import beta_thing\n", encoding="utf-8")
        check(("beta", "beta") not in measure(root, pkgs),
              "a package was reported as depending on itself")

        # __pycache__ must not contribute
        cache = root / "alpha" / "__pycache__"
        cache.mkdir()
        (cache / "stale.py").write_text("import g\n", encoding="utf-8")
        check(measure(root, pkgs) == measured,
              "__pycache__ contents changed the measurement")

        view = root / "view.puml"
        view.write_text(
            "@startuml\n"
            "' alpha --> nowhere   <- a comment must not count as an edge\n"
            "alpha --> beta : beta_thing\n"
            "alpha --> gamma\n"
            "note as N\n"
            "alpha -> beta -> gamma is prose, single arrows, not edges\n"
            "end note\n"
            "@enduml\n", encoding="utf-8")
        asserted = declared(view)
        check(asserted == {("alpha", "beta"), ("alpha", "gamma")},
              f"view parsing wrong: {sorted(asserted)}")
        check(("alpha", "nowhere") not in asserted,
              "a commented-out edge was parsed as declared")

        agreed = compare(measured, asserted)
        check(agreed["in_code_not_in_view"] == [] and
              agreed["in_view_not_in_code"] == [],
              "a matching view and source were reported as drifting")

        # both drift directions must be detected
        one_way = compare(measured | {("beta", "gamma")}, asserted)
        check(one_way["in_code_not_in_view"] == [("beta", "gamma")],
              "an edge present only in the code was not reported")
        other_way = compare(measured, asserted | {("gamma", "alpha")})
        check(other_way["in_view_not_in_code"] == [("gamma", "alpha")],
              "an edge present only in the view was not reported")

    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("OK  self-test: 9 checks")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if not VIEW.exists():
        print(f"FAIL  measured view not found: {VIEW}")
        return 1
    return _report(compare(measure(), declared()))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
