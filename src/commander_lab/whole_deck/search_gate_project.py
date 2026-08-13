from __future__ import annotations


def fresh_rebuild_issue(context, mainboard):
    if context.root is None:
        return None
    try:
        context.materialize(mainboard, label="hard-gate")
    except (ValueError, RuntimeError) as exc:
        return f"fresh_rebuild:{exc}"
    return None
