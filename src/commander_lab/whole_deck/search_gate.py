from __future__ import annotations

from .search_gate_counts import count_and_availability_issues
from .search_gate_identity import identity_issues
from .search_gate_land import land_gate_values
from .search_gate_project import fresh_rebuild_issue
from .search_models import WholeDeckHardGate


def hard_gate(engine, mainboard: tuple[str, ...]) -> WholeDeckHardGate:
    issues = list(count_and_availability_issues(mainboard, engine.context.cards))
    issues.extend(identity_issues(mainboard, engine.context.cards, engine.context.commander_names))
    land_count, basic_count, land_issues = land_gate_values(
        mainboard, engine.context.cards, engine.mana_policy
    )
    issues.extend(land_issues)
    if not issues:
        project_issue = fresh_rebuild_issue(engine.context, mainboard)
        if project_issue is not None:
            issues.append(project_issue)
    return WholeDeckHardGate(
        valid=not issues,
        issues=tuple(issues),
        card_count=len(mainboard) + len(engine.context.commander_names),
        land_count=land_count,
        basic_count=basic_count,
    )
