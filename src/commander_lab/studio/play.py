"""Play one simulated game with the rules engine and record it for the Studio viewer.

The existing full-game runner does all the work: XMage decides every rule, the Lab's pilots
decide every choice. This module only chooses decks and a seed, lets the runner play, and has
the recorder of ``games.py`` write down what happened. Every seat is a pilot here; a human
seat is a later step.
"""

from __future__ import annotations

from pathlib import Path

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.failure_privacy import (
    public_exception_type,
    public_full_game_exception_message,
)
from commander_lab.engine.rules.full_game import (
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
        if self.recorder is None:
            raise RuntimeError("no recorder bound")
        return RecordingPolicy(policy, self.recorder)

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


def play_recorded_game(
    data_folder: str | Path,
    deck_paths: list[Path],
    *,
    seed: int,
    game_id: str | None = None,
    strategy: str = "generic",
    max_decisions: int = 50_000,
    request_timeout_seconds: float = 120.0,
) -> dict[str, object]:
    """Play one game on the configured engine and write its log. Returns a short summary.

    The engine start command comes from the environment as for every full game of the Lab,
    or from the engine file in the Studio data folder.
    A game that fails keeps its log up to the failure, with the public failure class.
    """
    decks = load_decks(deck_paths)
    own = decks[0]
    if own.deck_hash is None:
        raise ValueError("the own deck has no deck hash")
    pin = canonical_xmage_engine_pin()
    game = game_id or free_game_id(data_folder, f"{own.deck_id}-{len(decks)}p-seed{seed}")
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=len(decks),
        seat=1,
        scenario_id=f"studio-game-{game}",
        seed=seed,
        xmage_commit=pin,
        bridge_version=BRIDGE_VERSION,
        pilot_identity=PILOT_IDENTITY,
        pilot_version=PILOT_VERSION,
        decision_policy_version=POLICY_VERSION,
    )
    pilots = tuple(
        FullGamePilotBinding(
            seat=seat,
            deck_id=deck.deck_id,
            strategy=strategy,
            commander_names=deck.commander_names,
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity=PILOT_IDENTITY,
            pilot_version=PILOT_VERSION,
            decision_policy_version=POLICY_VERSION,
        )
        for seat, deck in enumerate(decks, start=1)
    )
    recorder = GameRecorder(
        data_folder,
        game,
        {
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
                }
                for index, deck in enumerate(decks)
            ],
        },
    )
    runner = _RecordingRunner(
        command=engine_command(data_folder),
        max_decisions=max_decisions,
        request_timeout_seconds=request_timeout_seconds,
    )
    runner.recorder = recorder
    try:
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    except Exception as error:
        # run() is behind the public error boundary, so its message carries only a fixed
        # site and audited codes (failure_privacy); it says why the game did not start.
        failure = {
            "status": "failed",
            "failure_class": public_exception_type(error),
            "failure_message": public_full_game_exception_message(error),
        }
        path = recorder.close(failure)
        return {
            "game_id": game,
            **failure,
            "frames": recorder.frames,
            "log": str(path),
        }
    # the engine counts seats from 1 in its outcome, the board frames count from 0
    winners = [seat - 1 for seat in result.winner_seats]
    path = recorder.close(
        {
            "status": "finished",
            "winner_seats": winners,
            "decision_count": result.decision_count,
            "engine_version": result.engine_version,
        }
    )
    return {
        "game_id": game,
        "status": "finished",
        "winner_seats": winners,
        "frames": recorder.frames,
        "log": str(path),
    }
