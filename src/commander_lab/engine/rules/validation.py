from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
    RulesGameRequest,
    TacticalScenario,
    TurnPhase,
    ZoneState,
)

from . import (
    manager as rules_manager,
)
from . import (
    project as rules_project,
)
from . import (
    registry as rules_registry,
)

PHASE8_ENGINE_VERSION = "tactical-0.8.0"


def _catalog_card_names(root: Path) -> list[str]:
    payload = json.loads((root / "data/cards/oracle_subset.json").read_text(encoding="utf-8"))
    return sorted(card["oracle_name"] for card in payload["cards"])


def _action_scenario() -> TacticalScenario:
    action = LegalAction(
        action_id="pass-test",
        actor_id="p1",
        action_type=ActionType.PASS_PRIORITY,
    )
    state = GameState(
        game_id="phase8-action-scenario",
        seed=20260804,
        status=GameStatus.IN_PROGRESS,
        turn_number=5,
        active_player_id="p1",
        priority_player_id="p1",
        phase=TurnPhase.PRECOMBAT_MAIN,
        players=(
            PlayerState(player_id="p1", seat=0, zones=ZoneState()),
            PlayerState(player_id="p2", seat=1, zones=ZoneState()),
        ),
        legal_actions=(action,),
    )
    return TacticalScenario(
        scenario_id="programmatic-action-roundtrip",
        description="Expose one legal action, submit it, and transfer the resulting state.",
        state=state,
        tags=("adapter", "action_submission"),
    )


def run_phase8_validation(
    root: str | Path,
    *,
    output_directory: str | Path | None = None,
    seed: int = 20260804,
    persist_canonical_registry: bool = False,
) -> dict[str, object]:
    root_path = Path(root)
    output = (
        Path(output_directory)
        if output_directory is not None
        else root_path / "data/runs/phase8_validation"
    )
    output.mkdir(parents=True, exist_ok=True)

    manager = rules_manager.RulesEngineManager(root=root_path)
    try:
        probes = manager.probes()
        decks = rules_project.load_project_rules_decks(root_path)
        handles = {
            deck_id: manager.tactical.load_deck(deck)
            for deck_id, deck in decks.items()
        }

        request_a = RulesGameRequest(
            game_id="phase8-repro-a",
            deck_handles=(
                handles["korvold/current"].handle_id,
                handles["rogshai/current"].handle_id,
                handles["korvold/current"].handle_id,
                handles["rogshai/current"].handle_id,
            ),
            seed=seed,
            starting_player_seat=0,
        )
        request_b = request_a.model_copy(update={"game_id": "phase8-repro-b"})
        game_a = manager.tactical.start_commander_game(request_a)
        game_b = manager.tactical.start_commander_game(request_b)
        zones_a = [player.zones.model_dump(mode="json") for player in game_a.state.players]
        zones_b = [player.zones.model_dump(mode="json") for player in game_b.state.players]
        deterministic_start = zones_a == zones_b

        scenario_session = manager.tactical.create_scenario(_action_scenario())
        legal_actions = manager.tactical.get_legal_actions(scenario_session.session_id)
        proposal = ActionProposal(
            proposal_id="phase8-pass",
            actor_id="p1",
            legal_action_id="pass-test",
            action_type=ActionType.PASS_PRIORITY,
            policy_name="phase8_validation",
        )
        state_after_action = manager.tactical.submit_action(
            scenario_session.session_id, proposal
        )
        action_logs = manager.tactical.get_logs(scenario_session.session_id)

        interactions = rules_registry.load_interaction_catalog(
            root_path / "data/rules/project_critical_interactions.json"
        )
        external = manager.available_external()
        registry = rules_registry.build_validation_registry(
            all_card_names=_catalog_card_names(root_path),
            interactions=interactions,
            tactical_oracle=manager.tactical.oracle,
            external_adapters=external,
            engine_version=PHASE8_ENGINE_VERSION,
        )
        run_registry_path = rules_registry.write_validation_registry(
            registry, output / "validation_registry.json"
        )
        canonical_registry_path: Path | None = None
        if persist_canonical_registry:
            canonical_registry_path = rules_registry.write_validation_registry(
                registry, root_path / "data/rules/validation_registry.json"
            )

        interaction_results_path = output / "interaction_results.jsonl"
        interaction_results_path.write_text(
            "".join(
                result.model_dump_json() + "\n"
                for _, result in sorted(registry.interactions.items())
            ),
            encoding="utf-8",
        )
        probes_path = output / "backend_probes.json"
        probes_path.write_text(
            json.dumps(
                {
                    key.value: value.model_dump(mode="json")
                    for key, value in probes.items()
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        logs_path = output / "adapter_action_log.jsonl"
        logs_path.write_text(
            "".join(event.model_dump_json() + "\n" for event in action_logs.events),
            encoding="utf-8",
        )

        local_passed = (
            len(interactions) >= 50
            and registry.tactical_passed == registry.tactical_cases
            and deterministic_start
            and len(legal_actions) == 1
            and state_after_action.priority_player_id == "p2"
            and len(action_logs.events) >= 2
        )
        external_passed = registry.rules_engine_passed >= 50
        summary: dict[str, object] = {
            "phase": 8,
            "package_version": "0.8.0",
            "engine_version": PHASE8_ENGINE_VERSION,
            "interaction_cases": len(interactions),
            "tactical_passed": registry.tactical_passed,
            "rules_engine_cases_attempted": registry.rules_engine_cases,
            "rules_engine_passed": registry.rules_engine_passed,
            "cards_total": len(registry.cards),
            "card_status_counts": {
                level: sum(
                    1 for item in registry.cards.values() if item.level.value == level
                )
                for level in (
                    "structural_only",
                    "tactical_oracle",
                    "external_rules_engine",
                )
            },
            "deterministic_starting_state": deterministic_start,
            "programmatic_action_roundtrip": state_after_action.priority_player_id
            == "p2",
            "event_log_captured": len(action_logs.events) >= 2,
            "backend_probes": {
                key.value: value.model_dump(mode="json") for key, value in probes.items()
            },
            "local_acceptance_passed": local_passed,
            "rules_engine_release_gate_passed": external_passed,
            "artifacts": {
                "canonical_registry": (
                    str(canonical_registry_path)
                    if canonical_registry_path is not None
                    else None
                ),
                "run_registry": str(run_registry_path),
                "interaction_results": str(interaction_results_path),
                "backend_probes": str(probes_path),
                "adapter_action_log": str(logs_path),
            },
            "notes": [
                (
                    "All tactical results are bounded tactical validations, "
                    "not complete rules-engine proofs."
                ),
                (
                    "The external release gate requires at least 50 matching "
                    "XMage or Forge observations."
                ),
                (
                    "Canonical validation registry persistence is opt-in; normal "
                    "validation runs write only to the run output directory."
                ),
            ],
        }
        summary_path = output / "phase8_validation_summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return summary
    finally:
        manager.close()


__all__ = ["PHASE8_ENGINE_VERSION", "run_phase8_validation"]
