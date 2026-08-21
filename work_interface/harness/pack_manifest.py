#!/usr/bin/env python3
"""Backlog B-2 — a pack declares its own inputs; reporters derive from it.

Cloning a pack repeatedly carried literals the new pack could not satisfy:

```text
W1-F  authority_report used A4.verdict, not worker_verdict  -> false CONTESTED 3/3
W1-I  CONSUMPTION_MARKERS held the W1-A fixture titles      -> false NO 6/6
W1-I  grade.py skill_match pinned to the r2 hash            -> false no, whole r3 arm
W1-K  the same skill_match pin, recloned from W1-H          -> false no, whole r2c arm
```

Every one was a constant naming an input, copied rather than derived. The rule
this module enforces:

> **A reporter constant that names an input must be derived from that input, or
> asserted against it.**

It also makes the **run set authoritative**. Reporters must ask the manifest for
the run list, never glob the runs directory: a stray debug directory would
otherwise change denominators silently, months later, with no diff to show it.

Manifest lives at `<pack>/manifest.json`. Paths inside it are relative to
`work_interface/`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

WI = Path(__file__).resolve().parent.parent


class ManifestError(RuntimeError):
    """A pack whose declaration does not match reality. Never guessed around."""


class PackManifest:
    def __init__(self, pack_dir: Path):
        self.pack_dir = Path(pack_dir).resolve()
        self.path = self.pack_dir / "manifest.json"
        if not self.path.is_file():
            raise ManifestError(f"no manifest.json in {self.pack_dir}")
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    # -- identity -----------------------------------------------------------
    @property
    def pack(self) -> str:
        return str(self.data["pack"])

    @property
    def artifact(self) -> str:
        return str(self.data.get("artifact", "work_definition.json"))

    # -- the AUTHORITATIVE run set -----------------------------------------
    @property
    def runs(self) -> list[str]:
        """The declared run set. Reporters use this, never a directory glob."""
        runs = self.data.get("runs")
        if not isinstance(runs, list) or not runs:
            raise ManifestError("manifest declares no runs")
        return [str(r) for r in runs]

    def run_dir(self, run: str) -> Path:
        return self.pack_dir / "runs" / run

    def undeclared_run_dirs(self) -> list[str]:
        """Directories present under runs/ that the manifest does not declare.

        Not an error by itself -- it is reported, so a stray directory can never
        change a denominator quietly.
        """
        root = self.pack_dir / "runs"
        if not root.is_dir():
            return []
        declared = set(self.runs)
        return sorted(d.name for d in root.iterdir()
                      if d.is_dir() and d.name not in declared)

    # -- arms ---------------------------------------------------------------
    @property
    def arms(self) -> dict[str, list[str]]:
        arms = self.data.get("arms") or {}
        return {str(k): [str(x) for x in v] for k, v in arms.items()}

    def arm_of(self, run: str) -> str | None:
        for arm, members in self.arms.items():
            if run in members:
                return arm
        return None

    # -- skill revisions, per arm ------------------------------------------
    @property
    def skills(self) -> dict[str, dict]:
        return self.data.get("skills") or {}

    def skill_revision(self, run: str) -> str:
        arm = self.arm_of(run)
        skills = self.skills
        if arm and arm in skills:
            return str(skills[arm]["revision"])
        if len(skills) == 1:
            return str(next(iter(skills.values()))["revision"])
        raise ManifestError(f"cannot resolve a skill revision for {run!r}")

    def skill_sha256(self, run: str) -> str:
        rev = self.skill_revision(run)
        for spec in self.skills.values():
            if str(spec["revision"]) == rev:
                return str(spec["sha256"])
        raise ManifestError(f"no sha256 declared for revision {rev!r}")

    def declared_revisions(self) -> dict[str, str]:
        """sha256 -> revision name, for every revision this pack declares."""
        return {str(s["sha256"]): str(s["revision"]) for s in
                self.skills.values()}

    # -- fixtures, derived not cloned --------------------------------------
    @property
    def fixtures_dir(self) -> Path:
        return WI / str(self.data["fixtures"]["dir"])

    @property
    def fixture_roles(self) -> dict[str, str]:
        return {str(k): str(v)
                for k, v in self.data["fixtures"]["roles"].items()}

    def fixture_path(self, role: str) -> Path:
        return self.fixtures_dir / self.fixture_roles[role]

    def consumption_markers(self) -> dict[str, str]:
        """DERIVED from this pack's own fixtures -- never a copied literal.

        The marker for a fixture is its first non-empty line, which is the
        fixture's own title. W1-I reported NO for every run because this was a
        hard-coded W1-A title that fixture T could not contain.
        """
        markers = {"skill": "define-lab-process"}
        for role in self.fixture_roles:
            p = self.fixture_path(role)
            if p.is_file():
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        markers[role] = line.strip()
                        break
        return markers

    # -- answers and block --------------------------------------------------
    @property
    def answers_path(self) -> Path:
        return WI / str(self.data["answers"]["path"])

    @property
    def answers_sha256(self) -> str:
        return str(self.data["answers"]["sha256"])

    @property
    def block_order(self) -> tuple[int, ...]:
        return tuple(int(i) for i in self.data["block"]["order"])

    @property
    def block_sha256(self) -> str:
        return str(self.data["block"]["sha256"])

    # -- denominators, always derived --------------------------------------
    def denominators(self) -> dict[str, int]:
        return {"runs": len(self.runs),
                "resources": len(self.fixture_roles) + 1,   # + the skill
                "rows": len(self.block_order)}

    # -- integrity ----------------------------------------------------------
    def verify(self) -> list[str]:
        """Every declaration checked against the bytes. Returns problems."""
        problems: list[str] = []

        for run in self.runs:
            d = self.run_dir(run)
            if not d.is_dir():
                problems.append(f"declared run {run!r} has no directory")
                continue
            sk = d / "SKILL.md"
            if not sk.is_file():
                problems.append(f"{run}: SKILL.md missing")
                continue
            got = hashlib.sha256(sk.read_bytes()).hexdigest()
            want = self.skill_sha256(run)
            if got != want:
                problems.append(
                    f"{run}: SKILL.md {got[:16]} != declared "
                    f"{self.skill_revision(run)} {want[:16]}")

        for extra in self.undeclared_run_dirs():
            problems.append(
                f"undeclared directory under runs/: {extra!r} -- the manifest "
                f"is authoritative, so this would silently change denominators")

        for role in self.fixture_roles:
            if not self.fixture_path(role).is_file():
                problems.append(f"fixture for role {role!r} is missing")

        ap = self.answers_path
        if not ap.is_file():
            problems.append("answer table missing")
        elif hashlib.sha256(ap.read_bytes()).hexdigest() != self.answers_sha256:
            problems.append("answer table does not match its declared sha256")

        markers = self.consumption_markers()
        for role in self.fixture_roles:
            m = markers.get(role)
            if not m:
                problems.append(f"no consumption marker derivable for {role!r}")
            elif m not in self.fixture_path(role).read_text(encoding="utf-8"):
                problems.append(
                    f"consumption marker for {role!r} does not occur in its "
                    f"own fixture")
        return problems


def load(pack_dir: Path) -> PackManifest:
    return PackManifest(pack_dir)
