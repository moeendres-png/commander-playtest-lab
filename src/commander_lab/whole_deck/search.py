from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from commander_lab.storage import atomic_write_json

from .mana import derive_mana_base_policy
from .models import DeckDesignPolicy
from .search_acceptance import _AcceptanceMixin
from .search_construct import _ConstructMixin
from .search_context import (
    SEARCH_ENGINE_VERSION,
    SearchCard,
    WholeDeckSearchContext,
    current_control_mainboard,
    stable_variant_hash,
)
from .search_features import _FeatureMixin
from .search_gate import hard_gate
from .search_mana_neighborhoods import _ManaNeighborhoodMixin
from .search_meta_score import _MetaScoreMixin
from .search_packages import _PackageNeighborhoodMixin
from .search_pool_ops import _PoolOpsMixin
from .search_proposal import _ProposalMixin
from .search_run import _RunMixin
from .search_score import _ScoreMixin
from .search_models import ManaBasePolicy, WholeDeckSearchConfig, WholeDeckSearchResult


class WholeDeckSearchEngine(
    _RunMixin,
    _ProposalMixin,
    _AcceptanceMixin,
    _ManaNeighborhoodMixin,
    _PackageNeighborhoodMixin,
    _PoolOpsMixin,
    _ScoreMixin,
    _MetaScoreMixin,
    _FeatureMixin,
    _ConstructMixin,
):
    _hard_gate = hard_gate

    def __init__(
        self,
        context: WholeDeckSearchContext,
        policy: DeckDesignPolicy,
        *,
        config: WholeDeckSearchConfig | None = None,
        mana_policy: ManaBasePolicy | None = None,
        meta_references: Mapping[Any, Any] | None = None,
    ) -> None:
        self.context = context
        self.policy = policy
        self.config = config or WholeDeckSearchConfig()
        self.mana_policy = mana_policy or derive_mana_base_policy(policy)
        self.meta_references = dict(meta_references or {})
        if not self.meta_references and context.root is not None and policy.functional_meta_weight > 0.0:
            self.meta_references = self._load_project_meta_references()
        self._utility = self._build_utility_map()


def save_search_result(
    root: str | Path,
    result: WholeDeckSearchResult,
    *,
    relative_directory: str = ".runtime/whole_deck_search",
) -> Path:
    project = Path(root).resolve()
    output = (project / relative_directory / result.campaign_id / "archive.json").resolve()
    if project not in output.parents:
        raise ValueError("whole-deck search archive path escapes project root")
    atomic_write_json(output, result.model_dump(mode="json"))
    return output
