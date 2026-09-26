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
from commander_lab.rogshai_mvp_acceptance import (
    PRIMARY_OPPONENT_IDS,
    run_rogshai_mvp_acceptance,
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


def test_rogshai_mvp_end_to_end_acceptance(repo_root: Path) -> None:
    report = run_rogshai_mvp_acceptance(repo_root, iterations=1, seed=20260810)

    assert report["ROGSHAI_MVP_READY"] is True
    assert report["smoke_test_only"] is True
    assert report["deck_strength_inference_allowed"] is False
    assert report["estimate_type"] == "structural_model_estimates"
    assert report["primary_4p_opponents"] == list(PRIMARY_OPPONENT_IDS)
    assert all(report["technical_checks"].values())

    paired = report["paired_comparison"]
    assert paired["same_seed_reproducible"] is True
    assert paired["actual_sample_size"] == 1

    package = report["package_ablation"]
    assert package["package_id"].startswith("package:rogshai:")
    assert len(package["cards"]) == 2
    assert package["actual_sample_size"] == 1

    denial = report["commander_denial"]
    assert set(denial) == {"Ishai", "Rograkh", "both"}
    assert all(row["actual_sample_size"] == 1 for row in denial.values())

    sensitivity = report["sensitivity"]
    assert sensitivity["axis"] == "opponent_composition"
    assert sensitivity["result"]["estimate_type"] == "structural_model_estimates"

    search = report["bounded_search_pareto"]
    assert search["legal_single_swaps"] > 0
    assert search["variants_evaluated"] == 2
    assert search["pareto_front_ids"]

    identity = report["run_identity"]
    assert identity["canonical_input_status"] == "current"
    assert identity["engine_mode"] == "structural"
    assert len(identity["run_identity_hash"]) == 64

    evidence = report["opponent_evidence"]
    morcant = evidence["alen_high_perfect_morcant"]
    cosmic = evidence["cosmic_spider_man"]
    assert morcant["deck_status"] == "partially_observed"
    assert cosmic["deck_status"] == "partially_observed"
    assert "synthetic" in morcant["deck_source_type"]
    assert "synthetic" in cosmic["deck_source_type"]
