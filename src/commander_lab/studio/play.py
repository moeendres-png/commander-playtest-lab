"""Play one simulated game with the rules engine and record it for the Studio viewer.

The existing full-game runner does all the work: XMage decides every rule, the Lab's pilots
decide every choice. This module only chooses decks and a seed, lets the runner play, and has
the recorder of ``games.py`` write down what happened. Every seat is a pilot here; a human
seat is a later step.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from commander_lab.agents import (
    derive_deck_plan,
    style_label,
    style_reserve_mana,
    style_weights,
)
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.failure_privacy import (
    public_exception_type,
    public_full_game_exception_message,
)
from commander_lab.engine.rules.full_game import (
    FullGameConformanceResult,
    FullGamePilotBinding,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.storage import sha256_value

from .games import DecisionPolicy, GameRecorder, RecordingPolicy, free_game_id
from .launch import engine_command

PILOT_IDENTITY = "GenericCommanderPilot"
PILOT_VERSION = "1.0.0"
POLICY_VERSION = "xmage-full-game-policy-1.0.0"
BRIDGE_VERSION = "xmage-engine-bridge-0.1.0-SNAPSHOT"


def _with_hash(deck: RulesDeckInput) -> RulesDeckInput:
    if deck.deck_hash is not None:
        return deck
    derived = sha256_value(
        {
            "deck_id": deck.deck_id,
            "commander_names": list(deck.commander_names),
            "mainboard": list(deck.mainboard),
            "sideboard": list(deck.sideboard),
        }
    )
    return deck.model_copy(update={"deck_hash": derived})


def load_decks(paths: list[Path]) -> tuple[RulesDeckInput, ...]:
    """Deck snapshots in seat order. Two to six decks, each with its own id."""
    if not 2 <= len(paths) <= 6:
        raise ValueError("a game has two to six seats")
    decks = tuple(_with_hash(load_rules_deck_snapshot(path)) for path in paths)
    if len({deck.deck_id for deck in decks}) != len(decks):
        raise ValueError("every seat needs its own deck (distinct deck ids)")
    return decks


class _RecordingRunner(XmageFullGameRunner):
    """The full-game runner with a recorder between the engine's questions and the pilots."""

    recorder: GameRecorder | None = None

    def _validated_policy(  # type: ignore[override]
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> DecisionPolicy:
        policy = super()._validated_policy(scenario, decks, pilots)
        return RecordingPolicy(policy, self._recorder_for(scenario))

    def _recorder_for(self, scenario: FutureXmageScenario) -> GameRecorder:
        """The log the game of ``scenario`` is written to; one bound recorder for one game."""
        if self.recorder is None:
            raise RuntimeError("no recorder bound")
        return self.recorder

    def _drive(  # type: ignore[override]
        self, client: object, policy: object, *, stop_after: int | None = None, **kwargs: object
    ) -> tuple[int, object, bool]:
        res = super()._drive(client, policy, stop_after=stop_after, **kwargs)  # type: ignore[arg-type]
        if self.recorder is not None and hasattr(client, "request"):
            try:
                raw_log = client.request("export_event_log")
                if isinstance(raw_log, dict):
                    events = raw_log.get("events")
                    if isinstance(events, list):
                        self.recorder.save_event_log(events)
            except Exception:
                pass
        return res


@dataclass(frozen=True)
class PreparedGame:
    """Everything one recorded game needs before the engine is asked anything."""

    game_id: str
    scenario: FutureXmageScenario
    decks: tuple[RulesDeckInput, ...]
    pilots: tuple[FullGamePilotBinding, ...]
    header: dict[str, object]


def prepare_game(
    decks: tuple[RulesDeckInput, ...],
    *,
    seed: int,
    game_id: str,
    strategy: str = "generic",
    style: float | None = None,
    seat_styles: Mapping[int, float] | None = None,
) -> PreparedGame:
    """Scenario, pilots and log header of one game. A game played alone and a game played in a
    batch (``play_batch``) are built by this one function, so they cannot differ in setup."""
    own = decks[0]
    if own.deck_hash is None:
        raise ValueError("the own deck has no deck hash")
    pin = canonical_xmage_engine_pin()
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=len(decks),
        seat=1,
        scenario_id=f"studio-game-{game_id}",
        seed=seed,
        xmage_commit=pin,
        bridge_version=BRIDGE_VERSION,
        pilot_identity=PILOT_IDENTITY,
        pilot_version=PILOT_VERSION,
        decision_policy_version=POLICY_VERSION,
    )
    seat_details = []
    pilots_list = []
    for seat, deck in enumerate(decks, start=1):
        seat_style = (seat_styles or {}).get(seat, style if style is not None else 0.5)
        plan = derive_deck_plan(deck)
        seat_details.append((deck, seat_style, plan))
        pilots_list.append(
            FullGamePilotBinding(
                seat=seat,
                deck_id=deck.deck_id,
                strategy=strategy,
                commander_names=deck.commander_names,
                config=PilotConfig(
                    pilot_name="auto",
                    strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                    mode=PilotDecisionMode.DETERMINISTIC,
                    style=seat_style,
                    weights=style_weights(seat_style),
                    reserve_mana_target=style_reserve_mana(seat_style),
                    deck_plan=plan.as_dict(),
                ),
                pilot_identity=PILOT_IDENTITY,
                pilot_version=PILOT_VERSION,
                decision_policy_version=POLICY_VERSION,
            )
        )
    header: dict[str, object] = {
        "seed": seed,
        "engine_commit": pin,
        "pilot": f"{PILOT_IDENTITY} {PILOT_VERSION}",
        "decision_policy": POLICY_VERSION,
        "strategy": strategy,
        "seats": [
            {
                "seat": index,
                "deck_id": deck.deck_id,
                "commanders": list(deck.commander_names),
                "pilot": "KI",
                "style": s_style,
                "style_name": style_label(s_style),
                "deck_plan": s_plan.as_dict(),
            }
            for index, (deck, s_style, s_plan) in enumerate(seat_details)
        ],
    }
    return PreparedGame(game_id, scenario, decks, tuple(pilots_list), header)


