from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

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
    deck_id: str | None = None,
) -> WorkflowSemanticIdentity:
    """Project governance inputs onto one deck-scoped priority comparison identity.

    The current canonical data may contain only one active own deck, but that is a data-state
    property rather than an API contract. Callers may select any active ``deck_id`` represented by
    the supplied context. Opponent deck content remains bound separately by exact opponent hashes
    in ``RunIdentity``.
    """

    selected_deck_id = deck_id or context.primary_deckbuilding_focus
    if selected_deck_id not in context.active_own_deck_ids:
        raise WorkflowIdentityError(
            f"priority comparison deck is not active in this context: {selected_deck_id}"
        )

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
            f"active_deck:{selected_deck_id}",
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
        schema_version="1.1.0",
        workflow_name=f"priority_structural_paired_comparison:{selected_deck_id}",
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
