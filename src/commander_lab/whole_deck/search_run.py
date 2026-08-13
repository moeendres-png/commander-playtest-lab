from __future__ import annotations

from .search_explore import explore
from .search_finalize import finalize
from .search_starts import build_starts


class _RunMixin:
    def run(self, *, current_control: tuple[str, ...] | None = None):
        starts = build_starts(self, current_control)
        archive, start_ids = explore(self, starts)
        return finalize(self, archive, start_ids, current_control)
