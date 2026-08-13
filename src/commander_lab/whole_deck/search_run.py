from __future__ import annotations

from .search_base import SearchEngineBase
from .search_explore import explore
from .search_finalize import finalize
from .search_models import WholeDeckSearchResult
from .search_starts import build_starts


class _RunMixin(SearchEngineBase):
    def run(self, *, current_control: tuple[str, ...] | None = None) -> WholeDeckSearchResult:
        starts = build_starts(self, current_control)
        archive, start_ids = explore(self, starts)
        return finalize(self, archive, start_ids, current_control)
