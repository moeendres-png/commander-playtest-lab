from __future__ import annotations

from collections.abc import Sequence

from .search_context import WholeDeckSearchContext


def fresh_rebuild_issue(context: WholeDeckSearchContext, mainboard: Sequence[str]) -> str | None:
    if context.root is None:
        return None
    try:
        context.materialize(tuple(mainboard), label="hard-gate")
    except (ValueError, RuntimeError) as exc:
        return f"fresh_rebuild:{exc}"
    return None
