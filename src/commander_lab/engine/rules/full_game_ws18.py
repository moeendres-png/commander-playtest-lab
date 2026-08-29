from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from commander_lab.agents import build_pilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import PilotStateView, RulesDeckInput

from .full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    ExternalPilotDecisionPolicy,
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameReplayGate,
    XmageFullGameRunner,
    _RawFullGameClient,
    _RuntimePilot,
)

MIN_PLAYER_COUNT = 2
MAX_PLAYER_COUNT = 5
SUPPORTED_PLAYER_COUNTS = tuple(range(MIN_PLAYER_COUNT, MAX_PLAYER_COUNT + 1))


class FullGamePilotBindingV2(FullGamePilotBinding):
    """WS-18 binding supporting the technical 2P-5P production-candidate surface."""

    seat: int = Field(ge=1, le=MAX_PLAYER_COUNT)


class DynamicExternalPilotDecisionPolicy(ExternalPilotDecisionPolicy):
    """Existing explicit decision policy with cardinality generalized to 2P-5P.

    The inherited decision implementations still choose only among XMage-offered
    option identifiers and preserve the fail-closed unknown-class behavior.
    """

    def __init__(self, runtime_pilots: tuple[_RuntimePilot, ...], scenario_seed: int) -> None:
        count = len(runtime_pilots)
        if count not in SUPPORTED_PLAYER_COUNTS:
            raise ValueError(f"full-game policy requires 2-5 pilot bindings; observed {count}")
        expected = set(range(1, count + 1))
        seats = {item.binding.seat for item in runtime_pilots}
        if seats != expected:
            raise ValueError(
                f"full-game pilot bindings must cover seats 1..{count} exactly; observed {sorted(seats)}"
            )
        self._pilots = {item.binding.seat: item for item in runtime_pilots}
        self.scenario_seed = scenario_seed
        self._mulligan_count = {seat: 0 for seat in expected}

    def _pilot_state(self, runtime: _RuntimePilot, state: dict[str, Any]) -> PilotStateView:
        base = super()._pilot_state(runtime, state)
        configured = int(state.get("player_count", 0))
        if configured not in SUPPORTED_PLAYER_COUNTS:
            players = state.get("players")
            configured = len(players) if isinstance(players, list) else 0
        if configured not in SUPPORTED_PLAYER_COUNTS:
            raise FullGameConformanceError(
                f"actor observation has invalid player_count={configured}"
            )
        opponents = tuple(base.opponents)
        return base.model_copy(
            update={
                "pod_size": configured,
                "opponents_to_act_before_next_turn": len(opponents),
            }
        )


