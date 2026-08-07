from commander_lab.agents.optimization_orchestrator import (
    RunProfile, build_optimization_plan, select_run_profile,
)
from commander_lab.tools.registry import TOOL_DEFINITIONS


def test_run_profile_selection_is_goal_sensitive() -> None:
    assert select_run_profile("Prüfe das in XMage und Forge") == RunProfile.EXTERNAL_ENGINE_VALIDATION
    assert select_run_profile("Optimiere Korvold und RogShai gleichzeitig ohne Doppelbelegung") == RunProfile.FULL_OPTIMIZATION
    assert select_run_profile("Warum erscheint diese Karte schwach?") == RunProfile.DEEP_VALIDATION
    assert select_run_profile("Schneller Screen") == RunProfile.QUICK_SCREEN
    assert select_run_profile("Verbessere Korvold") == RunProfile.STANDARD_VALIDATION


def test_plan_uses_available_registry_and_never_applies_changes() -> None:
    available = [row.name for row in TOOL_DEFINITIONS]
    plan = build_optimization_plan(
        "Optimiere Korvold und RogShai gleichzeitig ohne Doppelbelegung",
        available_tools=available,
    )
    assert plan.profile == RunProfile.FULL_OPTIMIZATION
    assert plan.tools[0] == "build_optimization_context"
    assert "optimize_multiple_decks_with_allocation" in plan.tools
    assert plan.applies_changes is False
