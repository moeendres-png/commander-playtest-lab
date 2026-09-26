from __future__ import annotations

from .search_base import SearchArchive, SearchEngineBase, SearchStart
from .search_step import explore_start


def explore(engine: SearchEngineBase, starts: list[SearchStart]) -> tuple[SearchArchive, list[str]]:
    archive: SearchArchive = {}
    start_ids: list[str] = []
    for start_type, mainboard, seed in starts:
        current = engine._evaluate(
            mainboard,
            seed=seed,
            parent_variant_id=None,
            mutation=None,
            start_type=start_type,
        )
        archive.setdefault(current.variant_id, current)
        start_ids.append(current.variant_id)
        if current.hard_gate.valid:
            explore_start(engine, current, seed, archive)
        if len(archive) >= engine.config.archive_limit:
            break
    return archive, start_ids