class XmageFullGameRunnerV2:
    """WS-18 2P-5P runner used by the RSP 1.1 candidate provider."""

    def __init__(
        self,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
        max_decisions: int = 50_000,
    ) -> None:
        self.command = command or XmageFullGameRunner.command_from_environment()
        self.cwd = cwd
        self.request_timeout_seconds = request_timeout_seconds
        self.max_decisions = max_decisions
        if self.max_decisions < 1:
            raise ValueError("max_decisions must be positive")

    _deck_payload = staticmethod(XmageFullGameRunner._deck_payload)
    semantic_transcript = staticmethod(XmageFullGameRunner.semantic_transcript)
    _sha256 = staticmethod(XmageFullGameRunner._sha256)

    def run(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBindingV2, ...],
    ) -> FullGameConformanceResult:
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                "full-game bridge is not configured for WS-18 candidate runtime"
            )
        self._validate_inputs_v2(scenario, decks, pilots)
        runtime_pilots = tuple(
            _RuntimePilot(
                binding=binding,
                pilot=build_pilot(binding.config, strategy=binding.strategy),
            )
            for binding in sorted(pilots, key=lambda item: item.seat)
        )
        policy = DynamicExternalPilotDecisionPolicy(runtime_pilots, scenario.seed)

        with _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
        ) as client:
            started = client.request("start_engine")
            if started.get("lane") != FULL_GAME_LANE:
                raise FullGameConformanceError("bridge did not enter explicit full-game lane")
            provider = client.request("get_provider_version")
            capabilities = client.request("get_capabilities")
            self._validate_handshake_v2(scenario, provider, capabilities)

            handles: list[str] = []
            for deck in decks:
                imported = client.request("import_deck", {"deck": self._deck_payload(deck)})
                handle = imported.get("deck_handle")
                if not isinstance(handle, dict):
                    raise FullGameConformanceError("IMPORT_DECK returned no deck_handle")
                handle_id = str(handle.get("handle_id", "")).strip()
                if not handle_id:
                    raise FullGameConformanceError("IMPORT_DECK returned blank handle_id")
                handles.append(handle_id)

            game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
            created = client.request(
                "create_full_game",
                {
                    "game_id": game_id,
                    "deck_handles": handles,
                    "seed": scenario.seed,
                    "starting_player_seat": scenario.seed % scenario.player_count,
                    "starting_life": 40,
                },
            )
            if created.get("player_count") != scenario.player_count:
                raise FullGameConformanceError(
                    "full-game creation did not preserve requested player_count"
                )
            if created.get("seed") != scenario.seed:
                raise FullGameConformanceError("full-game creation did not preserve seed")
            if created.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
                raise FullGameConformanceError("full-game creation returned unsafe evidence class")
            if created.get("holdout_consumed") is not False:
                raise FullGameConformanceError("technical conformance must not consume holdout")

            status = client.request("start_full_game")
            decision_count = 0
            while True:
                failure = status.get("failure")
                if isinstance(failure, dict):
                    raise FullGameConformanceError(
                        "XMage full-game engine failed: " + json.dumps(failure, sort_keys=True)
                    )
                decision = status.get("decision")
                if isinstance(decision, dict):
                    decision_count += 1
                    if decision_count > self.max_decisions:
                        raise FullGameConformanceError(
                            f"full-game exceeded max_decisions={self.max_decisions}"
                        )
                    response = policy.decide(decision)
                    status = client.request(
                        "submit_full_game_decision",
                        {"response": response},
                    )
                    continue
                if bool(status.get("terminal")):
                    break
                status = client.request("get_full_game_decision")

            result = client.request("get_full_game_result")

        return self._build_result_v2(scenario, provider, result)

    def run_replay_gate(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBindingV2, ...],
    ) -> FullGameReplayGate:
        first = self.run(scenario=scenario, decks=decks, pilots=pilots)
        second = self.run(scenario=scenario, decks=decks, pilots=pilots)
        return FullGameReplayGate(
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            semantic_replay_match=(
                first.semantic_transcript_sha256 == second.semantic_transcript_sha256
            ),
            raw_result_match=first.raw_result_sha256 == second.raw_result_sha256,
            first_semantic_sha256=first.semantic_transcript_sha256,
            second_semantic_sha256=second.semantic_transcript_sha256,
            first_raw_sha256=first.raw_result_sha256,
            second_raw_sha256=second.raw_result_sha256,
            bit_exact_replay_validated=False,
        )

    @staticmethod
    def _validate_inputs_v2(
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBindingV2, ...],
    ) -> None:
        count = scenario.player_count
        if count not in SUPPORTED_PLAYER_COUNTS:
            raise FullGameConformanceError(f"unsupported player_count={count}")
        if len(decks) != count or len(pilots) != count:
            raise FullGameConformanceError(
                f"scenario/deck/pilot cardinality mismatch: {count}/{len(decks)}/{len(pilots)}"
            )
        if len({deck.deck_id for deck in decks}) != count:
            raise FullGameConformanceError("full-game requires distinct deck identities per seat")
        if {pilot.seat for pilot in pilots} != set(range(1, count + 1)):
            raise FullGameConformanceError(f"pilot bindings must cover seats 1..{count} exactly")
        ordered_pilots = sorted(pilots, key=lambda item: item.seat)
        for index, (deck, pilot) in enumerate(zip(decks, ordered_pilots, strict=True), start=1):
            if deck.deck_id != pilot.deck_id:
                raise FullGameConformanceError(
                    f"seat {index} deck/pilot mismatch: {deck.deck_id} != {pilot.deck_id}"
                )
            if tuple(deck.commander_names) != tuple(pilot.commander_names):
                raise FullGameConformanceError(f"seat {index} commander/pilot mismatch")
            if deck.deck_hash is None:
                raise FullGameConformanceError(f"seat {index} deck_hash is required")
        own = decks[scenario.seat - 1]
        if own.deck_id != scenario.candidate_id:
            raise FullGameConformanceError(
                "FutureXmageScenario candidate_id must occupy the declared scenario seat"
            )
        if own.deck_hash != scenario.deck_hash:
            raise FullGameConformanceError("FutureXmageScenario deck_hash does not match own deck")
        opponent_ids = tuple(
            deck.deck_id for index, deck in enumerate(decks, start=1) if index != scenario.seat
        )
        if opponent_ids != scenario.opponent_deck_ids:
            raise FullGameConformanceError(
                "FutureXmageScenario opponent_deck_ids do not match seat-ordered opponents"
            )
        own_pilot = ordered_pilots[scenario.seat - 1]
        if own_pilot.pilot_identity != scenario.pilot_identity:
            raise FullGameConformanceError("scenario pilot_identity mismatch")
        if own_pilot.pilot_version != scenario.pilot_version:
            raise FullGameConformanceError("scenario pilot_version mismatch")
        if own_pilot.decision_policy_version != scenario.decision_policy_version:
            raise FullGameConformanceError("scenario decision_policy_version mismatch")

    @staticmethod
    def _validate_handshake_v2(
        scenario: FutureXmageScenario,
        provider: dict[str, Any],
        capabilities_payload: dict[str, Any],
    ) -> None:
        if provider.get("engine") != "xmage":
            raise FullGameConformanceError("full-game provider is not XMage")
        if provider.get("engine_commit") != scenario.xmage_commit:
            raise FullGameConformanceError(
                f"XMage commit mismatch: scenario={scenario.xmage_commit} "
                f"provider={provider.get('engine_commit')}"
            )
        lane = capabilities_payload.get("full_game_lane")
        caps = capabilities_payload.get("capabilities")
        if not isinstance(lane, dict) or not isinstance(caps, dict):
            raise FullGameConformanceError("full-game capability handshake is incomplete")
        if lane.get("lane") != FULL_GAME_LANE:
            raise FullGameConformanceError("full-game lane identity mismatch")
        if lane.get("decision_protocol_version") != FULL_GAME_DECISION_PROTOCOL_VERSION:
            raise FullGameConformanceError("full-game decision protocol mismatch")
        supported = lane.get("supported_player_counts")
        if supported != list(SUPPORTED_PLAYER_COUNTS):
            raise FullGameConformanceError(
                f"full-game supported_player_counts mismatch: {supported!r}"
            )
        if (
            lane.get("min_players") != MIN_PLAYER_COUNT
            or lane.get("max_players") != MAX_PLAYER_COUNT
        ):
            raise FullGameConformanceError("full-game capability cardinality range mismatch")
        if lane.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("full-game capability evidence class is unsafe")
        if lane.get("generic_capability_promotion") is not False:
            raise FullGameConformanceError("full-game lane must not promote generic capabilities")
        if lane.get("one_game_per_process") is not True:
            raise FullGameConformanceError("full-game lane must isolate one game per JVM")
        if lane.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay may not be preclaimed")
        required_true = {
            "commander_supported",
            "partner_supported",
            "multiplayer_supported",
            "headless_supported",
            "seed_supported",
            "deck_import_supported",
            "target_selection_supported",
            "mode_selection_supported",
            "trigger_order_supported",
            "mulligan_supported",
        }
        missing = sorted(name for name in required_true if caps.get(name) is not True)
        if missing:
            raise FullGameConformanceError(
                "full-game lane missing required capabilities: " + ", ".join(missing)
            )

    @classmethod
    def _build_result_v2(
        cls,
        scenario: FutureXmageScenario,
        provider: dict[str, Any],
        result: dict[str, Any],
    ) -> FullGameConformanceResult:
        if result.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("result evidence class is not technical conformance")
        for field in (
            "consumed_gameplay_evidence",
            "holdout_consumed",
            "official_campaign_eligible",
        ):
            if result.get(field) is not False:
                raise FullGameConformanceError(f"unsafe full-game result flag: {field}")
        if result.get("rules_authority") != "xmage":
            raise FullGameConformanceError("result rules authority is not XMage")
        if result.get("decision_policy_authority") != "commander_lab_external_pilot":
            raise FullGameConformanceError("result decision authority is not Commander Lab pilot")
        if result.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay was promoted without gate")
        if result.get("seed") != scenario.seed:
            raise FullGameConformanceError("result seed mismatch")
        if result.get("terminal") is not True:
            raise FullGameConformanceError("XMage full-game did not terminate")
        if result.get("player_count") != scenario.player_count:
            raise FullGameConformanceError("result configured player_count mismatch")

        outcomes = result.get("outcomes")
        if not isinstance(outcomes, list) or len(outcomes) != scenario.player_count:
            raise FullGameConformanceError(
                f"full-game result must contain {scenario.player_count} stable seat outcomes"
            )
        seats = [item.get("seat") for item in outcomes if isinstance(item, dict)]
        if seats != list(range(scenario.player_count)):
            raise FullGameConformanceError(f"stable seat outcome order mismatch: {seats!r}")
        winner_seats = tuple(
            int(item.get("seat", -1)) + 1
            for item in outcomes
            if isinstance(item, dict) and item.get("won") is True
        )
        semantic = cls.semantic_transcript(result)
        return FullGameConformanceResult(
            scenario=scenario,
            engine_version=str(provider.get("engine_version", "unknown")),
            xmage_commit=str(provider.get("engine_commit", "")),
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=int(result.get("decision_count", 0)),
            terminal=True,
            winner_seats=winner_seats,
            result_payload=result,
            semantic_transcript_sha256=cls._sha256(semantic),
            raw_result_sha256=cls._sha256(result),
        )