def close_recorded_game(
    recorder: GameRecorder, outcome: FullGameConformanceResult | Exception
) -> dict[str, object]:
    """Write the closing entry of a game log from its outcome and return the short summary."""
    if isinstance(outcome, Exception):
        # run() is behind the public error boundary, so its message carries only a fixed
        # site and audited codes (failure_privacy); it says why the game did not start.
        failure = {
            "status": "failed",
            "failure_class": public_exception_type(outcome),
            "failure_message": public_full_game_exception_message(outcome),
        }
        path = recorder.close(failure)
        return {
            "game_id": recorder.game_id,
            **failure,
            "frames": recorder.frames,
            "log": str(path),
        }
    # the engine counts seats from 1 in its outcome, the board frames count from 0
    winners = [seat - 1 for seat in outcome.winner_seats]
    path = recorder.close(
        {
            "status": "finished",
            "winner_seats": winners,
            "decision_count": outcome.decision_count,
            "engine_version": outcome.engine_version,
            "semantic_transcript_sha256": outcome.semantic_transcript_sha256,
        }
    )
    return {
        "game_id": recorder.game_id,
        "status": "finished",
        "winner_seats": winners,
        "frames": recorder.frames,
        "log": str(path),
    }


def play_recorded_game(
    data_folder: str | Path,
    deck_paths: list[Path],
    *,
    seed: int,
    game_id: str | None = None,
    strategy: str = "generic",
    style: float | None = None,
    seat_styles: Mapping[int, float] | None = None,
    max_decisions: int = 50_000,
    request_timeout_seconds: float = 120.0,
) -> dict[str, object]:
    """Play one game on the configured engine and write its log. Returns a short summary.

    The engine start command comes from the environment as for every full game of the Lab,
    or from the engine file in the Studio data folder.
    A game that fails keeps its log up to the failure, with the public failure class.
    """
    decks = load_decks(deck_paths)
    game = game_id or free_game_id(data_folder, f"{decks[0].deck_id}-{len(decks)}p-seed{seed}")
    prepared = prepare_game(
        decks, seed=seed, game_id=game, strategy=strategy, style=style, seat_styles=seat_styles
    )
    recorder = GameRecorder(data_folder, game, prepared.header)
    runner = _RecordingRunner(
        command=engine_command(data_folder),
        max_decisions=max_decisions,
        request_timeout_seconds=request_timeout_seconds,
    )
    runner.recorder = recorder
    try:
        result = runner.run(scenario=prepared.scenario, decks=decks, pilots=prepared.pilots)
    except Exception as error:
        return close_recorded_game(recorder, error)
    return close_recorded_game(recorder, result)
