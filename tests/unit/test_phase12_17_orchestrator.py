from commander_lab.agents.optimization_orchestrator import (
    RunProfile,
    select_run_profile,
)


def test_run_profile_selection_is_goal_sensitive() -> None:
    assert (
        select_run_profile("Prüfe das in XMage und Forge") == RunProfile.EXTERNAL_ENGINE_VALIDATION
    )
    assert (
        select_run_profile("Optimiere Korvold und RogShai gleichzeitig ohne Doppelbelegung")
        == RunProfile.FULL_OPTIMIZATION
    )
    assert select_run_profile("Warum erscheint diese Karte schwach?") == RunProfile.DEEP_VALIDATION
    assert select_run_profile("Schneller Screen") == RunProfile.QUICK_SCREEN
    assert select_run_profile("Verbessere Korvold") == RunProfile.STANDARD_VALIDATION
