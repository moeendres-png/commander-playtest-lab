from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from commander_lab.project_context import ProjectContextSnapshot
from commander_lab.storage.run_identity import sha256_run_value


class WorkflowIdentityError(ValueError):
    """Raised when a declared semantic workflow dependency cannot be resolved."""


@dataclass(frozen=True)
class WorkflowSemanticIdentity:
    schema_version: str
    workflow_name: str
    software_version: str
    engine_version: str
    source_dependencies: tuple[tuple[str, str], ...]
    policy_dependencies: tuple[tuple[str, str], ...]

    def payload(self) -> dict[str, object]:
        return asdict(self)

    @property
    def identity_hash(self) -> str:
        return sha256_run_value(self.payload())

    def as_dict(self) -> dict[str, object]:
        return {"identity_hash": self.identity_hash, **self.payload()}


def _select_exact(
    available: dict[str, str],
    requested: Iterable[str],
    *,
    kind: str,
) -> tuple[tuple[str, str], ...]:
    selected: list[tuple[str, str]] = []
    for key in requested:
        if key not in available:
            raise WorkflowIdentityError(f"missing declared {kind} dependency: {key}")
        selected.append((key, available[key]))
    return tuple(sorted(selected))


def _select_prefixes(
    available: dict[str, str],
    prefixes: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    selected = {
        key: value
        for key, value in available.items()
        if any(key.startswith(prefix) for prefix in prefixes)
    }
    for prefix in prefixes:
        if not any(key.startswith(prefix) for key in available):
            raise WorkflowIdentityError(f"missing declared source dependency prefix: {prefix}")
    return tuple(sorted(selected.items()))


def build_priority_comparison_identity(
    context: ProjectContextSnapshot,
) -> WorkflowSemanticIdentity:
    """Project the global governance snapshot onto inputs consumed by priority comparison.

    Opponent deck content is bound separately by exact opponent deck hashes in RunIdentity.
    Historical handoffs, unrelated external-engine configs and calibration/search configs are not
    semantic dependencies of the current structural paired comparison.
    """

    sources = dict(context.source_hashes)
    policies = dict(context.policy_config_hashes)
    exact_sources = _select_exact(
        sources,
        (
            "active_scope",
            "allocation_snapshot",
            "candidate_eligibility",
            "feature_projection_manifest",
            "inventory_snapshot",
            "opponent_registry",
            "pod_scenarios",
            "protected_cards",
            "active_deck:rogshai/current",
        ),
        kind="source",
    )
    prefixed = _select_prefixes(
        sources,
        (
            "drive_feature:",
            "feature_projection:",
        ),
    )
    selected_sources = tuple(sorted(dict((*exact_sources, *prefixed)).items()))
    selected_policies = _select_exact(
        policies,
        (
            "config/phase7_optimization.json",
            "config/protected_cards.json",
        ),
        kind="policy",
    )
    return WorkflowSemanticIdentity(
        schema_version="1.0.0",
        workflow_name="priority_structural_paired_comparison",
        software_version=context.software_version,
        engine_version=context.engine_version,
        source_dependencies=selected_sources,
        policy_dependencies=selected_policies,
    )


__all__ = [
    "WorkflowIdentityError",
    "WorkflowSemanticIdentity",
    "build_priority_comparison_identity",
]
