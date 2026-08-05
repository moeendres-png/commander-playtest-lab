from __future__ import annotations

import csv
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from commander_lab.analysis import CalibrationPolicy, calibrate_playtests
from commander_lab.importers import RealPlaytestImporter
from commander_lab.models import (
    EvidenceSplit,
    PlaytestDatasetManifest,
    PlaytestParticipant,
    RealPlaytest,
    SplitStrategy,
    StructuralBatchResult,
    StructuralMatchResult,
    StructuralPlayerMetrics,
    CalibrateInput,
    ToolStatus,
)
from commander_lab.storage import PlaytestConflictError, PlaytestRepository
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def _participant(player_id: str, deck: str, seat: int, placement: int) -> PlaytestParticipant:
    return PlaytestParticipant(
        player_id=player_id,
        deck_name=deck,
        deck_version="v1",
        commander_names=["Korvold, Fae-Cursed King"] if deck == "Korvold" else ["Other"],
        seat=seat,
        placement=placement,
        mulligans=0,
        starting_hand_lands=3,
        first_commander_cast_turn=4 if deck == "Korvold" else 5,
        removal_events=2 if deck == "Korvold" else 1,
        boardwipes_cast=0,
        korvold_cards_drawn=4 if deck == "Korvold" else None,
        was_archenemy=deck == "Korvold",
        win_axis="table_damage" if placement == 1 else None,
        loss_causes=[] if placement == 1 else ["opponent_finish"],
    )


def _game(index: int, split: EvidenceSplit) -> RealPlaytest:
    participants = [
        _participant(f"p{index}-0", "Korvold", 0, 1),
        _participant(f"p{index}-1", "Opponent A", 1, 2),
        _participant(f"p{index}-2", "Opponent B", 2, 3),
        _participant(f"p{index}-3", "Opponent C", 3, 4),
    ]
    return RealPlaytest(
        dataset_version="calibration-v1",
        game_id=f"g{index:03d}",
        played_on=date(2026, 1, 1),
        pod_size=4,
        participants=participants,
        turns=10,
        winner_player_ids=[participants[0].player_id],
        starting_player_id=participants[0].player_id,
        evidence_split=split,
        validated=True,
    )


def _metrics(match_index: int) -> StructuralPlayerMetrics:
    return StructuralPlayerMetrics(
        player_id=f"sim-{match_index}",
        deck_id="korvold/current",
        placement=1,
        life=20,
        mulligans=0,
        lands_played=7,
        ramp_resolved=2,
        cards_drawn=8,
        commander_casts=1,
        commander_tax_paid=0,
        first_commander_cast_turn=4,
        commander_peak_power={"Korvold, Fae-Cursed King": 7.0},
        korvold_cards_drawn=4,
        removals_resolved=1,
        counters_resolved=0,
        protections_resolved=1,
        wipes_resolved=0,
        graveyard_hate_resolved=0,
        recursions_resolved=1,
        engine_value=3.0,
        resources_generated=4.0,
        normal_damage_dealt=80.0,
        commander_damage_dealt=0.0,
        was_archenemy=True,
    )


def _batch() -> StructuralBatchResult:
    matches = []
    for index in range(120):
        metrics = _metrics(index)
        matches.append(
            StructuralMatchResult(
                run_id="sim-calibration",
                match_id=f"m{index:03d}",
                seed=index,
                completed=True,
                turns=10,
                winner_ids=(metrics.player_id,),
                placements={metrics.player_id: 1},
                end_reason="last_player_standing",
                player_metrics={metrics.player_id: metrics},
                event_count=1,
            )
        )
    return StructuralBatchResult(
        run_id="sim-calibration",
        master_seed=1,
        iterations=len(matches),
        workers=1,
        pod_size=4,
        completed_games=len(matches),
        aborted_games=0,
        match_results=matches,
    )


