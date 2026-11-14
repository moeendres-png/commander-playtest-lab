from __future__ import annotations

from pathlib import Path

from commander_lab.fresh_rebuild import (
    ROGSHAI_COMMANDERS,
    build_fresh_rogshai_profile,
    build_independent_smoke_mainboard,
    load_fresh_rebuild_runtime,
    load_fresh_rogshai_universe,
    run_k2_bias_suite,
)


def test_current_drive_universe_is_complete_and_k2_bias_suite_passes(repo_root: Path) -> None:
    runtime = load_fresh_rebuild_runtime(repo_root)
    universe = load_fresh_rogshai_universe(repo_root)
    coverage = runtime["candidate_universe"]["coverage_counts"]

    assert universe.candidate_count == 795
    assert coverage == {
        "PARTIALLY_MODELED": 588,
        "STRUCTURALLY_MODELED": 123,
        "STRUCTURALLY_UNMODELED": 84,
    }
    assert universe.candidate_count == (
        universe.structurally_scorable_count + universe.review_required_count
    )
    assert universe.review_required_count > 0
    assert set(universe.review_required) <= set(universe.candidate_names)
    for basic in ("Plains", "Island", "Mountain"):
        assert universe.available_quantities.get(basic, 0) >= 50
    # Korvold is historical-only and must not reserve active RogShai inventory.
    assert universe.available_quantities.get("Lightning Greaves", 0) >= 1
    assert universe.available_quantities.get("Goblin Bombardment", 0) >= 1

    bias = run_k2_bias_suite(repo_root)
    assert bias["status"] == "PASS"
    assert all(bias["tests"].values())


def test_independent_smoke_build_never_reads_current_rogshai_control(
    repo_root: Path, monkeypatch
) -> None:
    original = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        assert path.name != "rogshai_current.json"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    universe = load_fresh_rogshai_universe(repo_root)
    mainboard = build_independent_smoke_mainboard(repo_root, universe=universe)
    profile = build_fresh_rogshai_profile(
        repo_root,
        mainboard,
        variant_label="control-blind-test",
        universe=universe,
    )

    assert len(mainboard) == 98
    assert len(profile.cards) == 100
    assert profile.commander_names == ROGSHAI_COMMANDERS
    assert profile.commander_strategy == "rogshai"
    assert profile.deck_id.startswith("rogshai/fresh/")
    assert profile.data_snapshot_hash == universe.runtime_sha256
