"""Fail-safe materiality classification for review-gate enforcement.

The cross-executor review is expensive, so genuinely generated-state-only and
documentation-only closeout may be NON_MATERIAL. Everything else -- including
unknown paths -- defaults to MATERIAL, so implementation, executable tooling,
schemas/contracts, CI, tests that alter acceptance semantics, and
evidence/qualification semantics can never evade review.

Classification is path-based and deterministic:

- ``GENERATED_STATE``: the explicit workstream state file and canonical
  ``.foundry/reviews/**`` receipts (checkpoint-only artifacts).
- ``NON_MATERIAL``: ``docs/**`` and non-policy root markdown.
- ``MATERIAL``: everything else, including every unknown path.

A commit-range classification failure (missing objects, Git unavailable) is
reported as ``UNKNOWN`` and is treated as MATERIAL by callers.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

MATERIAL = "MATERIAL"
NON_MATERIAL = "NON_MATERIAL"
UNKNOWN = "UNKNOWN"
GENERATED_STATE = "GENERATED_STATE"
PATH_CLASSES = (MATERIAL, NON_MATERIAL, GENERATED_STATE)

# Policy files that look like documentation but change operating authority.
_POLICY_ROOT_MARKDOWN = {"AGENTS.md", "CLAUDE.md"}


def _relative(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def classify_path(path: str, *, state_paths: tuple[str, ...] = ()) -> str:
    """Classify one repo-relative path; unknown shapes are MATERIAL."""
    rel = _relative(path)
    if not rel:
        return MATERIAL
    explicit_states = {_relative(item) for item in state_paths}
    if rel in explicit_states:
        return GENERATED_STATE
    if rel.startswith(".foundry/reviews/"):
        return GENERATED_STATE
    parts = rel.split("/")
    if parts[0] == ".foundry" and rel.endswith((".yaml", ".yml")):
        # Operational workstream-state YAML is generated state, never Source
        # Authority; the registry/schema/receipt JSON under .foundry stays
        # MATERIAL so policy and evidence semantics cannot evade review.
        return GENERATED_STATE
    if rel in _POLICY_ROOT_MARKDOWN:
        return MATERIAL
    if "/" not in rel and rel.endswith(".md"):
        return NON_MATERIAL
    if parts[0] == "docs" and rel.endswith((".md", ".txt")):
        return NON_MATERIAL
    return MATERIAL


@dataclass(frozen=True)
class MaterialityReport:
    declared: str
    computed: str
    material_paths: tuple[str, ...]
    generated_state_paths: tuple[str, ...]
    non_material_paths: tuple[str, ...]
    reason: str = ""

    @property
    def effective_computed(self) -> str:
        return MATERIAL if self.computed == UNKNOWN else self.computed

    @property
    def is_material(self) -> bool:
        return self.effective_computed == MATERIAL

    def to_dict(self) -> dict:
        return {
            "declared": self.declared,
            "computed": self.computed,
            "effective_computed": self.effective_computed,
            "material_paths": list(self.material_paths),
            "generated_state_paths": list(self.generated_state_paths),
            "non_material_paths": list(self.non_material_paths),
            "reason": self.reason,
        }


def classify_paths(
    paths: list[str] | tuple[str, ...],
    *,
    declared: str | None = None,
    state_paths: tuple[str, ...] = (),
) -> MaterialityReport:
    """Classify a change set. Any MATERIAL or unknown path => MATERIAL."""
    material: list[str] = []
    generated: list[str] = []
    non_material: list[str] = []
    for path in paths:
        kind = classify_path(path, state_paths=state_paths)
        if kind == GENERATED_STATE:
            generated.append(_relative(path))
        elif kind == NON_MATERIAL:
            non_material.append(_relative(path))
        else:
            material.append(_relative(path))
    computed = MATERIAL if material else NON_MATERIAL
    return MaterialityReport(
        declared=declared or UNKNOWN,
        computed=computed,
        material_paths=tuple(sorted(material)),
        generated_state_paths=tuple(sorted(generated)),
        non_material_paths=tuple(sorted(non_material)),
    )


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def classify_commit_range(
    workdir: str,
    base: str,
    head: str,
    *,
    declared: str | None = None,
    state_paths: tuple[str, ...] = (),
) -> MaterialityReport:
    """Classify the changed paths between two commits. Unknown => MATERIAL."""
    if not base or not head:
        return MaterialityReport(
            declared=declared or UNKNOWN,
            computed=UNKNOWN,
            material_paths=(),
            generated_state_paths=(),
            non_material_paths=(),
            reason="missing commit identity; fail-safe MATERIAL",
        )
    if base == head:
        return MaterialityReport(
            declared=declared or UNKNOWN,
            computed=NON_MATERIAL,
            material_paths=(),
            generated_state_paths=(),
            non_material_paths=(),
            reason="empty delta",
        )
    try:
        listing = _git(["diff", "--name-only", base, head], workdir)
    except RuntimeError as exc:
        return MaterialityReport(
            declared=declared or UNKNOWN,
            computed=UNKNOWN,
            material_paths=(),
            generated_state_paths=(),
            non_material_paths=(),
            reason=f"git diff unavailable ({exc}); fail-safe MATERIAL",
        )
    touched = [line.strip() for line in listing.splitlines() if line.strip()]
    if not touched:
        return MaterialityReport(
            declared=declared or UNKNOWN,
            computed=NON_MATERIAL,
            material_paths=(),
            generated_state_paths=(),
            non_material_paths=(),
            reason="empty delta",
        )
    return classify_paths(touched, declared=declared, state_paths=state_paths)


def declared_materiality_problems(declared: str | None, report: MaterialityReport) -> list[str]:
    """Fail closed when a NON_MATERIAL claim hides a MATERIAL change set."""
    if declared in (None, "", UNKNOWN):
        return []
    if declared not in (MATERIAL, NON_MATERIAL):
        return [f"MATERIALITY_INVALID: declared {declared!r} not in MATERIAL/NON_MATERIAL"]
    if declared == NON_MATERIAL and report.is_material:
        shown = ", ".join(report.material_paths[:5]) or report.reason
        return [
            f"MATERIALITY_UNDERCLAIM: declared NON_MATERIAL but change set is MATERIAL ({shown})"
        ]
    if (
        declared == MATERIAL
        and report.effective_computed == NON_MATERIAL
        and report.computed != UNKNOWN
    ):
        # Over-claiming is safe but recorded; never an evasion and never a pass boost.
        return []
    return []