def test_importer_captures_phase9_fields_and_german_aliases(tmp_path: Path) -> None:
    path = tmp_path / "real.csv"
    rows = []
    for index in range(4):
        rows.append(
            {
                "Spiel-ID": "g1",
                "Datum": "2026-08-05",
                "Datenversion": "session-2026-08",
                "Spieler-ID": f"p{index}",
                "Deck": "Korvold" if index == 0 else f"Opponent {index}",
                "Version": "deck-v1",
                "Commander": "Korvold, Fae-Cursed King" if index == 0 else "Other",
                "Sitz": index,
                "Platzierung": index + 1,
                "Mulligans": 0,
                "Starthandländer": 3,
                "Länder": 7,
                "Erster Rampzug": 2,
                "Ramp": 2,
                "Commander Cast": 4,
                "Commander Entfernungen": 1,
                "Removal": 2,
                "Drawengines": 1,
                "Boardwipes": 0,
                "Rebuild": 1,
                "Korvold Draws": 5 if index == 0 else "",
                "Archenemy": "ja" if index == 0 else "nein",
                "Siegachse": "table_damage" if index == 0 else "",
                "Niederlagenursache": "" if index == 0 else "opponent_finish",
                "Tote Karten": "Card A|Card B" if index == 0 else "",
                "Sequencingfehler": "land_before_draw" if index == 0 else "",
                "Startspieler": "p0",
                "Spielzüge": 11,
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    games = RealPlaytestImporter().import_file(path)
    assert games[0].validated
    participant = games[0].participants[0]
    assert participant.deck_version == "deck-v1"
    assert participant.first_commander_cast_turn == 4
    assert participant.korvold_cards_drawn == 5
    assert participant.dead_cards == ["Card A", "Card B"]
    assert participant.sequencing_errors == ["land_before_draw"]


def test_playtest_repository_is_append_only_and_split_is_sealed(tmp_path: Path) -> None:
    repository = PlaytestRepository(tmp_path)
    game = _game(1, EvidenceSplit.UNSPLIT)
    manifest = repository.ingest([game], dataset_version="v1")
    assert manifest.validated_games == 1
    manifest = repository.seal_split(
        "v1",
        assignments={game.game_id: EvidenceSplit.TRAIN},
        strategy=SplitStrategy.STABLE_HASH,
        seed=7,
        train_fraction=0.7,
    )
    assert manifest.split_sealed_at is not None
    with pytest.raises(PlaytestConflictError):
        repository.seal_split(
            "v1",
            assignments={game.game_id: EvidenceSplit.VALIDATION},
            strategy=SplitStrategy.STABLE_HASH,
            seed=8,
            train_fraction=0.7,
        )
    changed = game.model_copy(deep=True)
    changed.turns = 99
    with pytest.raises(PlaytestConflictError):
        repository.ingest([changed], dataset_version="v1")
    with pytest.raises(PlaytestConflictError):
        repository.ingest([_game(2, EvidenceSplit.UNSPLIT)], dataset_version="v1")


def test_calibration_uses_train_only_and_accepts_only_after_validation_improves() -> None:
    games = [
        _game(index, EvidenceSplit.TRAIN if index < 30 else EvidenceSplit.VALIDATION)
        for index in range(40)
    ]
    assignments = {game.game_id: game.evidence_split for game in games}
    manifest = PlaytestDatasetManifest(
        dataset_id="real-playtests/calibration-v1",
        dataset_version="calibration-v1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        game_ids=tuple(game.game_id for game in games),
        game_hashes={game.game_id: "0" * 64 for game in games},
        data_hash="1" * 64,
        validated_games=40,
        excluded_games=0,
        split_strategy=SplitStrategy.CHRONOLOGICAL,
        split_seed=3,
        train_fraction=0.75,
        split_assignments=assignments,
        split_sealed_at=datetime.now(UTC),
    )
    report = calibrate_playtests(
        manifest=manifest,
        games=games,
        simulation_batches=[_batch()],
        simulation_source_hashes={"sim.json": "2" * 64},
        policy=CalibrationPolicy(
            train_fraction=0.75,
            split_seed=3,
            minimum_train_games=20,
            minimum_validation_games=8,
            minimum_train_observations=12,
            minimum_validation_observations=5,
            bootstrap_samples=200,
        ),
    )
    key = "korvold.removal_frequency_multiplier"
    assert key in report.accepted_parameters
    assert report.internal_validation_only
    assert not report.independent_confirmation
    assert not report.engine_parameters_modified


def test_single_game_never_calibrates_parameter() -> None:
    game = _game(1, EvidenceSplit.TRAIN)
    manifest = PlaytestDatasetManifest(
        dataset_id="real-playtests/one",
        dataset_version="one",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        game_ids=(game.game_id,),
        game_hashes={game.game_id: "0" * 64},
        data_hash="1" * 64,
        validated_games=1,
        excluded_games=0,
        split_strategy=SplitStrategy.STABLE_HASH,
        split_seed=1,
        train_fraction=0.7,
        split_assignments={game.game_id: EvidenceSplit.TRAIN},
        split_sealed_at=datetime.now(UTC),
    )
    report = calibrate_playtests(
        manifest=manifest,
        games=[game],
        simulation_batches=[_batch()],
        simulation_source_hashes={"sim.json": "2" * 64},
        policy=CalibrationPolicy(bootstrap_samples=100),
    )
    assert not report.accepted_parameters
    assert report.status.value == "insufficient_evidence"


def test_starting_player_flag_satisfies_validation_without_explicit_id() -> None:
    rows = []
    for index in range(4):
        rows.append(
            {
                "game_id": "flag-start",
                "dataset_version": "v1",
                "player_id": f"p{index}",
                "deck_name": "Korvold" if index == 0 else f"Opponent {index}",
                "deck_version": "deck-v1",
                "seat": index,
                "placement": index + 1,
                "mulligans": 0,
                "starting_hand_lands": 3,
                "turns": 9,
                "is_starting_player": index == 2,
            }
        )
    game = RealPlaytestImporter().import_rows(rows)[0]
    assert game.starting_player_id == "p2"
    assert "starting_player_missing" not in game.validation_errors
    assert game.validated


def test_multiple_deck_versions_are_not_pooled_without_explicit_target() -> None:
    games = [
        _game(index, EvidenceSplit.TRAIN if index < 30 else EvidenceSplit.VALIDATION)
        for index in range(40)
    ]
    for index, game in enumerate(games):
        game.participants[0].deck_version = "v1" if index < 20 else "v2"
    assignments = {game.game_id: game.evidence_split for game in games}
    manifest = PlaytestDatasetManifest(
        dataset_id="real-playtests/versioned",
        dataset_version="versioned",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        game_ids=tuple(game.game_id for game in games),
        game_hashes={game.game_id: "0" * 64 for game in games},
        data_hash="1" * 64,
        validated_games=40,
        excluded_games=0,
        split_strategy=SplitStrategy.CHRONOLOGICAL,
        split_seed=3,
        train_fraction=0.75,
        split_assignments=assignments,
        split_sealed_at=datetime.now(UTC),
    )
    report = calibrate_playtests(
        manifest=manifest,
        games=games,
        simulation_batches=[_batch()],
        simulation_source_hashes={"sim.json": "2" * 64},
        policy=CalibrationPolicy(
            train_fraction=0.75,
            split_seed=3,
            minimum_train_games=20,
            minimum_validation_games=8,
            minimum_train_observations=5,
            minimum_validation_observations=2,
            bootstrap_samples=100,
        ),
    )
    assert report.version_conflicts == {"korvold": ("v1", "v2")}
    assert not report.accepted_parameters
    assert all(item.deck_key != "korvold" for item in report.parameter_results)

    selected = calibrate_playtests(
        manifest=manifest,
        games=games,
        simulation_batches=[_batch()],
        simulation_source_hashes={"sim.json": "2" * 64},
        policy=CalibrationPolicy(
            train_fraction=0.75,
            split_seed=3,
            minimum_train_games=20,
            minimum_validation_games=8,
            minimum_train_observations=5,
            minimum_validation_observations=2,
            bootstrap_samples=100,
        ),
        target_deck_versions={"korvold": "v2"},
    )
    assert not selected.version_conflicts
    assert selected.target_deck_versions == {"korvold": "v2"}
    assert any(item.deck_key == "korvold" for item in selected.parameter_results)


def test_tool_service_loads_versioned_policy_and_completes_calibration(tmp_path: Path) -> None:
    for relative in ("data/cards", "data/decks", "data/collections"):
        source = ROOT / relative
        if source.exists():
            shutil.copytree(source, tmp_path / relative)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    for name in ("calibration_policy.json", "openai_workflow.json", "protected_cards.json"):
        source = ROOT / "config" / name
        if source.exists():
            shutil.copy2(source, tmp_path / "config" / name)

    games = [_game(index, EvidenceSplit.UNSPLIT) for index in range(6)]
    PlaytestRepository(tmp_path).ingest(games, dataset_version="service-v1")
    simulation_path = tmp_path / "structural_results.json"
    simulation_path.write_text(
        json.dumps(_batch().model_dump(mode="json")), encoding="utf-8"
    )

    response = CommanderToolService(tmp_path).calibrate(
        CalibrateInput(
            dataset_version="service-v1",
            simulation_result_paths=(str(simulation_path),),
            target_deck_versions={"korvold": "v1"},
        )
    )
    assert response.status is ToolStatus.COMPLETED
    assert response.result["policy_version"] == "1.0.0"
    assert len(response.result["policy_hash"]) == 64
    assert response.result["status"] == "insufficient_evidence"
    assert response.result["accepted_parameters"] == {}
    assert response.result["independent_confirmation"] is False
    assert response.result["engine_parameters_modified"] is False


def test_aborted_structural_matches_are_excluded_from_calibration() -> None:
    game = _game(1, EvidenceSplit.TRAIN)
    manifest = PlaytestDatasetManifest(
        dataset_id="real-playtests/exclusion",
        dataset_version="exclusion",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        game_ids=(game.game_id,),
        game_hashes={game.game_id: "0" * 64},
        data_hash="1" * 64,
        validated_games=1,
        excluded_games=0,
        split_strategy=SplitStrategy.STABLE_HASH,
        split_seed=1,
        train_fraction=0.7,
        split_assignments={game.game_id: EvidenceSplit.TRAIN},
        split_sealed_at=datetime.now(UTC),
    )
    batch = _batch()
    aborted = batch.match_results[0].model_copy(
        update={
            "completed": False,
            "aborted": True,
            "abort_reason": "max_events",
        }
    )
    batch.match_results = [aborted, *batch.match_results[1:]]
    batch.completed_games -= 1
    batch.aborted_games += 1
    report = calibrate_playtests(
        manifest=manifest,
        games=[game],
        simulation_batches=[batch],
        simulation_source_hashes={"sim.json": "2" * 64},
        policy=CalibrationPolicy(bootstrap_samples=100),
    )
    assert report.simulated_matches_total == 120
    assert report.simulated_matches_used == 119
    assert report.simulated_matches_excluded == 1
    assert report.simulated_exclusion_reasons == {"max_events": 1}
    assert any("Excluded 1" in warning for warning in report.warnings)
